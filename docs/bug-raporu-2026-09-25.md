# Derin Bug Taraması Raporu — 2026-09-25

**Repo:** `dorukakindev/whisper-live-translator` — dal `main`, denetlenen kod `8ec70dc`
**Kapsam:** A'dan Z'ye tam tur — backend (`buyedektir.py` ~6529 satır), frontend (`templates/index.html` ~6411 satır + `static/*.js`), overlay, Electron (`main.js`, `main_helpers.js`, `preload.js`), paketleme (`build.js`), `transkribe.py`, test altyapısı.
**Yöntem:** Satır satır kod denetimi + Flask `test_client` canlı problar + tüm kalıcı test süitleri + `npm run build` ve paket denetimi. Uygulama kodunda **hiçbir değişiklik yapılmadı**.
**Önceki turlar:** `BUG_BULGULARI_TUM_2026-09-19.md` (N-1..N-14, A/B/C/D serisi) ve `docs/overnight-hardening-2026-09-22.md` (P1-P13) bulguları bu HEAD'de tek tek yeniden doğrulandı.

---

## 1. Test matrisi

| Test / araç | Sonuç |
|---|---|
| `python -m py_compile buyedektir.py` | ✅ Temiz |
| `python -m pyflakes buyedektir.py` | ✅ Temiz |
| `python test_smoke.py` (kalıcı süit + `tests/archive/` + `tests/test_concurrency_audit.py` + `tests/test_capture_lifecycle.py`) | ✅ `TUM TESTLER GECTI` (bu oturumda yeniden koşuldu) |
| `tests/test_answer_harness.py` | ✅ 6/6 |
| `tests/test_pronunciation_fixture.py` | ✅ 9/9 |
| Çeviri işçisi / ses tanı / enhancement süitleri | ✅ 4/4, 5/5, 16/16 |
| Frontend JS süitleri (complete/follow-up/new-report/third-report, cockpit, game-mode, overlay) | ✅ Geçti |
| Electron testleri (`test_overlay_stale`, `test_capture_lifecycle`, `test_game_overlay_native` — Electron runtime ile) | ✅ Geçti |
| `tests/test_soak.py` (30 sn sentetik yük) | ✅ 25 final / 445 partial / 0 hata / backlog 0 / thread sızıntısı yok |
| Inline-JS + `node --check` (main.js, main_helpers.js, preload.js, build.js) | ✅ Temiz |
| `npm run scan` (kaynak sızıntı taraması) | ✅ Temiz |
| `npm run build` → `dist/Whisper-Pro-win32-x64` | ✅ Üretildi; exe ~190 MB, `PYTHON-GEREKSINIMI.txt` yerinde, paket-içi sızıntı taraması temiz; `resources/app` beyaz listeyle birebir (main.js, main_helpers.js, preload.js, buyedektir.py, audio_diagnostics.py, requirements.txt, package.json, assets/, static/, templates/) |
| Flask `test_client` canlı probu (27 sözleşme + W-1 senaryoları) | ✅ 27/27 + 20/20 — W-1 deterministik üretildi |
| `test_cevap_onerisi.py` | ⏭️ Atlandı — gerçek API kredisi harcar (opt-in) |
| `test_live_audio.py` (köke özel eski script) | ❌ Fixture uyumsuzluğu — bkz. W-4 |

---

## 2. Bu turun doğrulanmış bulgusu

### W-1 🔴 `/api/translation_settings` boş `apiKey` alanı kayıtlı çeviri anahtarını siliyor — ve frontend bu alanı **her sayfa açılışında** gönderiyor

**Kök:** `buyedektir.py:4984-4986` — AI sağlayıcı dalında koruma yalnız alan *yokluğuna* bakar:

```python
if provider in {'anthropic', 'openai_reseller', 'openai_official'}:
    if 'apiKey' in data:
        transcriber.openai_responder.configure_translation(provider, data.get('apiKey'))
```

`configure_translation` (`buyedektir.py:1597`) `api_key=''` → `normalized_key = None` → `translation_api_keys[provider] = None`. Yani **alanın var olması ama boş olması** korumayı atlatır ve anahtarı siler. DeepL dalında da aynı (`4992`: `str(data.get('apiKey') or '').strip() or None`).

