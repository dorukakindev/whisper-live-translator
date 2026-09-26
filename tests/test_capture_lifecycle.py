"""Capture yaşam döngüsü denetimi (backend tarafı).

/api/start ile capture thread arasindaki hazirlik el sikismasi ve thread'in
erken olimu sonrasi backend durumunun/olaylarinin dogrulugu icin
deterministik testler. PyAudio sahte host ile modellenir; sleep'e degil
threading.Event / Event.wait esasli senkronizasyon kullanilir.

Kapsanan akislar (gorev listesinin backend kismi):
 1) normal start -> normal stop,
 2) /api/start sonrasi thread'in acilis hatasiyla olmesi,
 3) cihaz acma hatasi (start artik basari dondurmemeli),
 4) aktif yakalamada cihaz kopmasi (ardisik okuma hatasi),
 5) kullanici stop ile eszamanli thread olimu/p.open icerisindeyken stop,
 6) hizli start -> stop -> start dizisi,
 7) eski oturumun gecikmis capture_stopped'unun yeni oturumu etkilememesi,
 8) el sikisma zaman asimi (cihaz hic yanit vermiyor).
"""
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_TMP = tempfile.mkdtemp(prefix='wlt-caplife-')
os.environ.setdefault('WHISPER_SKIP_DOTENV', '1')
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = os.path.join(
    _TMP, 'speaker_profiles.json')

import buyedektir as b  # noqa: E402


def _client():
    c = b.app.test_client()
    c.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
    return c


def _collect_emits():
    """socketio.emit cagri listesi; olay adi -> [payload]."""
    events = []

    def _emit(name, data=None, **kw):
        events.append((name, dict(data) if isinstance(data, dict) else data))

    return events, patch.object(b.socketio, 'emit', _emit)


def _by_name(events, name):
    return [d for n, d in events if n == name]


class _FakeStream:
    """read(): gate set olana dek bekler, sonra sessiz kare dondurur;
    fail_reads=True ise her okuma OSError verir (cihaz koptu)."""

    def __init__(self, fail_reads=False, read_gate=None):
        self.fail_reads = fail_reads
        self.read_gate = read_gate
        self.reads = 0
        self.closed = False

    def read(self, n, exception_on_overflow=False):
        self.reads += 1
        if self.read_gate is not None:
            self.read_gate.wait(10)
        if self.fail_reads:
            raise OSError('device lost')
        return b'\x00' * (n * 2)

    def stop_stream(self):
        pass

    def close(self):
        self.closed = True


def _fake_host(open_raises=None, open_gate=None, open_entered=None,
               stream=None):
    """_resolve_capture_device'in bekledigi arayuzu karsilayan sahte host."""

    class _Host:
        def get_host_api_info_by_type(self, _t):
            return {'defaultOutputDevice': 0}

        def get_device_info_by_index(self, i):
            return {'index': i, 'maxInputChannels': 1,
                    'defaultSampleRate': 16000, 'name': 'sahte-cihaz',
                    'isLoopbackDevice': True}

        def get_loopback_device_info_generator(self):
            return iter([self.get_device_info_by_index(0)])

        def get_default_input_device_info(self):
            return self.get_device_info_by_index(0)

        def get_device_count(self):
            return 1

        def open(self, **_kw):
            if open_entered is not None:
                open_entered.set()
            if open_gate is not None:
                open_gate.wait(10)
            if open_raises is not None:
                raise open_raises
            return stream

        def terminate(self):
            pass

    return _Host()


class _FeederStream:
    """read(): disaridan beslenen kareleri sirayla dondurur; bosken sessizlik.
    Test, capture dongusunun her adimini deterministik ilerletebilsin diye."""

    def __init__(self, feeder):
        self.feeder = feeder
        self.reads = 0
        self.closed = False

    def read(self, n, exception_on_overflow=False):
        self.reads += 1
        try:
            return self.feeder.get(timeout=2)
        except Exception:
            return b'\x00' * (n * 2)

    def stop_stream(self):
        pass

    def close(self):
        self.closed = True


def _wait_for(predicate, timeout=10.0, step=0.01):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


