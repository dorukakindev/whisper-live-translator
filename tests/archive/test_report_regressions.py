"""Derin raporun dogrulanan bulgulari: ag/cihaz/gercek profil yazimi yok."""
import ast
import json
import os
import re
import subprocess
from pathlib import Path
import tempfile
import threading
import types
import sys
import unittest
from unittest.mock import patch

os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
import buyedektir as b


class ReportRegressions(unittest.TestCase):
    def test_rendered_pages_javascript(self):
        for route in ('/', '/overlay'):
            response = self.client().get(route)
            self.assertEqual(response.status_code, 200)
            blocks = re.findall(r'<script\b[^>]*>(.*?)</script>', response.get_data(as_text=True), re.S)
            self.assertTrue(blocks)
            for code in blocks:
                result = subprocess.run(['node', '--check', '-'], input=code, text=True,
                                        encoding='utf-8', capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_lazy_setup_does_not_restore_cleared_token(self):
        diarizer = b.SpeakerDiarizer.__new__(b.SpeakerDiarizer)
        diarizer._setup_lock = threading.RLock()
        diarizer.hf_token = 'old-test-token'
        diarizer.is_ready = False
        result = []
        with patch.object(diarizer, '_setup_pyannote_unlocked') as setup:
            with diarizer._setup_lock:
                worker = threading.Thread(target=lambda: result.append(diarizer.ensure_ready()))
                worker.start()
                diarizer.hf_token = None
            worker.join(2)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result, [False])
            setup.assert_not_called()

    def client(self):
        client = b.app.test_client()
        client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
        return client

    def test_short_speech_and_script(self):
        for text in ('はい', 'OK', 'No', 'Ne?', '你好', '对', '好', '是', 'Why?', '元気?'):
            self.assertFalse(b.transcriber._is_likely_hallucination(text), text)
        for text in ('...', '!!!', '🎵', 'ご視聴ありがとうございました'):
            self.assertTrue(b.transcriber._is_likely_hallucination(text), text)
        detect = b.transcriber._detect_script_lang
        self.assertEqual(detect('東京大学法学部卒業です'), 'ja')
        self.assertEqual(detect('Γεια σας'), 'el')
        self.assertEqual(detect('Привіт', 'uk'), 'uk')
        self.assertEqual(detect('東京', 'ja'), 'ja')

    def test_short_answer_reaches_mock_provider(self):
        reply = {'response': json.dumps({'options': [
            {'translation': 'Yes', 'turkish': 'Evet', 'romanized': 'yes'}
        ], 'detected_lang': 'en'})}
        responder = b.transcriber.openai_responder
        with patch.object(responder, 'api_key', 'test'), patch.object(responder, 'answer_question', return_value=reply) as call:
            for text in ('Why?', '何?', '好吗?'):
                response = self.client().post('/api/generate_ai_response', json={
                    'text': text, 'mode': 'answer', 'target_lang': 'en'
                }).get_json()
                self.assertTrue(response['success'], response)
                self.assertTrue(response.get('options'), response)
            self.assertEqual(call.call_count, 6)

    def test_deepl_snapshot_endpoint(self):
        translator = b.DeepLTranslator()
        translator.enabled = True
        translator.api_key = 'test-free:fx'
        snapshot = translator.snapshot_request()
        translator.api_key = 'test-pro'
        with patch.object(b._http_session, 'post') as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = {'translations': [{'text': 'Hello'}]}
            translator.translate('Merhaba', request_snapshot=snapshot)
            self.assertEqual(post.call_args.args[0], 'https://api-free.deepl.com/v2/translate')
            translator.translate('Merhaba')
            self.assertEqual(post.call_args.args[0], 'https://api.deepl.com/v2/translate')

    def test_reset_never_persists_token_and_clear_removes_memory_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            diarizer = b.SpeakerDiarizer.__new__(b.SpeakerDiarizer)
            diarizer._profile_lock = threading.RLock()
            diarizer._profile_load_failed = False
            diarizer._setup_lock = threading.Lock()
            diarizer._profile_generation = 0
            diarizer.profile_file = str(Path(temp) / 'profile.json')
            diarizer.speaker_names = {'0': 'Ada'}
            diarizer.hf_token = 'test-token'
            diarizer.reset()
            profile = json.loads(Path(diarizer.profile_file).read_text(encoding='utf-8'))
            self.assertEqual(profile, {'names': {}})
            self.assertEqual(diarizer.hf_token, 'test-token')
            with patch.object(b.transcriber, 'diarizer', diarizer):
                response = self.client().post('/api/hf_token', json={'token': ''})
                self.assertTrue(response.get_json()['cleared'])
            self.assertIsNone(diarizer.hf_token)
            self.assertEqual(
                json.loads(Path(diarizer.profile_file).read_text(encoding='utf-8')),
                {'names': {}}
            )

    def test_resample_identity_and_vad_shapes(self):
        audio = b.np.array([1, -2, 32767], dtype=b.np.int16)
        b.np.testing.assert_array_equal(b._resample_int16(audio, 16000, 16000), audio)
        class FakeVad:
            def is_speech(self, payload, rate):
                self.asserted = len(payload) == 960 and rate == 16000
                if not self.asserted:
                    raise AssertionError('VAD cercevesi bozuk')
                return True
        for size in (1, 479, 480, 481):
            self.assertTrue(b._vad_is_speech(FakeVad(), b.np.ones(size, dtype=b.np.int16), 16000))

    def test_mic_cleanup_exactly_once(self):
        recorder = b.MicRecorder()
        with patch.object(b, 'socketio'):
            from unittest.mock import Mock
            stream, host = Mock(), Mock()
            recorder.stream, recorder.p = stream, host
            workers = [threading.Thread(target=recorder.stop_stream) for _ in range(8)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join(2)
            stream.close.assert_called_once()
            host.terminate.assert_called_once()

    def test_ptt_target_resolution_and_discard(self):
        with patch.object(b.transcriber, 'transcriptions', b.deque()), patch.object(b.transcriber, 'whisper_language', None), patch.object(b.mic_recorder, 'start', return_value=True) as start:
            bad = self.client().post('/api/ptt_mic', json={'active': True, 'target_lang': 'auto'})
            self.assertEqual(bad.status_code, 400)
            start.assert_not_called()
            with patch.object(b.mic_recorder, 'target_lang', None, create=True):
                good = self.client().post('/api/ptt_mic', json={'active': True, 'target_lang': 'ja'})
                self.assertEqual(good.get_json()['target_lang'], 'ja')
                with patch.object(b.mic_recorder, 'stop', return_value=b.np.ones(1)), patch.object(b._mic_executor, 'submit') as submit:
                    self.assertTrue(self.client().post('/api/ptt_mic', json={'active': False, 'discard': True}).get_json()['discarded'])
                    submit.assert_not_called()

    def test_ptt_cancel_before_start_and_stale_stop(self):
        recorder = b.mic_recorder
        with patch.object(recorder, '_cancelled_recordings', b.deque(maxlen=64)), patch.object(recorder, 'recording_id', 'new'), patch.object(recorder, 'start', return_value=True) as start, patch.object(recorder, 'stop') as stop:
            self.client().post('/api/ptt_mic', json={'active': False, 'discard': True, 'recording_id': 'old'})
            stop.assert_not_called()
            response = self.client().post('/api/ptt_mic', json={'active': True, 'target_lang': 'ja', 'recording_id': 'old'})
            self.assertTrue(response.get_json()['discarded'])
            start.assert_not_called()

    def test_overlap_and_worker_tk_boundary(self):
        # App/Tk veya agir model import etmeden gercek fonksiyonun AST'sini calistir.
        source = (Path(__file__).resolve().parents[2] / 'transkribe.py').read_text(
            encoding='utf-8'
        )
        tree = ast.parse(source)
        overlap = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'remove_overlap')
        scope = {}
        exec(compile(ast.Module(body=[overlap], type_ignores=[]), 'transkribe.py', 'exec'), scope)
        self.assertEqual(scope['remove_overlap'](['Bugün dışarı çıkacağız'], 'çık'), 'çık')
        self.assertEqual(scope['remove_overlap'](['bir iki üç'], 'iki üç dört'), 'dört')
        app_class = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        worker = next(node for node in app_class.body if isinstance(node, ast.FunctionDef) and node.name == '_run')
        worker_text = ast.unparse(worker)
        self.assertNotIn('self.after(', worker_text)
        self.assertNotIn('_var.get(', worker_text)

    def test_model_alias(self):
        responder = b.transcriber.openai_responder
        with patch.object(responder, 'response_model', responder.response_model):
            alias = next(iter(responder._legacy_aliases))
            self.assertTrue(responder.set_response_model(alias))
            self.assertEqual(responder.response_model, responder.DEFAULT_MODEL)

    def test_ptt_result_persists_with_unique_id(self):
        transcriber = b.transcriber
        fake_model = types.SimpleNamespace(transcribe=lambda *a, **k: ([types.SimpleNamespace(text='Merhaba')], None))
        snapshot = {'provider': 'deepl', 'enabled': True, 'source_lang': 'TR', 'target_lang': 'EN', 'deepl_api_key': 'test'}
        with patch.object(transcriber, 'current_model', fake_model), patch.object(transcriber, 'transcriptions', b.deque()), patch.object(transcriber, 'conversation_turns', b.deque()), patch.object(transcriber, 'stats', dict(transcriber.stats)), patch.object(transcriber, '_next_transcription_id', 900), patch.object(transcriber.translator, 'translate', return_value='Hello'), patch.object(b, '_append_transcript'), patch.object(b.socketio, 'emit'):
            for _ in range(2):
                b.process_mic_audio(b.np.ones(1600, dtype=b.np.int16), 'en', transcriber._result_generation, snapshot)
            records = self.client().get('/api/transcriptions').get_json()['transcriptions']
            self.assertEqual([record['id'] for record in records], [901, 902])
            self.assertTrue(all(record['source'] == 'ptt' and record['text'] == 'Merhaba' for record in records))
            self.assertEqual(len(transcriber.conversation_turns), 2)

    def test_rename_updates_export_and_event(self):
        records = b.deque([{'id': 1, 'speaker_id': '0', 'speaker_name': 'Eski'}])
        with patch.object(b.transcriber, 'transcriptions', records), patch.object(b.transcriber.diarizer, 'update_speaker_name'), patch.object(b.socketio, 'emit') as emit:
            response = self.client().post('/api/update_speaker_name', json={'speaker_id': '0', 'name': 'Ada'})
            self.assertTrue(response.get_json()['success'])
            self.assertEqual(records[0]['speaker_name'], 'Ada')
            emit.assert_called_with('speaker_updated', {'speaker_id': '0', 'speaker_name': 'Ada'})

    def test_gpu_swap_oom_preserves_working_model(self):
        from unittest.mock import Mock
        old_model = object()
        constructor = Mock(side_effect=RuntimeError('CUDA out of memory'))
        torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: True), zeros=lambda *a, **k: None)
        with patch.dict(sys.modules, {'faster_whisper': types.SimpleNamespace(WhisperModel=constructor), 'torch': torch}), patch.object(b.transcriber, 'current_model', old_model), patch.object(b.socketio, 'emit'):
            result = b.transcriber._load_model_unlocked('large-v3')
            self.assertFalse(result['success'])
            self.assertIs(b.transcriber.current_model, old_model)
            self.assertEqual(constructor.call_count, 1, 'OOM sonrasi sessiz CPU swap yapilmamali')


if __name__ == '__main__':
    unittest.main()
