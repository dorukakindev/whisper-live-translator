# Ses Yakalama Yaşam Döngüsü Denetimi — 2026-09-21

Dal: `devin/1790002213-capture-lifecycle-ui`, taban `48a4a17` (main).

## Kök neden

İki bağımsız kusur birleşerek "sahte dinleniyor" durumunu üretiyordu:

1. **Frontend:** `capture_stopped` soket işleyicisi yalnızca `updateStatus('inactive')`,
   `stopTimer()` ve `clearPartialPreview()` çağırıyordu. `isCapturing`, `stopBtn`,
   `deviceSelect`, `pauseBtn`, `flushBtn`, Cockpit göstergeleri ve ses aktivite
   göstergesi sıfırlanmıyordu. Backend capture thread'i `/api/start` başarısından
   sonra ölünce (cihaz açma hatası, sürücü kopması) kullanıcı arayüzü kalıcı olarak
   "dinleniyor" kalıyordu; Durdur'a basmak bile `stopBtn`'yi düzeltemiyordu çünkü
   `/api/stop` artık `is_running=False` görüp reddediyordu.

2. **Backend:** `start_capture`, thread'leri başlatır başlatmaz `True` döndürüyordu.
   `pyaudio.open()`'un başarısız olması (veya hiç dönmemesi) API'de `success:true`
   olarak raporlanıyordu; hata yalnızca yarış halinde gelen `error` soket olayıyla
   öğreniliyordu. `/api/start` "gerçekte hazır olmayan yakalamayı başarılı"
   gösteriyordu.

## Durum geçiş tablosu (yeni davranış)

Backend `WhisperWebTranscriber` — `_session_id` oturum kimliği monoton artar:

| Olay | `_lifecycle_lock` altında | Emit | Sonuç |
|---|---|---|---|
| `/api/start` | `is_running=True`, `_session_id++`, yeni `_capture_handshake` | — | Thread'ler başlar; API `handshake.event.wait(15s)` bekler |
| Capture thread `p.open` başarısı | `stream_registered=True` | `capture_started{session_id}` | handshake → API `success:true, session_id` |
| `p.open` hatası | (early return) | `error` + `capture_stopped{reason:'error'}` | handshake.error → API `success:false` |
| 50 ardışık okuma hatası | break | `error` + `capture_stopped{reason:'error'}` | `is_running=False` |
| Handshake timeout (15s) | — | `capture_start_timeout` health kaydı | `stop_capture()` + API `success:false` |
| `/api/stop` | `is_running=False`, `_stop_in_progress` | thread'ler join | Thread `finally` → `capture_stopped{reason:'stopped'}` |
| Bayat thread `finally`si | `session_id != _session_id` | **emit yok** | Yeni oturum korunur |

Frontend `index.html` — `isCapturing`/`isPaused`/`_captureSessionId`:

| Olay | İşleyici | Sonuç |
|---|---|---|
| `/api/start` success | `isCapturing=true`, `_captureSessionId=data.session_id`, butonlar aktif | — |
| `/api/start` `session_id == _lastEndedSessionId` | `endCaptureSession` + hata alert | Sahte dinleniyor engellendi |
| `capture_started` | oturum guard → `updateStatus('active')` + `startTimer`; null ise evlat edin | Bayat started yoksayılır |
| `capture_stopped` | oturum guard → `endCaptureSession` (merkezi, idempotent) | Tüm kontroller sıfırlanır; `reason:'error'` → ek alert yok |
| `stopCapture` success | `endCaptureSession` | Soket olayından bağımsız |
| `resyncAfterReconnect` (`capturing:false`) | `endCaptureSession(startEnabled=model_loaded)` | Yeniden bağlanmada uzlaşma |
| `resyncAfterReconnect` (`capturing:true`) | `_captureSessionId=st.session_id` evlat edin | Sayaç/butonlar sürdürülür |

`endCaptureSession` tek merkezi nokta: `isCapturing/isPaused/_captureSessionId`
sıfırlar, retry zincirini iptal eder, sayaç/kısmi önizleme/ses göstergesini durdurur,
`startBtn/stopBtn/deviceSelect/pauseBtn/flushBtn`'i normalize eder, Cockpit'i
günceller. Alert yalnızca `wasActive` ise gösterilir → duplicate `capture_stopped`
bildirim üretmez.

## Doğrulanan akışlar (görev listesindeki 10 senaryo)

