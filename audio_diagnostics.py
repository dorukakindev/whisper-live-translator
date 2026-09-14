"""PCM16 ses düzeyi ve konuşma sonu bekleme yardımcıları."""

import math

import numpy as np


def analyze_pcm16(samples):
    """Tek veya çok kanallı PCM16 örneklerinin ortak düzey özetini döndür."""
    pcm = np.asarray(samples, dtype=np.int16).reshape(-1)
    if pcm.size == 0:
        return {"rms_dbfs": -96.0, "peak_dbfs": -96.0,
                "clipped_ratio": 0.0, "status": "no_signal"}

    # int16 üzerinde abs(-32768) taşar; düzeyi geniş türde hesapla.
    normalized = pcm.astype(np.float64) / 32768.0
    peak = float(np.max(np.abs(normalized)))
    rms = float(np.sqrt(np.mean(np.square(normalized))))
    peak_dbfs = max(-96.0, 20.0 * math.log10(peak)) if peak else -96.0
    rms_dbfs = max(-96.0, 20.0 * math.log10(rms)) if rms else -96.0
    clipped_ratio = float(np.count_nonzero(np.abs(pcm.astype(np.int32)) >= 32760) / pcm.size)

    if peak_dbfs < -60.0 or rms_dbfs < -70.0:
        status = "no_signal"
    elif clipped_ratio >= 0.005:
        status = "clipping"
    elif rms_dbfs < -38.0:
        status = "quiet"
    else:
        status = "ok"
    return {"rms_dbfs": rms_dbfs, "peak_dbfs": peak_dbfs,
            "clipped_ratio": clipped_ratio, "status": status}


def adaptive_silence_seconds(base_silence, speech_seconds, recent_pauses, enabled=True):
    """Kısa sözde hızlan, belirgin duraksamada erken kesmeyi önle."""
    base = min(2.0, max(0.65, float(base_silence)))
    if not enabled:
        return base

    speech = max(0.0, float(speech_seconds))
    if speech <= 1.2:
        wait = base * 0.75
    elif speech >= 8.0:
        wait = base * 1.15
    else:
        wait = base

    pauses = [float(p) for p in recent_pauses
              if math.isfinite(float(p)) and float(p) > 0.0]
    if pauses:
        # Son üç duraksama, eski bir uzun molanın oturumu etkilemesini önler.
        measured = max(pauses[-3:])
        if measured >= base * 0.5:
            wait = max(wait, measured + 0.15)
    return min(2.0, max(0.65, wait))
