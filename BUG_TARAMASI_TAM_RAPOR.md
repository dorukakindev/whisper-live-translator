# Whisper Pro — Tam Bug Tarama Raporu

**Tarih:** 2026-07-25
**Kapsam:** Tüm kod tabanı (buyedektir.py, index.html, test_smoke.py, transkribe.py, main.js, build.js, preload.js, launcher_whisper.py, .env.example, .gitignore, _gen_phrases.py, package.json, requirements.txt, CLAUDE.md, AGENTS.md, assets/, static/, archive/, debug_*.html, batch/.bat dosyaları, .claude/, .agents/, .codex/, .git geçmişi, bağımlılıklar)
**Yöntem:** 3 turda ~20 paralel agent ile derin statik analiz
**Kodda değişiklik yapılmadı.**

---

## İçindekiler

1. [Özet Tablo](#özet-tablo)
2. [🔴 CRITICAL (18 adet)](#-critical-18-adet)
3. [🟠 HIGH (28 adet)](#-high-28-adet)
4. [🟡 MEDIUM (35 adet)](#-medium-35-adet)
5. [🟢 LOW (43 adet)](#-low-43-adet)
6. [Tüm Bug'lar — Dosya Bazında Dizin](#tüm-buglar--dosya-bazında-dizin)

---

## Özet Tablo

| Kategori | 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM | 🟢 LOW | Toplam |
|----------|:-----------:|:--------:|:----------:|:-------:|:------:|
| Backend (`buyedektir.py`) | 3 | 8 | 13 | 15 | 39 |
| Frontend (`templates/index.html`) | 3 | 6 | 7 | 10 | 26 |
| Test & Script (`test_smoke.py`, `test_cevap_onerisi.py`, `_gen_phrases.py`, `transkribe.py`) | 0 | 3 | 4 | 4 | 11 |
| Electron & Build (`main.js`, `preload.js`, `build.js`, `package.json`, `launcher_whisper.py`) | 2 | 2 | 3 | 7 | 14 |
| Batch Files (`başlat.bat`, `calistir.bat`, `transkribe.bat`, `başlat-exe.bat`) | 0 | 0 | 0 | 5 | 5 |
| Debug Files (`debug_output.html`, `debug_served.html`) | 6 | 2 | 1 | 2 | 11 |
| Archive (`archive/`) | 1 | 2 | 3 | 1 | 7 |
| Assets & Config (`.env.example`, `.gitignore`, `BAŞLAT.md`, `SONNET_GOREVLERI.md`, `assets/`, `CLAUDE.md`, `AGENTS.md`) | 0 | 2 | 1 | 4 | 7 |
| AI Config (`.claude/`, `.agents/`, `.codex/`) | 0 | 0 | 2 | 2 | 4 |
| Bağımlılıklar (`requirements.txt`, `package.json`, pip env) | 0 | 3 | 3 | 4 | 10 |
| .git Geçmişi | 0 | 0 | 1 | 0 | 1 |
| Cross-file / Infrastructure | 0 | 1 | 1 | 2 | 4 |
| **NET TOPLAM** | **15** | **27** | **35** | **47** | **~124 benzersiz bug** |

---

## 🔴 CRITICAL (15 adet)

### B-FR-001: `renderAiResult` null guard eksik — DOM crash
- **Dosya:** `templates/index.html`
- **Satır:** 4767-4768
- **Tür:** Frontend / DOM Race / Null Reference
- **Açıklama:** `document.getElementById('ai-result-${id}')` null dönebilir (DOM'dan budanmış transkript). `resultDiv.style.display = 'block'` satırında `TypeError: Cannot read properties of null` crash'i.
- **Tetiklendiği senaryo:** 100+ transkript varken AI yanıtı gecikir, `pruneTranscriptionList` eski transcript ID'sini siler, AI yanıtı geldiğinde DOM'da element kalmamıştır.
- **Etki:** JS crash, AI yanıtı gösterilemez, kullanıcıya hata bildirilmez.
- **Çözüm:** `if (!resultDiv) return;` eklenmeli.

### B-FR-002: `setupSocketListeners` — socket.off() hiç kullanılmıyor, listener birikimi
- **Dosya:** `templates/index.html`
- **Satır:** 2789-2945
- **Tür:** Frontend / Memory Leak
- **Açıklama:** 14 adet `socket.on(...)` çağrısı var, hiçbiri `socket.off()` kullanmıyor. `setupSocketListeners()` 2. kez çağrılırsa her event için listener sayısı katlanır.
- **Etki:** Şu an 1x çağrıldığı için çalışıyor, ama "works by coincidence". Refactor'da patlar. Her event 2x+ tetiklenir, DOM'da transkript 2 kere eklenir.
- **Çözüm:** `socket.off()` ile eski listener'ları temizle veya singleton guard ekle.

### B-FR-003: `saveHFToken` fetch'inde .catch() yok
- **Dosya:** `templates/index.html`
- **Satır:** 2251-2290
- **Tür:** Frontend / Missing Error Handling
- **Açıklama:** HF token doğrulama fetch'inde `.catch()` handler'ı yok. Network hatası olursa Promise sessizce reject olur, UI sonsuza dek "doğrulanıyor..." kalır.
- **Etki:** Kullanıcı HF token'ın doğrulanmasını beklerken sonsuza dek bekler.
- **Çözüm:** `.catch(err => { statusDiv.textContent = 'Bağlantı hatası'; ... })` eklenmeli.

### B-FR-004: `startCapture` retry `stopCapture` ile race ediyor
- **Dosya:** `templates/index.html`
- **Satır:** 3116-3158
- **Tür:** Frontend / Race Condition
- **Açıklama:** `setTimeout(() => startCapture(retryCount + 1), 800)` her retry'de yeni bir timeout başlatır. `stopCapture()` bu timeout'ları temizlemez. Kullanıcı "Durdur" dedikten 800ms sonra capture yeniden başlar.
- **Etki:** Kullanıcı Durdur'a basar, app durmuş gibi görünür, 800ms sonra yeniden başlar. Kullanıcı deneyimi felç.
- **Çözüm:** Stale retry guard'ı ekle (`if (!isCapturing) return;` ve retry session ID).

### B-FR-005: `stopCapture`'da `data.success=false` ele alınmıyor
- **Dosya:** `templates/index.html`
- **Satır:** 3141-3153
- **Tür:** Frontend / Missing Error Handling
- **Açıklama:** `stopCapture` sadece `if (data.success)` içinde UI günceller. Backend `{success: false, error: "..."}` dönerse butonlar devredışı kalır, `isCapturing=true` kalır.
- **Etki:** UI kilitlenir, kullanıcı ne Stop ne Start yapabilir, sayfayı yenilemek zorunda kalır.
- **Çözüm:** `else` branch'inde butonları etkinleştir, hatayı göster.

### B-BE-001: `conversation_turns` deque — 2 thread lockSIZ append data race
- **Dosya:** `buyedektir.py`
- **Satır:** 3072, 3599
- **Tür:** Threading / Data Race
- **Açıklama:** `_transcribe_audio` (transcribe thread) ve `process_mic_audio` (`_mic_executor` thread) aynı `deque`'e hiçbir kilit olmadan `append` yapar. CPython C seviyesinde blok tahsisi (realloc) data race'e yol açabilir.
- **Etki:** Segfault, sessiz veri bozulması, AI cevaplarında eksik/karışık conversation history.
- **Çözüm:** `threading.Lock` ile tüm append/list/clear işlemlerini koru.

### B-BE-002: `transcriptions` deque — transcribe + translate thread çakışması
- **Dosya:** `buyedektir.py`
- **Satır:** 3108, 3229
- **Tür:** Threading / Data Race
- **Açıklama:** Transcribe thread `transcriptions.append(...)` yaparken translate worker (`translate_executor`) `list(self.transcriptions)` ile kopyalama yapar. Eşzamanlı `list(deque)` + `append` deque korrupsiyonuna yol açabilir.
- **Etki:** Bozuk deque, çeviri güncellemesi kaçırılır, kullanıcı çeviriyi hiç görmeyebilir.
- **Çözüm:** `threading.Lock` ile tüm erişimleri koru.

### B-BE-003: `speaker_names` dict — 3 thread arası data race
- **Dosya:** `buyedektir.py`
- **Satır:** 1610, 3098, 3340
- **Tür:** Threading / Data Race
- **Açıklama:** `identify_speaker` (diarize_executor), `_transcribe_audio` (transcribe thread), `update_speaker_name` (Flask thread) — üç thread aynı dict'e lock'suz yazar/okur. `save_profiles()` ile eşzamanlı dosya yazımı da çakışabilir.
- **Etki:** Veri kaybı, yanlış konuşmacı etiketlemesi, `speaker_profiles.json` dosyası bozulabilir.
- **Çözüm:** `threading.Lock` ile tüm dict mutasyonlarını ve dosya yazmalarını koru.

### B-BE-004: `_session_id` transcript emit öncesi yeniden kontrol EDİLMİYOR
- **Dosya:** `buyedektir.py`
- **Satır:** 2976 → 3108-3111
- **Tür:** Threading / Stale Session
- **Açıklama:** `_transcribe_audio` while döngüsü başında `_session_id` kontrol eder, ama transcription+emit işlemine kadar (2-30sn) kontrol edilmez. Yeni session başlatılırsa eski session'ın verisi yeni session'a yazılır.
- **Etki:** UI'da hayalet transkriptler, AI cevaplarında karışık conversation history. En sinsi bug.
- **Çözüm:** `if self._session_id != session_id: return` satır 3108 öncesine eklenmeli.

### B-BE-005: `process_mic_audio` hiç `_session_id` kontrol etmez
- **Dosya:** `buyedektir.py`
- **Satır:** 3473-3605
- **Tür:** Threading / Stale Session
- **Açıklama:** PTT mic sonuçları session sınırlarını aşar. Capture stop/start arasında PTT işlenirse yeni session'a ait conversation_turns'e eski veri eklenir.
- **Etki:** AI önerileri geçmiş konuşma ile karışır.
- **Çözüm:** `_session_id` kontrolü ekle, bayat ise conversation_turns append'ini atla.

### B-BE-006: `_transcribe_partial` socket emit'i session stale olduktan sonra
- **Dosya:** `buyedektir.py`
- **Satır:** 3163-3191
- **Tür:** Threading / Stale Session
- **Açıklama:** `_transcribe_partial` 3 noktada `_session_id` kontrol eder, ama son emit'ten (L3191) ÖNCEKİ son kontrol L3185'tedir. Hızlı start/stop/start döngüsünde session değişebilir.
- **Etki:** UI'da hayalet partial preview.
- **Çözüm:** L3191 öncesi `if session_id != self._session_id: return` eklenmeli.

### B-INF-001: `build.js` whitelist tüm dosyaları siliyor
- **Dosya:** `build.js`
- **Satır:** 26-41
- **Tür:** Build / Broken Packaging
- **Açıklama:** `KEEP_FILES` ve `KEEP_DIRS`'de leading slash var (`'/main.js'`, `'/templates'`). electron-packager `ignore` callback'ine pathsiz yol gelir (ör. `'main.js'`). `KEEP_FILES.has('/main.js')` → false. Tüm dosyalar exclude edilir.
- **Etki:** `npm run build` tamamen boş exe üretir. Hiçbir kaynak dosya build'e girmez.
- **Çözüm:** Leading slash'leri kaldır: `'main.js'`, `'templates'`.

### B-INF-002: `static/` dizini build artifact'te yok
- **Dosya:** `dist/`
- **Tür:** Build / Missing Asset
- **Açıklama:** `templates/index.html` `<script src="/static/socket.io.min.js">` yükler. Packaged exe'de `static/` dizini yok. Flask 404 döner.
- **Etki:** Packaged exe'de `io` undefined → tüm socket.io özellikleri (gerçek zamanlı transkripsiyon, AI yanıtları, çeviri) ölü.
- **Çözüm:** `npm run build` yeniden çalıştır. Post-build doğrulama ekle.

### B-INF-003: `electron-store` v8 ESM-only, proje CommonJS
- **Dosya:** `package.json` (satır 15), `main.js` (satır 24)
- **Tür:** Configuration / Runtime Crash
- **Açıklama:** `"electron-store": "^8.2.0"` v8.x ESM-only'dir. Proje `"type": "commonjs"`. `require('electron-store')` → `ERR_REQUIRE_ESM`. `try/catch` sessizce `store = null` yapar.
- **Etki:** Pencere konumu, overlay pozisyonu, tüm kullanıcı ayarları her restart'ta sıfırlanır. Hata gösterilmez.
- **Çözüm:** `electron-store` v6.x'e düşür (son CommonJS uyumlu versiyon).

### B-INF-004: `launcher_whisper.py` shell=True (CWE-78 deseni)
- **Dosya:** `launcher_whisper.py`
- **Satır:** 25-29
- **Tür:** Security / Defensive Weakness
- **Açıklama:** `subprocess.Popen("npm start", ..., shell=True)`. Şu an hardcoded string olduğu için aktif exploit yok, ama `shell=True` tehlikeli desen. Gelecekte path kontrol edilebilir olursa RCE.
- **Etki:** Düşük olasılık, yüksek etki.
- **Çözüm:** `subprocess.Popen(["npm", "start"], ...)` ile değiştir.

### B-INF-005: Session cookie hardening yok (CWE-614)
- **Dosya:** `buyedektir.py`
- **Satır:** 54
- **Tür:** Security / Missing Configuration
- **Açıklama:** `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE` hiçbiri ayarlanmamış. Flask default: Secure=False, HttpOnly=True (modern), SameSite=None.
- **Etki:** Localhost uygulaması olduğu için düşük risk, ama local XSS'de session hijack mümkün.
- **Çözüm:** `app.config.update(SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_HTTPONLY=True)` ekle.

---

## 🟠 HIGH (27 adet)

### Backend — buyedektir.py

#### B-BE-007: `MicRecorder.frames` lock'suz list mutasyonu
- **Satır:** 1727, 1766-1767
- **Açıklama:** `_record()` her chunk'ta `self.frames.append(...)` yapar. `stop()` `np.concatenate(self.frames)` ve `self.frames = []` yapar. Lock yok.
- **Etki:** `np.concatenate` bozuk buffer alabilir, crash veya sessiz veri kaybı.
- **Çözüm:** `threading.Lock` ekle.

#### B-BE-008: "Input overflowed" hatasında ses kırpılıp atılıyor
- **Satır:** 2705, 2932-2934
- **Açıklama:** `exception_on_overflow=False`'a rağmen IOError fırlatılabilir. `except` bloğu hatayı yakalar ve `continue` yapar, ama `data` değişkeni kaybolur. O chunk sessizce kaybolur.
- **Etki:** Yük altında kelimeler kaybolur, konuşmada boşluklar oluşur.
- **Çözüm:** Stream read'i try/except ile iki aşamalı yap.

#### B-BE-009: Chunk-bazlı resampling boundary hatası (tıkırtı)
- **Satır:** 2716
- **Açıklama:** Her 30ms chunk bağımsız `_resample_int16` ile işlenir. FIR filtresi her chunk'ta transient üretir (~10 örnek). Chunk'lar birleştirildiğinde (L2890) her sınırda bu hatalar birikir → işitilebilir tıkırtı.
- **Etki:** 30ms periyotlu duyulabilir tıkırtı. Mikrofon yolu (MicRecorder) bundan etkilenmez (tek geçişte örnekler), sistem sesi yolu etkilenir.
- **Çözüm:** Chunk'ları üst üste bindirerek (overlap-add) resampling yap veya tüm buffer'ı tek seferde resample et.

#### B-BE-010: `_model_lock` crash/deadlock riski
- **Satır:** 1906
- **Açıklama:** `threading.Lock` otomatik release yapmaz. `with self._model_lock:` içinde thread CUDA OOM/segfault/native abort ile ölürse kilit sonsuza dek kilitli kalır. Tüm gelecek transkripsiyonlar (partial, final, mic) bloke olur.
- **Etki:** App ölene kadar tüm transkripsiyon durur. Kullanıcı restart zorunda.
- **Çözüm:** Timeout ekle veya `contextlib.suppress` ile lock ediniminde timeout.

#### B-BE-011: `stream.read()` süresiz blokaj riski
- **Satır:** 2705
- **Açıklama:** `stream.read()`'e timeout parametresi geçilmez. Ses cihazı fiziksel olarak koparsa (USB reset, Bluetooth kesintisi) read süresiz bloke olur. `capture_thread.join(timeout=2)` timeout alır, thread canlı kalır.
- **Etki:** Capture kilitlenir, tüm start/stop döngüleri "Onceki oturum thread'leri hala calisiyor" hatasıyla reddedilir.
- **Çözüm:** Ayrı bir watchdog thread'i ile stream okuma zaman aşımını izle, bloke olursa stream'i kapat.

#### B-BE-012: `speaker_profiles.json` — çift thread eşzamanlı yazma
- **Satır:** 1542, 1613, 3340
- **Açıklama:** `identify_speaker` (diarize_executor) ve `update_speaker_name` (Flask thread) aynı anda `save_profiles()` çağırabilir. `json.dump` + `open('w')` atomik değil.
- **Etki:** `speaker_profiles.json` kısmi yazma ile bozulur, tüm profiller kaybolur.
- **Çözüm:** `threading.Lock` ve atomik rename pattern (temp file → os.replace).

#### B-BE-013: `_append_transcript` file rotation race
- **Satır:** 121-132
- **Açıklama:** İki thread (transcribe + translate worker) aynı anda `_append_transcript` çağırabilir. `os.path.getsize` check → `os.replace` → `open("a")` arasında race var. İki thread aynı anda rename yapabilir.
- **Etki:** Satırlar `.1` yedek dosyasına yazılabilir veya kaybolur.
- **Çözüm:** `threading.Lock` ile tüm fonksiyonu koru.

#### B-BE-014: `capture_stopped` eski session'dan gönderiliyor
- **Satır:** 2970-2972
- **Açıklama:** `_capture_audio` finally bloğunda `socketio.emit('capture_stopped')` koşulsuz çağrılır. `_session_id` kontrolü yapılmaz. Yeni session çalışırken UI'a "Durduruldu" sinyali gider.
- **Etki:** Hızlı start/stop/start döngüsünde UI "Durduruldu" gösterirken backend hala çalışıyor olabilir.
- **Çözüm:** `if session_id == self._session_id:` guard'ına al.

#### B-BE-015: `socketio.emit` cleanup/exception yollarında try/catch yok
- **Satır:** 2972, 3148, 3605
- **Açıklama:** `socketio.emit()` kendisi exception fırlatabilir. finally/except bloklarındaki emit'ler korunmasız. Exception fırlatırsa ya thread çöker ya da executor worker'ı ölür.
- **Etki:** Transcribe thread çökerse tüm transkripsiyon durur. UI hata alamaz.
- **Çözüm:** Tüm emit'leri `try/except Exception: pass` ile sar.

#### B-BE-016: `transcriptions` deque + `conversation_turns` deque + `context_buffer` deque + `stats` dict — tümü locksuz
- **Satır:** 1817 (transcriptions), 3068 (context_buffer), 3072 (conversation_turns), 3079-3080 (stats)
- **Açıklama:** Dört adet paylaşılan mutable veri yapısı transcribe thread, translate worker, Flask route'ları arasında lock'suz erişiliyor. `clear()` + `append()` race'leri var.
- **Etki:** Korrupsiyon, veri kaybı, AI karışıklığı.
- **Çözüm:** Her biri için ayrı `threading.Lock`.

### Frontend — templates/index.html

#### B-FR-006: Yaygın `.catch()` eksikliği (10+ fetch çağrısı)
- **Satır:** 3705-3708, 3711-3726, 2463-2484, 3770-3782, 3794-3798, 3813-3817, 3880-3894, 2472-2477
- **Açıklama:** Bu fetch çağrılarının hiçbirinde `.catch()` handler'ı yok. Network hatası sessizce yutulur.
- **Etki:** Kullanıcı ayar değişikliğinin başarısız olduğunu görmez. API key değişikliği gibi kritik işlemler sessizce başarısız olur.
- **Çözüm:** Her fetch zincirine `.catch(err => { showAlert('Bağlantı hatası', 'error'); })` ekle.

#### B-FR-007: 5 ayrı `document.addEventListener('keydown', ...)` — listener birikimi
- **Satır:** 3993, 4016, 4049, 4105, 4255
- **Açıklama:** Beş ayrı keydown listener'ı module seviyesinde. Sayfa re-init olursa hepsi birikir. PTT ve C/1/2/3 kısayolları çoklu tetiklenir.
- **Etki:** Potansiyel duplicate API çağrıları, çift UI toggle.
- **Çözüm:** Tek bir keydown listener'ına birleştir veya `AbortController` kullan.

#### B-FR-008: `updateTranslationStatus` timer çakışması
- **Satır:** 2590-2593
- **Açıklama:** `setTimeout(() => { status.classList.remove('active'); }, 3000)` — timeout ID'si saklanmaz. 3sn içinde iki çağrı olursa ilk timeout ikinci mesajın CSS class'ını erken kaldırır.
- **Etki:** Kullanıcı ikinci mesajı görmeyebilir (aktif durum erken kalkar).
- **Çözüm:** Timeout ID'sini sakla, her çağrıda önce temizle: `if (_translationTimer) clearTimeout(_translationTimer)`.

#### B-FR-009: Download `\n` kullanıyor, Windows Notepad'de bozuk
- **Satır:** 3510
- **Açıklama:** `const NL = '\n'` — Unix line ending. Windows Notepad (`\r\n` bekler) ile açıldığında tek satır olarak görünür.
- **Etki:** Kullanıcı transcript dosyasını Notepad'de açtığında tek satır.
- **Çözüm:** `navigator.platform.includes('Win') ? '\r\n' : '\n'`.

#### B-FR-010: `changeAIModel` ve `changeAITranslationModel` success=false sessiz
- **Satır:** 3705-3707
- **Açıklama:** `if (data.success)` başarısız olursa hiçbir işlem yapılmaz, hata gösterilmez.
- **Etki:** Kullanıcı model değiştiğini sanır, hala eski model çalışır.
- **Çözüm:** `else { showAlert(data.error || 'Model değiştirilemedi', 'error'); }`.

#### B-FR-011: 5 adet `fetch()` `.then(response => response.json())` — HTTP hata kodları ele alınmıyor
- **Satır:** 2263, 2472, 3705, 3711, 3880
- **Açıklama:** `response.json()` çağrılmadan önce `response.ok` kontrolü yok. HTTP 500/404'te `.json()` çalışmaz (yanıt HTML olabilir), silent failure.
- **Çözüm:** `.then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })`.

### Test & Infra

#### B-TST-001: `test_resample_clip` vacuous truth
- **Dosya:** `test_smoke.py`
- **Satır:** 375, 380
- **Açıklama:** `over = fl > 32767` boş array ise `np.all([])` → `True`. Taşma oluşmazsa test geçer. Clipping kod yolu hiç test edilmez.
- **Etki:** `np.clip` kaldırılırsa test yakalamaz. Sessiz regresyon.
- **Çözüm:** Precondition'da taşma garantile veya taşma yoksa testi fail et.

#### B-TST-002: `test_answer_contract` dedup doğruluğunu test etmiyor
- **Dosya:** `test_smoke.py`
- **Satır:** 144-151
- **Açıklama:** Sadece opsiyon sayısını kontrol eder (3 = 4 - 1). Hangi opsiyonların hayatta kaldığını kontrol etmez. Yanlış merge'de 3 opsiyon dönse de test geçer.
- **Etki:** Dedup algoritması bozulursa sessiz regresyon.
- **Çözüm:** Opsiyon içeriklerini de assert et: ör. `'Ganbatte'` mevcut, `'Hai sou desu'` tam 1 kere.

#### B-TST-003: `transkribe.py` dosya handle sızıntısı
- **Dosya:** `transkribe.py`
- **Satır:** 412-426
- **Açıklama:** `open()` context manager ile değil. Write loop'unda exception olursa dosyalar kapanmaz, buffer flush edilmez.
- **Etki:** Veri kaybı, leaked handle'lar.
- **Çözüm:** `with open(...) as f:` kullan.

### Debug Files

#### B-DBG-001: Canlı API key'leri HTML value attribute'larında
- **Dosya:** `debug_output.html`, `debug_served.html`
- **Satır:** 1404-1412
- **Açıklama:** Groq API key ve DeepL API key `<input type="password" value="...">` içinde düz metin.
- **Çözüm:** `value` attribute'larını kaldır veya dosyaları sil.

#### B-DBG-002: `transcriptions is not defined` ReferenceError
- **Dosya:** `debug_output.html`, `debug_served.html`
- **Satır:** 2827, 2833, 2884, 2890-2892
- **Açıklama:** `analyzeSentiment()` ve `correctText()` `transcriptions` array'ine erişir ama bu değişken hiç tanımlanmamış.
- **Etki:** "Duygu Analizi"/"Metni Düzelt" butonları crash.
- **Çözüm:** `transcriptions` değişkenini tanımla veya `transcriptionTexts` kullan.

#### B-DBG-003: XSS — `correctText()` innerHTML'e controlsüz injection
- **Dosya:** `debug_output.html`, `debug_served.html`
- **Satır:** 2922
- **Açıklama:** `originalP.innerHTML = ...${data.correction}...` — AI API yanıtı innerHTML'e controlsüz yazılır. MITM'de RCE.
- **Çözüm:** `textContent` kullan.

#### B-DBG-004: XSS — `showAlert()` innerHTML'e controlsüz injection
- **Dosya:** `debug_output.html`, `debug_served.html`
- **Satır:** 2951
- **Açıklama:** `alertDiv.innerHTML = ...${message}...` — server'dan gelen hata mesajları innerHTML'e yazılır.
- **Çözüm:** `textContent` kullan.

#### B-DBG-005: `addTranscription` innerHTML'de controlsüz server verisi
- **Dosya:** `debug_output.html`, `debug_served.html`
- **Satır:** 2263-2346
- **Açıklama:** `data.text`, `data.translation`, `data.speaker_name` gibi server verileri escape edilmeden innerHTML'e `${...}` ile yazılıyor.
- **Çözüm:** Tüm değişkenleri `escapeHtml()`'den geçir.

### Config & Güvenlik

#### B-CFG-001: Content Security Policy (CSP) YOK
- **Dosya:** `templates/index.html`, `main.js`
- **Açıklama:** HTML'de `<meta http-equiv="Content-Security-Policy">` yok. `main.js`'de `session.webRequest.onHeadersReceived` yok.
- **Etki:** XSS varsa inline script çalıştırılabilir, her origin'den script yüklenebilir.
- **Çözüm:** CSP meta tag'i ekle: `default-src 'self'; connect-src 'self' ws://localhost:5000;`.

#### B-CFG-002: Raw `str(e)` socket error event'leriyle UI'a sızıyor
- **Dosya:** `buyedektir.py`
- **Satır:** 2941, 2957, 3148
- **Açıklama:** `socketio.emit('error', {'message': str(e)})` — ham exception string'i UI'a gider. Path leak, OpenAI error leak.
- **Çözüm:** Log'a yaz, kullanıcıya genel mesaj göster.

#### B-CFG-003: Raw OpenAI exception detayı kullanıcıya gidiyor
- **Dosya:** `buyedektir.py`
- **Satır:** 4267-4268
- **Açıklama:** `return jsonify({'success': False, 'error': str(e)})` — rate limit, model overload, content filter mesajlarını kullanıcıya gösterir.
- **Çözüm:** `exc_info=True` ile log'a yaz, kullanıcıya `'AI servisi yanıt vermedi'` göster.

### Bağımlılıklar

#### B-DEP-001: `webrtcvad` kurulu DEĞİL — startup'ta crash
- **Dosya:** `requirements.txt`, `buyedektir.py:34`
- **Açıklama:** `import webrtcvad` module-level import. `webrtcvad-wheels==2.0.14` kurulu değil. Python 3.14 için wheel yok.
- **Etki:** Uygulama AÇILMAZ.
- **Çözüm:** Python 3.12 veya 3.13'e düş, veya webrtcvad'ı lazy import yap.

#### B-DEP-002: CUDA devre dışı — CPU-only torch
- **Açıklama:** `torch 2.10.0+cpu` kurulu. NVIDIA kütüphaneleri (cuBLAS, cuDNN) var ama torch kullanamıyor. `torch.cuda.is_available()` = False.
- **Etki:** GPU transkripsiyon yok, CPU'da ~3x yavaş.
- **Çözüm:** `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128`.

#### B-DEP-003: `pyannote.audio` kurulu DEĞİL
- **Açıklama:** Lazy import olduğu için crash olmaz, ama diarizasyon sessizce başarısız olur.
- **Çözüm:** Python versiyonuna uygun `pyannote.audio` kur.

---

## 🟡 MEDIUM (35 adet)

### Backend — buyedektir.py

| # | Satır | Açıklama | Çözüm |
|---|-------|----------|-------|
| M01 | 1358, 1635, 1746, 1752 | Bare `except:` `SystemExit`/`KeyboardInterrupt`'u da yutar | `except Exception:` ile değiştir |
| M02 | 514-518 | `_clean_json_object` `startswith('```')` ile kırılgan; ````json` öneki varsa çalışmaz | Regex ile esnek yakala |
| M03 | 972 | `not value` valid falsy değerleri (0, "", False) reddeder | `value is None` ile değiştir |
| M04 | 903 | Gürcüce `kh` digraph yanlış pozitif (k+h geçen kelimelerde) | Word boundary ekle |
| M05 | 2791-2794 | VAD fallback'inde sabit threshold (500) — sessiz mikrofon/amplifikasyon hatalı | Relative threshold kullan (`np.iinfo(np.int16).max * 0.02`) |
| M06 | 4113-4124 | JSON çözümlenemeyince ham AI çıktısı kullanıcıya "Türkçe" olarak gösterilir | Ham çıktıyı kontrol et, anlaşılamadı mesajı göster |
| M07 | 22-26 | `python-dotenv` import hatası sessizce yutulur, `.env` yüklenmez, AI özellikleri kapalı | `logger.warning` ekle |
| M08 | 82-85 | Çift `TextIOWrapper` `sys.stdout.buffer` üzerinde — buffer interleaving | `logging.StreamHandler(sys.stdout)` kullan |
| M09 | 134-141 | FIR filter 192kHz'de ~30MB, cache'li bellek şişmesi | max_rate'e üst sınır koy (96000) |
| M10 | 3215-3219 | Translation backlog guard lock'suz, race window | Integer atomik GIL altında, yorum ekle |
| M11 | 1464-1636 | `SpeakerDiarizer.pipeline` GPU belleği asla serbest bırakılmaz → CUDA OOM | `del pipeline; torch.cuda.empty_cache()` |
| M12 | 3229 | `list(self.transcriptions)` kopyalama sırasında append race | Lock altında kopyala |
| M13 | 2564-2573 | `join(timeout=2)` sonrası kurtarma yok → "hala kapanıyor" | Zorla stream kapat + thread terminate |
| M14 | 1851, 3201 | Tek-worker translate executor 60sn OpenAI'de bloke, tüm kuyruk birikir | `max_workers=2` veya timeout'lu worker |
| M15 | 1249-1252, 1294-1296 | OpenAI hata yanıtları kullanıcıya ham `str(e)` ile gidiyor | Genel mesaj göster, detayı log'a yaz |

### Frontend — templates/index.html

| # | Satır | Açıklama | Çözüm |
|---|-------|----------|-------|
| M16 | 3449, 3866-3874 | Token counter clear sonrası eski değere sıçrıyor | Backend'in de token counter'ı sıfırlamasını sağla |
| M17 | 4465-4474 | `buildTranslationResultHtml` iki nokta (`:`) içeren metni kırpıyor (ör. "Let's go: to the store") | Son iki noktaya göre böl veya delimiter marker kullan |
| M18 | 3382 | `innerHTML +=` tüm DOM alt ağacını yeniden ayrıştırıyor | `insertAdjacentHTML('beforeend', ...)` kullan |
| M19 | 3120 | `startCapture` retry timeout'ları `stopCapture`'da temizlenmiyor | AbortController veya retry session ID |
| M20 | 3180 | `flushNow` timer'ları her çağrıda birikir | Timer ID'sini sakla ve temizle |
| M21 | 2591 | `updateTranslationStatus` timer ID'si saklanmıyor | `_translationStatusTimer` değişkenine ata |

### Test & Infra

| # | Dosya | Satır | Açıklama | Çözüm |
|---|-------|-------|----------|-------|
| M22 | `test_smoke.py` | 486-531 | Test state cleanup başarısız olursa tüm modül bozulur | Context manager deseni kullan |
| M23 | `test_smoke.py` | 315-321 | `_salvage_answer_options`'ın `detected_lang` dönüşü test EDİLMİYOR | detected_lang test caseleri ekle |
| M24 | `_gen_phrases.py` | 160-161 | Çıktı JSON manuel kopyalanıyor, hata riski | Doğrudan index.html'e yaz veya runtime fetch |
| M25 | `package.json` | 15 | `electron-store` v8 + CommonJS uyumsuz | v6'ya düşür |
| M26 | `package.json` | 19 | `electron-builder` kullanılmıyor | `devDependencies`'ten kaldır |

### Debug Files

| # | Satır | Açıklama | Çözüm |
|---|-------|----------|-------|
| M27 | 2351-2356 | DOM pruning'de empty-state guard dead code (empty-state zaten kaldırılmış) | Guard'ı kaldır |
| M28 | 1032-1050 | `copy-btn` CSS class'ı isim-semantik uyuşmaz (AI trigger butonlarında) | Yeni class oluştur |

### Archive

| # | Dosya | Açıklama | Çözüm |
|---|-------|----------|-------|
| M29 | `archive/run_whisper.py:10,22` | `chdir` archive'e yapıp parent'taki buyedektir.py'yi arıyor | Path'i `"../buyedektir.py"` yap |
| M30 | `archive/main.py:370-371` | Bare `except: continue` tüm hataları yutar, sonsuz döngü riski | `except OSError` yap |
| M31 | `archive/main.py:409-411` | `stream` tanımsız olabilir, finally'de `UnboundLocalError` | `stream = None` ile başlat |
| M32 | `archive/ai_studio_code.py:626-678` | Duplicate CSS bloğu (copy-paste) | Fazla bloğu kaldır |
| M33 | `archive/__pycache__yedek/` | 8 neredeyse özdeş yedek ~847 KB, gereksiz repo şişkinliği | Git'ten kaldır |

### Config / AI

| # | Dosya | Açıklama | Çözüm |
|---|-------|----------|-------|
| M34 | `.claude/settings.local.json:17` | Eski path `/c/Users/T/...` — proje `D:\`'de | `/d/Whisper Live` ile değiştir |
| M35 | `.claude/launch.json:6` | `runtimeExecutable` göreceli path (`.` ile başlıyor) | `${workspaceFolder}/.venv/Scripts/python.exe` |

---

## 🟢 LOW (47 adet)

### Backend — buyedektir.py

| # | Satır | Açıklama |
|---|-------|----------|
| L01 | 2673, 2886 | `chunk_seconds` native rate'den hesaplanıyor, resample edilmiş veri için mantıksal tutarsızlık |
| L02 | 3858-3885 | `tone` değişkeni `else` garantisine dayanıyor, validasyon yoksa kırılır |
| L03 | 2699-2704, 2799-2811 | Diagnostic counter'lar pause/resume'da sıfırlanmıyor |
| L04 | 3470, 3525-3564 | PTT çeviri provider yokken bile audio kaydı başlatır, kullanıcı boşuna bekler |
| L05 | 1110-1117, 1923-1928, 3747 | Çift `test_connection()` çağrısı (arkaplan + API çağrısı), %2 bandwidth israfı |
| L06 | 1327 | DeepL URL `api-free.deepl.com` hardcoded, Pro kullanıcıları çalışmaz |
| L07 | 1671 | Redundant `import pyaudiowpatch as pyaudio` (module-level zaten var) |
| L08 | 2793 | `logger.debug` olmalı `logger.warning` — VAD düşüşü production'da görünmez |
| L09 | 1823 | `_next_transcription_id` sınırsız büyür (çok uzun session'larda DOM ID'si şişer) |
| L10 | 2537 | `_session_id` sınırsız büyür (sık start/stop'ta) |
| L11 | 532 | `_salvage_answer_options` regex'i `\{[^{}]*\}` iç içe JSON'ı yakalamaz (amaçlanan davranış) |
| L12 | 588-590 | `\s` Unicode whitespace dahil NBSP'yi de eşler, AI çıktısında no-break space kalabilir |
| L13 | 529 | `[a-zA-Z-]{2,8}` language code regex'i region subtag'leri (es-419) desteklemez |
| L14 | 851, 853 | `r'y(?=[aeiou])'` ve `r'v'` no-op entry'ler (yerine kendini koyar) |
| L15 | 2712, 1721 | `np.mean().astype(np.int16)` truncation (yuvarlama değil), ~0.5 LSB kayıp |

### Frontend — templates/index.html

| # | Satır | Açıklama |
|---|-------|----------|
| L16 | 2165-2170 | Quick language select DOM değerini set eder ama `setOtherPartyLanguage()` çağırmaz, radio'lar güncellenmez |
| L17 | 2506-2510 | `localStorage.getItem` boş string dönerse `getCurrentInputLang` sessizce `'tr'` kullanır |
| L18 | 966, 1052-1059 | CSS `.with-translation` vs `.speaker-N` border rengi çakışması, speaker kazanır |
| L19 | 2898, 2912-2913, 3263-3264 | `copy-btn` class'ı kullanılıyor ama CSS'te tanımı YOK (inline style var) |
| L20 | 4791 | `regenerateAnswer`'da `id` `escapeJsString`'den geçmiyor (şu an numeric, güvenli) |
| L21 | 4960-4963 | `showAlert` en eski alert'i değil `firstChild`'i kaldırır, timer ile yarışabilir |
| L22 | 4429-4458 | `appendInlineTranslationToItem` duplicate socket event'lerinde aynı çeviriyi tekrar yazar (görsel flicker) |
| L23 | 3510 | `const NL = '\n'` — Windows'ta Notepad'de düzgün görünmez |
| L24 | 2591 | `updateTranslationStatus` `status` DOM elemanı kaldırılmışsa `classList.remove` no-op |
| L25 | 2677 | `checkInstalledModels` hatayı sadece `console.error` ile loglar, UI bilgilendirilmez |

### Test & Script

| # | Dosya | Satır | Açıklama |
|---|-------|-------|----------|
| L26 | `test_smoke.py` | 77 | Sadece 1 Türkçe test case, early-return blanket skip test edilmez |
| L27 | `test_cevap_onerisi.py` | 107-109 | `auto` caseler gerçek OpenAI API çağrısı yapar, para harcar (guard yok) |
| L28 | `transkribe.py` | 303 | `import time as _time` fonksiyon içinde, her çağrıda tekrar import |
| L29 | `_gen_phrases.py` | 160-161 | `_quick_phrases.json` gitignore'da değil, yanlışlıkla commit edilebilir |

### Batch Files

| # | Dosya | Açıklama |
|---|-------|----------|
| L30 | `başlat.bat:14-24` | `exit /b 0` eksik, sonraki satırlar yanlışlıkla çalışabilir |
| L31 | `başlat.bat` (filename) | `ş` harfi legacy CMD'de/code page 437'de bozuk görünebilir |
| L32 | `başlat-exe.bat:14-17` | Unconditional success mesajı (exe çökse de "başlatıldı" yazar) |
| L33 | `transkribe.bat:2` | `.venv` tercihi yok (calistir.bat'ın aksine) |
| L34 | `main.js:114-118` | `venvCandidates` Unix path'leri (`bin/python`) Windows'ta extra FS check yapar |

### Electron & Build

| # | Dosya | Açıklama |
|---|-------|----------|
| L35 | `main.js:369-374` | `pythonProcess.pid` spawn sonrası senkron check, yüklü sistemde false negative |
| L36 | `preload.js:6` | `DEBUG === '*'` çok katı, diğer npm paketlerinin DEBUG değeri ile çakışır |
| L37 | `build.js:84` | `ignore: (file) => !isKept(file)` double negative, refactor'da tersinebilir |
| L38 | `build.js:59-73` | `scanForLeaks` sadece yasaklı dosyaları kontrol eder, eksik asset'leri yakalamaz |
| L39 | `launcher_whisper.py:18-21` | exe Popen sonrası `process.wait()` veya `poll()` yok, sessiz başarısızlık |

### Config / AI

| # | Dosya | Açıklama |
|---|-------|----------|
| L40 | `.env.example:1-10` | MiniMax legacy, `OPENAI_API_KEY` eksik — yeni geliştiriciyi yanıltır |
| L41 | `.gitignore:2` | Sadece `.env`; `*key*`, `*.key` gibi pattern'ler yok |
| L42 | `BAŞLAT.md:111-127` | Dosya ağacında `Whisper/` yazıyor, gerçek dizin `Whisper Live` |
| L43 | `SONNET_GOREVLERI.md:3` | `claude-sonnet-5` referansı, kullanılan model `claude-opus-4-6` |
| L44 | `CLAUDE.md` | Geçmiş güvenlik olayı belgelenmiş (dist/build'e key sızması) |
| L45 | `.claude/settings.local.json:16` | `python3` Windows'ta standart değil |
| L46 | `.claude/launch.json:8` | Port 5096, uygulama portu 5000 ile uyuşmuyor (debug portu olabilir, açıklanmamış) |
| L47 | `launcher_whisper.py:25-30` | `shell=True` ile "npm not found" hatası asla yakalanmaz |

---

## Tüm Bug'lar — Dosya Bazında Dizin

| Dosya | 🔴 | 🟠 | 🟡 | 🟢 | Toplam |
|-------|:--:|:--:|:--:|:--:|:------:|
| `buyedektir.py` | 3 | 8 | 13 | 15 | 39 |
| `templates/index.html` | 3 | 6 | 7 | 10 | 26 |
| `test_smoke.py` | 0 | 2 | 2 | 1 | 5 |
| `test_cevap_onerisi.py` | 0 | 0 | 0 | 1 | 1 |
| `build.js` | 1 | 0 | 0 | 2 | 3 |
| `main.js` | 0 | 0 | 0 | 1 | 1 |
| `preload.js` | 0 | 0 | 0 | 1 | 1 |
| `launcher_whisper.py` | 1 | 0 | 0 | 1 | 2 |
| `package.json` | 1 | 0 | 1 | 0 | 2 |
| `requirements.txt` | 0 | 1 | 2 | 1 | 4 |
| `başlat.bat` | 0 | 0 | 0 | 2 | 2 |
| `başlat-exe.bat` | 0 | 0 | 0 | 1 | 1 |
| `transkribe.bat` | 0 | 0 | 0 | 1 | 1 |
| `debug_output.html` | 3 | 1 | 0 | 1 | 5 |
| `debug_served.html` | 3 | 1 | 0 | 1 | 5 |
| `transkribe.py` | 0 | 1 | 0 | 1 | 2 |
| `_gen_phrases.py` | 0 | 0 | 1 | 1 | 2 |
| `.env.example` | 0 | 1 | 0 | 1 | 2 |
| `.gitignore` | 0 | 0 | 0 | 1 | 1 |
| `.claude/settings.local.json` | 0 | 0 | 1 | 1 | 2 |
| `.claude/launch.json` | 0 | 0 | 1 | 1 | 2 |
| `BAŞLAT.md` | 0 | 0 | 0 | 1 | 1 |
| `SONNET_GOREVLERI.md` | 0 | 0 | 0 | 1 | 1 |
| `CLAUDE.md` | 0 | 0 | 0 | 1 | 1 |
| `archive/main.py` | 1 | 0 | 2 | 0 | 3 |
| `archive/translator_gui.py` | 0 | 1 | 0 | 0 | 1 |
| `archive/run_whisper.py` | 0 | 0 | 0 | 1 | 1 |
| `archive/ai_studio_code.py` | 0 | 0 | 0 | 1 | 1 |
| `archive/__pycache__yedek/` | 0 | 0 | 1 | 0 | 1 |
| `archive/18797.jpg` | 0 | 0 | 1 | 0 | 1 |
| Infrastructure (cross-file) | 1 | 1 | 1 | 2 | 5 |
| pip environment | 0 | 2 | 1 | 1 | 4 |
| Zero-byte files (`npm`, `npm run`, `electron`, `whisper-pro@1.0.0`) | 0 | 0 | 1 | 0 | 1 |
| **TOPLAM** | **15** | **27** | **35** | **47** | **~124** |

---

## İlk 10 Acil Müdahale

| Öncelik | ID | Bug | Dosya | Etki |
|:-------:|:--:|-----|-------|------|
| 1 | B-DEP-001 | `webrtcvad` kurulu değil → startup crash | `requirements.txt` / `buyedektir.py:34` | App açılmaz |
| 2 | B-INF-001 | build whitelist bozuk → boş exe | `build.js:26-41` | `npm run build` çalışmaz |
| 3 | B-INF-002 | `static/` build'de yok → socket.io 404 | `dist/` | Packaged exe'de real-time özellikler ölü |
| 4 | B-INF-003 | electron-store v8 CommonJS uyumsuz | `package.json:15` | Ayarlar her restart'ta sıfırlanır |
| 5 | B-BE-004 | `_session_id` transcript emit'te kontrolsüz | `buyedektir.py:3108-3111` | Session cross-contamination |
| 6 | B-FR-001 | `renderAiResult` null guard yok | `index.html:4767-4768` | JS crash |
| 7 | B-BE-001 | `conversation_turns` deque data race | `buyedektir.py:3072,3599` | Segfault/corruption |
| 8 | B-BE-002 | `transcriptions` deque list+append race | `buyedektir.py:3108,3229` | Deque corruption |
| 9 | B-BE-007 | `MicRecorder.frames` lock'suz | `buyedektir.py:1727,1766` | Ses buffer corruption |
| 10 | B-BE-009 | Chunk-bazlı resampling tıkırtısı | `buyedektir.py:2716` | Duyulabilir audio artefakt |

---

*Rapor sonu. Kodda hiçbir değişiklik yapılmamıştır.*
