# Derin bug raporu — doğrulama ve düzeltme sonucu

Tarih: 3 Eylül 2026. İncelenen kaynak başlangıcı: `782d72e` ve çalışma ağacı.

## Sonuç

[Orijinal raporun](<D:/Whisper Live/DERIN_BUG_TARAMASI_RAPORU.md>) 30 maddesi mevcut kaynakla karşılaştırıldı. **“30 adet doğrulanmış hata” ifadesi doğru bir sonuç değil.** Gerçek hatalar yanında koşullu riskler, hatalı örnekler ve mevcut davranışı değiştiren öneriler bulunuyor.

25 madde kapsamında düzeltme veya koruma uygulandı. Bu sayı “25 hatanın tamamı gerçek cihazda tekrar üretildi” anlamına gelmez. 12, 18, 24, 29 ve 30 numaralı maddelerde önerilen değişiklik uygulanmadı; gerekçeleri aşağıda. Orijinal rapor değiştirilmedi.

Kod düzeltmeleri tamamlandı; gerçek ses cihazı, Electron etkileşimi ve canlı sağlayıcı sonuçları bu doğrulamanın dışında. Commit oluşturulmadı. Başlangıçta zaten değişmiş olan `archive/` dosyalarına ve diğer bağımsız dosyalara dokunulmadı.

## Madde madde karar

