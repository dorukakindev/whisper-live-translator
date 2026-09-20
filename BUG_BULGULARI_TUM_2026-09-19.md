# Birleşik Derin Test ve Bug Taraması Raporu — 2026-09-19 (rev. 2026-09-20)

**Repo:** `dorukakindev/whisper-live-translator` — dal `main`, denetlenen kod `358ca1e`
**Revizyon:** Bu dosya ikinci bağımsız doğrulamadan sonra düzeltildi: 15 Eylül bulgu kimlikleri özgün anlamlarına geri bağlandı, kanıtlanmamış iddialar yumuşatıldı ve birkaç yanlış madde geri çekildi. Değişiklikler §6 "Errata"da listelidir.
**Kapsam:** `DERIN_TEST_VE_BUG_RAPORU_2026-09-19.md` + `GENEL_DENETIM_RAPORU_2026-09-15.md` + ilgili eski raporların birleşik sonucu.
**Yöntem:** `test_smoke.py` + arşiv süitleri + tüm Node/Electron testleri + `npm run scan` + Flask `test_client` ile canlı endpoint yüklemesi (fuzz, eşzamanlılık, yetkisiz istek) + satır satır kod denetimi. Uygulama kodunda **hiçbir değişiklik yapılmadı**.

---

## 1. Test matrisi

| Test / araç | Sonuç |
|---|---|
| `python test_smoke.py` | ✅ Geçti |
| `tests/archive/` Python süitleri (4 dosya) | ✅ Geçti |
| `tests/` Node testleri (12 dosya) | ✅ Geçti |
| `tests/` Electron testleri (3 dosya, xvfb) | ✅ Geçti |
| `npm run scan` | ✅ Geçti |
| `py_compile` + `pyflakes` + `node --check` | ✅ Temiz |
| `test_game_overlay_native.js` | ⚠️ Tek seferlik flaky gözlem (bkz. N-7 — kesin bug değil) |
| `test_cevap_onerisi.py` | ⏭️ Atlandı — canlı API kredisi gerektirir (opt-in) |

## 2. Yeni bulgular (19 Eylül turu; doğrulanmış, düzeltilmiş)

Önem: 🔴 yüksek / 🟠 orta / 🟡 düşük. "Canlı" = Flask test_client'ta üretildi.

### N-1 🔴 Claude-only kullanıcıda "Özet Al / Soru Sor" tamamen kapalı
`buyedektir.py:6202` — `/api/ai_chat` yalnız `openai_responder.api_key` (OpenAI anahtarı) kontrol eder. `ANTHROPIC_API_KEY` ile açılan kullanıcıda özet/soru hep "OpenAI API anahtari gerekli" (HTTP 200, `success:false`) ile reddedilir. `answer_question` (1686-1691) anthropic anahtarını doğru kullanır; `/api/status` (5252-5264) sağlayıcı-bilinçli → kapı yanlış, üretim yolu doğru. **Canlı kanıtlandı.** Ek kusur: hata mesajı sağlayıcı adını yanlış söylüyor.

### N-2 🔴 Claude canlı çeviri sessizce hiç çalışmıyor (çift duvar)
`buyedektir.py:4314-4320` — kuyruğa girme koşulundaki sağlayıcı kümesi `{'openai','openai_reseller','openai_official'}`; `'anthropic'` eksik → `has_key=False` → `translate_executor.submit` hiç çağrılmaz; `translation_status` 'pending' bile olmaz. UI "Claude çeviri aktif" gösterir ama çeviri üretilmez — **sessiz ölü özellik**.
İkinci duvar: `ANTHROPIC_API_KEY` açılışta yalnız `anthropic_api_key`'e yazılır (2700-2705); `translation_api_keys['anthropic']` **hiçbir yerde tohumlanmaz** → env-kullanıcısında kapı düzeltildikten sonra bile `_translate_with_openai` (2026-2030) `api_key=None` görüp None döner. `translate()` (1977) anthropic'i zaten doğru yönlendirir.

