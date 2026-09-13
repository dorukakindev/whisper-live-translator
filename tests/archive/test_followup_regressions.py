"""Ikinci rapor: ag/cihaz kullanmadan yeni bulgular ve yanlis alarm testleri."""
import ast
from contextlib import ExitStack
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
import buyedektir as b


class FollowupRegressions(unittest.TestCase):
    def client(self):
        client = b.app.test_client()
        client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
        return client

    def test_full_ptt_queue_rejected_before_recording(self):
        slots = threading.BoundedSemaphore(2)
        slots.acquire()
        slots.acquire()
        recorder = b.MicRecorder()
        with patch.object(b, 'mic_recorder', recorder), patch.object(b, '_mic_job_slots', slots), patch.object(recorder, 'start', return_value=True) as start:
            response = self.client().post('/api/ptt_mic', json={'active': True, 'target_lang': 'ja'})
            self.assertEqual(response.status_code, 429)
            start.assert_not_called()

    def test_abandoned_ptt_reservation_is_released(self):
        slots = threading.BoundedSemaphore(1)
        recorder = b.MicRecorder()
        slots.acquire()
        recorder._job_slot_reserved = True
        recorder.recording_id = 'abandoned'
        recorder.is_recording = False
        class ImmediateTimer:
            daemon = False
            def __init__(self, _seconds, callback): self.callback = callback
            def start(self): self.callback()
            def cancel(self): pass
        with patch.object(b, 'mic_recorder', recorder), patch.object(b, '_mic_job_slots', slots), patch.object(b.threading, 'Timer', ImmediateTimer):
            b._schedule_mic_slot_guard('abandoned')
        self.assertFalse(recorder._job_slot_reserved)
        self.assertTrue(slots.acquire(blocking=False))

    def test_unicode_answer_dedup_without_erasing_non_latin(self):
        replies = [('Café', '東京'), ('Cafe\u0301', '大阪')]
        responses = [{'response': json.dumps({'options': [{'translation': text, 'turkish': 'Anlam', 'romanized': ''} for text in pair]})} for pair in replies]
        responder = b.transcriber.openai_responder
        with patch.object(responder, 'api_key', 'test'), patch.object(responder, 'answer_question', side_effect=responses):
            result = self.client().post('/api/generate_ai_response', json={'text': 'Hello', 'mode': 'answer', 'target_lang': 'en'}).get_json()
        self.assertEqual({item['translation'] for item in result['options']}, {'Café', '東京', '大阪'})

    def test_option_retains_its_detected_language(self):
        for lang, reply in [('ja', 'はい'), ('en', 'Yes')]:
            raw = json.dumps({'detected_lang': lang, 'options': [{'translation': reply, 'turkish': 'Evet'}]})
            entries, _ = b._extract_answer_options(raw, 'auto')
            self.assertEqual(entries[0].get('language'), lang)

    def test_stop_does_not_close_a_live_capture_stream(self):
        transcriber = b.transcriber
        stream, host, worker = Mock(), Mock(), Mock()
        worker.is_alive.return_value = True
        with patch.object(transcriber, 'capture_thread', worker), patch.object(transcriber, 'transcribe_thread', None), patch.object(transcriber, '_active_audio_stream', stream), patch.object(transcriber, '_active_audio_p', host), patch.object(transcriber, 'is_running', True), patch.object(transcriber, '_result_generation', 91), patch.object(transcriber, '_drain_audio_queue'):
            transcriber.stop_capture()
            stream.close.assert_not_called()
            host.terminate.assert_not_called()
            self.assertEqual(transcriber._result_generation, 92)

    def test_real_stop_invalidates_old_ptt_result(self):
        transcriber = b.transcriber
        fake_model = types.SimpleNamespace(transcribe=lambda *a, **k: ([types.SimpleNamespace(text='Merhaba')], None))
        def delayed_translation(*args, **kwargs):
            transcriber.stop_capture()
            transcriber._session_id += 1
            return 'Hello'
        with patch.object(transcriber, 'capture_thread', None), patch.object(transcriber, 'transcribe_thread', None), patch.object(transcriber, '_close_active_audio_stream'), patch.object(transcriber, '_drain_audio_queue'), patch.object(transcriber, 'is_running', True), patch.object(transcriber, '_result_generation', 91), patch.object(transcriber, '_session_id', 100), patch.object(transcriber, 'current_model', fake_model), patch.object(transcriber.translator, 'translate', side_effect=delayed_translation), patch.object(b.socketio, 'emit') as emit, patch.object(b, '_append_transcript') as write:
            b.process_mic_audio(b.np.ones(1600, dtype=b.np.int16), 'en', 91, {'provider': 'deepl'})
            emit.assert_not_called()
            write.assert_not_called()

    def test_quiet_split_tiny_buffers(self):
        for count in (0, 1, 5):
            for seconds in (0.001, 0.01, 10):
                buf = [b.np.ones(4, dtype=b.np.float32) for _ in range(count)]
                index = b.transcriber._find_quiet_split_index(buf, seconds)
                self.assertGreaterEqual(index, 0)
                self.assertLessEqual(index, count)

    def test_stale_device_falls_back_by_capture_mode(self):
        class Host:
            def get_device_info_by_index(self, index):
                if index == 99: raise OSError('gone')
                return {0: {'index': 0, 'name': 'Speakers', 'isLoopbackDevice': False},
                        7: {'index': 7, 'name': 'Speakers loopback', 'isLoopbackDevice': True,
                            'maxInputChannels': 2, 'defaultSampleRate': 48000}}[index]
            def get_default_input_device_info(self):
                return {'index': 3, 'name': 'Mic', 'maxInputChannels': 1, 'defaultSampleRate': 44100}
            def get_host_api_info_by_type(self, _kind): return {'defaultOutputDevice': 0}
            def get_loopback_device_info_generator(self):
                return iter([self.get_device_info_by_index(7)])
        transcriber = b.transcriber
        with patch.object(transcriber, 'capture_mode', 'system'):
            self.assertEqual(transcriber._resolve_capture_device(Host(), 99)[0], 7)
        with patch.object(transcriber, 'capture_mode', 'mic'):
            self.assertEqual(transcriber._resolve_capture_device(Host(), 99)[0], 3)

    def test_translation_that_becomes_stale_in_flight_is_not_emitted(self):
        transcriber = b.transcriber
        records = b.deque([{'id': 10, 'text': 'eski'}])
        def slow_result(*args, **kwargs):
            transcriber._latest_translate_submit_id = 20
            return 'old result'
        with patch.object(transcriber, 'transcriptions', records), patch.object(transcriber, '_latest_translate_submit_id', 10), patch.object(transcriber.translator, 'translate', side_effect=slow_result), patch.object(b.socketio, 'emit') as emit, patch.object(b, '_append_transcript') as write:
            transcriber._translate_async(10, 'eski', {'target_lang': 'TR'}, transcriber._session_id, transcriber._result_generation)
            self.assertNotIn('translation', records[0])
            emit.assert_not_called()
            write.assert_not_called()

    def test_merge_output_does_not_overlap_or_lose_text(self):
        source = (Path(__file__).resolve().parents[2] / 'transkribe.py').read_text(
            encoding='utf-8'
        )
        tree = ast.parse(source)
        funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        app = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        worker = next(node for node in app.body if isinstance(node, ast.FunctionDef) and node.name == '_run')
        scope = {'os': os, 'ExitStack': ExitStack}
        exec(compile(ast.Module(body=funcs + [worker], type_ignores=[]), 'transkribe.py', 'exec'), scope)
        texts = ['Birinci uzun cümle burada bitiyor.', 'İkinci farklı cümle burada bitiyor.', 'Üçüncü ayrı cümle burada bitiyor.']
        segments = [types.SimpleNamespace(start=start, end=end, text=text) for (start, end), text in zip([(0.5, 1.5), (1.2, 1.8), (2.0, 3.0)], texts)]
        noop = lambda *args: None
        fake = types.SimpleNamespace(_models={'fake': 'fake'}, _loaded_model_key=('fake', 'cpu'), _model=types.SimpleNamespace(transcribe=lambda *a, **k: (segments, types.SimpleNamespace(duration=3, language='tr', language_probability=1))), _ui_events=queue.Queue(), _log=noop, _set_status=noop, _set_progress=noop, _set_time=noop)
        with tempfile.TemporaryDirectory() as temp:
            filename = str(Path(temp) / 'audio.wav')
            scope['_run'](fake, filename, {'model': 'fake', 'device': 'CPU', 'lang': 'tr', 'merge': True, 'max_chars': 100, 'srt': True, 'txt': True})
            result = Path(temp, 'audio.srt').read_text(encoding='utf-8')
            cues = result.strip().split('\n\n')
            previous_end = ''
            for cue in cues:
                start, end = cue.splitlines()[1].split(' --> ')
                self.assertGreaterEqual(start, previous_end)
                self.assertLess(start, end)
                previous_end = end
            for text in texts:
                self.assertIn(text, result)


if __name__ == '__main__':
    unittest.main()
