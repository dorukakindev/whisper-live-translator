# Whisper Pro — tüm sağlanan raporların kapsam ve sonuç dökümü

Tarih: 4 Eylül 2026. İnceleme tabanı: mevcut çalışma ağacı; önceki düzeltmeler 40a8269, 6070c0e ve 903d24c ile karşılaştırıldı. Bu dosya yalnız yeni bir “paket” değil, erişilebilen raporların bütün görünür iddialarının sonuç envanteridir.

## Son sınır kontrolü

ba4b88a sonrası15999/16001Hz yaklaşımının1:1'e yuvarlanıp FIR ValueError üretmesi düzeltildi. Tam hız taraması önceki125ppm iddiasını250ppm olarak düzeltti. İki yeni regresyonla güncel toplam91Python testi ve6Node test dosyasıdır; aşağıdaki89sayısı önceki aşamanın kaydıdır.

Son statik taramada aktif backend'deki DeepL ağ testi ve PortAudio cleanup yollarında kalan dört çıplak `except` bloğu bulundu; hepsi `except Exception` olarak daraltıldı. Böylece process-level `SystemExit`/`KeyboardInterrupt` sessizce yutulmuyor; cleanup davranışı korunuyor.

Electron pencere yaşam döngüsü yeniden tarandı: menü korumalarına ek olarak backend-ready, second-instance, ready-to-show ve overlay toggle yolları destroyed pencereyi kullanmıyor. Sentetik overlay toggle testi eklendi; native Electron stres sınırı değişmedi. Son backend `except` değişiklikleri de portable pakete yeniden yansıtıldı.

## Yeni gönderilen 13 maddelik rapor

aba9083f-c729-4fbd-b47e-600dcbd429c0 eki ayrıca13/13değerlendirildi. Ayrıntılı kararlar, daraltılan iddialar, testler ve ölçülerek giderilen patolojik FIR maliyeti [yeni raporda](RAPOR_YENI_13_DOGRULAMA_2026-09-04.md). Toplam Python regresyon sayısı89, Node test dosyası6oldu. Bu ek, aşağıdaki tarihsel307iddialık sayımı yeniden benzersiz bug sayısına dönüştürmez.

## İkinci devam incelemesi — 8d718ec sonrası

- S-H10/placeholder-karışımı: Bir gürültü kaydı ve iki geçerli öneri geldiğinde partial önce filtreleyip iki öneri gösteriyor, final ise önce ikiye kesip ikinci gerçek öneriyi kaybediyordu. Bu, önceki cap değişikliğinin regresyonuydu. Final şimdi partial ile aynı sırada önce gürültüyü filtreliyor; sonra çağrı başına iki sınırı uyguluyor. Test düzeltmeden önce second seçeneğinin kaybıyla başarısız, sonra başarılı.
- Başlatıcı: checkServerReady yalnız error/end geldiğinde yeniden deniyordu; bağlantı açılıp yanıt bitmezse120deneme sınırına hiç erişilmiyordu. İstek başına en fazla5sn abort ve bütün denemelerde korunan60sn deadline eklendi. settled koruması abort+error çift retry'sini ve geç gelen yanıtı engelliyor. Gerçek fonksiyon VM/mock testi yanıtsız istek ve deadline aşımını doğruluyor; gerçek Electron stres testi değil.
- B-BE-009 sentetik ölçüm:1sn,997Hz,10000tepe genlikli int16 sinüs;44.1kHz ve48kHz girdileri30ms parçalara bölünerek ve tek parça halinde16kHz'e dönüştürüldü. Her iki yöntem16000örnek verdi. RMS farkları sırasıyla111.798 ve116.528int16birimi. Dolayısıyla chunk sınırı sayısal etkisi var; ancak bu ölçüm işitilebilir tıkırtı veya Whisper doğruluk kaybını kanıtlamaz. Gecikmeli/stateful DSP dönüşümü ses kalite kanıtı olmadan uygulanmadı.
- Python toplamı81test; beş Node dosyası yeniden doğrulandı. Kalan gerçek cihaz/uzun oturum sınırları korunuyor.

## Devam incelemesi — 0650f92 sonrası

Önceki307satırlık dağılım ilk kapsam incelemesinin kaydıdır; aşağıdaki ek kanıtlar bu kaydı günceller:

- Settings test kör noktaları11/12/13: JSON üst düzey liste/string/sayı/bool/null için kontrollü400 ve değişmeyen ayar durumu testi eklendi. Önce liste/string girdileri500, boş liste/null ise sessiz varsayılana dönüş üretiyordu. Endpoint artık yalnız JSON nesnesi kabul eder.
- Sayısal alanlarda Python bool/int ilişkisi nedeniyle true sessizlik süresini1.0, true/false VAD seviyesini1/0 yapıyordu. Bool artık geçersiz sayılır; mevcut güvenli varsayılan2 davranışı korunur. Negatif/sınır aşımı/NaN/inf/string/liste/nesne ve geçerli VAD0..3/silence60 matrisleri geçti. Bu genel fuzz ispatı değil, açıkça listelenmiş girdi matrisidir.
- S-L10: Somut gecikmiş-restart yolu doğrulandı. Child-close kapanıştan önce restart timer kurabiliyor; startPythonServer kapanıştan sonra çalıştığında guard yoktu. isQuitting giriş kontrolü eklendi. Gerçek fonksiyonun VM testi kapanışta hiçbir başlatma hazırlığına girilmediğini doğruluyor. Native Electron kapanış stresi halen yapılmadı.
- S-M26: Gerçek setupSocketListeners fonksiyonu socket=null ile test edildi; uyarı verip güvenli döner. Aynı socket ile iki kurulum listener çoğaltmaz. Somut null/tekrar-kurulum senaryosu yanlış alarm; belirtilmemiş diğer payload senaryoları bu testin garantisi değildir.
- Tüm Python süitleri yeniden geçti:28+15+10+4+9+14=80test. Beş Node dosyası tekrar geçti; py_compile/pyflakes temiz. Yeni testler düzeltme öncesinde başarısız, sonrasında başarılıydı.
- Fiziksel mikrofon/Bluetooth/CUDA, FIR işitilebilirliği, eski CMD codepage, sessizlikte glossary hallucination ve8saat soak halen sınanmadı; yalnız bunları kapatmış görünmek için kod değiştirilmedi.

## Sonuç ve sayım yöntemi

- 128 eski rapor maddesi + 30 derin rapor maddesi + 19 P-kodlu madde + 113 özet ifade + 17 ek rapor maddesi = **307 iddia değerlendirmesi**. Bunlar 307 benzersiz bug değildir; aynı kusur farklı raporlarda tekrar ediyor.
- Dağılım: **55 bu tur düzeltildi**, **108 önceden düzeltilmiş/mevcut koruma**, **55 yanlış alarm**, **81 tasarım/iyileştirme/kapsam ayrımı**, **8 kesinleştirilemeyen iddia**. Birden fazla alt iddialı satırda gerekçe ve sınır ayrıca okunmalı; “mevcut koruma” bütün donanım koşullarında ispat demek değildir.
- Ek olarak 8 UI önerisi, doküman kayması, 7 şüphe, 14 test kör noktası, 14 önerilen test ve 10 gerçek cihaz kontrolü aşağıda ele alındı. Öncelik sırası ve eski raporların tekrar disposition tabloları yeni bug diye sayılmadı.
- “153 bug” ekinin başlık sayıları 22+35+49+48=154 ediyor; verilen metinde ise **21 kritik,32 yüksek,43 orta,17 düşük =113 görünür ifade** var. Eksik ayrıntılar uydurulmadı. S-C/H/M/L kimlikleri, metindeki sıra ve noktalı virgülle ayrılan ifadelere bu incelemede atandı.
- Eski tam raporun yaklaşık124 toplamı yerine gerçekten128 farklı ID mevcut. E raporunun iki ayrı yüklemesinin SHA256 değeri aynı: E6A233C4605FFA46EC33624BC11673A4F6039E5042E81EBAA5850675D6DD8540. İkinci kopya yeniden bug sayılmadı.

## Bu turdaki somut değişiklikler

- Kuyruğun bütün yakalama yollarında Full/Empty yarışına dayanıklı ekleme ve gecikme uyarısı; stale final işini model kilidinden sonra reddetme; hata emit'i hata verse de worker'ın çıkmaması.
- Native yazım ile hazır Türkçe fonetik ayrımı; somut İtalyanca/İspanyolca/Slovakça çift dönüşüm; queso/xin/Portekizce terminal o; kısa tekrar vurgusu ve tam motor marker'ları.
- Answer çağrısı başına2 seçenek; timeout'ta pending future iptali; NFC/casefold dedup; belirsiz auto için çelişen çoklu stil bloklarının kaldırılması; esnek JSON fence.
- Windows transcript rotasyonunda paylaşım hatası fallback'i ve gelecek UTF8 satırın hesaba katılması. Bütün yedek hedefleri kilitliyse hata kaydı+metin koruma tercihi: sınırsız diski kesin önlediği iddia edilmez.
- CJK partial kaynak boşluğu, glossary pipe/backslash, collapsed cevap paneli, art arda başarısız ayarda teyitli değere geri dönüş, güvenli geçici storage fallback, doğru key durumu mesajları, meşru alert noktalaması.
- Başarılı Python komutunun process çapında cache'i,5sn probe timeout, restart hakkı tükenince çıkış; batch çağrısı/venv/başlatma mesajları; arşiv launcher dizini ve read/cleanup hataları.
- Eval token referansı; offsetli millisecond ISO zamanı; uyumlu CSP/nosniff/referrer başlıkları; güncel CLAUDE.md ve başlangıç belgeleri.

## Doğrulama ve sınırlar

Proje .venv Python3.11.9; torch2.10.0+cu130, ctranslate2 4.7.1, pyaudiowpatch0.2.12.8. webrtcvad/pyannote.audio/faster_whisper modül bulunurluğu doğrulandı. GPU üzerinde inference çalıştırılmadı.

- Python: test_smoke.py28; test_report_regressions.py15; test_followup_regressions.py10; test_third_report.py4; test_fourth_report.py9; test_complete_audit.py12: **78 test geçti**.
- Node: test_main_helpers.js, test_frontend_regressions.js, test_followup_frontend.js, test_third_frontend.js, test_complete_frontend.js geçti. VM/mock testleri gerçek Electron render/GPU testi değildir.
- Render edilmiş index/overlay inline scriptleri node --check; main.js/build.js/static/runtime-safety.js sözdizimi; değiştirilmiş Pythonlar py_compile; buyedektir.py/eval/yeni test pyflakes temiz. git diff --check temiz.
- Ücretli test_cevap_onerisi.py çalıştırılmadı: yalnız run_case AST'den çıkarılıp mock ile token sınandı. Gerçek API, Whisper model yükleme/indirme, mikrofon, USB/Bluetooth, CUDA stress, sekiz saatlik oturum ve Electron GUI testi yapılmadı.
- Portable yeniden üretildi: npm run build başarılı, paket güvenlik taraması temiz. Eski oluşturulmuş pakette kullanıcı transkripti/profili/venv adayları bulunmadığı kontrol edilerek yalnız build çıktısı yenilendi. buyedektir.py, main.js, main_helpers.js, preload.js, index.html, overlay.html, runtime-safety.js ve whisper-pro-theme.css kaynak/paket dosyaları byte-byte ve SHA256 karşılaştırmasında eşleşti.

Önemli açık sınırlar: İşitilebilir FIR chunk artefaktı, native sürücü read kilitlenmesi ve gerçek ses hallucination kalitesi sentetik testlerle kapanmış sayılmaz. Yerel anahtarların OS-vault ile şifrelenmesi yapılmadı; localhost token'ı çok-kullanıcılı yetkilendirme değildir. CSP inline olaylar nedeniyle unsafe-inline içeriyor ve escapeHtml'in yerine geçmez. Eski debug kopyaları/kullanıcı yedekleri silinmedi. İyileştirme veya tasarım satırları “düzeltildi” diye sunulmadı.

## 1. BUG_TARAMASI_TAM_RAPORU.md — 128 madde

