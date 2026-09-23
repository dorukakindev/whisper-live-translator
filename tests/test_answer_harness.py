"""Cevap-onerisi kalite/latency harness'i — stub'li, deterministik.

/api/generate_ai_response 'answer' modunun sozlesmesini kanitlar:
iki paralel provider cagrisi (_ai_executor) -> cagri-bazli
'ai_options_partial' socket emit'i -> birlesim + dedup + gurultu ayiklamasi.

Provider cagrilari `answer_question` seviyesinde sahtelenir (kontrollu uyku +
sabit JSON); socket emit'leri toplayiciyla izlenir. Rastgele sleep YOK — gecikme
iddialari cagri basina sabit uyku uzerinden kesin siniirlarla olculur.

KAPSAM DISI (ayri, opt-in): gercek Anthropic/OpenAI anahtarlariyla latency +
secenek kalite eval'i -> kok dizindeki test_cevap_onerisi.py (~19 golden case,
OPENAI_API_KEY/ANTHROPIC_API_KEY gerekli, gercek API kredisi harcar — CI'a ve
otomatik suite'e GIRMEZ; AGENTS.md 'Testing & validation' bolumune bak).
"""
import json
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_TMP = tempfile.mkdtemp(prefix='wlt-answer-')
os.environ.setdefault('WHISPER_SKIP_DOTENV', '1')
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = os.path.join(
    _TMP, 'speaker_profiles.json')

import buyedektir as b  # noqa: E402
from concurrent.futures import as_completed as _real_as_completed  # noqa: E402


def _client():
    c = b.app.test_client()
    c.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
    return c


def _collect_emits():
    """b.socketio.emit'i yakala; (events, patcher) dondurur."""
    events = []
    lock = threading.Lock()

    def _emit(name, data=None, **kw):
        with lock:
            events.append((name, data))

    return events, patch.object(b.socketio, 'emit', _emit)


def _opts(*pairs):
    """{'response': <json>} — answer_question stub ciktisi. pairs=(tr,tk,rom)."""
    return {'response': json.dumps({
        'detected_lang': 'ja',
        'options': [
            {'turkish': tk, 'translation': tr, 'romanized': rom}
            for tr, tk, rom in pairs
        ]})}


def _stub_calls(delays_and_results, calls):
    """answer_question stub'u: sirayla her cagri icin (sleep, sonuc/exception)."""
    idx = {'n': 0}
    lock = threading.Lock()

    def fake(text, context_list=None, json_mode=False, model_type='response',
             max_tokens=None, **kw):
        with lock:
            i = idx['n']
            idx['n'] += 1
        calls.append({'index': i, 'json_mode': json_mode,
                      'max_tokens': max_tokens})
        delay, result = delays_and_results[i]
        if delay:
            time.sleep(delay)
        if isinstance(result, Exception):
            raise result
        return result

    return fake


def _post_answer(text='Do you want to grab coffee tomorrow?', request_id=''):
    return _client().post('/api/generate_ai_response', json={
        'text': text, 'mode': 'answer', 'target_lang': 'ja',
        'tone': 'arkadasca', 'response_length': 'normal',
        'request_id': request_id})


# Romanize cikti Turkce-okunur ASCII+turkce harfler disinda kalmamali
_ROMAN_OK = re.compile(r"^[a-zçğıöşüA-ZÇĞIÖŞÜ0-9\s\-'?!:;.,/()]*$")


