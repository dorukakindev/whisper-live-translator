---
name: testing-whisper-ui
description: How to run and end-to-end test the Whisper Pro web UI on a Linux box with no audio hardware (backend-only mode, token auth, stubbed pyaudiowpatch, model pre-load, and PTT contract probes).
---

# Testing the Whisper Pro web UI (Linux, no audio hardware)

## Run the backend (UI served from Flask, no Electron needed)

```bash
cd ~/repos/whisper-live-translator
PORT=5099 WHISPER_APP_TOKEN=testtok WHISPER_SKIP_API_VERIFY=1 .venv/bin/python buyedektir.py
# UI: http://127.0.0.1:5099/  (app_token is injected into the page; same-origin /api fetches get X-Whisper-Token automatically via the window.fetch wrapper at templates/index.html ~2480)
```

Startup takes ~40-60s (torch/faster-whisper). `.venv` and the `pyaudiowpatch` Linux stub (0 devices, `open()` raises OSError) are provisioned by the repo blueprint — verify `.venv/lib/python3.*/site-packages/pyaudiowpatch.py` exists if imports fail.

## Enable the Başlat button

Başlat stays disabled until a model loads. tiny is ~39 MB and loads in seconds (HF reachable):

```bash
curl -X POST -H "X-Whisper-Token: testtok" -H "Content-Type: application/json" \
  -d '{"model":"tiny"}' http://127.0.0.1:5099/api/load_model
```

## No-device behaviors to expect (don't mistake for bugs)

- `GET /api/devices` → `[]`; device selects show "Ses cihazi bulunamadi".
- To exercise the real `/api/start` path, inject an option in page console:
  `document.getElementById('deviceSelect').innerHTML='<option value="0">Sim</option>'`
  then click Başlat. Current branches (post capture-lifecycle audit): `/api/start` waits on a `_capture_handshake` and returns `{success:false, error:'Ses cihazı açılamadı veya okunamadı: …'}` synchronously; the UI shows the toast and settles fully (`isCapturing=false`, Başlat re-enabled). On older code, `/api/start` returned success optimistically, the capture thread died → socket `error`+`capture_stopped`, and the frontend stayed half-stuck (`isCapturing=true`) until Durdur — that desync state was the setup for `/api/ptt` 409 tests; on new code Ctrl-PTT is gated by `if (!isCapturing) return` so a 409 test needs a different desync or a direct fetch probe.
- The physical Ctrl key may not reach the page under automation (modifier quirk). Equivalent real-path probe: `document.dispatchEvent(new KeyboardEvent('keydown',{key:'Control'}))` — fires the actual listener incl. 150 ms pending timer → `setPtt(true)` → POST → error toast. Physical Alt does reach the page and drives the MicRecorder path.
- Alt-PTT (`#ownReplyMic` "Mikrofonla söyle" inside "Kendi cevabını yaz veya söyle") does NOT require capture running, but needs a concrete target lang — set the top "Karşı taraf" select first (`auto`+TR source → 400 'PTT için somut bir hedef dil seçin.').

## Fast API contract probes (page console inherits the token)

```js
// /api/ptt unsequenced start must 409 (not silently apply):
fetch('/api/ptt',{method:'POST',headers:{'Content-Type':'application/json'},body:'{"active":true}'})
// → 409 {"success":false,"error":"Önce ses yakalamayı başlatın"}; a following {"active":false} echoes ptt:false.
// /api/ptt_mic cancelled id must 409:
// 1) POST {active:false,discard:true,recording_id:'X'}  → 200 discarded (registers)
// 2) POST {active:true,recording_id:'X',target_lang:'en'} → 409 {"success":false,"discarded":true,...}
```

## Simulating server→client socket events (no audio needed)

Real `ptt_mic_result`/`new_transcription` events can never be produced without audio hardware, but socket.io-client dispatches incoming events to exactly the functions stored in `socket._callbacks['$<event>']` (array). Invoking them executes the REAL registered handler — any guards inside are exercised, not bypassed:

