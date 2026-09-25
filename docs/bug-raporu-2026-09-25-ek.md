# Derin Bug Taraması — Ek Rapor (ikinci tur, 2026-09-25)

Bu belge, aynı gün 03:45'te üretilen [bug-raporu-2026-09-25.md](bug-raporu-2026-09-25.md)
üzerine yapılan ikinci bağımsız A→Z taramanın sonucudur. Kod tabanı aynıdır
(HEAD `eacfcdb`, aradaki commit'ler yalnız doküman). Önceki bulgular tekrar
yazılmadı; yalnızca durumları güncellendi.

## 1. Kapsam ve doğrulama yöntemi

- `buyedektir.py` (~6.5k satır): capture/transcribe/partial/PTT/flush/pause
  yaşam döngüsü, `update_settings`, `get_capture_profile`, `snapshot_request`,
  `_translate_async`, `MicRecorder`, `SpeakerDiarizer`, `/api/*` endpoint'leri,
  auth/CSP/CORS katmanı — tamamı okundu, şüpheli yollar uçtan uca izlendi.
- `main.js`, `main_helpers.js`, `preload.js`, `build.js`, `templates/index.html`,
  `templates/overlay.html`, `static/*.js`, `transkribe.py`, `launcher_whisper.py`,
  `audio_diagnostics.py`, `başlat.bat`, `diger-baslaticilar/`, `scripts/`,
  `package.json`, test dosyaları.
- Her aday bulgu için iki taraf da (frontend↔backend / route↔snapshot) ayrı ayrı
  izlendi; izlenemeyenler "şüpheli" değil "doğrulanmamış" sayılıp rapora alınmadı.

## 2. Bu turun yeni doğrulanmış bulguları

### W-5 🟡 `/api/status` yanıtı `session_id` alanını düşürüyor — yeniden bağlanma sonrası oturum evlat-edinme kodu ölü

**Kanıt:**

- `get_runtime_snapshot()` `session_id` üretir: `buyedektir.py:2930`.
- `/api/status` route'u snapshot'taki diğer alanları tek tek kopyalar ama
  `session_id`'yi **dışarıda bırakır**: `buyedektir.py:5501-5518`.
- Frontend `resyncAfterReconnect` bu alanı okur:
  `templates/index.html:3741` → `if (st.session_id != null) _captureSessionId = st.session_id;`
  — `st.session_id` her zaman `undefined`, satır hiç çalışmaz.

**Etki:** Sayfa yakalama sürerken yenilenirse `_captureSessionId` `null` kalır.
`capture_stopped` handler'ındaki koruma
(`index.html:3548-3549` → `data.session_id != null && _captureSessionId != null`
koşulu) `_captureSessionId == null` iken hiçbir olayı reddedemez. Uç senaryo:
yenileme sırasında eski oturumun capture thread'i hâlâ kapanıyorsa (stop istendi,
thread `stream.read`'de takılı), gecikmiş `capture_stopped(eski_id)` yeni sokete
düşer ve session 6 canlıyken UI "Durduruldu"ya döner → UI/backend senkron
kaybı. Nadir ve kendini bir sonraki gerçek olayla toparlayan bir durum; ama
yazarın niyeti açık (3539'daki `capture_started` evlat-edinmesi ve yorumlar),
`/api/status`'a tek satırla `session_id` eklenmesi planlanmış ve unutulmuş.

**Neden false-positive değil:** Alan snapshot'ta var, route'ta yok, frontend
okuyor — üç nokta da dosya/satır kanıtlı. Niyet-uygulama uyuşmazlığı kesin;
tek tartışılabilir kısım tetikleme sıklığıdır (düşük), bu yüzden önem: düşük.

**Önerilen düzeltme:** `get_status()` yanıtına `'session_id': state['session_id']`
ekle.

### W-6 🟡 Sessizlik süresi slider'ı ile etkin davranış sessizce ayrışıyor (üç mekanizma)

**Kanıt:**

- Slider `min="0.2" max="5" step="0.1"`: `templates/index.html:2309`.
- Backend `update_settings` `0 < sd <= 60` kabul eder ve saklar:
  `buyedektir.py:3419-3423`.
- Etkin sessizlik `_capture_audio`'da: adaptif **açıkken**
  `adaptive_silence_seconds()` sonucu `[0.65, 2.0]`'a kıstırılır
  (`audio_diagnostics.py:37` base clamp + `:56` sonuç clamp;
  `buyedektir.py:4067-4072`). Adaptif **kapalıyken** ham değer kullanılır
  (`buyedektir.py:4073-4074`).
- Oyun modu + sistem sesi: `get_capture_profile` sessizliği **0.9s ve
  adaptif=True'ya sabitler** — slider ve adaptif toggle tamamen baypas
  (`buyedektir.py:3448-3452`; yorum "Oyun profili normal ayarları
  değiştirmez" — state'i değiştirmez ama davranışı değiştirir).
- UI'da etkin değerin geri gösterimi yok; `settings_updated`/snapshot'ta
  yalnızca **yapılandırılan** değer döner (`index.html:2544-2550`).

**Etki:** Adaptif mod açıkken (varsayılan) slider'ın 0.2–0.64 ve 2.1–5.0
bölgeleri (aralığın kabaca %60'ı) hiçbir davranış değişikliği üretmez; ayar
"5.0" saklanır ama kesim hep ≤2.0s'de olur. Oyun modunda ise slider tamamen
ölüdür. Veri kaybı/çökme yok; kullanıcı-yanlıltıcı kontrat kusuru.

**Neden false-positive değil / neden tartışmalı:** Clamp'in kendisi kasıtlı bir
güvenlik zarfı (docstring "kısa sözde hızlan, belirgin duraksamada erken kesmeyi
önle" — `audio_diagnostics.py:36`) ve oyun-profil sabitleri de açıkça kasıtlı.
Kusur olan kısım **UI'nin hiçbir zaman etkin değeri yansıtmaması ve slider'ın
onurulamayacak aralık sunması**dır. Bu yüzden "uygulama hatası" değil,
"sözleşme/UX tutarsızlığı (düşük)" olarak sınıflandırıldı.

**Önerilen düzeltme (birini seç):** (a) adaptif açıkken slider aralığını
0.65–2.0'a indir + tooltip'te zarfı açıkla; (b) `/api/update_settings`
yanıtına etkin değeri (`_effective_silence`) ekleyip UI'da göster;
(c) oyun modu açıkken slider'ı disable et + "Oyun profili 0.9s kullanıyor"
notu.

## 3. Önceki bulguların HEAD durumu (bu turda yeniden doğrulandı)

| Bulgu | Durum | Taze kanıt |
|---|---|---|
| **W-1** 🔴 boş `apiKey` anahtarı siler | **Hâlâ açık** | `buyedektir.py:4985-4992` — `'apiKey' in data` dalı `''`/`None`'ı `configure_translation`'a/`translator.api_key`'e yazar; `configure_translation` `normalize→None` yapar (1597-1600). Frontend `translationSettings.apiKey` varsayılanı `''` (`index.html:2646`) ve `persistTranslationSettings` nesneyi bütün gönderir (3181, 3224) → localStorage boşken herhangi bir çeviri-ayarı kaydı anahtarı siler. |
| **W-1 kardeş yüzeyi** `/api/deepl_config` AI dalı | **Hâlâ açık** | `buyedektir.py:4924` `configure_translation(provider, api_key)` `api_key` alansız da koşulsuz çağrılıyor → `None` → `translation_api_keys[provider]=None` (siler) + `4925` provider koşulsuz değişir. |
| **W-4** `test_live_audio.py` bayat | **Ampirik teyit** | Çalıştırıldı: `AttributeError: 'SimpleNamespace' object has no attribute '_capture_handshake'` (`buyedektir.py:3783`). `test_smoke.py` bu dosyayı çalıştırmıyor (1910-1917 yalnız archive + concurrency + lifecycle) → kırık kapı değil, ölü test dosyası. |

## 4. Test borcu / hijyen (ürün bug'ı değil)

- **W-4** yukarıdaki gibi — ayrıca fixture'ın SimpleNamespace'i production'ın
  okuduğu diğer alanları da (`audio_queue`, `_signal_snapshot`, `_capture_phase`,
  `_partial_*`) taşımıyor; tek alan eklemek yetmez, harness hizalama ister.
- Kökteki `test_*.py`/`test_*.js` dosyalarının çoğu hiçbir kapıya bağlı değil:
  `package.json`'da yalnız `test:ui-language` script'i var; `test_smoke.py`
  kök dosyaları sürmüyor. Çalıştırılınca sonuç:
  `test_audio_diagnostics.py` ✅ 5/5, `test_live_enhancements.py` ✅ 16/16,
  `test_translation_worker.py` ✅ 4/4; node ile çalışan 13 JS testinin tamamı ✅;
  `test_capture_lifecycle.js`, `test_cockpit_browser.js`,
  `test_game_overlay_native.js`, `test_overlay_stale.js` Electron harness'idir
  (düz `node` ile `TypeError` — `electron <dosya>` ile koşulmalı; npm script'i
  yok). **Risk:** hiçbir CI/npm/test_smoke bunları koşmadığından sessizce
  çürüyebilirler — W-4 tam olarak böyle çürüdü.
- `untracked nul` dosyası kökte duruyor (Windows `NUL` aygıt-adı kazası ürünü);
  koddan bağımsız, silinmedi.

## 5. Doğrulanmış NON-BUG'lar (kasıtlı/sağlam davranış)

- **Auth katmanı sağlam:** `require_local_app_token` tüm `/api/*` metodlarını
  (GET dahil) `hmac.compare_digest` ile korur (`buyedektir.py:119-128`);
  `/healthz` kasıtlı olarak tokensuz ve kimliksiz veri taşır (5521-5536).
  Frontend `window.fetch` wrapper'ı tüm same-origin `/api/*` çağrılarına
  merkezi token basar (`index.html:2476-2489`); soket `auth.token` doğrulanır
  (145-150). CSP/CORS localhost kısıtlı.
- **Kuyruk dolunca eski ses düşürülmesi** (`_enqueue_audio_unlocked`, 4221-4240):
  kasıtlı backpressure + `transcription_lagging` yayını — bug değil.
- **`socketio.emit` `_frames_lock` altında** (`MicRecorder._record` 2454): tek
  seferlik sınır mesajı; threading async modda bloklamaz — önemsiz.
- **Çok kanallı `signal_frames` RMS'i interleaved hesaplanır** (3894-3904):
  `analyze_pcm16` zaten "ortak düzey özeti" üretir; tanı amaçlı yaklaşık değer —
  bug değil.
- **`adaptive_silence_seconds` clamp'inin kendisi:** kasıtlı güvenlik zarfı —
  W-6'da kusur olan kısım clamp değil, UI'nın sessizliği.
- **`openai_responder.enabled` bayrağı** yazılıyor ama okunmuyor (4988, 4931):
  önceki turda not edildi; davranış etkisi yok → bug değil, ölü alan.
- **`test_overlay_stale.js` ve benzerleri düz node'da `TypeError`:** Electron
  harness'i; yanlış koşucu hatası, ürün/test bug'ı değil.

## 6. Doğrulanmamış sınırlar

- Gerçek sağlayıcı/API çağrısı, gerçek ses donanımı ve Windows UI/DPI/GPU
  davranışı bu ortamda sınanmadı (kural gereği ücretli anahtar kullanılmadı).
- Electron'a özgü test dosyaları `electron` koşucusuyla ayrıca doğrulanmadı.
