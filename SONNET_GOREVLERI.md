# Sonnet 5 Görev Listesi — Whisper Pro İyileştirmeleri

**DURUM (2026-07-10): TÜM MADDELER TAMAMLANDI.** Bu oturumda (model claude-sonnet-5) B1, B5-B14, F1, F3-F16, E1-E3 (28 görev) uygulandı ve doğrulandı: `py_compile`+`pyflakes` temiz, `test_smoke.py` 12/12 geçti (yeni testler: `test_auto_mode_style_narrowing`, `test_transcription_id_survives_clear`), tüm inline `<script>` blokları `node --check` temiz, `main.js`/`build.js` sözdizimi temiz. Frontend değişiklikleri canlı önizlemede (F3 kalıcılık, F4 panel-açık-kalma farklı sıralamada dahi, F12 arama, F15 alert limiti, F16 otomatik yeniden deneme, F6 light-mode renkleri) doğrudan test edilip kanıtlandı. E6 (API anahtarı şifreleme) kasıtlı olarak Fable'a bırakıldı, dokunulmadı. Backlog maddeleri (gerçek indirme göstergesi, model profil UX'i, 25sn akıllı bölme) hâlâ yapılmadı, düşük öncelikli.

Aşağıdaki orijinal görev metinleri arşiv/referans amaçlı korunmuştur.

---

Bu liste, kod tabanının derin incelemesinden çıkan ve **iyi tanımlanmış, mekanik, orta seviye bir modelin güvenle yapabileceği** işlerdir. Zor/kesişimsel işler (yeniden bağlanma senkronu, otomatik cevap önerisi, istek sahiplik modeli, hayalet önizleme düzeltmesi, prompt sadeleştirme, cevap zaman aşımı) **zaten yapıldı** — bu dosyadaki işler onların üstüne gelir.

**Her görevden sonra çalıştır:** `python -m py_compile buyedektir.py`, `.venv/Scripts/python.exe -m pyflakes buyedektir.py`, `python test_smoke.py` (backend işleri için) ve inline `<script>` bloklarına `node --check` (frontend işleri için). CLAUDE.md'deki kurallara uy: Türkçe yorumlar, buyedektir.py LF satır sonları, template değişince backend'i yeniden başlat.

---

## Backend (`buyedektir.py`)

### B1. Ses cihazı kopunca sonsuz hata döngüsü ⭐ öncelikli
`_capture_audio` iç döngüsündeki `except` bloğu (`"Input overflowed"` kontrolü olan): cihaz koparsa (BT kulaklık kapanması) `stream.read()` her turda fırlatır → %100 CPU + her turda `error` soket olayı. Düzeltme: `consecutive_errors` sayacı (başarılı okuyuşta sıfırla); hata olunca sayacı artır + `time.sleep(0.05)` + emit'i mevcut `last_emit_time` kalıbıyla throttle et; sayaç > 50 olursa tek bir net "Ses cihazı koptu, yakalama durdu" hatası emit edip `break` (finally zaten `capture_stopped` yayar).

### ~~B2. Maksimum utterance süresi~~ → TAMAMLANDI (Fable, 2026-07-10)
`buyedektir.log`'da somut kanıt bulunmuştu — kesintisiz seste tampon ~20 dakikaya kadar büyüyüp kısmi transkripsiyon `Unable to allocate 29.0 GiB for an array with shape (1, 19489535, 400)` hatası vermişti. Uygulanan düzeltme: `__init__`'e `MAX_UTTERANCE_S = 25.0` ve `MAX_PTT_S = 120.0` eklendi; `_capture_audio`'nun `is_speech` dalında buffer bu süreyi aşınca "Şimdi Gönder" ile aynı yoldan zorla kuyruğa konup `_utterance_seq` artırılıyor (hayalet önizleme önleniyor), `ptt_buffer` için de aynı desen eklendi. Gerçek `_capture_audio` thread'i sahte (mock) PyAudio akışıyla çalıştırılıp doğrulandı: sürekli "konuşma" sinyalinde her segment tam `MAX_UTTERANCE_S`'te sınırlı kaldı, sınırsız büyüme olmadı. **Sonnet bu maddeye dokunmasın.**