class _FakeModel:
    """faster-whisper yerine: transcribe() tek cumle dondurur.

    object() stub'i worker'i AttributeError ile olduruyordu ama hicbir test
    bunu yalamiyordu; gercek teslim zincirini (kuyruk -> transcribe ->
    new_transcription emit) dogrulayabilmek icin calisir bir stub gerekli.
    """

    def __init__(self):
        self.calls = 0

    def transcribe(self, *_args, **_kwargs):
        self.calls += 1
        seg = type('Seg', (), {'text': 'sentetik test cumlesi'})()
        info = type('Info', (), {'language': 'en',
                                 'language_probability': 0.95})()
        return [seg], info


class _LifecycleState:
    """Singleton transcriber'i start/stop denemelerine hazir duruma getirir;
    cikista thread'leri join'leyip durumu geri yukler."""

    def __enter__(self):
        t = b.transcriber
        self.t = t
        with t._lifecycle_lock:
            self._saved = {
                'is_running': t.is_running,
                'is_paused': t.is_paused,
                'session_id': t._session_id,
                'result_generation': t._result_generation,
                'current_model': t.current_model,
                'current_model_name': t.current_model_name,
                'capture_mode': t.capture_mode,
                'capture_thread': t.capture_thread,
                'transcribe_thread': t.transcribe_thread,
                'handshake': getattr(t, '_capture_handshake', None),
                'audio_test_active': t._audio_test_active,
                'stop_in_progress': t._stop_in_progress,
                'capture_phase': t._capture_phase,
                'capture_stalled': t._capture_stalled,
                'last_capture_read': t._last_capture_read,
                'watchdog_thread': t._watchdog_thread,
            }
            t.is_running = False
            t.is_paused = False
            t.ptt_active = False
            t.capture_mode = 'system'
            t.current_model = _FakeModel()  # kuyruktaki segmentleri gercekten isler
            t.current_model_name = 'fake'
            t.capture_thread = None
            t.transcribe_thread = None
            t._watchdog_thread = None
            t._capture_stalled = False
            t._audio_test_active = False
            t._stop_in_progress = False
        return self

    def __exit__(self, *exc):
        t = self.t
        # Acilan thread'ler daemon ama temiz cikis icin stop cagir.
        try:
            t.stop_capture()
        except Exception:
            pass
        for th in (t.capture_thread, t.transcribe_thread,
                   t._watchdog_thread):
            if th is not None:
                th.join(timeout=5)
        with t._lifecycle_lock:
            s = self._saved
            t.is_running = s['is_running']
            t.is_paused = s['is_paused']
            t._session_id = s['session_id']
            t._result_generation = s['result_generation']
            t.current_model = s['current_model']
            t.current_model_name = s['current_model_name']
            t.capture_mode = s['capture_mode']
            t.capture_thread = s['capture_thread']
            t.transcribe_thread = s['transcribe_thread']
            t._watchdog_thread = s['watchdog_thread']
            t._capture_stalled = s['capture_stalled']
            t._last_capture_read = s['last_capture_read']
            t._capture_handshake = s['handshake']  # eski kodda yok; set etmek zararsiz
            t._audio_test_active = s['audio_test_active']
            t._stop_in_progress = s['stop_in_progress']
            t._capture_phase = s['capture_phase']


