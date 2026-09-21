"""Deterministik es-zamanlilik / lifecycle / hata-enjeksiyonu audit testleri.

Bu dosya test_smoke.py tarafindan alt surec olarak calistirilir. Donanim
gerektiren yollar (PyAudio akisi, mikrofon thread'i) uygulamanin kendi
arayuzlerinde sahtelenir; kanit olarak rastgele sleep yerine threading.Event,
kontrollu executor'lar ve kilit sondalari kullanilir.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
from collections import deque
from types import SimpleNamespace
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_TMP = tempfile.mkdtemp(prefix='wlt-audit-')
os.environ.setdefault('WHISPER_SKIP_DOTENV', '1')
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = os.path.join(
    _TMP, 'speaker_profiles.json')

import buyedektir as b  # noqa: E402
import numpy as np  # noqa: E402

_MISSING = object()


def _client():
    c = b.app.test_client()
    c.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
    return c


class _Seg:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    """transcribe(): sabit metin dondurur; cagri/enjekte edilen hata izlenir."""

    def __init__(self, text='merhaba dunya nasilsin'):
        self.text = text
        self.calls = 0
        self.error = None

    def transcribe(self, *args, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return (
            [_Seg(self.text)],
            SimpleNamespace(language='tr', language_probability=0.99),
        )


def _collect_emits(watch=()):
    """b.socketio.emit'i yakala. (events, flags, patcher) dondurur;
    flags[name] o isimli ilk emit'te set olan Event'tir."""
    events = []
    flags = {name: threading.Event() for name in watch}

    def _emit(name, data=None, **kw):
        events.append((name, data))
        flag = flags.get(name)
        if flag is not None:
            flag.set()

    return events, flags, patch.object(b.socketio, 'emit', _emit)


class _TranscriberState:
    """Test icin transcriber/mic singleton'larini kontrollu duruma sokar
    ve cikista geri yukler (testler arasi sizinti onlenir)."""

    def __init__(self):
        self.t = b.transcriber
        self.mr = b.mic_recorder
        self._saved = {}

    def __enter__(self):
        t = self.t
        with t._lifecycle_lock:
            self._saved = {
                'is_running': t.is_running,
                'session_id': t._session_id,
                'result_generation': t._result_generation,
                'current_model': t.current_model,
                'current_model_name': t.current_model_name,
                'capture_mode': t.capture_mode,
                'transcriptions': list(t.transcriptions),
                'conversation_turns': list(t.conversation_turns),
                'context_buffer': list(t.context_buffer),
                'next_id': t._next_transcription_id,
                'stats': dict(t.stats),
                'ptt_active': t.ptt_active,
                'ptt_sequences': dict(t._ptt_sequences),
                'ptt_retired': {k: list(v) for k, v in t._ptt_retired_clients.items()},
                'diarizer_enabled': t.diarizer.enabled,
                'speaker_names': dict(t.diarizer.speaker_names),
                'translator_enabled': t.translator.enabled,
                'translator_provider': t.translator.provider,
                'translator_key': t.translator.api_key,
                'translator_source': t.translator.source_lang,
                'translator_target': t.translator.target_lang,
                'audio_test_active': t._audio_test_active,
            }
            t._session_id += 1
            t._result_generation += 1
            t._ptt_sequences.clear()
            t._ptt_retired_clients.clear()
            t.ptt_active = False
            t.current_model = _FakeModel()
            t.current_model_name = 'fake'
            t.capture_mode = 'system'
            t.transcriptions.clear()
            t.conversation_turns.clear()
            t.context_buffer.clear()
            t._audio_test_active = False
            t.is_running = True
        with self.mr._command_lock:
            self._saved_mic = {
                'recording_id': self.mr.recording_id,
                'job_slot_reserved': self.mr._job_slot_reserved,
                'timer': self.mr._slot_reservation_timer,
                'is_recording': self.mr.is_recording,
                'target_lang': getattr(self.mr, 'target_lang', None),
                'cancelled': list(self.mr._cancelled_recordings),
            }
            self.mr.recording_id = None
            self.mr._job_slot_reserved = False
            self.mr._slot_reservation_timer = None
            self.mr.is_recording = False
            self.mr.frames = []
            self.mr._cancelled_recordings.clear()
        return self

    def __exit__(self, *exc):
        t = self.t
        with t._lifecycle_lock:
            s = self._saved
            t.is_running = s['is_running']
            t._session_id = s['session_id']
            t._result_generation = s['result_generation']
            t.current_model = s['current_model']
            t.current_model_name = s['current_model_name']
            t.capture_mode = s['capture_mode']
            t.transcriptions.clear()
            t.transcriptions.extend(s['transcriptions'])
            t.conversation_turns.clear()
            t.conversation_turns.extend(s['conversation_turns'])
            t.context_buffer.clear()
            t.context_buffer.extend(s['context_buffer'])
            t._next_transcription_id = s['next_id']
            t.stats.clear()
            t.stats.update(s['stats'])
            t.ptt_active = s['ptt_active']
            t._ptt_sequences.clear()
            t._ptt_sequences.update(s['ptt_sequences'])
            t._ptt_retired_clients.clear()
            for k, v in s['ptt_retired'].items():
                t._ptt_retired_clients[k] = deque(v, maxlen=64)
            t.diarizer.enabled = s['diarizer_enabled']
            t.diarizer.speaker_names = s['speaker_names']
            t.translator.enabled = s['translator_enabled']
            t.translator.provider = s['translator_provider']
            t.translator.api_key = s['translator_key']
            t.translator.source_lang = s['translator_source']
            t.translator.target_lang = s['translator_target']
            t._audio_test_active = s['audio_test_active']
        with self.mr._command_lock:
            m = self._saved_mic
            self.mr.recording_id = m['recording_id']
            self.mr._job_slot_reserved = m['job_slot_reserved']
            self.mr._slot_reservation_timer = m['timer']
            self.mr.is_recording = m['is_recording']
            self.mr.target_lang = m['target_lang']
            self.mr._cancelled_recordings.clear()
            self.mr._cancelled_recordings.extend(m['cancelled'])
        # Semafor tam kapasiteye getirilir (sizan rezervasyon test zincirini bozmasin).
        for _ in range(2):
            try:
                b._mic_job_slots.release()
            except ValueError:
                break
        return False


def _drive_one_transcription(t, wait_flag=None, timeout=5.0):
    """Kuyruga tek ses parcasi koyar, _transcribe_audio'yu gercek thread'de
    calistirir, wait_flag set olana kadar bekler ve capture'i kapatip join eder."""
    t.audio_queue.put_nowait(np.zeros(16000, dtype=np.int16))
    worker = threading.Thread(
        target=t._transcribe_audio, args=(t._session_id,), daemon=True)
    worker.start()
    if wait_flag is not None:
        assert wait_flag.wait(timeout), 'beklenen socket eventi hic gelmedi'
    with t._lifecycle_lock:
        t.is_running = False
    worker.join(timeout=timeout)
    return worker