| No | Karar | Kanıt, yapılan değişiklik ve sınır |
| --- | --- | --- |
| 01 | Düzeltildi | Alt PTT hedefi giriş dilinden değil `aiTargetLang` seçiminden okunuyor. `auto`, son karşı-taraf kaydının diliyle veya somut dinleme diliyle çözümleniyor; sonuç bulunamazsa kayıt başlamadan anlaşılır hata dönüyor. Rastgele İngilizce varsayılmıyor. Açıkça Türkçe seçilmişse gereksiz çeviri yapılmıyor. |
| 02 | Düzeltildi | Üç karakter altını toptan atan filtre kaldırıldı. `はい`, `No`, `Ne?`, `你好`, tek Çince ideogram gibi yanıtlar geçiyor; salt noktalama ve mevcut bilinen halüsinasyon kalıpları elenmeye devam ediyor. |
| 03 | Düzeltildi | Cevap modundaki dört karakter barajı kaldırıldı. `Why?`, `何?`, `好吗?` testleri gerçek endpoint üzerinden sahte sağlayıcıya ulaşıyor ve seçenek döndürüyor. |
| 04 | Düzeltildi | Bağımsız dosya transkripsiyon aracında sırf önceki metnin içinde geçiyor diye yeni sözcük silinmiyor. Tam eşitlik ve son/baş örtüşmesi korunuyor. `çık` örneği kaybolmuyor; `bir iki üç` ardından `iki üç dört` hâlâ `dört` oluyor. |
| 05 | Düzeltildi; açılış testi yapılmadı | Windows npm yedeği `shutil.which('npm.cmd')` ile çözümleniyor. EXE önceliği korunuyor. Uygulama başlatılarak denenmedi. |
| 06 | Koruma uygulandı | Kapanış isteği `keepalive` kullanıyor ve Promise kuyruğunu beklemiyor. Her kayıt ayrı kimlik taşıyor; durdurma başlatmadan önce ulaşırsa iptal kaydı tutuluyor, eski sayfanın durdurması yeni kaydı kapatmıyor. Sıralamalar sahtelerle test edildi. Tarayıcı/işletim sistemi zorla kapanırsa teslim garantisi yok. |
| 07 | Düzeltildi | Free ve Pro anahtarları farklı DeepL uç noktalarına yönleniyor. Kuyruktaki iş kendi anahtar/URL anlık görüntüsünü koruyor. Sahte HTTP istekleri iki adresi de doğruluyor; canlı anahtar kullanılmadı. |
| 08 | Düzeltildi | Cevap modeli seçimi de mevcut eski-model takma adlarını varsayılan modele eşliyor. |
| 09 | Düzeltildi | PTT sonuçları ortak, artan transkript kimliği ve `source=ptt` ile backend geçmişine alınıyor. Kart kimliği ve metin haritası eklendi; yenileme aynı PTT kartını geri kuruyor, tekrarını eklemiyor. Overlay kendi mikrofon metinlerini göstermeme davranışını koruyor. |
| 10 | Düzeltildi | Geçmişten yüklenen normal/mikrofon/PTT kayıtları toplam sayıyı tekrar artırmıyor. Üç kaynak türüyle arayüz fonksiyon testi eklendi. |
| 11 | Koşullu hata düzeltildi | Genel “iki noktaya kadarki her şeyi sil” ifadesi yalnızca bilinen `Line N`, `Hedef`, `Target` etiketleriyle sınırlandı. Rapordaki yalnız tek satırlık örnek, eski kodda ham-metin dönüşüne girebildiği için tek başına yeterli kanıt değildi. `Note: bring water` ve ayrı Türkçe satırı içeren gerçek ayrıştırma yolu test edildi. |
| 12 | Davranış ayrımı; değiştirilmedi | Gelen konuşmanın normal çevirisi ile AI hedef dil/okunuş çıktısı aynı sözleşme değil. İkisi aynı anda açıkken ek maliyet olabilir; otomatik AI çevirisini kaldırmak okunuş/hedef çıktı özelliğini kaybettirebilir. Aynı metne iki istek bulunması tek başına eşdeğer işin iki kez yapıldığını kanıtlamıyor. |
| 13 | Düzeltildi; cihaz sınırı var | PortAudio akışı kilit altında tek sahibine devredilip bir kez kapatılıyor. Worker hâlâ `read` içindeyken HTTP thread'i akışı zorla kapatmıyor. Sekiz eşzamanlı temizleme çağrısında tek `close`/`terminate` test edildi. Sürücü sonsuza dek takılırsa yeni kayıt güvenlik gereği reddedilir; gerçek sürücü denenmedi. |
| 14 | Düzeltildi | Kana içeren Kanji ağırlıklı Japonca, Han sayısı fazla diye Çinceye zorlanmıyor. Salt Han metninde uyumlu Japonca/Çince model tahmini korunuyor. |
| 15 | Düzeltildi | `transkribe.py` worker'ı Tk değişkenlerini okumuyor ve Tk `after` çağrısı yapmıyor. Seçenekler ana thread'de alınarak worker'a aktarılıyor; ilerleme/log/sonuç olayları kuyruktan ana thread'de işleniyor. Gerçek Tk penceresi açılmadı. |
| 16 | Düzeltildi | Konuşmacı sıfırlama tüm profil dosyasını silmek yerine boş isim listesiyle mevcut HF token'ını koruyor. Geçici profil dosyasıyla test edildi. |
| 17 | Güvenli hata davranışı; kapasite sorunu sürer | Model değişiminde iki modelin geçici olarak VRAM'de birlikte bulunması gerçek risk. OOM oluşursa mevcut model korunup açık hata dönüyor; sessiz CPU değişimi yapılmıyor. Aktif modelin çalışırken zorla silinmesi uygulanmadı. Daha büyük modele sorunsuz sıcak geçiş garantisi değil; küçük model veya yeniden başlatma gerekebilir. |
| 18 | Mevcut iptal davranışı; değiştirilmedi | Durdurma mevcut nesli geçersiz kılıyor; son bekleyen parçanın teslim edilmemesi gerçek bir sınırlama. Ancak nesil/oturum korumasını kaldırmak eski sonuçları yeni oturuma sızdırabilir. “Kuyruğu tamamlayarak durdur” ayrı bir durum/geçiş tasarımı gerektiriyor. Bu raporda çözülmüş sayılmıyor. |
| 19 | Kısmen düzeltildi | Yunanca aralığı eklendi. Final ASR yolunda Ukraynaca/Bulgarca gibi uyumlu Kiril dil tahminleri Rusçaya zorlanmıyor. Yalnız alfabeden dil kesin belirlenemez; geçerli model tahmini olmayan Kiril metnindeki varsayım sürüyor. |
| 20 | Düzeltildi | İsim değişikliği mevcut backend kayıtlarına ve `speaker_updated` olayıyla görünür rozetlere işleniyor. Geç tamamlanan konuşmacı tespiti de profilin güncel adını kullanıyor; eski adı geri yazmıyor. |
| 21 | Düzeltildi | Boş HF token gönderimi artık temizleme işlemi. Kalıcı token kaldırılıyor, pipeline ve konuşmacı tanıma kapatılıyor, tarayıcı ayarı temizleniyor. Kurulum/tembel yükleme ile temizleme aynı kilitle sıralanıyor; bekleyen tembel yükleme silinmiş eski token'ı geri kurmuyor. |
| 22 | Önlem; mevcut hata kanıtlanmadı | Nesne URL'sinin iptali bir saniye geciktirildi. Güncel Electron/Chromium'da indirmenin gerçekten iptal olduğunu gösteren uçtan uca kanıt yok; kritik doğrulanmış hata olarak sayılmıyor. |
| 23 | Düzeltildi | DOM'dan budanan kimlikler `seenTranscriptionIds` kümesinden de çıkarılıyor. Budanan en büyük kimlik ayrıca tutuluyor; geçmiş yüklemesi eski satırları tekrar içeri almıyor. Temizleme/yeni backend oturumu bu sınırı da sıfırlıyor. |
| 24 | Yanlış alarm | Mikrofon sonucundaki `conversation_turns.append` mevcut kodda zaten `_lifecycle_lock` bloğunun içinde. Rapordaki kilitsiz erişim iddiası bu sürüm için geçerli değil. |
| 25 | Yardımcı işlev düzeltildi; etki abartılmış | Eşit oranlı doğrudan yardımcı çağrısında filtre hatası mümkündü; ana çağrı noktaları eşit oranı zaten atlıyordu. Eşit oran/boş ses için kopya dönüşü ve pozitif oran kontrolü eklendi. Kesirli kaynak hızından çıkan kısa/uzun VAD blokları VAD kopyasında tam 30 ms'ye bölünüp dolduruluyor; Whisper'a dolgu eklenmiyor. Eski VAD hatasında ses-seviyesi yedeği bulunduğundan her olay uygulama çökmesi değildi. |
| 26 | Düzeltildi; etkileşim testi sınırlı | Alt kaydı 150 ms bekliyor; başka tuşla kombinasyon veya odak kaybı iptal ediyor. Başlamış kayıt da kombinasyonda atılıyor. Alt+Tab, tuş bırakma ve kapanış sırası fonksiyon testlerinde doğrulandı; gerçek Electron/Windows klavye testi yapılmadı. |
| 27 | Kısmi iddia düzeltildi | Boşluklu bağlamın başında oluşan yarım sözcük atılıyor. Python Unicode karakter dilimlemesi UTF-8 baytını ortadan kesmez; raporun bu kısmı yanlış. Boşluksuz CJK bağlamı tamamen silinmiyor. |
| 28 | Koşullu sınır iyileştirildi | 0,5 saniye kontrolü yalnız konuşmayı değil biriken sessizlik payını da ölçüyor; varsayılan sessizlik süresinde “her kısa cümle kaybolur” doğru değil. Düşük sessizlik ayarındaki kaybı azaltmak için birikmiş tampon alt eşiği 0,2 saniyeye indirildi. Gerçek kısa-hece tanıma başarısı ses/model testi gerektirir. |
| 29 | Doğrulanmadı; güvenlik korunuyor | Bu makinede 8.3 süreç yolu senaryosu yeniden üretilmedi. Yol uyuşmazlığına karşı yalnız dosya adına bakıp süreç öldürmek güvenlik kapsamını genişletir. Sahiplik kontrolü gevşetilmedi; mevcut yardımcı testleri geçiyor. |
| 30 | Tasarım davranışı; değiştirilmedi | İşlev açıkça tam eşleşme telaffuz override'ı. Cümle içi sözlük girdileri zaten isteme ekleniyor. Yerel yazıdaki alt dizenin konumu ile Türkçe okunuştaki konum aynı olmadığı için kör alt-dize değiştirme güvenli çözüm değil. |

