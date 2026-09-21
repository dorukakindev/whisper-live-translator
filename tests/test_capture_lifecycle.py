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
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

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
            }
            t.is_running = False
            t.is_paused = False
            t.ptt_active = False
            t.capture_mode = 'system'
            t.current_model = object()  # 'model yuklu' yeterli; transcribe ses gormez
            t.current_model_name = 'fake'
            t.capture_thread = None
            t.transcribe_thread = None
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
        for th in (t.capture_thread, t.transcribe_thread):
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
            t._capture_handshake = s['handshake']  # eski kodda yok; set etmek zararsiz
            t._audio_test_active = s['audio_test_active']
            t._stop_in_progress = s['stop_in_progress']


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
        self.assertFalse(self.t.is_running)
        stopped = _by_name(events, 'capture_stopped')
        self.assertEqual(len(stopped), 1)
        self.assertEqual(stopped[0].get('reason'), 'error')
        self.assertIsNotNone(stopped[0].get('session_id'))

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
                             create=True):  # eski kodda nitelik yok: hata degil assertFalse ile batmali
            r = self.client.post('/api/start', json={'device_id': 0})
            data = r.get_json()
        self.assertFalse(data['success'])
        self.assertIn('zaman', data['error'])
        self.assertFalse(self.t.is_running)


if __name__ == '__main__':
    unittest.main(verbosity=2)
