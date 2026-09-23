"use strict";

// Arayüz çevirisi merkezi tutulur. Transkript, çeviri, okunuş ve kullanıcının
// kaydettiği cümleler ürün içeriğidir; bu katman onları değiştirmez.
(() => {
    const STORAGE_KEY = 'whisperUiLanguage';
    const DEFAULT_LANGUAGE = 'en';
    const supported = new Set(['en', 'tr']);

    const EN = Object.freeze({
        'Whisper Transkripsiyon + Çeviri Pro': 'Whisper Transcription + Translation Pro',
        'Canlı görüşme asistanı': 'Live conversation assistant',
        'Canlı çeviri ve konuşma asistanı': 'Live translation and conversation assistant',
        'Oyun modu': 'Game Mode',
        'Oyun modu açık': 'Game Mode on',
        'Bağlanıyor': 'Connecting',
        'Bağlı': 'Connected',
        'Bağlantı yok': 'Disconnected',
        'Ayarlar': 'Settings',
        'Beklet': 'Pause',
        'Devam Et': 'Resume',
        'Şimdi Gönder': 'Send now',
        'Aydınlık': 'Light',
        'Karanlık': 'Dark',
        'Kapat': 'Close',
        'Arayüz': 'Interface', 'Arayüz dili': 'Interface language',
        'AI önerileri kapalı — OpenAI anahtarı geçersiz.': 'AI suggestions are off — the OpenAI key is invalid.',
        'Senin dilin': 'Your language',
        'Türkçe': 'Turkish',
        'Karşı taraf': 'Other party',
        '— seç —': '— select —',
        '🌐 Otomatik Algıla': '🌐 Detect automatically',
        '🌐 Dil Algıla': '🌐 Detect language',
        '🌐 Otomatik Algıla (karşının diliyle yanıtla)': '🌐 Detect automatically (reply in the other party’s language)',
        '🇯🇵 Japonca': '🇯🇵 Japanese', '🇬🇧 İngilizce': '🇬🇧 English',
        '🇩🇪 Almanca': '🇩🇪 German', '🇨🇳 Çince': '🇨🇳 Chinese',
        '🇸🇦 Arapça': '🇸🇦 Arabic', '🇫🇷 Fransızca': '🇫🇷 French',
        '🇪🇸 İspanyolca': '🇪🇸 Spanish', '🇷🇺 Rusça': '🇷🇺 Russian',
        '🇰🇷 Korece': '🇰🇷 Korean', '🇵🇹 Portekizce': '🇵🇹 Portuguese',
        '🇩🇰 Danca': '🇩🇰 Danish', '🇸🇪 İsveççe': '🇸🇪 Swedish',
        '🇫🇮 Fince': '🇫🇮 Finnish', '🇬🇷 Yunanca': '🇬🇷 Greek',
        '🇬🇪 Gürcüce': '🇬🇪 Georgian', '🇸🇰 Slovakça': '🇸🇰 Slovak',
        '🇦🇿 Azerice': '🇦🇿 Azerbaijani', '🇮🇹 İtalyanca': '🇮🇹 Italian',
        'Başlat': 'Start', 'Durdur': 'Stop', 'AKIŞ': 'FLOW', 'Hazır': 'Ready',
        'BAĞLANTI': 'CONNECTION', 'HEDEF DİL': 'TARGET LANGUAGE', 'Otomatik': 'Automatic',
        'KAYIT': 'CAPTURE', 'Kapalı': 'Off', 'Açık': 'On', 'GECİKME': 'LATENCY',
        'Ölçülüyor': 'Measuring', 'Henüz gecikme ölçümü yok.': 'No latency measurements yet.',
        'Görüşmeye hazırlık': 'Conversation readiness', 'Durumu kontrol et': 'Check status',
        'Model · Kontrol edilmedi': 'Model · Not checked', 'Ses · Cihaz seç': 'Audio · Select a device',
        'AI · Kontrol edilmedi': 'AI · Not checked', 'Yeniden kontrol et': 'Check again',
        'Sesi 3 saniye test et': 'Test audio for 3 seconds',
        'Seçili cihazı test et; sistem sesi için karşı taraftan ses çal.': 'Test the selected device; play remote audio when testing system capture.',
        'Konuşmaya göre bekleme süresi': 'Adaptive silence timing',
        'Önceki 3 cümleyi çeviride kullan': 'Use the previous 3 sentences for translation',
        'Kontrol için aç.': 'Expand to review.', 'ÇALIŞMA ALANI': 'WORKSPACE',
        'Ses ve dil ayarları': 'Audio and language settings', 'Bağlam Taşıma': 'Context carry-over',
        'Son 10 konuşma bağlam olarak kullanılır ve transkripsiyon doğruluğu artırılır': 'Uses the last 10 utterances as context to improve transcription accuracy',
        'Bağlam Hafızası:': 'Context memory:', '/ 10 kayıt': '/ 10 records',
        'Hızlı Kurulum — Karşı Tarafın Dili': 'Quick setup — Other party’s language',
        'Tek seçimle hem giriş dilini (Whisper) hem cevap önerisi dilini ayarlar. Senin dilin her zaman Türkçe kabul edilir. İnce ayar istersen aşağıdaki bölümleri tek tek de değiştirebilirsin.': 'One selection sets both the Whisper input language and the reply language. Your language is always treated as Turkish. You can still fine-tune the sections below.',
        'Karşı tarafın dilini üstteki görüşme şeridinden seçebilirsiniz.': 'Choose the other party’s language from the conversation bar above.',
        'Bunu ayarlayınca': 'Changing this updates', 'Giriş Dili': 'Input Language',
        've': 'and', 'Cevap Önerisi Dili': 'Reply Language',
        'otomatik güncellenir. Türkçe senin dilin olarak sabittir.': 'automatically. Turkish remains fixed as your language.',
        "1. Giriş Dili (PC'den gelen ses)": '1. Input Language (audio from the PC)',
        "PC'den alınan sesin dili. Whisper bunu yazıya döker ve otomatik çevirinin kaynağı da budur.": 'The language of the captured PC audio. Whisper transcribes it and uses it as the source for automatic translation.',
        'Konuşmacı Tanıma (Pyannote)': 'Speaker Diarization (Pyannote)',
        'Farklı konuşmacıları otomatik olarak tanımlar ve ayırt eder': 'Automatically detects and separates different speakers',
        'Konuşmacı Tanıma:': 'Speaker diarization:', '🤗 Hugging Face Token (Zorunlu)': '🤗 Hugging Face token (required)',
        '🔑 Token almak için tıklayın (Ücretsiz)': '🔑 Click to get a token (free)',
        'Not: Token girdikten sonra': 'Note: After entering the token,', 'buradan': 'accept',
        'kullanım şartlarını kabul edin': 'the usage terms here', 'Algılanan Konuşmacılar:': 'Detected speakers:',
        'Henüz konuşmacı algılanmadı': 'No speakers detected yet', 'Konuşmacıları Sıfırla': 'Reset speakers',
        '2. Çevrilecek Dil': '2. Translation Language',
        "Yapay zekâ her transkripti bu dile otomatik çevirir. Kaynak dil otomatik olarak 1. Giriş Dili'dir.": 'AI automatically translates each transcript into this language. The source is the Input Language above.',
        'Çeviri Servisi:': 'Translation service:', 'OpenAI (Resmi)': 'OpenAI (Official)',
        'Reseller ve resmi OpenAI anahtarları ayrı tutulur. Resmi seçenekte api.openai.com anahtarınızı girin.': 'Reseller and official OpenAI keys are stored separately. Enter your api.openai.com key for the official option.',
        'Şu dile çevir (kaynak: 1. Giriş Dili):': 'Translate into (source: Input Language):',
        '🔑 DeepL Free API Key almak için tıklayın': '🔑 Click to get a DeepL Free API key',
        'Çeviri servisi hazır değil': 'Translation service is not ready',
        'AI Cevap Önerisi': 'AI Reply Suggestions',
        'Sorulara otomatik cevap önerisi (Türkçe + Japonca + Romaji)': 'Automatic reply suggestions with Turkish meaning and pronunciation',
        'AI Önerileri Aktif': 'AI suggestions enabled', '🌐 Otomatik Çeviri': '🌐 Automatic translation',
        '💬 Otomatik Cevap Önerisi': '💬 Automatic reply suggestions',
        'Her yeni mesajda önerileri beklemeden üret (mesaj başına 2 AI çağrısı)': 'Generate suggestions for every new message without waiting (2 AI calls per message)',
        '💸 Ucuz Mod': '💸 Economy mode',
        'Tüm AI’da minimal reasoning — token tasarrufu (kalite hafif düşebilir)': 'Use minimal reasoning for all AI calls to save tokens (quality may decrease slightly)',
        '📊 Bu oturum:': '📊 This session:', 'token': 'tokens', 'Çeviri Dili': 'Translation Language',
        'Çeviri Sonucu:': 'Translation result:', '3. Cevap Önerisi Dili': '3. Reply Language',
        '"Soru-Cevap"ta AI bu dilde öneri verir; altında Türkçe karşılığı ve okunuşu da gösterilir.': 'AI suggests replies in this language and shows the Turkish meaning and pronunciation below.',
        '4. Cevap Önerisi Tonu': '4. Reply Tone',
        '😊 Arkadaşça (Samimi ve rahat)': '😊 Friendly (warm and relaxed)',
        '💬 Günlük (Doğal konuşma dili)': '💬 Casual (natural everyday speech)',
        '👔 Resmi (Kibar, nazik ve mesafeli)': '👔 Formal (polite and reserved)',
        'AI cevap önerileri üretirken bu konuşma üslubunu ve tonunu kullanır.': 'AI uses this style and tone when generating reply suggestions.',
        'Kalıp Cevaplar': 'Saved Replies',
        'Cevap önerilerinde ⭐ ile kaydettiğin hazır cümleler. AI beklemeden anında okunuşuyla kullan.': 'Replies saved with ⭐. Open them with pronunciation immediately without waiting for AI.',
        'Henüz kalıp yok. Cevap önerilerinin yanındaki ⭐ butonuyla sık kullandığın cümleleri buraya kaydet.': 'No saved replies yet. Use ⭐ beside a suggestion to save frequently used sentences here.',
        'Terim Sözlüğü': 'Term Glossary',
        'Özel adları yazıya dökümde tanıtır; çeviri karşılığını ve okunuşu AI cevaplarında korur.': 'Helps transcription recognize names and preserves preferred translations and pronunciations in AI replies.',
        'Her satır: kaynak | tercih edilen çeviri | Türkçe okunuş | hedef dil. Yalnız kaynak alanı zorunlu; en fazla 100 satır.': 'Each line: source | preferred translation | Turkish pronunciation | target language. Only source is required; maximum 100 lines.',
        'Sözlüğü Kaydet': 'Save glossary', 'Model Seçimi': 'Model Selection',
        'Daha büyük model = Daha iyi doğruluk ama daha yavaş': 'Larger model = better accuracy but slower',
        'Çok Hızlı': 'Very fast', 'Hızlı': 'Fast', 'Dengeli': 'Balanced', 'İyi': 'Good',
        'En İyi': 'Best', 'Hızlı+İyi': 'Fast + accurate', 'Model indiriliyor...': 'Downloading model...',
        'CPU kullan (GPU yoğunken / oyun oynarken önerilir)': 'Use CPU (recommended while the GPU is busy or gaming)',
        'Model Yükle': 'Load model', 'Model seçin ve yükleyin': 'Select and load a model',
        'Yakalama Modu:': 'Capture mode:', '🖥️ Karşı tarafı dinle (sistem sesi)': '🖥️ Listen to the other party (system audio)',
        '🎤 Kendi sesim (mikrofon dikte)': '🎤 My voice (microphone dictation)',
        'Karşı tarafın sesini yakalar; AI cevap önerileri bu mod için çalışır.': 'Captures the other party; AI reply suggestions work in this mode.',
        'Ses Kaynağı:': 'Audio source:', 'Yenile': 'Refresh', 'Yükleniyor...': 'Loading...',
        'Bas-Konuş (Alt) Mikrofonu:': 'Push-to-talk (Alt) microphone:',
        'Sistem ve AI Ayarları': 'System and AI Settings',
        'AI Sağlayıcısı': 'AI provider', 'Anthropic API Key': 'Anthropic API key', 'Resmi OpenAI API Key': 'Official OpenAI API Key',
        'AI Çeviri Modeli': 'AI Translation Model', 'AI Cevap & Okunuş Modeli': 'AI Reply & Pronunciation Model',
        'API ve Model Ayarlarını Kaydet': 'Save API and model settings', 'AI servisi hazır değil': 'AI service is not ready',
        'En Hızlı + En Tasarruflu': 'Fastest + most economical', 'Gelişmiş Akıl Yürütme (Mini)': 'Advanced reasoning (Mini)',
        'Akıl Yürütme (Mini)': 'Reasoning (Mini)', 'Yeni Nesil Akıl Yürütme (Mini)': 'Next-generation reasoning (Mini)',
        'Tasarruflu Mini': 'Economical Mini', 'Kararlı Mini': 'Stable Mini', 'Mini Kodlama': 'Mini coding',
        'Kodlama': 'Coding', 'En Yüksek Kalite': 'Highest quality', 'Yüksek Kalite': 'High quality',
        'Kararlı Büyük': 'Stable large', 'Standart Büyük': 'Standard large', 'Dengeli Standart': 'Balanced standard',
        'Eski Kararlı Büyük': 'Legacy stable large', 'En Gelişmiş Akıl Yürütme': 'Most advanced reasoning',
        'Akıl Yürütme': 'Reasoning', 'En Son Sohbet': 'Latest chat', 'Büyük Kodlama': 'Large coding',
        'Gelişmiş Kodlama': 'Advanced coding', 'Sessizlik Süresi (saniye)': 'Silence duration (seconds)',
        'VAD Hassasiyeti': 'VAD sensitivity', 'Canlı önizleme': 'Live preview',
        'Karşı taraf konuşurken metni anlık göster (yavaş donanımda kapatın)': 'Show text while the other party is speaking (disable on slow hardware)',
        'Temizle': 'Clear', 'Toplam Kayıt': 'Total records', 'Süre': 'Duration',
        'ASR p95': 'ASR p95', 'Çeviri p95': 'Translation p95', 'KARŞI TARAF': 'OTHER PARTY',
        'Konuşma akışı': 'Conversation', 'Sıfırla': 'Reset', 'İndirme biçimi': 'Download format',
        'İndir': 'Download', 'Geçmişte ayrıntılı ara': 'Search full history', 'Tarih filtresi': 'Date filter',
        'Konuşmacı filtresi': 'Speaker filter', 'Tüm geçmişte ara': 'Search all history',
        'Ses ölçümü bekleniyor': 'Waiting for audio measurement', 'Canlıya dön ↑': 'Return to live ↑',
        'İşlem aşamaları': 'Processing stages', 'Henüz işlem yok.': 'No processing yet.',
        'İlk konuşmayı bekliyoruz': 'Waiting for the first utterance',
        'Modeli ve ses kaynağını hazırlayıp üstten Başlat’a basın.': 'Prepare the model and audio source, then press Start above.',
        'Model seç ve yükle': 'Select and load a model', 'Ses cihazı seç': 'Select an audio device',
        'OpenAI anahtarını doğrula': 'Verify the OpenAI key', 'Başlat düğmesine bas': 'Press Start',
        'Konuşma hakkında sor': 'Ask about the conversation', 'Özet Al': 'Create summary', 'Sor': 'Ask',
        'AI Cevabı:': 'AI answer:', 'SENİN CEVABIN': 'YOUR REPLY', 'Ne söylemek istersin?': 'What would you like to say?',
        'Konuşmadan bir cümle seç. Cevabını Türkçe okunuşuyla seslendir.': 'Select a sentence from the conversation and speak your reply using the Turkish pronunciation guide.',
        'Öneri uzunluğu': 'Reply length', 'Kısa': 'Short', 'Normal': 'Normal', 'Detaylı': 'Detailed',
        'Kendi cevabını yaz veya söyle': 'Write or say your own reply', 'Türkçeden çevir': 'Translate from Turkish',
        'Söylemek istediğimi çevir': 'Translate what I want to say', 'Çevir ve okunuşu göster': 'Translate and show pronunciation',
        'Mikrofonla söyle': 'Speak with microphone', 'Bitir ve çevir': 'Finish and translate',
        'Türkçe yaz veya Alt tuşunu basılı tutarak konuş.': 'Write in Turkish or hold Alt to speak.',
        'Hızlı kalıplar': 'Quick phrases', 'Tekrar eder misin? · Daha yavaş lütfen': 'Repeat that · Please speak more slowly',
        'Cevabın burada hazırlanacak': 'Your reply will appear here',
        'Gelen konuşmada Cevap öner düğmesine bas.': 'Press Suggest reply on an incoming sentence.',
        'Yabancı dil bilmeden, okunuşu takip ederek yanıt ver.': 'Reply by following the pronunciation guide, even if you do not speak the language.',
        '1–4 ile okuma modunu aç · Esc ile kapat': 'Press 1–4 for Reading mode · Esc to close',
        'Metni düzelt': 'Edit text', 'Duyulan metin': 'Recognized text', 'Kaydet': 'Save', 'Vazgeç': 'Cancel',
        'Cevap öner': 'Suggest reply', 'Çevir': 'Translate', 'Kopyala': 'Copy', 'Büyüt': 'Enlarge',
        'Çeviriyi Kopyala': 'Copy translation', 'Cevabı Kopyala': 'Copy reply',
        'Cevaplar hazırlanıyor.': 'Preparing replies.', 'Henüz seçili bir konuşma yok.': 'No conversation selected yet.',
        'Kullanılabilir cevap alınamadı.': 'No usable reply was returned.', 'Böyle söyle': 'Say it like this',
        'Türkçe okunuş': 'Turkish pronunciation', 'Türkçe anlamı': 'Meaning in Turkish',
        'Okuma modu': 'Reading mode', 'Kalıplara kaydet': 'Save to phrases', 'Söyledim': 'Said',
        'Dinle': 'Listen', 'Yavaş dinle': 'Listen slowly', 'Sesi durdur': 'Stop audio',
        'Okunuş sorunlu': 'Pronunciation issue', 'Sorunlu': 'Report issue',
        '1–4 ile seçenek değiştir · Esc ile kapat': 'Press 1–4 to change option · Esc to close',
        'Bu cevap dili için hazır kalıp yok. Mevcut: Japonca, İngilizce, İspanyolca, Almanca, Fransızca, İtalyanca, Portekizce, Rusça, Korece, Çince, Arapça.': 'No quick phrases are available for this reply language. Available: Japanese, English, Spanish, German, French, Italian, Portuguese, Russian, Korean, Chinese, and Arabic.',
        '1–2000 karakter arasında Türkçe bir cümle yaz.': 'Write a Turkish sentence between 1 and 2,000 characters.',
        'Üst şeritten karşı tarafın dilini seç.': 'Choose the other party’s language from the top bar.',
        'Çeviri hazırlanıyor…': 'Preparing translation…', 'Çeviri alınamadı. Tekrar dene.': 'Translation failed. Try again.',
        'Okunuş alınamadı. Tekrar dene.': 'Pronunciation could not be generated. Try again.',
        'Çeviri hazır. Okunuşu seslendirebilirsin.': 'Translation is ready. You can read the pronunciation aloud.',
        'Seçim değiştiği için eski çeviri gösterilmedi. Yeniden çevirebilirsin.': 'The previous translation was hidden because the selection changed. You can translate again.',
        'Çeviri zaman aşımına uğradı. Tekrar dene.': 'Translation timed out. Try again.',
        'Çeviri alınamadı': 'Translation failed', 'Metnin korundu. Çevir düğmesiyle tekrar deneyebilirsin.': 'Your text was preserved. Use Translate to try again.',
        'Türkçe konuş. Bitir ve çevir düğmesine bas.': 'Speak Turkish, then press Finish and translate.',
        'Ses işleniyor; sonuç konuşma akışında da görünür.': 'Processing audio; the result will also appear in the conversation.',
        'Ses işlenemedi. Tekrar dene.': 'Audio could not be processed. Try again.',
        'Sesin çevrildi. Konuşma akışından okuma modunu açabilirsin.': 'Your speech was translated. You can open Reading mode from the conversation.',
        'Kontrol ediliyor…': 'Checking…', 'Durum alınamadı': 'Could not get status',
        'Kontrol başarısız': 'Check failed', 'Sunucuya ulaşılamadı. Yeniden kontrol et.': 'Could not reach the server. Check again.',
        'Doğrulandı': 'Verified', 'Anahtar ekle': 'Add key', 'Doğrulanıyor': 'Verifying',
        'Anahtarı düzelt': 'Fix key', 'Henüz doğrulanmadı': 'Not verified yet', 'Hizmete ulaşılamıyor': 'Service unavailable',
        'Yüklü': 'Loaded', 'Model · Seç ve yükle': 'Model · Select and load',
        'Çeviri sonucu': 'Translation result', 'Çeviri bekleniyor…': 'Waiting for translation…',
        'Çeviri alınamadı · ana pencerede tekrar dene': 'Translation failed · retry in the main window',
        'Çeviri atlandı': 'Translation skipped', 'Çeviri sırada…': 'Translation queued…',
        'Çevriliyor…': 'Translating…', 'Çeviri için ana pencerede çeviriyi aç': 'Enable translation in the main window',
        'Cevap Önerisi': 'Suggest reply', 'Yükleniyor…': 'Loading…', 'Öneri alınamadı': 'Could not get suggestions',
        'Canlı çeviri': 'Live translation', 'Bağlantı kesildi': 'Disconnected', 'Konuşma bekleniyor': 'Waiting for speech',
        'Sistem sesini ve çeviriyi ana pencereden başlat.': 'Start system audio and translation in the main window.',
        'Görünüm': 'Appearance', 'Yazı': 'Text', 'Zemin': 'Background', 'Orijinal metin': 'Original text',
        'Başlıktan taşı, kenardan boyutlandır. Ctrl+Shift+O: göster/gizle. Ctrl+Shift+L: oyun kilidi; yalnız çeviri görünür. Kenarlıksız pencere modu önerilir.': 'Drag the header to move and resize from the edges. Ctrl+Shift+O: show/hide. Ctrl+Shift+L: game lock; only the translation remains visible. Borderless-windowed mode is recommended.',
        'Kutuyu yerleştir, sonra kilitle': 'Position the overlay, then lock it', 'Oyuna kilitle': 'Lock to game',
        'Kilitli · Ctrl+Shift+L': 'Locked · Ctrl+Shift+L', 'Tıklamalar oyuna geçiyor': 'Clicks pass through to the game',
        'Oyun senin, çeviri burada.': 'Stay in the game. Translation appears here.',
        'Ana pencerede Sistem sesi ve çeviriyi açıp Başlat’a bas. Duyulan konuşmanın çevirisi burada belirecek.': 'Enable system audio and translation in the main window, then press Start. Translated dialogue will appear here.',
        'Dinleme durdu': 'Listening stopped',
        'Oyun modunu masaüstü uygulamasından açabilirsin.': 'Open Game Mode from the desktop application.',
        'Çeviri kutusu açılamadı; bağlantının hazır olmasını bekle.': 'The translation overlay could not open; wait for the connection to become ready.',
        'Oyun modu değiştirilemedi.': 'Game Mode could not be changed.',
        'Oyun modu açık: dengeli hızlı diyalog profili. Sistem sesi ve çeviri açıkken Başlat’ı kullan.': 'Game Mode is on with the balanced fast-dialogue profile. Enable system audio and translation, then press Start.',
        'Oyun modu kapalı; normal ses ayarların geçerli.': 'Game Mode is off; your normal audio settings apply.',
        'İstek zaman aşımına uğradı; modu kontrol edip tekrar dene.': 'The request timed out; check the mode and try again.',
        'Dengeli hızlı diyalog profili ve çeviri kutusu': 'Balanced fast-dialogue profile and translation overlay',
        'Sistem sesi: 0,9 sn uyarlanabilir bekleme, 10 sn konuşma sınırı. Kapatınca normal ayarlar geçerli.': 'System audio: 0.9 s adaptive wait and 10 s speech limit. Normal settings return when disabled.'
    });

    const ATTRIBUTE_NAMES = ['placeholder', 'title', 'aria-label'];
    const CONTENT_CLASSES = new Set([
        'transcription-original', 'transcription-translation', 'translation-text', 'reply-option-native',
        'reply-option-pronunciation', 'reply-option-meaning-text', 'reading-okunus',
        'reading-translation', 'reading-meaning', 'quick-phrase-choice',
        'okunus-text', 'reply-text', 'response-text'
    ]);
    const translatedNodes = new Set();
    const translatedAttributes = new Map();
    let currentLanguage = DEFAULT_LANGUAGE;

    function storage() {
        return window.whisperStorage || window.localStorage;
    }

    function normalizeLanguage(value) {
        const language = String(value || '').toLowerCase();
        return supported.has(language) ? language : DEFAULT_LANGUAGE;
    }

    function preserveSpacing(source, translated) {
        const leading = source.match(/^\s*/)?.[0] || '';
        const trailing = source.match(/\s*$/)?.[0] || '';
        return leading + translated + trailing;
    }

    function translatePattern(value) {
        const patterns = [
            [/^(\d+)\/3 hazır$/, '$1/3 ready'],
            [/^(\d+) seçenek hazır$/, '$1 suggestions ready'],
            [/^(\d+) kayıt$/, '$1 records'],
            [/^Konuşmacı (\d+)$/, 'Speaker $1'],
            [/^Seçenek (\d+)$/, 'Option $1'],
            [/^Model · (.+)$/, 'Model · $1'],
            [/^Ses · (.+)$/, 'Audio · $1'],
            [/^(\d+) kayıt (TXT|SRT|JSON) olarak indirildi$/, '$1 records downloaded as $2'],
            [/^(\d+) sonuç bulundu$/, '$1 results found'],
            [/^Bu oturum: (.+) token$/, 'This session: $1 tokens']
        ];
        for (const [pattern, replacement] of patterns) {
            if (pattern.test(value)) return value.replace(pattern, replacement);
        }
        return null;
    }

    // '📝 Çevir' gibi emoji + metin dugme etiketleri: emoji onekini ayirip
    // sozlukte/pattern'de yalniz cekirdek metni ara; bulunursa emoji korunarak
    // sonuc kurulur ('📝 Translate'). Saf emoji ('🗑️') metin icermedigi icin
    // degismez; sozlukte tam emoji'li anahtar varsa o eslesme yine ustte.
    function translateEmojiPrefixed(trimmed) {
        const match = trimmed.match(/^(\p{Extended_Pictographic}(?:\uFE0F|\u200D\p{Extended_Pictographic})*)\s*(.+)$/u);
        if (!match) return null;
        const core = EN[match[2]] || translatePattern(match[2]);
        return core ? `${match[1]} ${core}` : null;
    }

    function translateString(value) {
        if (currentLanguage !== 'en' || typeof value !== 'string') return value;
        const trimmed = value.trim();
        if (!trimmed) return value;
        const translated = EN[trimmed] || translatePattern(trimmed) || translateEmojiPrefixed(trimmed);
        return translated ? preserveSpacing(value, translated) : value;
    }

    function contentNode(node) {
        const parent = node?.parentElement;
        return Boolean(parent && (
            parent.hasAttribute('data-i18n-ignore') ||
            [...CONTENT_CLASSES].some(name => parent.classList.contains(name)) ||
            parent.closest('.speaker-badge, .ai-chat-result') ||
            ['SCRIPT', 'STYLE', 'TEXTAREA'].includes(parent.tagName)
        ));
    }

    function translateTextNode(node) {
        if (!node || node.nodeType !== Node.TEXT_NODE || contentNode(node)) return;
        if (node.__whisperI18nValue === node.data) return;
        const next = translateString(node.data);
        if (next === node.data) return;
        node.__whisperI18nOriginal = node.data;
        node.__whisperI18nValue = next;
        translatedNodes.add(node);
        node.data = next;
    }

    function translateAttribute(element, name) {
        if (!element?.hasAttribute?.(name) || element.hasAttribute('data-i18n-ignore')) return;
        const current = element.getAttribute(name);
        const record = translatedAttributes.get(element)?.[name];
        if (record?.translated === current) return;
        const next = translateString(current);
        if (next === current) return;
        const values = translatedAttributes.get(element) || {};
        values[name] = {original: current, translated: next};
        translatedAttributes.set(element, values);
        element.setAttribute(name, next);
    }

    function localizeTree(root) {
        if (!root) return;
        if (root.nodeType === Node.TEXT_NODE) {
            translateTextNode(root);
            return;
        }
        if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_NODE) return;
        if (root.nodeType === Node.ELEMENT_NODE) {
            for (const name of ATTRIBUTE_NAMES) translateAttribute(root, name);
        }
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
            if (node.nodeType === Node.TEXT_NODE) translateTextNode(node);
            else for (const name of ATTRIBUTE_NAMES) translateAttribute(node, name);
        }
        document.title = translateString(document.title);
    }

    function restoreTurkish() {
        for (const node of translatedNodes) {
            if (node.isConnected && node.__whisperI18nOriginal != null) node.data = node.__whisperI18nOriginal;
            delete node.__whisperI18nOriginal;
            delete node.__whisperI18nValue;
        }
        translatedNodes.clear();
        for (const [element, values] of translatedAttributes) {
            if (!element.isConnected) continue;
            for (const [name, record] of Object.entries(values)) element.setAttribute(name, record.original);
        }
        translatedAttributes.clear();
        if (document.title === EN['Whisper Transkripsiyon + Çeviri Pro']) {
            document.title = 'Whisper Transkripsiyon + Çeviri Pro';
        }
    }

    function syncSelector() {
        const select = document.getElementById('uiLanguage');
        if (select) select.value = currentLanguage;
    }

    function setLanguage(language, persist = true) {
        const next = normalizeLanguage(language);
        if (next === currentLanguage && document.documentElement.dataset.uiReady === 'true') return;
        if (currentLanguage === 'en') restoreTurkish();
        currentLanguage = next;
        document.documentElement.lang = next;
        document.documentElement.dataset.uiLang = next;
        if (persist) storage().setItem(STORAGE_KEY, next);
        syncSelector();
        if (next === 'en') localizeTree(document.body || document.documentElement);
        document.documentElement.dataset.uiReady = 'true';
        document.dispatchEvent(new CustomEvent('whisper:language-changed', {detail: {language: next}}));
    }

    window.uiText = value => translateString(String(value == null ? '' : value));
    window.whisperI18n = Object.freeze({
        t: value => translateString(String(value == null ? '' : value)),
        getLanguage: () => currentLanguage,
        setLanguage,
        refresh: () => currentLanguage === 'en' && localizeTree(document.body || document.documentElement)
    });

    try { currentLanguage = normalizeLanguage(storage().getItem(STORAGE_KEY)); }
    catch (_) { currentLanguage = DEFAULT_LANGUAGE; }

    const observer = new MutationObserver(mutations => {
        if (currentLanguage !== 'en') return;
        for (const mutation of mutations) {
            if (mutation.type === 'characterData') translateTextNode(mutation.target);
            else if (mutation.type === 'attributes') translateAttribute(mutation.target, mutation.attributeName);
            else for (const node of mutation.addedNodes) localizeTree(node);
        }
    });
    observer.observe(document.documentElement, {
        subtree: true, childList: true, characterData: true,
        attributes: true, attributeFilter: ATTRIBUTE_NAMES
    });

    window.addEventListener('storage', event => {
        if (event.key === STORAGE_KEY && event.newValue) setLanguage(event.newValue, false);
    });
    document.addEventListener('DOMContentLoaded', () => setLanguage(currentLanguage, false), {once: true});
})();
