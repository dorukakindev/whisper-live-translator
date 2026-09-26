"""Ses hattını model/SciPy yüklemeden gerçek fonksiyon gövdeleriyle sınar."""
import ast
import logging
import queue
from pathlib import Path
from collections import deque
from fractions import Fraction
from functools import lru_cache
from types import SimpleNamespace
import threading
import time
import re
import numpy as np
from scipy import signal
from audio_diagnostics import analyze_pcm16, adaptive_silence_seconds


tree = ast.parse(Path('buyedektir.py').read_text(encoding='utf-8'))
join_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == '_join_transcription_segments')
resample_nodes = [n for n in tree.body
                  if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                  and n.name in ('_resample_filter', '_resample_ratio',
                                 '_resample_int16', 'StreamResampler')]
klass = next(n for n in tree.body if isinstance(n, ast.ClassDef)
             and n.name == 'WhisperWebTranscriber')
capture_node = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                    and n.name == '_capture_audio')
split_node = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                  and n.name == '_find_quiet_split_index')
namespace = dict(np=np, deque=deque, time=time, re=re,
                 signal=signal, Fraction=Fraction, lru_cache=lru_cache,
                 analyze_pcm16=analyze_pcm16, adaptive_silence_seconds=adaptive_silence_seconds,
                 logger=logging.getLogger('live-audio-test'))
exec(compile(ast.Module(body=resample_nodes + [join_node, capture_node, split_node],
                        type_ignores=[]),
             'buyedektir.py', 'exec'), namespace)
join = namespace['_join_transcription_segments']
split = namespace['_find_quiet_split_index']
split_owner = SimpleNamespace(SPLIT_SEARCH_S=2)
assert split(split_owner, [np.array([100], dtype=np.int16),
                          np.array([-32768], dtype=np.int16),
                          np.array([0], dtype=np.int16)], .03) == 2, \
    'En yüksek negatif genlik sessiz bölge sayılmamalı'
assert join([SimpleNamespace(text=s) for s in ['Bugün', 'toplantıya gelemem.']]) == 'Bugün toplantıya gelemem.'
assert join([SimpleNamespace(text=s) for s in ['Merhaba.', 'Nasılsın?']]) == 'Merhaba. Nasılsın?'
assert join([SimpleNamespace(text=s) for s in ['こんにちは', '。']]) == 'こんにちは。'


def capture_case(prefix, speech, vad_fails=False, reset_at=None, ptt=False):
    values = iter(prefix + speech + list(range(20, 28)))
    captured = []
    owner = SimpleNamespace(
        CHUNK_DURATION_MS=30, RATE=16000, _lifecycle_lock=threading.Lock(),
        _session_id=1, _result_generation=0, is_running=True, is_paused=False, ptt_active=ptt,
        flush_now=False, partial_enabled=False, vad=None, capture_mode='system',
        _utterance_seq=0, silence_duration=0.09, adaptive_silence=False, MAX_UTTERANCE_S=25, MAX_PTT_S=25,
        last_emit_time=0, EMIT_INTERVAL=0.1,
        # _capture_audio'nun dogrudan okudugu alanlar (production sözleşmesi):
        # el sikismasiz bagimsiz cagri icin None, sinyal olcumleri icin girdi alanlari,
        # heartbeat satirindaki audio_queue.qsize() icin bos kuyruk.
        _capture_handshake=None, _signal_snapshot=None, _capture_phase='idle',
        audio_queue=queue.Queue(),
        _resolve_capture_device=lambda p, d: (0, {'maxInputChannels':1, 'defaultSampleRate':16000, 'name':'Test'}),
        # Sahiplik eslesirse True: finally'deki dogrudan-kapatma kolu atlanir.
        _close_active_audio_stream=lambda *a, **k: True,
        _enqueue_audio=lambda data, *args: captured.append(data.copy()))

    read_index = 0
    owner.get_capture_profile = lambda: {'silence': owner.silence_duration, 'adaptive': False, 'max_utterance': owner.MAX_UTTERANCE_S}
    def read(count, **kwargs):
        nonlocal read_index
        read_index += 1
        if read_index == reset_at:
            owner._result_generation += 1
            owner._utterance_seq += 1
        if ptt and read_index == 18:
            owner.ptt_active = False
        try:
            value = next(values)
        except StopIteration:
            owner.is_running = False
            value = 0
        return np.full(count, value, dtype=np.int16).tobytes()

    stream = SimpleNamespace(read=read)
    def classify(vad, data, rate):
        if vad_fails:
            raise ValueError('Test VAD hatası')
        return data[0] >= 100

    namespace.update(
        pyaudio=SimpleNamespace(paInt16=8, PyAudio=lambda: SimpleNamespace(open=lambda **kwargs:stream)),
        socketio=SimpleNamespace(emit=lambda *args, **kwargs:None),
        _vad_is_speech=classify,
        _record_health_error=lambda code: None)
    namespace['_capture_audio'](owner, 0, 1)
    return [data[::480].tolist() for data in captured]


assert capture_case(list(range(1, 13)), [100, 101, 102]) == [
    [7, 8, 9, 10, 11, 12, 100, 101, 102, 20, 21, 22]]
assert capture_case(list(range(1, 80)), []) == [], 'Sessizlik tek başına döküme gönderilmemeli'
assert capture_case([0] * 12, [-32768] * 3, vad_fails=True), 'Tam negatif ses seviyesi taşarak sessizlik sayılmamalı'
for ptt_mode in (False, True):
    reset_result = capture_case([100] * 4, [200] * 10, reset_at=5, ptt=ptt_mode)
    assert reset_result == [[200] * 9 + [20, 21, 22]], 'Sıfırlama öncesi ses yeni kayda sızdı'
onset_reset = capture_case(list(range(1, 13)), [200] * 10, reset_at=10)
assert onset_reset[0][:2] == [11, 12], 'Sıfırlama önceki ilk-hece tamponunu temizlemeli'
print('Metin birleştirme, ilk hece tamponu ve sessizlik testleri geçti')