| # | Senaryo | Backend testi | Frontend testi |
|---|---|---|---|
| 1 | normal start→stop | `test_normal_start_then_stop` | `1a/1b` |
| 2 | start sonrası thread ölümü | `test_start_fails_when_device_open_raises` | `2`, `2b` |
| 3 | cihaz açma hatası | aynı + `test_start_response_waits_until_stream_open` | `3` |
| 4 | aktif yakalamada cihaz kopması | `test_device_loss_mid_capture_emits_stop_and_clears` | `2` |
| 5 | kullanıcı stop + backend ölümü eşzamanlı | `test_stop_during_device_open_returns_error_not_success` | `5` |
| 6 | hızlı start→stop→start | `test_rapid_start_stop_start` | dolaylı (retry zinciri korunur) |
| 7 | bayat oturum olayı | `test_stale_session_never_emits_capture_stopped` | `7` |
| 8 | reconnect uzlaşması | `/api/status` artık `session_id` döndürüyor | `8`, `8b` |
| 9 | takılı kontrol/önizleme | `is_running` temizliği testleri | `1b/2` buton+timer assert |
| 10 | duplicate olay | emit tek sefer (finally koruması) | `9/10`, `10b` |

## Değişen dosyalar

- `buyedektir.py`: `_capture_handshake` (oturum başına Event dict),
  `CAPTURE_START_TIMEOUT_S=15s`, `start_capture` → 3-tuple `(success, error, session_id)`
  + hazırlık el sıkışması; `capture_started`/`capture_stopped` → `session_id`;
  `capture_stopped` → `reason`; `/api/status` → `session_id`.
- `templates/index.html`: `_captureSessionId`, `_lastEndedSessionId`, merkezi
  `endCaptureSession`, oturum-guard'lı `capture_started`/`capture_stopped`,
  `stopCapture`/`resyncAfterReconnect` merkezi yola bağlandı.
- `tests/test_capture_lifecycle.py` (yeni, 8 test) — test_smoke'a eklendi.
- `test_capture_lifecycle.js` (yeni, 11 kontrol) — Electron fixture testi.
- `test_smoke.py`: yeni suite kaydı.

## Pre-fix / post-fix kanıtı

Backend (`tests/test_capture_lifecycle.py`): eski `buyedektir.py` altında
5 FAIL + 1 ERROR — `/api/start` `p.open` tamamlanmadan `success` döndü,
cihaz açma hatası `success:true` raporlandı, `session_id`/`reason` alanları
yoktu. Düzeltmeyle 8/8 OK.

Frontend (`test_capture_lifecycle.js`, xvfb Electron): eski `index.html` altında
7 FAIL — `capture_stopped(reason='error')` sonrası `capturing:true,
stopDisabled:false, deviceDisabled:true` (sahte dinleniyor); bayat oturum olayı
uygulandı; stopped bildirimi hiç üretilmedi; reconnect'te oturum evlat edinilmedi.
Düzeltmeyle 11/11 PASS.

## Doğrulama komutları ve sonuçları

- `.venv/bin/python -m py_compile buyedektir.py` — temiz
- `.venv/bin/python -m pyflakes buyedektir.py` — temiz
- `.venv/bin/python test_smoke.py` — TUM TESTLER GECTI (yeni suite dahil)
- `node --check` inline `<script>` (Jinja `{{ app_token|tojson }}` → `"t"` ikamesiyle) — temiz
- `node --check test_capture_lifecycle.js main.js` — temiz
- `npm run scan` — temiz
- xvfb Electron: `test_capture_lifecycle.js` 11/11, `test_cockpit_browser.js`,
  `test_game_overlay_native.js`, `test:ui-language` — hepsi geçti

## Sınırlamalar / kalan riskler

- Gerçek WASAPI cihaz davranışı sahte host ile modellendi; Windows'ta gerçek
  Bluetooth/sürücü takılması zamanlaması manuel doğrulama gerektirir.
- `npm run build` çalıştırılamadı (Ubuntu + wine64 yok; mevcut ortam engeli).
- 15s handshake timeout'u çok yavaş ama çalışan cihazlarda teorik false-negative
  üretebilir — kullanıcı "zaman aşımı" hatası görür, ikinci deneme çalışır.
- Transcribe thread hazırlığı handshake kapsamı dışında (model yüklemesi ayrı);
  yalnızca capture stream açılışı doğrulanıyor.
