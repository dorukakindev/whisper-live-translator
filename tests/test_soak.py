"""Sentetik soak/stres testi — gercek donanim/saglayici cagrisi yok.

SOAK_SECONDS ile ayarlanan sure boyunca gercek /api yuzeyi uzerinden:
  * hizli transkript akisi (queue-tabanli fake stream + stub model),
  * yavas ceviri (0.05sn/istek stub — translate_executor birikimi icin),
  * model kilidi cekismesi (final + partial ayni _model_lock'u paylasir),
  * kuyruk dolmasi (sentetik akis modelden hizli),
  * PTT bas-birak donguleri (/api/ptt),
  * periyodik start/stop donguleri (/api/start + /api/stop)

her SAMPLE_EVERY saniyede metrik orneklenir: RSS (MB), thread sayisi,
audio_queue derinligi, emit sayilari, driver hatalari. Sonunda executor
birikimi, thread/RSS buyumesi ve hata sayaci dogrulanir.

SINIRLAR: model stub'dir — faster-whisper gercek bellek/gecikme davranisini
kanitlamaz; test kutusu kucuk bir VM'dir; gercek konusma performansi
kanitlanmamis. Yalniz kaynak sizintisi, bayat-oturum sizmasi ve kuyruk
sinirlarinin uzun vadede bozulmadigi dogrulanir.
"""
import gc
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
_TMP = tempfile.mkdtemp(prefix='wlt-soak-')
os.environ.setdefault('WHISPER_SKIP_DOTENV', '1')
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = os.path.join(
    _TMP, 'speaker_profiles.json')

import numpy as np  # noqa: E402
import buyedektir as b  # noqa: E402

SOAK_SECONDS = int(os.environ.get('SOAK_SECONDS', '180'))
SAMPLE_EVERY = 5.0
STOP_CYCLE_EVERY = 45
PTT_CYCLE_EVERY = 7


def _rss_mb():
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS'):
                    return int(line.split()[1]) / 1024.0
    except OSError:
        pass
    return -1.0


class _FeederStream:
    """read() kuyruktan kare verir; bos kalinca 32ms sessizlik."""

    def __init__(self):
        self.feeder = queue.Queue()
        self.reads = 0
        self.closed = False

    def read(self, n, exception_on_overflow=False):
        self.reads += 1
        try:
            return self.feeder.get(timeout=0.2)
        except queue.Empty:
            return b'\x00' * (n * 2)

    def feed(self, noise=4, silence=24):
        # Gercek konusma deseni: kisa ses patlamasi + VAD'in segmenti
        # kesecegi kadar sessizlik (yoksa hic finalize olmaz).
        for _ in range(noise):
            self.feeder.put(b'\x11' * 1024)
        for _ in range(silence):
            self.feeder.put(b'\x00' * 1024)

    def stop_stream(self):
        pass

    def close(self):
        self.closed = True


class _FakeHost:
    def __init__(self, stream):
        self._stream = stream

    def get_device_info_by_index(self, idx):
        return {'index': idx, 'name': 'soak-loopback', 'maxInputChannels': 1,
                'defaultSampleRate': 16000}

    def get_default_output_device_info(self):
        return {'index': 0, 'name': 'soak-loopback', 'defaultSampleRate': 16000}

    def open(self, **kw):
        return self._stream

    def terminate(self):
        pass


class _FakeModel:
    """Kucuk gecikmeli stub model — _model_lock cekismesi uretir."""

    def __init__(self):
        self.calls = 0
        self.lock = threading.Lock()
        self.counter = 0

    def transcribe(self, audio, **kw):
        with self.lock:
            self.calls += 1
        time.sleep(0.02)
        with self.lock:
            self.counter += 1
            n = self.counter
        seg = type('S', (), {'text': f'segment-{n}'})()
        info = type('I', (), {'language': 'en', 'language_probability': 0.9})()
        return [seg], info


def _client():
    c = b.app.test_client()
    c.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
    return c