**Tetikleyici (deterministik):** `templates/index.html:2643-2649` `translationSettings.apiKey = ''` ile başlar; `loadTranslationSettings` (3082-3113) localStorage'da anahtar yoksa `apiKey=''` bırakır ve `updateLanguageSettings()` (3170-3181) → `persistRuntimeSettings` (3240-3252) `JSON.stringify({...translationSettings})` ile **`apiKey` alanını her zaman** gönderir. Tetik noktaları: her sayfa açılışı, sağlayıcı değişimi (`changeTranslationProvider`, 3116-3123), hedef dil değişimi, çeviri toggle'ı (3224), `setOtherPartyLanguage` üzerinden gelen dolaylı çağrı.

**Kim etkilenir:** Anahtarı `.env`'den gelen kullanıcılar — özellikle `ANTHROPIC_TRANSLATION_API_KEY` (`buyedektir.py:2748-2751` tohumlar). Sayfa açılışı tohumlanmış anahtarı siler → canlı çeviri sessizce ölür (N-2'nin düzeltmesi bu yolda etkisiz kalır). `/api/status` `translation_key_available.anthropic` anında `false`'a döner ama açılış POST'u UI hidrasyonundan *sonra* gittiği için kullanıcı "Claude çeviri aktif" görmüş olur. localStorage'a kaydedilmiş anahtarı olan kullanıcılar etkilenmez (anahtar her seferinde geri gönderilir); tarayıcı sekmesini `127.0.0.1` (farklı origin → boş localStorage) üzerinden açan ikinci istemci de aynı silmeyi yapar.

**Canlı kanıt (Flask test_client, `WHISPER_SKIP_API_VERIFY=1`):**

| Adım | Beklenen | Gözlenen |
|---|---|---|
| env tohumlama | `translation_api_keys['anthropic']` dolu | ✅ `'sk-ant-SEEDED-KEY'` |
| `POST /api/translation_settings {provider:'anthropic', apiKey:'', ...}` | anahtar korunur | ❌ `key=None` (HTTP 200) |
| ardından `GET /api/status` | `anthropic: true` | ❌ `{'anthropic': False, ...}` |
| kontrol: `apiKey` alanı hiç yok | anahtar korunur | ✅ `'sk-ant-SEEDED-KEY'` |
| `deepl` dalında `apiKey:''` | anahtar korunur | ❌ `translator.api_key=None` |
| sağlayıcı geçişi + `apiKey:''` | reseller anahtarı korunur | ❌ `'reseller-key-123'` → `None` |

**N-9 ile ilişki:** N-9 düzeltmesi "alan yoksa koru" semantiğini getirdi ve `test_smoke.py::test_verified_report_regressions` (1667-1673) bunu kilitledi — ama yalnız *alan-yokluğu* senaryosunu. Frontend'in gönderdiği gerçek yük (`apiKey:''`) kapsam dışı kaldı → bug hâlâ canlı. **Regresyon testi hem yokluk hem boş-string durumunu kapsamalı.**

**İkincil yüzey (aynı kök):** `/api/deepl_config` (`buyedektir.py:4923-4933`) AI-sağlayıcı dalında `api_key` alanı hiç gelmese de `configure_translation(provider, None)` → anahtar silinir **ve** `translator.provider` koşulsuz değiştirilir; yanıt `success:false` döner ama mutasyon çoktan işlenmiştir. Frontend her zaman `api_key` gönderdiği için pratik etki düşük; sözleşme tutarsızlığı olarak kayıtlı.

**Yan etki (bilgi):** `translation_settings`'te boş-olmayan `apiKey` geldiğinde `openai_responder.enabled = True` (4988). `enabled` hiçbir yerde gate olarak okunmuyor (gerçek kapı anahtar varlığı) — salt-yazılır durum, işlevsel bug değil, kaldırılabilir/belgelenebilir.

---

## 3. Önceki bulguların HEAD durumu

### Düzeldiği doğrulananlar (kod + test kanıtlı)