### ~~B3. Kısmi önizleme kuyruk sınırı~~ → TAMAMLANDI (Fable, 2026-07-10)
B2 ile aynı pakette uygulandı: yeni `_partial_snapshot(audio_buffer, chunk_seconds)` metodu, önizleme snapshot'ını `PARTIAL_SNAPSHOT_S = 12.0` sn ile sınırlıyor (tampon daha kısaysa tümü döner — davranış korunur). `test_smoke.py::test_partial_snapshot_cap` ile kalıcı regresyon testi eklendi (sentetik chunk dizisi, model/ses donanımı gerektirmez). **Sonnet bu maddeye dokunmasın.**

### B5. 'auto' modda dil tespiti ile stil/rehber seçimi
`generate_ai_response` answer modunda `target_lang == 'auto'` iken TÜM dillerin stil blokları ekleniyor (ja+es+fr+ar+zh+ru) ve `_build_pronunciation_guide('auto')` 6 rehber + OTHER enjekte ediyor; üstelik ar "tire kullanma" ile ja "tire kullan" çelişiyor. Düzeltme: auto iken gelen `text` üzerinde `_detect_script_lang(text)` çalıştır; bir dil dönerse `style_notes` ve `_build_pronunciation_guide` için o dili kullan (auto tespit direktifi kalsın). Latin alfabeli/tespitsiz metinde mevcut davranış korunur. `test_smoke.py`'a vaka ekle.

### B6. Whisper initial-prompt yankısı filtreye eklensin
Whisper sessizlikte `initial_prompt`'u aynen basabilir; `_LANG_INITIAL_PROMPTS` metinleri ("Bu Türkçe bir konuşmadır..." vb. 19 dil) `_is_likely_hallucination`'da yakalanmıyor. Düzeltme: modül yüklenirken `_LANG_INITIAL_PROMPTS.values()`'tan normalize (küçük harf, boşluk/noktalama sıyrılmış) bir set üret (tam metin + tek tek cümleler); filtrede `cleaned` bu setle eşleşirse veya içinde geçiyorsa (mevcut `len(text) <= 90` benzeri uzunluk sınırıyla) True döndür. Smoke testine vaka ekle.

### B7. CJK tekrar döngüsü halüsinasyonu
`_is_likely_hallucination` tekrar tespiti `text.split()` tabanlı; boşluksuz Japonca/Çince tek token sayılıyor, "ありがとうありがとう..." geçiyor. Düzeltme: token kontrollerinden sonra, az boşluklu ve uzunluğu ≥ 12 olan `cleaned` için `re.search(r'(.{2,10})\1{3,}', cleaned)` → halüsinasyon (≥4 ardışık tekrar, doğal "はいはい"yi yanlış yakalamaz). Smoke'a ja/zh vakaları ekle.

### B8. Socket.IO CORS varsayılanını localhost'a indir
Şu an `ALLOWED_ORIGINS` boşken `allowed_origins = "*"` — tarayıcıdaki HERHANGİ bir web sayfası `ws://127.0.0.1:5000/socket.io`'ya bağlanıp canlı transkript akışını okuyabilir. Düzeltme: varsayılanı `["http://127.0.0.1:5000", "http://localhost:5000"]` yap (portu `PORT` env'den okuyarak üret; SocketIO app.run'dan önce kurulduğu için port değişkenini yukarıda hesapla). `ALLOWED_ORIGINS` env override'ı korunur. NOT: Electron↔backend arası ek "oturum anahtarı" ÖNERİLDİ ama GEREKMİYOR — origin kısıtı web sayfalarını keser; localhost'a doğrudan bağlanabilen bir süreç zaten makinede kod çalıştırıyordur, oturum anahtarı ona karşı koruma sağlamaz. Ekleme.

### B9. `/api/clear` id sayacını sıfırlamasın
`/api/clear` `stats['total_transcriptions'] = 0` yapıyor; id bu sayaçtan üretildiği için clear sonrası yeni transkriptler 1'den başlar ve 10-30 sn süren eski bir çeviri (`_translate_async` id ile eşleştirir) YANLIŞ öğeye yapışır. Düzeltme: `__init__`'e hiç sıfırlanmayan `self._next_transcription_id = 0` ekle; `transcription['id']`'yi ondan üret (`self._next_transcription_id += 1`); `stats['total_transcriptions']` yalnız görüntü sayacı olarak kalsın. `_latest_translate_submit_id` mantığı monotonik id ile aynen çalışır. Smoke'a vaka ekle.

