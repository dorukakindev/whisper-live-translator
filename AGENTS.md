# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Yeni oturumda önce oku

- Konuşma geçmişinin mevcut olduğunu varsayma. Önce bu dosyayı, [BAŞLANGIÇ rehberini](BASLANGIC.md), ardından [devir indeksindeki](DEVIR-NOTU.md) güncel notu oku. Güncel not önceki bir soruna atıf yapıyorsa ilgili eski notu da oku.
- Kullanıcı gerekli geliştirme araçlarını, bağımlılıkları ve modelleri indirmeye/kurmaya izin verdi. İş için gereken kurulumu tekrar izin istemeden yap; proje için `.venv` ve `npm ci` kullan, resmi kaynakları tercih et. Ücretli satın alma, hesap girişi, diski silme/format veya başka projelerin verilerini değiştirme bu izne dahil değildir. Kullanıcı girişini/anahtarını tahmin etme veya notlara yazma.
- Başlangıçta `git status --short`, dal, HEAD ve origin adresini kontrol et. Kullanıcının mevcut değişikliklerini silme veya kendi değişikliklerinmiş gibi commit etme. Çalışma ağacı kirliyse dosyaların kapsamını incele; yalnız kendi çalışmanı sahnele.
- Her tamamlanan düzeltme/geliştirme grubu için uygun testleri çalıştır, kod commit'i oluştur, tarihli devir ve kök indeksi güncelle, belge commit'i oluştur ve push et. Sadece plan veya “yapabilirim” yanıtında kalma. Ayrıntılı yayın sırası aşağıda ve BASLANGIC.md içindedir.
- Format sonrası eski mutlak kullanıcı yollarını, `.venv` ortamını, oturum açmayı ve kurulu programları geçerli sayma. Gerçek makineyi incele. Önceki notlardaki sürümler çalışan bir kurulum garantisi değildir.

## Windows birincil ortam (kullanıcı kuralı)

Projenin asıl kullanım ortamı Windows'tur (`D:\Whisper Local`). Ubuntu'da geliştirme ve Electron testi serbest; fakat:

