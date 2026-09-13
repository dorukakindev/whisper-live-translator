# İkinci derin bug raporu — güncel koda göre doğrulama

İncelenen girdi: Codex ekinde paylaşılan `WHISPER PRO — DERİN BUG DENETİMİ RAPORU`.

Bu raporun çalışma ağacı tespiti artık güncel değil: rapor `782d72e` temiz aktif kaynaklarını incelemiş, oysa ilk doğrulama turunda kaynaklar değiştirilmişti. Bu nedenle P0-01, P0-02 ve P0-03 dahil eski satır numaraları ve birçok “hâlâ geçerli” sonucu doğrudan kabul edilmedi. Her yeni iddia mevcut çalışma ağacında ayrı testle sınandı.

## Uygulanan ek düzeltmeler

1. **PTT kapasitesi konuşmadan önce ayrılıyor.** İki iş yeri doluysa mikrofon hiç açılmadan HTTP 429 dönüyor; kullanıcı konuşup bıraktıktan sonra ses artık kuyruk dolu diye atılmıyor. Başlatma başarısızlığı, iptal, boş kayıt ve worker sonucu kapasiteyi tam bir kez geri veriyor. Sayfa kapanış isteği hiç ulaşmaz ve kayıt kendi kendine biterse koruma zamanlayıcısı ayrılmış yeri geri alıyor.
2. **Canlı ses akışı tek sahibinden kapatılıyor.** Stop işlemi `is_running` durumunu kapatıp worker'ı bekliyor; PortAudio `read` sürerken başka thread'den C akışını kapatmıyor. Normal okuma döndüğünde capture worker kendi `finally` yolunda, yaşam-döngüsü kilidi altında sahipliği alıp bir kez kapatıyor. Takılmış sürücü varken yeni oturum açılmıyor.
3. **Geciken çeviri dönüşte yeniden kontrol ediliyor.** İş kuyruğa girerken güncel olsa da sağlayıcı yanıt verene kadar konuşma beşten fazla transkript ilerlediyse eski sonuç kayda ve ekrana yazılmıyor.
4. **HTML entity / buton kırılması kapatıldı.** `escapeJsString`, `&` karakterini HTML parser katmanı için kaçırıyor. `&apos;`, `&quot;`, sayısal entity, tırnak, ters eğik çizgi, satır sonu, U+2028/U+2029, CJK ve enjeksiyon benzeri metinler gerçek HTML attribute ayrıştırması ve JS çalıştırmasıyla round-trip test edildi.
5. **SRT çakışması metin kaybetmeden giderildi.** `transkribe.py` birleştirme modunda zamanları örtüşen ardışık cue'ları tek zaman aralığında birleştiriyor. Başlangıcı körlemesine ileri itip sıfır/negatif süre oluşturulmuyor; tüm metin korunuyor.
6. **Unicode cevap tekrarları giderildi.** NFC ve NFD biçimindeki aynı cevap tek seçenek oluyor. Rapordaki ASCII'ye indirgeme önerisi kullanılmadı; o yöntem Japonca/Çince gibi Latin olmayan farklı cevapları boş anahtara indirip yanlışlıkla birbirine eşleyebilirdi.
7. **Otomatik dil seçenekleri tutarlılaştırıldı.** Backend her seçeneğe üretildiği çağrının dilini ekliyor. Arayüz otomatik dilde seçenek başına dil etiketi gösteriyor ve dinletme/kaydetme/büyük okuma işlemleri o seçeneğin dilini kullanıyor. Kısmi paralel sonuçlarda da Unicode tekrarları çizimden önce eleniyor.
8. **Bayat cihaz indeksi için güvenli geri dönüş eklendi.** Kaydedilmiş aygıt artık yoksa mikrofon modunda güncel varsayılan giriş, sistem modunda güncel varsayılan çıkışın loopback aygıtı seçiliyor. Sistem sesinde loopback bulunamazsa yanlışlıkla mikrofona düşmek yerine açık hata oluşuyor.

## Rapordaki iddiaların kararı