class TestAnswerHarness(unittest.TestCase):

    def test_parallel_latency_bound(self):
        """Iki cagri paralel kosar: toplam sure ~tek cagri, ~iki cagri degil.

        Siraliyken >= 0.8 sn garantili olur; paralelde ~0.45 beklenir.
        """
        calls = []
        stub = _stub_calls([
            (0.4, _opts(('Fine, thanks', 'iyiyim', 'fayn tenks'),
                        ('You?', 'ya sen', 'yuu'))),
            (0.4, _opts(('Sure!', 'olur', 'şor'),
                        ('Where at?', 'nerede', 'ver at'))),
        ], calls)
        events, emit_patch = _collect_emits()
        with patch.object(b.transcriber.openai_responder,
                          'answer_question', stub), emit_patch:
            t0 = time.monotonic()
            resp = _post_answer(request_id='req-par')
            elapsed = time.monotonic() - t0
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body['success'])
        self.assertLess(elapsed, 0.75,
                        f"paralel sinir asildi: {elapsed:.2f}s (sirali >=0.8)")
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(c['json_mode'] for c in calls))
        # Iki cagrinin da secenekleri birlesimde
        turkish = [o['turkish'] for o in body['options']]
        self.assertIn('iyiyim', turkish)
        self.assertIn('olur', turkish)

    def test_partial_emit_order_and_request_id(self):
        """Her biten cagri aninda emit eder: sira=tamamlanma, hepsi request_id'li."""
        calls = []
        stub = _stub_calls([
            (0.35, _opts(('Slow-A1', 'yavas1', 'slowa'))),
            (0.02, _opts(('Fast-B1', 'hizli1', 'fastb'))),
        ], calls)
        events, emit_patch = _collect_emits()
        with patch.object(b.transcriber.openai_responder,
                          'answer_question', stub), emit_patch:
            resp = _post_answer(request_id='req-ord')
        self.assertTrue(resp.get_json()['success'])
        partials = [(n, d) for n, d in events if n == 'ai_options_partial']
        self.assertEqual(len(partials), 2)
        # Hizli biten (ikinci submit edilen) cagri ilk emit'i uretir
        first_turkish = [o['turkish'] for o in partials[0][1]['options']]
        self.assertIn('hizli1', first_turkish)
        for _, data in partials:
            self.assertEqual(data['request_id'], 'req-ord')
            self.assertIn('detected_lang', data)

    def test_no_request_id_still_returns_but_no_partial(self):
        calls = []
        stub = _stub_calls([
            (0.0, _opts(('A', 'bir', 'ey'))),
            (0.0, _opts(('B', 'iki', 'bii'))),
        ], calls)
        events, emit_patch = _collect_emits()
        with patch.object(b.transcriber.openai_responder,
                          'answer_question', stub), emit_patch:
            resp = _post_answer(request_id='')
        self.assertTrue(resp.get_json()['success'])
        self.assertFalse([e for e in events if e[0] == 'ai_options_partial'])

    def test_single_call_failure_resilience(self):
        """Bir cagri patlarsa digerinin secenekleri yine teslim edilir."""
        calls = []
        stub = _stub_calls([
            (0.0, RuntimeError('provider patladi')),
            (0.02, _opts(('Survivor', 'sag-kalan', 'survayvır'),
                         ('Second', 'ikinci', 'sekınd'))),
        ], calls)
        events, emit_patch = _collect_emits()
        with patch.object(b.transcriber.openai_responder,
                          'answer_question', stub), emit_patch:
            resp = _post_answer(request_id='req-fail')
        body = resp.get_json()
        self.assertTrue(body['success'])
        self.assertEqual([o['turkish'] for o in body['options']],
                         ['sag-kalan', 'ikinci'])
        partials = [e for e in events if e[0] == 'ai_options_partial']
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0][1]['options'][0]['turkish'], 'sag-kalan')

    def test_option_contract_dedup_and_charset(self):
        """Sozlesme: <=2/cagri dedup'li benzersiz secenek; rom Turkce charset'i;
        '[Yanitlanamadi' gurultusu ne partial'a ne birlesime duser."""
        calls = []
        stub = _stub_calls([
            (0.0, _opts(('Same opt', 'ayni', 'seym'),
                        ('Unique A', 'tek-a', 'yunik'),
                        ('[Yanitlanamadi]', 'gurultu', ''))),
            (0.0, _opts(('Same opt!', 'ayni-!', 'seym!'),
                        ('Unique B', 'tek-b', 'yunik-bee'))),
        ], calls)
        events, emit_patch = _collect_emits()
        with patch.object(b.transcriber.openai_responder,
                          'answer_question', stub), emit_patch:
            resp = _post_answer(request_id='req-contract')
        body = resp.get_json()
        self.assertTrue(body['success'])
        opts = body['options']
        # 'Same opt' vs 'Same opt!' noktalama-insensitive dedup'a takilir
        self.assertLessEqual(len(opts), 3)
        seen = set()
        for o in opts:
            for key in ('turkish', 'translation', 'romanized', 'language'):
                self.assertIn(key, o)
            self.assertTrue(o['turkish'].strip())
            self.assertFalse(o['turkish'].startswith('[Yanitlanamadi'))
            norm = re.sub(r'[\s.,!?;:…]+', '', o['translation'] or o['turkish'])
            self.assertNotIn(norm, seen)
            seen.add(norm)
            self.assertRegex(o['romanized'], _ROMAN_OK,
                             f"romanized Turkce-okunur disi karakter: {o['romanized']}")
        # Partial emit'lerde gurultu kayit dusmez
        for name, data in events:
            if name == 'ai_options_partial':
                for o in data['options']:
                    self.assertFalse(o['turkish'].startswith('[Yanitlanamadi'))

    def test_stuck_call_timeout_resilience(self):
        """Takilan cagri cevabi kilitlemez: timeout sinirinda digeri doner.

        b.as_completed'i kisaltiilmis-timeout'lu sariciyla sahteleriz — gercek
        as_completed(timeout=0.5) davranisi; takilan 2s'lik cagri iptal edilir.
        """
        calls = []
        stub = _stub_calls([
            (2.0, _opts(('Stuck', 'takilan', 'stak'))),   # zamaninda bitmez
            (0.02, _opts(('OnTime', 'zamaninda', 'ontaym'))),
        ], calls)

        def bounded_as_completed(futures, timeout=None):
            return _real_as_completed(futures, timeout=0.5)

        events, emit_patch = _collect_emits()
        with patch.object(b.transcriber.openai_responder,
                          'answer_question', stub), \
                patch.object(b, 'as_completed', bounded_as_completed), \
                emit_patch:
            t0 = time.monotonic()
            resp = _post_answer(request_id='req-stuck')
            elapsed = time.monotonic() - t0
        body = resp.get_json()
        self.assertTrue(body['success'])
        self.assertLess(elapsed, 1.5,
                        f"takilan cagri cevabi kilitledi: {elapsed:.2f}s")
        self.assertEqual([o['turkish'] for o in body['options']], ['zamaninda'])
        partials = [e for e in events if e[0] == 'ai_options_partial']
        self.assertEqual(len(partials), 1)
        self.assertEqual(partials[0][1]['options'][0]['turkish'], 'zamaninda')


if __name__ == '__main__':
    unittest.main(verbosity=2)