# ─────────────────────────────────────────────────────────────────────────────
# PTT sahiplik / siralama (/api/ptt yuzu)
# ─────────────────────────────────────────────────────────────────────────────
class PttOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.t = b.transcriber
        self.client = _client()
        self._state = _TranscriberState().__enter__()
        self.addCleanup(self._state.__exit__, None, None, None)

    def _ptt(self, **kw):
        r = self.client.post('/api/ptt', json=kw)
        return r.status_code, (r.get_json() or {})

    def _set_running(self, value):
        with self.t._lifecycle_lock:
            self.t.is_running = value

    def _reset_ptt(self):
        with self.t._lifecycle_lock:
            self.t._ptt_sequences.clear()
            self.t._ptt_retired_clients.clear()
            self.t.ptt_active = False
            self.t.is_running = True

    # B-1a: sirasiz/bozuk 'sequence' ile gelen BASLATMA sahiplik alamaz,
    # bayragi degistiremez.
    def test_unsequenced_start_never_applies(self):
        code, data = self._ptt(active=True, client='owner', sequence=1)
        self.assertTrue(data['success'])
        self.assertTrue(self.t.ptt_active)
        for bad in (_MISSING, None, '2', 1.5, True, [], {}):
            with self.subTest(sequence=repr(bad)):
                with self.t._lifecycle_lock:
                    self.t.ptt_active = False
                body = {'active': True, 'client': 'intruder', 'source': 'renderer'}
                if bad is not _MISSING:
                    body['sequence'] = bad
                code, data = self._ptt(**body)
                self.assertFalse(
                    self.t.ptt_active,
                    f'sequence={bad!r} ile ptt_active acildi (sahiplik atlandi)')
                self.assertTrue(
                    data.get('stale') or data.get('ptt') is False,
                    f'sirasiz start uygulanmis gorunuyor: {data}')
        # Capture kapaliyken sirasiz start da 409 alir (uygulanmaz).
        self._set_running(False)
        code, data = self._ptt(active=True, client='intruder')
        self.assertEqual(code, 409)
        self.assertFalse(self.t.ptt_active)
        self._set_running(True)
        # Sahiplik hala 'owner'da: sirasiz denemeler kayit defterini bozmadi.
        code, data = self._ptt(active=False, client='owner', sequence=2)
        self.assertTrue(data['success'])
        self.assertFalse(data.get('stale'))
        self.assertFalse(self.t.ptt_active)

    # Sirasiz DURDURMA her zaman uygulanir (telafi stop'lari hic dusurulmez).
    def test_unsequenced_stop_always_applies(self):
        self._ptt(active=True, client='owner', sequence=1)
        self.assertTrue(self.t.ptt_active)
        code, data = self._ptt(active=False, client='stray')
        self.assertTrue(data['success'])
        self.assertFalse(self.t.ptt_active, 'sirasiz stop uygulanmadi')

    # B-1b: reddedilen (409) start sahipligi elden ALMAMALI ve eski sahibi
    # emekliye ayirmamali.
    def test_rejected_start_does_not_steal_ownership(self):
        self._ptt(active=True, client='A', sequence=1)
        self._set_running(False)
        code, data = self._ptt(active=True, client='B', sequence=1)
        self.assertEqual(code, 409)
        self._set_running(True)
        code, data = self._ptt(active=False, client='A', sequence=2)
        self.assertTrue(data['success'])
        self.assertFalse(
            data.get('stale'),
            "B'nin reddedilen start'i A'yi emekliye ayirdi; A kilitlendi")
        self.assertFalse(self.t.ptt_active)
        code, data = self._ptt(active=True, client='A', sequence=3)
        self.assertTrue(data['success'])
        self.assertFalse(data.get('stale'))
        self.assertTrue(self.t.ptt_active)

    # Uc sayfa nesli + reload'da seq=1'e donus.
    def test_three_page_generations_and_sequence_restart(self):
        self._ptt(active=True, client='gen1', sequence=1)
        code, d = self._ptt(active=True, client='gen2', sequence=1)
        self.assertTrue(d['success'])
        self.assertFalse(d.get('stale'), 'yeni sayfa seq=1 ile sahiplik alamadi')
        code, d = self._ptt(active=True, client='gen1', sequence=2)
        self.assertTrue(d.get('stale'), 'emekli gen1 start geri dondu')
        code, d = self._ptt(active=False, client='gen1', sequence=3)
        self.assertTrue(d.get('stale'))
        self.assertTrue(self.t.ptt_active, 'emekli stop aktif PTT yi kapatti')
        code, d = self._ptt(active=True, client='gen3', sequence=1)
        self.assertFalse(d.get('stale'))
        code, d = self._ptt(active=False, client='gen2', sequence=9)
        self.assertTrue(d.get('stale'))
        self.assertTrue(self.t.ptt_active)
        code, d = self._ptt(active=False, client='gen3', sequence=2)
        self.assertFalse(d.get('stale'))
        self.assertFalse(self.t.ptt_active)

    # Kaynak basina sinirsiz buyume: benzersiz 'source' dizgileri haritayi sisemez.
    def test_ptt_bookkeeping_bounded_per_source(self):
        for i in range(24):
            self._ptt(active=True, client=f'c{i}', sequence=1, source=f'flood{i}')
            self._ptt(active=False, client=f'c{i}', sequence=2, source=f'flood{i}')
        self.assertLessEqual(
            len(self.t._ptt_sequences), 16,
            f'_ptt_sequences sinirsiz buyudu: {len(self.t._ptt_sequences)}')
        self.assertLessEqual(
            len(self.t._ptt_retired_clients), 16,
            f'_ptt_retired_clients sinirsiz buyudu: {len(self.t._ptt_retired_clients)}')
        code, d = self._ptt(active=True, client='main', sequence=1, source='renderer')
        self.assertTrue(d['success'])
        self.assertFalse(d.get('stale'))

    # Deterministik komut-sirasi matrisi: (ops, beklenen ptt_active, beklenen sahip).
    def test_ptt_command_order_matrix(self):
        # Her op: (client, 'S' start / 'T' stop). Seq'ler istemci basina artan.
        cases = [
            # Tek istemci temel akislar (6)
            ([('A', 'S')], True, 'A'),
            ([('A', 'S'), ('A', 'T')], False, 'A'),
            ([('A', 'T')], False, 'A'),
            ([('A', 'S'), ('A', 'S')], True, 'A'),
            ([('A', 'S'), ('A', 'T'), ('A', 'T')], False, 'A'),
            ([('A', 'S'), ('A', 'T'), ('A', 'S')], True, 'A'),
            # Iki istemci devralma + emekli korumasi (6)
            ([('A', 'S'), ('B', 'S')], True, 'B'),
            ([('A', 'S'), ('B', 'S'), ('A', 'S')], True, 'B'),
            ([('A', 'S'), ('B', 'S'), ('A', 'T')], True, 'B'),
            ([('A', 'S'), ('B', 'T')], True, 'A'),
            ([('A', 'T'), ('B', 'S')], True, 'B'),
            ([('A', 'S'), ('B', 'S'), ('B', 'T'), ('A', 'S')], False, 'B'),
            # Uc nesil (5)
            ([('A', 'S'), ('B', 'S'), ('C', 'S')], True, 'C'),
            ([('A', 'S'), ('B', 'S'), ('C', 'S'), ('B', 'S')], True, 'C'),
            ([('A', 'S'), ('B', 'S'), ('C', 'S'), ('A', 'T')], True, 'C'),
            ([('A', 'S'), ('B', 'S'), ('C', 'S'), ('C', 'T'), ('C', 'S')], True, 'C'),
            ([('A', 'S'), ('B', 'S'), ('B', 'T'), ('C', 'S'), ('B', 'S')], True, 'C'),
        ]
        for idx, (ops, expected_active, expected_owner) in enumerate(cases):
            with self.subTest(case=idx, ops=ops):
                self._reset_ptt()
                counters = {}
                for client, op in ops:
                    counters[client] = counters.get(client, 0) + 1
                    code, d = self._ptt(
                        active=(op == 'S'), client=client,
                        sequence=counters[client], source='renderer')
                    self.assertEqual(code, 200, f'{ops} -> HTTP {code}')
                self.assertEqual(
                    self.t.ptt_active, expected_active,
                    f'{ops}: ptt_active={self.t.ptt_active} beklenen {expected_active}')
                owner = self.t._ptt_sequences.get('renderer', (None, -1))[0]
                self.assertEqual(
                    owner, expected_owner,
                    f'{ops}: sahip={owner} beklenen {expected_owner}')

    # Property-style: deterministik tohumlu komut dizilerinde invariant'lar:
    # emekli client asla yeniden uygulanamaz, sahip hicbir zaman emekli olamaz.
    def test_ptt_property_interleavings(self):
        import random
        for seed in range(20):
            rng = random.Random(seed)
            self._reset_ptt()
            gens = {'A': 0, 'B': 0, 'N': 0}
            seqs = {'A': 0, 'B': 0, 'N': 0}
            retired_seen = set()
            for step in range(25):
                letter = rng.choice(('A', 'B', 'N'))
                if rng.random() < 0.12:
                    gens[letter] += 1
                    seqs[letter] = 0
                seqs[letter] += 1
                client_id = None if letter == 'N' else f'{letter}g{gens[letter]}'
                active = rng.random() < 0.5
                code, d = self._ptt(
                    active=active, client=client_id,
                    sequence=seqs[letter], source='renderer')
                self.assertEqual(code, 200)
                with self.t._lifecycle_lock:
                    retired = set(self.t._ptt_retired_clients.get('renderer', ()))
                    owner = self.t._ptt_sequences.get('renderer', (None, -1))[0]
                    still_active = self.t.ptt_active
                retired_seen |= retired
                with self.subTest(seed=seed, step=step):
                    self.assertNotIn(owner, retired_seen,
                                     f'sahip {owner} emekli listesinde')
                    if client_id in retired_seen:
                        self.assertTrue(
                            d.get('stale'),
                            f'emekli client {client_id} komutu uygulandi')
                    self.assertIsInstance(still_active, bool)

    # Kaynaklarin seq defterleri karismaz; ortak flag dogru uygulanir.
    def test_cross_source_commands(self):
        self._ptt(active=True, client='r1', sequence=1, source='renderer')
        code, d = self._ptt(active=False, client=None, sequence=1, source='global')
        self.assertTrue(d['success'])
        self.assertFalse(self.t.ptt_active)
        code, d = self._ptt(active=True, client='r1', sequence=2, source='renderer')
        self.assertFalse(d.get('stale'))

    # Client kimlikleri: eksik/bos/devasa/tekrar-eden degerler guvenli islenir.
    def test_client_id_edge_shapes(self):
        self._reset_ptt()
        huge = 'x' * 5000
        code, d = self._ptt(active=True, client=huge, sequence=1)
        self.assertTrue(d['success'])
        self.assertTrue(self.t.ptt_active)
        # Bos string client -> None'a normalize; farkli client'tan sayilir.
        code, d = self._ptt(active=False, client='', sequence=1)
        self.assertTrue(d['stale'], 'bos client ile foreign stop reddedilmedi')
        self.assertTrue(self.t.ptt_active)
        # Ayni truncated client (ilk 64 char): tekrar start ayni sahip olarak okunur.
        code, d = self._ptt(active=False, client=huge, sequence=2)
        self.assertFalse(d.get('stale'))
        self.assertFalse(self.t.ptt_active)