| İddia | Güncel karar |
| --- | --- |
| P0-01 Alt PTT hedef dili | İlk doğrulama turunda zaten düzeltildi; bu rapor eski kaynağı okumuş. |
| P0-02 kısa CJK/onay silinmesi | İlk turda düzeltildi ve çalışan testlerle doğrulandı. |
| P0-03 kısa AI sorusu reddi | İlk turda düzeltildi ve endpoint testiyle doğrulandı. |
| P1-01 PTT `session_id` sızıntısı | Rapordaki reproducer gerçek `stop_capture()` çağrısını taklit etmiyor. Gerçek stop `_result_generation` değerini artırdığı için mevcut guard eski sonucu atıyor. Stop sırasında sağlayıcı dönüşü testi emit/dosya yazımı olmadığını doğruladı. Ayrı `session_id` değişikliği gerekmedi. |
| P1-02 çeviri kuyruğu/geciken sonuç | Sınırsız executor kuyruğu teorik olarak büyüyebilir; worker başındaki mevcut backlog kontrolü eski işleri no-op yapıyor. Asıl kullanıcı etkisi olan, istek sürerken bayatlayan dönüş için ikinci kontrol eklendi. |
| P1-03 PTT slot doluyken kayıt kaybı | Doğrulandı ve düzeltildi. |
| P1-04 capture stream yarışı | Rapordaki “kilit içine al ve kapat” önerisi C `read` sürerken çapraz-thread kapatmayı güvenli yapmaz. Risk doğrulandı; sahiplik/tek kapatma modeliyle düzeltildi. Gerçek sürücü testi hâlâ gerekli. |
| P1-05 executor çalışan işi öldürüyor | Yanlış. `ThreadPoolExecutor.shutdown(wait=False)` çalışan thread'i kesmez; hemen döner, fakat işler tamamlanır. `cancel_futures=True` de yalnız başlamamış işleri iptal eder. Kod değiştirilmedi. İşletim sisteminin süreci zorla öldürmesi ayrı durumdur. |
| P1-06 `&apos;` attribute kırılması | Doğrulandı ve düzeltildi. |
| P2-01 SRT zaman çakışması | Sentetik örtüşen segmentlerle doğrulandı ve düzeltildi. |
| P2-02 kısa tampon bölme | Rapordaki adımlarda `start=max(1,n-tail_chunks)` hesabı zaten tampon sınırında kalıyor; IndexError veya sonu aşma yok. 0/1/5 chunk ve 0.001/0.01/10 saniye kombinasyonları geçti. Değişiklik gerekmedi. |
| P2-03 Unicode dedup | Doğrulandı; NFC ile güvenli biçimde düzeltildi. |
| P2-04 paralel dil tespiti | Tek üst dil etiketi karışık cevaplarda yetersizdi. Çoğunluk oyu uydurmak yerine her seçenek kendi diliyle taşınıp işleniyor. |
| P2-05 attribute whitespace | Raporun kendisi de yanlış alarm olarak sınıflıyor; değişiklik yok. |
| P2-06 partial executor çalışan işi öldürüyor | P1-05 ile aynı yanlış varsayım. Çalışan iş öldürülmez; ayrıca mevcut session/utterance guard'ları stale partial emit'ini önlüyor. |
| P2-07 queue `get` sırasında stale session | Raporun kendisi sonradan kontrol bulunduğunu belirtiyor; yanlış alarm. |
| P3-01 yinelenen idempotent lower | Stil/çok küçük maliyet; davranış hatası değil. Değişiklik yapılmadı. |
| P3-02 `_quick_phrases.json` untracked | Üretim kaynağı değil; gömülü `QUICK_PHRASES` kullanılıyor ve build beyaz listesi bu ara ürünü bilinçli dışlıyor. Otomasyon önerisi olabilir, bug değil. |
| P3-03 U+2028/U+2029 | Modern Electron JavaScript'inde geçerli; round-trip testi geçti. Değişiklik gerekmedi. |

## Doğrulanan testler

- Proje `.venv` ortamındaki mevcut smoke paketi: **tüm 28 test işlevi geçti**.
- İlk rapor için yazılan regresyon paketi: **15 test geçti**.
- Bu rapor için yazılan [ikinci regresyon paketi](<D:/Whisper Live/test_followup_regressions.py>): **10 test geçti**.
- [HTML/JS round-trip testi](<D:/Whisper Live/test_followup_frontend.js>) geçti.
- Önceki frontend regresyonları, ana Electron yardımcı testleri ve JavaScript sözdizimi kontrolleri geçti.
- Python derleme ve pyflakes kontrolleri temiz.

## Kalan gerçek-cihaz sınırı

Gerçek mikrofon/loopback, USB veya Bluetooth cihaz çıkarma, 44.1/48 kHz uzun ses, gerçek GPU ve canlı AI/çeviri sağlayıcısı bu turda kullanılmadı. Bu nedenle PortAudio sürücüsünün donanım özelindeki davranışı, uzun oturum bellek profili ve ses kalitesi için sahte testlerin ötesinde garanti verilmez.

Python executor davranışı için birincil kaynak: [Python `Executor.shutdown` belgesi](https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Executor.shutdown).
