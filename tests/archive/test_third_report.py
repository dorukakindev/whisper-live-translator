"""Ucuncu rapor: gercek cihaz/ag olmadan hedefli regresyonlar."""
import os
import threading
import unittest
from unittest.mock import Mock, patch

os.environ['WHISPER_SKIP_API_VERIFY'] = '1'
import buyedektir as b


class ThirdReportTests(unittest.TestCase):
    def test_deepl_network_test_does_not_hold_config_lock(self):
        translator = b.transcriber.translator
        entered, release = threading.Event(), threading.Event()
        def slow_test(key):
            self.assertEqual(key, 'test-key')
            entered.set()
            release.wait(3)
            return True
        def request():
            client = b.app.test_client()
            client.environ_base['HTTP_X_WHISPER_TOKEN'] = b.APP_TOKEN
            client.post('/api/deepl_config', json={'provider': 'deepl', 'api_key': 'test-key'})
        with patch.object(translator, 'api_key', None), patch.object(translator, 'provider', 'deepl'), patch.object(translator, 'test_api', side_effect=slow_test):
            worker = threading.Thread(target=request)
            worker.start()
            try:
                self.assertTrue(entered.wait(1))
                acquired = translator._config_lock.acquire(timeout=0.2)
                self.assertTrue(acquired)
                if acquired:
                    translator._config_lock.release()
            finally:
                release.set()
                worker.join(4)

    def test_salvage_literal_braces(self):
        raw = '{"options":[{"translation":"Use {name} here", "turkish":"Adını kullan"}, {"translation":"unfinished'
        options, _ = b._salvage_answer_options(raw)
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]['translation'], 'Use {name} here')

    def test_stop_during_lazy_load_does_not_block_or_restart(self):
        t = b.transcriber
        entered, release = threading.Event(), threading.Event()
        result = []
        def slow_load():
            entered.set()
            release.wait(3)
            return True
        with patch.object(t.diarizer, 'ensure_ready', side_effect=slow_load), patch.object(t, '_result_generation', 100), patch.object(t, 'capture_thread', None), patch.object(t, 'transcribe_thread', None), patch.object(t, 'is_running', False), patch.object(t, '_close_active_audio_stream'), patch.object(t, '_drain_audio_queue'):
            worker = threading.Thread(target=lambda: result.append(t.start_capture(speaker_diarization=True)))
            worker.start()
            try:
                self.assertTrue(entered.wait(1))
                acquired = t._lifecycle_lock.acquire(timeout=0.2)
                self.assertTrue(acquired, 'Model yukleme yasam dongusu kilidini tutuyor')
                if acquired:
                    t._lifecycle_lock.release()
                t.stop_capture()
            finally:
                release.set()
                worker.join(4)
            self.assertFalse(worker.is_alive())
            self.assertFalse(result[0][0])

    def test_paused_device_disconnect_uses_bounded_retry(self):
        t = b.transcriber
        stream = Mock()
        stream.read.side_effect = OSError('device disconnected')
        host = Mock()
        host.open.return_value = stream
        host.get_device_info_by_index.return_value = {'maxInputChannels': 1, 'defaultSampleRate': 16000, 'name': 'test'}
        # Regresyonda sonsuz dongu olursa testi de sonsuza dek bekletme.
        calls = []
        def fail_read(*args, **kwargs):
            calls.append(1)
            if len(calls) > 55:
                t.is_running = False
            raise OSError('disconnected')
        stream.read.side_effect = fail_read
        with patch.object(t, 'is_running', True), patch.object(t, 'is_paused', True), patch.object(t, 'ptt_active', False), patch.object(t, '_active_audio_stream', None), patch.object(t, '_active_audio_p', None), patch.object(b.pyaudio, 'PyAudio', return_value=host), patch.object(b.socketio, 'emit'), patch.object(b.time, 'sleep') as sleep:
            t._capture_audio(0, t._session_id)
            self.assertEqual(len(calls), 50)
            self.assertEqual(sleep.call_count, 49)
            stream.close.assert_called_once()
            host.terminate.assert_called_once()


if __name__ == '__main__':
    unittest.main()
