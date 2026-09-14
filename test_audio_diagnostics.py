"""Ses düzeyi ve uyarlanır sessizlik için ağsız birim kontrolleri."""

import unittest

import numpy as np

from audio_diagnostics import adaptive_silence_seconds, analyze_pcm16


class AudioDiagnosticsTests(unittest.TestCase):
    def test_empty_and_silence(self):
        for samples in (np.array([], dtype=np.int16), np.zeros(128, dtype=np.int16)):
            result = analyze_pcm16(samples)
            self.assertEqual(result["status"], "no_signal")
            self.assertEqual(result["rms_dbfs"], -96.0)
            self.assertEqual(result["peak_dbfs"], -96.0)
            self.assertEqual(result["clipped_ratio"], 0.0)

    def test_quiet_normal_and_multichannel(self):
        quiet = analyze_pcm16(np.full((100, 2), 100, dtype=np.int16))
        normal = analyze_pcm16(np.full((100, 2), 4096, dtype=np.int16))
        self.assertEqual(quiet["status"], "quiet")
        self.assertEqual(normal["status"], "ok")
        self.assertGreater(normal["rms_dbfs"], quiet["rms_dbfs"])

    def test_clipping_and_negative_full_scale(self):
        result = analyze_pcm16(np.array([-32768, 32767] * 100, dtype=np.int16))
        self.assertEqual(result["status"], "clipping")
        self.assertEqual(result["peak_dbfs"], 0.0)
        self.assertEqual(result["clipped_ratio"], 1.0)
        self.assertLessEqual(result["rms_dbfs"], 0.0)

    def test_short_speech_is_faster_and_pauses_are_respected(self):
        short = adaptive_silence_seconds(1.4, 0.8, [])
        medium = adaptive_silence_seconds(1.4, 3.0, [])
        long = adaptive_silence_seconds(1.4, 10.0, [])
        hesitant = adaptive_silence_seconds(1.4, 0.8, [0.9])
        self.assertLess(short, medium)
        self.assertLess(medium, long)
        self.assertGreater(hesitant, short)
        self.assertGreaterEqual(hesitant, 1.05)

    def test_disabled_and_bounds(self):
        self.assertEqual(adaptive_silence_seconds(1.4, 0.1, [1.9], False), 1.4)
        self.assertEqual(adaptive_silence_seconds(0.1, 0.1, []), 0.65)
        self.assertEqual(adaptive_silence_seconds(3.0, 10.0, [5.0]), 2.0)


if __name__ == "__main__":
    unittest.main()