| Kimlik | Rapordaki iddia | Sonuç | Gerekçe / kaynak / test |
|---|---|---|---|
| B-FR-001 | `renderAiResult` null guard eksik — DOM crash | Önceden düzeltilmiş / mevcut koruma | renderAiResult, aiBox/item yoksa güvenli dönüş; frontend regresyonu. |
| B-FR-002 | `setupSocketListeners` — socket.off() hiç kullanılmıyor, listener birikimi | Yanlış alarm | setupSocketListeners tek kurulum akışında; reconnect aynı socket üzerinde, yeniden kayıt döngüsü gösterilmedi. |
| B-FR-003 | `saveHFToken` fetch'inde .catch() yok | Önceden düzeltilmiş / mevcut koruma | saveHFToken catch ve kullanıcı bildirimi mevcut; boş token yolu da düzeltildi. |
| B-FR-004 | `startCapture` retry `stopCapture` ile race ediyor | Önceden düzeltilmiş / mevcut koruma | _captureStartGeneration ve retry iptali eski start yanıtını geçersizleştiriyor. |
| B-FR-005 | `stopCapture`'da `data.success=false` ele alınmıyor | Önceden düzeltilmiş / mevcut koruma | stopCapture başarısız yanıtı ve ağ hatasını ele alıyor. |
| B-BE-001 | `conversation_turns` deque — 2 thread lockSIZ append data race | Önceden düzeltilmiş / mevcut koruma | conversation_turns yazıları ve snapshot lifecycle kilidinde; smoke snapshot testi. |
| B-BE-002 | `transcriptions` deque — transcribe + translate thread çakışması | Önceden düzeltilmiş / mevcut koruma | transcriptions commit/çeviri/snapshot lifecycle kilidinde. |
| B-BE-003 | `speaker_names` dict — 3 thread arası data race | Önceden düzeltilmiş / mevcut koruma | SpeakerDiarizer profil kilidi, generation ve güncel ad çözümleme mevcut. |
| B-BE-004 | `_session_id` transcript emit öncesi yeniden kontrol EDİLMİYOR | Önceden düzeltilmiş / mevcut koruma | Final commit oturum+sonuç nesli altında; stale işin emit yolu kapalı. |
| B-BE-005 | `process_mic_audio` hiç `_session_id` kontrol etmez | Yanlış alarm | Gerçek stop _result_generation artırıyor; yalnız session_id değiştirilen sentetik senaryo gerçek stop değildir. test_real_stop_invalidates_old_ptt_result. |
| B-BE-006 | `_transcribe_partial` socket emit'i session stale olduktan sonra | Önceden düzeltilmiş / mevcut koruma | Partial emit öncesi lifecycle/session kontrolü; test_partial_emit_session_guard. |
| B-INF-001 | `build.js` whitelist tüm dosyaları siliyor | Önceden düzeltilmiş / mevcut koruma | build.js isKept baştaki slash/backslash normalleştirmesi ve boş kök kabulü mevcut. |
| B-INF-002 | `static/` dizini build artifact'te yok | Önceden düzeltilmiş / mevcut koruma | KEEP_DIRS static içeriyor; yeni runtime-safety.js de paketlenecek. |
| B-INF-003 | `electron-store` v8 ESM-only, proje CommonJS | Yanlış alarm | Kurulu electron-store 8.2.0 CommonJS; ESM-only iddiası daha yeni ana sürümle karıştırılmış. |
| B-INF-004 | `launcher_whisper.py` shell=True (CWE-78 deseni) | Önceden düzeltilmiş / mevcut koruma | launcher_whisper.py kontrollü npm.cmd çözümü kullanıyor; kullanıcı metni shell komutuna eklenmiyor. |
| B-INF-005 | Session cookie hardening yok (CWE-614) | Yanlış alarm | Flask session/cookie ile oturum açma kullanılmıyor; SECRET_KEY varlığı aktif session cookie demek değil. |
| B-BE-007 | `MicRecorder.frames` lock'suz list mutasyonu | Önceden düzeltilmiş / mevcut koruma | MicRecorder frame snapshot/temizleme kilitli; smoke mic testi. |
| B-BE-008 | "Input overflowed" hatasında ses kırpılıp atılıyor | Tasarım / iyileştirme / kapsam ayrımı | Yetişmeyen gerçek zamanlı yakalamada overflow ile veri düşmesi donanım kapasite sınırıdır; yok olmuş örnekler yazılımla geri getirilemez. Kuyruk taşması artık bütün yollarda görünür. |
| B-BE-009 | Chunk-bazlı resampling boundary hatası (tıkırtı) | Kesinleştirilemedi | Bağımsız chunk FIR sınır etkisi teorik olarak mümkün; işitilebilir hata veya transkripsiyon kaybı gerçek sesle ölçülmedi. DSP algoritması körlemesine değiştirilmedi. |
| B-BE-010 | `_model_lock` crash/deadlock riski | Yanlış alarm | Python hata yolları model kilidini finally ile bırakıyor. Native segfault bütün süreci bitirir; contextmanager bunu iyileştirmez. |
| B-BE-011 | `stream.read()` süresiz blokaj riski | Kesinleştirilemedi | PortAudio sürücüsünün sonsuz blokajı gerçek donanım olmadan doğrulanmadı. Canlı C stream nesnesini başka thread'den zorla kapatmak güvenli çözüm değil. |
| B-BE-012 | `speaker_profiles.json` — çift thread eşzamanlı yazma | Önceden düzeltilmiş / mevcut koruma | Profil yazıları profile lock+atomik replace; bozuk dosyanın üzerine yazmama koruması var. |
| B-BE-013 | `_append_transcript` file rotation race | Bu tur düzeltildi | Yazılar zaten kilitliydi; bu tur Windows paylaşım hatasına dayanıklı rotasyon ve yeni satır boyutunu hesaba katma eklendi. |
| B-BE-014 | `capture_stopped` eski session'dan gönderiliyor | Önceden düzeltilmiş / mevcut koruma | capture_stopped stale guard var; eski oturum yeni oturumu durdurmuyor. |
| B-BE-015 | `socketio.emit` cleanup/exception yollarında try/catch yok | Bu tur düzeltildi | Transcribe hata bildirimi ikinci kez hata verirse worker artık bu nedenle ölmüyor; mevcut capture cleanup korumaları muhafaza edildi. |
| B-BE-016 | `transcriptions` deque + `conversation_turns` deque + `context_buffer` deque + `stats` dict — tümü locksuz | Önceden düzeltilmiş / mevcut koruma | Paylaşılan iş verisi snapshot/commit kilitleri mevcut. Diagnostik sayaçların yaklaşık okunması ayrı bir iddia. |
| B-FR-006 | Yaygın `.catch()` eksikliği (10+ fetch çağrısı) | Bu tur düzeltildi | Somut ayar yolları persistRuntimeSettings ile sıralı, zaman aşımlı, teyitli değere geri alınıyor; bütün fetch çağrılarının aynı işlevi görmesi gerekmiyor. |
| B-FR-007 | 5 ayrı `document.addEventListener('keydown', ...)` — listener birikimi | Yanlış alarm | Farklı tuş görevleri için bir kez kurulan beş listener, beş kat yeniden kayıt değildir. |
| B-FR-008 | `updateTranslationStatus` timer çakışması | Önceden düzeltilmiş / mevcut koruma | _translationStatusTimer saklanıp temizleniyor. |
| B-FR-009 | Download `\n` kullanıyor, Windows Notepad'de bozuk | Yanlış alarm | LF modern Windows/Electron hedefinde geçerli; eski Notepad desteği vaat edilmemiş. |
| B-FR-010 | `changeAIModel` ve `changeAITranslationModel` success=false sessiz | Önceden düzeltilmiş / mevcut koruma | İki model seçimi başarısızlığı kontrol ediyor. |
| B-FR-011 | 5 adet `fetch()` `.then(response => response.json())` — HTTP hata kodları ele alınmıyor | Bu tur düzeltildi | Ayar kaydetme yardımcısı HTTP durumu ve success kontrol ediyor; diğer işlevlerdeki mevcut hata yolları korundu. |
| B-TST-001 | `test_resample_clip` vacuous truth | Yanlış alarm | test_resample_clip taşacak ara değer önkoşulunu ve clipping sonucunu kontrol ediyor; vacuous değil. |
| B-TST-002 | `test_answer_contract` dedup doğruluğunu test etmiyor | Bu tur düzeltildi | Unicode NFC/NFD ve Latin dışı seçenekler followup testiyle; çağrı başına cap yeni testle doğrulandı. |
| B-TST-003 | `transkribe.py` dosya handle sızıntısı | Önceden düzeltilmiş / mevcut koruma | transkribe.py model segment iterasyonu/iş bitişi cleanup akışı güncel; kaynak iddiadaki açık handle yolu yok. |
| B-DBG-001 | Canlı API key'leri HTML value attribute'larında | Tasarım / iyileştirme / kapsam ayrımı | Eski debug HTML üretim allowlist dışında ve ignore edilmiş. Hassas gerçek içerik okunmadı; eski kopyaların silinmesi veya anahtar yenileme bu incelemede yapılmadı. |
| B-DBG-002 | `transcriptions is not defined` ReferenceError | Önceden düzeltilmiş / mevcut koruma | Aktif templates/index.html transcriptionTexts kullanıyor; eski debug dosyasındaki tanımsız değişken üretim yolu değil. |
| B-DBG-003 | XSS — `correctText()` innerHTML'e controlsüz injection | Önceden düzeltilmiş / mevcut koruma | Aktif correctText/render yolu escape kullanıyor; debug HTML üretim dışı. |
| B-DBG-004 | XSS — `showAlert()` innerHTML'e controlsüz injection | Önceden düzeltilmiş / mevcut koruma | Aktif showAlert metni escape ediyor; bu tur baştaki meşru noktalama korunması ayrıca düzeltildi. |
| B-DBG-005 | `addTranscription` innerHTML'de controlsüz server verisi | Önceden düzeltilmiş / mevcut koruma | Aktif addTranscription kullanıcı/sunucu metnini escape ediyor; entity round-trip testleri mevcut. |
| B-CFG-001 | Content Security Policy (CSP) YOK | Bu tur düzeltildi | set_browser_security_headers ile CSP, nosniff, no-referrer eklendi. Inline JS halen izinli: bu strict-CSP/XSS garantisi değildir. |
| B-CFG-002 | Raw `str(e)` socket error event'leriyle UI'a sızıyor | Önceden düzeltilmiş / mevcut koruma | Ana hata olayları kullanıcıya güvenli mesaj verir; ayrıntı yerel logda. Her str(e) ifadesi kendiliğinden credential sızıntısı değildir. |
| B-CFG-003 | Raw OpenAI exception detayı kullanıcıya gidiyor | Önceden düzeltilmiş / mevcut koruma | AI başarısızlık/bozuk JSON ham cevabı Türkçe alanına dökülmüyor; smoke parse-failure testi. |
| B-DEP-001 | `webrtcvad` kurulu DEĞİL — startup'ta crash | Yanlış alarm | Proje .venv Python3.11.9 ortamında webrtcvad bulunuyor; mevcut testlerin importu başarılı. |
| B-DEP-002 | CUDA devre dışı — CPU-only torch | Yanlış alarm | Kurulu torch 2.10.0+cu130; CPU-only iddiası yanlış. Gerçek GPU iş yükü başarısı ayrıca test edilmedi. |
| B-DEP-003 | `pyannote.audio` kurulu DEĞİL | Yanlış alarm | Proje .venv içinde pyannote.audio bulunuyor. Token erişimi/model indirme gerçek API ile test edilmedi. |
| M01 | 1358, 1635, 1746, 1752 \| Bare `except:` `SystemExit`/`KeyboardInterrupt`'u da yutar \| `except Exception:` ile değiştir \| | Tasarım / iyileştirme / kapsam ayrımı | Aktif kritik cleanup yolları exception sınıflarıyla korunuyor; tüm bare-except'leri mekanik değiştirmek davranış kanıtı değildir. Archive read döngüsündeki somut sorun M30'da düzeltildi. |
| M02 | 514-518 \| `_clean_json_object` `startswith('```')` ile kırılgan; ````json` öneki varsa çalışmaz \| Regex ile esnek yakala \| | Bu tur düzeltildi | _clean_json_object 3+ backtick ve büyük harf JSON kabul ediyor; test_json_fences. |
| M03 | 972 \| `not value` valid falsy değerleri (0, "", False) reddeder \| `value is None` ile değiştir \| | Yanlış alarm | Telaffuz girdisi metindir; 0/False geçerli okunuş değildir; boş girişin reddi sözleşmeyle uyumlu. |
| M04 | 903 \| Gürcüce `kh` digraph yanlış pozitif (k+h geçen kelimelerde) \| Word boundary ekle \| | Tasarım / iyileştirme / kapsam ayrımı | Gürcüce kh digraph'ını kelime başına sınırlamak kelime içi gerçek kh sesini bozar; somut karşı örnek olmadan uygulanmadı. |
| M05 | 2791-2794 \| VAD fallback'inde sabit threshold (500) — sessiz mikrofon/amplifikasyon hatalı \| Relative threshold kullan (`np.iinfo(np.int16).max * 0.02`) \| | Tasarım / iyileştirme / kapsam ayrımı | 32767*0.02 de sabit eşiktir, öneri adaptif değildir. VAD seviyesi/enerji eşiği kalibrasyonu gerçek mikrofonla ölçülmeli. |
| M06 | 4113-4124 \| JSON çözümlenemeyince ham AI çıktısı kullanıcıya "Türkçe" olarak gösterilir \| Ham çıktıyı kontrol et, anlaşılamadı mesajı göster \| | Önceden düzeltilmiş / mevcut koruma | JSON parse başarısızlığında success:false; ham model metni cevap diye gösterilmiyor. |
| M07 | 22-26 \| `python-dotenv` import hatası sessizce yutulur, `.env` yüklenmez, AI özellikleri kapalı \| `logger.warning` ekle \| | Tasarım / iyileştirme / kapsam ayrımı | dotenv requirements içinde; eksik opsiyonel dotenv durumunda ortam değişkenleri yine çalışır. Kurulum bağımlılığı uyarısı iyileştirme, aktif ortam hatası değil. |
| M08 | 82-85 \| Çift `TextIOWrapper` `sys.stdout.buffer` üzerinde — buffer interleaving \| `logging.StreamHandler(sys.stdout)` kullan \| | Tasarım / iyileştirme / kapsam ayrımı | stdout wrapper ve logging farklı akışlarının olası satır sırası, kanıtlanmış veri bozulması değil; logger yeniden-kurulum senaryosu raporda yok. |
| M09 | 134-141 \| FIR filter 192kHz'de ~30MB, cache'li bellek şişmesi \| max_rate'e üst sınır koy (96000) \| | Yanlış alarm | 192000/16000 gcd indirgemesi up=1/down=12; FIR 241 katsayı, yaklaşık 30MB iddiası yanlış. |
| M10 | 3215-3219 \| Translation backlog guard lock'suz, race window \| Integer atomik GIL altında, yorum ekle \| | Önceden düzeltilmiş / mevcut koruma | Çeviri sequence snapshot ve commit'te yeniden stale kontrolü mevcut; test_translation_that_becomes_stale_in_flight_is_not_emitted. |
| M11 | 1464-1636 \| `SpeakerDiarizer.pipeline` GPU belleği asla serbest bırakılmaz → CUDA OOM \| `del pipeline; torch.cuda.empty_cache()` \| | Tasarım / iyileştirme / kapsam ayrımı | Diarizer pipeline tekrar kullanım için tutulur; kapanıp tekrar açıldığında model yüklememek tasarım. OOM olmadan koşulsuz GPU boşaltma yapılmadı. |
| M12 | 3229 \| `list(self.transcriptions)` kopyalama sırasında append race \| Lock altında kopyala \| | Önceden düzeltilmiş / mevcut koruma | Transcription kopyaları snapshot kilidi altında. |
| M13 | 2564-2573 \| `join(timeout=2)` sonrası kurtarma yok → "hala kapanıyor" \| Zorla stream kapat + thread terminate \| | Kesinleştirilemedi | Native read sonsuz beklerse timeout thread öldürmez; zorla thread terminate güvenli değil. Gerçek cihaz sınaması açık. |
| M14 | 1851, 3201 \| Tek-worker translate executor 60sn OpenAI'de bloke, tüm kuyruk birikir \| `max_workers=2` veya timeout'lu worker \| | Önceden düzeltilmiş / mevcut koruma | translate_executor iki worker ve backlog/nesil koruması var; sınırsız canlı çeviri kuyruğu iddiası mevcut akışla uyuşmuyor. |
| M15 | 1249-1252, 1294-1296 \| OpenAI hata yanıtları kullanıcıya ham `str(e)` ile gidiyor \| Genel mesaj göster, detayı log'a yaz \| | Önceden düzeltilmiş / mevcut koruma | AI ham hata/bozuk cevap güvenli failure yoluna çevriliyor. |
| M16 | 3449, 3866-3874 \| Token counter clear sonrası eski değere sıçrıyor \| Backend'in de token counter'ı sıfırlamasını sağla \| | Önceden düzeltilmiş / mevcut koruma | Clear backend token/stat değerlerini de sıfırlıyor; UI hydrate/instance nesli eski değeri geri getirmiyor. |
| M17 | 4465-4474 \| `buildTranslationResultHtml` iki nokta (`:`) içeren metni kırpıyor (ör. "Let's go: to the store") \| Son iki noktaya göre böl veya delimiter marker kullan \| | Önceden düzeltilmiş / mevcut koruma | buildTranslationResultHtml yapılandırılmış alan/etiket ayrıştırıyor; cümle içi kolonları keyfi kesmiyor. |
| M18 | 3382 \| `innerHTML +=` tüm DOM alt ağacını yeniden ayrıştırıyor \| `insertAdjacentHTML('beforeend', ...)` kullan \| | Önceden düzeltilmiş / mevcut koruma | Aktif ekleme insertAdjacentHTML/ayrı düğüm yolu; bütün transcript alt ağacı += ile yeniden oluşturulmuyor. |
| M19 | 3120 \| `startCapture` retry timeout'ları `stopCapture`'da temizlenmiyor \| AbortController veya retry session ID \| | Önceden düzeltilmiş / mevcut koruma | Capture start generation ve retry iptali uygulanmış. |
| M20 | 3180 \| `flushNow` timer'ları her çağrıda birikir \| Timer ID'sini sakla ve temizle \| | Önceden düzeltilmiş / mevcut koruma | flushNow zamanlayıcısı temizleniyor; birikim yolu kapalı. |
| M21 | 2591 \| `updateTranslationStatus` timer ID'si saklanmıyor \| `_translationStatusTimer` değişkenine ata \| | Önceden düzeltilmiş / mevcut koruma | _translationStatusTimer tutuluyor; B-FR-008 ile aynı. |
| M22 | `test_smoke.py` \| 486-531 \| Test state cleanup başarısız olursa tüm modül bozulur \| Context manager deseni kullan \| | Tasarım / iyileştirme / kapsam ayrımı | Smoke cleanup mevcut finally bloklarıyla; failure injection daha geniş test altyapısı önerisi, üretim bug'ı değil. |
| M23 | `test_smoke.py` \| 315-321 \| `_salvage_answer_options`'ın `detected_lang` dönüşü test EDİLMİYOR \| detected_lang test caseleri ekle \| | Önceden düzeltilmiş / mevcut koruma | Salvage testleri detected_lang ve literal braces içeriyor; third suite. |
| M24 | `_gen_phrases.py` \| 160-161 \| Çıktı JSON manuel kopyalanıyor, hata riski \| Doğrudan index.html'e yaz veya runtime fetch \| | Tasarım / iyileştirme / kapsam ayrımı | _gen_phrases.py kontrollü üretici; elle kopyalama belgelenmiş iş akışı, otomatik template yazımı yeni özellik. |
| M25 | `package.json` \| 15 \| `electron-store` v8 + CommonJS uyumsuz \| v6'ya düşür \| | Yanlış alarm | B-INF-003 ile aynı; v8 CJS uyumlu, downgrade gerekmez. |
| M26 | `package.json` \| 19 \| `electron-builder` kullanılmıyor \| `devDependencies`'ten kaldır \| | Tasarım / iyileştirme / kapsam ayrımı | Kullanılmayan electron-builder geliştirme bağımlılığı temizlik konusu; çalışma bug'ı yok, lockfile gereksiz değiştirilmedi. |
| M27 | 2351-2356 \| DOM pruning'de empty-state guard dead code (empty-state zaten kaldırılmış) \| Guard'ı kaldır \| | Tasarım / iyileştirme / kapsam ayrımı | Koruyucu empty-state kontrolünün gereksiz olması işlev hatası değil. |
| M28 | 1032-1050 \| `copy-btn` CSS class'ı isim-semantik uyuşmaz (AI trigger butonlarında) \| Yeni class oluştur \| | Tasarım / iyileştirme / kapsam ayrımı | CSS class adı anlamı refactor tercihi, davranış kaybı yok. |
| M29 | `archive/run_whisper.py:10,22` \| `chdir` archive'e yapıp parent'taki buyedektir.py'yi arıyor \| Path'i `"../buyedektir.py"` yap \| | Bu tur düzeltildi | archive/run_whisper.py proje köküne geçiyor; yanlış çalışma dizini düzeltildi. |
| M30 | `archive/main.py:370-371` \| Bare `except: continue` tüm hataları yutar, sonsuz döngü riski \| `except OSError` yap \| | Bu tur düzeltildi | archive/main.py read OSError için 50 deneme/49 backoff ile sonlanıyor; AST sentetik testi. |
| M31 | `archive/main.py:409-411` \| `stream` tanımsız olabilir, finally'de `UnboundLocalError` \| `stream = None` ile başlat \| | Bu tur düzeltildi | archive/main.py stream=None ve finally iç içe cleanup; open hatasında terminate garantisi, AST testi. |
| M32 | `archive/ai_studio_code.py:626-678` \| Duplicate CSS bloğu (copy-paste) \| Fazla bloğu kaldır \| | Tasarım / iyileştirme / kapsam ayrımı | Archive CSS tekrarları aktif uygulama yolu değil; kullanıcının eski arşivi temizlenmedi. |
| M33 | `archive/__pycache__yedek/` \| 8 neredeyse özdeş yedek ~847 KB, gereksiz repo şişkinliği \| Git'ten kaldır \| | Tasarım / iyileştirme / kapsam ayrımı | Yedek dosyalar kullanıcı geçmişi; silmek bug düzeltmesi değildir. Önceden kirli arşiv dosyaları korunuyor. |
| M34 | `.claude/settings.local.json:17` \| Eski path `/c/Users/T/...` — proje `D:\`'de \| `/d/Whisper Live` ile değiştir \| | Tasarım / iyileştirme / kapsam ayrımı | Kullanıcıya özel .claude izin dosyası uygulama runtime'ı değil; eski makine izinlerini genişletmek bu görevin doğal düzeltmesi değil. |
| M35 | `.claude/launch.json:6` \| `runtimeExecutable` göreceli path (`.` ile başlıyor) \| `${workspaceFolder}/.venv/Scripts/python.exe` \| | Yanlış alarm | Workspace-relative runtimeExecutable geçerli bir launcher tercihidir; bu değerden tek başına açılış hatası çıkarılamaz. |
| L01 | 2673, 2886 \| `chunk_seconds` native rate'den hesaplanıyor, resample edilmiş veri için mantıksal tutarsızlık \| | Yanlış alarm | Chunk süresi gerçek native örnek sayısı/native rate ile hesaplanır; resampling süreyi değiştirmez. |
| L02 | 3858-3885 \| `tone` değişkeni `else` garantisine dayanıyor, validasyon yoksa kırılır \| | Önceden düzeltilmiş / mevcut koruma | Tone allowlist/fallback doğrulaması endpointte var. |
| L03 | 2699-2704, 2799-2811 \| Diagnostic counter'lar pause/resume'da sıfırlanmıyor \| | Tasarım / iyileştirme / kapsam ayrımı | Oturum diagnostik sayacı pause ile sıfırlanmamak üzere tutuluyor. |
| L04 | 3470, 3525-3564 \| PTT çeviri provider yokken bile audio kaydı başlatır, kullanıcı boşuna bekler \| | Önceden düzeltilmiş / mevcut koruma | PTT hedef/yapılandırma doğrulaması ve kayıt öncesi iş slotu rezervasyonu var; full queue testi. |
| L05 | 1110-1117, 1923-1928, 3747 \| Çift `test_connection()` çağrısı (arkaplan + API çağrısı), %2 bandwidth israfı \| | Önceden düzeltilmiş / mevcut koruma | Config bağlantı doğrulaması aynı kayıt için bir kez; smoke test_connection_once. |
| L06 | 1327 \| DeepL URL `api-free.deepl.com` hardcoded, Pro kullanıcıları çalışmaz \| | Önceden düzeltilmiş / mevcut koruma | DeepL :fx/free ile Pro api.deepl.com ayrımı, endpoint snapshot testi. |
| L07 | 1671 \| Redundant `import pyaudiowpatch as pyaudio` (module-level zaten var) \| | Tasarım / iyileştirme / kapsam ayrımı | Fonksiyon içi import sys.modules cache kullanır; kaynak temizliği, sızıntı değil. |
| L08 | 2793 \| `logger.debug` olmalı `logger.warning` — VAD düşüşü production'da görünmez \| | Tasarım / iyileştirme / kapsam ayrımı | VAD fallback normal düşük seviye diagnostiktir; her frame warning yapmak log yükünü artırır. |
| L09 | 1823 \| `_next_transcription_id` sınırsız büyür (çok uzun session'larda DOM ID'si şişer) \| | Yanlış alarm | Python integer taşmaz; monoton transcript ID reset sonrası çakışmayı önler. |
| L10 | 2537 \| `_session_id` sınırsız büyür (sık start/stop'ta) \| | Yanlış alarm | Monoton session_id eski işlerin reddi için gerekli; resetlemek race yaratabilir. |
| L11 | 532 \| `_salvage_answer_options` regex'i `\{[^{}]*\}` iç içe JSON'ı yakalamaz (amaçlanan davranış) \| | Önceden düzeltilmiş / mevcut koruma | Salvage artık string içindeki süslü parantezleri koruyor; third regression. |
| L12 | 588-590 \| `\s` Unicode whitespace dahil NBSP'yi de eşler, AI çıktısında no-break space kalabilir \| | Yanlış alarm | Regex \s NBSP'yi de temizler; bunun NBSP bırakacağı iddiası ters. |
| L13 | 529 \| `[a-zA-Z-]{2,8}` language code regex'i region subtag'leri (es-419) desteklemez \| | Önceden düzeltilmiş / mevcut koruma | Dil kodu normalize helper bölgesel kodları temel dile indirger; desteklenmeyen özgül lehçe ayrı özellik. |
| L14 | 851, 853 \| `r'y(?=[aeiou])'` ve `r'v'` no-op entry'ler (yerine kendini koyar) \| | Tasarım / iyileştirme / kapsam ayrımı | No-op tablo kuralları temizlik; ses kaybı kanıtı yok. |
| L15 | 2712, 1721 \| `np.mean().astype(np.int16)` truncation (yuvarlama değil), ~0.5 LSB kayıp \| | Yanlış alarm | Int16 kanalların ortalaması int16 sınırlarının dışına taşmaz; yaklaşık yarım LSB yuvarlama farkı beklenen nicemleme. |
| L16 | 2165-2170 \| Quick language select DOM değerini set eder ama `setOtherPartyLanguage()` çağırmaz, radio'lar güncellenmez \| | Önceden düzeltilmiş / mevcut koruma | Quick language select setOtherPartyLanguage ile eşleniyor. |
| L17 | 2506-2510 \| `localStorage.getItem` boş string dönerse `getCurrentInputLang` sessizce `'tr'` kullanır \| | Tasarım / iyileştirme / kapsam ayrımı | Boş kayıtlı input lang için tr fallback kasıtlı güvenli varsayılan. |
| L18 | 966, 1052-1059 \| CSS `.with-translation` vs `.speaker-N` border rengi çakışması, speaker kazanır \| | Tasarım / iyileştirme / kapsam ayrımı | Konuşmacı kenarlığının önceliği görsel tasarım; veri veya kontrol kaybı gösterilmedi. |
| L19 | 2898, 2912-2913, 3263-3264 \| `copy-btn` class'ı kullanılıyor ama CSS'te tanımı YOK (inline style var) \| | Tasarım / iyileştirme / kapsam ayrımı | Inline style ile çalışabilen class adının tanımsız CSS'i tek başına bug değil. |
| L20 | 4791 \| `regenerateAnswer`'da `id` `escapeJsString`'den geçmiyor (şu an numeric, güvenli) \| | Yanlış alarm | Backend sayısal ID kontratı mevcut; keyfi kullanıcı dizesi geldiği gösterilmedi. |
| L21 | 4960-4963 \| `showAlert` en eski alert'i değil `firstChild`'i kaldırır, timer ile yarışabilir \| | Yanlış alarm | Alert'ler sona eklenir; firstChild en eski alert'tir, remove tekrarı güvenli. |
| L22 | 4429-4458 \| `appendInlineTranslationToItem` duplicate socket event'lerinde aynı çeviriyi tekrar yazar (görsel flicker) \| | Tasarım / iyileştirme / kapsam ayrımı | Aynı translation yeniden atanması veri çoğaltmaz; ölçülmüş flicker/performans kaybı gösterilmedi. |
| L23 | 3510 \| `const NL = '\n'` — Windows'ta Notepad'de düzgün görünmez \| | Yanlış alarm | B-FR-009 ile aynı; LF modern Notepad'de geçerli. |
| L24 | 2591 \| `updateTranslationStatus` `status` DOM elemanı kaldırılmışsa `classList.remove` no-op \| | Önceden düzeltilmiş / mevcut koruma | Durum timer'ı saklanıyor ve eleman guard var; kaldırılmış elemanın güncellenmemesi normal. |
| L25 | 2677 \| `checkInstalledModels` hatayı sadece `console.error` ile loglar, UI bilgilendirilmez \| | Tasarım / iyileştirme / kapsam ayrımı | Model listesi fetch hatası console'a kaydedilir; uygulama kontrollü kalır. Daha belirgin bildirim UX önerisi. |
| L26 | `test_smoke.py` \| 77 \| Sadece 1 Türkçe test case, early-return blanket skip test edilmez \| | Bu tur düzeltildi | Kısa sözler ve farklı diller report+complete suite içinde; Türkçe erken dönüş mevcut smoke ile birlikte korunuyor. |
| L27 | `test_cevap_onerisi.py` \| 107-109 \| `auto` caseler gerçek OpenAI API çağrısı yapar, para harcar (guard yok) \| | Tasarım / iyileştirme / kapsam ayrımı | test_cevap_onerisi.py açıkça canlı/ücretli eval; unit suite'e dahil değil. Bu tur sadece AST/mock test edildi. |
| L28 | `transkribe.py` \| 303 \| `import time as _time` fonksiyon içinde, her çağrıda tekrar import \| | Yanlış alarm | Yerel import cache'lidir; her çağrıda paketi yeniden yüklemez. |
| L29 | `_gen_phrases.py` \| 160-161 \| `_quick_phrases.json` gitignore'da değil, yanlışlıkla commit edilebilir \| | Tasarım / iyileştirme / kapsam ayrımı | Üretilmiş quick phrases dosyası gizli veri değil; yanlışlıkla commit riski gerçek bug değil, bu tur stage edilmedi. |
| L30 | `başlat.bat:14-24` \| `exit /b 0` eksik, sonraki satırlar yanlışlıkla çalışabilir \| | Bu tur düzeltildi | başlat.bat call npm.cmd start kullanıyor; hata/çıkış yolu batch çağrısından sonra artık çalışıyor. |
| L31 | `başlat.bat` (filename) \| `ş` harfi legacy CMD'de/code page 437'de bozuk görünebilir \| | Kesinleştirilemedi | Legacy codepage filename uyumu eski CMD/OS kurulumu gerektirir; desteklenen modern Windows'ta ASCII yardımcı ismi zorunlu değil. |
| L32 | `başlat-exe.bat:14-17` \| Unconditional success mesajı (exe çökse de "başlatıldı" yazar) \| | Bu tur düzeltildi | başlat-exe.bat artık process sağlığı iddia etmiyor, sadece başlatma isteğinin gönderildiğini bildiriyor. |
| L33 | `transkribe.bat:2` \| `.venv` tercihi yok (calistir.bat'ın aksine) \| | Bu tur düzeltildi | transkribe.bat .venv Python tercihi eklendi. |
| L34 | `main.js:114-118` \| `venvCandidates` Unix path'leri (`bin/python`) Windows'ta extra FS check yapar \| | Tasarım / iyileştirme / kapsam ayrımı | Birkaç existsSync Unix adayı taşınabilirlik desteği; ölçülebilir donma nedeni değil. |
| L35 | `main.js:369-374` \| `pythonProcess.pid` spawn sonrası senkron check, yüklü sistemde false negative \| | Yanlış alarm | child_process spawn pid başarılı process oluşturulunca atanır; undefined gerçek spawn failure olabilir, salt sistem yükü delili yok. |
| L36 | `preload.js:6` \| `DEBUG === '*'` çok katı, diğer npm paketlerinin DEBUG değeri ile çakışır \| | Tasarım / iyileştirme / kapsam ayrımı | DEBUG=* npm dev sözleşmesi; bütün npm DEBUG desenlerini uygulama debug anahtarına dönüştürme gereği yok. |
| L37 | `build.js:84` \| `ignore: (file) => !isKept(file)` double negative, refactor'da tersinebilir \| | Tasarım / iyileştirme / kapsam ayrımı | Boolean ignore dönüşümü packager API sözleşmesi; double-negative stil tercihi. |
| L38 | `build.js:59-73` \| `scanForLeaks` sadece yasaklı dosyaları kontrol eder, eksik asset'leri yakalamaz \| | Önceden düzeltilmiş / mevcut koruma | Build allowlist doğru; bu tur paket kritik kaynak hashleri ve varlık listesi ayrıca doğrulanacak. |
| L39 | `launcher_whisper.py:18-21` \| exe Popen sonrası `process.wait()` veya `poll()` yok, sessiz başarısızlık \| | Tasarım / iyileştirme / kapsam ayrımı | Launcher GUI'yi asenkron başlatır; parent'ın child bitene kadar beklemesi gerekmiyor. Uygulama kendi error path'ini yönetir. |
| L40 | `.env.example:1-10` \| MiniMax legacy, `OPENAI_API_KEY` eksik — yeni geliştiriciyi yanıltır \| | Önceden düzeltilmiş / mevcut koruma | .env.example OPENAI_API_KEY içeriyor; bu tur localhost/veri erişimi uyarısı eklendi. |
| L41 | `.gitignore:2` \| Sadece `.env`; `*key*`, `*.key` gibi pattern'ler yok \| | Tasarım / iyileştirme / kapsam ayrımı | Somut credential adları ignore edilmiş; *key* keyboard gibi masum kaynakları da saklar, kör glob uygulanmadı. |
| L42 | `BAŞLAT.md:111-127` \| Dosya ağacında `Whisper/` yazıyor, gerçek dizin `Whisper Live` \| | Bu tur düzeltildi | BAŞLAT.md örnek ağaç kökü Whisper Live olarak düzeltildi. |
| L43 | `SONNET_GOREVLERI.md:3` \| `claude-sonnet-5` referansı, kullanılan model `claude-opus-4-6` \| | Tasarım / iyileştirme / kapsam ayrımı | SONNET_GOREVLERI.md tarihli oturum kaydı; bugünkü model adıyla tarih yeniden yazılmaz. |
| L44 | `CLAUDE.md` \| Geçmiş güvenlik olayı belgelenmiş (dist/build'e key sızması) \| | Tasarım / iyileştirme / kapsam ayrımı | Geçmiş güvenlik olayını belgelemek bug değil; allowlist/content scan korunuyor. |
| L45 | `.claude/settings.local.json:16` \| `python3` Windows'ta standart değil \| | Tasarım / iyileştirme / kapsam ayrımı | Kullanıcı izin girdisinde python3 bulunması runtime seçimini değiştirmiyor; .claude izinleri değiştirilmedi. |
| L46 | `.claude/launch.json:8` \| Port 5096, uygulama portu 5000 ile uyuşmuyor (debug portu olabilir, açıklanmamış) \| | Tasarım / iyileştirme / kapsam ayrımı | Debug launch port metadata'sı ile gerçek PORT ayrı; .claude çalışma profili taşınabilir üretim başlatıcısı değil. |
| L47 | `launcher_whisper.py:25-30` \| `shell=True` ile "npm not found" hatası asla yakalanmaz \| | Önceden düzeltilmiş / mevcut koruma | Kontrollü npm.cmd çözümü ve launcher hata akışı; B-INF-004/BUG-05 ile aynı. |

## 2. DERIN_BUG_TARAMASI_RAPORU.md — 30 madde

| Kimlik | Rapordaki iddia | Sonuç | Gerekçe / kaynak / test |
|---|---|---|---|
| BUG-01 | Alt PTT (Bas-Konuş) Hedef Dil Tersliği ve "auto" Prompt İflası | Önceden düzeltilmiş / mevcut koruma | setAltPtt hedefi aiTargetLang üzerinden çözülüyor; auto/geçersiz hedef backend'de reddediliyor. PTT hedef regresyonu. |
| BUG-02 | Canlı İletişimde En Temel Kısa Yanıtların ("はい", "OK", "No", "Ne?", "你好") Halüsinasyon Sayılarak Silinmesi | Önceden düzeltilmiş / mevcut koruma | Kısa anlamlı Latin/CJK sözler korunuyor; test_short_speech_and_script. Bu tur kısa tekrar vurguları da korundu. |
| BUG-03 | Yapay Zeka Cevap Modunda Kısa Soruların Reddedilmesi (`[Yanitlanamadi: mesaj cok kisa]`) | Önceden düzeltilmiş / mevcut koruma | Kısa sorular mock sağlayıcıya ulaşıyor; test_short_answer_reaches_mock_provider. |
| BUG-04 | `transkribe.py` İçindeki `remove_overlap` Alt Dize Katliamı | Önceden düzeltilmiş / mevcut koruma | transkribe.remove_overlap keyfi substring silmiyor; kelime sınırı/gerçek overlap testleri. |
| BUG-05 | `launcher_whisper.py` Dosyasının Windows'ta `npm` Çalıştıramayıp Çökmesi | Önceden düzeltilmiş / mevcut koruma | launcher_whisper.py Windows npm.cmd çözümlemesi mevcut. |
| BUG-06 | Sekme Kapanırken / F5 Yenilemesinde `beforeunload` Mikrofon Kapatma İsteğinin İptal Olması | Önceden düzeltilmiş / mevcut koruma | beforeunload keepalive ve discard işareti; PTT lifecycle/frontend regresyonları. |
| BUG-07 | DeepL Pro Lisanslı API Anahtarlarının Desteklenmemesi | Önceden düzeltilmiş / mevcut koruma | DeepL free/pro endpoint seçimi test_deepl_snapshot_endpoint ile doğrulandı. |
| BUG-08 | `set_response_model` Fonksiyonunda Eski Model Takma Adlarının Kontrol Edilmemesi | Önceden düzeltilmiş / mevcut koruma | Model alias normalize edilerek allowlist'e giriyor; model regression. |
| BUG-09 | PTT Mikrofon Sonuçlarına `data-transcription-id` Eklenmemesi (Arama ve Budama İflası) | Önceden düzeltilmiş / mevcut koruma | PTT düğümleri transcription ID taşıyor; ortak arama/budama akışı. |
| BUG-10 | Sayfa Yenilemede ve Geri Yüklemede Sayaç Enflasyonu (`totalCount` Çifte Sayım) | Önceden düzeltilmiş / mevcut koruma | Hydration count canlı eklemeden ayrılmış; instance/hydration nesli çifte sayımı önlüyor. |
| BUG-11 | Çeviri Ayrıştırmada Metin İçi İki Nokta Üst Üste (`:`) Kırpılması | Önceden düzeltilmiş / mevcut koruma | Yapılandırılmış çeviri alanı kullanılıyor; metin içi kolon korunuyor. |
| BUG-12 | Otomatik Çeviride Paralel Çifte OpenAI İsteği Gönderilmesi | Önceden düzeltilmiş / mevcut koruma | Otomatik translate trigger/backend translation yolu ayrılmış, pending request koruması var. |
| BUG-13 | `MicRecorder.stop_stream()` İçinde PortAudio C-Pointer Yarış Durumu | Önceden düzeltilmiş / mevcut koruma | Recorder cleanup sahipliği ve lock koruması; test_mic_cleanup_exactly_once. Native driver stress testi ayrı. |
| BUG-14 | Kanji Ağırlıklı Japonca Konuşmaların Çince (`zh`) Algılanması | Önceden düzeltilmiş / mevcut koruma | Kana içeren/ASR ja bildiren kanji metni ja kalıyor; test_short_speech_and_script. |
| BUG-15 | `transkribe.py` Arka Plan İş Parçacığından Tkinter GUI'ye Güvensiz Erişim | Önceden düzeltilmiş / mevcut koruma | transkribe worker UI güncellemeleri after üzerinden; eski thread erişimi düzeltilmiş. |
| BUG-16 | Konuşmacılar Sıfırlandığında HuggingFace Token'ının Kalıcı Olarak Silinmesi | Önceden düzeltilmiş / mevcut koruma | Reset ad/profil durumunu sıfırlar, HF token'ı korur; clear token ayrı endpoint. Regression. |
| BUG-17 | `load_model` Sırasında Eski Modelin VRAM'den Boşaltılmadan Yenisinin Yüklenmesi ve Sessizce CPU'ya Düşme | Tasarım / iyileştirme / kapsam ayrımı | Yeni model yüklenemezse eski model korunuyor ve hata görünür; eski modeli önce silmek geri dönüşü yok eder. Gerçek VRAM kıtlığı testi yapılmadı. |
| BUG-18 | `stop_capture` ile `_transcribe_audio` Arasındaki Mantıksal Çelişki ve Son Konuşmanın Çöpe Atılması | Tasarım / iyileştirme / kapsam ayrımı | Stop iptal semantiği taşır; devam eden ses/AI sonucu kesilir. Son sözü tamamlatmak için flush var. Graceful-drain özelliği vaat edilmiyor. |
| BUG-19 | `_detect_script_lang` İçinde Yunanca (`el`) Alfabesinin Bulunmaması ve Kiril Alfabesinin Zorla Rusça Yapılması | Önceden düzeltilmiş / mevcut koruma | Yunanca algısı ve ASR uk/bg gibi uyumlu tahmini koruma mevcut. Kiril yazısı tek başına kesin dil kanıtı değildir. |
| BUG-20 | `update_speaker_name` Fonksiyonunun Mevcut Transkript Kayıtlarını ve DOM Rozetlerini Güncellememesi | Önceden düzeltilmiş / mevcut koruma | Speaker rename geçmiş kayıt+socket/UI güncelleme yoluna sahip; geç diarization güncel adı kullanıyor. |
| BUG-21 | `saveHFToken` Fonksiyonunda Token'ı Temizleme / Sıfırlama İmkânının Olmaması | Önceden düzeltilmiş / mevcut koruma | saveHFToken boş değerle backend/token storage temizliyor. |
| BUG-22 | `downloadTranscriptions` İçinde `URL.revokeObjectURL(url)` Senkron Çağrısının İndirmeyi İptal Edebilmesi | Önceden düzeltilmiş / mevcut koruma | Object URL bir saniye sonra serbest bırakılıyor; indirme tıklamasıyla aynı tick değil. |
| BUG-23 | `pruneTranscriptionList` İçinde `seenTranscriptionIds` Set'inin Hiç Temizlenmemesi | Önceden düzeltilmiş / mevcut koruma | Budama seenTranscriptionIds/transcriptionTexts temizliyor; stale duplicate DOM dışı kaydı map'e geri doldurmuyor. |
| BUG-24 | `_process_mic_audio` İçerisinde `conversation_turns.append` Çağrısının Kilitsiz Yapılması | Önceden düzeltilmiş / mevcut koruma | PTT conversation append lifecycle kilidinde; gerçek stop generation guard testi. |
| BUG-25 | `_resample_filter` İçinde Eşit Örnekleme Oranlarında Nyquist Frekans Çökmesi (`ValueError`) | Önceden düzeltilmiş / mevcut koruma | Aynı-rate kısa devresi ve VAD tam frame boyu helper; test_resample_identity_and_vad_shapes. FIR helper'a doğrudan hatalı parametre aktif yol değil. |
| BUG-26 | Alt-PTT Tuş Kombinasyonu Kontrolü Olmaması ve Her Alt+Tab / Alt+F4 Basışında Hayalet Kayıt Başlatılması | Önceden düzeltilmiş / mevcut koruma | Alt gecikmesi/kombinasyon/blur iptali uygulanmış; frontend regresyonları. |
| BUG-27 | `get_context_prompt()` Fonksiyonunun Kelimeleri ve Karakterleri Ortadan Rastgele Kesmesi | Önceden düzeltilmiş / mevcut koruma | Context boşluklu metinde kelime sınırından kesilir. Python slicing UTF-8 byte bölmez; boşluksuz yazılarda anlam sınırı için NLP yok. |
| BUG-28 | 0.5 Saniyeden Kısa Cümlelerin VAD Tarafından Sessizce Çöpe Atılması | Önceden düzeltilmiş / mevcut koruma | Kısa final eşik 0.2sn; eski 0.5sn iddiası güncel değil. Gerçek kısa ses tanıma kalitesi donanım/model testi gerektirir. |
| BUG-29 | `main_helpers.js` İçindeki `isOwnedWhisperBackend` Fonksiyonunun Windows 8.3 Kısa Dosya Yollarında Hatalı Kapanması | Tasarım / iyileştirme / kapsam ayrımı | 8.3 kısaltılmış yabancı process sahipliği doğrulanamazsa öldürülmez. Sadece script adıyla kill önerisi başka projeyi öldürebilir; güvenlik adına fail-closed korunuyor. |
| BUG-30 | `_apply_exact_pronunciation_override` Fonksiyonunun Cümle İçi Terimleri Yoksayması | Tasarım / iyileştirme / kapsam ayrımı | Exact override adının sözleşmesi tam ifade. Cümle içi terimler prompt'a verilir; native karakter indisleri Türkçe fonetiğe doğrudan taşınamaz. |

## 3. P0/P1/P2/P3 ek raporu — 19 madde

| Kimlik | Rapordaki iddia | Sonuç | Gerekçe / kaynak / test |
|---|---|---|---|
| BUG-P0-01 | Alt PTT mikrofonu hedef dili yanlış gönderiyor — kullanıcı yabancı dilde okunuş ALAMIYOR | Önceden düzeltilmiş / mevcut koruma | BUG-01 ile aynı; Alt PTT hedef çözümü mevcut. |
| BUG-P0-02 | CJK / kısa onay kelimelerinin (「ええ」「嗯」「네」) halüsinasyon filtresi tarafından sessizce silinmesi | Önceden düzeltilmiş / mevcut koruma | BUG-02 ile aynı; kısa CJK/Latin testleri geçiyor. |
| BUG-P0-03 | Kısa CJK soruları AI cevap modunda reddediliyor — kullanıcı cevap alamıyor | Önceden düzeltilmiş / mevcut koruma | BUG-03 ile aynı; kısa sorular sağlayıcıya ulaşıyor. |
| BUG-P1-01 | `process_mic_audio` (Alt PTT) `_session_id` guard'ı hiç kullanmıyor — stop+start arasında eski PTT yeni oturuma sızıyor | Yanlış alarm | Reproducer yalnız _session_id değiştiriyor, gerçek stop'un artırdığı _result_generation'ı sabit tutuyor. Gerçek stop testi eski mic emit/yazıyı reddediyor. |
| BUG-P1-02 | `transcribe_executor` (çeviri kuyruğu) sınırsız büyüyebilir ve backlog guard ID farkına dayanır | Önceden düzeltilmiş / mevcut koruma | Çeviri backlog ayrı canlı sıra numarasıyla hesaplanıyor; PTT ID'leri kuyruğu zehirlemiyor, stale tamamlanan iş de reddediliyor. |
| BUG-P1-03 | Mikrofon PTT kaydı iş kuyruğu doluysa sessizce kayboluyor | Önceden düzeltilmiş / mevcut koruma | Slot kayıt başlamadan rezerve ediliyor, doluysa429; test_full_ptt_queue_rejected_before_recording ve slot release. |
| BUG-P1-04 | Capture thread'i durdurulurken `_active_audio_stream` race koşulu — hızlı stop+start'ta stream sızıntısı | Önceden düzeltilmiş / mevcut koruma | Stream detach sahipliği lifecycle altında; aktif capture thread'in C pointer'ı başka thread'den kapatılmıyor. Native sürücü takılması ayrı H. |
| BUG-P1-05 | Mikrofon PTT `_mic_executor` kapanırken worker hâlâ çalışıyorsa ses callback'i sessizce ölür | Tasarım / iyileştirme / kapsam ayrımı | shutdown(wait=False) çalışan worker'ı öldürmez; interpreter çıkışı kullanıcı oturumu sonudur. Kapanışta yeni PTT işinin kabulü garanti edilmez. |
| BUG-P1-06 | `escapeJsString` HTML attribute'unda `&` entity referansı saldırısına karşı savunmasız | Önceden düzeltilmiş / mevcut koruma | escapeJsString entity round-trip (&apos;/&quot;) koruması; test_followup_frontend. |
| BUG-P2-01 | `transkribe.py` SRT timestamp overlap — birleştirme modunda cue çakışması | Önceden düzeltilmiş / mevcut koruma | SRT merge monotonic zamanları ve metin kayıpsızlığı test_merge_output_does_not_overlap_or_lose_text. |
| BUG-P2-02 | `_find_quiet_split_index` aşırı kısa tamponlarda tampon sonunu döndürür — kelime ortası kesim | Yanlış alarm | Çok kısa tamponda tampon sonu geçerli sınırdır; yeterli pencere yokken sessizlik noktası uydurulmaz. test_quiet_split_tiny_buffers. |
| BUG-P2-03 | AI cevap modunda "dedup" büyük-küçük harf ve Unicode normalization farklarını kaçırır | Bu tur düzeltildi | NFC/casefold ve Türkçe birleşen nokta düzeltildi; iki çağrıdan gelen gerçekçi mock seçeneklerle Unicode regresyonu. |
| BUG-P2-04 | AI answer modunda `detected_lang` yalnız ilk çağrıdan alınır — çakışan tespitlerden kullanıcı görmez | Önceden düzeltilmiş / mevcut koruma | Her seçenek kendi language alanını koruyor; üst detected_lang sadece fallback. test_option_retains_its_detected_language. |
| BUG-P2-05 | `escapeJsString` `</script>` injection'ı için değil ama attribute'lar arası boşluk bozabilir | Yanlış alarm | HTML attribute escape round-trip test edildi; boşluk tek başına attribute kapatmaz. P1-06 entity konusu ayrı düzeltilmiş. |
| BUG-P2-06 | Whisper transkripsiyonunda `_partial_executor` shutdown'da inflight worker ölür, kullanıcı "hayalet" partial görür | Yanlış alarm | shutdown running worker'ı öldürmez; session/utterance guard stale partial'ı reddeder. UI hide timer var. |
| BUG-P2-07 | `_transcribe_audio` `while` loop session_id kontrolü `audio_queue.get(timeout=1)` BLOĞU sırasında stale kalabilir | Bu tur düzeltildi | Model kilidi alındıktan sonra session/result/is_running yeniden kontrol ediliyor; stale audio modele girmiyor testi. |
| BUG-P3-01 | `_turkish_lower` `'i̇' → 'i'` çift dönüşüm — bazı path'lerde tekrar uygulanabilir | Yanlış alarm | _turkish_lower birleşen i noktasını temizleme kararlı normalizasyon; aynı uygulama harf kaybı göstermiyor. |
| BUG-P3-02 | `_gen_phrases.py` çıktısı `_quick_phrases.json` üretiyor ama dosya commit edilmemiş | Tasarım / iyileştirme / kapsam ayrımı | Üretici çıktısının commit edilmemesi çalışan QUICK_PHRASES tablosunu bozmaz; yeni feature/iş akışı kararı. |
| BUG-P3-03 | `escapeJsString` `\u2028` `\u2029` (line separator / paragraph separator) escape etmiyor | Yanlış alarm | Hedef modern V8 Unicode U+2028/U+2029 string literal kabul ediyor; eski ECMAScript motoru hedeflenmiyor. |

## 4. “6 alan, 153 bug” ek raporu — metindeki 113 ifade

| Kimlik | Rapordaki iddia | Sonuç | Gerekçe / kaynak / test |
|---|---|---|---|
| S-C1 | **`buyedektir.py:3180,3213`** — `_lifecycle_lock` pyannote lazy-load boyunca tutuluyor (dakikalarca); `/api/stop` bile kilitlenir. | Önceden düzeltilmiş / mevcut koruma | Lazy diarizer setup lifecycle kilidi dışında; test_stop_during_lazy_load_does_not_block_or_restart. |
| S-C2 | **`buyedektir.py:3836-3935`** — Manuel `acquire/release` çifti (context manager değil); 100 satırlık blokta herhangi bir raise lock'ı kalıcı sızdırır, tüm endpoint'ler donar. | Yanlış alarm | commit_lock_held/exception finally release mevcut; rapor bu yolu atlıyor. |
| S-C3 | **`buyedektir.py:715`** — Salvage regex `\{[^{}]*\}` JSON içindeki `{` literal'lerinde sessizce option kaybediyor. | Önceden düzeltilmiş / mevcut koruma | Salvage JSON string içindeki braces korunuyor; third regression. |
| S-C4 | **`buyedektir.py:5140 vs 759`** — Prompt "TAM 2 seçenek" diyor ama parser sınır yok; model 3-4 dönerse UI 6-8 kart basıyor. | Bu tur düzeltildi | Her answer çağrısı en fazla2 seçenek, final en fazla4; complete cap testi. |
| S-C5 | **`buyedektir.py:5168-5201`** — 30 s `as_completed` timeout paylaşımlı; bir call yavaşsa diğerinin partial'i çöpe gider ve "AI önerisi başarısız" toast'u zaten ekranda görünen sonuçla çelişir. | Yanlış alarm | Tamamlanan futures ham yanıtları TimeoutError sonrası mevcut raws listesinde kalıyor. |
| S-C6 | **`buyedektir.py:537`** — `_finalize_pronunciation` koşulsuz `q→k`; İspanyol `queso`→`kueso` (silent u kalmalıydı). | Bu tur düzeltildi | İspanyolca native qu[e/i]→k; queso→keso testi. |
| S-C7 | **`buyedektir.py:538`** — Koşulsuz `x→ks`; Vietnamca `xin`→`ksin`. | Bu tur düzeltildi | Vietnamca native x→s; xin→sin testi. |
| S-C8 | **`buyedektir.py:946-960`** — İtalyanca `giorno` non-idempotent: ilk pass `corno`, ikinci pass `korno` (c→k re-handle). | Bu tur düzeltildi | Native giorno→corno, hazır fonetik ikinci native kurala sokulmuyor. phonetic=True contract testi. |
| S-C9 | **`buyedektir.py:1028,1037`** — İspanyolca `guitarra` non-idempotent: `gitarra→hitarra→itarra`. | Bu tur düzeltildi | Native guitarra→gitarra ve hazır fonetik korunması; phonetic contract testi. |
| S-C10 | **`buyedektir.py:1101-1111`** — Slovakça `džem` non-idempotent: `cem→tsem`. | Bu tur düzeltildi | Native džem→cem ve hazır fonetik korunması; phonetic contract testi. |
| S-C11 | **`buyedektir.py:962-984`** — Portekizce guide "kelime sonu o→u" diyor ama fonksiyon uygulamıyor (`obrigado` kalıyor). | Bu tur düzeltildi | Portekizce vurgusuz terminal native o→u; obrigado→obrigadu. Hazır fonetik değiştirilmiyor. |
| S-C12 | **`buyedektir.py:2758-2837`** — `_is_likely_hallucination` YouTube outro'larını yakalamıyor: `Thank you for watching`, `Please subscribe`, `See you next time`, `Danke fürs Zuschauen`, `Merci d'avoir regardé`, `感谢您的观看`, `شكراً للمشاهدة`. | Tasarım / iyileştirme / kapsam ayrımı | Bilinen tam engine marker'ları genişletildi; tüm dillerde gerçek vedaları silmek doğru değil. See you next time gibi doğal sözler için kör blacklist uygulanmadı. |
| S-C13 | **`buyedektir.py:5061-5076`** — `target_lang='auto'` + script belirsiz → tüm 6 stil bloğu + çelişen kurallar (`ar: ASLA tire` ile `ja: tire kullan` aynı anda). | Bu tur düzeltildi | Auto/belirsiz hedefe altı çelişen dil bloğu birden verilmez; complete prompt testi. |
| S-C14 | **`templates/index.html:3512 vs 3633/3681/3780`** — `transcriptionTexts` map'e **sayısal** key yazılıyor, prune **string** key arıyor → `hasOwnProperty` her zaman false, **sızıntı sınırsız**. | Yanlış alarm | JS object sayısal anahtarı string'e çevirir; test_third_frontend. |
| S-C15 | **`templates/index.html:3011-3023`** — `disconnect` handler'ı `_pendingAiRequests`/`_activeAnswerRequests` map'lerini temizlemiyor → sonraki reconnect'te 💬 butonu **kalıcı ölü**. | Yanlış alarm | HTTP yanıtı socket'ten bağımsız; pending timeout temizliği var. Reconnect kalıcı kilit kanıtı yok. |
| S-C16 | **`templates/index.html:5254-5320`** — AI fetch'inde `AbortController`/`setTimeout` yok → backend askıda kalırsa buton **sonsuza dek** `⏳ Yükleniyor...`. | Önceden düzeltilmiş / mevcut koruma | AI istemci timeout/abort ve pending cleanup mevcut. |
| S-C17 | **`templates/index.html:2553`** — Speaker avatar initials `speaker.name.substring(0,2)` **escapesız** `innerHTML`'e yazılıyor → self-XSS. | Önceden düzeltilmiş / mevcut koruma | Avatar initials escape mevcut; iki karakterlik ad tek başına gösterilmiş exploit değildi. |
| S-C18 | **`main.js:91`** — Türkçe Windows'ta `netstat -ano` `DİNLENİYOR` döndürür, `"LISTENING"` filtresi **tüm satırları atlar** → orphan python hiç öldürülmez, app ikinci açılışta bağlanamaz. | Önceden düzeltilmiş / mevcut koruma | netstat satırı yapısal alanlarla çözülüyor; yerelleştirilmiş durum sözcüğüne bağlı değil. helper test. |
| S-C19 | **`main.js:465-470`** — `HOST` env var Electron'da iletilmiyor (`.env`'de `HOST=0.0.0.0` işe yaramaz). | Yanlış alarm | spawn env ...process.env taşır; HOST kaybolmuyor. |
| S-C20 | **`buyedektir.py:144-158`** — `transcriptions.txt` rotation `os.replace` Windows `ERROR_SHARING_VIOLATION`'da sessizce başarısız → dosya **sınırsız büyür**, `.1` hiç oluşmaz. | Bu tur düzeltildi | Replace paylaşım hatasında copy+fsync+truncate, .1/.2/.3 yedek denemesi ve uyarı. Tüm hedefler kilitliyse yeni metin korunur, mutlak disk sınırı garanti değil. |
| S-C21 | **`buyedektir.py:1930-1943`** — JSON corrupt → DEBUG log + sonraki save boş payload yazıp **tüm speaker name + HF token'ı siliyor**. | Önceden düzeltilmiş / mevcut koruma | Bozuk profil yüklenirse sonraki otomatik yazılar bloke; fourth tests. Eski dosya zorla resetlenmiyor. |
| S-H1 | **`buyedektir.py:3408-3421`** — Paused capture + cihaz kopunca `except:pass` sonsuz %100 CPU (consecutive_errors artırılmıyor). | Önceden düzeltilmiş / mevcut koruma | Paused read hataları da bounded retry; third test50read49sleep. |
| S-H2 | **`buyedektir.py:3453-3496`** — 4 queue overflow path'i sessizce eski item'ı drop ediyor (PTT release / manual flush / max-utterance). | Bu tur düzeltildi | Beş capture kuyruğu yolu tek _enqueue_audio; Full/Empty yarışı retry edilir; complete test. |
| S-H3 | **`buyedektir.py:4091, 3926, 4680`** — `TRANSLATE_MAX_LAG` sayımı PTT/mic ID'lerini de içeriyor; in-flight live translation yanlışlıkla iptal. | Önceden düzeltilmiş / mevcut koruma | Backlog live translation sequence kullanıyor; PTT ID bağımsız. |
| S-H4 | **`buyedektir.py:4282-4296`** — DeepL config lock'u 5-10 s network test'i boyunca tutuluyor → live pipeline donuyor (lock convoy). | Önceden düzeltilmiş / mevcut koruma | DeepL remote test config lock dışında; third lock testi. |
| S-H5 | **`buyedektir.py:5154-5201`** — Zaman aşımına uğrayan future'lar cancel edilmiyor; token yanar, `ai_options_partial` kaybolur. | Bu tur düzeltildi | AI timeout'ta henüz başlamamış futures cancel edilir. Running API çağrısı Future.cancel ile kesilemez. |
| S-H6 | **`buyedektir.py:5227-5230`** — `.lower()` Türkçe `İ`/`i`+U+0307 ve Alman `ß`→ss fold'unu kaçırıyor → gerçek duplicate'ler kalıyor. | Bu tur düzeltildi | Backend NFC casefold ve frontend karşılıkları; Unicode/nonlatin testi. |
| S-H7 | **`buyedektir.py:5033-5100`** — `target_directive`/`translation_label` `static_head` içinde → dil her değiştiğinde OpenAI prefix cache invalidation. | Tasarım / iyileştirme / kapsam ayrımı | Hedef dil/statik dil kuralları değişince cache prefix değişmesi normal; aynı hedefte statik prefix değişken mesajdan önce. |
| S-H8 | **`buyedektir.py:5150`** — `request_id` validate edilmiyor; aynı id ile iki concurrent request partial'ları çapraz karıştırır. | Tasarım / iyileştirme / kapsam ayrımı | UI request ID rastgele üretiliyor; yanlışlıkla çakışma tekrarlanmadı. Ortak yerel oturum çok-kullanıcılı erişim izolasyonu değildir. |
| S-H9 | **`buyedektir.py:5203`** — İkisi de başarısız → HTTP 200 `{success:False}` (5xx olmalı). | Yanlış alarm | HTTP200+success:false mevcut istemci sözleşmesi, tek başına hata değil; istemci alanı kontrol ediyor. |
| S-H10 | **`buyedektir.py:5179-5249`** — Partial emit ile HTTP response canonical normalization uyuşmazlığı → UI flicker. | Bu tur düzeltildi | Partial/final aynı parser ve çağrı cap'i kullanıyor, dedup normalize uyumu artırıldı. Kanonik final sıralaması güncellenebilir. |
| S-H11 | **`buyedektir.py:2694-2750`** — `_detect_script_lang` Latin harfleri denominator'a katmıyor → `"OK, ありがとう"` için `ja` döndürüyor. | Tasarım / iyileştirme / kapsam ayrımı | Script helper dil sınıflandırıcısı değil; uyumlu ASR tahminini korur. Karışık OK/ありがとう metninde kesin oran eşiği dil gerçeği sayılmaz. |
| S-H12 | **`buyedektir.py:3729-3789`** — Session guard `model.transcribe`'tan sonra; hızlı Stop+Start'ta boşa ASR pass + audio kaybı. | Bu tur düzeltildi | Model kilidinden sonra stale guard; complete stale test. |
| S-H13 | **`templates/index.html:5374-5381`** — `openReplyTexts` snapshot'ı collapsed panel'leri her partial'da yeniden açıyor. | Bu tur düzeltildi | renderAiResult eski collapsed durumunu koruyor; complete frontend gerçek fonksiyon testi. |
| S-H14 | **`templates/index.html:3992-4031`** — `searchFullTranscriptHistory` race; eski arama yeni sonucu eziyor. | Önceden düzeltilmiş / mevcut koruma | Search hydration generation eski yanıtın yeni aramayı ezmesini engelliyor; third frontend. |
| S-H15 | **`templates/index.html:2377,2581,3257`** — 3 settings POST'unda error handling yok → offline'ta UI/server state diverges. | Bu tur düzeltildi | Speaker/translation/sliders ayarları sıralı yazılıyor; son başarısızlık en son teyitli değere geri dönüyor. |
| S-H16 | **`templates/index.html:2281+` (22 site)** — `localStorage.getItem` try/catch dışında; incognito'da tüm UI init çöker. | Bu tur düzeltildi | whisperStorage bütün index localStorage erişimini korur, geçici bellek fallback ve bir uyarı; complete frontend. |
| S-H17 | **`templates/index.html:3011-3023`** — Disconnect capture/pause state resetlemiyor → 60 s boyunca stale UI. | Tasarım / iyileştirme / kapsam ayrımı | Socket disconnect capture'ın gerçekten durduğu anlamına gelmez; UI bunu stop diye göstermemeli. Bağlantı durumu ayrı. |
| S-H18 | **`templates/index.html:5216,5220`** — DEBUG log spam + `Object.keys(transcriptionTexts)` leak on miss. | Bu tur düzeltildi | Hata console logu tüm transkript ID listesini dökmüyor. |
| S-H19 | **`templates/index.html:5227-5321`** — Re-click `_pendingAiRequests` sızıntısı. | Yanlış alarm | Reclick için aktif request guard ve timeout cleanup var; kalıcı pending sızıntısı gösterilmedi. |
| S-H20 | **`buyedektir.py:155-156`** — `transcriptions.txt` yazımında fsync yok → güç kaybında son birkaç dakika uçar (konuşma log'u en önemli dosya, en az dayanıklı). | Tasarım / iyileştirme / kapsam ayrımı | Normal append close flush eder, güç kesintisi dayanıklılığı fsync garantisi yok. Her cümlede sync I/O canlı thread'i yavaşlatabilir; rotasyon yedeği bu tur fsync. |
| S-H21 | **`main.js:42,510-570`** — Restart cap'i 30 s "stable" sonrası resetleniyor; ömür boyu 3 değil, pencereli 3. Trip'te `app.quit()` çağrılmıyor → 60 s daha dönüyor. | Bu tur düzeltildi | Restart sınırı tükenince app.quit, görünmez canlı process bırakılmaz; cached Python komutu reset mantığı güncellendi. |
| S-H22 | **`main.js:496-521`** — Python <1 s'de çıkarsa hızlı fail short-circuit yok → 9 s boşuna polling. | Yanlış alarm | Child close activeBackendNonce=null yapıyor; eski readiness poll geçersizleşir. |
| S-H23 | **`main.js:222-233,324-339`** — `will-navigate` + `setWindowOpenHandler` yok → XSS renderer'ı evil.com'a yönlendirebilir. | Önceden düzeltilmiş / mevcut koruma | Navigation ve window-open politikası mevcut; harici sayfa renderer içinde açılmıyor. |
| S-H24 | **`buyedektir.py:3907-4691`** — `transcriptions.txt` LF yazıyor, eski Notepad/Excel importer'ları bozar. | Yanlış alarm | LF modern Windows hedefinde geçerli. |
| S-H25 | **`buyedektir.py:22-27`** — `.env` import-time bir kez yükleniyor; hot-reload yok (AGENTS.md "API key reloadable" diyor, değil). | Tasarım / iyileştirme / kapsam ayrımı | .env başlangıçta yüklenir; runtime değişiklik endpointleri ayrı. Dosya watcher vaat edilmemiş. |
| S-H26 | **`buyedektir.py:2841`** — Pure-digit `'12345'` hallucination değil, geçiyor. | Yanlış alarm | Sayılar gerçek konuşma olabilir; sırf rakam diye hallucination silme yanlış. |
| S-H27 | **`buyedektir.py:2764`** — Strip pattern `<>` kapsamıyor; `<music>`, `<\|nospeech\|>` sızıyor. | Önceden düzeltilmiş / mevcut koruma | Tam engine angle tag filtreleri mevcut; gerçek metin içinde angle var diye tüm söz silinmez. |
| S-H28 | **`buyedektir.py:2752-2877`** — Audio duration/text ratio bakılmıyor (5 dakika → 3 kelime şüpheli). | Tasarım / iyileştirme / kapsam ayrımı | Duration/text oranı yeni heuristic; kısa sözleri yanlış silebilir, gerçek ses kalibrasyonu olmadan uygulanmadı. |
| S-H29 | **`buyedektir.py:2748`** — Unknown Cyrillic lang → `'ru'` fallback (Azerbaycan/Bulgar/Ukrayna için yanlış). | Tasarım / iyileştirme / kapsam ayrımı | Kiril script ru/uk/bg arasında tek başına yeterli değil; mevcut uyumlu ASR dili korunur, unknown fallback kesin sınıflandırma değildir. |
| S-H30 | **`buyedektir.py:543-547`** — Fallback `_finalize_pronunciation` <30% Turkish-readability gate'i İbranice/Tayca/Hintçe'yi tamamen düşürüyor. | Yanlış alarm | NFKD Kiril/Kana'yı Latin'e translitere etmez; önerilen çözüm yanlış. |
| S-H31 | **`buyedektir.py:2849-2859`** — 4-token consecutive repetition legitimate emphasis'i yakalıyor (`ja ja ja ja`, `OK OK OK OK`). | Bu tur düzeltildi | Kısa4tekrar vurgu20karakter eşiğiyle korunur; uzun döngü yine elenir. |
| S-H32 | **`buyedektir.py:2776-2778`** — `'Thank you for watching!'` exact-word match'i kaçırıyor. | Tasarım / iyileştirme / kapsam ayrımı | Tam/noise örnekleri filtreleniyor; Thank you for watching gerçek vedası bağlamsız her durumda silinmedi. C12 ile aynı politika. |
| S-M1 | transcribe loop dış try/except yok | Yanlış alarm | Transcribe döngüsünde outer try zaten var; hata emit'inin kendi exception'ı bu tur korundu. |
| S-M2 | socketio.emit + dosya yazma `_lifecycle_lock` altında | Tasarım / iyileştirme / kapsam ayrımı | Commit sırasında emit/dosya kilidi sıralama ve stale izolasyonu sağlıyor. Ölçülmüş deadlock yok; sırf kilidi parçalamak güvenli performans fix'i değil. |
| S-M3 | partial worker stale session state mutate ediyor | Önceden düzeltilmiş / mevcut koruma | Partial finally/session guard eski işin yeni state'i sıfırlamasını engelliyor; smoke partial testi. |
| S-M4 | `shutdown(wait=False)` future cancel etmiyor | Tasarım / iyileştirme / kapsam ayrımı | wait=False pending future iptal etmez, ama kapanış semantiği zaten iptal/çıkış. Pending PTT slot callback'lerini rastgele kaldırmak ayrı risk; running worker öldürülmez. |
| S-M5 | `_command_lock→_lifecycle_lock` ordering fragility | Yanlış alarm | Command→lifecycle yönü tek başına döngü değildir; ters yönde bekleyen yol gösterilmedi. |
| S-M6 | TOCTOU `audio_queue.empty()` | Tasarım / iyileştirme / kapsam ayrımı | queue.empty partial için öncelik ipucu, veri tüketimi değil. Model lock serileştirir; sonradan gelen final kısa süre bekleyebilir. |
| S-M7 | PTT-mic `_final_model_pending` set etmiyor. | Tasarım / iyileştirme / kapsam ayrımı | Mic de model lock alır; final_model_pending işaretinin olmaması correctness bug değil, PTT öncelik planlama özelliği. |
| S-M8 | Top-level JSON array AttributeError | Yanlış alarm | Parser isinstance kontrolüyle üst düzey array'i reddediyor. |
| S-M9 | `socketio.emit` global → cross-talk | Tasarım / iyileştirme / kapsam ayrımı | Global SocketIO tek yerel ortak konuşma oturumu sözleşmesi; çok-kullanıcı tenant izolasyonu yok. .env uyarısı. |
| S-M10 | `except Exception: logger.debug` swallow | Tasarım / iyileştirme / kapsam ayrımı | Yer/beklenen sonuç/reproducer verilmeden genel debug except iddiası üretim bug'ı doğrulamıyor. |
| S-M11 | `_clean_json_object` tek fence strip | Bu tur düzeltildi | 3+ fence/JSON case regex; complete test. |
| S-M12 | test gaps | Bu tur düzeltildi | Yeni sentetik testler ve mevcut78Python/5Node dosyası; gerçek cihaz kapsamı açıkça ayrı. |
| S-M13 | placeholder hybrid leak | Kesinleştirilemedi | Hangi placeholder/girdi yolunun sızdığı verilmemiş; somut karşı örnek yok, kesin bug sayılmadı. |
| S-M14 | `request_id` collision | Tasarım / iyileştirme / kapsam ayrımı | H08 ile aynı request ID/ortak yerel oturum değerlendirmesi. |
| S-M15 | legacy MINIMAX env vars. | Tasarım / iyileştirme / kapsam ayrımı | MINIMAX eski provider değişkenleri bilerek kullanılmıyor. |
| S-M16 | 4 queue overflow path lag warning göndermiyor (sadece silence flush) | Bu tur düzeltildi | Bütün5 enqueue yolu ortak warning/throttle kullanıyor. |
| S-M17 | MicRecorder `_command_lock` start'ta yok | Yanlış alarm | PTT route recorder start/stop'u command lock ile serileştiriyor; doğrudan sınıf çağrısı üretim endpointiyle karıştırılmış. |
| S-M18 | cpu_threads container limit'i görmüyor | Tasarım / iyileştirme / kapsam ayrımı | Uygulama Windows masaüstü hedefli; container CPU quota ayrı dağıtım hedefi, CPU override mevcut. |
| S-M19 | `_partial_snapshot` GC churn | Tasarım / iyileştirme / kapsam ayrımı | Partial snapshot3.5-7sn ile sınırlı; tekrar allocation tek başına sızıntı değil. |
| S-M20 | int16/float32 upcast intermediate float64. | Yanlış alarm | Downmix/resample float ara dizi bounded ses uzunluğu; sayısal taşma örneği yok. |
| S-M21 | Reading-mode Escape listener leak | Yanlış alarm | Reading listener overlay ilk yaratılırken bir kez; kapama DOM'u yok etmiyor. |
| S-M22 | `_partialHideTimer` reset'te clear değil | Önceden düzeltilmiş / mevcut koruma | clearPartialPreview timer'ı temizliyor; reset çağrısı bu yolu kullanıyor. |
| S-M23 | search filter no-debounce | Tasarım / iyileştirme / kapsam ayrımı | Görünen DOM100ile sınırlı, arama generation korumalı; debounce performans önerisi, ölçüm yok. |
| S-M24 | API key plaintext localStorage | Tasarım / iyileştirme / kapsam ayrımı | localStorage/profilde düz metin anahtarlar yerel kullanıcı tehdidi olarak mevcut; OS vault geçişi yapılmadı. CSP/storage fallback bunu şifrelemez; .env localhost uyarısı eklendi. |
| S-M25 | speaker rename race | Önceden düzeltilmiş / mevcut koruma | Ad yazıları profil lock+generation, geç sonuç güncel isim; reset testi. |
| S-M26 | socket null-checks fragile | Kesinleştirilemedi | Hangi socket-null çağrısının ulaşılabilir olduğu verilmemiş; setup guard var, somut hata üretilemedi. |
| S-M27 | loadAIConfig reconnect'te her seferinde key POST | Yanlış alarm | _configSyncedInstanceId aynı backend reconnect'te config yeniden uygulamayı engeller. |
| S-M28 | partial preview ordering edge case | Önceden düzeltilmiş / mevcut koruma | Partial source whitespace korunması ve oturum/utterance guard; daha belirsiz sıralama iddiası için failure trace yok. |
| S-M29 | numeric ID coercion | Yanlış alarm | Object numeric/string key aynı; third frontend testi. |
| S-M30 | unnecessary `<div>` wrapper. | Tasarım / iyileştirme / kapsam ayrımı | Div wrapper fazlalığı stil/DOM temizlik önerisi. |
| S-M31 | `process.env` spread → secret leak to child | Tasarım / iyileştirme / kapsam ayrımı | Backend child güvenilen yerel süreç ve API anahtarına ihtiyacı var; env aktarımı kendi başına exfiltration değil. |
| S-M32 | rotation pre-write değil | Bu tur düzeltildi | Rotasyon gelecek UTF8 satır boyutunu da hesaba katar. |
| S-M33 | save_profiles diarize worker'ı blokluyor (fsync) | Tasarım / iyileştirme / kapsam ayrımı | Profil fsync veri dayanıklılığı; ölçülmüş darboğaz yok. Rastgele kaldırılmadı. |
| S-M34 | Unix killer image-name check yok | Önceden düzeltilmiş / mevcut koruma | Unix orphan process komutu platform dalında ps ile; sahiplik yine doğrulanıyor. |
| S-M35 | HW-accel unconditional | Tasarım / iyileştirme / kapsam ayrımı | Hardware acceleration kapalı tercihi CUDA/driver kararlılığı içindir; GPU renderer performansı gerçek cihaz ölçümü olmadan açılmadı. |
| S-M36 | `_setup_lock`/`_profile_lock` ordering fragility. | Yanlış alarm | Setup→profile sırası; profile tutularak setup beklenen ters yol bulunmadı. |
| S-M37 | `_detect_script_lang` Armenian/Khmer/Tibetan/Ethiopic → None | Tasarım / iyileştirme / kapsam ayrımı | Armenian vb script çıkarımı yardımcıda yok; ASR dil kodu yine kullanılabilir. Yeni dil desteği ayrı özellik. |
| S-M38 | whitespace/punct input | Önceden düzeltilmiş / mevcut koruma | Whitespace/punctuation-only input meaningful kontrolüyle reddediliyor; kısa anlamlı giriş korunuyor. |
| S-M39 | NFC normalization eksik | Bu tur düzeltildi | AI dedup NFC eklendi; her dil için transliterasyon ayrı contract, bütün Unicode işlevleri için tek blanket normalizasyon iddia edilmez. |
| S-M40 | vowel order inconsistency | Bu tur düzeltildi | Somut it/es/sk çift dönüşüm phonetic modu ile çözüldü; örneksiz genel vowel-order hükmü kurulmadı. |
| S-M41 | fallback English-cleanup | Bu tur düzeltildi | Somut vi fallback düzeltildi; bütün dillerin native yazımını İngilizce kuralıyla kusursuz okumak vaat edilmiyor. |
| S-M42 | Azerbaijani guide yok | Tasarım / iyileştirme / kapsam ayrımı | Azerbaycanca özel guide genişletmesi özellik talebi; mevcut generic fallback çalışır, kalite garantisi yok. |
| S-M43 | kana-dominant yanlış ja/zh disambiguation. | Önceden düzeltilmiş / mevcut koruma | Kana varlığı/ASR uyumlu dil hint korunuyor; salt kanji çoğunluğu ja'yı zh'ye ezmiyor. |
| S-L1 | Dead `Input overflowed` branch | Tasarım / iyileştirme / kapsam ayrımı | Ulaşılamayan overflow dalı kod temizliği; aktif sorun _enqueue_audio ile tekleştirildi. |
| S-L2 | YouTube outros eksik (`[Musik]`, `[音楽]`) | Bu tur düzeltildi | Tam [Musik]/[音楽] marker'ları filtrelendi; gerçek içerik içindeki kelimeler silinmez. |
| S-L3 | int16 normalization 32768 vs 32767 | Yanlış alarm | Signed int16 negatif sınırı32768; bu ölçek doğru,32767 zorunlu değil. |
| S-L4 | WASAPI loopback missing error message generic | Önceden düzeltilmiş / mevcut koruma | Loopback bulunamaması açık hata verir; stale device fallback testleri. |
| S-L5 | cpu_threads env override not re-evaluated | Tasarım / iyileştirme / kapsam ayrımı | CPU env startup konfigürasyonu; her model yüklemesinde dosyadan hot reload vaadi yok. |
| S-L6 | Debug logs | Tasarım / iyileştirme / kapsam ayrımı | Genel debug gürültüsü somut performans ölçümü değil; tüm ID dökümü kaldırıldı. |
| S-L7 | `escapeJsString` U+2028/2029 | Yanlış alarm | Modern V8 U2028/U2029 string literal kabul ediyor. |
| S-L8 | `prefers-reduced-motion` yok | Yanlış alarm | prefers-reduced-motion static/theme CSS içinde mevcut. |
| S-L9 | quickReset/clearTranscriptions duplicate code | Tasarım / iyileştirme / kapsam ayrımı | Farklı reset işlevleri farklı veri kapsamını temizliyor, isim benzerliği bug değil. |
| S-L10 | window-all-quit ordering | Kesinleştirilemedi | Somut window-quit aralık izi verilmedi; mevcut shutdown/nonce guard var. Gerçek Electron close stress testi yapılmadı. |
| S-L11 | stdout stderr chunk split | Tasarım / iyileştirme / kapsam ayrımı | stdout chunk bölünmesi kozmetik log satırı konusu; readiness protokolü HTTP üzerinden. |
| S-L12 | cwd in dist `resources/app/` | Tasarım / iyileştirme / kapsam ayrımı | Paket resources/app backend kökü; harici Python/venv araması launch klasörleriyle ayrıca yapılıyor, belgelenmiş. |
| S-L13 | electron-store silent fail | Yanlış alarm | Store başarısızlığı console.warn ile görünür; rapordaki tamamen sessiz iddiası yanlış. |
| S-L14 | `_partialHideTimer` scope leak | Önceden düzeltilmiş / mevcut koruma | Tek hide timer yenilenir/temizlenir; sınırsız listener/timer yok. |
| S-L15 | `transcribe` `_strip_foreign_diacritics` `<>` eksik | Tasarım / iyileştirme / kapsam ayrımı | Angle temizleme okunurluk politikası; XSS kontrolü escape tarafında, iki şey karıştırılmamalı. |
| S-L16 | smoke test idempotency/direct-script/auto-mode coverage gaps | Bu tur düzeltildi | Native→phonetic korunması ve ambiguous auto prompt testleri eklendi; genel f(f(x)) idempotence vaat edilmez. |
| S-L17 | Portekizce `ão→an` nasalization yok. | Tasarım / iyileştirme / kapsam ayrımı | PT burun sesinin Türkçe yaklaşık yazımı dil rehberi tercihi; tüm ao→an mekanik değişimi ses kalitesini garanti etmez. |

## 5. Ek doğrulama raporu — 10 ana + 7 küçük madde

| Kimlik | Rapordaki iddia | Sonuç | Gerekçe / kaynak / test |
|---|---|---|---|
| E-01 | Kalite eval'inde app-token eksik | Bu tur düzeltildi | Eval app-token gerçek buyedektir.APP_TOKEN ile; önceki yanlış os/APP_TOKEN referansları giderildi. AST test sağlayıcı çağırmıyor. |
| E-02 | DeepL config kilidi altında ağ isteği | Önceden düzeltilmiş / mevcut koruma | DeepL HTTP test config lock dışında; third regresyon concurrent lock alımını doğruluyor. |
| E-03 | CJK partial'a fazladan boşluk | Bu tur düzeltildi | Partial separator kaynak metnin gerçek whitespace'ından; Japonca, karma Tokyo+Latin ve Latin prefix testi. |
| E-04 | Glossary pipe/boş satır round-trip | Bu tur düzeltildi | Glossary pipe/backslash round-trip ve boş satır kotası; C:\Docs unknown escape korunuyor. |
| E-05 | Prune edilmeyen seenTranscriptionIds | Önceden düzeltilmiş / mevcut koruma | Prune set/map beraber; DOM dışı stale duplicate yeniden map doldurmuyor. |
| E-06 | Windows dışı orphan komutu / elle backend devralma | Önceden düzeltilmiş / mevcut koruma | Unix ps dalı mevcut. Elle açılmış backend'i zorla öldürmemek kasıtlı güvenlik; otomatik devralma vaat edilmiyor. |
| E-07 | Senkron Python import ön kontrolü | Bu tur düzeltildi | find_spec ön kontrolü korunup başarılı Python process çapında cache'lendi; her probe5s timeout, tekrar aramada1probe testi. |
| E-08 | Ortak lifecycle kilidinin performansı | Tasarım / iyileştirme / kapsam ayrımı | Ortak lifecycle kilidi tutarlılık sınırı; somut network-lock sebebi giderildi. Genel lock parçalama ölçümsüz geniş refactor olarak uygulanmadı. |
| E-09 | 1.2sn sessizlik / 15sn segment kararı | Tasarım / iyileştirme / kapsam ayrımı | 1.2sn/15sn latency/segment uzunluğu kararı; silence_duration ayarlanabilir. Görüşme kalitesi/maliyet gerçek ses ölçümü olmadan kesin bug değil. |
| E-10 | Glossary initial_prompt hallucination riski | Kesinleştirilemedi | Glossary prompt kaynaklı gerçek sessizlik hallucination ölçülmedi. VAD mevcut; tüm sözlüğü kaldırmak ana özelliği bozabilir. |
| E-11 | OpenAI key kaydetme doğrulandı sanılıyor | Bu tur düzeltildi | OpenAI translation key kaydı verified:false dönüyor; UI mesajı gerçek remote doğrulaması yapılmadığını söylüyor. |
| E-12 | Boş reseller key / shared fallback yanlış mesajı | Bu tur düzeltildi | Boş ayrı anahtarda shared fallback kullanılıyorsa using_shared_key ve mesaj doğru; sahte silindi iddiası yok. |
| E-13 | showAlert meşru baş noktalamasını siliyor | Bu tur düzeltildi | showAlert yalnız piktogram/variation/ZWJ/boşluk önekini temizler; meşru quote/#/parantez korunur. |
| E-14 | session_start ISO parse taşınabilirliği | Bu tur düzeltildi | session_start offset+3haneli milliseconds ISO biçimi. |
| E-15 | Stream kapatmada sahiplik yarışı | Önceden düzeltilmiş / mevcut koruma | Stream detach/cleanup sahipliği lifecycle guard; gerçek live C handle zorla başka thread'den kapatılmıyor. |
| E-16 | Diagnostik sayaçların lock tutarlılığı | Tasarım / iyileştirme / kapsam ayrımı | Diagnostik busy sayaçları yaklaşık telemetri; CPython basit atama/okuma, iş verisi invariant'ı değil. |
| E-17 | GET/socket erişimi ve HOST uyarısı | Bu tur düzeltildi | .env.example localhost/GET/socket erişim uyarısı. Bu token kullanıcı kimlik doğrulaması değildir, LAN güvenliği sağladığı iddia edilmez. |

## 6. Kozmetik öneri raporu — 8 değerlendirme

| Kimlik | Rapordaki iddia | Sonuç | Gerekçe / kaynak / test |
|---|---|---|---|
| UI-1 | Okunuş kapsülü | Önceden düzeltilmiş / mevcut koruma | Okunuş kapsülü/spacing önceki903d24c değişikliğinde mevcut; bu tur yeniden tasarlanmadı. |
| UI-2 | Inline renk uyumu | Tasarım / iyileştirme / kapsam ayrımı | Tema override'ları mevcut; bütün inline stillerin temizlenmesi kozmetik refactor, raporda üretim bug'ı değil. |
| UI-3 | Sol panel tabs/dil seçimi | Tasarım / iyileştirme / kapsam ayrımı | Panel tabs/compact language yeni gezinme tasarımı; mevcut düzeni değiştirme gereği doğrulanmadı. |
| UI-4 | Diyalog balonu ve partial animasyon | Tasarım / iyileştirme / kapsam ayrımı | Balon hizası/typing dots isteğe bağlı tasarım; ek animasyon kasma çözümü değil. |
| UI-5 | Cevap kısayolları/toolbar/skeleton | Önceden düzeltilmiş / mevcut koruma | 1–4 kbd rozetleri903d24c içinde mevcut. Hover-only toolbar/skeleton eklemek zorunlu bug düzeltmesi değil. |
| UI-6 | Reading overlay blur/punto | Tasarım / iyileştirme / kapsam ayrımı | Blur/punto/kısayol önerisi yeni özellik; büyük blur GPU maliyetini artırabilir. Mevcut reading mode korundu. |
| UI-7 | İkonografi | Tasarım / iyileştirme / kapsam ayrımı | Emoji→SVG genel dönüşümü kozmetik; mevcut simgeler çalışıyor, kör toplu değişiklik yapılmadı. |
| UI-8 | Kopya geri bildirimi/equalizer | Tasarım / iyileştirme / kapsam ayrımı | Kopya toast mevcut geri bildirim; equalizer gradient/glow kozmetik ve render maliyeti, eklenmedi. |
## 7. Ek rapordaki doküman kayması

E-DOC: CLAUDE.md güncellendi:15sn utterance,1.2sn sessizlik,7sn/adaptif partial,iki çeviri worker'ı, geç speaker event/admission slot, provider ayrımı, token/instance/nonce, glossary/stats, env override'ları, main_helpers ve static dosyalar. Tarihli SONNET_GOREVLERI oturum kaydı bugünkü model adına göre yeniden yazılmadı.

## 8. P raporunun doğrulanamayan şüpheleri — 7/7

| No | Sonuç |
|---|---|
| 1 | Stale cihaz ID'si capture-mode bazlı fallback ile sentetik testte ele alınıyor; gerçek USB/OS değişimi testi yapılmadı. |
| 2 | Int16 kanalların float64 ortalaması int16 aralığını aşmaz: overflow iddiası yanlış. Surround LFE ağırlığı/algısal kalite gerçek5.1/7.1 kaydıyla değerlendirilmeli. |
| 3 | Chunk resampling boundary işitilebilirliği doğrulanmadı; H olarak açık sınır, algoritma rastgele değiştirilmedi. |
| 4 | Bounded50read/49backoff sentetik olarak test edildi, tek terminal hata yolu mevcut; Bluetooth'ta 2.5sn boyunca50alert iddiası gerçek ölçüm değil. |
| 5 | Error emit koruması eklendi; socket disconnect normalde exception fırlatmaz. Her emit'e catch eklemek delivery garantisi vermez. |
| 6 | seenTranscriptionIds/map budaması mevcut frontend regresyonuyla korunuyor;8saat gerçek bellek profili yapılmadı. |
| 7 | conversation deque20turn sınırı bilinçli context/bellek sınırı. |

## 9. P raporundaki 14 test kör noktası

| No | Mevcut karşılık / kalan sınır |
|---|---|
| 1 | Kısa CJK/Latin pozitif-negatif report+complete testlerinde. |
| 2 | Kısa answer metni mock sağlayıcıya ulaşıyor; report suite. |
| 3 | HTML entity/onclick round-trip followup frontend. |
| 4 | Gerçek stop nesli mic sonucunu iptal ediyor; followup backend. |
| 5 | PTT kayıt öncesi slot doluluğu429 ve rezervasyon release testleri. |
| 6 | Mic tam bir kez cleanup +stop canlı stream'i zorla kapatmaz +stale capture guard testleri; native sürücü testi değil. |
| 7 | Clear sonrası ID monotonluğu zaten smoke kapsamındaydı. |
| 8 | Budama/pending timeout mekanizmaları kontrol edildi;8saat soak/GC/Future profili yapılmadı. |
| 9 | Identity resample ve VAD480örnek/960byte şekli report suite; gerçek ses frekans cevabı ölçülmedi. |
| 10 | Çok kanallı ortalamanın sayısal sınır analizi; surround algısal ses testi yok. |
| 11 | Settings mevcut bounds kontrolleri/smoke kapsamı; bütün olağandışı scalar türleri için tam fuzz iddiası yok. |
| 12 | Boş/kısa quiet-split sınırları followup testi; doğal kelime sınırını ses olmadan garanti etmez. |
| 13 | Backend parallel calls+partial akışı smoke, cap/auto complete; gerçek tarayıcı event-loop uzun süreli race testi değil. |
| 14 | apos/quot/entity round-trip followup frontend;3 ile aynı kusur. |

## 10. Önerilen 14 regresyonun eşlemesi

| Öneri | Karşılık |
|---|---|
| 1 Alt PTT hedef | report backend/frontend PTT target/discard kontrolleri. |
| 2 Kısa hallucination | report short_speech_and_script +complete short_emphasis. |
| 3 Kısa answer | report short_answer_reaches_mock_provider. |
| 4 Mic izolasyonu | followup real_stop_invalidates_old_ptt_result; rapordaki yalnız session artırma gerçek lifecycle değil. |
| 5 Slot kaybı | followup full_ptt_queue_rejected_before_recording. |
| 6 Stream lock | report mic_cleanup_exactly_once/followup stop_does_not_close_a_live_capture_stream. |
| 7 Entity injection | followup_frontend gerçek escape fonksiyonu round-trip. |
| 8 SRT overlap | followup merge_output_does_not_overlap_or_lose_text. |
| 9 Unicode dedup | followup unicode_answer_dedup_without_erasing_non_latin; sözleşmeye uygun2+2mock. |
| 10 Partial race | smoke parallel answer/partial ve complete cap/collapsed; bütün olası event interleaving ispatı değil. |
| 11 Quiet split uçlar | followup quiet_split_tiny_buffers +smoke quiet_split_index. |
| 12 Silence bounds | smoke settings_bounds; tüm önerilen fuzz matrisinin tamamlandığı iddia edilmez. |
| 13 VAD bounds | Mevcut route bounds kontrolü incelendi; önerideki tüm fuzz değerleri için ayrı yeni test yazılmadı. |
| 14 Glossary XSS | Mevcut escape/render koruması ve sözlük normalizasyon testleri; bu tur pipe/backslash round-trip eklendi. |

## 11. Gerçek cihaz için istenen 10 kontrol

Bu kontroller rapordan çıkarılmadı; başlıkların tamamı değerlendirildi ama yapılmayan test yapılmış sayılmadı.

| No | Durum |
|---|---|
| 1 |44.1/48kHz işitilebilir artefakt: gerçek ses testi yapılmadı. |
| 2 |5.1/7.1 kanal ses kalitesi: yapılmadı; sayısal overflow gerekçesi yanlış. |
| 3 |USB/Bluetooth cihaz değişimi: fallback mock geçti; fiziksel test yapılmadı. |
| 4 |Bluetooth kopmasında kullanıcı alert akışı: bounded retry mock geçti; fiziksel test yapılmadı. |
| 5 |Türkçe PTT→Japonca gerçek okunuş kalitesi: hedef/contract test edildi; ücretli/gerçek konuşma eval'i yapılmadı. |
| 6 |Gerçek はい/ええ/うん ses tanıması: filtre metin testi geçti; Whisper tanıma başarısı ayrıca ölçülmedi. |
| 7 |Hızlı stop/start gerçek PTT: generation mock geçti; fiziksel stres yapılmadı. |
| 8 |Üç ardışık gerçek PTT: kapasite/rezerve-before-record mock geçti; gerçek ses oturumu yapılmadı. |
| 9 |Gerçek AI entity çıktısı: sentetik literal round-trip geçti; ücretli AI çağrısı gerekmedi/yapılmadı. |
| 10 |8saat oturum: yapılmadı; kısa testlerden gerçek soak başarısı türetilmedi. |

## Kaynaklar ve korunan dosyalar

- D:/Whisper Live/BUG_TARAMASI_TAM_RAPORU.md
- D:/Whisper Live/DERIN_BUG_TARAMASI_RAPORU.md
- C:/Users/K/.codex/attachments/8baa2ba8-b069-4cae-8fe2-8e0e3ae584d1/pasted-text.txt
- C:/Users/K/.codex/attachments/339d7c6e-0f80-41be-820c-a72731087e96/pasted-text.txt
- C:/Users/K/.codex/attachments/2ec556c0-a2f7-4e5a-9101-9c320392a18d/pasted-text.txt (126a92ff-e11a-48c7-9840-358a8abfaaa2 aynı içerik)
- C:/Users/K/.codex/attachments/45458724-f85e-4c3b-9273-21daded0cef4/pasted-text.txt

Önceden değiştirilmiş archive/__pycache__yedek/{carry,enozellik,enyeni2,enyerni2,job works}.py ve archive/translator_gui.py bu tur değiştirilmedi/stage edilmeyecek. Kullanıcı .claude/settings.local.json ve _quick_phrases.json da dahil edilmedi. archive/main.py ve archive/run_whisper.py ise rapordaki somut kusurlar için bu tur kapsamlı olarak ayrı düzeltildi.