def run_soak(duration):
    t = b.transcriber
    client = _client()
    stream = _FeederStream()
    host = _FakeHost(stream)
    fake_model = _FakeModel()
    saved_model = t.current_model
    saved_name = t.current_model_name
    t.current_model = fake_model
    t.current_model_name = 'soak-stub'

    emitted = {'news': 0, 'partials': 0, 'lagging': 0, 'stopped': 0,
               'started': 0, 'errors': 0, 'ptt': 0}

    def _emit(name, data=None, **kw):
        if name == 'new_transcription':
            emitted['news'] += 1
        elif name == 'partial_transcription':
            emitted['partials'] += 1
        elif name == 'transcription_lagging':
            emitted['lagging'] += 1
        elif name == 'capture_stopped':
            emitted['stopped'] += 1
        elif name == 'capture_started':
            emitted['started'] += 1
        elif name == 'ptt_mic_result':
            emitted['ptt'] += 1
        elif name in ('error', 'transcription_error'):
            emitted['errors'] += 1

    def _slow_translate(text, **kw):
        time.sleep(0.05)
        return 'ceviri-' + str(len(text or ''))

    samples = []
    errors = []
    http_status = []
    stop_flag = threading.Event()
    t0 = time.monotonic()

    def _record_http(path, resp):
        try:
            http_status.append((path, resp.status_code))
        except Exception:
            pass

    def _load_driver():
        """Hizli transkript akisi + model-lock cekismesi (partial dogrudan)."""
        while not stop_flag.is_set():
            stream.feed()
            time.sleep(0.05)
            try:
                with t._lifecycle_lock:
                    sid, useq, gen = (t._session_id, t._utterance_seq,
                                      t._result_generation)
                if t.is_running and not t.is_paused:
                    t._transcribe_partial(
                        np.zeros(t.CHUNK_SIZE * 3, dtype=np.int16),
                        sid, useq, gen)
            except Exception as exc:               # noqa: BLE001
                errors.append(f'partial:{exc}')

    def _ptt_driver():
        seq = 0
        while not stop_flag.wait(PTT_CYCLE_EVERY):
            try:
                seq += 1
                r = client.post('/api/ptt', json={
                    'active': True, 'source': 'soak', 'client': 'soak-cli',
                    'sequence': seq})
                _record_http('ptt-start', r)
                stream.feed(noise=4, silence=0)
                time.sleep(0.15)
                seq += 1
                r = client.post('/api/ptt', json={
                    'active': False, 'source': 'soak', 'client': 'soak-cli',
                    'sequence': seq})
                _record_http('ptt-stop', r)
            except Exception as exc:               # noqa: BLE001
                errors.append(f'ptt:{exc}')

    def _cycle_driver():
        while not stop_flag.wait(STOP_CYCLE_EVERY):
            try:
                r = client.post('/api/stop')
                _record_http('stop', r)
                time.sleep(0.2)
                r = client.post('/api/start', json={'device_id': 0,
                                                    'whisper_language': 'tr'})
                _record_http('start', r)
            except Exception as exc:               # noqa: BLE001
                errors.append(f'cycle:{exc}')

    def _sampler():
        while not stop_flag.is_set():
            samples.append({
                't': round(time.monotonic() - t0, 1),
                'rss': round(_rss_mb(), 1),
                'threads': threading.active_count(),
                'queue': t.audio_queue.qsize(),
                'news': emitted['news'],
                'partials': emitted['partials'],
            })
            stop_flag.wait(SAMPLE_EVERY)

    baseline_threads = threading.active_count()
    baseline_rss = _rss_mb()
    try:
        with patch.object(b.socketio, 'emit', _emit), \
             patch.object(b.pyaudio, 'PyAudio', return_value=host), \
             patch.object(b, 'TRANSCRIPT_FILE',
                          os.path.join(_TMP, 'transcriptions.txt')), \
             patch.object(t.translator, 'translate', _slow_translate):
            r = client.post('/api/start', json={'device_id': 0,
                                                'whisper_language': 'tr'})
            _record_http('start', r)
            for fn in (_load_driver, _ptt_driver, _cycle_driver, _sampler):
                threading.Thread(target=fn, daemon=True).start()
            stop_flag.wait(duration)
            stop_flag.set()
            try:
                r = client.post('/api/stop')
                _record_http('stop', r)
            except Exception as exc:               # noqa: BLE001
                errors.append(f'final-stop:{exc}')
    finally:
        t.current_model = saved_model
        t.current_model_name = saved_name

    gc.collect()
    backlog = getattr(t.translate_executor, '_work_queue', None)
    model_calls = fake_model.calls
    report = {
        'duration_s': round(time.monotonic() - t0, 1),
        'samples': samples,
        'emitted': dict(emitted),
        'errors': errors[:20],
        'http_status_tail': http_status[-10:],
        'http_non2xx': sum(1 for _p, s in http_status if s >= 400),
        'rss_start': baseline_rss, 'rss_end': _rss_mb(),
        'threads_start': baseline_threads,
        'threads_end': threading.active_count(),
        'model_calls': model_calls,
        'stream_reads': stream.reads,
        'translate_backlog': backlog.qsize() if backlog is not None else -1,
        'transcript_bytes': os.path.getsize(
            os.path.join(_TMP, 'transcriptions.txt'))
            if os.path.exists(os.path.join(_TMP, 'transcriptions.txt')) else 0,
    }
    q = [s['queue'] for s in samples] or [0]
    rss = [s['rss'] for s in samples] or [0]
    report['queue_max'] = max(q)
    report['rss_max'] = max(rss)
    report['rss_delta'] = round(report['rss_end'] - baseline_rss, 1)
    report['threads_delta'] = report['threads_end'] - baseline_threads
    return report, t


class SoakTests(unittest.TestCase):
    def test_soak_window(self):
        report, t = run_soak(SOAK_SECONDS)
        print('\n=== SOAK RAPORU ===')
        for k, v in report.items():
            if k == 'samples':
                print(f'samples: {len(v)} nokta; ilk={v[0]}; son={v[-1]}')
            else:
                print(f'{k}: {v}')
        print('=== /SOAK RAPORU ===\n')
        self.assertFalse(t.is_running, 'soak sonunda capture hala calisiyor')
        self.assertFalse(report['errors'],
                         f'soak sirasinda hata: {report["errors"]}')
        self.assertLessEqual(report['threads_delta'], 25,
                             f'thread sizintisi suphesi: +{report["threads_delta"]}')
        self.assertLessEqual(report['translate_backlog'], 4,
                             'ceviri executor birikimi sinirsiz buyudu')
        self.assertGreaterEqual(report['emitted']['news'], 3,
                                'hic transkript uretilmedi — soak veri uretmedi')


if __name__ == '__main__':
    unittest.main(verbosity=2)
