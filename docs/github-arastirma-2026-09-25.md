# GitHub Depo Araştırması — Whisper Pro İçin Geliştirme ve Özellik Fırsatları

**Tarih:** 2026-09-25 · **Kapsam:** Whisper Pro (`buyedektir.py` 6529 satır, Electron + Flask + faster-whisper canlı çeviri/AI-asistanı) ile aynı problem alanındaki açık kaynak projelerin **kaynak kodu seviyesinde** incelenmesi.

**Yöntem:** GitHub REST API ile depo arama → aday depoların gerçek kaynak dosyalarının (`raw.githubusercontent.com`) okunması → mevcut kodla karşılaştırma. Hiçbir uygulama kodu değiştirilmedi; bu dosya yalnız rapordur.

## İncelenen depolar

| Depo | Yıldız | Ne için bakıldı |
|---|---|---|
| [QuentinFuxa/WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit) | 11k | Canlı ASR + diarization + çeviri; en yakın ürün |
| [ufal/whisper_streaming](https://github.com/ufal/whisper_streaming) & [ufal/SimulStreaming](https://github.com/ufal/SimulStreaming) | 676 | LocalAgreement-2 / AlignAtt eşzamanlılık politikaları |
| [TheDeathDragon/LiveTranslate](https://github.com/TheDeathDragon/LiveTranslate) | 700 | Windows sistem-sesi yakalama + ASR + altyazı overlay'i; VAD tasarımı |
| [Sharrnah/whispering](https://github.com/Sharrnah/whispering) | 548 | Oyun/çağrı odaklı canlı STT; ses iyileştirme, TTS, OCR |
| [Prat011/free-cluely](https://github.com/Prat011/free-cluely) | 1.7k | Electron "görünmez asistan" pencere teknikleri |
| [juanmc2005/diart](https://github.com/juanmc2005/diart) | 2k | Gerçek zamanlı (streaming) konuşmacı ayrıştırma |
| [snakers4/silero-vad](https://github.com/snakers4/silero-vad) · [TEN-framework/ten-vad](https://github.com/TEN-framework/ten-vad) | 10.3k / 2.3k | webrtcvad alternatifi NN tabanlı VAD |
| [rany2/edge-tts](https://github.com/rany2/edge-tts) | 12k | Ücretsiz Microsoft neural TTS (100+ dil) |
| [QuentinFuxa/NoLanguageLeftWaiting](https://github.com/QuentinFuxa/NoLanguageLeftWaiting) (nllw) | — | faster-whisper'la aynı ctranslate2 çekirdeğinde çalışan NLLB-200 çeviri |
| [miurahr/pykakasi](https://github.com/miurahr/pykakasi) · [polm/cutlet](https://github.com/polm/cutlet) · [mozillazg/python-pinyin](https://github.com/mozillazg/python-pinyin) · [osori/korean-romanizer](https://github.com/osori/korean-romanizer) · [dmort27/epitran](https://github.com/dmort27/epitran) · [isi-nlp/uroman](https://github.com/isi-nlp/uroman) | 460–5.4k | Deterministik romanizasyon → okunuş doğrulama |
| [sarthakdev143-lite/wingman](https://github.com/sarthakdev143-lite/wingman), [JonathanFly/faster-whisper-livestream-translator](https://github.com/JonathanFly/faster-whisper-livestream-translator) | 4 / 84 | Groq STT, canlı altyazı zincirleri |
| [moonshine-ai/moonshine](https://github.com/moonshine-ai/moonshine) | 11k | Ultra düşük gecikmeli streaming ASR |
| [argosopentech/argos-translate](https://github.com/argosopentech/argos-translate) | 6.5k | Yerel çeviri alternatifi |

---

## 1. Canlı transkripsiyon çekirdeği

### 1.1 LocalAgreement-2 ile kararlı kısmi transkript — EN GÜÇLÜ ÖNERİ

**Mevcut durum:** `_transcribe_partial` her `PARTIAL_INTERVAL`'da (1.2–4 sn) tamponun son `PARTIAL_SNAPSHOT_S` (7 sn) anlık kopyasını yeniden transkribe ediyor ve tüm önizleme metnini değiştiriyor (`buyedektir.py:4531+`). İki ardışık geçişte kelimeler değişirse ekranda titreme olur; "kilitlenmiş" kelime kavramı yok.

**Repodaki yaklaşım:** WhisperLiveKit'in `whisperlivekit/local_agreement/online_asr.py` dosyasında Interspeech 2020 LocalAgreement-2 politikası var (`HypothesisBuffer` + `OnlineASRProcessor`, ~230 satır):

- **HypothesisBuffer.insert/flush:** yeni hipotez ile önceki tamponun **en uzun ortak öneki** "committed" (kesinleşmiş) sayılır; yalnız kuyruk gri önizleme olarak kalır. Kelime kelime kesinleşme → UI'da titreme biter, metin büyüdükçe erken satırlar kararlı siyahlaşır.
- **N-gram dedup (insert içinde 1–5 token):** commit kuyruğu ile yeni hipotez başındaki 1–5 kelimelik çakışmayı siler. Whisper Pro'nun segment sınırlarındaki tekrar sorununu (halüsinasyon filtresiyle kısmen çözülen) yapısal olarak giderir.
- **`prompt()`:** ses tamponunun DIŞINDA kalan son ~200 karakteri `init_prompt` olarak modele veriyor. Bizim `condition_on_previous_text=False` seçimimizin (tekrar döngüsünü kırmak için 4287. satırda) daha güvenli karşılığı: bağlam devamı sağlıyor ama tampon içeriğine koşullanmadığı için döngü yaratmıyor.
- **Anti-freeze reset:** `buffer_trimming_sec` (örn. 15 sn) boyunca hiç commit çıkmazsa tamponu sıfırlıyor — bizim `_utterance_seq`/snapshot damgasının üstüne ek bir takılma koruması.
- **confidence_validation:** `avg_logprob` > eşik olan tokenlar iki geçiş beklemeden anında commit ediliyor — hızlı donanımda gecikmeyi daha da düşürüyor.

**Taşıma notu:** faster-whisper `word_timestamps=True` ile kelime zamanları veriyor (şu an hiç kullanılmıyor). `HypothesisBuffer` sınıfı ASR'dan bağımsız, ~100 satır; port maliyeti düşük. Önce sadece `partial` yolunda `word_timestamps=True` + metin-seviyesi önek anlaşması ile başlanıp tam token-zamanlı versiyona geçilebilir.

**Etki/efor:** Yüksek etki (canlı önizlemenin ana kalite kusuru olan titremeyi bitirir + önizlemeden finale dönüşen kısmın erken kilitlenmesi), orta efor.

### 1.2 Segmentasyon için Silero VAD (webrtcvad yerine)

**Mevcut durum:** Yakalama döngüsü `webrtcvad` (GMM, 2009 dönemi) ile konuşma/sessizlik ayrımı yapıyor (`_vad_is_speech`, `buyedektir.py:312`, `self.vad = webrtcvad.Vad(level)`). Final çağrısında `vad_filter=True` zaten faster-whisper'ın **içsel Silero VAD**'ini kullanıyor — yani Silero modeli paketin içinde zaten mevcut.

**Repodaki yaklaşım:** WLK `silero_vad_iterator.py`'de ONNX Silero'yı `FixedVADIterator` ile akışlı çalıştırıyor; LiveTranslate `vad_processor.py`'de `pip install silero-vad` paketinin içinden gelen modeli `load_silero_vad()` ile çevrimdışı yüklüyor (torch.hub ağ erişimi gerekmiyor — kodda bilinçli fallback sırası var).

**Bizdeki kısa yol:** `faster_whisper.vad.get_speech_timestamps(audio, vad_options)` kurulu sürümde (1.2.1) hazır ve model faster-whisper paketinin `assets` klasöründe geliyor — **sıfır yeni bağımlılık**, torch bile gerekmiyor (ONNX). Alternatif olarak daha yeni `TEN-framework/ten-vad` (2.3k★) da düşük gecikmeli.

**Etki/efor:** Orta-yüksek etki (oyun sesi/müzik/arka plan gürültüsünde konuşma başlangıç-bitiş hassasiyeti), düşük-orta efor. `_vad_is_speech` arayüzü sabit kalıp içi Silero olabilir; risk: VAD'nin 512 örneklik (32 ms) pencere gereksinimi — mevcut chunk düzeniyle uyumlu kontrol edilmeli.

### 1.3 Progressif sessizlik katmanları (LiveTranslate'den tek eksik parça)

**Mevcut durum:** `adaptive_silence_seconds` (`audio_diagnostics.py:35`) konuşma uzadıkça bekleme süresini *uzatıyor* (8 sn+ konuşmada ×1.15) ve son duraksamaları taban olarak alıyor — yani adaptif sessizlik zaten var ama tek yönlü.

**Repodaki ek fikir:** `LiveTranslate/vad_processor.py` `_progressive_tiers`: tampon 3 sn'yi geçince sessizlik eşiği ×0.5, 6 sn'yi geçince ×0.25 — **uzun konuşmalarda kısa nefes arasında bile erken segment kesiyor**, böylece 10+ sn'lik monologlarda transkript gecikmesi birikmiyor. Ayrıca P75×1.2 ölçümüyle konuşmacının kişisel duraksama tarzına adaptasyon (bizim `recent_pauses[-3:]` yaklaşımına benzer ama yüzdelik tabanlı, daha stabil).

**Etki/efor:** Orta etki (uzun konuşmalarda ilk transkript görünme süresi), düşük efor (mevcut `adaptive_silence_seconds`'a bir katman).

### 1.4 Diğer ASR motorları (seçenek, mevcut yolu korumak kaydıyla)

- **Groq Whisper API** (wingman'da kullanımı var): OpenAI-uyumlu chat değil, **audio transcriptions** endpoint'i; 10 sn sesi ~200 ms'de döndürüyor. Zayıf donanımda "hızlı bulut modu" olabilir. Dikkat: ses makineden çıkar → kesinlikle opt-in ve gizlilik uyarılı. `OPENAI_BASE_URL`'ün SSRF için bilinçli kilitlendiğini unutma (buyedektir.py:1367-1426); Groq yolu ayrı, allowlist'li bir sağlayıcı olmalı.
- **SenseVoiceSmall** (FunASR; LiveTranslate `asr_sensevoice.py`): zh/ja/ko/en/yue için çok hızlı, duygu etiketi de üretiyor. faster-whisper'ın CJK kalitesinden şikayet durumunda alternatif "hızlı mod".
- **Moonshine** (moonshine-ai, 11k★): streaming için sıfırdan eğitilmiş; EN için large-v3'ten iyi iddiası. **Lisans tuzağı:** İngilizce dışı eski modeller non-commercial — yalnız MIT kapsamlı dillerde değerlendirilebilir.
- **SimulStreaming/AlignAtt** (ufal, 676★): LocalAgreement'tan ~5× hızlı, IWSLT 2025 SOTA. Ancak upstream whisper fork'u gerekiyor (faster-whisper değil), GPU odaklı — **uzun vadeli araştırma yönü**, bugün portlamak ağır.
- **BatchedInferencePipeline** (faster-whisper'da mevcut): dosya transkripsiyonunda (`transkribe.py`) büyük hız kazancı; ≤15 sn canlı utterance'ta kazanç sınırlı çünkü tek 30 sn pencere dolmuyor. Öncelik: transkribe aracı.

## 2. Konuşmacı ayrıştırma

**Mevcut durum:** pyannote 3.1, utterance başına batch çalışıyor (`diarize_executor`, 1 worker + 1-slot semaphore) — kayıt önce speakersız yayınlanıp sonra etiketleniyor; HF token + lazy-load var.

**Repodaki yaklaşım:**
- **diart** (`juanmc2005/diart`, 2k★; WLK `diarization/diart_backend.py`): `StreamingInference` ile 500 ms bloklarda **canlı** diarization; konuşmacılar cümle bitmeden etiketlenmeye başlar. Kısıt: Python 3.11–3.12 ve `numpy<2` gerekiyor (WLK README'si bunu açıkça not ediyor) — bizim `numpy>=1.21` tanımıyla çakışabilir, ekstra dikkat.
- **Streaming Sortformer** (NVIDIA NeMo; WLK `sortformer_backend.py`): 2025 SOTA, Python 3.13 uyumlu ama `nemo-toolkit` bağımlılığı ağır (~GB seviyesi).

**Öneri:** pyannote per-utterance yaklaşımı "geç ama doğru" olarak kalabilir; diart/Sortformer "canlı konuşmacı" istenirse değerlendirilecek yol. Mevcut yapıya en az riskli deneme: diart'ı `diarize_executor`'a paralel ikinci yol olarak eklemek. Öncelik orta — mevcut sistem çalışıyor.

## 3. Çeviri katmanı

**Mevcut durum:** DeepL / OpenAI / Anthropic / reseller — tamamı ücretli API + internet bağımlı; backlog guard ve force-bypass mevcut.

**Repodaki yaklaşım:** WLK `translation.py` + `nllw` paketi: **NLLB-200 distilled 600M'ı ctranslate2 ile yerel** çalıştırıyor — faster-whisper ile aynı inference çekirdeği, ek runtime yok. Sunucu genelinde tek model yükleniyor; oturum başına hedef dil `forced_bos_token_id`/`target_prefix` ile seçiliyor (kodda kilit/model-reload yok). 200 dil, internet yok, API maliyeti yok, kısa cümlede API round-trip'ten daha hızlı.

**Öneri:** "Çevrimdışı/ücretsiz çeviri" sağlayıcısı olarak `nllw` (veya doğrudan ctranslate2 NLLB) — ayarlarda 4. sağlayıcı. Kalite nüans olarak GPT'nin altında ama canlı altyazı için yeterli; DeepL/OpenAI anahtarsız kullanıcılara tüm çeviri akışını açar. Alternatif argos-translate (6.5k★) daha kolay kurulumlu ama birçok dil çiftinde NLLB'nin gerisinde.

**Etki/efor:** Yüksek etki (ürünün en pahalı dış bağımlılığına yerel alternatif), orta efor. Model ~600 MB indirme.

## 4. Gizlilik / Electron — tek satırlık kritik fark

**Bulgu:** `free-cluely/electron/WindowHelper.ts:102` → `mainWindow.setContentProtection(true)`. Windows'ta `WDA_EXCLUDEFROMCAPTURE` yapıyor: **pencere ekran paylaşımında/kaydında görünmez oluyor.**

**Bizdeki durum:** `main.js`'te overlay (`createOverlayWindow`, ~l.365) `alwaysOnTop`, `transparent`, `skipTaskbar`, `setIgnoreMouseEvents` kullanıyor ama `setContentProtection` yok. Kullanıcı Zoom/Meet/Discord'da ekran paylaşınca AI cevap önerileri taşıyan overlay karşı tarafa görünür — bu uygulamanın tam kullanım senaryosunda gizlilik açığı.

**Öneri:** Overlay'e `setContentProtection(true)` (+ tray'den geçiş anahtarı; bazı kullanıcılar overlay'i paylaşımda göstermek isteyebilir). Main pencere için opsiyonel. 1-2 satır, testi kolay (screen capture ile görünmezlik doğrulanır). **En yüksek etki/efor oranı.**

## 5. TTS — okunuşu seslendirme

**Mevcut durum:** `index.html`'de `window.speechSynthesis` + `speechSynthesis.getVoices()` (l.5538+). Windows ses paketi kurulu değilse ja/ko/zh/ar gibi diller için robotik/boş ses riski var; kurulum kullanıcıya kalmış.

**Repodaki yaklaşım:**
- **edge-tts** (rany2, 12k★): Microsoft Edge'in neural TTS servisi, 100+ dilde doğal ses, ücretsiz, `pip install edge-tts` → mp3/akış üretimi. İnternet gerektirir ama AI cevap yolu zaten internete bağımlı.
- **Whispering Tiger TTS katmanı:** Silero TTS, Kokoro (82M, MIT'e yakın, akışlı çalma) ve voice-cloning modelleri — yerel alternatif ailesi.

**Öneri:** Okunuş seslendirmesine edge-tts backend'i (hedef dilin doğal sesiyle okutma) ve "öneriyi otomatik seslendir" modu — eller serbest akış. Whisper Pro'nun imza işlevi (okunuşu sesli okuyup konuşma) için ses kalitesi doğrudan ürün değeri. edge-tts CJK/Arapça için Windows paket kurmadan doğal ses verir.

## 6. Okunuş (pronunciation) sağlamlığı — deterministik doğrulama

**Mevcut durum:** Okunuş LLM'den geliyor; `_normalize_turkish_pronunciation(text, lang)` regex/uralama temizliği yapıyor. Halüsinasyon riski: model fonetikte sapıtırsa yakalayan mekanizma yok (dil bilgisi doğru ama okunuş yanlış olabilir).

**Repodaki yaklaşım (kütüphaneler):**
- `pykakasi`/`cutlet` → Japonca romaji (cutlet `use_foreign_spelling` dahil hepburn varyantları)
- `python-pinyin` (mozillazg, 5.4k★) → Çince pinyin + ton işaretleri
- `osori/korean-romanizer` → Korece romanizasyon
- `epitran` (838★) → 100+ dil için IPA; `uroman` → evrensel romanizasyon

**Öneri (kademeli):**
1. **Prompt'a referans ipucu:** hedef dildeki cevabın canonical romanizasyonunu üretip prompt'a ekle → model okunuşu ondan türetsin (halüsinasyonu azaltır).
2. **Post-check:** LLM okunuşu ile canonical romanizasyonun kaba dif'ini al; belirgin sapmada logla/uyarı ver → `test_cevap_onerisi.py`'ye ek kalite kontrolü.
3. (opsiyonel) `_gen_phrases.py` hızlı kalıplarına romanizasyon tabanlı çift-kaynak doğrulama.

Dikkat: canonical romaji ≠ Türkçe okunuş (örn. romaji "shi" → okunuş "şi"); köprü eşleme tablosu gerekir — mevcut `PRONUNCIATION_GUIDES` kuralları zaten bu mantıkta.

## 7. Ses iyileştirme (denoise)

**Repodaki yaklaşım:** Whispering Tiger `Models/STS/AudioEnhancer.py`: DeepFilterNet / spectral gating ile STT öncesi gürültü bastırma; `IncrementalAudioEnhancer` büyüyen tamponu **tamamını değil yalnız kuyruğunu** işleyip seam'de crossfade yapıyor — bizim PARTIAL_SNAPSHOT_S ile çözdüğümüz O(n²) sorununun aynısını denoise tarafında çözüyorlar.

**Öneri:** Oyun/çağrı gürültüsünde transcription kalitesi düşüyorsa capture yoluna (VAD öncesi) DeepFilterNet-3 onnx aşaması. Efor orta-yüksek; gerçek kazanç donanımda ölçülmeli. Öncelik düşük-orta — önce Silero VAD ve LA.

## 8. Küçük/kenar bulgular

- **OCR oyun metni** (Whispering Tiger): oyun sesi yakalanamadığında ekrandaki diyalog metnini EasyOCR ile çeviriyor — Game Mode'a uzun vadeli eklenti fikri (ağır bağımlılık).
- **Diff protokolü** (WLK `diff_protocol.py`): frontend'e tam metin yerine delta gönderme — bizdeki payload küçük, kazanç sınırlı.
- **WtP cümle tokenizer** (WLK): buffer'ı cümle sınırında kesiyor (`chunk_completed_sentence`); bizim `_find_quiet_split_index` enerji tabanlı. Sessizlik bulunamadığında cümle sınırı ikinci kriter olabilir.
- **wtpsplit** bağımsız olarak da metin segmentasyonunda kullanılabilir.
- **free-cluely pencere trikleri:** `setVisibleOnAllWorkspaces`, kısayolla taşıma/gizleme — overlay UX'ine eklenebilir.
- **Groq/LLM sağlayıcı çeşitliliği:** cevap önerisi için Groq (OpenAI-uyumlu, TTFT çok düşük) üçüncü sağlayıcı olabilir; allowlist'li base_url politikasına dikkat.

## Öncelik sırası (öneri)

| # | Madde | Etki | Efor | Risk |
|---|---|---|---|---|
| 1 | Overlay `setContentProtection` | Yüksek (gizlilik) | Çok düşük | Yok denecek |
| 2 | LocalAgreement kararlı kısmi metin | Yüksek | Orta | word_timestamps maliyeti |
| 3 | NLLB yerel çeviri sağlayıcısı | Yüksek | Orta | ~600MB model, kalite farkı |
| 4 | Silero VAD segmentasyon | Orta-yüksek | Düşük-orta | Eşik kalibrasyonu |
| 5 | edge-tts + otomatik seslendirme | Orta-yüksek | Orta | İnternet bağımlılığı |
| 6 | Progressif sessizlik katmanı | Orta | Düşük | Adaptasyon gerilemesi → mevcut adaptif mantıkla harmanla |
| 7 | Canonical romanizasyon doğrulaması | Orta | Orta | Dil başına köprü tablosu |
| 8 | diart canlı diarization | Orta | Orta-yüksek | numpy<2 / py≤3.12 kısıtı |
| 9 | DeepFilterNet denoise | Orta | Orta-yüksek | Gerçek kazanç donanıma bağlı |
| 10 | BatchedInferencePipeline (transkribe.py) | Orta | Düşük | Yalnız dosya modu |
| 11 | Groq hızlı bulut STT (opt-in) | Orta | Orta | Gizlilik — ses dışarı çıkar |
| 12 | SimulStreaming/AlignAtt | Yüksek ama uzak | Çok yüksek | whisper fork + GPU |
| 13 | SenseVoice / Moonshine alternatif ASR | Orta | Orta | Lisans (moonshine non-EN), ek dep |
| 14 | OCR oyun metni | Düşük-orta | Yüksek | Ağır bağımlılık |

## Notlar ve sınırlar

- Bu turda hiçbir repo yerel diske klonlanmadı; inceleme `raw.githubusercontent.com`/`api.github.com` üzerinden okuma ile yapıldı.
- WhisperLiveKit'in LocalAgreement portu `faster-whisper` backend'iyle çalışıyor — doğrudan bağımlılık (`pip install whisperlivekit`) yerine ilgili sınıfların anlaşılıp bizim `_partial`/`_transcribe` yoluna uyarlanması daha sürdürülebilir (bizim pipeline'ın `_model_lock`, `_session_id`, queue semantiği farklı).
- diart ve WLK notlarındaki `numpy<2` + `Python≤3.12` kısıtı mevcut `numpy>=1.21` tanımıyla doğrulanmalı.
- Moonshine non-İngilizce modelleri ticari lisans gerektiriyor; listeye almadan önce LICENSE kontrolü şart.
- `setContentProtection` Windows'ta ekran paylaşımını engeller ama üçüncü parti yakalama yazılımları (harici kart, HDMI) etkilenmez; beklenti notuna yazılmalı.
