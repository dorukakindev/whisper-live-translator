# Kalan bulguların doğrulanması — 4. tur

Bu rapor, 153 bulgu başlıklı özetin tamamının kapatıldığı anlamına gelmez. Bu turda altı başlıkta değişiklik yapıldı; gerçek hata ile koşullu güvenlik sağlamlaştırması aşağıda ayrıldı. Commit oluşturulmadı, önceden mevcut arşiv değişikliklerine dokunulmadı.

## Doğrulanan ve düzeltilen yollar

1. **Bozuk konuşmacı profilinin üzerine yazılması.** `SpeakerDiarizer.load_profiles/save_profiles`: bozuk JSON veya geçersiz alan türleri yüklenemediğinde sonraki kayıt boş/eksik verilerle asıl dosyayı değiştirebiliyordu. Şema doğrulandı; yükleme başarısızsa kayıt engelleniyor ve uyarı yazılıyor. Geçici dosyalarda bozuk JSON, liste kökü, yanlış names/token türleri ve erişim reddi sınandı; özgün dosya değişmedi. Geçerli yeniden yükleme kayıt kilidini kaldırıyor. Bu **otomatik veri kurtarma değildir**: bozuk dosya korunur; dosya düzeltilip uygulama yeniden açılana kadar yeni profil değişiklikleri kalıcı kaydedilemez.

2. **PTT yüzünden yanlış çeviri gecikmesi.** Canlı çeviri işi kimliği ile son kayıt kimliği arasındaki fark, araya giren PTT kayıtlarını da kuyruk yükü sayıyordu. Gerçek gönderim yoluna ayrı çeviri sıra sayacı eklendi; `_translate_async` bunu hem istekten önce hem sonuçtan sonra kontrol ediyor. Büyük genel kimlik farkında çeviri çağrılıyor; gerçek iş birikmesinde çağrı atlanıyor; yavaş sonuç kuyruk gerisinde kalırsa yayınlanmıyor. Eski doğrudan yardımcı çağrıları için kimlik tabanlı uyumluluk yolu korundu; üretim gönderimi yeni sayacı kullanıyor.

3. **Portekizce aynı turda çift dönüşüm.** `gue/gui → ge/gi → je/ji` sırası sert g'yi yanlışlıkla yumuşatıyordu. Yumuşak g kuralı öne alındı. `guerra guia → gerra gia`, `gelo girar → jelo jirar` testleri geçti. Bu, tüm Portekizce telaffuzun veya normalizasyonda ikinci geçişin doğrulandığı iddiası değildir; özellikle ham yazım ile hazır Türkçe okunuşun ayrılması hâlâ açık.

4. **Tek başına motor etiketi metin olarak geçiyordu.** `<music>`, `<silence>`, `<nospeech>`, `<|nospeech|>` yalnızca tüm çıktı bunlardan biriyse eleniyor. Büyük/küçük harf ve çevre boşlukları sınandı. Aynı etiket geçen gerçek cümleler yeni kuralla elenmiyor. Genel outro/tekrar filtresi genişletilmedi.

## Sağlamlaştırılan sınırlar

5. **Electron gezinme ve yeni pencere sınırı.** Ana pencere ve overlay için `will-navigate` / `will-redirect` üzerinden yalnızca uygulamanın tam origin'ine izin verildi; renderer kaynaklı yeni pencereler reddedildi. URL parser kullanıldı, önek karşılaştırması yapılmadı. Başka port, benzer alan adı, kullanıcı bilgili URL, data/file ve bozuk URL örnekleri sahte webContents ile engellendi. Bu bir gerçek Electron exploit gösterimi değildir; eksik sınır koddan doğrulandı. Yaklaşım [Electron güvenlik rehberi](https://www.electronjs.org/docs/latest/tutorial/security) ile karşılaştırıldı.

6. **Port temizliğinin İngilizce etikete bağımlılığı.** TCP dinleyiciler artık durum sözcüğünden değil, tam yerel port + sıfır uzak uç + sayısal pozitif PID yapısından tanınıyor. IPv4/IPv6 ve farklı sentetik durum etiketleri geçti; benzer port, bağlantı satırı, UDP, sıfır/komut içerikli PID reddedildi. Python süreç adı ve projeye ait child komut satırı denetimleri korunuyor. Türkçe Windows'ta gerçekten çevrilmiş netstat çıktısı gözlemlenmedi; yerelleştirme iddiası gerçek cihaz bulgusu olarak sunulmuyor. Hiçbir süreç test sırasında öldürülmedi.

## Test ve paket kanıtı

- `test_fourth_report.py`: 9 test geçti.
- `test_smoke.py`: 28 test işlevi geçti.
- Önceki Python paketleri: 15 + 10 + 4 geçti. Toplam 66 Python test/test işlevi.
- Üç frontend paketi ve genişletilmiş `test_main_helpers.js` geçti.
- Yeni profil durumu nedeniyle kurucuyu atlayan üç eski test nesnesine yeni başlangıç alanı eklendi. İlk toplu çalıştırmada bu eksik alan yüzünden oluşan hatalar giderildi; test beklentileri zayıflatılmadı.
- Python compile/pyflakes ve JavaScript sözdizimi kontrolleri yapıldı.
- Uygulama paketi yeniden oluşturuldu; paket güvenlik taraması temiz.
- Gerçek mikrofon/loopback, GPU, ücretli sağlayıcı ve açık Electron penceresiyle uçtan uca sınama yapılmadı. Çalışan uygulama zorla yeniden başlatılmadı.

## Açık kalanlar — tamamlandı sayılmamalı

- **Dosya rotasyonu/paylaşım kilidi:** `_append_transcript` rotasyon hatasını sessizce geçip yazmaya devam ediyor. Metni koruyor ama dosya boyut sınırını garanti etmiyor. Bu turda değiştirilmedi; sınırsız yedek üretmek veya kilit halinde yeni konuşmayı düşürmek de güvenli çözüm değil. Kontrollü kurtarma politikasına ve paylaşım hatası testine ihtiyaç var.
- **Genel telaffuz idempotansı:** İtalyanca/Slovakça vb. ham yazım ve zaten Türkçeleştirilmiş metin ayrımı yok. Aynı harfin iki anlamı var; salt regex sıralamasıyla bütün sorun çözülmüş sayılmaz. Portekizce son o dönüşümü lehçe/vurgu bağlamı olmadan her kelimeye uygulanmadı.
- **Ayarların başarısız istekte geri alınması ve localStorage hataları:** Bazı kontrol yolları önce yerelde değişiyor; istek hatasında tam geri alma yok. Genişletilmiş düzeltme ve arayüz olay sırası testleri henüz yapılmadı.
- **Diğer özet bulgular:** kuyruk taşma yarışları, uzun oturum kaynak kullanımı, tüm dil/outro/tekrar senaryoları ve ayrıntısı verilmeyen medium/low maddeler kapatılmadı.

Güncel değişikliklerin kullanılması için uygulamayı normal biçimde kapatıp yeniden açmak gerekiyor.