# ─────────────────────────────────────────────────────────────────────────────
# Executor reddi / terminal-sonuc sozlesmesi
# ─────────────────────────────────────────────────────────────────────────────
class ExecutorRejectionTests(unittest.TestCase):
    def setUp(self):
        self.t = b.transcriber
        self._state = _TranscriberState().__enter__()
        self.addCleanup(self._state.__exit__, None, None, None)

    # B-2: translate_executor.submit patlarsa kayit sonsuza kadar
    # 'pending' kalmaz — 'failed' terminal durumu iletilir.
    def test_translate_submit_failure_emits_terminal(self):
        t = self.t
        events, flags, emit_patch = _collect_emits(watch=('new_transcription',))
        with emit_patch, \
                patch.object(b, 'TRANSCRIPT_FILE', os.path.join(_TMP, 't.txt')):
            t.translator.enabled = True
            t.translator.provider = 'deepl'
            t.translator.api_key = 'x'
            t.translator.source_lang = 'TR'
            t.translator.target_lang = 'EN'
            with patch.object(
                    t.translate_executor, 'submit',
                    side_effect=RuntimeError('executor down')):
                worker = _drive_one_transcription(
                    t, wait_flag=flags['new_transcription'])
            self.assertFalse(worker.is_alive(), 'transcribe thread takildi')
            with t._lifecycle_lock:
                self.assertEqual(len(t.transcriptions), 1)
                rec = t.transcriptions[0]
                self.assertEqual(
                    rec.get('translation_status'), 'failed',
                    'submit reddi sonrasi kayit hala: '
                    f'{rec.get("translation_status")!r}')
            statuses = [d for n, d in events if n == 'transcription_translation_status']
            self.assertTrue(
                any(d.get('status') == 'failed' for d in statuses),
                f'failed status event yok: {statuses}')
            self.assertFalse(
                any(n == 'error' for n, _ in events),
                'basarili transkript icin genel hata eventi gitti')

    # B-3: diarize_executor.submit patlarsa kullaniciya 'transkripsiyon hatasi'
    # yayinlanamaz; kayit zaten commit edildi.
    def test_diarize_submit_failure_is_silent(self):
        t = self.t
        events, flags, emit_patch = _collect_emits(watch=('new_transcription',))
        with emit_patch, \
                patch.object(b, 'TRANSCRIPT_FILE', os.path.join(_TMP, 't.txt')):
            t.diarizer.enabled = True
            with patch.object(
                    t.diarize_executor, 'submit',
                    side_effect=RuntimeError('executor down')):
                worker = _drive_one_transcription(
                    t, wait_flag=flags['new_transcription'])
            self.assertFalse(worker.is_alive())
            self.assertFalse(
                any(n == 'error' for n, _ in events),
                'diarize submit hatasi kullaniciya error eventi olarak sizdi')
            self.assertTrue(
                t._diarize_slot.acquire(blocking=False),
                'diarize slot reddi sonrasi serbest kalmadi')
            t._diarize_slot.release()

    # Transkript kaydindan SONRA patlayan executor reddi kaydi guncellemez.
    def test_transcription_committed_before_optional_workers(self):
        t = self.t
        events, flags, emit_patch = _collect_emits(watch=('new_transcription',))
        with emit_patch, \
                patch.object(b, 'TRANSCRIPT_FILE', os.path.join(_TMP, 't.txt')):
            worker = _drive_one_transcription(
                t, wait_flag=flags['new_transcription'])
        self.assertFalse(worker.is_alive())
        with t._lifecycle_lock:
            self.assertEqual(len(t.transcriptions), 1)
            self.assertEqual(t.transcriptions[0]['text'], 'merhaba dunya nasilsin')