### N-3 🟠 Alt-PTT Claude sağlayıcıda okunuşsuz kalıyor
`buyedektir.py:5094-5096` — `process_mic_audio` aynı eksik küme → Claude'la romanized-JSON yoluna girmez → `romanized` boş. 5164 satırı ja/zh/ko/ar'ı `_normalize_turkish_pronunciation` fallback'inden hariç tutar → okunuşun en kritik olduğu dillerde tamamen kayıp. Frontend etkisi: `cockpit.js:319` `opt.romanized || nativeText` — kart "Türkçe okunuş" etiketiyle **okunamaz yerli yazı** gösterir.

### N-4 🟠 Sayfa açılışı backend yapılandırmasını eziyor
`templates/index.html`:
- `syncAITranslationModelOptions` (4748-4766) her çağrıda `/api/ai_translation_model`'e koşulsuz POST; `updateTranslationProviderUI` (3117) ← `loadTranslationSettings` (3075) ← `window.onload` (2665) ve her `changeTranslationProvider`'da tetiklenir → env `ANTHROPIC_MODEL`/`OPENAI_MODEL` ilk açılışta dropdown'ın ilk seçeneğiyle ezilir; provider='deepl' iken bile atılır.
- `loadAIConfig` (4864-4874): `provider === 'openai_official' ? provider : 'anthropic'` eski localStorage değerlerini **anthropic'e zorlar** ve `changeAIProvider()` bunu backend'e POST eder → cevap sağlayıcısı kullanıcı istemeden değişir.
- `loadAIConfig` (4883) saklı anahtarı her açılışta `/api/ai_response_config`'e yeniden POST eder → `set_api_key` → canlı doğrulama (N-13 ile birleşir).
- Aynı zincir açılışta `/api/translation_settings`'e de POST eder → N-9'un tetikleyicisi.

### N-5 🟡 PTT-mikrofon "recording:true" döner ama kayıt ölü olabilir (donanım koşullu)
`MicRecorder.start` (2332-2351) cihaz açılmadan `True` döner; `_record`'un açılış hatası (2433-2441) yalnız loglanır → `/api/ptt_mic` `{'recording': True}` dönerken yakalama çökmüş olabilir; `stop()` boş veri üretir → "Ses anlaşılamadı". Windows ses yığınında doğrulanmalı.

### N-6 🟡 `transkribe.py` çalışırken model değişim yarışı (kısmen doğru)
`_on_model_change` (290-293) `_model=None` yapar; `_run` worker (423) aynı attribute'u kullanır. Doğrulanan etki: yarış penceresi gerçek; işin `NoneType` hatasıyla bitmesi mümkün. "Native use-after-free çökmesi" **kanıtlanmadı** — Windows'ta ayrıca doğrulanmalı. Ayrıca `_open_output_folder` (584) `os.startfile` — yalnız Windows.

### N-7 ⚪ Kesin bug değil — tek seferlik flaky gözlem
`test_game_overlay_native.js` 4 koşuda 1 kez patladı; saklanmış çıktı/deterministik tekrar yok. Kayıt olarak bırakıldı; bug kabul edilmedi.

### N-8 🟡 `/api/generate_ai_response` tip denetimsiz → 500 / yanıltıcı hata
`buyedektir.py:5594-5605` — `if not text` sonrası `_is_likely_hallucination(text)` → string-olmayan truthy değerlerde (`123`, `{}`, `[]`) `AttributeError` → HTTP 500. `target_lang` liste/dict ise `lang_names.get(target_lang)` (5646) → `TypeError: unhashable` → generic `except` yutup `200 + 'AI servisi yanıt vermedi'` döner (B-08). **Canlı kanıtlandı.**