DeepL ayrımı için birincil kaynak: [DeepL kimlik doğrulama belgesi](https://developers.deepl.com/docs/getting-started/auth). Free anahtarın `:fx` son eki ve Free/Pro sunucu ayrımı buradan kontrol edildi.

## Çalıştırılan doğrulamalar

- Proje `.venv` ortamında `py_compile` ve `pyflakes`: değiştirilmiş Python kaynakları ile test dosyaları temiz.
- [Mevcut smoke paketi](<D:/Whisper Live/test_smoke.py>): 28 test işlevi geçti. Eski konuşmacı testi yerel kullanıcı isimlerinden yalıtıldı; token koruyan reset beklentisi güncellendi.
- [Yeni rapor regresyonları](<D:/Whisper Live/test_report_regressions.py>): 15 test geçti. Sahte sağlayıcı, sahte model/ses akışı ve geçici profil kullanıldı.
- Flask test istemcisiyle `/` ve `/overlay`: HTTP 200. Gerçek render edilmiş HTML içindeki script blokları `node --check` doğrulamasından geçti.
- [Arayüz regresyonları](<D:/Whisper Live/test_frontend_regressions.js>): iki şablonun script sözdizimi, çeviri metni, budama/kimlik sınırı, üç kaynak türünün hydration sayacı, PTT tekrar önleme, Alt kombinasyonları ve kapanış isteği sırası geçti. Bu bir gerçek tarayıcı/Electron testi değil; kaynak fonksiyonları küçük DOM/ağ sahteleriyle çalıştırılıyor.
- `test_main_helpers.js`, `main.js` ve `main_helpers.js` sözdizimi kontrolleri geçti.
- Değiştirilen kaynaklarda `git diff --check` temiz. `buyedektir.py` LF satır sonları korundu.
- `npm run build` başarılı; paket güvenlik taraması temiz. Yeniden paketlemeden önce hedefte temel kişisel ayar/transkript dosyaları bulunmadığı kontrol edildi.
- Paket içindeki backend, ana arayüz, overlay, Electron ana dosyası ve yardımcı dosyanın SHA-256 değerleri kaynaklarıyla eşleşiyor.

## Kullanım ve kalan sınırlar

Güncel paket: [Whisper-Pro.exe](<D:/Whisper Live/dist/Whisper-Pro-win32-x64/Whisper-Pro.exe>). Açık uygulama/arka uç bu çalışma sırasında kapatılmadı veya yeniden başlatılmadı; değişiklikleri kullanmak için normal şekilde kapatıp yeniden açın. Paket Python/ML ortamını gömmez; mevcut çalışma zamanı gereksinimi değişmedi.

Canlı mikrofon, loopback, GPU model yüklemesi, ücretli çeviri/AI API'si, pyannote model indirmesi, gerçek Tk/Electron penceresi kullanılmadı. Dolayısıyla “takılma tamamen bitti”, “cihaz yarışı gerçek sürücüde kesin giderildi” veya “tüm dillerin ses kalitesi doğrulandı” sonucu çıkarılmamalı.

Özellikle 17 numarada büyük modele geçiş kapasite sınırı, 18 numarada durdurmada bekleyen sesin iptali ve 29 numarada 8.3 yol senaryosu açık sınırlar olarak kalıyor.