# ─────────────────────────────────────────────────────────────────────────────
# Dosya yazimlari yasam-dongusu kilidinin DISINDA olmali (E kapsami)
# ─────────────────────────────────────────────────────────────────────────────
class FileIoOutsideLockTests(unittest.TestCase):
    def setUp(self):
        self.t = b.transcriber
        self._state = _TranscriberState().__enter__()
        self.addCleanup(self._state.__exit__, None, None, None)

    @staticmethod
    def _blocking_append(gate_open, gate_entered):
        def _append(_line):
            gate_entered.set()
            gate_open.wait(10)
        return _append

    def _probe_lock_free(self, lock):
        """Kilit baska thread'de tutulmuyorsa True. Sonda basarisizsa bile
        kilit birakilmis durumda kalir."""
        if lock.acquire(blocking=False):
            lock.release()
            return True
        return False

    def test_transcribe_commit_write_outside_lock(self):
        t = self.t
        entered = threading.Event()
        gate = threading.Event()
        events, flags, emit_patch = _collect_emits()
        with emit_patch, patch.object(b, '_append_transcript',
                                      self._blocking_append(gate, entered)):
            t.audio_queue.put_nowait(np.zeros(16000, dtype=np.int16))
            worker = threading.Thread(
                target=t._transcribe_audio, args=(t._session_id,), daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), 'dosya yazimi hic cagrilmadi')
            lock_held = not self._probe_lock_free(t._lifecycle_lock)
            gate.set()
            with t._lifecycle_lock:
                t.is_running = False
            worker.join(timeout=5)
        self.assertFalse(
            lock_held,
            'yasam-dongusu kilidi dosya yazimi boyunca tutuldu — '
            'stop/reset yavas diskte kilitlenir')
        self.assertFalse(worker.is_alive())

    def test_mic_result_write_outside_lock(self):
        t = self.t
        entered = threading.Event()
        gate = threading.Event()
        events, flags, emit_patch = _collect_emits()
        with emit_patch, \
                patch.object(b, '_append_transcript',
                             self._blocking_append(gate, entered)), \
                patch.object(t.translator, 'translate', return_value='hello'), \
                patch.object(t.openai_responder, 'answer_question',
                             return_value=None):
            req = t.translator.snapshot_request(source_lang='TR', target_lang='EN')
            gen = t._result_generation
            worker = threading.Thread(
                target=b.process_mic_audio,
                args=(np.zeros(16000, dtype=np.int16), 'en', gen, req, 'rid-1'),
                daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), 'mic dosya yazimi hic cagrilmadi')
            lock_held = not self._probe_lock_free(t._lifecycle_lock)
            gate.set()
            worker.join(timeout=5)
        self.assertFalse(
            lock_held,
            'mic commit dosya yazimini kilit altinda yapti')
        self.assertFalse(worker.is_alive())

    def test_translate_append_outside_lock(self):
        t = self.t
        with t._lifecycle_lock:
            t._next_transcription_id += 1
            rec = {'id': t._next_transcription_id, 'revision': 0,
                   'text': 'x', 'translation_status': 'pending'}
            t.transcriptions.append(rec)
            tid, sid, gen = rec['id'], t._session_id, t._result_generation
        entered = threading.Event()
        gate = threading.Event()
        events, flags, emit_patch = _collect_emits()
        with emit_patch, \
                patch.object(b, '_append_transcript',
                             self._blocking_append(gate, entered)), \
                patch.object(t.translator, 'translate', return_value='hello'):
            req = t.translator.snapshot_request()
            req['user_initiated'] = True
            worker = threading.Thread(
                target=t._translate_async,
                args=(tid, 'x', req, sid, gen), kwargs={'transcript_revision': 0},
                daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), 'ceviri dosya yazimi hic cagrilmadi')
            lock_held = not self._probe_lock_free(t._lifecycle_lock)
            gate.set()
            worker.join(timeout=5)
        self.assertFalse(
            lock_held,
            'ceviri kaydi dosya yazimini kilit altinda yapti')
        self.assertFalse(worker.is_alive())

    def test_speaker_profile_write_outside_lock(self):
        d = self.t.diarizer
        entered = threading.Event()
        gate = threading.Event()
        real_replace = os.replace

        def slow_replace(src, dst):
            entered.set()
            gate.wait(10)
            return real_replace(src, dst)

        with patch('os.replace', side_effect=slow_replace):
            worker = threading.Thread(target=d.save_profiles, daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), 'profil yazimi hic cagrilmadi')
            lock_held = not self._probe_lock_free(d._profile_lock)
            gate.set()
            worker.join(timeout=5)
        self.assertFalse(
            lock_held, 'profil kilidi dosya yazimi boyunca tutuldu')
        self.assertFalse(worker.is_alive())

    # E-6b: snapshot alindiktan sonra bloklanan eski yazici, daha yeni bir
    # profil guncellemesinin ustune yazamaz — yazimlar serilestirilmeli.
    def test_profile_save_delayed_writer_cannot_overwrite_newer(self):
        d = self.t.diarizer
        first_in_replace = threading.Event()
        release_first = threading.Event()
        calls = []
        real_replace = os.replace

        def gated_replace(src, dst):
            calls.append(src)
            if len(calls) == 1:
                first_in_replace.set()
                release_first.wait(10)
            return real_replace(src, dst)

        with d._profile_lock:
            d.speaker_names = {'0': 'Eski'}

        with patch('os.replace', side_effect=gated_replace):
            w1 = threading.Thread(target=d.save_profiles, daemon=True)
            w1.start()
            self.assertTrue(
                first_in_replace.wait(5),
                'ilk yazici os.replace icinde bloklanmadi')
            # Eski yazici blokluyken yeni ad ve ikinci kayit cagrisi.
            with d._profile_lock:
                d.speaker_names = {'0': 'Yeni'}
            w2 = threading.Thread(target=d.save_profiles, daemon=True)
            w2.start()
            # Duzeltmesiz kodda w2 hemen tamamlanir (ilk replace'i gecer);
            # duzeltilmis kodda w1 kilidi birakana dek bekler — join burada
            # yalnizca w2'ye ulasmak icin, iddia son satirdaki dosya iceriginde.
            w2.join(timeout=3)
            release_first.set()
            w1.join(timeout=10)
            w2.join(timeout=10)
        self.assertFalse(
            w1.is_alive() or w2.is_alive(),
            'save_profiles cagrilari kilitlerde takili kaldi')
        with open(d.profile_file, 'r', encoding='utf-8') as f:
            final = json.load(f)
        self.assertEqual(
            final.get('names', {}).get('0'), 'Yeni',
            'geciken eski snapshot yeni profil guncellemesini ezdi')


