# Overnight hardening audit — 2026-09-22

Branch: `devin/1790050008-overnight-hardening` (base `95f9b93`).
Scope: harden the real-use chain capture → transcript → optional translation → reply suggestion → Turkish okunuş → game overlay. No new features; verified bugs get deterministic tests + minimal fixes; packages with no verifiable bug get a "no change needed" verdict with evidence.

## Per-package verdicts

| # | Package | Verdict | Evidence |
| - | ------- | ------- | -------- |
| 1 | Event/state contract | 1 verified bug fixed + 1 contract tightened | `ptt_mic_result` broadcast had no ownership check → foreign Alt-PTT rows injected into the main window (Electron check `P1a` failed pre-fix, passes now). `transcription_translation_status` `pending` emit was the only status emit missing `revision` → added for a uniform contract. Stale-session/instance paths otherwise already guarded (session_id, result_generation, revision under `_lifecycle_lock`). |
| 2 | Capture+PTT concurrency | No new bug; missing evidence added | Ownership/sequence/retired-client guards already strong (PR #2 property suite ~500 scenarios). New `test_ptt_buffer_single_flush_per_release`: rapid press-release-press + PTT-during-pause → exactly one segment per release, no loss/duplication. |
| 3 | Partial/final delivery | No new bug; 3 invariants locked | `test_empty_final_produces_no_transcription`, `test_stale_utterance_partial_never_emits`, `test_queue_full_drops_oldest_and_warns` (drop-oldest + `transcription_lagging` emit). |
| 4 | Optional translation + reply | No new bug; 1 invariant locked | Per-row **Çevir** writes only to its own row (id+revision ownership); `/api/clear` never reuses ids so a stale result cannot hit a recycled row. Electron check `P4 late AI result cannot resurrect removed row`. Parallel-call/dedup/streaming contract already covered by `test_smoke.py::test_answer_contract`. |
| 5 | Turkish okunuş fitness | No verified rule bug; fixture added | `tests/test_pronunciation_fixture.py`: representative samples over all 17 `PRONUNCIATION_GUIDES` languages (native+romanized inputs), pinned outputs, charset invariant, ja-hyphen-keep vs others-strip, broken/empty inputs, language switch. Automated tests cannot prove pronunciation *quality* — only contract regressions. |
| 6 | Frontend lifecycle + long conversation | No functional bug; 4 invariants locked | Electron checks `P6a` (130 transcripts → DOM pruned to 100 + `transcriptionTexts` lockstep cleanup + pruned-id re-emit rejected), `P6b` (UI language switch), `P6c` (theme roundtrip), `P6d` (history search renders). Scroll-follow + anchor-preserve already implemented in `static/live-flow.js`. Narrow-window layout is CSS-level — not functionally verified here. |
| 7 | Game mode + overlay | No functional bug; 8 invariants locked | `test_overlay_stale.js`: stale-revision translation, foreign id/instance, mic/ptt source filter, clear+late-translation resurrection, instance switch. Window bounds/focus/always-on-top/preload already covered by `test_game_overlay.js` + `test_game_overlay_native.js`. Xvfb cannot prove real Windows game-window/focus/DPI behavior — manual-verify item. IPC unchanged (sender+mainFrame allowlist already in place). |
| 8 | Security/privacy boundaries | No confirmed vulnerability; negative tests added | Token required on every `/api/*` method (GET+POST), Socket.IO connect auth, dict-body 400, CSP/navigation/`window.open` deny, `escapeHtml` sinks. New tests: socket bad/missing token reject, API token contract, healthz leaks no sensitive fields, XSS payload stays inert (Electron `P8`). Theoretical risk noted separately: any local process can `GET /` to read `app_token` — accepted localhost trust model, `HOST` must stay `127.0.0.1`. Packaging scan covers new files (repo-wide walk). |
| 9 | Error recovery/observability | 1 privacy fix | `buyedektir.log` wrote raw speech at 3 sites: `[transcribe diag] -> repr(full_text[:60])`, `Halusinasyon filtrelendi: {full_text[:80]}`, `Mic transcription: {full_text}` → now logs length only. Bounded retries verified (backend restart ≤3 + backoff; alert cap 3; `transcription_lagging` 8 s rate-limit); profile-save failure → warning + tmp cleanup; no unbounded retry loops found. |
| 10 | Performance/soak | Harness built + 30-min run | `tests/test_soak.py` (`SOAK_SECONDS`): fast transcript feed, 50 ms translate stub, model-lock contention, queue pressure, PTT cycles, periodic start/stop. Samples: RSS, threads, queue depth, emit counts, errors. Limits: stub model does not prove faster-whisper memory/latency; small VM does not prove real-speech performance. Results in the test section below. |
| 11 | Install/packaging/clean env | Verified, no changes needed | `npm ls` consistent with lockfile; `py_compile`/`pyflakes` clean; `node --check` main.js + inline JS (2 blocks) clean; `npm run scan` clean; `npm run audit:history` 78 revisions clean. `build.js` allowlist covers `templates/` (incl. overlay.html) and excludes tests; repo-wide source scan covers new files. `npm run build` NOT run: win32 packaging needs wine64, absent on this box — do not claim EXE build passes. `dist` staleness warning exists in `build.js` and TROUBLESHOOTING.md. |
| 12 | English docs vs code | No stale claims found | README/USAGE/TROUBLESHOOTING/PRIVACY/ARCHITECTURE match audited behavior: Game Mode shortcuts (`Ctrl+Shift+O`/`L`), overlay semantics, manual-vs-auto Translate, PTT, providers, `dist` non-auto-update, localhost trust boundary. |
| 13 | Final cross-validation | See test section | |

## Verified bugs this round

1. **`ptt_mic_result` missing ownership check** — `templates/index.html` handler (pre-fix ~line 5404). Event is broadcast to all socket clients; handler inserted a row + alert without comparing `recording_id` to `altPttRecordingId`. Reachable path: second localhost client (e.g. a stray `localhost:5000` tab or a second Electron window) runs Alt-PTT → its success/error result lands in the main page's transcript list and toasts an error the main page never asked for. Failing pre-fix check `P1a foreign ptt_mic_result ignored` (row count 1, 2 alerts); fix = early-return unless `data.recording_id === altPttRecordingId` (empty ids also rejected). User impact: phantom transcript rows + misleading error toasts in multi-client use.

2. **`pending` status emit missing `revision`** — `buyedektir.py` `transcription_translation_status` emit (~line 4434). Frontend matches status updates by exact `(id, revision)`; the pending emit lacked `revision` while `translating`/`done`/`failed` carries it — a uniform contract now: every status emit includes `revision`. Low user impact (pending label path tolerated `undefined`) but the contract was inconsistent.

3. **Raw speech written to `buyedektir.log`** — 3 sites (transcribe diag, hallucination filter, mic transcription). Plaintext log duplicated conversation content outside `transcriptions.txt`. Now logs lengths only (`-> 42chr`, `Halusinasyon filtrelendi (42 karakter)`, `Mic transcription tamamlandi (42 karakter)`). User impact: privacy — log files shared with bug reports could carry private speech.

## Test evidence

| Check | Result |
| ----- | ------ |
| `tests/test_capture_lifecycle.py` (backend, 15 tests) | OK |
| `test_capture_lifecycle.js` (Electron/Xvfb, 21 checks) | ALL PASS |
| `test_overlay_stale.js` (Electron/Xvfb, 8 checks) | ALL PASS |
| `tests/test_pronunciation_fixture.py` (9 tests) | OK |
| `tests/test_soak.py` — 30-min run (`SOAK_SECONDS=1800`) | see soak results |
| `tests/test_concurrency_audit.py` (21 tests) | OK (unchanged) |
| `python -m py_compile / pyflakes buyedektir.py` | clean |
| `node --check` main.js + extracted inline JS | clean |
| `npm run scan`, `npm run audit:history` | clean (78 revisions) |

### Soak results (30 min, `SOAK_SECONDS=1800`)

| Metric | Value |
| ------ | ----- |
| duration / samples | 1800.2 s / 360 points (5 s) |
| `new_transcription` emits | 1599 |
| `partial_transcription` emits | 26898 |
| start/stop cycles | 40 (all clean stop) |
| stream reads / model calls | 718281 / 28572 |
| errors | 0 |
| RSS start→end→max | 124.7 → 131.1 → 134.7 MB (Δ +6.3) |
| threads start→end | 1 → 2 (Δ +1) |
| queue max / lagging emits | 1 / 0 |
| translate backlog at end | 0 |
| HTTP non-2xx | 1 of ~600 (transient start-during-stop 409 on a cycle boundary — by design) |

No leak pattern (RSS +6.3 MB over 30 min is allocator noise, not a trend; no thread accumulation; executor backlog zero; queue never filled under this load). Limits: fake model + fake stream — proves bookkeeping/emit-path stability, NOT faster-whisper memory, provider latency, or real-speech throughput.

## Not run / limitations

- `npm run build` (win32 EXE): requires wine64 — absent on this Ubuntu box (env blocker). `build.js --scan-source` verified instead.
- Real microphone/WASAPI, real game window/focus/DPI/multi-monitor, provider latency: simulated or unverifiable here.
- Automated tests cannot prove pronunciation *quality* — fixture locks contract regressions only.
- Narrow-window layout is CSS-level; not functionally exercised.

## Windows manual-verification list

- `npm run build` on Windows (or a wine-equipped host) → verify `dist/Whisper-Pro-win32-x64` packages + post-build scan clean.
- Real WASAPI loopback capture + device hot-unplug during a meeting.
- Game Mode over a real borderless-windowed game: lock (`Ctrl+Shift+L`), click-through, multi-monitor + DPI scaling.
- Alt-PTT mic dictation on real microphone, incl. device-open failure toast.
- `pyannote` diarization on real hardware.
