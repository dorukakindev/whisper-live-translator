"""Çeviri işçisinin gerçek gövdelerini ağ/model yüklemeden sınar."""
import ast
import logging
from pathlib import Path
import threading
import time
from types import SimpleNamespace
import unittest


tree = ast.parse(Path('buyedektir.py').read_text(encoding='utf-8'))
klass = next(n for n in tree.body if isinstance(n, ast.ClassDef)
             and n.name == 'WhisperWebTranscriber')
methods = [n for n in klass.body if isinstance(n, ast.FunctionDef)
           and n.name in {'_translate_async', '_set_translation_status'}]


class TranslationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.metrics = []
        self.lines = []
        self.namespace = dict(
            time=time, logger=logging.getLogger('translation-test'),
            socketio=SimpleNamespace(emit=lambda *args: self.events.append(args)),
            _append_transcript=self.lines.append, _record_health_error=lambda code: None)
        exec(compile(ast.Module(body=methods, type_ignores=[]),
                     'buyedektir.py', 'exec'), self.namespace)
        owner_type = type('Worker', (), {n.name: self.namespace[n.name] for n in methods})
        self.worker = owner_type()
        self.worker.__dict__.update(
            _session_id=1, _result_generation=1, _lifecycle_lock=threading.Lock(),
            _latest_translate_sequence=1, _latest_translate_submit_id=1,
            TRANSLATE_MAX_LAG=5, transcriptions=[{'id': 1}],
            _record_latency=lambda *args: self.metrics.append(args),
            translator=SimpleNamespace(translate=lambda *a, **k: '  Merhaba  '))

    def run_translation(self):
        self.worker._translate_async(1, 'Hello', {'target_lang': 'TR'}, 1, 1, 1)

    def test_success(self):
        self.run_translation()
        self.assertEqual(self.worker.transcriptions[0]['translation'], 'Merhaba')
        self.assertEqual(self.worker.transcriptions[0]['translation_status'], 'done')
        self.assertEqual(len(self.metrics), 1)
        self.assertEqual(len(self.lines), 1)

    def test_stale_results_do_not_change_metrics(self):
        for field in ('_session_id', '_result_generation'):
            with self.subTest(field=field):
                self.setUp()
                def translate(*args, **kwargs):
                    setattr(self.worker, field, 2)
                    return 'Eski sonuç'
                self.worker.translator.translate = translate
                self.run_translation()
                self.assertEqual(self.metrics, [])
                self.assertNotIn('translation', self.worker.transcriptions[0])
                self.assertEqual(self.lines, [])

    def test_delivery_error_keeps_completed_result(self):
        def emit(event, data):
            if event == 'transcription_translation':
                raise RuntimeError('Sentetik bildirim hatası')
        self.namespace['socketio'].emit = emit
        with self.assertLogs('translation-test', level='ERROR'):
            self.run_translation()
        record = self.worker.transcriptions[0]
        self.assertEqual(record['translation_status'], 'done')
        self.assertEqual(record['translation'], 'Merhaba')
        self.assertTrue(self.worker._lifecycle_lock.acquire(blocking=False))
        self.worker._lifecycle_lock.release()

    def test_invalid_provider_results_fail(self):
        for result in ('   ', None, {'text': 'bozuk'}, 42):
            with self.subTest(result=result):
                self.setUp()
                self.worker.translator.translate = lambda *a, **k: result
                self.run_translation()
                self.assertEqual(self.worker.transcriptions[0]['translation_status'], 'failed')
                self.assertNotIn('translation', self.worker.transcriptions[0])
                self.assertEqual(self.lines, [])


if __name__ == '__main__':
    unittest.main()
