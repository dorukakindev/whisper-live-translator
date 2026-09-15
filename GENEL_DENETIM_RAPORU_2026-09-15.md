# WHISPER PRO — GENEL KOD DENETİMİ, BUG ve GELİŞTİRME RAPORU
**Tarih:** 15 Eylül 2026 (üçüncü derin tur ile genişletildi)
**Kapsam:** Tüm uygulama (`buyedektir.py`, `audio_diagnostics.py`, `templates/index.html`, `templates/overlay.html`, `static/*.js`, `main.js`, `main_helpers.js`, `preload.js`, `transkribe.py`, `build.js`, `launcher_whisper.py`, `başlat.bat`, `requirements.txt`, `.venv` kurulu paket sürümleri)
**Durum:** Kodda değişiklik yapılmadı — yalnızca denetim ve raporlama.
**Önceki raporlar:** `BUG_TARAMASI_TAM_RAPOR.md` (15 kritik + 27 yüksek + 35 orta) ve `DERIN_BUG_TARAMASI_RAPORU.md` (30 madde) bu rapora konsolide edildi; her madde güncel koda karşı tek tek doğrulandı.

---

## 1. YÖNETİCİ ÖZETİ

Önceki iki rapordaki **30 + 70+ bulgunun büyük çoğunluğu güncel kodda düzeltilmiş** durumda. İkinci derin turda ilk rapordaki **A-06 ve A-07'nin de aslında düzeltilmiş olduğu** doğrulandı (bkz. §2 düzeltmeleri) — ilk turdaki kanıt satırları yanıltıcıydı.

İkinci turda backend'in tamamı, Electron ana süreci, overlay, bağımsız betikler ve **kurulu `.venv` paket sürümleri** de incelendi; **10 yeni bulgu** çıktı (B-01..B-09), en önemlisi: **konuşmacı tanıma (diarization) bu ortamda tamamen ölü** — pyannote.audio 4.x API kırılması + torchcodec eksikliği.

Üçüncü turda kalan statik JS modülleri (`cockpit.js`, `live-flow.js`, `reading-mode.js`, `runtime-safety.js`, `html-utils.js`, `quick-phrases.js`), `audio_diagnostics.py`, Socket.IO bağlantı/auth sınırı, ayar-kalıcılık yarışları, `main.js`'in tamamı, mic executor yaşam döngüsü, `transkribe.py`, `build.js`, `launcher_whisper.py`, overlay hydration/socket yarışları ve çeviri worker'ının tamamı incelendi; **6 yeni bulgu** çıktı (C-01..C-06) — ikisi **canlı Flask test client ile doğrudan üretilerek kanıtlandı**.

**Hâlâ açık doğrulanmış bulgular — 20 adet:**

