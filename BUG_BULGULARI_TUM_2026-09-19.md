# Birleşik Derin Test ve Bug Taraması Raporu — 2026-09-19

**Repo:** `dorukakindev/whisper-live-translator` — dal `main`, HEAD `358ca1e`
**Kapsam:** İkinci tur derin tarama. Birinci tur rapor (`DERIN_TEST_VE_BUG_RAPORU_2026-09-19.md`, aynı gün) bu dosyayla **birleştirildi ve onun yerini alır**. 2026-09-15 tarihli `GENEL_DENETIM_RAPORU` bulguları da yeniden doğrulanıp burada tek tabloda toplandı.
**Yöntem:** `test_smoke.py` + arşiv süitleri + tüm Node/Electron testleri + `npm run scan` + Flask `test_client` ile canlı endpoint yüklemesi (fuzz, eşzamanlılık, yetkisiz istek) + satır satır kod denetimi (uygulama kodunda **hiçbir değişiklik yapılmadı**).

---

## 1. Test matrisi

| Test / araç | Sonuç |
|---|---|
| `python test_smoke.py` | ✅ Geçti |
| `tests/archive/` Python süitleri (4 dosya) | ✅ Geçti |
| `tests/` Node testleri (12 dosya, `node` ile tek tek) | ✅ Geçti |
| `tests/` Electron testleri (3 dosya, `DISPLAY=:0` xvfb) | ✅ Geçti |
| `npm run scan` (build.js güvenlik taraması) | ✅ Geçti |
| `py_compile` + `pyflakes` (buyedektir.py ve yardımcı .py) | ✅ Temiz |
| `node --check` (index.html inline script'ler + static/*.js + main/preload/build) | ✅ Temiz |
| `test_game_overlay_native.js` | ⚠️ 4 koşuda 1 kez flaky patladı, tekrarda geçti (N-7) |
| `test_cevap_onerisi.py` | ⏭️ Atlandı — canlı OpenAI kredisi gerektirir (tasarım gereği opt-in) |

Canlı endpoint yüklemesi (Flask test_client, gerçek route'lar): yetkisiz istekler reddediliyor, `/api/*` 401 doğru; JSON-fuzz, tip karıştırma, eşzamanlı AI slot, çift-baslatma ve düzeltme yarışları temiz; istisnalar aşağıdaki bulgularda.

## 2. Yeni bulgular (bu tur, doğrulanmış)

Önem: 🔴 yüksek / 🟠 orta / 🟡 düşük

### N-1 🔴 Claude-only kullanıcıda "Özet Al / Soru Sor" tamamen kapalı
`buyedektir.py:6202` — `/api/ai_chat` yalnız `openai_responder.api_key` (resmi OpenAI anahtarı) kontrol eder:
```python
if not transcriber.openai_responder.api_key:
    return jsonify({'success': False, 'error': 'OpenAI API anahtari gerekli'})
```
`ANTHROPIC_API_KEY` ile açılan ya da sağlayıcıyı Claude seçen kullanıcıda `api_key` None kalır → özet/soru hep "OpenAI API anahtari gerekli" ile reddedilir. Halbuki `answer_question` (1686-1691) `response_provider=='anthropic'` için `anthropic_api_key`'i doğru kullanır ve `/api/status` (5252-5264) sağlayıcı-bilinçli — yani kapı yanlış, üretim yolu doğru. Canlı kanıt: test_client ile anthropic-only durumda `summary` → `{success: False, error: 'OpenAI API anahtari gerekli'}` (200). Ek: hata mesajı da yanıltıcı (sorun OpenAI değil).

### N-2 🔴 Claude canlı çeviri sessizce hiç çalışmıyor (çift duvar)
`buyedektir.py:4314-4320` — transkript işlenirken çeviri kuyruğuna girme koşulu:
```python
if translation_request['provider'] in {'openai','openai_reseller','openai_official'}:
    has_key = bool((translation_request.get('openai') or {}).get('api_key'))
else:
    has_key = bool(translation_request.get('deepl_api_key'))
```
`provider == 'anthropic'` → else dalı → `deepl_api_key` None → `has_key=False` → `translate_executor.submit` hiç çağrılmaz. `translation_status` bile 'pending' olmaz; arayüzde "Claude çeviri aktif" görünür ama hiçbir çeviri üretilmez — **tamamen sessiz ölü özellik**. `translate()` (1977) zaten anthropic'i `_translate_with_openai`'ye doğru yönlendirir; tek engel bu kapı.
İkinci duvar: `ANTHROPIC_API_KEY` ortam değişkeni açılışta `anthropic_api_key`'e yazılır (2700-2705) ama **`translation_api_keys['anthropic']` hiçbir yerde tohumlanmaz** → `.env`'den gelen kullanıcıda, kapı düzeltildikten sonra bile `snapshot_translation_request` `api_key=None` döndürür ve `_translate_with_openai` (2026-2030) "API key yok" diye None verir. Anthropic çeviri **yalnızca** panelden elle anahtar girilince çalışabilir.

### N-3 🟠 Alt-PTT (mikrofonla söyle) Claude sağlayıcıda okunuşsuz kalıyor
`buyedektir.py:5094-5096` — `process_mic_audio` içinde aynı sağlayıcı seti tekrarlanır; 'anthropic' yine eksik → Claude seçiliyken romanized-JSON prompt'lu yol (`answer_question`) yerine düz `translator.translate`'e düşer → `romanized` boş kalır. Üstelik 5164 satırı ja/zh/ko/ar için `_normalize_turkish_pronunciation` fallback'ini hariç tutar → **tam okunuşun en kritik olduğu dillerde hiç okunuş üretilmez**. Frontend etkisi: `cockpit.js:319` `opt.romanized || nativeText` — kart "Böyle söyle · Türkçe okunuş" etiketiyle **okunamaz yerli yazıyı** (漢字, Кирилл, العربية) gösterir; kullanıcı bunu sesli okuyamaz.

### N-4 🟠 Sayfa açılışı backend yapılandırmasını eziyor (model + sağlayıcı + anahtar testi)
`templates/index.html`:
- `syncAITranslationModelOptions` (4748-4766) her çağrıda `/api/ai_translation_model`'e koşulsuz POST atar; `updateTranslationProviderUI` (3117) ← `loadTranslationSettings` (3075) ← `window.onload` (2665) ve her `changeTranslationProvider`'da tetiklenir → `.env`'deki `ANTHROPIC_MODEL`/`OPENAI_MODEL` ilk açılışta dropdown'ın ilk elemanıyla ezilir; provider='deepl' iken bile atılır.
- `loadAIConfig` (4864-4874): `provider === 'openai_official' ? provider : 'anthropic'` eski localStorage değerlerini ('minimax' vb.) **anthropic'e zorlar**, ardından `changeAIProvider()` bunu `/api/ai_provider`'a POST eder → backend cevap sağlayıcısı kullanıcı istemeden değişir.
- `loadAIConfig` (4883): saklı anahtarı her açılışta `/api/ai_response_config`'e yeniden POST eder → `set_api_key` → `test_connection` → **her sayfa yenilemesinde canlı Anthropic/OpenAI API çağrısı** (N-14 ile birleşince yavaşlama).
- `updateTranslationProviderUI`/`updateLanguageSettings` zinciri açılışta `/api/translation_settings`'e de POST eder → N-9'un ana tetikleyicisi.

### N-5 🟡 PTT-mikrofon "recording:true" döner ama kayıt ölü olabilir
`buyedektir.py` `MicRecorder.start` (2332-2351) cihaz açılmadan `True` döner; `_record` thread'indeki hata (2433-2441) yalnız loglanır, socket/HTTP bildirimi yok → `/api/ptt_mic` (4971) `{'recording': True}` dönerken yakalama thread'i çökmüş olabilir; kullanıcı konuşur, bırakınca `stop()` boş/sessiz veri üretir → "Ses anlaşılamadı".

### N-6 🟡 `transkribe.py` çalışırken model değişimi native çökme riski
`transkribe.py`: `_on_model_change` (290-293) `_model=None` yapar; `_run` worker'ı (423) `self._model.transcribe(...)` çağırırken model/combobox değişirse eski ctranslate2 nesnesi GC edilirken transcribe sürüyor olabilir → buyedektir'in `_model_lock` ile engellediği use-after-free sınıfı. Ayrıca `_open_output_folder` (584) `os.startfile` — yalnız Windows'ta var (hedef platform Windows; yine de taşınabilirlik notu).

### N-7 🟡 `test_game_overlay_native.js` flaky
4 koşunun 1'inde assertion patladı, tekrarda geçti — zamanlama/yarış hassasiyeti; CI'ya bağlanırsa ara ara kırmızı üretir.

### N-8 🟡 `/api/generate_ai_response` metin tipi denetimsiz → HTTP 500
`buyedektir.py:5594-5605` — `if not text` sonrası `_is_likely_hallucination(text)` (3054'te `text.strip()`) → `123`, `{}`, `[]`, `true` gibi string-olmayan JSON değerlerinde AttributeError → Flask 500 + stack trace log'a. Canlı kanıt: int ve dict gövdeyle 500 döndü. Kullanıcıdan gelmez ama API'ye dokunan her istemci vurur; `isinstance(text, str)` eksik.

### N-9 🔴 `/api/translation_settings` saklı çeviri anahtarını siliyor
`buyedektir.py:4827-4828` — AI sağlayıcılarında koşulsuz `configure_translation(provider, data.get('apiKey'))`. `apiKey` alanı yoksa veya `''` ise `normalized_key=None` → `translation_api_keys[provider] = None` (**silme**). DeepL dalında kasten `'apiKey' in data` koruması (4831) var; AI dallarında yok — tutarsız.
Canlı kanıt (test_client): `deepl_config` ile `sk-ant-test123` kaydet → `translation_settings` {provider:'anthropic', apiKey alansız} → `translation_api_keys['anthropic'] → None`. Tetikleyiciler: `toggleTranslation`/`updateLanguageSettings` localStorage'dan boş `apiKey` gönderir (profil sıfırlandıysa, yeni makinedeyse veya anahtar yalnız env/`deepl_config` ile girildiyse) → aynı oturumda çeviriler sessizce durur.

### N-10 🟡 `ai_chat` dedup anahtarı bağlamı içeriyor — özet tekrarlarına toleranslı, sorular ayrışıyor (bilgi)
`_begin_ai_request(f'chat:{action}', json.dumps([context_text, question]))` — metin karmasına tüm bağlam girer; iki aynı 'question' farklı bağlamda ayrı istek sayılır (doğru), aynı 'summary' de bağlam değişince yeniden hesaplanır (kabul edilebilir). Kayıt amaçlı.

### N-11 🟡 Banner metinlerinde mojibake
`buyedektir.py:6244-6247` — `logger.info` satırları `"ğŸâ€..."` şeklinde bozuk UTF-8 kalıntısı içeriyor (çift-encoding kazası). Yalnız başlangıç log'u; görünür kusur.

### N-12 🟡 Overlay "Cevap Önerisi" zaman aşımsız
`overlay.html:279-321` — `requestAnswer` fetch'inde AbortController yok; sağlayıcı ~60 sn + retry zinciri sürerken buton "Yükleniyor…"da takılı kalır (ana pencere 60 sn'de abort eder, 5860). Yanıt gelirse koruma (revision/instance guard 296) doğru çalışır; tek eksik zaman aşımı.

### N-13 🟡 Anthropic anahtar doğrulaması her seferinde canlı ağ çağrısı
`buyedektir.py:1640-1668` — `_verified_api_key` önbelleği yalnız `openai_official` için; anthropic dalında eşdeğer yok → `set_api_key`/`test_connection` her çağrıda `GET api.anthropic.com/v1/models` yapar (timeout 5+15 sn). N-4'teki `loadAIConfig` açılış POST'uyla birleşince her yenilemede 20 sn'ye kadar bloklama.

### N-14 🟡 Küçük girdiler/şeyler (kayıt için tek satır)
- `buyedektir.py:5505` `/api/ai_response_toggle`: `enabled` bool'e zorlanmaz (`"evet"` stringi truthy kalır); alan yoksa `False` — bozuk POST AI'yi kapatır.
- `buyedektir.py:5490-5499` `/api/mark_said`: `text`/`turkish` uzunluk sınırı yok; `conversation_turns` (deque 20) şişmez ama prompt'a 8 satır olarak sızar — ucuz kötüye kullanım yüzeyi.
- `buyedektir.py:5660` `context_id`: `transcript_id` int değilse `_next_transcription_id+1`'e düşer (kasıtlı geri dönüş; B-07 ile ilişkili, hata yok).
- `buyedektir.py:2029` `_translate_with_openai` log'u anthropic için de "OpenAI çeviri" der — yanlış etiket (kozmetik).

## 3. 2026-09-15 denetim bulguları — yeniden doğrulama

22 açık bulgu tek tek kod okuyarak ve canlı endpoint'lerle kontrol edildi:

| ID | Durum | Not |
|---|---|---|
| B-01 pyannote 4.x `itertracks` kırılması | **Açık** | `buyedektir.py:2260` `diarization.itertracks(yield_label=True)` hâlâ 3.x API'si; 4.x `DiarizeOutput` döndürür. HF kurulu + diarization açıkken her cümlede exception → `diarization_failed`. |
| B-02 `speaker_updated` kayıtlı konuşmacıyı düşürür | **Açık** | 4733-4755 + frontend `speaker_updated` handler — id senkronu yalnız `speakers` haritasında; olmayan id'lerde kartlarda ad güncellenmez. |
| B-03 başarı mesajı anahtarsız "aktif" diyor | **Açık (yeni örnek)** | index.html:3189 `provider==='anthropic'` dalında apiKey denetimi yok → "Claude çeviri aktif". |
| B-04 `ai_target_lang` açılış drift'i | **Açık** | `loadAIConfig`/`syncAutoTranslateTargetLang` açılışta backend'e POST zinciri kuruyor (N-4 ile kesişir). |
| B-05 PTT başlatma "dinleniyor" mesajı sunucu kabulünden önce | **Açık** | index.html:5175 — `setPtt(true)` sonucu beklenmeden alert. |
| B-07 `transcript_id` int-olmayan tipte sessiz bağlam kaybı | **Açık (belgeli)** | 5659-5661 geri dönüşü kasıtlı; sorun UI'nin `data.id` ile backend `transcriptions[].id` eşleşmeme olasılığı — düşük. |
| B-08 `speaker.name` HTML'e kaçışsız sızar mı | **Kapandı** | Tüm interpolasyonlar `escapeHtml`/`escapeJsString` altında; `speaker.color` sayısal (speakerColors 2640/4219). XSS yüzeyi temiz. |
| B-09 `get_audio_devices` `p.terminate()` finally'de değil | **Kısmen** | Tüm istisna yolları 3463'e ulaşır ama `terminate` fırlatırsa PyAudio nesnesi sızar — kenar durum. |
| A-01..A-05 önceki tur | Açık | A-01 (soket token'sız — tasarım: localhost-only CORS), A-04 GPU→CPU sessiz düşüş (3278 koşulu yalnız yüklü model varken hata döner), A-02/A-03/A-05 aynen geçerli. |
| C-01 `deepl_config` sağlayıcıyı doğrulamadan commit eder | **Açık, genelleşti** | 4774-4775 `translator.provider` kilit içinde koşulsuz yazılır; N-9 ile birleşince tek POST hem sağlayıcıyı değiştirir hem anahtarı silebilir. |
| C-02..C-06 | Açık/Kısmen | C-02 (localStorage=tek kaynak, backend restart'ta ayar kaybı — restoreRuntimeSettings ile hafifletildi), C-05 (revision map eski instance'tan kalma) hâlâ. |
| D-01 `_detect_script_lang` tek Latin-dışı karakter sapması | **Açık** | 2989-3045 `total` yalnız Latin-olmayan scriptleri sayar → "İyiyim 😀" tek emojiyle de dil sapabilir. |
| D-02 `/api/translation_settings` tip doğrulaması yok | **Açık** | 4811-4836: `enabled`/`sourceLang`/`targetLang` doğrulanmaz; N-9'un etkisini büyütür. |

## 4. Doğrulanan sağlam alanlar (regresyon yok)

- Yetki: `X-Whisper-Token` tüm `/api/*`'de (119-128); token'sız istek 401; socket.io yalnız localhost CORS.
- `/api/correct` (5349-5408): instance_id + revision + kaynak-rolü korunur; 409 kaybında kayıt geri döner; rollback güvenli.
- `_begin_ai_request`/`_finish_ai_request` (193-222): `kind:transcript_id` + request_id dedup + global slot=2 → 409/429 doğru; yarışlarda slot sızıntısı yok.
- Capture/transcribe/partial/translate thread'leri: `_session_id` + `_result_generation` + revision korumalı; eski nesil işçi sızamıyor.
- `load_model`: tek-yükleme kilidi, CUDA-canlı-deneme, `_model_lock` altında swap, eski model kilit dışında GC — sağlam.
- Frontend: `saveTranscriptCorrection`/`getAIResponse`/`addTranscription`/`renderPttTranscription`/`hydrateTranscriptions` — generation/revision/ownership guard'ları tutarlı; `ai_options_partial` sahiplik kontrolü (3606-3626) doğru.
- `main.js`: port-sahibi doğrulamalı yetim temizliği, nonce doğrulamalı `checkServerReady`, sınırlı restart backoff, single-instance, contextIsolation+preload, IPC sender doğrulaması (54-62) — sağlam.
- `build.js`: beyaz-liste paketleme + ikili sızıntı taraması — sağlam.

## 5. Önerilen düzeltme önceliği (kod değişikliği bu görevde YAPILMADI)

1. **N-2 + N-9 + C-01** (tek PR mantığı): `4314`'teki sete `'anthropic'` ekle; `configure_translation`'a `api_key is not None`/`'apiKey' in data` koruması; env ANTHROPIC_API_KEY → `translation_api_keys['anthropic']` tohumu (2700-2705).
2. **N-1**: 6202 kapısını sağlayıcı-bilinçli yap (`response_provider`'a göre `anthropic_api_key`/`api_key`).
3. **N-3**: 5094 setine `'anthropic'` ekle → PTT romanized yolu çalışsın.
4. **N-4**: `syncAITranslationModelOptions`'ı koşula bağla (yalnız kullanıcı dropdown değiştirdiğinde POST); `loadAIConfig`'in provider zorlamasını kaldır; açılışta anahtar yeniden-POST'unu durum 'missing' değilse atla.
5. **N-8**: `generate_ai_response` girişine `isinstance(text, str)` kontrolü.
6. Düşükler: N-5 (MicRecorder hatasını emit et), N-6 (transkribe.py model kilidi), N-12 (overlay timeout), N-13 (anthropic verified-cache), N-11 (mojibake temizliği), B-01 (pyannote 4.x uyumu — ayrı iş).

## 6. Sınırlar

- Windows'a özgü ses yolları (pyaudiowpatch loopback, WASAPI) Linux'ta stub ile çalıştırıldı; gerçek cihaz akışı Windows'ta tekrar denenmeli.
- `/api/devices` Linux'ta 500 üretir — platform sınırlaması, bug değil.
- Gerçek API çağrıları (Anthropic/OpenAI/DeepL) ücret/anahtar nedeniyle stub'landı; sağlayıcı iç hataları prompt/parse düzeyinde denetlendi.
- N-2/N-3 "canlı boru hattında gözlendi" değil, kod-yolu + test_client ispatıyla sabitlendi; Windows'ta uçtan uca doğrulama önerilir.
