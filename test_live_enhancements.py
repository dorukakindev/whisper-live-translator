"""Canlı ses testi, düzeltme ve bağlam için çevrimdışı regresyonlar."""

import os
import tempfile
import unittest
from collections import deque
from unittest.mock import patch

import numpy as np

_private_state = tempfile.TemporaryDirectory(prefix='whisper-live-enhancements-')
os.environ['WHISPER_SKIP_DOTENV'] = '1'
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = os.path.join(_private_state.name, 'speakers.json')

import buyedektir  # noqa: E402


class DeferredExecutor:
    def __init__(self):
        self.jobs = []

    def submit(self, fn, *args, **kwargs):
        self.jobs.append((fn, args, kwargs))


class LiveEnhancementTests(unittest.TestCase):
    def setUp(self):
        self.t = buyedektir.transcriber
        self.client = buyedektir.app.test_client()
        self.client.environ_base['HTTP_X_WHISPER_TOKEN'] = buyedektir.APP_TOKEN
        self.saved = {key: getattr(self.t, key) for key in (
            'transcriptions', 'conversation_turns', 'context_buffer',
            'translate_executor', 'translator', 'translation_context',
            '_session_id', '_result_generation', '_audio_test_active',
            'is_running', '_stop_in_progress', '_latest_translate_submit_id')}
        self.saved_recording = buyedektir.mic_recorder.is_recording
        self.t.transcriptions = deque([{
            'id': 7, 'text': 'eski söz', 'source': 'system', 'revision': 0,
            'translation': 'old translation', 'translation_status': 'done',
            'model_language': 'JA', 'target_lang': 'TR'}])
        self.t.conversation_turns = deque([{'transcript_id': 7, 'role': 'other', 'text': 'eski söz'}])
        self.t.context_buffer = deque(['eski söz'], maxlen=10)
        self.t.translate_executor = DeferredExecutor()
        self.t.translator = type('TranslatorFake', (), {
            'snapshot_request': lambda _, **kw: {'target_lang': kw['target_lang']},
            'translate': lambda _, text, **kw: 'çeviri',
        })()
        self.t.translation_context = True
        self.t._session_id = 9
        self.t._result_generation = 4
        self.t._latest_translate_submit_id = 7
        self.t._audio_test_active = False
        self.t.is_running = False
        self.t._stop_in_progress = False
        buyedektir.mic_recorder.is_recording = False
        self.output = patch.object(buyedektir, '_append_transcript')
        self.output.start()

    def tearDown(self):
        self.output.stop()
        for key, value in self.saved.items():
            setattr(self.t, key, value)
        buyedektir.mic_recorder.is_recording = self.saved_recording

    def test_correction_revisions_context_and_stale_submit(self):
        response = self.client.post('/api/transcriptions/7/correct', json={
            'text': 'yeni söz', 'revision': 0})
        self.assertEqual(response.status_code, 200)
        record = self.t.transcriptions[0]
        self.assertEqual(record['revision'], 1)
        self.assertEqual(record['text'], 'yeni söz')
        self.assertNotIn('translation', record)
        self.assertEqual(record['translation_status'], 'pending')
        self.assertEqual(self.t.conversation_turns[0]['text'], 'yeni söz')
        self.assertEqual(self.t.context_buffer[0], 'yeni söz')
        self.assertEqual(len(self.t.translate_executor.jobs), 1)
        self.assertEqual(self.t.translate_executor.jobs[0][1][-1], 1)
        stale = self.client.post('/api/transcriptions/7/correct', json={
            'text': 'geç gelen', 'revision': 0})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(record['text'], 'yeni söz')
        self.assertEqual(len(self.t.translate_executor.jobs), 1)

    def test_invalid_correction_does_not_mutate(self):
        before = dict(self.t.transcriptions[0])
        for text in ('', 'x' * 4001):
            with self.subTest(length=len(text)):
                response = self.client.post('/api/transcriptions/7/correct', json={
                    'text': text, 'revision': 0})
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.t.transcriptions[0], before)
                self.assertFalse(self.t.translate_executor.jobs)

    def test_stale_translation_skips_provider_before_and_after_call(self):
        calls = []
        self.t.transcriptions[0]['revision'] = 1
        self.t.translator.translate = lambda *args, **kwargs: calls.append(1) or 'çeviri'
        snapshot = {'target_lang': 'TR', 'user_initiated': True}
        self.t._translate_async(7, 'eski', snapshot, 9, 4, transcript_revision=0)
        self.assertFalse(calls)
        def edit_during_request(*args, **kwargs):
            self.t.transcriptions[0]['revision'] = 2
            return 'geç çeviri'
        self.t.translator.translate = edit_during_request
        self.t._translate_async(7, 'yeni', snapshot, 9, 4, transcript_revision=1)
        self.assertNotEqual(self.t.transcriptions[0].get('translation'), 'geç çeviri')

    def test_translation_context_is_prior_bounded_and_optional(self):
        self.t.transcriptions = deque({'id': i, 'source': 'system', 'text': str(i) * 500}
                                      for i in range(1, 6))
        context = self.t.get_translation_context(5)
        self.assertNotIn('1' * 20, context)
        self.assertIn('2' * 20, context)
        self.assertNotIn('5' * 20, context)
        self.assertLessEqual(len(context), 1200)
        self.t.translation_context = False
        self.assertEqual(self.t.get_translation_context(5), '')

    def test_audio_test_invalid_request_never_opens_host(self):
        with patch.object(buyedektir.pyaudio, 'PyAudio') as host:
            for value in (None, -1, True, '1'):
                response = self.client.post('/api/audio_test', json={'device_id': value})
                self.assertEqual(response.status_code, 400)
            host.assert_not_called()

    def test_audio_test_reads_pcm_and_closes_resources(self):
        frames = 800
        pcm = np.zeros(frames, dtype=np.int16).tobytes()
        class Stream:
            closed = False
            def get_read_available(self):
                return frames
            def read(self, count, **kwargs):
                return pcm
            def close(self):
                self.closed = True
        class Host:
            terminated = False
            def get_device_info_by_index(self, index):
                return {'maxInputChannels': 1, 'defaultSampleRate': 16000}
            def open(self, **kwargs):
                return stream
            def terminate(self):
                self.terminated = True
        stream, host = Stream(), Host()
        with patch.object(buyedektir.pyaudio, 'PyAudio', return_value=host):
            response = self.client.post('/api/audio_test', json={'device_id': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['measurement']['status'], 'no_signal')
        self.assertTrue(stream.closed)
        self.assertTrue(host.terminated)
        self.assertFalse(self.t._audio_test_active)

    def test_audio_test_no_frames_is_not_device_failure(self):
        from types import SimpleNamespace
        stream = SimpleNamespace(get_read_available=lambda: 0, close=lambda: None)
        host = SimpleNamespace(
            get_device_info_by_index=lambda _: {'maxInputChannels': 2, 'defaultSampleRate': 44100},
            open=lambda **kwargs: stream, terminate=lambda: None)
        with patch.object(buyedektir.pyaudio, 'PyAudio', return_value=host), \
                patch.object(buyedektir.time, 'monotonic', side_effect=[0, 5]):
            response = self.client.post('/api/audio_test', json={'device_id': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['measurement']['status'], 'no_frames')
        self.assertNotIn('rms_dbfs', response.json['measurement'])
        self.assertFalse(self.t._audio_test_active)

    def test_audio_test_failure_releases_flag_and_host(self):
        class Host:
            terminated = False
            def get_device_info_by_index(self, index):
                raise OSError('fake device error')
            def terminate(self):
                self.terminated = True
        host = Host()
        with patch.object(buyedektir.pyaudio, 'PyAudio', return_value=host):
            response = self.client.post('/api/audio_test', json={'device_id': 2})
        self.assertEqual(response.status_code, 503)
        self.assertTrue(host.terminated)
        self.assertFalse(self.t._audio_test_active)


if __name__ == '__main__':
    unittest.main()