# ─────────────────────────────────────────────────────────────────────────────
# MicRecorder / Alt-PTT yolu
# ─────────────────────────────────────────────────────────────────────────────
class MicRecorderFaultTests(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.t = b.transcriber
        self.mr = b.mic_recorder
        self._state = _TranscriberState().__enter__()
        self.addCleanup(self._state.__exit__, None, None, None)

    # B-6: iptal edilmis recording_id ile gelen start 'success:true' donemez.
    def test_cancelled_recording_id_start_is_rejected(self):
        with self.mr._command_lock:
            self.mr._cancelled_recordings.append('rid-x')
        r = self.client.post('/api/ptt_mic', json={
            'active': True, 'recording_id': 'rid-x', 'target_lang': 'ja'})
        data = r.get_json() or {}
        self.assertFalse(
            data.get('success') and not data.get('error'),
            f'iptal edilmis id ile start false-success dondu: {data}')
        self.assertFalse(self.mr.is_recording, 'iptal edilmis id kayit baslatti')

    # B-4: stream read hatasi kaydi sessizce oldurmemeli; UI'ya error iletilmeli.
    def test_mic_read_failure_notifies_user(self):
        events, flags, emit_patch = _collect_emits(watch=('error',))
        read_gate = threading.Event()

        class _BoomStream:
            def read(self, n, exception_on_overflow=False):
                read_gate.wait(5)
                raise OSError('device vanished')
            def stop_stream(self):
                pass
            def close(self):
                pass

        class _BoomPyAudio:
            def get_device_info_by_index(self, i):
                return {'index': i, 'maxInputChannels': 1,
                        'defaultSampleRate': 16000}
            def get_default_input_device_info(self):
                return self.get_device_info_by_index(0)
            def get_device_count(self):
                return 1
            def open(self, **kw):
                return _BoomStream()
            def terminate(self):
                pass

        fake_module = SimpleNamespace(PyAudio=_BoomPyAudio, paInt16=8)
        rec = b.MicRecorder()
        with emit_patch, patch.dict(sys.modules, {'pyaudiowpatch': fake_module}):
            self.assertTrue(rec.start(device_index=0), 'start() False dondu')
            read_gate.set()
            rec.thread.join(timeout=5)
            self.assertFalse(rec.thread.is_alive(), 'record thread takildi')
            self.assertFalse(rec.is_recording)
        self.assertTrue(
            flags['error'].is_set(),
            'mic okuma hatasi UI ya hic bildirilmedi (sessiz kayit olumu)')

    # B-7: ayni kayit icin en fazla bir terminal event yayinlanir; success emit'i
    # patlarsa bile except kolu ikinci bir sonuc basmaz.
    def test_mic_result_at_most_one_terminal(self):
        t = self.t
        calls = []

        def flaky_emit(name, data=None, **kw):
            if name == 'ptt_mic_result':
                calls.append(data)
                raise RuntimeError('socket kapandi')

        with patch.object(b.socketio, 'emit', flaky_emit), \
                patch.object(b, 'TRANSCRIPT_FILE', os.path.join(_TMP, 't.txt')), \
                patch.object(t.translator, 'translate', return_value='hello'):
            req = t.translator.snapshot_request(source_lang='TR', target_lang='EN')
            try:
                b.process_mic_audio(
                    np.zeros(16000, dtype=np.int16), 'en',
                    t._result_generation, req, 'rid-9')
            except Exception:
                pass  # emit hatasi yukari firlayabilir; onemli olan cagri sayisi
        self.assertEqual(
            len(calls), 1,
            f'tek kayit icin {len(calls)} terminal ptt_mic_result yayinlandi')

    # B-8: kayit sonlandirma komutu islenirken Stop/Reset geldiyse sonuc
    # DOM'a / transcriptions'a / dosyaya yazmamali.
    def test_mic_stop_during_stop_capture_is_stale(self):
        t = self.t
        gate = threading.Event()
        entered = threading.Event()
        audio = np.zeros(16000, dtype=np.int16)

        def gated_stop():
            entered.set()
            gate.wait(10)
            return audio

        events, flags, emit_patch = _collect_emits(watch=('ptt_mic_result',))
        self.assertTrue(b._mic_job_slots.acquire(blocking=False))
        with emit_patch, \
                patch.object(b, 'TRANSCRIPT_FILE', os.path.join(_TMP, 't.txt')), \
                patch.object(t.translator, 'translate', return_value='hello'), \
                patch.object(self.mr, 'stop', gated_stop):
            self.mr.recording_id = 'rid-late'
            self.mr._job_slot_reserved = True
            self.mr.is_recording = True
            self.mr.frames = [np.zeros(10, dtype=np.int16)]
            holder = {}

            def run_cmd():
                holder['resp'] = self.client.post('/api/ptt_mic', json={
                    'active': False, 'recording_id': 'rid-late',
                    'target_lang': 'en'})

            worker = threading.Thread(target=run_cmd, daemon=True)
            worker.start()
            self.assertTrue(entered.wait(5), 'mic stop() hic cagrilmadi')
            # Komut mic_recorder.stop() icinde bloke: capture Stop/Reset gelsin.
            with t._lifecycle_lock:
                t._result_generation += 1
            gate.set()
            worker.join(timeout=5)
        self.assertFalse(worker.is_alive(), 'ptt_mic komutu takildi')
        self.assertTrue(
            flags['ptt_mic_result'].wait(5),
            'mic sonucu icin terminal event hic gelmedi')
        with t._lifecycle_lock:
            self.assertEqual(
                len(t.transcriptions), 0,
                'Stop/Reset sonrasi mic sonucu transcriptions a sizdi')
        stale = [d for n, d in events
                 if n == 'ptt_mic_result' and d and d.get('success') is False]
        self.assertTrue(stale, f'bayat mic sonucu icin stale emit yok: {events}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