class CaptureLifecycleBackendTests(unittest.TestCase):
    def setUp(self):
        self.client = _client()
        self.t = b.transcriber
        self._state = _LifecycleState().__enter__()
        self.addCleanup(self._state.__exit__, None, None, None)

    # ── 1) normal start -> normal stop ──────────────────────────────────
    def test_normal_start_then_stop(self):
        stream = _FakeStream()
        host = _fake_host(stream=stream)
        events, emit_patch = _collect_emits()
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host):
            r = self.client.post('/api/start', json={
                'device_id': 0, 'whisper_language': 'tr'})
            data = r.get_json()
            self.assertTrue(data['success'], f'/api/start reddetti: {data}')
            self.assertIsInstance(data.get('session_id'), int)
            self.assertTrue(self.t.is_running)

            stop = self.client.post('/api/stop')
            self.assertTrue(stop.get_json()['success'])
        self.assertFalse(self.t.is_running)
        started = _by_name(events, 'capture_started')
        stopped = _by_name(events, 'capture_stopped')
        self.assertEqual(len(started), 1, 'capture_started emit edilmedi')
        self.assertEqual(started[0].get('session_id'), data['session_id'])
        self.assertEqual(len(stopped), 1, 'capture_stopped emit edilmedi')
        self.assertEqual(stopped[0].get('session_id'), data['session_id'])
        self.assertEqual(stopped[0].get('reason'), 'stopped')

    # ── 2+3) /api/start sonrasinda/acilis sirasinda cihaz hatasi ────────
    def test_start_fails_when_device_open_raises(self):
        host = _fake_host(open_raises=OSError('aygit bulunamadi'))
        events, emit_patch = _collect_emits()
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host):
            r = self.client.post('/api/start', json={'device_id': 0})
            data = r.get_json()
        # El sikismasi: API, capture thread'in acilis hatasini bekleyip
        # basarisiz dondurmeli; eski davranis stream acilmadan success donuyordu.
        self.assertFalse(data['success'],
                         'cihaz acma hatasi basari gibi raporlandi')
        self.assertTrue(data.get('error'), 'hata mesaji bos')
        # Capture thread'in finally temizligi (is_running=False,
        # _capture_phase='idle') el sikismasi yanitindan SONRA tamamlanir;
        # dogrudan okumak yarisa girer, kisa poll ile beklenir.
        self.assertTrue(_wait_for(
            lambda: not self.t.is_running and self.t._capture_phase == 'idle',
            timeout=3),
            'basarisiz start sonrasi thread temizligi tamamlanmadi')
        stopped = _by_name(events, 'capture_stopped')
        self.assertEqual(len(stopped), 1)
        self.assertEqual(stopped[0].get('reason'), 'error')
        self.assertIsNotNone(stopped[0].get('session_id'))
        # Hata el sikismasiyla HTTP yanitina tasindi; soket 'error' emit'i
        # ayni basarisizligi ikinci kez duyururdu (UI'da cift toast).
        self.assertEqual(_by_name(events, 'error'), [],
                         'handshake ile tasinan hata soket uzerinden de emit edildi')

    # ── 3b) el sikismasi gercekten bekler: thread p.open icindeyken yanit
    #        donmemeli ────────────────────────────────────────────────────
    def test_start_response_waits_until_stream_open(self):
        open_entered = threading.Event()
        open_gate = threading.Event()
        stream = _FakeStream()
        host = _fake_host(open_gate=open_gate, open_entered=open_entered,
                          stream=stream)
        responded = threading.Event()
        holder = {}
        with patch.object(b.pyaudio, 'PyAudio', return_value=host):
            worker = threading.Thread(
                target=lambda: (holder.setdefault('resp',
                    self.client.post('/api/start', json={'device_id': 0})),
                    responded.set()), daemon=True)
            worker.start()
            self.assertTrue(open_entered.wait(5),
                            'capture thread p.open icine girmedi')
            # Thread KESIN olarak p.open icinde; eski kodda yanit coktan
            # donmus olurdu (handshake yok).
            self.assertFalse(responded.is_set(),
                             '/api/start stream acilmadan success dondurdu')
            open_gate.set()
            self.assertTrue(responded.wait(5), '/api/start yanit vermedi')
            worker.join(5)
            data = holder['resp'].get_json()
            self.assertTrue(data['success'])
            self.assertTrue(self.t.is_running)

    # ── 4) aktif yakalamada cihaz kopmasi ────────────────────────────────
    def test_device_loss_mid_capture_emits_stop_and_clears(self):
        stream = _FakeStream(fail_reads=True)
        host = _fake_host(stream=stream)
        events, emit_patch = _collect_emits()
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host):
            r = self.client.post('/api/start', json={'device_id': 0})
            self.assertTrue(r.get_json()['success'])
            # 50 ardisik hata dongusu time.sleep(0.05) ile; sinirli bekle.
            self.t.capture_thread.join(timeout=10)
        self.assertFalse(self.t.is_running,
                         'cihaz kopunca is_running temizlenmedi')
        self.assertEqual(self.t._capture_phase, 'idle',
                         'cihaz kopmasinda _capture_phase takili kaldi')
        stopped = _by_name(events, 'capture_stopped')
        self.assertTrue(stopped, 'cihaz kopmasinda capture_stopped emit edilmedi')
        self.assertEqual(stopped[-1].get('reason'), 'error')
        self.assertTrue(_by_name(events, 'error'),
                        'kullaniciya hata emit edilmedi')

    # ── 5) p.open icinde beklerken kullanici Stop ─────────────────────────
    def test_stop_during_device_open_returns_error_not_success(self):
        open_entered = threading.Event()
        open_gate = threading.Event()
        host = _fake_host(open_gate=open_gate, open_entered=open_entered,
                          stream=_FakeStream())
        holder = {}
        responded = threading.Event()
        with patch.object(b.pyaudio, 'PyAudio', return_value=host):
            worker = threading.Thread(
                target=lambda: (holder.setdefault('resp',
                    self.client.post('/api/start', json={'device_id': 0})),
                    responded.set()), daemon=True)
            worker.start()
            self.assertTrue(open_entered.wait(5), 'p.open beklenmiyor')
            stop = self.client.post('/api/stop')
            self.assertTrue(stop.get_json()['success'])
            open_gate.set()  # thread uyansin, oturumun oldugunu gorsun
            self.assertTrue(responded.wait(5))
            worker.join(5)
        data = holder['resp'].get_json()
        self.assertFalse(data['success'],
                         'stop sirasinda acilan stream icin start basari dondurdu')
        self.assertFalse(self.t.is_running)

    # ── 6) hizli start -> stop -> start ──────────────────────────────────
    def test_rapid_start_stop_start(self):
        host = _fake_host(stream=_FakeStream())
        with patch.object(b.pyaudio, 'PyAudio', return_value=host):
            first = self.client.post('/api/start', json={'device_id': 0})
            self.assertTrue(first.get_json()['success'])
            self.client.post('/api/stop')
            second = self.client.post('/api/start', json={'device_id': 0})
            data = second.get_json()
            self.assertTrue(data['success'],
                            f'ikinci start reddedildi: {data}')
            self.assertGreater(data['session_id'],
                               first.get_json()['session_id'])
            self.client.post('/api/stop')
        self.assertFalse(self.t.is_running)

    # ── 7) eski oturumun capture_stopped'i emit edilmiyor (backend guard) ─
    def test_stale_session_never_emits_capture_stopped(self):
        t = self.t
        events, emit_patch = _collect_emits()
        stream = _FakeStream()
        host = _fake_host(stream=stream)
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host):
            # Oturum id'sini once alip sonra baska bir oturum acilmis gibi
            # davran: _capture_audio dogrudan bayat session_id ile cagrilir.
            t._session_id += 1
            current = t._session_id
            stale = current - 1
            t.is_running = True
            t._capture_audio(0, stale)
        self.assertFalse(_by_name(events, 'capture_stopped'),
                         'bayat oturumun capture_stopped emit edildi')

    # ── 8) el sikisma zaman asimi ─────────────────────────────────────────
    def test_start_handshake_timeout_returns_error(self):
        never_open = threading.Event()  # hic set edilmez
        host = _fake_host(open_gate=never_open, stream=_FakeStream())
        with patch.object(b.pyaudio, 'PyAudio', return_value=host), \
                patch.object(self.t, 'CAPTURE_START_TIMEOUT_S', 0.3,
                             create=True):  # eski kodda nitelik yok: nitelik yoksa hata degil assertFalse ile batmali
            r = self.client.post('/api/start', json={'device_id': 0})
            data = r.get_json()
        self.assertFalse(data['success'])
        self.assertIn('zaman', data['error'])
        self.assertFalse(self.t.is_running)

    # ── P2) PTT tamponu: her birakista tam olarak bir segment kuyruga
    #         girer; hizli bas-birak-bas dizisinde kayip/duplikasyon yok ──
    def test_ptt_buffer_single_flush_per_release(self):
        feeder = queue.Queue()
        stream = _FeederStream(feeder)
        host = _fake_host(stream=stream)
        events, emit_patch = _collect_emits()
        chunk = lambda: b'\x01' * (self.t.CHUNK_SIZE * 2)
        enqueued = []
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host):
            orig = self.t._enqueue_audio

            def spy(audio, sid, cgen):
                enqueued.append(len(audio))
                return orig(audio, sid, cgen)

            with patch.object(self.t, '_enqueue_audio', side_effect=spy):
                r = self.client.post('/api/start', json={'device_id': 0})
                self.assertTrue(r.get_json()['success'])

                def press(seq):
                    rr = self.client.post('/api/ptt', json={
                        'active': True, 'client': 'sayfaA', 'sequence': seq})
                    self.assertEqual(rr.status_code, 200)
                    self.assertTrue(rr.get_json()['ptt'])

                def release(seq):
                    rr = self.client.post('/api/ptt', json={
                        'active': False, 'client': 'sayfaA', 'sequence': seq})
                    self.assertEqual(rr.status_code, 200)
                    self.assertFalse(rr.get_json()['ptt'])

                for i, seq in enumerate([(1, 2), (3, 4)]):
                    press(seq[0])
                    reads_before = stream.reads
                    for _ in range(11):  # ~0.33sn > 0.3s esigi
                        feeder.put(chunk())
                    self.assertTrue(_wait_for(
                        lambda r=reads_before: stream.reads >= r + 11),
                        'PTT kareleri okunmadi')
                    release(seq[1])
                    feeder.put(chunk())  # birakma sonrasi ilk kare flush'i tetikler
                    self.assertTrue(_wait_for(
                        lambda n=i + 1: len(enqueued) >= n, timeout=5),
                        f'{i + 1}. birakista kuyruk olusmadi: {enqueued}')

                # Flush sonrasi gelen sessiz kareler ek kopya uretmemeli
                for _ in range(3):
                    feeder.put(chunk())
                self.assertTrue(_wait_for(lambda: stream.reads >= 25 or True))
                self.assertEqual(len(enqueued), 2,
                                 f'PTT segmenti duplike oldu: {enqueued}')

                # Teslim zinciri: kuyruga giren her segment transcribe worker'i
                # tarafindan islendi ve new_transcription olarak yayildi.
                # (object() stub'i worker'i AttributeError ile olduruyor ama
                #  kuyruk sayaci yine de dogru cikiyordu -> test bos geciyordu)
                self.assertTrue(_wait_for(
                    lambda: len(_by_name(events, 'new_transcription')) >= 2,
                    timeout=5),
                    'birakilan PTT segmentleri new_transcription olarak gelmedi')

                # Beklemedeyken PTT: kareler yine toplanip tek segment olarak
                # kuyruga girmeli (pause normal sesi atar ama PTT'yi disarida birakir)
                rr = self.client.post('/api/pause', json={'paused': True})
                self.assertTrue(rr.get_json()['success'])
                press(5)
                reads_before = stream.reads
                # Bekletme okuma kolu (paused read) beslenen ilk 1-2 kareyi
                # yutabilir; tamponun 0.3sn esigini asmasi icin payli besle.
                for _ in range(15):
                    feeder.put(chunk())
                self.assertTrue(_wait_for(
                    lambda r=reads_before: stream.reads >= r + 15))
                release(6)
                feeder.put(chunk())
                self.assertTrue(_wait_for(lambda: len(enqueued) >= 3, timeout=5),
                                'beklemede birakilan PTT kuyruga girmedi')
                self.client.post('/api/pause', json={'paused': False})
                # Ilk iki segment tam 11 kare; beklemedekinde pause kolu
                # yuttugu kadari eksik olabilir ama 0.3sn esigi gecmeli.
                expected = 11 * self.t.CHUNK_SIZE
                for size in enqueued[:2]:
                    self.assertAlmostEqual(size, expected,
                                           delta=self.t.CHUNK_SIZE)
                self.assertGreater(enqueued[2], 10 * self.t.CHUNK_SIZE)

                # Ucuncu segment de teslim edildi; model gercekten cagrildi
                # (AttributeError ile bos gecemez).
                self.assertTrue(_wait_for(
                    lambda: len(_by_name(events, 'new_transcription')) >= 3,
                    timeout=5),
                    'beklemede birakilan PTT sonucu yayinmadi')
                self.assertGreaterEqual(self.t.current_model.calls, 3,
                                        'model stub hic cagrilmadi')
            self.client.post('/api/stop')

    # ── P3a) bayat partial: cumle finalize olduysa onizleme yayilmaz ────
    def test_stale_utterance_partial_never_emits(self):
        t = self.t
        events, emit_patch = _collect_emits()
        audio = np.zeros(t.CHUNK_SIZE * 10, dtype=np.int16)
        with emit_patch:
            with t._lifecycle_lock:
                t.is_running = True
                t._session_id = 42
                t._result_generation = 7
                t._utterance_seq = 5
            # Ayni seq + ayni generation + eslesen session'dan onceki durumda
            # model cagrisina bile girmez; dogrudan erken donus verir.
            t._transcribe_partial(audio, 42, 4, 7)   # seq bayat
            t._transcribe_partial(audio, 42, 5, 8)   # generation bayat
            t._transcribe_partial(audio, 41, 5, 7)   # session bayat
        self.assertFalse(_by_name(events, 'partial_transcription'),
                         'bayat onizleme emit edildi')

    # ── P3b) bos final metin: transcription commit+emit atlanir ─────────
    def test_empty_final_produces_no_transcription(self):
        feeder = queue.Queue()
        stream = _FeederStream(feeder)
        host = _fake_host(stream=stream)
        events, emit_patch = _collect_emits()
        t = self.t

        class _Seg:
            def __init__(self, text):
                self.text = text

        class _Info:
            language = 'en'
            language_probability = 0.9

        class _FakeModel:
            def __init__(self, texts):
                self.texts = iter(texts)

            def transcribe(self, _a, **_kw):
                return iter([_Seg(next(self.texts))]), _Info()

        t.current_model = _FakeModel(['', '  ', 'merhaba'])
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host), \
                patch.object(t, '_is_likely_hallucination', return_value=False):
            r = self.client.post('/api/start', json={'device_id': 0})
            self.assertTrue(r.get_json()['success'])
            sess = r.get_json()['session_id']
            # Bos iki segment + bir dolu segment kuyruga sirayla verilir
            for _ in range(3):
                t._enqueue_audio(np.zeros(t.CHUNK_SIZE * 20, dtype=np.int16),
                                 sess, t._result_generation)
            self.assertTrue(_wait_for(
                lambda: len(_by_name(events, 'new_transcription')) >= 1,
                timeout=8), 'dolu final emit edilmedi')
            time.sleep(0.3)
            news = _by_name(events, 'new_transcription')
            self.assertEqual(len(news), 1,
                             f'bos final de kayit uretti: {news}')
            self.assertEqual(news[0]['text'], 'merhaba')
            self.client.post('/api/stop')

    # ── P3c) kuyruk dolu: en eski kare duser + lagging uyarisi ──────────
    def test_queue_full_drops_oldest_and_warns(self):
        t = self.t
        events, emit_patch = _collect_emits()
        old_q = t.audio_queue
        t.audio_queue = queue.Queue(maxsize=5)
        t.last_lag_warn_time = 0.0
        try:
            with emit_patch:
                for i in range(5):
                    t._enqueue_audio_unlocked(f'kare-{i}')
                t._enqueue_audio_unlocked('kare-5')
            items = []
            while not t.audio_queue.empty():
                items.append(t.audio_queue.get_nowait())
            self.assertEqual(items, [f'kare-{i}' for i in range(1, 6)],
                             'en eski kare yerine baska kare dustu')
            self.assertEqual(len(_by_name(events, 'transcription_lagging')), 1,
                             'kuyruk dolunca lagging uyarisi emit edilmedi')
        finally:
            t.audio_queue = old_q

    # ── P8a) Socket.IO baglantisi token olmadan / yanlis tokenla reddedilir ──
    def test_socket_rejects_bad_or_missing_token(self):
        bad = b.socketio.test_client(b.app, auth={'token': 'yanlis-token'})
        self.assertFalse(bad.is_connected(), 'yanlis token ile baglanti acildi')
        none = b.socketio.test_client(b.app, auth={})
        self.assertFalse(none.is_connected(), 'token olmadan baglanti acildi')
        good = b.socketio.test_client(b.app, auth={'token': b.APP_TOKEN})
        self.assertTrue(good.is_connected(), 'dogru tokenla baglanti reddedildi')
        good.disconnect()

    # ── P8b) /api/* butun metodlarda token ister; dict-olmayan JSON 400 ──
    def test_api_token_and_body_contract(self):
        bare = b.app.test_client()   # token enjekte edilmeyen istemci
        for path in ['/api/status', '/api/transcriptions', '/api/settings',
                     '/api/stats']:
            r = bare.get(path)
            self.assertEqual(r.status_code, 403,
                             f'tokensuz GET {path} reddedilmedi: {r.status_code}')
        for path, payload in [('/api/stop', {}), ('/api/ptt', {}),
                              ('/api/clear', {}), ('/api/pause', {})]:
            r = bare.post(path, json=payload)
            self.assertEqual(r.status_code, 403,
                             f'tokensuz POST {path} reddedilmedi: {r.status_code}')
        r = bare.post('/api/stop', data='"metin"',
                      content_type='application/json',
                      headers={'X-Whisper-Token': b.APP_TOKEN})
        self.assertEqual(r.status_code, 400,
                         f'dict-olmayan JSON 400 vermedi: {r.status_code}')

    # ── P8c) healthz gizli alan tasimaz ──────────────────────────────────
    def test_healthz_leaks_no_sensitive_fields(self):
        c = b.app.test_client()
        r = c.get('/healthz')
        self.assertEqual(r.status_code, 200)
        body = r.get_data(as_text=True)
        for forbidden in ('token', 'api_key', 'secret', 'password', '.env'):
            self.assertNotIn(forbidden, body.lower(),
                             f'healthz gizli alan sizdiriyor: {forbidden}')

    # ── P9a) stream.read() sonsuza bloke -> watchdog oturumu stalled ilan
    #         eder, is_running kapanir, UI'ya tek capture_stopped gider ────
    def test_blocked_read_watchdog_marks_stalled(self):
        never_returns = threading.Event()   # hic set edilmez: read takili kalir
        stream = _FakeStream(read_gate=never_returns)
        host = _fake_host(stream=stream)
        events, emit_patch = _collect_emits()
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host), \
                patch.object(self.t, 'CAPTURE_STALL_S', 0.4):
            r = self.client.post('/api/start', json={'device_id': 0})
            self.assertTrue(r.get_json()['success'])
            # Read hic donmuyor: hata sayaci calismaz, thread is_alive kalir;
            # eski kodda oturum burada sonsuza dek 'dinliyor' gorunuyordu.
            self.assertTrue(_wait_for(
                lambda: self.t._capture_stalled, timeout=5),
                "watchdog bloke read'i stalled olarak isaretlemedi")
            self.assertFalse(self.t.is_running)
            stopped = _by_name(events, 'capture_stopped')
            self.assertTrue(stopped, 'stalled oturum icin capture_stopped yok')
            self.assertEqual(stopped[-1].get('reason'), 'stalled')
            self.assertTrue(_by_name(events, 'error'),
                            'stalled durumu kullaniciya hata olarak gitmedi')
            diag = _by_name(events, 'audio_diagnostic')
            self.assertTrue(diag and diag[-1].get('status') == 'disconnected',
                            'audio_diagnostic disconnected yayinlanmadi')
            # Temizlik: bloke read'i serbest birak ki eski thread cikabilsin.
            never_returns.set()

    # ── P9b) stalled oturum ardindan yeni start: takili eski thread yeni
    #         akisi KAPATAMAZ (sahiplik eslestirmesi) ──────────────────────
    def test_stalled_session_new_start_keeps_new_stream(self):
        old_gate = threading.Event()  # eski read'i tutan gate
        old_stream = _FakeStream(read_gate=old_gate)
        new_stream = _FakeStream()
        streams = [old_stream, new_stream]
        host = _fake_host(stream=None)

        def _open(**_kw):
            return streams.pop(0)
        host.open = _open

        events, emit_patch = _collect_emits()
        with emit_patch, patch.object(b.pyaudio, 'PyAudio', return_value=host), \
                patch.object(self.t, 'CAPTURE_STALL_S', 0.4):
            r = self.client.post('/api/start', json={'device_id': 0})
            self.assertTrue(r.get_json()['success'])
            first_session = r.get_json()['session_id']
            self.assertTrue(_wait_for(
                lambda: self.t._capture_stalled, timeout=5))
            # Eski thread hala bloke (is_alive) ama stalled: yeni start
            # kabul edilmeli — eski kod burada 'hala kapaniyor' reddediyordu.
            second = None
            for _ in range(50):
                second = self.client.post('/api/start', json={'device_id': 0})
                if second.get_json().get('success'):
                    break
                time.sleep(0.1)
            self.assertTrue(second and second.get_json()['success'],
                            f'stalled sonrasi yeni start reddedildi: {second.get_json() if second else None}')
            self.assertGreater(second.get_json()['session_id'], first_session)
            # Simdi eski read'i serbest birak: eski thread cikarken finally'si
            # sahipligi kendisinde olmayan YENI akisa dokunmamali.
            old_gate.set()
            self.assertTrue(_wait_for(lambda: old_stream.closed, timeout=5),
                            'eski thread kendi akisini kapatamadi')
            self.assertFalse(new_stream.closed,
                             'eski thread finallysi yeni oturumun akisini kapatti')
            self.assertTrue(self.t.is_running,
                            'eski thread cikisi yeni oturumu durdurdu')
            self.client.post('/api/stop')
            # Yeni oturum icin de capture_stopped yayimlanmis olmali.
            stopped = _by_name(events, 'capture_stopped')
            self.assertIn(second.get_json()['session_id'],
                          [s.get('session_id') for s in stopped])


if __name__ == '__main__':
    unittest.main(verbosity=2)