### N-9 🔴 `/api/translation_settings` saklı çeviri anahtarını siliyor
`buyedektir.py:4827-4828` — AI sağlayıcılarında koşulsuz `configure_translation(provider, data.get('apiKey'))`; `apiKey` yoksa/boşsa `normalized_key=None` → `translation_api_keys[provider]=None`. DeepL dalında `'apiKey' in data` koruması (4831) var; AI dallarında yok. **Canlı kanıtlandı:** `deepl_config`'le `sk-ant-test123` → `translation_settings` {provider:'anthropic', apiKey alansız} → anahtar `None`. Tetikleyiciler: `toggleTranslation`/`updateLanguageSettings`/`loadTranslationSettings` localStorage'dan boş `apiKey` gönderir (profil sıfırlama, yeni makine, env-anahtarı kullanıcısı). (15 Eylül raporundaki özgün **B-04** ile aynı kök.)

### N-10 ⚪ Bug değil — geri çekildi
`ai_chat` dedup anahtarının bağlamı içermesi soru-cevap için doğru, özet için kabul edilebilir davranış. Kayıt amaçlı.

### N-11 🟡 Banner metinlerinde mojibake
`buyedektir.py:6244-6247` — başlangıç log dizgeleri `"ğŸâ€"` bozuk UTF-8 kalıntısı içeriyor. Kozmetik.

### N-12 🟡 Overlay "Cevap Önerisi" zaman aşımsız
`overlay.html:279-321` — `requestAnswer` fetch'inde AbortController/timeout yok; sağlayıcı uzun sürerse buton "Yükleniyor…"da takılır. Revision/instance guard'ları (296) doğru; tek eksik zaman aşımı.

### N-13 🟡 Anthropic doğrulamasında önbellek yok
`buyedektir.py:1640-1668` — `_verified_api_key` yalnız `openai_official` için; anthropic dalında eşdeğer yok → her `set_api_key`/`test_connection` canlı `GET api.anthropic.com/v1/models` (timeout 5+15 sn). N-4'ün açılış re-POST'uyla birleşince her yenilemede ağ çağrısı.

