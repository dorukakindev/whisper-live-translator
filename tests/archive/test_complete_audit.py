"""Tum raporlarin acik kalan yollarina yonelik cihaz/API gerektirmeyen testler."""
import ast
import json
import os
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch

os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
import buyedektir as b


class CompleteAuditTests(unittest.TestCase):
    def test_settings_reject_non_object_without_mutation(self):
        client = b.app.test_client()
        client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
        t = b.transcriber
        before = (t.silence_duration, t.vad_level, t.vad)
        for value in [[], [1], 'text', 1, True, None]:
            with self.subTest(value=value):
                response = client.post('/api/update_settings', data=json.dumps(value), content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()['success'])
                self.assertEqual((t.silence_duration, t.vad_level, t.vad), before)

    def test_settings_scalar_boundary_matrix(self):
        t = b.transcriber
        before = (t.silence_duration, t.vad_level, t.vad)
        try:
            for value in [True, False, None, [], {}, 'abc', -1, 0, 60.0001, float('inf'), float('nan')]:
                with self.subTest(silence=value):
                    t.silence_duration = b.DEFAULTS['silence_duration']
                    t.update_settings({'silence_duration': value})
                    self.assertEqual(t.silence_duration, b.DEFAULTS['silence_duration'])
            for value in [True, False, None, [], {}, 'abc', -1, 4, 99, 1.5, float('inf'), float('nan')]:
                with self.subTest(vad=value):
                    t.update_settings({'vad_level': value})
                    self.assertEqual(t.vad_level, 2)
            for level in range(4):
                t.update_settings({'silence_duration': 60, 'vad_level': level})
                self.assertEqual(t.silence_duration, 60.0)
                self.assertEqual(t.vad_level, level)
        finally:
            t.silence_duration, t.vad_level, t.vad = before

    def test_archive_capture_cleans_up_failed_open_and_bounded_read(self):
        tree = ast.parse(Path('archive/main.py').read_text(encoding='utf-8'))
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_capture')
        host = Mock()
        host.get_device_info_by_index.return_value = {'defaultSampleRate': 16000, 'maxInputChannels': 1}
        host.open.side_effect = OSError('synthetic-open')
        env = {'pyaudio': Mock(PyAudio=Mock(return_value=host)), 'time': Mock(), 'SILENCE_TIMEOUT_MS': 1000}
        exec(compile(ast.Module(body=[func], type_ignores=[]), '<archive-test>', 'exec'), env)
        with self.assertRaises(OSError):
            env['_capture'](Mock(running=True), 0)
        host.terminate.assert_called_once()
        host.reset_mock()
        host.open.side_effect = None
        stream = host.open.return_value
        stream.read.side_effect = OSError('synthetic-disconnect')
        recorder = Mock(running=True)
        env['_capture'](recorder, 0)
        self.assertFalse(recorder.running)
        self.assertEqual(stream.read.call_count, 50)
        self.assertEqual(env['time'].sleep.call_count, 49)
        stream.close.assert_called_once()
        host.terminate.assert_called_once()

    def test_pages_have_compatible_security_headers(self):
        client = b.app.test_client()
        for route in ['/', '/overlay']:
            response = client.get(route)
            self.assertEqual(response.status_code, 200)
            policy = response.headers['Content-Security-Policy']
            self.assertIn("object-src 'none'", policy)
            self.assertIn("script-src 'self' 'unsafe-inline'", policy)
            self.assertIn("ws://127.0.0.1:*", policy)
            self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_eval_uses_real_module_token_without_calling_provider(self):
        tree = ast.parse(Path('test_cevap_onerisi.py').read_text(encoding='utf-8'))
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run_case')
        client = Mock(environ_base={})
        client.post.return_value.get_json.return_value = {'success': False, 'error': 'test'}
        env = {'app': Mock(test_client=Mock(return_value=client)), 'buyedektir': Mock(APP_TOKEN='synthetic-token'), 'check': Mock()}
        exec(compile(ast.Module(body=[func], type_ignores=[]), '<eval-test>', 'exec'), env)
        env['run_case']('ja', 'test', 'arkadasca')
        self.assertEqual(client.environ_base['HTTP_X_WHISPER_TOKEN'], 'synthetic-token')

    def test_queue_full_then_consumer_empty_keeps_new_audio(self):
        t = b.transcriber
        q = Mock()
        q.put_nowait.side_effect = [queue.Full, None]
        q.get_nowait.side_effect = queue.Empty
        with patch.object(t, 'audio_queue', q):
            t._enqueue_audio('new')
        self.assertEqual(q.put_nowait.call_count, 2)

    def test_queue_drops_oldest_and_warns(self):
        t = b.transcriber
        q = queue.Queue(maxsize=2)
        q.put('old'); q.put('middle')
        with patch.object(t, 'audio_queue', q), patch.object(t, 'last_lag_warn_time', -1e20), patch.object(b.socketio, 'emit') as emit:
            t._enqueue_audio('new')
            emit.assert_called_once_with('transcription_lagging', {})
        self.assertEqual([q.get(), q.get()], ['middle', 'new'])

    def test_stale_audio_does_not_run_model(self):
        t = b.transcriber
        q = queue.Queue()
        q.put(b.np.zeros(480, dtype='int16'))
        model = Mock()
        with patch.object(t, 'audio_queue', q), patch.object(t, 'is_running', False), patch.object(t, 'current_model', model), patch.object(t, 'get_context_prompt', return_value=None):
            t._transcribe_audio(t._session_id)
        model.transcribe.assert_not_called()

    def test_rotation_sharing_failure_preserves_backup_and_new_line(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'transcripts.txt'
            path.write_bytes(b'old-text')
            with patch.object(b, 'TRANSCRIPT_FILE', str(path)), patch.object(b, 'TRANSCRIPT_MAX_BYTES', 9), patch.object(b.os, 'replace', side_effect=PermissionError):
                b._append_transcript('new-text')
            self.assertEqual(path.read_bytes(), b'new-text')
            self.assertEqual(Path(str(path) + '.1').read_bytes(), b'old-text')

    def test_phonetic_output_is_not_retransliterated(self):
        for lang, native, expected in [('it', 'giorno', 'corno'), ('es', 'guitarra', 'gitarra'), ('sk', 'džem', 'cem')]:
            first = b._normalize_turkish_pronunciation(native, lang)
            self.assertEqual(first, expected)
            self.assertEqual(b._normalize_turkish_pronunciation(first, lang, phonetic=True), first)
            entries, _ = b._extract_answer_options(json.dumps({'options': [{'translation': native, 'turkish': 'Test', 'romanized': first}]}), lang)
            self.assertEqual(entries[0]['romanized'], expected)

    def test_language_specific_fallbacks(self):
        self.assertEqual(b._normalize_turkish_pronunciation('queso', 'es'), 'keso')
        self.assertEqual(b._normalize_turkish_pronunciation('xin', 'vi'), 'sin')
        self.assertEqual(b._normalize_turkish_pronunciation('obrigado', 'pt'), 'obrigadu')

    def test_short_emphasis_is_not_noise(self):
        for text in ['OK OK OK OK', 'ja ja ja ja', '12345', 'はい', 'Ne?']:
            self.assertFalse(b.transcriber._is_likely_hallucination(text), text)
        self.assertTrue(b.transcriber._is_likely_hallucination('something ' * 9))
        for marker in ['[Musik]', '[音楽]']:
            self.assertTrue(b.transcriber._is_likely_hallucination(marker), marker)

    def test_json_fences(self):
        for fence in ['```', '````']:
            self.assertEqual(json.loads(b._clean_json_object(fence + 'JSON\n{"a":1}\n' + fence)), {'a': 1})

    def test_answer_cap_and_ambiguous_auto_style(self):
        prompts = []
        def answer(prompt, **kwargs):
            prompts.append(prompt)
            return {'response': json.dumps({'options': [{'translation': 'reply' + str(i), 'turkish': 'Anlam', 'romanized': 'test'} for i in range(4)], 'detected_lang': 'en'})}
        client = b.app.test_client()
        client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
        with patch.object(b.transcriber.openai_responder, 'answer_question', side_effect=answer), patch.object(b.socketio, 'emit') as emit:
            result = client.post('/api/generate_ai_response', json={'text': 'Hello', 'mode': 'answer', 'target_lang': 'auto', 'request_id': 'synthetic'}).get_json()
        self.assertTrue(result['success'], result)
        self.assertEqual({o['translation'] for o in result['options']}, {'reply0', 'reply1', 'reply2', 'reply3'})
        for call in emit.call_args_list:
            if call.args[0] == 'ai_options_partial':
                self.assertLessEqual(len(call.args[1]['options']), 2)
        self.assertEqual(len(prompts), 2)
        for prompt in prompts:
            self.assertNotIn(b.SIMPLE_ARABIC_STYLE_RULES, prompt)
            self.assertNotIn(b.SIMPLE_JAPANESE_STYLE_RULES, prompt)

    def test_noise_does_not_evict_streamed_answer_from_final(self):
        entries = [{'translation': '', 'turkish': '[Yanitlanamadi: gurultu]', 'romanized': ''}]
        entries += [{'translation': text, 'turkish': 'Anlam', 'romanized': 'test'} for text in ['first', 'second']]
        raw = json.dumps({'options': entries, 'detected_lang': 'en'})
        client = b.app.test_client()
        client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
        with patch.object(b.transcriber.openai_responder, 'answer_question', return_value={'response': raw}), patch.object(b.socketio, 'emit') as emit:
            result = client.post('/api/generate_ai_response', json={'text': 'Hello', 'mode': 'answer', 'target_lang': 'en', 'request_id': 'synthetic-noise'}).get_json()
        streamed = {o['translation'] for call in emit.call_args_list if call.args[0] == 'ai_options_partial' for o in call.args[1]['options']}
        self.assertEqual(streamed, {'first', 'second'})
        self.assertEqual({o['translation'] for o in result['options']}, streamed)


if __name__ == '__main__':
    unittest.main()
