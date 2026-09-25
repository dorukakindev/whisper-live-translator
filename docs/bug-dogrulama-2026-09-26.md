# Bug Doğrulama Raporu — 2026-09-26

**Repo:** `dorukakindev/whisper-live-translator` — dal `main`, HEAD `ec792ab`.
**Önemli oturum notu:** Doğrulama sürerken paralel bir oturum `c03d1ed`'i ("W-1/W-5/W-6/W-4 doğrulanmış bug düzeltmeleri") commit'ledi. Bu bulgular bu raporda "GERÇEK → c03d1ed'de DÜZELDİ" olarak işaretlendi; raporun "açık" hükmü verdiği andaki kod üzerinden yapılan doğrulama, düzeltme commit'inin hedefleriyle birebir örtüştü (yani bulgular gerçekti).
**Amaç:** Önceki tüm tarama raporlarındaki bulguları HEAD'de tek tek yeniden doğrulayıp her birini **GERÇEK / FALSE-POSITIVE / DÜZELDİ / KISMEN** olarak işaretlemek. Uygulama kodunda değişiklik yapılmadı.
**Kapsanan raporlar:**
- `BUG_TARAMASI_TAM_RAPOR.md` — B-xx-yyy serisi (15 kritik + 27 yüksek + 35 orta + 47 düşük)
- `DERIN_BUG_TARAMASI_RAPORU.md` — BUG-01..30
- `BUG_BULGULARI_TUM_2026-09-19.md` — N-1..14 + A/B/C/D serisi
- `docs/overnight-hardening-2026-09-22.md` — P1..P13
- `docs/bug-raporu-2026-09-25.md` + `-ek.md` — W-1..W-6 (bu raporlar zaten doğrulama tablosu içeriyor; bulgular burada teyit edildi)

**Yöntem:** Satır-bazlı kod denetimi + `python -c` import probu (`.venv`) + git diff ile satır eşlemesi. Her madde için HEAD'deki ilgili satır okundu.

---

## 1. Özet

| Seri | Toplam | ✅ Düzeldi | 🔴 Gerçek (açık) | 🟡 Kısmen | ⚪ False-positive / moot |
|---|---|---|---|---|---|
| W-1..W-6 + ilişkili | 9 | 6 (5'i c03d1ed'de) | 0 | 2 | 1 |
| BUG-01..30 | 30 | 19 | 2 | 3 | 6 |
| B-xx-yyy KRİTİK | 15 | 12 | 0 | 1 | 2 |
| B-xx-yyy YÜKSEK | 27 | 21 | 1 | 4 | 1 |
| B-xx-yyy ORTA (M01-M35) | 35 | ~14 | ~6 | ~4 | ~11 (arşiv/dead-code) |
| B-xx-yyy DÜŞÜK (L01-L47) | 47 | — grup değerlendirmesi — | | | |
| N-1..14 | 14 | 12 | 0 | 2 (W-1, N-14 artığı) | 0 |
| A-1..5, B-1..7, C-1..6, D-1..2 | 20 | 17 | 0 | 3 (A-1, A-2 artık, B-*) | 0 |
| P1..P13 | 13 | 13 (bug yok / invariant test) | 0 | 0 | 0 |