| ID | Durum | Kanıt |
|---|---|---|
| N-1 `/api/ai_chat` yanlış kapı | ✅ | 6463-6469 sağlayıcı-bilinçli anahtar + nötr mesaj |
| N-2 Claude canlı çeviri çift duvar | ✅ | 4437-4438 kümede `anthropic`; 2748-2751 env tohumlama (W-1 ile ayrıca sınırlandı) |
| N-3 Alt-PTT okunuşsuz | ✅ | 5324-5326 kümede `anthropic`; 5391-5394 ja/zh/ko/ar hariç tutma bilinçli + belgeli |
| N-4 açılış POST'ları | ✅ büyük ölçüde | `syncAITranslationModelOptions` (4858-4873) artık saf UI; `loadAIConfig` (4973+) `/api/status`'tan okur, `changeAIProvider(false)` POST atmaz, anahtar re-POST'u yalnız `ai_key_status==='missing'` iken (4987). Artık: localStorage'da kayıtlı model varsa her açılışta yeniden POST edilir (5012, 5032) — env modelini ezer; "kullanıcı tercihi kazanır" tasarımı, bilinçli bırakılabilir |
| N-5 MicRecorder sahte `recording:true` | ✅ | `start` cihaz açılışını `_start_event` ile bekler (2366-2377); hata UI'a taşınır |
| N-6 transkribe model yarışı | ✅ | `_on_model_change` `_running` iken erken döner (293-294) |
| N-8/B-8 tip denetimsizlik | ✅ | 5842-5859 `isinstance` + allowlist + 400; prob 400'leri doğruladı |
| N-9/B-4 anahtar silme | ⚠️ kısmen | alan-yokluğu korunuyor; `apiKey:''` hâlâ siliyor → **W-1** |
| N-11 mojibake banner | ✅ | bozuk dizgeler kodda yok |
| N-12 overlay zaman aşımsız | ✅ | `overlay.html:279-321` AbortController + 60 sn |
| N-13 Anthropic doğrulama önbelleği | ✅ | `_verified_anthropic_api_key` (1647-1648) |
| N-14 bool toggle + mark_said sınırı | ✅ | 5754-5756 bool; 5742-5743 uzunluk sınırı |
| A-1 stop'ta kuyruk kaybı | ✅ büyük ölçüde | `stopCapture` önce `/api/flush` + `/api/stats` boşalma beklemesi (index.html:4018-4026). Artık: 10 sn'yi aşan birikimde son segment yine düşer (sınırlı) |
| A-2 `isOwnedWhisperBackend` | ✅ büyük ölçüde | `--whisper-electron-child` işareti zorunlu; 8.3 kısa-yol senaryosu teorik kaldı |
| A-3 çift çeviri | ✅ | frontend otomatik çevirisi yalnız `!translationSettings.enabled` iken (4451-4453) — yollar karşılıklı dışlayıcı |
| A-4 GPU fallback nedeni | ✅ | `gpu_fallback` + neden yanıtta (3375-3378) |
| A-5+C-4 PTT sıralama/keepalive | ✅ | `keepalive`, monoton `sequence`, `client`, seri `pttCommandChain` (5251-5267); "dinleniyor" mesajı sunucu kabulünden sonra |
| B-1 pyannote `itertracks` | ✅ | `getattr(diarization,'speaker_diarization',diarization)` (2270) |
| B-2 torchcodec/FFmpeg dosya yolu | ✅ | pipeline'a daima bellek tensor'u (2261-2266) |
| B-3 anahtarsız "çeviri aktif" | ✅ | `translationKeyAvailability` `/api/status`'tan hidratlanır (2670, 3712) |
| B-5 stale PTT sonucu takılması | ✅ | `emit_stale_result()` (5401, 5418) |
| B-6 `context_buffer` kirlenmesi | ✅ | yalnız `capture_mode=='system'` ekler (4357); dil/mod değişiminde `clear()` (3617-3618) |
| B-7 string `transcript_id` | ✅ | `isdigit()` kontrollü int dönüşümü (5917-5921) |
| C-1 deepl_config commit sırası | ✅ | aday anahtar önce `test_api` ile doğrulanır (4919-4922) |
| C-2 socket auth yok | ✅ | `connect`'te `auth.token` + `hmac.compare_digest` (145-150) |
| C-3 mic modunda yanlış dil | ✅ | `capture_mode=='mic'` → `whisper_language='tr'` (3612-3613) |
| C-5 instance değişiminde revision kalıntısı | ✅ | `window._transcriptRevisions = {}` (3720) |
| C-6 transkribe CUDA fallback | ✅ | gerçek `torch.zeros` denemesi (51) + yükleme hatasında CPU fallback (413-420) |
| D-1 script-baskınlık saptırması | ✅ | `%30` alfabetik eşik (3080-3081) |
| D-2 `translation_settings` doğrulama | ✅ | bool + allowlist 400'ler (4967-4977) |

### Hâlâ açık / kısmi kalanlar