- **Her PR'da Windows etkisi ayrıca değerlendirilir:** `install.bat` / `start.bat` akışı (repo tarafındaki karşılığı kök `başlat.bat` + `diger-baslaticilar/`), Windows yolları, PowerShell/cmd davranışı, dosya seçici (file picker), UTF-8/Türkçe karakterler ve varsa GPU/CUDA bağımlılıkları kontrol edilir.
- Normal Windows açılışı `start.bat` (repo'da `başlat.bat`) üzerindendir; yalnız `npm start` testi bunu doğrulamaz.
- Yalnızca değişen alanlara yönelik testler çalıştırılır; görev başına gereksiz yere tam test paketi koşulmaz. Windows CI sonucu beklenir.
- Ubuntu Electron testi; gerçek Windows arayüzü, DPI, GPU, DRM veya kullanıcı-hesabı doğrulaması yerine geçmez. Doğrulanamayan sınırlar PR açıklamasında açıkça yazılır.
- Güncel `master` (bu repo'da `main`) üzerinden ayrı dal + PR açılır; kendi PR'ı merge edilmez — kullanıcı inceleyip Windows makineye taşır.
- Değişen dosyalar, test sonuçları, Windows'a özgü riskler ve doğrulanmamış sınırlar devir notuna yazılır.
- Gerçek profil, API anahtarı ve kişisel veriler testlerde veya commit'lerde kullanılmaz.

## What this is

Whisper Pro is a Windows desktop app for **live, real-time conversation across languages**. It captures system audio (or a microphone), transcribes the other party's speech with faster-whisper, and generates AI reply suggestions. The defining workflow: the user reads the **Turkish phonetic spelling** (`romanized`/`okunuş`) of a suggested reply aloud to speak back in a language they don't know (Japanese, Arabic, Chinese, Russian, Spanish, etc.). Optimize for that read-aloud use — pronunciations must be effortless to read and replies must sound natural to a native speaker.

The codebase and all code comments are in **Turkish**. Match that when editing; keep comment density and idiom consistent with surrounding code.

## Running & building

- **Dev (full app):** `npm start` — Electron (`main.js`) spawns the Flask backend (`buyedektir.py`) on port 5000 and loads the UI. `başlat.bat` is a double-click wrapper for this.
- Kullanıcının normal başlatıcısı proje kökündeki `başlat.bat` dosyasıdır. Diğer BAT araçları `diger-baslaticilar/` altında tutulur; köke ek alternatif başlatıcı koyma.
- **Backend only (no Electron):** `python buyedektir.py` (or `diger-baslaticilar\calistir.bat`) → serves http://localhost:5000. Override with `HOST` / `PORT` env vars (defaults `127.0.0.1:5000`, local-only). This is the fastest way to iterate on backend/frontend.
- **Build portable exe:** `npm run build` → `dist/Whisper-Pro-win32-x64/Whisper-Pro.exe`. The `dist/` tree is a full copy of the app — rebuild after backend/frontend changes; it does NOT auto-update.
- `main.js` prefers a project-local venv (`.venv/`/`venv/`) python, then `python`/`python3`/`py` on PATH; it kills orphaned python holding port 5000 and restarts the backend on crash (capped).

`transkribe.py` is a **standalone** tkinter GUI for transcribing audio/video files — unrelated to the live app, shares no code. Run with `python transkribe.py`.

## Testing & validation

There is no test framework. Validate changes with:

- `python -m py_compile buyedektir.py` and `python -m pyflakes buyedektir.py` (keep pyflakes clean).
- `python test_smoke.py` — permanent regression suite (no pytest dependency; exit 0 = pass). Covers the 15-language pronunciation table, the multilingual hallucination filter, the answer-mode contract (parallel calls + `ai_options_partial` streaming + dedup), settings bounds, and the JSON salvage parser. Run after any change to normalization, prompts, or the answer endpoint.
- Frontend JS has no build step. Validate by extracting inline `<script>` blocks from `templates/index.html` and running `node --check` on them.
- Backend route/socket logic can be exercised with Flask's `app.test_client()` and `socketio.test_client(app)` (used previously to verify the parallel-answer and partial-emit paths).
- `test_cevap_onerisi.py` is an ad-hoc script that rebuilds the answer-mode prompt from `buyedektir.py` and calls the live API to eyeball pronunciation quality (it reads an API key from a local file). Not a unit test.
- Full smoke test: start the backend (`PORT=509x python buyedektir.py`), confirm `GET /` → 200 and the `/api/*` endpoints respond. Backend startup is slow (~40-50s) due to torch/faster-whisper imports.

## Architecture

**Backend (`buyedektir.py`, ~3000 lines, Flask + SocketIO in `threading` async mode).** One module-global `transcriber` (`WhisperWebTranscriber`) and `mic_recorder` hold all state. Real-time pipeline:

- **Capture thread** (`_capture_audio`) reads native-rate audio, downmixes to mono, resamples to 16 kHz via a cached FIR filter (`_resample_int16`), runs WebRTC VAD to segment on silence, and pushes utterances to `audio_queue` (maxsize 5; drops oldest under load and emits `transcription_lagging`).
- **Transcribe thread** (`_transcribe_audio`) pulls from the queue, runs faster-whisper, filters hallucinations (`_is_likely_hallucination`, multilingual), corrects the detected language by script (`_detect_script_lang`), and emits `new_transcription`.
- **Offloaded work:** translation (`translate_executor`) and speaker diarization (`diarize_executor`, runs in parallel with Whisper) are separate single-worker `ThreadPoolExecutor`s so they never block transcription. A monotonic `_session_id` guards every thread so a stale worker from a previous start/stop can't leak into a new session. Incoming-transcript translation also has a backlog guard: a translation more than `TRANSLATE_MAX_LAG` transcripts behind the latest is skipped (keeps live translations current instead of falling indefinitely behind).
- **Live partial transcription** (`_transcribe_partial`, `_partial_executor`, toggle `partial_enabled` via `/api/partial_toggle`): while speech accumulates, a snapshot of the growing buffer is transcribed every `PARTIAL_INTERVAL`s and emitted as `partial_transcription` for a live on-screen preview — before the 2 s silence segment finalizes. It NEVER touches the final path (no transcriptions list/file/AI/translation). A `_model_lock` serializes all `current_model.transcribe(...)` calls (partial + final + mic + warmup) since they share one `WhisperModel`; partials skip when a final is queued (`audio_queue` non-empty) so the final is never starved. Frontend shows a greyed preview item that `new_transcription` replaces (with a 6 s hide-timer fallback).
- Model load (`load_model`) tries CUDA (float16) then falls back to CPU (int8), scales `cpu_threads` to the machine, and warms the model in a background thread so the first real utterance doesn't pay CUDA/alloc startup.

**AI reply suggestions (`/api/generate_ai_response`).** Modes: `answer` (reply options), `translate`, `translate_dual`. Key design points:

- **Answer mode runs TWO parallel provider calls (Anthropic or OpenAI)** (via `_ai_executor`) that split the 4 suggestions by style (2 + 2, see `style_splits`) — latency is dominated by output tokens, so halving per-call output roughly halves wait. Results are merged and deduplicated (`_extract_answer_options` / `_parse_answer_options`); if one call fails the other's options still show. `_salvage_answer_options` recovers truncated JSON.
- **Streaming:** if the UI sends a `request_id`, each parallel call emits its options via the `ai_options_partial` socket event the moment it finishes, so suggestions appear before the HTTP response (which returns the merged, deduped, canonical list).
- **Prompt structure:** static rule blocks (pronunciation guides, tone/quality rules) go FIRST, variable content (context + the message) LAST, to preserve provider prompt caching. Don't reorder casually.

**Pronunciation system.** `PRONUNCIATION_GUIDES` holds per-language romanization rules; `_build_pronunciation_guide(lang)` injects ONLY the target language's guide (irrelevant languages degrade quality). `_normalize_turkish_pronunciation(text, lang)` post-processes model output into readable Turkish per language — note Japanese intentionally keeps hyphens (`kore-va`, `suki-des-ka`) while all other languages strip them. `_finalize_pronunciation` is the shared final cleanup.

**Frontend (`templates/index.html` + `static/*.js`, vanilla JS + socket.io).** The main application flow remains inline; Cockpit, reading mode, and quick phrases live in classic global scripts (`static/cockpit.js`, `static/reading-mode.js`, `static/quick-phrases.js`) loaded after the inline block. `renderAiResult` is shared by both the final HTTP response and partial socket events (`partial` flag). Transcript text is kept in a `transcriptionTexts` map keyed by id; the DOM is pruned to `MAX_DOM_ITEMS` and the map is cleaned in lockstep. `window._pendingAiRequests` tracks in-flight answer requests for the streaming path. Always escape interpolated user/AI data with `escapeHtml`/`escapeJsString`.

- **Quick phrases (`⚡ Hızlı Kalıplar`):** `static/quick-phrases.js` holds the `QUICK_PHRASES` object with ~10 ready common phrases per target language (ja/en/es/de/fr/it/pt/ru/ko/zh/ar), each `{tr, t (native, for TTS), o (okunuş)}`, rendered by `renderQuickPhrases()` for the current `aiTargetLang`. The okunuş values are NOT hand-written — they're generated by `_gen_phrases.py` (standalone, imports `buyedektir`) which runs each phrase's phonetic/native form through `_normalize_turkish_pronunciation` so they stay consistent with the rest of the app. To add/edit phrases, edit `_gen_phrases.py`, re-run it, and paste the output into `static/quick-phrases.js`.

## Configuration & gotchas

- **Restart the backend after editing `index.html` or `buyedektir.py`.** Flask/Jinja caches the rendered template, so editing `templates/index.html` and just reloading the page serves the OLD HTML — restart the Python process (`başlat.bat` / `npm start`, or `python buyedektir.py`). For the portable `dist/` exe, run `npm run build` (dist is a full copy). This is the #1 source of "my change didn't take effect" confusion.
- **AI providers:** reply/pronunciation generation can use official Anthropic (`ANTHROPIC_API_KEY`, `https://api.anthropic.com/v1/messages`) or official OpenAI (`OPENAI_API_KEY`, Chat Completions). Provider keys, response models, translation models, and translation keys remain separate. Claude is listed first in the UI; an existing OpenAI configuration is preserved. Keys are verified without blocking startup.
- **Secret hygiene:** API keys and tokens belong only in the ignored `.env`; never keep them in notes, transcripts, test fixtures, or other plaintext repository files. `npm run scan` checks the source tree before packaging, but any exposed key must still be revoked and rotated at its provider.
- **Legacy env vars:** `.env` may still carry `MINIMAX_*` keys from an older provider — **the current code ignores them**. Don't wire them back in without intent.
- **`HF_TOKEN`** enables pyannote speaker diarization, which is **lazy-loaded** (only when diarization is turned on, not at startup) to keep launch fast.
- **DeepL** translation is optional (`DeepLTranslator`); Anthropic, OpenAI, and reseller translation keys live separately on the responder. `translate(..., force=True)` bypasses the live-transcription translation toggle for user-initiated (PTT) translations.
- `buyedektir.py` uses **LF line endings** — preserve them when editing on Windows.
- Transcripts append to `transcriptions.txt` (auto-rotates at 5 MB); speaker profiles persist as `speaker_profiles.json` (JSON, not pickle — avoids deserialization risk).

## Devir notu ve yayınlama

- Bu projedeki her çalışma için `docs/devir/YYYY-MM-DD-HHMM.md` oluştur (Europe/Istanbul). Aynı dakika için dosya varsa üzerine yazma; benzersiz bir sonraki dakika adı kullan.
- Önceki devir notlarını koru. Kökteki `DEVIR-NOTU.md` güncel nota bağlantı veren bir indeks olsun; önceki bağlantıları da koru.
- Notta repo, dal, başlangıç ve bitiş **kod** commit kimlikleri; değişen dosyalar ve amaçları; hata/kök neden/kanıt; özelliklerin kullanımı; test komutları ve sonuçları; çalıştırılmayan kontroller; bağımlılık, kurulum, ayar/şema değişiklikleri; bilinen sorunlar, yarım işler ve sonraki adımlar yer alsın.
- Commit/push yapılmamış değişiklikleri açıkça belirt. API anahtarı, token değeri, şifre, kişisel veri ve ham özel kayıtları notlara koyma. Kanıtlanmamış işleri tamamlandı sayma.
- Kod değişikliklerini önce commit ederek bitiş kod kimliğini kesinleştir; devir notunu, indeksi ve gerekli yönergeleri ayrı bir belge commit'ine al. Böylece notun kendi commit kimliğini içine yazma döngüsü oluşmaz.
- Kullanıcının bu proje için talebi doğrultusunda notları ilgili GitHub deposunun kök indeksiyle birlikte commit et ve push et. Uzak dal ile yerel HEAD kimliğini doğrula; push başarılı olmadan “GitHub'a yüklendi” deme. Push engellenirse gerçek hatayı ve gönderilmemiş commitleri belirt; force push yapma.
- Son yanıtta repo bağlantısını, tarihli notun doğrudan GitHub bağlantısını ve push edilen son commit kimliğini ver.