### B10. PTT-mic fallback'te okunuş üret
`process_mic_audio` fallback'inde (OpenAI başarısız/JSON bozuk) `translation` DeepL'den geliyor ama `romanized` boş kalıyor — kullanıcı okuyamayacağı Kiril/kana görüyor. Düzeltme: fallback'te `romanized = _normalize_turkish_pronunciation(translation, target_lang)` dene; Latin alfabeli hedefler + ru/el/ka için işe yarar (transliterasyon tabloları mevcut). ja/zh/ar için boş bırak (native script'ten türetilemez).

### B11. MicRecorder hata durumunda `is_recording` bayrağı
`MicRecorder._record` stream hatasında `break` ediyor ama `finally`'de `is_recording = False` yapılmıyor; `/api/ptt_mic` koşulsuz `{'success': True}` dönüyor. Düzeltme: `_record`'un `finally`'sine `self.is_recording = False` ekle; `start()` bool döndürsün (thread hâlâ canlıysa/başlatılamazsa False) ve route bu değeri yansıtsın.

### B12. Asenkron çeviri satırı dosyada yanlış yere yapışıyor
`_translate_async` içindeki `_append_transcript(f"    Çeviri: {translation}\n")` geç yazıldığından araya giren yeni satırların altına düşüyor. Düzeltme: `f"    Çeviri [#{transcription_id}]: {translation}\n"`.

### B13. Çift çeviri çağrısını tekilleştir ⭐ öncelikli (2026-07-10 eklendi)
Çeviri sağlayıcısı OpenAI iken AYNI transkript için İKİ ayrı OpenAI çağrısı gidiyor: (1) backend `_transcribe_audio` → `_translate_async` (sonuç `transcription_translation` soket olayıyla UI'a düşüyor), (2) frontend `addTranscription` → `requestInlineOpenAITranslation` → `POST /api/generate_ai_response mode=translate_dual`. İkisi de `appendInlineTranslationToItem` ile aynı öğeye yazıyor — para israfı + çift render riski. Düzeltme: frontend'deki `requestInlineOpenAITranslation` fonksiyonunu ve `addTranscription` içindeki çağrısını KALDIR; backend yolu (`transcription_translation` dinleyicisi zaten bağlı) tek başına yeterli. Backend yolunun koşulu `translator.enabled && has_key && capture_mode != 'mic'` — inline'ın kapsadığı tek ek durum yok. Doğrulama: çeviri aktif + provider openai iken bir transkriptte network'te tek çeviri isteği görülmeli.

### B14. "Güven" göstergesi aslında dil tahmini olasılığı (2026-07-10 eklendi)
`transcription['confidence']` alanına `info.language_probability` yazılıyor — bu metnin doğruluk güveni DEĞİL, Whisper'ın dil tahmin olasılığı. UI'da `%95` gibi gösterilmesi yanıltıcı. Düzeltme (basit yol): index.html'de confidence rozetlerinin tooltip/etiketini "dil algılama güveni" yap (backend alan adını değiştirme — geri uyumluluk). İsteğe bağlı ileri yol (yapma, Fable'a bırak): segment `avg_logprob`/`no_speech_prob` birleşimiyle gerçek kalite göstergesi.

---

## Frontend (`templates/index.html`)

### F1. socket.io'yu yerelden servis et ⭐ öncelikli
Satır 8: `<script src="https://cdn.socket.io/4.6.0/socket.io.min.js">`. İnternet yoksa `io` tanımsız → `setupSocketListeners` fırlatır → onload'un kalanı ÇALIŞMAZ, uygulama ölü sayfa olur. Düzeltme: `static/` klasörü oluştur, socket.io.min.js'i (4.6.0) oraya koy, satırı `/static/socket.io.min.js` yap (Flask static'i otomatik servis eder). `setupSocketListeners` başına `if (!socket) { showAlert('Socket.IO yüklenemedi', 'error'); return; }` koruması ekle. `package.json` build files listesine ve electron-packager kopyasına `static/**/*` eklenmeli mi kontrol et (dist tam kopya olduğundan otomatik gelir ama `build.files` listesi ayrı).

### F3. "AI Önerileri Aktif" tercihi kalıcı olsun ⭐ öncelikli
`toggleAIResponse()` localStorage'a yazmıyor ve onload geri yüklemiyor; sayfa yenilenince otomatik çeviri (iki checkbox'ın VE'si) sessizce ölüyor. Düzeltme: `toggleAIResponse()`'a `localStorage.setItem('aiResponseEnabled', ...)` ekle; onload'da (autoTranslate/autoAnswer geri yükleme bloklarının yanına) checkbox'ı geri yükle ve backend ile eşitlemek için `toggleAIResponse()` çağır. Aynı geri yüklemeyi `resyncAfterReconnect()`'e de ekle (yeni fonksiyon, setupSocketListeners'ın altında).