| ID | Önem | Özet | Kaynak |
|----|------|------|--------|
| B-01 | 🔴 | Konuşmacı tanıma pyannote 4.x'te sessizce ölü (`DiarizeOutput.itertracks` yok) | Yeni (derin tur) |
| A-01 | 🔴 | "Durdur" anında işlemdeki son konuşma hâlâ çöpe atılıyor | DERIN BUG-18 |
| A-02 | 🟠 | `isOwnedWhisperBackend` tam yol eşleşmesi (8.3 kısa yol + göreli yol varyantları) | DERIN BUG-29 |
| B-02 | 🟠 | `.venv`'de torchcodec bozuk → diarization dosya-yolu fallback'i de ölü | Yeni (derin tur) |
| A-03 | 🟠 | Backend çeviri + `autoTranslateEnabled` birlikte açıksa çift AI çevirisi | DERIN BUG-12 (kısmi) |
| A-04 | 🟠 | İlk GPU yüklemesinde OOM → sessiz CPU fallback | DERIN BUG-17 (kısmi) |
| B-03 | 🟡 | OpenAI çeviri sağlayıcısında anahtar yokken "aktif" mesajı + ana cevap anahtarına fallback yok | Yeni |
| B-04 | 🟡 | `configure_translation(provider, None)` o sağlayıcının kayıtlı anahtarını siliyor | Yeni |
| B-05 | 🟡 | Alt-PTT sonucu generation-uyuşmazlığında sessizce düşüyor → UI "işleniyor"da takılı | Yeni |
| B-06 | 🟡 | `context_buffer` oturumlar arası temizlenmiyor + mic-dikte (TR) Whisper prompt'unu kirletiyor | Yeni |
| A-05 | 🟡 | Ctrl-PTT `setPtt`'de `keepalive` eksik | DERIN BUG-06 (yarım) |
| B-07 | � | `generate_ai_response` `transcript_id` int değilse bağlam kaydı kendini de içeriyor | Yeni |
| B-08 | 🔵 | `target_lang` doğrulanmıyor (`None`/dize-dışı → prompt'ta "None") | Yeni |
| B-09 | � | Küçük sağlamlık boşlukları demeti (bool-coercion, PyAudio leak, durum tutarsızlığı, mojibake, ölü DEFAULTS anahtarları) | Yeni |
| C-01 | 🟠 | `deepl_config` başarısız anahtar testi runtime provider+anahtarı bozuyor (canlı üretildi) | 3. tur |
| C-02 | 🟠 | Socket.IO bağlantısında token yok — canlı transkript akışı tokensuz okunabilir (canlı üretildi) | 3. tur |
| C-03 | 🟡 | `capture_mode='mic'` Türkçe dikteyi seçili `whisper_language` ile çözümlüyor | 3. tur |
| C-04 | 🟡 | Ctrl-PTT ve Global-PTT'de istek sıralaması yok → `ptt_active` takılabilir | 3. tur |
| C-05 | 🔵 | Backend restart'ta `_transcriptRevisions` temizlenmiyor → eski id'li düzeltmeler düşebilir | 3. tur |
| C-06 | 🔵 | `transkribe.py` `torch.cuda.is_available()` kullanıyor — ana uygulamadaki düzeltme burada yok | 3. tur |

Ayrıca **tasarım gereği 1 bilinen sınırlama** (telaffuz sözlüğü tam-eşleşme) ve **16 geliştirme önerisi** (§4) var.

---

## 2. HALEN AÇIK BUGLAR (kanıtlı)

### [B-01] Konuşmacı tanıma pyannote.audio 4.x'te sessizce ölü 🔴
* **Konum:** `buyedektir.py:2199` (`diarization.itertracks(yield_label=True)`), `buyedektir.py:2059` (`Pipeline.from_pretrained("pyannote/speaker-diarization-3.1")`), `requirements.txt` (`pyannote.audio>=2.1.1` — üst sınır yok).
* **Kanıt (bu ortamda doğrulandı):** `.venv`'de **pyannote.audio 4.0.4** kurulu. `SpeakerDiarization.__init__`'in `legacy` parametresi varsayılan `False`; `apply()` bu durumda `Annotation` değil `DiarizeOutput` döndürür ve `DiarizeOutput`'ta `itertracks` metodu **yok** (`hasattr` kontrolü: `False`; yalnız `serialize`, `speaker_embeddings` üyeleri).
* **Mekanizma:** `diarization.itertracks(...)` → `AttributeError` → `identify_speaker`'ın genel `except`'i (2229) yutuyor, `_record_health_error('diarization_failed')` yazıp `(None, None)` dönüyor. Sonuç: diarization açıkken bile `speaker_identified` olayı **hiç yayınlanmaz**; `_diarize_busy_skips` artmaz çünkü iş "başarıyla" yürüyüp None döner.
* **Etki:** Kullanıcı "Konuşmacı tanıma"yı açar, HF token girer, her şey normal görünür — ama hiçbir transkript hiçbir zaman konuşmacı etiketi almaz. Hata yalnız log'da `diarization_failed` olarak kalır; UI'da uyarı yok.
* **Öneri:** Sonucu normalize et: `ann = getattr(diarization, 'speaker_diarization', diarization)` sonra `ann.itertracks(yield_label=True)` — hem 2.x/3.x (`Annotation`) hem 4.x (`DiarizeOutput`) çalışır. Alternatif: pipeline'ı `legacy=True` ile kur. Ayrıca `requirements.txt`'e üst sınır/uyum sürümü eklenmeli.

### [B-02] `.venv`'de torchcodec bozuk → diarization dosya fallback'i de ölü 🟠
* **Konum:** `buyedektir.py:2189-2190` (`torchaudio.save(tmp_path,...)` + `self.pipeline(tmp_path)`).
* **Kanıt:** `.venv`'de `torch 2.10.0+cu130` kurulu; pyannote import'u "torchcodec is not installed correctly ... Could not load libtorchcodec ... libtorchcodec_core8.dll" uyarısı veriyor. pyannote 4.x dosya yolu/URI çözümlemesini torchcodec üzerinden yapar.
* **Mekanizma:** Bellekteki `{"waveform": tensor}` yolu torchcodec GEREKTİRMEZ (uyarı metni de bunu söylüyor) → birincil yol çalışır. Fakat eski pyannote sürümleri tensor girdiyi kabul etmezse devreye giren dosya fallback'i bu ortamda decode aşamasında patlar → `except` (2229) → `(None, None)`.
* **Etki:** B-01 düzeltilse bile, tensor-girdisi reddedilen bir sürüm/path kombinasyonunda fallback yine sessizce ölür. Ayrıca pyannote import'u her açılışta bu uzun traceback'i log'a basar (gürültü).
* **Öneri:** `torchcodec`'i torch sürümüyle uyumlu kur (FFmpeg full-shared gerekir) veya fallback yolunu `torchaudio.load`→tensor yerine doğrudan `soundfile`/decode bağımsız yolla besle; en azından fallback'in çalışmadığını bir kere `logger.warning` ile belirt.

### [A-01] Durdur anında işlemdeki son konuşma hâlâ kayboluyor 🔴
* **Konum:** `buyedektir.py:3501-3512` (`stop_capture`: `is_running=False` + `_result_generation += 1`), `buyedektir.py:3534` (`_drain_audio_queue`), `buyedektir.py:4101-4105` ve `4132-4144` (commit kontrolü).
* **Mekanizma:** Stop, generation'ı artırıp kuyruğu boşaltır. Whisper'dan yeni dönmüş bir sonuç veya kuyrukta bekleyen tam bir segment, `result_generation != self._result_generation or not self.is_running → continue` ile düşürülür — ne ekrana basılır ne dosyaya yazılır. Frontend `stopCapture()` önce `/api/flush` çağırmaz.
* **Etki:** "Durdur"dan hemen önce söylenen son cümle (kuyrukta ~15 sn'ye kadar ses) sessizce kaybolur.
* **Öneri:** `/api/stop`'a `drain=true` kipi: generation'ı artırmadan önce kuyruktaki işlenmiş/ işlenen sonucu commit'e izin verecek şekilde `is_running` kontrolünü commit yolundan ayır (oturum/generation değişimi tek geçersizleştirici kalsın); ya da frontend `stopCapture()` önce `/api/flush` çağırıp kısa beklesin.

### [A-02] `isOwnedWhisperBackend` yol eşleşmesi — 8.3 + göreli-yol varyantları 🟠
* **Konum:** `main_helpers.js:9-14`.
* **Mekanizma:** `normalized.includes(expectedScript)` — `path.resolve(appDir,'buyedektir.py')`'nin uzun biçimi komut satırında birebir aranır. İki gerçekçi kaçış: (a) WMI `CommandLine` 8.3 kısa biçim döndürür (`d:\whispe~1\buyedektir.py`); (b) backend göreli yolla başlatılmışsa (`python buyedektir.py` — manuel başlatma veya başka bir başlatıcı), komut satırı tam yolu içermez.
* **Etki:** Port 5000'i tutan süreç "sahipsiz/yabancı" sayılır → `safeToStart=false` → "Port Kullanımda" diyaloğu veya 60 sn hazırlık-timeout'u → uygulama açılmıyor. (b) tasarım gereği "yabancı sürece dokunma" politikasının da parçası ama kullanıcıya "kendi projenin backend'i" olarak görünür; UX hâlâ kırılgan.
* **Öneri:** Eşleşmeyi `buyedektir.py` dosya adı + `--whisper-electron-child` işaretine indirge; ek güvence için `backend_nonce` yoksa `--whisper-electron-child` + script dosya adını birlikte şart koş (şu an ikisi de zaten aranıyor, yalnız tam-yol `includes` kırılgan). `fs.realpathSync`/`GetShortPathName` ile iki tarafı da normalize etmek alternatif.

### [A-03] Çift çeviri hâlâ mümkün 🟠
* **Konum:** `templates/index.html:4307-4314` + `buyedektir.py:4234-4250`.
* **Durum:** İlk turdaki gibi açık — iki bağımsız anahtar (backend `translation_settings.enabled` + localStorage `autoTranslateEnabled`) birlikte açıkken aynı transkripte iki ayrı çeviri gider.
* **Öneri:** Birini açarken diğerini otomatik kapat veya UI'da çakışma uyarısı göster.

### [A-04] İlk GPU yüklemesinde OOM → sessiz CPU fallback 🟠
* **Konum:** `buyedektir.py:3188-3195`.
* **Durum:** `current_model is None` iken GPU hatası `use_gpu=False` → CPU int8'e düşer; yanıt `device:'CPU'` döndürür ama GPU denemesinin neden başarısız olduğu bildirilmez. UI `device` alanını gösteriyorsa kısmen ayırt edilebilir.
* **Öneri:** Yanıta `gpu_fallback:true` + `gpu_error` eklenip UI'da uyarı gösterilsin.

### [B-03] OpenAI çeviri sağlayıcısında anahtarsız "aktif" + paylaşımlı anahtar fallback'i yok 🟡
* **Konum:** `templates/index.html:3154-3160` (`toggleTranslation`), `buyedektir.py:1563` (`snapshot_translation_request` yalnız `translation_api_keys` okur), `buyedektir.py:4712` (`using_shared_key` sabit `false`).
* **Mekanizma:** `deepl` için anahtar yoksa uyarı var; `openai_reseller`/`openai_official` için **anahtar kontrolü yapılmadan** "OpenAI çeviri aktif" gösteriliyor. Ayrıca çeviri çağrıları yalnız `translation_api_keys[provider]`'a bakar — kullanıcının ana cevap (`OpenAIResponder.api_key`) anahtarı çeviri için asla kullanılmaz. CLAUDE.md'deki "paylaşılan cevap anahtarına düşebilir" ifadesi güncel kodla örtüşmüyor.
* **Etki:** Ana OpenAI anahtarını girmiş ama çeviri-özel anahtar girmemiş kullanıcı "Çeviri aktif" görür; her transkriptte çeviri `None` → `translation_status: 'failed'`. Sessiz, yanıltıcı hata durumu.
* **Öneri:** Toggle'da openai sağlayıcıları için de anahtar kontrolü; veya `snapshot_translation_request` anahtar yoksa `self.api_key`'e düşsün (tek anahtarla her şeyi çalıştırmak beklenen UX).

### [B-04] `configure_translation(provider, None)` kayıtlı çeviri anahtarını siliyor 🟡
* **Konum:** `buyedektir.py:1525-1544` (`translation_api_keys[provider] = normalized_key` her zaman yazar), çağıranlar `4691`, `4741`.
* **Mekanizma:** `api_key` parametresi verilmediğinde/boş geldiğinde `normalized_key=None` → sağlayıcının kayıtlı anahtarı üzerine `None` yazılır. Frontend normalde `apiKey`'i localStorage'dan her istekte gönderdiği için çoğunlukla maskelenir; fakat alanı boş bırakılmış eski bir sekme, temizlenmiş localStorage veya `apiKey` içermeyen bir POST, backend'deki anahtarı sessizce siler.
* **Etki:** Çeviri bir sonraki istekte anahtarsız kalır; kullanıcı nedenini anlamaz (ayar değiştirmediğini sanır).
* **Öneri:** `api_key is None` ise `translation_api_keys[provider]`'a dokunma ("gönderilmedi = değiştirme"); açık silme için ayrı `clear_key` bayrağı.

### [B-05] Alt-PTT sonucu generation-uyuşmazlığında sessizce düşüyor → UI "işleniyor"da takılı �
* **Konum:** `buyedektir.py:4949-4951`, `5082-5084`, `5098-5100` (`return` — `ptt_mic_result` yayınlanmaz); frontend `index.html:5158-5161` (`'⏳ Sesiniz işleniyor ve çevriliyor...'`), `cockpit.js:129` (`'Ses işleniyor'`). İstemci tarafında `ptt_mic_result` için timeout/watchdog yok.
* **Mekanizma:** Mikrofon çözümlemesi sürerken kullanıcı Durdur/Temizle'ye basarsa `_result_generation` artar → üç dönüş yolu da **emit'siz** return eder. Frontend `ptt_mic_result`'i sonsuza dek bekler.
* **Etki:** "⏳ Sesiniz işleniyor…" uyarısı ve `ownReplyStatus` takılı kalır; kayıt sessizce kaybolur. Kenar durum ama gerçek kullanıcı akışı (PTT sonrası hızlı Temizle).
* **Öneri:** Stale-generation return yollarında `socketio.emit('ptt_mic_result', {recording_id, success:false, error:'Oturum sıfırlandı; kayıt işlenemedi'})` yayınla — frontend `renderPttTranscription` zaten hata durumunu gösteriyor. Alternatif/ek: frontend'e ~45 sn watchdog.

### [B-06] `context_buffer` oturumlar arası temizlenmiyor + mic-dikte (TR) Whisper prompt'unu kirletiyor 🟡
* **Konum:** `buyedektir.py:4148` (commit'te koşulsuz `context_buffer.append(full_text)`), `3463-3490` (`start_capture` — buffer temizlenmiyor), `5295-5297` (düzeltmede `source != 'ptt'` süzgeci — `'mic'` süzülmüyor), `2808-2853` (`get_context_prompt` kaynak süzgeci yok).
* **Mekanizma:** `context_buffer` Whisper `initial_prompt`'u besliyor ve kodun kendi yorumu bunu açıkça söylüyor: "context_buffer'a Türkçe metin karışırsa karşı tarafın dilini kilitleme amacını bozar" (2510-2513). Fakat `capture_mode='mic'` oturumundaki Türkçe dikteler commit yolunda buffer'a girer; `start_capture` da buffer'ı temizlemez → sonraki 'system' oturumunda Japonca/Arapça dinlerken initial_prompt'a Türkçe metin karışır.
* **Etki:** Dil-kilidi zayıflar; dinlenen dilde yanlış dilde transkripsiyon/algılama sapması olasılığı artar. Düzeltme yolu da 'mic' kayıtlarını buffer'a geri koyar.
* **Öneri:** `get_context_prompt`'ta yalnız `source` bilinmeyen/`system` metinlerini kullan (kaynak bilgisi buffer'da yok → append anında rolu sakla veya mic-modunda append'i atla); veya `start_capture`'da `capture_mode` değişiminde buffer'ı temizle.

### [A-05] Ctrl-PTT `setPtt`'de `keepalive` eksik 🟡
* **Konum:** `templates/index.html:5037-5043` vs `5105`.
* **Durum:** Alt-PTT'ye `keepalive: true` eklendi; sistem-sesi Ctrl-PTT'sine eklenmedi. `beforeunload`'daki `setPtt(false)` iptal edilebilir → `ptt_active` `MAX_PTT_S` kadar açık kalır.
* **Öneri:** Tek satır: `keepalive: true`.

### [B-07] `transcript_id` int değilse çeviri bağlamı kaydın kendisini içeriyor 🔵
* **Konum:** `buyedektir.py:5554-5557`.
* **Mekanizma:** `transcript_id` int değilse `context_id = _next_transcription_id + 1` atanır → `get_translation_context` `id < before_id` süzdüğü için cevaplanan kaydın kendisi de "önceki bağlam"a girer. Frontend şu an int gönderiyor; dize id'li istemcilerde (veya gelecekteki değişiklikte) mesaj metni BAĞLAM'da bir kez daha geçer.
* **Öneri:** `int()` dönüşümü dene (`str.isdigit`); olmazsa `None` → bağlamı atla veya son kaydı hariç tut.

### [B-08] `target_lang` doğrulanmıyor �
* **Konum:** `buyedektir.py:5483` (`data.get('target_lang','ja')`).
* **Mekanizma:** `None`/sayı/dize-dışı değerler doğrudan prompt'a ve `_build_pronunciation_guide`'a gider; `lang_names.get(None, None)` → `target_lang_name=None` → prompt'ta "None" basılır. Benzer şekilde `mode`/`tone`/`response_length` dışında doğrulama yok.
* **Öneri:** `isinstance(target_lang, str)` ve `allowed` kümesi kontrolü (whisper_language route'undaki desen).

### [B-09] Küçük sağlamlık boşlukları demeti 🔵
* **`/api/ai_response_toggle` (5412):** `data.get('enabled', False)` bool-coerce edilmiyor — `"false"` dizesi truthy → `enabled=True`. (`/api/partial_toggle` `bool(...)` sarıyor — tutarsız.)
* **`get_audio_devices` (3305-3377):** `p.terminate()` `finally`'de değil — numaralandırma ortasında fırlayan istisna PyAudio host'unu sızdırır (her `/api/devices` çağrısı bir host nesnesi açar).
* **`_verify_openai_key` (2620-2625):** Doğrulama başarısız olursa `enabled=False` yapılır ama `api_key` korunur → `/api/status` `ai_available: bool(api_key)` → UI "AI var" gösterirken çağrılar disabled. Durum göstergesi `enabled && api_key` birleşimi olmalı.
* **`__main__` başlangıç bannerı (6139-6143):** Bozulmuş emoji baytları (`"ğŸâ€â€ž"` vb.) — kaynak dosya bir noktada yanlış kodlamayla yazılmış; yalnız kozmetik (log/konsol çirkinliği).
* **`__init__` (2661-2662):** `self.adaptive_silence = True` ve `self.translation_context = True` `DEFAULTS[...]` yerine sabit — `DEFAULTS`'taki aynı isimli anahtarlar fiilen ölü konfigürasyon (davranış aynı; tutarlılık notu).

### [C-01] `deepl_config` başarısız anahtar testi runtime provider+anahtarı bozuyor 🟠
* **Konum:** `buyedektir.py:4687-4706`; çağıran `templates/index.html:3010-3036` (`saveDeepLKey`).
* **Mekanizma:** Route `translator._config_lock` altında `translator.provider = provider` (**koşulsuz**, 4688) ve `api_key` verildiyse `translator.api_key = <yeni anahtar>` (**testten önce**, 4701) yazar. DeepL testi kilit DIŞINDA çalışır (4719) ve başarısız olursa route `success:false` döner — ama mutasyon çoktan commit edilmiştir.
* **Canlı kanıt (Flask test client, bu oturumda üretildi):** önce `provider='openai_reseller', enabled=True` iken `POST /api/deepl_config {api_key:'geçersiz', provider:'deepl'}` → yanıt `{'success': False, 'error': 'API key gerekli veya geçersiz'}`; sonrasında `translator.provider='deepl'`, `translator.api_key='geçersiz'`, `enabled=True` — yani geçersiz anahtarla çeviri açık kaldı.
* **Etki:** Kullanıcı yanlış bir DeepL anahtarı deneyip "geçersiz" uyarısı alır; ama eski sağlayıcı (ör. çalışan openai_reseller) yerinden edilmiş ve canlı çeviri artık geçersiz anahtarla denenir → sonraki her transkriptte `translation_status: 'failed'`. Frontend hata dalında eski ayarı geri basmaz (yalnız uyarı gösterir). Provider-değiştirme denemesi de aynı şekilde eski çalışan sağlayıcıyı siler.
* **Öneri:** Route testi yalnız verilen anahtarla yapmalı (zaten öyle: `test_api(str(api_key))`); test BAŞARILIYSA provider+anahtar commit edilmeli, değilse runtime'a dokunulmamalı. Ya da mutasyonu testten SONRA yap: önce `test_api(candidate)`, sonra kilit altında yaz.

### [C-02] Socket.IO bağlantısında token doğrulaması yok 🟠
* **Konum:** `buyedektir.py:119-128` (`require_local_app_token` yalnız `/api/` prefix'i) + `143` (`SocketIO(...)` — connect handler/auth yok; backend'de hiç `@socketio.on` handler yok, socket yalnız sunucu→istemci emit).
* **Mekanizma:** Socket.IO handshake `/socket.io/` yolundan gider → `before_request` token kontrolünün dışında kalır. `cors_allowed_origins` yalnız Origin başlığını denetler: tarayıcı sayfaları engellenir ama **tarayıcı-olmayan yerel süreçler** Origin'i istedikleri gibi gönderir/atlar.
* **Canlı kanıt (bu oturumda üretildi):** `socketio.test_client(app)` token'sız → `is_connected() == True`.
* **Etki:** `/api/transcriptions` token isterken (doğru olarak) aynı verinin canlı akışı (`new_transcription`, `transcription_translation`, `ptt_mic_result` — özel konuşma içeriği) tokensuz okunabilir. Makinedeki herhangi bir süreç kullanıcının konuşmasını sessizce dinleyebilir. Tehdit modeli yerel olduğundan orta-düşük; ama token varken socket'i açık bırakmak tutarsız bir sınır.
* **Öneri:** `@socketio.on('connect')`'e auth ekle: istemci `io({auth:{token: APP_TOKEN}})` göndersin; bilinmeyen token'a `return False`. Sayfalara token zaten `{{ app_token|tojson }}` ile gömülü.

### [C-03] `capture_mode='mic'` seçili `whisper_language`'ı zorluyor — Türkçe dikte yabancı dilde çözümlenebilir 🟡
* **Konum:** `buyedektir.py:3457-3460` (`self.whisper_language` koşulsuz istekten), `4054/4083` (`language=whisper_lang` mic modunda da); frontend `index.html:3805/3819` (her zaman radio değerini gönderir).
* **Mekanizma:** Mic dikte modu Türkçe konuşma içindir (rol 'me', çeviri/AI yok). Fakat `start_capture` `capture_mode=='mic'` iken `whisper_language`'ı override ETMEZ: kullanıcı karşı taraf için 'ja' seçtiyse Türkçe dikte `language='ja'` ile çözümlenir → Whisper Türkçe sesi Japonca zorlar → anlamsız çıktı, kullanıcıya açıklama yok.
* **Etki:** Mod değiştiren kullanıcı neden saçma transkript aldığını anlamaz. (Alt-PTT `process_mic_audio` 4969'da `language='tr'` zorlar — mikrofon dikte moduyla tutarsız.)
* **Öneri:** `capture_mode=='mic'` iken `language='tr'` (veya `None`/auto) kullan — Alt-PTT ile aynı davranış. UI'da "mic modu Türkçe çalışır" ipucu zaten var (3417).

### [C-04] Ctrl-PTT ve Global-PTT'de istek sıralaması yok → `ptt_active` takılabilir 🟡
* **Konum:** `templates/index.html:5037-5043` (`setPtt` — bağımsız fetch, sıralama/keepalive yok) vs `5095` (`altPttCommandChain` — Alt-PTT serileşmiş); `main.js:438-484` (`sendPttRequest` — `globalPttRequestSerial` yalnız hata gösterimini korur, istek sırasını değil).
* **Mekanizma:** Hızlı bas-bırakta `POST {active:true}` ve `POST {active:false}` ağda sıralanabilir → backend son yazanı uygular. Backend `/api/ptt` (4815-4820) kilidi doğru ama "son gelen kazanır" semantiği taşıyor — gecikmiş `true` isteği `false`'tan sonra varırsa `ptt_active` açık kalır (`MAX_PTT_S`=120 sn'ye dek). Aynı sınıf: global PTT toggle (main.js) — `active:false` yanıtı timeout'a uğrasa bile backend komutu uygulamış olabilir; `fail()` yerel bayrağı `false`'a çeker ama backend'e telafi isteği göndermez.
* **Etki:** A-05 ile aynı semptom sınıfı (takılı PTT) ama farklı kök: istek sıralaması. Alt-PTT bu sorunu komut zinciriyle çözmüş; Ctrl-PTT ve global-PTT'de çözüm yok.
* **Öneri:** `setPtt`'i `altPttCommandChain` deseniyle serileştir (veya tek sequence numarası gönderip backend'de eski sequence'i reddet); `sendPttRequest` timeout'unda telafi `active:false` gönder.

### [C-05] Backend restart'ta `_transcriptRevisions` temizlenmiyor — geri dönüştürülmüş id'de düzeltme düşebilir 🔵
* **Konum:** `templates/index.html:3619-3629` (`backendRestarted` dalı `transcriptionTexts`/`seenTranscriptionIds`/`prunedTranscriptionId`'ı temizler ama `window._transcriptRevisions`'ı değil); `static/live-flow.js:44` (`revisions[id] = max(eski, yeni)`), `90-95` (`revision <= revisions[id]` → düşür).
* **Mekanizma:** Backend yeniden başlayınca `_next_transcription_id` 0'dan başlar → yeni kayıtlar eski id'leri geri kullanır. `decorateTranscript` eski (yüksek) revision'ı `max()` ile korur; sonra gelen `transcription_corrected` (revision=1) `applyTranscriptCorrection`'da `1 <= eskiRev` → **sessizce düşürülür**. Lazy temizleme (live-flow.js:182-184) yalnız `transcriptionTexts`'te olmayan id'leri siler — yeni kayıt eklendikten sonra o id map'te olduğundan eski revision hayatta kalır.
* **Etki:** Dar kenar: backend restart + aynı id'nin yeniden kullanımı + o kaydın düzeltilmesi → kullanıcının düzeltmesi ekranda görünmez (409 değil, sessiz düşüş; backend kaydı kabul eder, socket olayı düşer).
* **Öneri:** `backendRestarted` dalında `window._transcriptRevisions = {}` (ve overlay'deki karşılığı `lastTranscriptRevision` zaten `clearTranscript` ile sıfırlanıyor).

### [C-06] `transkribe.py` `torch.cuda.is_available()` kullanıyor — ana uygulamadaki düzeltme burada yok 🔵
* **Konum:** `transkribe.py` `detect_device` (`torch.cuda.is_available()` tabanlı) vs ana uygulamanın gerçek-tensor testi (CLAUDE.md: cuBLAS DLL adı değişince sessiz CPU düşüşü yaşanmıştı → gerçek `torch.zeros(1, device='cuda')` tahsisine geçildi).
* **Mekanizma:** `is_available()` True döndürebilir ama `WhisperModel(device='cuda')` yüklemesi (transkribe.py:408) sürücü/cuBLAS uyumsuzluğunda patlar → iş hata ile biter, CPU fallback YOK (ana uygulamada var). Kullanıcı CPU'yu elle seçene kadar transkribe çalışmaz.
* **Öneri:** `detect_device`'ı ana uygulamayla aynı gerçek-tensor testine al veya model yükleme hatasında `device='cpu'` ile tek otomatik deneme yap.

### Not — ilk tur düzeltmeleri
* **A-06 gerçekte DÜZELTİLMİŞ:** `process_mic_audio`'daki `conversation_turns.append` `with transcriber._lifecycle_lock:` bloğunun içinde (`buyedektir.py:5097-5120`). İlk turdaki "kilit dışında" bulgusu iptal edildi → DERIN BUG-24 ve B-BE-001/016 artık ✅.
* **A-07 gerçekte DÜZELTİLMİŞ:** CSP `<meta>` yok ama daha güçlüsü var — `set_browser_security_headers` (`buyedektir.py:104-116`) her yanıta `Content-Security-Policy` başlığı ekliyor (`default-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`). → TAM B-CFG-001 ✅.

---

## 3. BİLİNEN SINIRLAMA (tasarım kararı)

### [L-01] Telaffuz sözlüğü yalnız tam-eşleşmede uygulanır
* **Konum:** `buyedektir.py:741-756`.
* **Durum:** CLAUDE.md'de bilinçli tasarım olarak belgelenmiş; öneri G-05'e taşındı.

---

## 4. GELİŞTİRME ÖNERİLERİ (bug değil, fırsat)

| ID | Öneri | Gerekçe |
|----|-------|---------|
| G-01 | **"Durdur" öncesi otomatik flush** — `stopCapture()` `/api/flush` çağırsın | A-01'i kullanıcı tarafında kapatır |
| G-02 | **`/api/stop`'a `drain` kipi** | Tek istekle "durdurmadan önce kuyruğu bitir" semantiği |
| G-03 | **8.3/göreli yol normalize etme** | A-02'yi kökten çözer |
| G-04 | **GPU fallback uyarısı** — `gpu_fallback` bayrağı + UI banner | A-04'ü görünür kılar |
| G-05 | **Telaffuz sözlüğü kelime-sınırı ikamesi** (aynı alfabe ailesinde) | L-01'i genişletir |
| G-06 | **`autoTranslateEnabled` + backend çeviri kilidi** | A-03 maliyetini önler |
| G-07 | **Diarization sonuç normalizasyonu + uyum testi** — `speaker_diarization` attr kontrolü, pyannote sürüm pini | B-01 kalıcı çözümü |
| G-08 | **Frontend unit-test altyapısı** — `live-flow.js`/`runtime-safety.js`/`html-utils.js` saf mantık Node'da test edilebilir | Regresyon koruması |
| G-09 | **`setPtt`'ye `keepalive` + `navigator.sendBeacon`** | A-05 tutarlılığı |
| G-10 | **PTT işlem watchdog'u** — `ptt_mic_result` için ~45 sn istemci zaman aşımı | B-05'in frontend ayağı |
| G-11 | **Ana OpenAI anahtarı çeviri fallback'i** — `snapshot_translation_request` boşken `api_key`'e düşsün | B-03: tek anahtarla çalışan kurulum |
| G-12 | **`context_buffer`'a rol/kaynak etiketi** — append anında kaynak saklanıp prompt'ta mic/ptt elensin | B-06'nın temiz çözümü |
| G-13 | **`answer_question` toplam-süre üst sınırı** — çeviri yolunda retry zinciri ~3 dk sürebilir; ortak bir `deadline` parametresi | translate_executor tıkanmasını sınırlar |
| G-14 | **Diarization/çeviri başarısızlığını UI'a taşı** — `speaker_identified` hiç gelmiyorsa veya `diarization_failed` sağlık kodu varsa durum çubuğunda uyarı | B-01/B-02 gibi sessiz ölüm vakalarını görünür kılar |
| G-15 | **Socket auth** — `io({auth:{token}})` + `connect` handler | C-02'yi kapatır; frontend'e tek satır |
| G-16 | **PTT istek kimliği/sequence'i** — backend'de eski sequence'i reddet | C-04'ün kök çözümü (sıralama bağımsız) |

---

## 5. ÖNCEKİ RAPORLAR — DOĞRULANAN DURUM

### 5.1 `DERIN_BUG_TARAMASI_RAPORU.md` (30 madde) — güncel durum

| # | Başlık | Durum | Kanıt |
|---|--------|-------|-------|
| BUG-01 | Alt-PTT hedef dil tersliği | ✅ Düzeltildi | `index.html:5099` `aiTargetLang` + `keepalive` |
| BUG-02 | `<3` karakter halüsinasyon | ✅ Düzeltildi | uzunluk eşiği yok; yalnız gürültü kalıpları |
| BUG-03 | Answer `<4` karakter reddi | ✅ Düzeltildi | kontrol yok |
| BUG-04 | `remove_overlap` alt-dize | ✅ Düzeltildi | `transkribe.py:60-97` n-gram |
| BUG-05 | launcher `npm` | ✅ Düzeltildi | `shutil.which('npm.cmd')` |
| BUG-06 | `beforeunload` mic kapatma | ✅ Alt / ⚠️ Ctrl | `setPtt`'de `keepalive` yok → A-05 |
| BUG-07 | DeepL Pro anahtarı | ✅ Düzeltildi | `endpoint_for_key` `:fx` |
| BUG-08 | `set_response_model` alias | ✅ Düzeltildi | `_legacy_aliases` |
| BUG-09 | PTT `data-transcription-id` | ✅ Düzeltildi | `index.html:4068` |
| BUG-10 | `totalCount` çifte sayım | ✅ Düzeltildi | `!restoring` |
| BUG-11 | Çeviri `:` kırpması | ✅ Düzeltildi | bilinen ön-ek süzgeci |
| BUG-12 | Çifte OpenAI çevirisi | ⚠️ Kısmen | iki anahtar birlikte açılabiliyor → A-03 |
| BUG-13 | `stop_stream` PortAudio yarışı | ✅ Düzeltildi | `_stream_lock` |
| BUG-14 | Kanji→zh yanlış dil | ✅ Düzeltildi | Kana kontrolü + `zh_han` |
| BUG-15 | transkribe Tkinter thread | ✅ Düzeltildi | `_ui_events` kuyruğu |
| BUG-16 | `reset()` HF token silmesi | ✅ Düzeltildi | `save_profiles()` ile korunur |
| BUG-17 | VRAM iki model + CPU düşüşü | ⚠️ Kısmen | ilk yüklemede sessiz → A-04 |
| BUG-18 | Durdur'da son konuşma | ❌ Açık | → A-01 |
| BUG-19 | Yunanca/Kiril | ✅ Düzeltildi | `el` + `detected_lang` |
| BUG-20 | `update_speaker_name` kayıtlar | ✅ Düzeltildi | geçmiş güncelleme + `speaker_updated` |
| BUG-21 | `saveHFToken` boş token | ✅ Düzeltildi | `removeItem` + backend bildirimi |
| BUG-22 | `revokeObjectURL` senkron | ✅ Düzeltildi | `setTimeout` |
| BUG-23 | `seenTranscriptionIds` | ✅ Düzeltildi | prune'da siliniyor |
| BUG-24 | `conversation_turns` kilitsiz | ✅ Düzeltildi | mic append'i de `_lifecycle_lock` içinde (5097-5120) — ilk tur notu düzeltildi |
| BUG-25 | `_resample_filter` firwin | ✅ Düzeltildi | eşit oran erken dönüş |
| BUG-26 | Alt+Tab hayalet kayıt | ✅ Düzeltildi | 150ms timer + `e.altKey` |
| BUG-27 | `get_context_prompt` kesme | ✅ Düzeltildi | boşluk sınırı |
| BUG-28 | `<0.5s` VAD silinmesi | ✅ Düzeltildi | `> 0.2` eşiği |
| BUG-29 | 8.3 `isOwnedWhisperBackend` | ❌ Açık | → A-02 (göreli-yol varyantı da eklendi) |
| BUG-30 | Telaffuz tam-eşleşme | ℹ️ Tasarım | → L-01 |

### 5.2 `BUG_TARAMASI_TAM_RAPOR.md` — kritik/yüksek maddelerin durumu

| # | Durum | Not |
|---|-------|-----|
| B-FR-001..011 | ✅ | null guard, socket kurulumu, catch'ler, retry iptali, `\r\n` export — doğrulandı |
| B-BE-001..016 | ✅ | tüm kilit desenleri + mic append'in de kilit içinde olduğu doğrulandı |
| B-INF-001..005 | ✅ | allowlist, electron-store fallback, liste argümanı, header-token |
| B-TST-001..003 | ✅ | `test_smoke.py` geçiyor |
| B-DBG-001..005 | ✅ | HTML'de anahtar yok; kaçışlar tam |
| B-CFG-001 CSP | ✅ Düzeltildi | `after_request` CSP başlığı mevcut (`buyedektir.py:104-116`) — ilk tur notu düzeltildi |
| B-CFG-002/003 | ✅ | sanitize edilmiş hata yolları |
| B-DEP-001..003 | ⚠️ | webrtcvad/torch OK; **pyannote 4.0.4 API kırılması → B-01**; torchcodec bozuk → B-02 |

---

## 6. DOĞRULAMA (bu oturumlarda çalıştırılanlar)

| Komut | Sonuç |
|-------|-------|
| `python -m py_compile buyedektir.py` | ✅ |
| `python -m pyflakes buyedektir.py` | ✅ hata yok |
| `python test_smoke.py` | ✅ `TUM TESTLER GECTI` (telaffuz tabloları, halüsinasyon filtresi, cevap paralel+partial+dedup, JSON salvage, pause/flush, mic worker, clear-generation, backlog, model kilitleri, AI rate limit, chat, transkribe yardımcıları + tests/archive süitleri) |
| `node --check` — tüm `static/*.js`, `main.js`, `main_helpers.js`, `preload.js`, `build.js` | ✅ |
| `node --check` — inline scriptler | ⚠️ Jinja placeholder literal ile değiştirilerek kontrol edildi → geçti (yöntem sınırlaması, hata değil) |
| `require('./main_helpers')` + `main.js` CommonJS yükleme | ✅ |
| pyannote.audio kurulu sürüm | **4.0.4** — `SpeakerDiarization.apply` → `DiarizeOutput` (itertracks yok); `legacy=False` varsayılan → **B-01 kanıtı** |
| torchcodec | `.venv`'de bozuk (`libtorchcodec_core8.dll` yüklenemiyor, torch 2.10.0+cu130) → **B-02 kanıtı** |
| `git status` | Kod değişikliği yok; rapor/devir belgeleri untracked |
| **3. tur:** `POST /api/deepl_config` geçersiz anahtarla (Flask test client) | 🔴 **C-01 üretildi:** `success:false` döner ama `provider='deepl'` + geçersiz `api_key` runtime'a yazılır, `enabled` açık kalır |
| **3. tur:** `socketio.test_client(app)` tokensuz | 🔴 **C-02 üretildi:** `is_connected() == True` — handshake'de token yok |
| **3. tur:** `py_compile` + `pyflakes` + `test_smoke.py` (tekrar) | ✅ hepsi geçti |

**Çalıştırılmayan kontroller:** gerçek ses akışıyla uçtan uca test (mikrofon/sistem sesi), gerçek OpenAI/DeepL çağrıları (C-01 testi sahte anahtarla yapıldı — DeepL'e yalnız reddedilen tek istek gitti), diarization'ın çalışan bir ortamda gözlemi (bu ortamda B-01 nedeniyle imkânsız), `npm run build` tam paketleme, Electron davranış testi, C-03/C-04/C-05'in runtime üretimi (statik kanıtla raporlandı).

---

## 7. ÖNCELİK SIRASI ÖNERİSİ

1. **B-01 + B-02** — Konuşmacı tanıma bu kurulumda tamamen ölü; düzeltme küçük (`getattr(diarization,'speaker_diarization',diarization)`) ama etkisi büyük. torchcodec'i de aynı işte hallet.
2. **A-01** — Durdur'da son konuşmanın kaybı (veri kaybı).
3. **A-02** — Yol eşleşmesi; etkilenen kullanıcı uygulamayı açamaz.
4. **C-01** — Başarısız DeepL testinin runtime'ı bozması: test→commit sırasını değiştirmek küçük bir route düzeltmesi; canlı çeviriyi sessizce öldürüyor.
5. **B-03 + B-04 + G-11** — Çeviri anahtarı yaşam döngüsü: yanlış "aktif" mesajı + sessiz anahtar silinmesi + tek-anahtar beklentisi.
6. **A-04, A-03** — sessiz CPU düşüşü ve çift çeviri maliyeti.
7. **B-05 + G-10, C-04 + G-16** — PTT yaşam döngüsü: sessiz düşüş + sıralama/keepalive tutarlılığı.
8. **C-03** — mic modunda dil zorlama (tek satır); kullanıcı deneyimini doğrudan etkiler.
9. **C-02 + G-15** — socket auth (derinlemesine savunma; yerel tehdit modelinde düşük-orta).
10. **B-06, C-05, C-06, B-07..B-09, A-05** — küçük tutarlılık/sağlamlık düzeltmeleri.

---

*Bu rapor statik kod incelemesi, kurulu `.venv` paket-sürümü/API doğrulamaları ve yukarıdaki komutlara dayanır; çalışma-zamanı davranışı her ortamda birebir doğrulanmamıştır. Özellikle A-01/A-04 gerçek donanım/ses akışında, B-01/B-02 diarization açıkken yeniden üretilmelidir.*
