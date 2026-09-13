"""13 maddelik ek rapor: API/GUI/donanima dokunmadan regresyonlar."""
import ast
import json
import os
from pathlib import Path
import queue
import threading
import unittest
from concurrent.futures import Future
from unittest.mock import patch

os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
import buyedektir as b


class NewReportTests(unittest.TestCase):
    def client(self):
        client = b.app.test_client()
        client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
        return client

    def test_all_post_routes_reject_non_object(self):
        client = self.client()
        paths = [r.rule for r in b.app.url_map.iter_rules() if r.rule.startswith('/api/') and 'POST' in r.methods and not r.arguments]
        self.assertGreater(len(paths), 15)
        for path in paths:
            for value in [[1], [], 'text', True, 1, None]:
                with self.subTest(path=path, value=value):
                    response = client.post(path, data=json.dumps(value), content_type='application/json')
                    self.assertEqual(response.status_code, 400)
                    self.assertFalse(response.get_json()['success'])
        self.assertEqual(b.app.test_client().post('/api/start', json=[1]).status_code, 403)

    def test_empty_models_initialization(self):
        tree = ast.parse(Path('transkribe.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'App')
        init = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        class Base:
            def __getattr__(self, name):
                if name.startswith('_'):
                    raise AttributeError(name)
                return lambda *a, **k: None
        env = {
            'Base': Base, 'queue': queue, 'threading': threading,
            'find_models': lambda: {}, 'detect_device': lambda: ('cpu', 'CPU')
        }
        subset = ast.ClassDef(name='App', bases=[ast.Name(id='Base', ctx=ast.Load())], keywords=[], body=[init], decorator_list=[])
        exec(compile(ast.fix_missing_locations(ast.Module(body=[subset], type_ignores=[])), '<ui-init>', 'exec'), env)
        env['App']._build_ui = lambda self: self._ui_events.put(('log', 'no models'))
        env['App']._drain_ui_events = lambda self: None
        instance = env['App']()
        self.assertEqual(instance._ui_events.get_nowait(), ('log', 'no models'))

    def test_overlap_punctuation_and_meaningful_single_word_deletion(self):
        tree = ast.parse(Path('transkribe.py').read_text(encoding='utf-8'))
        func = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'remove_overlap')
        env = {}
        exec(compile(ast.Module(body=[func], type_ignores=[]), '<overlap>', 'exec'), env)
        overlap = env['remove_overlap']
        self.assertEqual(overlap(['Bugün hava çok güzel.'], 'çok güzel bir gün.'), 'bir gün.')
        self.assertEqual(overlap(['Bugün hava çok güzel.'], 'güzel olduğunu biliyorum.'), 'olduğunu biliyorum.')
        self.assertEqual(overlap(['I am ready.'], 'I agree.'), 'I agree.')

    def test_default_answer_and_dedup_backfill(self):
        responses = [{'response': json.dumps({'options': [{'translation': text, 'turkish': 'Anlam', 'romanized': 'test'} for text in items]})} for items in [('A', 'B'), ('A', 'C', 'D')]]
        class ImmediateExecutor:
            def submit(self, fn, *args, **kwargs):
                future = Future()
                future.set_result(fn(*args, **kwargs))
                return future
        with patch.object(b, '_ai_executor', ImmediateExecutor()), patch.object(b.transcriber.openai_responder, 'api_key', 'synthetic'), patch.object(b.transcriber.openai_responder, 'answer_question', side_effect=responses):
            result = self.client().post('/api/generate_ai_response', json={'text': 'Hello', 'target_lang': 'en'}).get_json()
        self.assertTrue(result['success'], result)
        self.assertEqual({o['translation'] for o in result['options']}, {'A', 'B', 'C', 'D'})

    def test_translation_language_case(self):
        translator = b.transcriber.translator
        snapshot = translator.snapshot_request(source_lang=' tr ', target_lang='TR', provider='openai_official')
        self.assertEqual(snapshot['source_lang'], 'TR')
        with patch.object(translator, '_translate_with_openai') as translate:
            self.assertIsNone(translator.translate('Merhaba', force=True, request_snapshot=snapshot))
            translate.assert_not_called()
        snapshot.update(source_lang='tr', target_lang='ja', openai={'api_key': 'synthetic'})
        with patch.object(translator.openai_responder, 'answer_question', return_value={'response': 'test'}) as answer:
            translator.translate('Merhaba', force=True, request_snapshot=snapshot)
            prompt = answer.call_args.args[0]
            self.assertIn('Türkçe dilinden Japonca diline', prompt)

    def test_chat_preserves_roles_and_names(self):
        records = [{'source': 'mic', 'text': 'Teklifim on', 'speaker_name': 'Ada'}, {'source': 'system', 'text': 'Onaylıyorum'}]
        with patch.object(b.transcriber, 'get_transcriptions_snapshot', return_value=records), patch.object(b.transcriber.openai_responder, 'api_key', 'synthetic'), patch.object(b.transcriber.openai_responder, 'answer_question', return_value={'response': 'test'}) as answer:
            self.assertTrue(self.client().post('/api/ai_chat', json={'action': 'summary'}).get_json()['success'])
            prompt = answer.call_args.args[0]
            self.assertIn('[Ben / Ada]: Teklifim on', prompt)
            self.assertIn('[Karşı taraf]: Onaylıyorum', prompt)

    def test_capture_ptt_requires_running_capture(self):
        with patch.object(b.transcriber, 'is_running', False), patch.object(b.transcriber, 'ptt_active', False):
            self.assertEqual(self.client().post('/api/ptt', json={'active': True}).status_code, 409)
            self.assertFalse(b.transcriber.ptt_active)
            self.assertTrue(self.client().post('/api/ptt', json={'active': False}).get_json()['success'])

    def test_pathological_resample_ratio_is_bounded(self):
        for rate in [8001, 44099, 44101, 47999, 48001, 192001]:
            with self.subTest(rate=rate), patch.object(b, '_resample_filter', wraps=b._resample_filter) as filt:
                count = int(rate * 0.03)
                result = b._resample_int16(b.np.zeros(count, dtype=b.np.int16), rate, 16000)
                up, down = filt.call_args.args
                self.assertLessEqual(max(up, down), 2000)
                self.assertLessEqual(abs(len(result) - 480), 1)
        # Standart oran birebir kalmali; mevcut filtre/kalite sozlesmesini degistirme.
        with patch.object(b, '_resample_filter', wraps=b._resample_filter) as filt:
            b._resample_int16(b.np.zeros(1323, dtype=b.np.int16), 44100, 16000)
            self.assertEqual(filt.call_args.args, (160, 441))

    def test_near_identity_resample_does_not_build_invalid_filter(self):
        audio = b.np.array([-32768, -100, 0, 100, 32767], dtype=b.np.int16)
        for rate in [15999, 16001]:
            with self.subTest(rate=rate), patch.object(b, '_resample_filter') as filt:
                result = b._resample_int16(audio, rate, 16000)
                b.np.testing.assert_array_equal(result, audio)
                self.assertIsNot(result, audio)
                filt.assert_not_called()

    def test_full_supported_rate_approximation_error_bound(self):
        worst = 0.0
        for rate in range(8000, 192001):
            ratio = b.Fraction(16000, rate).limit_denominator(2000)
            worst = max(worst, abs(float(ratio) / (16000 / rate) - 1))
            self.assertLessEqual(ratio.denominator, 2000)
            self.assertLessEqual(ratio.numerator, 4000)
        self.assertLessEqual(worst, 0.000250001)


if __name__ == '__main__':
    unittest.main()