```js
const fire = (ev, payload) => (socket._callbacks['$'+ev]||[]).forEach(f=>f.call(socket,payload));
fire('ptt_mic_result', {recording_id:'foreign', success:true, ...});   // must render NOTHING under the ownership guard
fire('new_transcription', {id:88001, text:'…', timestamp:'13:00:00', model_language:'EN', source:'system'}); // renders a real row w/ Çevir+Cevap öner buttons
fire('transcription_translation_status', {id:88001, status:'pending', revision:0}); // row status note updates; wrong revision is ignored (id,revision match)
```

- `altPttRecordingId` is set to a fresh uuid by the real "Mikrofonla söyle" click and is NOT cleared by `finishAltPtt` — after a failed mic start, read it and reuse it as the own-id payload for `ptt_mic_result` (proves the guard admits own results, not just blocks all).
- Row-level translation status lives in `.translation-status-note` inside the `.transcription-item` (pending='Çeviri sırada…', failed='Çeviri alınamadı. Çevir düğmesiyle yeniden deneyebilirsiniz.').
- `ai_options_partial` handler gates on `msg.request_id` ∈ `_pendingAiRequests` keys + `_activeAnswerRequests[pending.id]===request_id` + `_replyTargetId` — read the id from `window.__aiCalls`/`_pendingAiRequests` right after a real "Cevap öner" click, then fire it to reach the partial-cards path (failure then keeps cards + 'Kalan seçenekler alınamadı').
- Failed "Cevap öner" requests used to leave the YOUR REPLY dock stuck at 'Cevaplar hazırlanıyor.' — FIXED by `failReplyCockpit` on devin/1790090524-stale-state-fixes (no-partials → error text + `.reply-cockpit-empty`; with cards → 'Kalan seçenekler alınamadı' + cards kept). If a branch lacks it, expect the stuck dock.

## Deterministic AI-response stubbing (no keys needed)

`window.__aiDeferred` exists only in `test_capture_lifecycle.js` (Electron harness) — it is NOT on the plain page. To drive the reply cockpit deterministically, monkeypatch `window.fetch` for `/api/generate_ai_response` (the page's wrapper has already injected the token into `__realFetch` — keep it for pass-through):

```js
window.__realFetch = window.__realFetch || window.fetch;
window.__newPending = () => { window.__aiPending = new Promise(r => { window.__aiResolve = r; }); };
window.__aiCalls = [];
window.fetch = function(url, opts) {
  const u = typeof url === 'string' ? url : (url && url.url) || '';
  if (u.includes('/api/generate_ai_response')) {
    try { window.__aiCalls.push(JSON.parse(opts.body || '{}')); } catch(e) {}
    return window.__aiPending.then(p => new Response(JSON.stringify(p),
      {status:200, headers:{'Content-Type':'application/json'}}));
  }
  return window.__realFetch.apply(this, arguments);
};
// use: __newPending() → click a row's .ai-answer-btn (dock holds 'Cevaplar hazırlanıyor.' while pending)
// → __aiResolve({success:false, error:'…'}) for failure, or {success:true, options:[{romanized,turkish,translation,language}]} for cards
// __aiCalls[].request_id = the id to use in ai_options_partial payloads.
// NOTE: async IIFEs return {} under browser_console — resolve in one call, read state in the next.
```

## Gotchas

- Alert toasts auto-dismiss in ~4s — screenshot immediately after triggering.
- Reading state via `browser_console` (isCapturing, button.disabled, ownReplyStatus, cockpit ids) is reliable; `connectionState`/`statusText`/`cockpitCaptureState`/`cockpitFlowState` are the useful elements.
- Backend log (`/tmp/whisper-backend.log`) shows every request with status — cross-check 409s there when a toast may have expired.
- UI language: `i18n.js` `DEFAULT_LANGUAGE='en'` — English is the designed default for en-US browsers, not a bug; Türkçe via the Arayüz select.

## Devin secrets needed

None for the golden path. AI-reply quality needs a real `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` in `.env` (keys are intentionally absent on test boxes; AI calls must fail gracefully — verify the UI shows 'Çeviri başarısız' and the button re-enables).