### N-14 🟡 Küçük maddeler (daraltıldı)
- `buyedektir.py:5505` `/api/ai_response_toggle`: `enabled` bool'e zorlanmaz; string değer kabul edilir, alan yoksa `False` — bozuk POST AI'yi kapatır.
- `buyedektir.py:2029` `_translate_with_openai` log'u anthropic için de "OpenAI çeviri" der — yanlış etiket.
- (`mark_said` uzunluk sınırı yokluğu ve `context_id` fallback'i bug değil; yalnız sağlamlaştırma önerisi — ayrıntı düzeltme listesinde.)

## 3. 15 Eylül 2026 denetim bulguları — özgün kimliklerle yeniden doğrulama

Önceki sürümde bu tabloda kimlikler karışmıştı; aşağıdaki satırlar `GENEL_DENETIM_RAPORU_2026-09-15.md`'deki özgün kimlikleri kullanır.

| ID | Önem | Doğrulama | Açıklama |
|---|---|---|---|
| A-01 | 🔴 | **Doğru** | `stop_capture` (3588-3621): `_result_generation += 1` + `_drain_audio_queue()` → kuyruktaki/işlemdeki son konuşma commit'siz düşer. |
| A-02 | 🟠 | **Doğru** | `isOwnedWhisperBackend` (main_helpers.js:9): mutlak uzun yol `true`, göreli ve 8.3 kısa yol (`WHISPE~1`) `false` döner — yardımcı doğrudan çalıştırılıp üretildi. |
| A-03 | 🟠 | **Doğru** | Backend canlı çeviri + frontend `autoTranslateEnabled` aynı transkriptte iki AI isteği. |
| A-04 | 🟡 | **Kısmen** | GPU hatası → sessiz CPU fallback değil: sonuç `device:'CPU'` ile UI'a döner ve gösterilir; eksik olan GPU hatasının **nedeni** (3314 `device` alanı nedeni taşımaz). |
| A-05 | 🟡 | **Doğru** | `setPtt` (index.html:5138-5144) `keepalive` yok; sekme kapanışında release düşebilir. C-04 ile birleşik düzeltmede. |
| B-01 | 🟠 | **Doğru** | `buyedektir.py:2260` `diarization.itertracks(yield_label=True)` — kurulu `pyannote.audio 4.0.4` `DiarizeOutput` döndürür; `itertracks` yok → diarization her cümlede istisna. |
| B-02 | 🟠 | **Doğru (koşullu)** | Kullanıcı Windows venv'inde `torchcodec 0.14.0` importu DLL/FFmpeg uyumsuzluğuyla çöküyor → bellek-tensor yolu (2237) çalışırsa etkilenmez; dosya fallback'i (2242-2256) çalışmaz. |
| B-03 | 🟡 | **Kısmen** | Anahtarsızken "Claude/OpenAI çeviri aktif" mesajı gerçek (index.html:3189-3192). "Ana cevap anahtarına fallback yok" kusuru bilinçli tasarım — anahtarlar ayrı tutuluyor. |
| B-04 | 🟡 | **Doğru** | Özgün anlamı = N-9 ile aynı kök: `configure_translation(provider, None)` kayıtlı anahtarı siliyor. |
| B-05 | 🟡 | **Doğru** | `process_mic_audio` stale-generation dönüşü (5036-5038) `ptt_mic_result` emit etmez → UI "işleniyor"da takılır. |
| B-06 | 🟡 | **Doğru** | `start_capture` (3499+) `context_buffer`'ı temizlemez; mic-modu Türkçe dikteler 4235'te koşulsuz eklenir → Whisper `initial_prompt` kirlenir. |
| B-07 | 🟡 | **Doğru (UI dışı)** | String `transcript_id` → `_next_transcription_id+1` fallback'i (5659-5661) mevcut kaydı önceki bağlama katabilir; normal frontend sayı gönderiyor. |
| B-08 | 🟡 | **Doğru** | `target_lang` liste/dict → `lang_names.get` `TypeError` → generic `except` → yanıltıcı 'AI servisi yanıt vermedi' (canlı üretildi; N-8 ile aynı aile). |
| B-09 | 🔵 | **Kısmen** | bool-coercion + mojibake doğru (N-11/N-14). PyAudio leak iddiası mevcut `try` yapısında kanıtlanmadı; "OpenAI doğrulaması `enabled=False` yapıyor" alt iddiası eskimiş; sabit `DEFAULTS` kullanıcı hatası değil. |
| C-01 | 🟠 | **Doğru** | `/api/deepl_config` (4774-4775): provider commit'i anahtar doğrulamasından **önce**; başarısız test mevcut ayarı bozuyor. |
| C-02 | 🟠 | **Doğru** | `/api/*` token'lı, `/socket.io/` connect'te auth yok → yerel süreç canlı transkript akışını tokensuz dinleyebilir (localhost tasarım notu ile birlikte). |
| C-03 | 🟡 | **Doğru** | `start_capture` (3544-3547) `whisper_language`'ı `capture_mode` fark etmeksizin atar → mic modunda Türkçe dikte seçili yabancı dilde çözümlenir. |
| C-04 | 🟡 | **Doğru** | Ctrl-PTT `fetch` ve global-PTT `net.request` sıralaması yok → geç `active:true` bırakmadan sonra uygulanabilir; `sendPttRequest` timeout yolunda telafi `active:false` göndermiyor. |
| C-05 | 🟡 | **Doğru** | Backend instance değişiminde `window._transcriptRevisions` temizlenmiyor → yeni instance'ta yeniden kullanılan ID'nin düzeltme olayı eski revision yüzünden düşebilir. |
| C-06 | 🟡 | **Doğru** | `transkribe.py` yalnız `torch.cuda.is_available()` (50) kullanır; `WhisperModel` CUDA yükleme hatasında CPU fallback yok (buyedektir'in `torch.zeros` canlı denemesinin aksine). |
| D-01 | 🟡 | **Doğru (örnek düzeltildi)** | `_detect_script_lang` (2989-3045) `total` yalnız Latin-dışı scriptleri sayar → tek Kiril/Yunan/Arapça karakter uzun Türkçe metni 'ru'/'el'/'ar'a saptırır (canlı: `'...Ж'` → `ru`). Emoji aralıklarda yok; "tek emoji saptırır" örneği **yanlıştı, geri çekildi**. |
| D-02 | 🟡 | **Doğru** | `/api/translation_settings` `enabled`/`sourceLang`/`targetLang` tip-değer doğrulaması yok. |

## 4. Doğrulanan sağlam alanlar (regresyon yok)

- `X-Whisper-Token` tüm `/api/*`'de; tokensuz istek 401. Socket localhost CORS ile sınırlı (C-02 notuyla).
- `/api/correct` (5349-5408): instance_id + revision + kaynak-rolü korunur; rollback güvenli.
- `_begin_ai_request`/`_finish_ai_request` (193-222): dedup + global slot=2 doğru; sızıntı yok.
- Capture/transcribe/partial/translate işçileri: `_session_id` + `_result_generation` + revision korumalı.
- `load_model`: tek-yükleme kilidi + canlı CUDA denemesi (`torch.zeros`) + `_model_lock` swap — sağlam.
- Frontend düzeltme/AI/hydration akışları: generation/revision/ownership guard'ları tutarlı; tüm innerHTML interpolasyonları `escapeHtml`/`escapeJsString` altında (XSS yüzeyi temiz — önceki yanlış "speaker.name sızar" iddiası bu kapsamda geri çekildi).
- `main.js`: port-sahibi doğrulamalı yetim temizliği, nonce'lu `checkServerReady`, sınırlı backoff, single-instance, IPC sender doğrulaması — sağlam.
- `build.js`: beyaz-liste paketleme + sızıntı taraması — sağlam.

## 5. Doğrulanmış birleşik düzeltme listesi

Bağımsız doğrulamadan süzülmüş haliyle; önem sırasına göre değil kaynak kimliğine göre. Her düzeltmeye deterministik regresyon testi önerilir. **Cevap ve çeviri anahtarları arasında otomatik fallback kurulmamalı — anahtarların ayrı tutulması mevcut proje kararıdır.**

- **N-1:** `/api/ai_chat` kapısı `response_provider`'a göre doğru anahtarı kontrol etsin; hata mesajı sağlayıcı-nötr olsun.
- **N-2:** 4314'teki sağlayıcı kümesine `'anthropic'` ekle; `ANTHROPIC_API_KEY` → `translation_api_keys['anthropic']` tohumla (2700-2705).
- **N-3:** 5094 kümesine `'anthropic'` ekle; Alt-PTT'de ja/zh/ko/ar dahil okunuş üretilsin.
- **N-4:** Açılış POST'larını koşullandır — model POST'u yalnız kullanıcı seçiminde; eski provider'ı anthropic'e zorlama; anahtar re-POST'unu durum 'missing' değilse atla.
- **N-5:** `MicRecorder.start` yalnız cihaz gerçekten açıldığında başarı dönsün veya worker sonucu route/socket'e iletsin.
- **N-6:** transkribe.py'da model/cihaz seçicileri işlem sırasında devre dışı bırak veya `_model` erişimini kilitle.
- **N-8 + B-08:** `generate_ai_response` için `text`/`target_lang` `isinstance(str)` + allowlist doğrulaması; geçersiz veri 400 dönsün.
- **N-9 / B-04:** `translation_settings`'te `apiKey` yoksa mevcut anahtar korunsun; silme için ayrı açık işlem.
- **N-11:** Banner mojibake düzelt.
- **N-12:** Overlay `requestAnswer`'a AbortController + görünür timeout; sonrasında buton yeniden etkin.
- **N-13:** Anthropic doğrulamaya anahtar-bazlı `_verified_api_key` önbelleği.
- **N-14:** `ai_response_toggle` gerçek bool; anthropic çeviri logları "OpenAI" diye etiketlenmesin.
- **B-01:** `ann = getattr(diarization, 'speaker_diarization', diarization)` normalize et; Annotation ve DiarizeOutput için test.
- **B-02:** TorchCodec/FFmpeg'siz dosya fallback'i (veya uyumlu sürüm sabitleme).
- **A-01:** Stop'ta kuyruktaki/işlemdeki son segment sessizce düşmesin — drain/flush semantiği; kabul edilen son konuşma commit ya da açıkça iptal.
- **A-02:** `isOwnedWhisperBackend` 8.3 kısa yol + göreli yol tanısın; `--whisper-electron-child` işareti korunarak.
- **A-03:** Backend çeviri + frontend autoTranslate tek sahiplik — aynı transkriptte çift çağrı olmasın.
- **A-04:** GPU→CPU düşüşünde `gpu_fallback` + hata nedeni UI'a taşınsın.
- **B-03:** Anahtar yokken "çeviri aktif" mesajı gösterme.
- **B-05:** Stale-generation dönüşlerinde `recording_id`'li başarısız `ptt_mic_result` emit et + frontend PTT watchdog.
- **B-06:** `context_buffer`'a mic-modu TR dikte katılmasın; mod/dil değişiminde eski bağlam sızmasın.
- **A-05 + C-04:** Ctrl-PTT'ye `keepalive`; PTT start/stop sequence-serileştirme; timeout'ta telafi `active:false`; "dinleniyor" mesajı sunucu kabulünden önce gösterilmesin.
- **B-07:** String-sayısal `transcript_id`'yi kontrollü int'e çevir; dönüşmeyende bağlam kaydı yapma.
- **D-01:** Baskınlık tüm alfabetik karakter toplamına göre hesaplansın; tek yabancı karakter dil override etmesin.
- **D-02:** `translation_settings` `enabled` bool, `sourceLang`/`targetLang` izinli string; geçersizde 400 + state dokunulmasın.
- **C-01:** `deepl_config` önce aday anahtarı doğrulasın, başarıda atomik commit etsin.
- **C-02:** Socket.IO connect'te APP_TOKEN doğrulaması; istemciler `auth` alanında göndersin.
- **C-03:** `capture_mode='mic'` için dil 'tr' veya auto'ya zorlansın.
- **C-05:** Instance değişiminde `_transcriptRevisions` dahil instance-bağlı state temizlensin.
- **C-06:** transkribe.py CUDA'da gerçek tensor tahsisi dene veya yükleme hatasında bir kez CPU fallback.

## 6. Errata (2026-09-20 düzeltmeleri)

- §3 kimlikleri özgün 15 Eylül anlamlarına bağlandı (önceki sürümde A-01 socket-auth'a, B-02 speaker-badge'e, B-04 açılış drift'ine, B-05 PTT mesajına, B-08 speaker-name'e atanmıştı — hepsi yanlıştı).
- D-01 örneği düzeltildi: emoji `_detect_script_lang` aralıklarında sayılmıyor → saptırmaz; tek Kiril/Yunan/Arapça karakter saptırır (canlı üretildi).
- N-6: yarış gerçek; "native çökme" iddiası kanıtlanmamış olarak işaretlendi.
- N-7: kesin bug kabulünden çıkarıldı → tek seferlik flaky gözlem.
- N-10: bug kabulünden çıkarıldı.
- N-14: `mark_said`/`context_id` maddeleri bug kapsamından çıkarılıp sağlamlaştırma notuna indirildi.
- A-04: "tamamen sessiz" değil — UI `device:'CPU'` gösteriyor; eksik olan neden bilgisi.
- "B-08 speaker.name HTML sızması" iddiası geri çekildi — XSS yüzeyi temiz; B-08'in özgün anlamı `target_lang` tip hatasıdır (N-8 ailesi).

## 7. Sınırlar

- Windows'a özgü ses yolları (pyaudiowpatch/WASAPI) Linux'ta stub ile; gerçek cihaz akışı Windows'ta doğrulanmalı (N-5, N-6'nın çökme boyutu, B-02'nin kökü).
- Gerçek sağlayıcı çağrıları anahtar/ücret nedeniyle stub.
- `/api/devices` Linux'ta 500 — platform sınırlaması.
- N-2/N-3 kod-yolu + test_client ispatlı; uçtan-uca Windows doğrulaması önerilir.