### F4. Yeniden çizimde açık okunuş paneli kapanmasın ⭐ öncelikli
`renderAiResult` her `ai_options_partial` olayında ve nihai yanıtta `innerHTML`'i komple yeniler; kullanıcının okumakta olduğu açık okunuş paneli kapanıyor. Düzeltme: `renderAiResult` başında açık panellerin anahtarını topla (id yerine seçeneğin `translation` metniyle anahtarla: `[...resultDiv.querySelectorAll('.answer-option')].filter(o => o.querySelector('[id^="ans-"]')?.style.display === 'block')` içinden ilk `.response-text` metni), render sonrası aynı `translation` metnine sahip seçeneğin panelini yeniden aç.

### F5. Ctrl kombinasyonları PTT'yi tetiklemesin
PTT keydown handler'ı yalın Ctrl ile herhangi bir kombinasyonu ayırt etmiyor; Ctrl+C kopyalama bile PTT başlatıyor. Düzeltme: (a) keydown'da `setPtt(true)`'yu ~150 ms'lik timer'a bağla; (b) Ctrl basılıyken başka bir tuş inerse bekleyen/aktif PTT'yi iptal eden global keydown dinleyicisi; (c) `window.addEventListener('beforeunload', ...)` ile `pttHeld`/`altPttHeld` aktifse `setPtt(false)`/`setAltPtt(false)` gönder (Ctrl+R yenilemesinde backend'de PTT açık kalıyordu).

### F6. Light mode'da görünmeyen renkler
`renderAiResult` başlığı `style="color: white"` (light'ta beyaz üstüne beyaz); cevap seçeneği kartları ve hızlı kalıp/favori kartları `rgba(255,255,255,0.06)` arkaplan/kenarlıkla light'ta görünmez. Düzeltme: `color: white` → `color: var(--text-main)`; kart stillerini `.answer-option` CSS sınıfına taşı ve `body.light-mode .answer-option { background: rgba(0,0,0,0.04); border-color: rgba(0,0,0,0.12); }` override'ı ekle.

### F7. Okunuş yazısını büyüt
Okunuş, uygulamanın EN çok okunan metni ama ~13.6px render oluyor. Düzeltme: `.okunus-text { font-size: 17px; line-height: 1.65; font-weight: 600; color: var(--warning); }` sınıfı tanımla; cevap seçeneği okunuşuna, hızlı kalıplar (12.5px) ve favoriler okunuşlarına uygula.

### F8. `showAlert` ve transkript meta alanları escape edilsin
`showAlert` `innerHTML`'e ham `message` basıyor; `socket.on('error')` sunucudan gelen `str(e)` metnini geçiriyor. Düzeltme: mesaj span'ını `textContent` ile kur (veya `escapeHtml(message)`). `addTranscription`'daki `${data.timestamp}`, `${data.model_language}`, `${data.source_lang} → ${data.target_lang}` interpolasyonlarını `escapeHtml()` ile sar.

### F11. Klavyeden cevap isteme kısayolu
Öneri istemek şu an fare gerektiriyor. Düzeltme: mevcut 1-9 hotkey handler'ındaki focus/modifier korumalarının aynısıyla `C` tuşu: en yeni sistem transkriptini bul (`#transcriptionList .transcription-item[data-transcription-id]` ilk öğe, `partialPreview` id'lisini atla) ve `.ai-answer-btn` butonuyla `getAIResponseById(id, 'answer', btn)` çağır. Boş durum/yardım metnine ipucu ekle.

### F12. Transkript arama kutusu
`#transcriptionList` üstüne küçük bir filtre girişi: yazarken DOM öğelerini `transcriptionTexts` üzerinden gizle/göster; Enter'da `/api/transcriptions`'tan tam listeyi çekip eşleşenleri salt-okunur listele (DOM 100 öğeyle sınırlı, geçmiş yalnız backend'de).

### F13. Transkript öğesi şablonlarını tekilleştir
`addTranscription` 4 dal + mic dalı + `ptt_mic_result` handler'ı neredeyse aynı markup'ı ve budama döngüsünü 3-6 kopya tutuyor. Düzeltme: `buildTranscriptionItem({badgeHtml, timestamp, langBadge, confidence, bodyHtml, translationHtml})` ve tek `pruneList(list)` yardımcıları çıkar, tüm ekleme noktalarında kullan. Davranış birebir korunmalı (escape çağrıları dahil).

### F14. TTS'te dil sesi yoksa uyar
`speakText` eşleşen ses bulamayınca varsayılan (muhtemelen Türkçe) sesle Japonca okuyor — yanıltıcı. Düzeltme: `!voice && lang && lang !== 'tr'` ise `showAlert("❌ Bu dil için Windows'ta yüklü ses yok (Ayarlar → Zaman ve Dil → Konuşma'dan ekleyin)", 'warning')` göster ve konuşma (dil başına bir kez uyarmak yeterli).

### F15. Alert'ler üst üste binmesin
`showAlert` `container.innerHTML = ''` ile önceki mesajı siliyor; art arda olaylarda kullanıcı yalnız sonuncuyu görüyor. Düzeltme: temizlemek yerine append et, en fazla 3 alert tut (fazlasını en eskisinden sil).

### F16. Başlat reddedilirse otomatik yeniden dene (2026-07-10 eklendi)
Günlükte kanıtlı (5 kayıt, hepsi 2 Temmuz): uzun bir transcribe sürerken Durdur+Başlat yapılınca `/api/start` "Onceki yakalama oturumu hala kapaniyor" hatası dönüyor ve kullanıcı elle tekrar tekrar basmak zorunda kalıyordu. Kök neden (dakikalarca süren dev transcribe) MAX_UTTERANCE_S=25 sn düzeltmesiyle büyük ölçüde giderildi; kalan iş UX. Düzeltme: `startCapture()` (index.html) içinde, yanıt `success:false` ve `error` metni "hala kapaniyor" / "zaten calisiyor" içeriyorsa alert basmak yerine 800 ms arayla en fazla 6 kez otomatik yeniden dene; bu sırada status metnini "Önceki oturum kapanıyor, bekleniyor..." yap; denemeler biterse mevcut hata alert'ine düş. Yeniden deneme döngüsü sırasında Başlat butonu devre dışı kalsın (çift tıklama iki döngü başlatmasın).

---

## Electron (`main.js`)

### E1. Sunucu hazırlık beklemesi 15 sn → 60 sn
`checkServerReady`'de `maxRetries = 30` (30×500 ms = 15 sn) ama soğuk açılışta backend importları 40-50 sn sürebilir → uygulama "bağlanılamadı" deyip kapanır. Düzeltme: `maxRetries = 120` (60 sn) yap, hata mesajındaki "15sn"i güncelle.

### E2. Tray yokken pencere kapatma gizlemesin
`close` handler'ı tray olmasa bile `preventDefault + hide` yapıyor; tray ikonu yüklenemezse pencere kalıcı kaybolur. Düzeltme: `minimize` handler'ındaki gibi `if (!isQuitting && tray)` koşuluna bağla; tray yoksa normal kapanış (`isQuitting = true; app.quit()`).

### E3. Ctrl+Shift+I global kısayol olmasın
`globalShortcut.register('CommandOrControl+Shift+I', ...)` SİSTEM GENELİNDE kaçırıyor — başka uygulamalardaki DevTools kısayolunu gasp eder. Düzeltme: globalShortcut yerine `mainWindow.webContents.on('before-input-event', ...)` ile pencereye özel yakala (menüde zaten Dev Tools accelerator'ı var; global kaydı tamamen kaldırmak da kabul).

---

## Genel

### ~~G1. Git deposunu yeniden kur~~ → İPTAL
Kullanıcı git istemiyor (2026-07-10'da denendi ve kaldırıldı). Bir daha önerme. Değişiklik öncesi elle dosya yedeği al.

### ~~E5. electron-packager paket sızıntısını kapat~~ → TAMAMLANDI (Fable, 2026-07-10)
Doğrulanmıştı: eski `dist/Whisper-Pro-win32-x64/resources/app/` içinde `api.txt` (25 B), `OPENAI.txt` (166 B), `token (2).txt` (164 B) — anahtar boyutunda dolu dosyalar — artı 2,8 MB `transcriptions.txt`, `archive/`, `whisper_models/`, debug HTML'leri bulundu. Kök sebep: `package.json`'daki `build` config bloğu electron-builder söz dizimiydi ve gerçek araç (`electron-packager` CLI, `--ignore`'sız) tarafından hiç okunmuyordu.

Uygulanan düzeltme: yeni [build.js](../build.js) dosyası `electron-packager`'ın Node API'sini KARA LİSTE değil **BEYAZ LİSTE** (`ignore: file => !isKept(file)`) ile çağırıyor — yalnız `main.js`, `preload.js`, `buyedektir.py`, `package.json`, `templates/`, `assets/`, `node_modules/` pakete giriyor; gelecekte kazayla oluşan yeni bir dosya (bu sızıntıya yol açanlarla aynı türden) otomatik olarak dışarıda kalıyor. Build sonrası dahili bir tarayıcı da hassas dosya adı deseni (`token`, `api.txt`, `.env`, `transcriptions`, `.log`, `secret`, `credential` vb.) bulursa build'i başarısız sayıyor. `package.json`'daki ölü/yanıltıcı `build` config bloğu kaldırıldı, `scripts.build` artık `node build.js`.

Doğrulama: eski sızmış `dist/` silindi, temiz build alındı (2,0 GB → 279 MB), hem build.js'in kendi taraması hem bağımsız `find` taraması sızıntı bulmadı; `templates/index.html`, `assets/*.ico`, `node_modules/electron-store` pakette doğru şekilde mevcut.

**KULLANICI AKSİYONU (henüz yapılmadı):** Bu exe daha önce başkasına gönderildiyse veya bir yere yüklendiyse içindeki anahtarlar (OpenAI, muhtemelen HF/DeepL) İFŞA OLMUŞ sayılmalı ve ilgili panellerden yenilenmeli. Dosya içerikleri okunmadı (yalnız dosya adı/boyutu incelendi), o yüzden anahtarların GERÇEKTEN dolu olup olmadığı teyit edilmedi ama isimler/boyutlar güçlü işaret.

### E6. API anahtarlarını şifreli sakla → FABLE YAPACAK (Sonnet dokunmasın)
Doğrulandı: OpenAI anahtarı `localStorage('openaiApiKeyShared')`, DeepL anahtarı `translationSettings.apiKey`, HF token'ı benzer şekilde tarayıcı depolamasında DÜZ METİN duruyor (ayrıca `.env` de düz metin). Plan: Electron `safeStorage` (Windows'ta DPAPI) + `ipcMain`/`contextBridge` ile anahtarları main process'te şifreli sakla, renderer'a yalnız "kayıtlı anahtar var" bilgisini ver, backend'e main process üzerinden ilet; mevcut localStorage kayıtlarından tek seferlik migrasyon + temizlik. Kesişimsel iş (main.js + preload.js + index.html + backend akışı), Fable üstlenecek. Gerçekçi beklenti notu: DPAPI aynı Windows kullanıcısı altında çalışan her sürece açıktır; bu koruma esas olarak disk kopyalama/başka kullanıcı senaryolarına karşıdır — o yüzden işlevi bozan maddelerin ÖNÜNE alınmadı.

---

## Backlog (düşük öncelik — şimdilik yapma)

- **Gerçek model indirme göstergesi:** `load_model` şu an ilerlemeyi kelimenin tam anlamıyla simüle ediyor (yorum: "İndirme ilerlemesini simüle et" — 0 gönderiliyor, bitince 100). Gerçek yüzde/hız/kalan süre/iptal, huggingface_hub'ın tqdm hook'una bağlanmayı gerektirir; model indirme model başına bir kez yaşandığından değer/karmaşıklık oranı düşük. Ara çözüm (istenirse): belirsiz (indeterminate) ilerleme çubuğu + "indiriliyor..." metni — sahte %0 baştan yanıltıcı görünmesin.
- **Model seçiciyi profillere indirger:** çeviri/cevap model listelerinde codex/reasoning modelleri de var; kullanıcıya `Hızlı / Dengeli / En kaliteli / En ucuz` profilleri + "Gelişmiş" altında mevcut tam liste gösterilebilir. Dil ayarları sadeleştirmesiyle ("benim dilim / karşı dil") AYNI turda ele alınmalı — ikisi de ayar-UX yeniden düzeni.
- **25 sn zorunlu kesimde akıllı bölme:** zorla bölme kelime ortasına denk gelebilir; bölmeden önce son ~1,5 sn'deki en düşük RMS'li chunk sınırından kes, kalanı yeni tampona devret. Kalite iyileştirmesi, engelleyici değil.