| ID | Önem | Durum |
|---|---|---|
| W-1 (N-9 devamı) | 🔴 | `apiKey:''` anahtarı siliyor — yukarıda |
| A-1 artığı | 🟡 | Stop, 10 sn boşalma penceresini aşan kuyruk/işlemdeki son segmenti hâlâ sessizce düşürür (`stop_capture` 3683-3705 + emit guard'ları 4307-4311, 4341-4353) |
| N-14 artığı | ⚪ | `_translate_with_openai` boş-sonuç logu anthropic için de "OpenAI çeviri" der (2084) — kozmetik |
| A-2 artığı | ⚪ | 8.3 kısa-yol komut satırı tanınmaz — yalnız teorik (child kendisi mutlak yolla spawn edilir) |
| `openai_responder.enabled` | ⚪ | salt-yazılır durum; gate olarak okunmuyor — ölü bayrak |
| `deepl_config` AI dalı | 🟡 | `api_key` alansız çağrı anahtarı siler + provider'ı koşulsuz değiştirir (W-1 ile aynı kök, ayrı yüzey) |

### Test borcu (ürün bug'ı değil)

- **W-4** `test_live_audio.py` (kökteki eski script) `_capture_audio`'yu `SimpleNamespace` ile sürüyor ama production artık `self._capture_handshake` okuyor (`buyedektir.py:3783`; `__init__` 2577'de, `start_capture` 3650'de kurulur). Fixture'a `_capture_handshake` alanı eklenmeden geçmez — **uygulama kodu sağlam**, test harness'i bayat. Bu turda dokunulmadı (kod değişikliği yasağı).

---

## 4. Uygulama planı (önerilen sıra)

1. **W-1 düzeltmesi (öncelikli, küçük yüzey):**
   - `buyedektir.py` `translation_settings`: AI dalında `if 'apiKey' in data` yerine `api_key = data.get('apiKey'); if api_key is not None and str(api_key).strip()` → **yalnız boş-olmayan** anahtar yazılsın; silme işlemi yalnız açık `deepl_config` (veya yeni `deleteKey` alanı) üzerinden. Ya da frontend `apiKey` boşken alanı yükten düşürsün — **iki tarafı birden** düzeltmek en sağlamı (derinlemesine savunma).
   - `deepl_config` AI dalı: `api_key` yoksa `configure_translation`'ı çağırma; provider değişimini `success` ile atomik tut.
   - Regresyon: `test_verified_report_regressions`'a `apiKey:''` varyantı ekle (mevcut yokluk testinin yanına); ayrıca `ANTHROPIC_TRANSLATION_API_KEY` tohumlu fixture'da `translation_settings {provider:'anthropic', apiKey:''}` → anahtar korunur.
2. **A-1 artığı (opsiyonel):** `/api/stop`'a "önce kuyruğu commit'le" modu ya da frontend'in 10 sn'lik drain beklemesi aşıldığında kullanıcıya "son cümle düşürüldü" geri bildirimi.
3. **W-4 fixture hizalaması:** `test_live_audio.py` `SimpleNamespace`'e `_capture_handshake` (ve varsa diğer yeni alanlar) ekle; CI'a al ya da `tests/` altına taşı.
4. **Kozmetikler:** 2084 log etiketi sağlayıcı-adını kullansın; `openai_responder.enabled` ya gate olsun ya kaldırılsın.
5. **Windows doğrulama listesi (ortam burada yok):** gerçek WASAPI loopback + cihaz çıkarma, Alt-PTT gerçek mikrofon, Game Mode gerçek oyun penceresi (kilit/click-through/DPI), pyannote gerçek donanım, `test_cevap_onerisi.py` (kredili).

## 5. Sınırlar

- Bu makinede ses donanımı yok; pyaudiowpatch/WASAPI yolları stub/test double ile. Gerçek uçtan-uca ses akışı Windows'ta doğrulanmalı.
- Gerçek sağlayıcı çağrıları (ücret/anahtar) stub; W-1'in sağlayıcı tarafı etkisi kod yolu + durum gözlemiyle kanıtlı, canlı API çağrısı yapılmadı.
- `test_soak.py` 30 sn sentetik koşuldu (uzun 30 dk koşusu önceki turda yapıldı); RSS bu ortamda `-1` döndü.
- Soak/CI testleri Linux harnesi; Electron native davranışlar (globalShortcut, tray) Windows'ta elle doğrulanmalı.
