# WHISPER PRO — GENEL KOD DENETİMİ, BUG ve GELİŞTİRME RAPORU
**Tarih:** 15 Eylül 2026
**Kapsam:** Tüm uygulama (`buyedektir.py`, `templates/index.html`, `templates/overlay.html`, `static/*.js`, `main.js`, `main_helpers.js`, `preload.js`, `transkribe.py`, `build.js`, `launcher_whisper.py`, `başlat.bat`)
**Durum:** Kodda değişiklik yapılmadı — yalnızca denetim ve raporlama.
**Önceki raporlar:** `BUG_TARAMASI_TAM_RAPOR.md` (15 kritik + 27 yüksek + 35 orta) ve `DERIN_BUG_TARAMASI_RAPORU.md` (30 madde) bu rapora konsolide edildi; her madde güncel koda karşı tek tek doğrulandı.

---

## 1. YÖNETİCİ ÖZETİ

Önceki iki rapordaki **30 + 70+ bulgunun büyük çoğunluğu güncel kodda düzeltilmiş** durumda. Özellikle veri kaybı sınıfındaki kritik hatalar (kısa cevapların halüsinasyon sayılması, Alt-PTT dil tersliği, HF token'ın sıfırlamayla silinmesi, Alt+Tab hayalet kayıtları, DSP çökmesi, PTT öğelerinde id eksikliği, sayaç enflasyonu) kapatılmış.

**Hâlâ açık olan doğrulanmış bulgular 7 adet** (1 yüksek, 3 orta, 3 düşük):

| ID | Önem | Özet | Eski kayıt |
|----|------|------|-----------|
| A-01 | 🔴 Yüksek | "Durdur" anında işlemdeki son konuşma hâlâ çöpe atılıyor | DERIN BUG-18 |
| A-02 | 🟠 Orta | `isOwnedWhisperBackend` tam yol eşleşmesi; 8.3 kısa yollarda uygulama açılmıyor | DERIN BUG-29 |
| A-03 | 🟠 Orta | Backend çeviri + `autoTranslateEnabled` birlikte açıksa çift AI çevirisi | DERIN BUG-12 (kısmi) |
| A-04 | 🟠 Orta | İlk GPU yüklemesinde OOM → sessiz CPU fallback | DERIN BUG-17 (kısmi) |
| A-05 | 🟡 Düşük | Ctrl-PTT `setPtt` `keepalive` eksik; kapanışta mikrofon açık kalabilir | DERIN BUG-06 (yarım) |
| A-06 | 🟡 Düşük | `conversation_turns.append` mic yolunda kilit dışında | DERIN BUG-24 (kısmi) |
| A-07 | 🟡 Düşük | CSP meta etiketi yok | TAM B-CFG-001 |

Ayrıca **tasarım gereği olan 1 bilinen sınırlama** (telaffuz sözlüğü yalnız tam-eşleşme, DERIN BUG-30) ve **9 geliştirme önerisi** bölüm 4'te listelendi.

---

## 2. HALEN AÇIK BUGLAR (kanıtlı)

### [A-01] Durdur anında işlemdeki son konuşma hâlâ kayboluyor 🔴
* **Konum:** `buyedektir.py:3501-3512` (`stop_capture`) ve `buyedektir.py:4140-4144` (`_transcribe_audio` commit kontrolü); frontend `templates/index.html:3874-3899` (`stopCapture`).
* **Mekanizma:** `stop_capture` `is_running = False` ve `_result_generation += 1` yapar. Transcribe worker'ı kuyruktaki son sesi Whisper'dan geçirir, fakat commit kontrolü `result_generation != self._result_generation or not self.is_running → continue` ile sonucu düşürür. `/api/stop` öncesinde `/api/flush` çağrılmaz; frontend `stopCapture()` da flush yapmaz.
* **Etki:** Kullanıcı "Durdur"a basmadan hemen önce söylenen son cümle (veya kuyruktaki son 1-2 segment) GPU'da transkribe edilip sessizce çöpe atılır — ne ekrana basılır ne dosyaya yazılır.
* **Öneri:** Normal durdurma ile zorla sıfırlamayı ayır: `/api/stop` önce `flush_now` bayrağını kaldırıp kuyruğu boşaltmalı ve commit kontrolü `is_running` yerine yalnız oturum/generation değişimine bakmalı; ya da frontend `stopCapture()` önce `/api/flush` çağırmalı.

### [A-02] `isOwnedWhisperBackend` 8.3 kısa yollarda hâlâ başarısız 🟠
* **Konum:** `main_helpers.js:9-14`.
* **Mekanizma:** Eşleşme hâlâ `normalized.includes(expectedScript)` — `path.resolve(appDir, 'buyedektir.py')` uzun biçimiyle karşılaştırıyor. Windows WMI `CommandLine`'ı 8.3 kısa biçim (`d:\whispe~1\buyedektir.py`) döndürürse `includes` false verir.
* **Etki:** Kullanıcı adında/dizin yolunda boşluk olan veya 8.3 etkin sistemlerde portu tutan kendi backend'i "sahipsiz" sayılır → `safeToStart=false` → "Port Kullanımda" diyaloğu + `app.quit()`. Sık rastlanmayan ama engelleyici başlatma hatası.
* **Öneri:** Yol eşleşmesini gevşet: yalnızca `buyedektir.py` dosya adı + `--whisper-electron-child` bayrağı, ya da `fs.realpathSync`/kısa-yol çözümüyle iki tarafı da normalize et.

### [A-03] Çift çeviri hâlâ mümkün: backend çeviri + frontend otomatik AI çeviri 🟠
* **Konum:** `templates/index.html:4307-4314` (autoTranslate → `getAIResponseById(id,'translate')` → `translate_dual`) ve `buyedektir.py:4234-4250` (`_translate_async` submit).
* **Mekanizma:** Eski BUG-12'nin "koşulsuz çifte tetikleme" kısmı düzeltildi (bkz. `index.html:4289-4293` notu), fakat iki ayrı anahtar hâlâ bağımsız: sol panel çeviri sağlayıcısı (`/api/translation_settings` → `_translate_async`, DeepL/OpenAI) ve `autoTranslateEnabled` (yalnız localStorage → `translate_dual` AI çağrısı). İkisi birden açıksa aynı transkript için iki ayrı çeviri gider.
* **Etki:** API maliyeti ikiye katlanır; aynı öğede backend `transcription_translation` kutusu + AI `ai-result` kutusu çakışabilir.
* **Öneri:** `autoTranslateEnabled` açıkken backend `translation_settings.enabled` otomatik kapatılsın (veya tersi); UI'da ikisinin aynı anda açık olduğu uyarısı gösterilsin.

### [A-04] İlk GPU model yüklemesinde OOM → sessiz CPU fallback 🟠
* **Konum:** `buyedektir.py:3188-3195`.
* **Mekanizma:** Mevcut model varken OOM artık açık hata döndürüyor (mevcut model korunuyor — düzeldi). Fakat `self.current_model is None` iken (ilk yükleme / model boşaltılmışken) GPU OOM dahil herhangi bir hata `use_gpu = False` ile CPU int8'e düşer; kullanıcıya yalnız `device: 'CPU'` raporlanır, hata ayrıca belirtilmez.
* **Etki:** VRAM'i sınırda olan kartlarda kullanıcı GPU seçtiğini sanırken CPU hızında çalışır; gecikme 10x artar. `load_model` yanıtı `device` döndürdüğü için UI'da ayırt edilebilir ama uyarı yok.
* **Öneri:** `force_cpu=False` iken GPU denemesi OOM ile başarısız olursa yanıta `gpu_fallback: true, gpu_error: '...'` eklenip UI'da uyarı gösterilsin.

### [A-05] Ctrl-PTT `setPtt` `keepalive` eksik — kapanışta PTT takılı kalabilir 🟡
* **Konum:** `templates/index.html:5037-5043` (`setPtt`, keepalive yok) vs `5105` (`setAltPtt`, `keepalive: true` var). `beforeunload` `5087-5090`'da `setPtt(false)` çağrılıyor.
* **Mekanizma:** Alt-PTT için BUG-06 düzeltildi (`keepalive: true`), ama sistem-sesi Ctrl-PTT'sinde aynı düzeltme uygulanmadı. Sayfa kapanışında/yenilemede `setPtt(false)` fetch'i tarayıcı tarafından iptal edilebilir.
* **Etki:** Kullanıcı Ctrl'ye basılıyken pencereyi kapatırsa backend `ptt_active` `MAX_PTT_S` (120 sn) süresi dolana kadar açık kalır; o sürede mikrofon/sistem sesi boşa kaydedilir.
* **Öneri:** `setPtt` fetch'ine `keepalive: true` ekle (tek satır, Alt-PTT ile aynı).

### [A-06] `conversation_turns.append` mic yolunda `_lifecycle_lock` dışında 🟡
* **Konum:** `buyedektir.py:~5117` (`process_mic_audio` sonunda `transcriber.conversation_turns.append({role:'me', ...})`).
* **Mekanizma:** Diğer tüm `conversation_turns` erişimleri (`/api/mark_said` 5403, `_transcribe_audio` 4152, snapshot) `_lifecycle_lock` altında; mic yolundaki bu tek append kilit dışında. CPython'da `deque.append` atomiktir → tek başına çökme riski düşük; asıl risk eşzamanlı `get_conversation_snapshot` iterasyonu sırasında tutarsız sıra.
* **Öneri:** Tutarlılık için `with transcriber._lifecycle_lock:` içine al (diğer çağrılarla aynı desen).

### [A-07] Content Security Policy meta etiketi yok 🟡
* **Konum:** `templates/index.html` ve `templates/overlay.html` — `<meta http-equiv="Content-Security-Policy">` yok.
* **Mekanizma/Etki:** Electron navigasyonu `restrictWindowNavigation` ile sınırlandı ve server-verisi `escapeHtml`/`escapeJsString` ile kaçışlı; yine de derinlemesine savunma için `default-src 'self'` CSP önerilir. `index.html` büyük ölçüde inline script/style kullandığından `unsafe-inline` gerekir — tam kilitleme için scriptleri `static/`e taşımak gerekir (büyük iş).
* **Öneri:** Kademeli: önce `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws://localhost:5000 ws://127.0.0.1:5000`.

---

## 3. BİLİNEN SINIRLAMA (tasarım kararı)

### [L-01] Telaffuz sözlüğü yalnız tam-eşleşmede uygulanır
* **Konum:** `buyedektir.py:741-756` (`_apply_exact_pronunciation_override`).
* **Durum:** DERIN BUG-30'da bildirilmişti; CLAUDE.md bunu bilinçli tasarım olarak belgeliyor ("substring replacement across unrelated native/phonetic alphabets is intentionally not attempted"). Kullanıcı "arigatou" için sözlük okunuşu eklerse "arigatou gozaimasu" cümlesinde uygulanmaz.
* **Not:** Bug değil; aşağıdaki geliştirme önerilerine taşındı (G-05).

---

## 4. GELİŞTİRME ÖNERİLERİ (bug değil, fırsat)

| ID | Öneri | Gerekçe |
|----|-------|---------|
| G-01 | **"Durdur" öncesi otomatik flush** — `stopCapture()` `/api/flush` çağırsın | A-01'i kullanıcı tarafında da kapatır; son söz kaybolmaz |
| G-02 | **`/api/stop`'a `flush=true` parametresi** | Tek istekle "durdurmadan önce kuyruğu bitir" semantiği; ayrı flush+stop race'i kalmaz |
| G-03 | **8.3 yol normalize etme** — `isOwnedWhisperBackend`'de `fs.realpathSync` veya kısa-yol expansion | A-02'yi kökten çözer |
| G-04 | **GPU fallback uyarısı** — `load_model` yanıtına `gpu_fallback` bayrağı + UI banner | A-04'ü kullanıcıya görünür kılar |
| G-05 | **Telaffuz sözlüğü kelime-sınırı ikamesi** — `target` ifadesi çeviri içinde tam kelime olarak geçiyorsa o segmenti kullanıcının okunuşuyla değiştir | L-01'i genişletir; yalnızca aynı alfabe ailesinde güvenli (Latin↔Latin) uygulanmalı |
| G-06 | **`autoTranslateEnabled` + backend çeviri kilidi** | A-03 çift maliyetini önler |
| G-07 | **CSP meta + scriptlerin `static/`e taşınması** | A-07 derinlemesine savunma |
| G-08 | **Frontend unit-test altyapısı** — şu an yalnız `node --check` sözdizimi kontrolü var; `live-flow.js`/`runtime-safety.js` gibi saf mantık modülleri Node'da test edilebilir | Regresyon koruması |
| G-09 | **`setPtt`'ye `keepalive`** + `beforeunload`'da `navigator.sendBeacon` alternatifi | A-05 tutarlılığı |

---

## 5. ÖNCEKİ RAPORLAR — DOĞRULANAN DURUM

### 5.1 `DERIN_BUG_TARAMASI_RAPORU.md` (30 madde) — güncel durum

| # | Başlık | Durum | Kanıt |
|---|--------|-------|-------|
| BUG-01 | Alt-PTT hedef dil tersliği (`whisperLang` gönderiliyordu) | ✅ Düzeltildi | `index.html:5099` artık `aiTargetLang` okur; `keepalive: true` da eklendi |
| BUG-02 | `<3` karakter halüsinasyon sayılıyordu ("はい", "OK" siliniyordu) | ✅ Düzeltildi | `buyedektir.py:2960-3055` `_is_likely_hallucination` uzunluk eşiği kaldırıldı; yalnız alfasayısal-olmayan gürültü eleniyor |
| BUG-03 | Answer modunda `<4` karakter reddediliyordu | ✅ Düzeltildi | `generate_ai_response` (5477+) içinde `mesaj cok kisa` kontrolü yok |
| BUG-04 | `remove_overlap` alt-dize katliamı | ✅ Düzeltildi | `transkribe.py:60-97` n-gram kelime örtüşmesi; `new_lower in prev_lower` kaldırıldı |
| BUG-05 | `launcher_whisper.py` `npm` bulamıyor | ✅ Düzeltildi | `launcher_whisper.py:26-27` `shutil.which('npm.cmd' if win32)` |
| BUG-06 | `beforeunload` mikrofon kapatma iptali | ✅ Düzeltildi (Alt) / ⚠️ kısmen (Ctrl) | `setAltPtt` `keepalive: true`; `setPtt`'de yok → A-05 |
| BUG-07 | DeepL Pro anahtarları desteklenmiyor | ✅ Düzeltildi | `buyedektir.py:1820-1822` `endpoint_for_key` `:fx` kontrolü |
| BUG-08 | `set_response_model` legacy alias kontrolü yok | ✅ Düzeltildi | `buyedektir.py:1497-1499` `_legacy_aliases` kontrolü eklendi |
| BUG-09 | PTT öğelerinde `data-transcription-id` yok | ✅ Düzeltildi | `index.html:4067-4068` `item.dataset.transcriptionId` + `transcriptionTexts` |
| BUG-10 | `totalCount` restore'da çifte sayım | ✅ Düzeltildi | `index.html:4302` `if (!restoring)` koruyucu |
| BUG-11 | Çeviri `:` kırpması | ✅ Düzeltildi | `index.html:5561` yalnız bilinen ön-ekler (`Line N`, `Hedef`, `Target`) siliniyor |
| BUG-12 | Çifte OpenAI çevirisi | ⚠️ Kısmen | Koşulsuz tetikleme kaldırıldı (`index.html:4289-4293` notu) ama iki anahtar birlikte açılabiliyor → A-03 |
| BUG-13 | `MicRecorder.stop_stream` PortAudio yarışı | ✅ Düzeltildi | `buyedektir.py:2258,2382-2384` `_stream_lock` |
| BUG-14 | Kanji-ağırlıklı Japonca `zh` sanılıyordu | ✅ Düzeltildi | `buyedektir.py:2938-2950` Kana varsa `ja`; `zh_han` baskınsa `detected_lang` kullanılır |
| BUG-15 | `transkribe.py` Tkinter thread-unsafe `_log` | ✅ Düzeltildi | `transkribe.py:303-304` `_ui_events` kuyruğu + `after(50, ...)` drain |
| BUG-16 | `reset()` HF token'ı kalıcı siliyordu | ✅ Düzeltildi | `buyedektir.py:2241-2247` dosya silinmez, `save_profiles()` ile token korunur |
| BUG-17 | VRAM'de iki model + sessiz CPU düşüşü | ⚠️ Kısmen | Mevcut model varken OOM → açık hata (`buyedektir.py:3191`); ilk yüklemede hâlâ sessiz CPU → A-04 |
| BUG-18 | Durdur'da son konuşma çöpe atılıyor | ❌ Hâlâ açık | `stop_capture` + commit kontrolü aynı → A-01 |
| BUG-19 | Yunanca yok, Kiril→ru zorla | ✅ Düzeltildi | `buyedektir.py:2922,2954-2955` `el` eklendi; Kiril `detected_lang` kullanır |
| BUG-20 | `update_speaker_name` kayıtları güncellemiyor | ✅ Düzeltildi | `buyedektir.py:4660-4665` transcriptions güncellenir + `speaker_updated` soketi; frontend `3525` dinliyor |
| BUG-21 | `saveHFToken` boş token'ı temizleyemiyor | ✅ Düzeltildi | `index.html:2807` `whisperStorage.removeItem('hfToken')` + backend'e bildirim |
| BUG-22 | `URL.revokeObjectURL` senkron iptal | ✅ Düzeltildi | `index.html:4469` `setTimeout(...,1000)` |
| BUG-23 | `seenTranscriptionIds` temizlenmiyor | ✅ Düzeltildi | `index.html:3984-3986` `seenTranscriptionIds.delete(removedId)` |
| BUG-24 | `conversation_turns.append` kilitsiz | ⚠️ Kısmen | Ana pipeline + `mark_said` kilitli; mic yolundaki tek append hâlâ dışarıda → A-06 |
| BUG-25 | `_resample_filter` eşit oranlarda `firwin` çökmesi | ✅ Düzeltildi | `buyedektir.py:282-283` eşit oranlarda erken dönüş |
| BUG-26 | Alt+Tab/Alt+F4 hayalet kayıt | ✅ Düzeltildi | `index.html:5171-5189` 150ms `altPttPendingTimer` + `e.altKey` ile başka tuşta `finishAltPtt(true)` |
| BUG-27 | `get_context_prompt` kelime ortası kesme | ✅ Düzeltildi | `buyedektir.py:2840-2846` boşluk sınırından dilimleme |
| BUG-28 | `<0.5s` cümleler VAD'de siliniyor | ✅ Düzeltildi | `buyedektir.py:3772` eşik `> 0.2` saniyeye indi |
| BUG-29 | 8.3 kısa yollarda `isOwnedWhisperBackend` başarısız | ❌ Hâlâ açık | `main_helpers.js:11-13` hâlâ tam yol `includes` → A-02 |
| BUG-30 | Telaffuz override yalnız tam-eşleşme | ℹ️ Tasarım kararı | CLAUDE.md'de bilinçli olarak belgelendi → L-01 |

### 5.2 `BUG_TARAMASI_TAM_RAPOR.md` — kritik/yüksek maddelerin durumu

| # | Durum | Not |
|---|-------|-----|
| B-FR-001 renderAiResult null guard | ✅ | `renderAiResult` içinde `aiResult` elemanı kontrol ediliyor |
| B-FR-002 socket.off birikimi | ✅ | Tek `setupSocketListeners` kurulumu; sayfa tek yüklemede kalıyor |
| B-FR-003 saveHFToken .catch | ✅ | `index.html:2807-2812` boş-token yolu + catch var |
| B-FR-004 startCapture retry/stop race | ✅ | `stopCapture` `cancelCaptureStartRetries()` çağırıyor |
| B-FR-005 stopCapture success=false | ✅ | `else` dalında `data.error` gösteriliyor |
| B-BE-001/016 conversation_turns kilit | ⚠️ | Ana akış kilitli; mic yolu append'i dışarıda → A-06 |
| B-BE-002 transcriptions deque çakışması | ✅ | Tüm erişimler `_lifecycle_lock` altında |
| B-BE-003 speaker_names race | ✅ | `_profile_lock` eklendi |
| B-BE-004/005/006 session kontrolleri | ✅ | `process_mic_audio` generation kontrolleri (4951, 5083, 5099); partial emit session kontrollü |
| B-BE-007..015 | ✅ | `_stream_lock`, `_model_lock`, `_lifecycle_lock`, `_profile_lock`, queue sentinel, stream read timeout, tek-writer `_append_transcript` — doğrulandı |
| B-INF-001/002 build whitelist | ✅ | `build.js` allowlist + sızıntı taraması |
| B-INF-003 electron-store v8 ESM | ✅ | Bu ortamda `require('electron-store')` çalışıyor (v8 CJS-interop); try/catch + `store=null` fallback de var |
| B-INF-004 launcher shell=True | ✅ | Liste argümanı + `shutil.which` |
| B-INF-005 session cookie | ✅ | Uygulamada oturum çerezi yok; token header tabanlı |
| B-FR-006..011 fetch/.catch eksikleri | ✅ | Merkezi fetch sarmalayıcı `X-Whisper-Token` ekliyor; kritik çağrılar catch'li |
| B-FR-009 indirme `\n` | ✅ | `index.html:4414` `NL='\r\n'` |
| B-TST-001..003 | ✅ | `test_smoke.py` yeniden yazıldı; transkribe file-handle'ları `with` bloklarında |
| B-DBG-001..005 | ✅ | API anahtarları HTML'de yok; `showAlert`/`correctText`/`addTranscription` kaçışlı |
| B-CFG-001 CSP | ❌ | Hâlâ yok → A-07 |
| B-CFG-002/003 raw hata sızıntısı | ✅ | Socket hata olayları sanitize ediliyor; OpenAI detayları log'a, kullanıcıya özet |
| B-DEP-001..003 | ✅ | `webrtcvad`/`pyannote` kurulu; GPU torch çalışıyor (aşağıdaki doğrulama bölümü) |

---

## 6. DOĞRULAMA (bu oturumda çalıştırılanlar)

| Komut | Sonuç |
|-------|-------|
| `python -m py_compile buyedektir.py` | ✅ `py_compile OK` |
| `python -m pyflakes buyedektir.py` | ✅ hata yok |
| `python test_smoke.py` | ✅ `TUM TESTLER GECTI` (ayar sınırları, telaffuz tabloları, halüsinasyon filtresi, cevap-modu paralel+partial+dedup, JSON salvage, pause/flush, mic worker, diarization, clear-generation, çeviri backlog, model-load kilitleri, AI rate limit, chat doğrulama) |
| `node --check` — `static/cockpit.js`, `live-flow.js`, `quick-phrases.js`, `reading-mode.js`, `runtime-safety.js`, `html-utils.js`, `main.js`, `main_helpers.js`, `preload.js`, `build.js` | ✅ hepsi geçti |
| `node --check` — `index.html`/`overlay.html` inline scriptleri | ⚠️ Jinja placeholder (`{{ app_token|tojson }}`) nedeniyle doğrudan parse edilemedi; `"TOKEN"` literal ile değiştirilip kontrol edildi → geçti. Bu bir doğrulama yöntemi sınırlamasıdır, uygulama hatası değil. |
| `git status` | Çalışma ağacında bu rapor + eski raporlar untracked; kod değişikliği yok |

---

## 7. ÖNCELİK SIRASI ÖNERİSİ

1. **A-01** — Durdur'da son konuşmanın kaybı (kullanıcı-verisi kaybı; tek satır frontend flush çağrısıyla kısmen, backend'de generation ayrıştırmasıyla tam çözülür).
2. **A-02** — 8.3 yol; etkilenen kullanıcı uygulamayı hiç açamaz.
3. **A-04** — İlk yükleme GPU→CPU sessiz düşüş (kullanıcı fark etmez, performans 10x kötüleşir).
4. **A-03 + G-06** — Çift çeviri maliyeti.
5. **A-05** — Tek satırlık `keepalive` tutarlılığı.
6. **A-06, A-07, G-01..G-09** — düşük öncelik, sonraki sprintler.

---

*Bu rapor statik kod incelemesi + yukarıdaki doğrulama komutlarına dayanır; çalışma-zamanı (runtime) davranışı her ortamda birebir doğrulanmamıştır. Özellikle A-01/A-04 gerçek donanım/ses akışında yeniden üretilmelidir.*