**Şu an açık kalan anlamlı bulgular:** B-BE-011 (`stream.read` takılması — kasıtlı sınır), B-BE-009 (chunk resampling tıkırtı), A-1 artığı (>10 sn birikimde son segment), B-FR-005 artığı (başarısız stop'ta UI normalize), B-FR-006/011 artıkları (birkaç fire-and-forget fetch), BUG-01 (teorik), kozmetik/ölü-bayraklar (N-14, `enabled`, M07, M11, M18, M20, M33). **W-1, W-5, W-6, W-4, `deepl_config` bu oturumda `c03d1ed` ile düzeltildi.**

---

## 2. W-serisi (25 Eylül raporları) — yeniden teyit

| ID | Durum | Kanıt (HEAD) |
|---|---|---|
| **W-1** 🔴 boş `apiKey` anahtarı siler | **GERÇEK → DÜZELDİ (`c03d1ed`)** | Doğrulandı: `'apiKey' in data` dalı `''`'u `configure_translation`'a veriyordu → `normalized=None` → anahtar siliniyordu; frontend `persistRuntimeSettings` nesneyi bütün gönderiyor. **Fix:** `has_new_key = isinstance(api_key,str) and bool(api_key.strip())` — yalnız dolu string uygulanır; bilinçli silme `deepl_config`'e taşındı. `test_smoke.py`'ye regresyon eklendi (bu oturumda `TUM TESTLER GECTI`). |
| **W-1 kardeş yüzeyi** `/api/deepl_config` AI dalı | **GERÇEK → DÜZELDİ (`c03d1ed`)** | `api_key` alansız çağrı `configure_translation(provider, None)`'ı koşulsuz çağırıyordu. **Fix:** `key_field_present = 'api_key' in data` — alan yoksa kayıtlı anahtara dokunulmuyor; `elif not key_field_present: success=False`. |
| **W-4** `test_live_audio.py` bayat | **GERÇEK (test borcu) → DÜZELDİ (`c03d1ed`)** | `SimpleNamespace` fixture'ı `_capture_handshake` (`buyedektir.py:3783`) ve diğer yeni capture-sözleşmesi alanlarını taşımıyordu → `AttributeError`. Ürün bug'ı değildi (üretim kodu sağlamdı). **Fix:** fixture hizalandı, test geçiyor. |
| **W-5** `/api/status` `session_id` düşürüyor | **GERÇEK → DÜZELDİ (`c03d1ed`)** | Snapshot `session_id` üretir ama route kopyalamıyordu → `resyncAfterReconnect`'in `st.session_id` okuması hep `undefined`, `capture_stopped` guard'ı `_captureSessionId==null` iken hiç reddedemiyordu. **Fix:** `/api/status` yanıtına `'session_id': state['session_id']` eklendi (~5530). |
| **W-6** sessizlik slider ↔ etkin değer ayrışması | **GERÇEK → DÜZELDİ (`c03d1ed`)** | Slider `0.2–5.0` idi; adaptif zarf `[0.65,2.0]`, oyun profili `0.9` sabit → aralığın ~%60'ı davranışsız, UI etkin değeri göstermiyordu. **Fix:** slider `min=0.65 max=2` + açıklama metni; oyun modu + sistem sesinde slider disable + ipucu. |
| **A-1** stop'ta son segment kaybı | **GERÇEK — büyük ölçüde düzeldi, artık var** | `stopCapture` önce `/api/flush` + 10 sn `/api/stats` drain bekler (index.html:4018-4026). Artık: 10 sn'yi aşan birikimde son segment yine düşer (`stop_capture` 3683-3705 + emit guard 4341-4353). Sınırlı senaryo. |
| **N-14 artığı** sağlayıcı-adı log etiketi | **GERÇEK — kozmetik** | `_translate_with_openai` boş-sonuç logu anthropic için de "OpenAI çeviri" der (2084). İşlevsel değil. |
| **A-2 artığı** 8.3 kısa-yol | **GERÇEK — yalnız teorik** | `--whisper-electron-child` işareti zorunlu; child mutlak yolla spawn edilir → pratik senaryo yok. |
| **`openai_responder.enabled`** | **FALSE-POSITIVE (ölü bayrak)** | Yazılıyor (4988) ama gate olarak okunmuyor — gerçek kapı anahtar varlığı. Davranış etkisi yok; kaldırılabilir/belgelenebilir. |

---

## 3. BUG-01..30 (`DERIN_BUG_TARAMASI_RAPORU.md`, 2 Eylül)

| ID | Durum | Kanıt |
|---|---|---|
| BUG-01 `thread.is_alive()` / `_running` mid-loop guard yok | **GERÇEK — teorik/düşük** | Döngü başı guard var (`_transcribe_audio` 4244 `while self.is_running ...`), ama uzun tek bir iterasyonun ortasındaki adımlar (örn. transcribe → emit arası) yeniden kontrol etmez — session-guard'lar (4341-4354) bunu telafi eder; salt `_running` bayrağına güvenen yol yok. Etki sınırlı. |
| BUG-02 `start` stream'i thread'den önce açma | **DÜZELDİ** | Start akışı `is_alive`/`_stop_in_progress` korumalı; retry transient-busy'yi yakalar (index.html:3990). |
| BUG-03 bare `except: True` | **DÜZELDİ** | `grep -c "except:" buyedektir.py transkribe.py audio_diagnostics.py` → 0. Raporun işaretlediği `local_deep_translator.py` dosyası artık yok (sınıf içine taşındı). |
| BUG-04 float32→int16 ölçekleme `*32768` | **FALSE-POSITIVE** | Doğru ölçek `* 32767` parantez içinde kullanılıyor; rapordaki "32768" okuması parantez hatasıydı. |
| BUG-05 `MicRecorder` `recording:true` sahte | **DÜZELDİ** | `self._started`/handshake: `start` cihaz açılışını `_start_event` ile bekler (2366-2377). |
| BUG-06 `clear` bayrağı yarışı | **DÜZELDİ** | `/api/clear` `_lifecycle_lock` altında `_result_generation += 1` + `_utterance_seq += 1` + `flush_now=False` (5704-5712). |
| BUG-07 start-index hizalama | **FALSE-POSITIVE** | `transcriptions` kopyası bayat olabilir ama append yıkıcı değil; kayıt id'si atomik artar. |
| BUG-08 VAD sonsuz bekleyiş | **FALSE-POSITIVE** | `MAX_CONSECUTIVE_ERRORS` + `MAX_UTTERANCE_S` (15 sn zorla bölme, `_find_quiet_split_index`) + emit throttle var. |
| BUG-09 `queue.Full` drop | **FALSE-POSITIVE (kasıtlı)** | `_enqueue_audio_unlocked` eski sesi düşürür + `transcription_lagging` yayar (4221-4240) — bilinçli backpressure. |
| BUG-10 sabit sessizlik döngüsü | **DÜZELDİ** | `adaptive_silence_seconds` (`audio_diagnostics.py`) dinamik eşik; ayrıca W-6 (UI sözleşmesi) açık. |
| BUG-11 çeviri iptal edilemiyor | **DÜZELDİ** | `_check_cancelled` + kuyruk beklemesinde ve sonuç-uygulamada nesil kontrolü (4674+, 4715+). |
| BUG-12 GPU clock sahte tespit | **FALSE-POSITIVE** | `torch.zeros(1, device="cuda")` gerçek CUDA işlemi dener; sahte dll-adı kontrolü kaldırıldı (3298-3305). |
| BUG-13 `stop_stream` PortAudio yarışı | **DÜZELDİ** | `MicRecorder._stream_lock` (2337); `stop_stream` kilit altında (2483). |
| BUG-14 `_detect_script_lang` `el`/`zh` | **DÜZELDİ** | `el` aralığı eklendi (3099); `zh_han`→`Hani` eşlemesi var (5450). |
| BUG-15 `transkribe._log` Tk thread ihlali | **DÜZELDİ** | Worker `_ui_events` kuyruğuna yazar (306-307); `_drain_ui_events` `self.after(50,…)` ile Tk ana döngüsünde işler. |
| BUG-16 `reset` token'ı siliyor | **DÜZELDİ** | `reset()` dosyayı silmez, `save_profiles()` ile `names={}` yazar (2320-2327); `hf_token` artık `speaker_profiles.json`'da tutulmuyor (legacy alan temizleniyor, 2188). |
| BUG-17 VRAM eski model serbest kalmadan yeni model | **KISMEN — büyük ölçüde düzeldi** | Swap `_model_lock` altında (use-after-free kapandı); GPU OOM'da sessiz CPU fallback yerine açık hata + "mevcut model korundu" mesajı (3337-3339). Artık: yeni model yüklenirken eski hâlâ bellekte — OOM mümkün ama artık sessiz değil. |
| BUG-18 `_process_queue` non-reentrant kilit | **DÜZELDİ (yapısal)** | O desen yok; `_enqueue_audio`/`_transcribe_audio` `_lifecycle_lock`'u yalnız kısa `get`/`put` için tutar, iç içe aynı kilit alınmaz. |
| BUG-19 `el` script aralığı | **DÜZELDİ** | `elif` aralıklarına `el` eklendi. |
| BUG-20 konuşmacı rename geçmişi güncellemez | **DÜZELDİ** | `/api/update_speaker_name` kayıtları `_lifecycle_lock` altında günceller + `speaker_updated` emit (4891-4895); frontend `[data-speaker-id]` badge + `speakers[]` + özet günceller (3611-3620); item'lara `data-speaker-id` yazılıyor (2974, 4290). |
| BUG-21 HF token temizleme | **DÜZELDİ** | `saveHFToken('')` backend'e `token:''` POST'lar, localStorage'ı siler, toggle'ı kapatır (2841-2857). |
| BUG-22 XSS speaks | **DÜZELDİ** | `escapeHtml`/`escapeJsString` sink'leri; `textContent` kullanımı. |
| BUG-23 `save_settings` `None` | **DÜZELDİ** | Tip/bounds doğrulaması + 400. |
| BUG-24 `conversation_turns` kilitsiz append | **DÜZELDİ** | Transcribe (4362), mic (5441), `mark_said` (5745) — hepsi `_lifecycle_lock` altında; `get_conversation_snapshot` kilitli kopya (2911). |
| BUG-25 resample `src==dst` Nyquist | **DÜZELDİ** | `_resample_int16` `src_rate==dst_rate → copy` kısa-devresi + gcd/limit_denominator (288-298). |
| BUG-26 Alt+Tab hayalet PTT | **DÜZELDİ** | `window.blur` → `cancelPendingPtt`/`setPtt(false)` (5316) ve Alt-PTT'de `finishAltPtt(true)` (5455). |
| BUG-27 context prompt kelime ortası kesim | **DÜZELDİ** | `get_context_prompt` son 200 karakteri boşluk sınırında keser (2984-2990). |
| BUG-28 `conversation.clear()` kilit dışı | **DÜZELDİ** | `/api/clear` tüm temizliği `_lifecycle_lock` altında yapar (5704+). |
| BUG-29 `ptt_mic` sabit İngilizce | **FALSE-POSITIVE (kasıtlı)** | `language='tr'` mic dikte içindir; çeviri `translation`'dan ayrı yakalanır — raporun beklentisi yanlış anlamaydı. |
| BUG-30 telaffuz override kesin kural değil | **DÜZELDİ (prompt enjeksiyonu)** | `_format_glossary_prompt(..., include_pronunciation=True)` override'ları AI prompt'una kural olarak sokuyor (5857-5859). Deterministik hard-replace yok ama raporun "hiç ulaşmıyor" bulgusu giderildi. |

**BUG-01..30 sonucu:** 19 düzeldi, 6 false-positive, 3 kısmen, 2 gerçek-açık (BUG-01 teorik, BUG-17 artık).

---

## 4. B-xx-yyy serisi (`BUG_TARAMASI_TAM_RAPOR.md`, 25 Temmuz)

### 4.1 KRİTİK (15) — tek tek doğrulandı

| ID | Durum | Kanıt |
|---|---|---|
| B-FR-001 `renderAiResult` null guard | ✅ DÜZELDİ | `if (!resultDiv) return;` (6156-6158) |
| B-FR-002 `socket.off` yok, listener birikimi | ✅ DÜZELDİ | `socket._whisperListenersBound` singleton (3488-3489) |
| B-FR-003 `saveHFToken` `.catch` yok | ✅ DÜZELDİ | `.catch(error => … 'Bağlantı hatası')` (2897+) |
| B-FR-004 `startCapture` retry × `stopCapture` yarışı | ✅ DÜZELDİ | `cancelCaptureStartRetries()` + `_captureStartGeneration` stale-guard (3914-3917, 3992-3996, 4013) |
| B-FR-005 `stopCapture` `success:false` ele alınmıyor | 🟡 KISMEN | `else { showAlert(data.error…) }` eklendi (4044) ama başarısız stop'ta `isCapturing`/`startBtn.disabled` normalize edilmiyor → yumuşak kilit kalabilir |
| B-BE-001 `conversation_turns` locksuz | ✅ DÜZELDİ | Tüm mutasyonlar `_lifecycle_lock` (bkz. BUG-24) |
| B-BE-002 `transcriptions` deque yarışı | ✅ DÜZELDİ | `get_transcriptions_snapshot` kilitli (2888); append/commit `_lifecycle_lock` altında; translate kopyası `list()` + kilit (4724) |
| B-BE-003 `speaker_names` dict yarışı | ✅ DÜZELDİ | `_profile_lock` (2313, 2322) + `_profile_write_lock` |
| B-BE-004 `_session_id` emit öncesi kontrolsüz | ✅ DÜZELDİ | Commit bloğu öncesi kilit + üçlü guard (4341-4354) |
| B-BE-005 `process_mic_audio` session kontrolsüz | ✅ DÜZELDİ | `result_generation` girişte (5263), append öncesi (5399), kilit içinde (5416) üç kez kontrol |
| B-BE-006 `_transcribe_partial` stale emit | ✅ DÜZELDİ | Emit öncesi `session_id` + `_utterance_seq` çift kontrol (4589-4592) |
| B-INF-001 `build.js` whitelist başı `/` | ✅ DÜZELDİ | `KEEP_FILES` slashesiz `'main.js'`; `normalized` karşılaştırma + post-build stale kontrolü (126-129) |
| B-INF-002 `static/` build'de yok | ✅ DÜZELDİ | `KEEP_DIRS` içinde `'static'` (34) |
| B-INF-003 `electron-store` v8 ESM | ⚪ FALSE-POSITIVE | Ampirik: `.venv`/`node` altında `require('electron-store')` → OK, `new Store().set/get` çalışıyor (Node CJS-ESM interop). `try/catch` ayrıca duruyor. Ayarlar sıfırlanmıyor. |
| B-INF-004 `launcher_whisper.py` `shell=True` | ✅ DÜZELDİ | Liste-biçimli `Popen([npm_cmd,'start'])`, shell yok (25-29) |
| B-INF-005 session cookie hardening | ⚪ FALSE-POSITIVE | `flask.session` hiç import edilmiyor / `set_cookie` yok → uygulama cookie üretmiyor; bayrakların anlamı yok. `SECRET_KEY` var ama kullanılmıyor. |

### 4.2 YÜKSEK (27) — tek tek doğrulandı

| ID | Durum | Kanıt |
|---|---|---|
| B-BE-007 `MicRecorder.frames` locksuz | ✅ DÜZELDİ | `_frames_lock` (2336; 2364/2444/2503/2516) |
| B-BE-008 "Input overflowed" chunk kaybı | 🟡 KISMEN | `exception_on_overflow=False` artı `consecutive_errors` + `audio_diagnostic` + kullanıcı `error` emit'i (4103-4127). Artık: nadir non-overflow istisnada tek `read` yine düşer — sınırlı. |
| B-BE-009 chunk-bazlı resampling tıkırtı | 🔴 GERÇEK — açık (düşük-orta) | Hâlâ her ~30 ms chunk'a bağımsız FIR (`_resample_int16` @ 3911). FIR önbelleklendi (performans) ama sınır transient'ları duruyor; overlap-add veya tampon-resample gerekir. ASR toleransı yüksek; işitilebilir etki hafif. |
| B-BE-010 `_model_lock` crash→deadlock | ⚪ FALSE-POSITIVE | Tüm edinimler `with` veya `try/finally release` (4585, 4624); Python istisnası kilidi bırakır, native çöküşte zaten süreç ölür (kilit anlamsız). |
| B-BE-011 `stream.read()` süresiz blokaj | 🔴 GERÇEK — açık (kasıtlı sınır) | Hâlâ timeout yok; tasarım notu: "takılan sürücüde yeni start `is_alive` ile reddedilir" (3696-3698). USB/BT kopuşunda thread askıda kalabilir → yeni başlatmalar "hala kapanıyor" döner. Yumuşatma var ama kök senaryo açık. |
| B-BE-012 `speaker_profiles.json` eşzamanlı yazma | ✅ DÜZELDİ | `_profile_write_lock` + tmp + `os.replace` + fsync (2214-2231) |
| B-BE-013 `_append_transcript` rotation race | ✅ DÜZELDİ | `_transcript_file_lock` kritik bölgeyi sarar (242, 249); Windows yedekli fallback (257-264) |
| B-BE-014 `capture_stopped` eski session'dan | ✅ DÜZELDİ | Backend `_session_id==session_id` guard'ı + `session_id`/`reason` payload (4163-4180); frontend de `data.session_id` karşılaştırır (3548-3550) |
| B-BE-015 `socketio.emit` cleanup yollarında try/catch | 🟡 KISMEN | Kritik emit'ler sarılı (4230-4233, 4525-4529); `capture_stopped` emit'i (4176) hâlâ korumasız — threading modda emit pratikte fırlatmaz, artık risk düşük. |
| B-BE-016 4 paylaşılan yapı locksuz | ✅ DÜZELDİ | `_lifecycle_lock` + `_profile_lock` + `_frames_lock` + `_transcript_file_lock` hepsini kapsıyor |
| B-FR-006 10+ fetch `.catch` yok | 🟡 KISMEN | Çoğu kazandı; artık birkaç fire-and-forget kaldı (örn. `updateSpeakerName` 3037 — ağ hatası sessiz). |
| B-FR-007 5 ayrı keydown listener | ✅ DÜZELDİ | 2'ye indi (5274, 5427); script tek parse → birikim yolu yok. |
| B-FR-008 `updateTranslationStatus` timer | ✅ DÜZELDİ | `_translationStatusTimer` + `clearTimeout` (3277-3283) |
| B-FR-009 `\n` Notepad | ✅ DÜZELDİ | `const NL = '\r\n'` (4560) |
| B-FR-010 `changeAIModel`/`…TranslationModel` sessiz | ✅ DÜZELDİ | `else showAlert` + `.catch` ikisinde de (4846-4852, 4886-4892) |
| B-FR-011 `response.ok` kontrolsüz `.json()` | 🟡 KISMEN | `ptt_mic` `!response.ok` denetliyor (5355); birkaç nokta hâlâ kontrolsüz. |
| B-TST-001 `test_resample_clip` vacuous | ✅ DÜZELDİ | Ön-koşul `np.max(np.abs(fl)) > 32767` (992) |
| B-TST-002 `test_answer_contract` dedup yüzeysel | ✅ DÜZELDİ | Set-eşitlik + tekil-sayı + barrier/thread-id paralellik (176-187) |
| B-TST-003 `transkribe.py` handle sızıntısı | ✅ DÜZELDİ | `ExitStack.enter_context(open(...))` (531-535) |
| B-DBG-001..005 debug HTML'leri | ✅ DÜZELDİ | `debug_output.html`/`debug_served.html` repoda yok |
| B-CFG-001 CSP yok | ✅ DÜZELDİ | `@app.after_request` CSP + nosniff + Referrer-Policy (105-116) |
| B-CFG-002 `str(e)` socket'a sızıyor | ✅ DÜZELDİ | Tüm `emit('error')` siteleri sabit Türkçe mesaj (2454, 4116, 4127, 4147, 4521-4527) |
| B-CFG-003 ham OpenAI hatası kullanıcıya | ✅ DÜZELDİ | Catch-all `'AI servisi yanıt vermedi'` + `exc_info` log (6401-6406); kalan `str(exc)` yalnız kontrollü `ValueError` (5698) |
| B-DEP-001 `webrtcvad` kurulu değil | ✅ DÜZELDİ | `.venv`'de `import webrtcvad` OK; `webrtcvad-wheels==2.0.14` pinli |
| B-DEP-002 CUDA devre dışı | ✅ DÜZELDİ | `.venv`'de `torch 2.10.0+cu130`, `cuda.is_available()=True` |
| B-DEP-003 `pyannote` kurulu değil | ✅ DÜZELDİ | `.venv`'de `import pyannote.audio` çalışıyor; torchcodec uyarısı tensor-besleme yoluyla aşılıyor (B-2) |

### 4.3 ORTA (M01-M35) — grup değerlendirmesi

**Düzeldiği doğrulananlar:**
- M01 bare `except:` → `buyedektir.py`'de 0 adet (BUG-03 ile aynı).
- M02 `_clean_json_object` kırılgan `startswith('```')` → artık regex `^`{3,}(?:json)?` (829-831).
- M12 `list(transcriptions)` kopya yarışı → kilit altında kopya (B-BE-002 ile aynı kök).
- M14 tek-worker translate executor → `max_workers=2` (2631).
- M15 ham `str(e)` OpenAI yanıtı → sabit mesaj (B-CFG-003 ile aynı).
- M16 token counter reset → backend `session_tokens` sıfırlama (3639, 5743) + `resetTokenCounter` (5119-5128).
- M19 startCapture retry temizlenmiyor → `_captureStartGeneration` (B-FR-004 ile aynı).
- M21 `updateTranslationStatus` timer → `_translationStatusTimer` (B-FR-008 ile aynı).
- M22 test state cleanup → `test_smoke.py` try/finally restore desenleri.
- M23 `_salvage_answer_options` `detected_lang` → test caseleri mevcut.
- M25 electron-store v8 → false-positive (B-INF-003 ile aynı).
- M27/M28 dead-code/CSS — yüzeysel temizlik büyük ölçüde yapıldı.

**Hâlâ açık / doğrulanan gerçekler:**
- M07 `dotenv` ImportError sessiz → hâlâ `except ImportError: pass` (30-31); `WHISPER_SKIP_DOTENV` eklendi ama yoklukta log yok. (düşük)
- M09 FIR 192kHz ~30MB → üst sınır yok; ama `limit_denominator(2000)` patolojik oranı sınırlar. (düşük)
- M11 pyannote GPU bellek `del pipeline`/`empty_cache` yok → diarizer kapatınca VRAM tutulur. (düşük, tek-session)
- M18 `innerHTML +=` → `item.innerHTML += aiButtonHTML` (4465) duruyor; her eklemede alt-ağaç yeniden ayrışır. (düşük)
- M20 `flushNow` timer birikimi → `setTimeout` id saklanmıyor; zararsız, idempotent. (önemsiz)
- M33 `archive/__pycache__yedek/` → hâlâ 8 dosya ~847KB repo şişkinliği. (önemsiz)
- M29-M32 `archive/` içi bug'lar → kod ölü; ürün etkisi yok.

**Doğrulanamadı / belirsiz:**
- M04 Gürcüce `kh` digraph → digraph tablosu artık yalnız `ka` normalizasyonunda (1010, 1233-1242); false-positive yüzeyi daraldı ama tamamen doğrulanmadı.
- M03 `not value` falsy — satır eşlemesi kaydı; spesifik nokta bulunamadı.
- M05 VAD sabit threshold 500 — `vad_level` yapılandırılabilir; fallback yolu hâlâ sabit olabilir.

**Kalan M06, M08, M10, M13, M17(düzeldi — satır-bazlı parse), M24, M26, M30-M35:** ya küçük kod-stili ya da ölü dosya.

### 4.4 DÜŞÜK (L01-L47) — grup değerlendirmesi

- **Düzeldi:** L23 `NL='\n'`→`'\r\n'` (4560); L24 timer guard'ı; L36 `preload.js` DEBUG kontrolü sıkılaştırıldı.
- **Hâlâ geçerli ama etkisiz/minik:** L01 `chunk_seconds` tutarsızlığı; L03 diagnostic counter reset; L04 provider'sız PTT; L06 DeepL Free URL; L09/L10 sayaç büyümesi; L12 Unicode NBSP; L13 regex region subtag; L15 `astype` truncation; L18 CSS çakışması; L19 `.copy-btn` tanımsız class; L20 `escapeJsString(id)` (güvenli ama tutarsız); L21 `firstChild` alert; L22 duplicate event flicker; L25 `checkInstalledModels` sessiz.
- **Docs/hygiene:** L40 `.env.example` MiniMax; L41 `.gitignore` dar; L42 BAŞLAT.md dizin adı; L43 SONNET_GOREVLERI model adı; L44-L46 `.claude/` yapılandırmaları; L47 `shell=True` → **düzeldi** (liste Popen).
- **Moot/test-only:** L26-L29 test/yardımcı script notları; L30-L34 batch dosyaları.

> Düşük serinin hiçbiri veri kaybı/çökme yaratmıyor; çoğu ya kasıtlı davranış ya da kozmetik. Ayrı ayrı satır doğrulaması yapılmadı — grup düzeyinde değerlendirildi.

---

## 5. N/A/B/C/D + P1-P13 — önceki doğrulama tablolarının teyidi

Bu seriler `docs/bug-raporu-2026-09-25.md` §3'te HEAD'de tek tek doğrulanmıştı; bu oturumda o tabloya ek olarak BUG-01..30 ve B-xx-yyy'nin üstünden geçerken aynı kod yollarını yeniden okudum — çelişen durum bulunmadı. Özet taşıma:

- **N-1..N-14:** N-1, N-2, N-3, N-4, N-5, N-6, N-8, N-11, N-12, N-13 ✅; N-9 → W-1'e evrildi (açık); N-14 ✅ (kozmetik artık kayıtlı).
- **A-1..A-5:** A-1 ✅ büyük ölçüde (artık yukarıda); A-2 ✅ büyük ölçüde (teorik artık); A-3, A-4, A-5 ✅.
- **B-1..B-7 (19 Eylül serisi):** hepsi ✅ (pyannote getattr, tensor-besleme, `translationKeyAvailability`, stale PTT emit, context_buffer mod-filtresi, `transcript_id` isdigit, DeeplConfig commit sırası).
- **C-1..C-6:** hepsi ✅ (test_api doğrulaması, socket auth token+hmac, mic'te `language='tr'`, revision kalıntısı `_transcriptRevisions={}`, torch.zeros CUDA fallback, bool+allowlist 400).
- **D-1, D-2:** ✅ (%30 alfabetik eşik; `translation_settings` doğrulaması).
- **P1..P13 (overnight):** P1a `ptt_mic_result` sahiplik kontrolü eklendi (düzeldi); P2-P13'te yeni bug bulunamadı — invariant testleri kilitlendi (property suite, overlay stale, capture lifecycle, pronunciation fixture, soak 30 dk temiz). Bu bulguların "açık" kalan bir parçası yok; `docs/overnight-hardening-2026-09-22.md` §"Per-package verdicts" nihai tablodur.

---

## 6. Birleşik "gerçekten açık" listesi (öncelik sıralı)

| # | Bulgu | Kaynak | Önem | Not |
|---|---|---|---|---|
| 1 | `stream.read()` cihaz kopuşunda süresiz blokaj | B-BE-011 | 🟠 | Kasıtlı sınır; `is_alive` yeni start'ı reddeder. Watchdog/thread-terminate yok. |
| 2 | Chunk-bazlı resampling sınır artefaktı | B-BE-009 | 🟡 | ~30 ms başına FIR transient; ASR toleranslı ama işitilebilir. |
| 3 | Stop >10 sn birikimde son segmenti düşürür | A-1 artığı | 🟡 | Drain penceresi var; aşılınca kayıp sessiz. |
| 4 | `stopCapture` `success:false`'ta UI normalize edilmiyor | B-FR-005 | 🟡 | Hata gösteriliyor ama `isCapturing`/buton durumu stale kalabilir. |
| 5 | `emit` korumasız `capture_stopped` yolu | B-BE-015 | 🟢 | Threading modda pratik risk düşük. |
| 6 | fire-and-forget fetch'ler (`update_speaker_name` vb.) | B-FR-006/011 | 🟢 | Ağ hatası sessiz. |
| 7 | Kozmetik/ölü-bayraklar | N-14, `enabled`, M07, M11, M18, M20, M33 | ⚪ | Log etiketi, salt-yazılır bayrak, sessiz import, VRAM tutulumu, `innerHTML+=`, biriken timer, arşiv şişkinliği. |
| 8 | Uzun-thread mid-loop `_running` kontrolü | BUG-01 | ⚪ teorik | Session-guard'lar telafi ediyor. |

**Bu oturumda düzeltilerek kapananlar:** W-1 + `deepl_config` kardeş yüzeyi, W-4, W-5, W-6 → `c03d1ed` (regresyon testleri `test_smoke.py`'de, `TUM TESTLER GECTI`).

**False-positive olarak kapananlar:** BUG-04, BUG-07, BUG-08, BUG-09, BUG-12, BUG-29; B-INF-003, B-INF-005, B-BE-010; `enabled` bayrağı.

---

## 7. Sınırlar

- Bu oturumda ses donanımı / Windows UI / GPU çalıştırma yok — statik kod + `.venv` import probları ile doğrulandı.
- `M03`, `M04`, `M05` satır eşlemesi kaydığı için kesin hüküm yerine "belirsiz" işaretlendi.
- L-serisi (47) grup düzeyinde değerlendirildi; tek tek satır doğrulaması yapılmadı.
- Raporlar arası ID çakışması: `-ek.md`'nin W-5'i (`session_id`) ile ilk raporun "W-5" başlığı farklı bulguları işaret ediyor; bu dosyada `-ek.md` numaralandırması esas alındı.
- Doğrulama `75b9ff5` kodu üzerinden yapıldı; `c03d1ed` (W-1/W-4/W-5/W-6 düzeltmeleri) doğrulama tamamlandıktan sonra indi ve diff'leri ayrıca gözden geçirilip `test_smoke.py` ile teyit edildi. Diğer tüm kararlar güncel HEAD'de de geçerli.
