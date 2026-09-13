# 13 maddelik yeni rapor — doğrulama ve düzeltme sonucu

Tarih: 2026-09-04. Taban commit:38b25a2. Kaynak: C:/Users/K/.codex/attachments/aba9083f-c729-4fbd-b47e-600dcbd429c0/pasted-text.txt.

13 maddenin tamamı değerlendirildi. Raporun “hepsi yeni/kritik/canlı testle kanıtlı” nitelemesi otomatik kabul edilmedi. Aşağıdaki ayrımlar önceki307iddialık envanterin üzerine ek kanıttır.

| No | Karar | İnceleme ve yapılan işlem |
|---|---|---|
| 1 | Doğrulandı, düzeltildi | transkribe.App.__init__ içinde _ui_events artık _build_ui öncesinde kurulur. Model listesi boşken build'in log kuyruğuna yazabildiği AST testi var. Gerçek tkinter penceresi/model/GPU açılmadı. |
| 2 | Kısmen doğrulandı, dar düzeltme | Verilen tek kelimelik güzel örneği kasıtlı olarak korunur: döngü en az2kelime arar, noktalama tek neden değildir. çok güzel. / çok güzel bir gün gibi çok kelimeli örtüşmede noktalama eşleştirmesi düzeltildi; çıktı sözcüklerinin orijinal yazımı korunur. Whisper her zaman noktalama ekler iddiası garanti değildir. |
| 3 | Doğrulandı, ortak düzeltme | require_local_app_token yetki kontrolünden sonra application/json gövdesini dict olarak doğrular; validate_input ayrıca korundu. Tüm statik POST /api yollarına liste/string/sayı/bool/null gönderilen matriste400 ve success:false; yetkisiz istekte403önceliği korunur. Hiçbir geçersiz girdi handler'a girip model/cihaz/API başlatmaz.500 yanıtı bütün Flask sürecinin çökmesi anlamına gelmez. |
| 4 | Doğrulandı, düzeltildi | Kaldırılmış correction varsayılanı answer oldu. Mode belirtilmeyen çağrı mock sağlayıcıyla cevap verir. Önceki bilinmeyen-mod sonucu uygulama hatasıydı; raporda başlıktaki500iddiası kendi örneğiyle uyuşmuyordu. |
| 5 | Doğrulandı, düzeltildi | Finalde çağrı başına sınır artık iki benzersiz eklemeden sonra. [A,B]+[A,C,D] dört seçeneği korur. Kısmi yayın henüz diğer çağrının bütününü bilemez; final kanonik listesi ek benzersiz seçenekleri tamamlayabilir. Önceki noise-before-cap düzeltmesi korunur. Eski cap testi yeni sözleşmeye göre dört benzersiz sonuç bekler. |
| 6 | Doğrulandı, düzeltildi | speaker_updated rozetin tamamını değil son isim span'ını değiştirir. Badge.textContent atamasını hata yapan sentetik DOM testi geçti; ikon yapısı korunur. |
| 7 | Savunma açığı, koruma eklendi | Menü/tray callback'leri yanında backend-ready, second-instance, ready-to-show ve overlay toggle yollarında null/isDestroyed kontrolleri eklendi. Yok/yok edilmiş pencereyle menü ve overlay toggle testleri geçer. Windows'ta normal X genellikle tepsiye gizler; rapordaki her kapatmada kritik süreç çökmesi iddiası doğrulanmadı. Native Electron menü/overlay stresi yapılmadı. |
| 8 | Doğrulandı, düzeltildi | snapshot_request ve translate sınırlarında kaynak/hedef trim+uppercase. tr/TR için sağlayıcı çağrılmaz; tr→ja prompt'u Türkçe/Japonca adlarını kullanır. Snapshot mutasyonu yapılmaz; DeepL bölgesel kodları upper dışında budanmaz. |
| 9 | Helper eksikliği, düzeltildi | buildTranslationResultHtml tek hedef metninde de standart kopyala/dinle kartı üretir; Türkçe bölüm yalnız varsa eklenir. Mevcut ana UI translate isteğini translate_dual'e çevirdiğinden yaygın aktif yolda tüm butonların kaybolması iddiası abartılı. Tek/çift metin, kolon ve placeholder koruması kontrol edildi. |
| 10 | Anlam/geri bildirim düzeltildi | Global PTT mevcut seçili yakalama kaynağını kontrol eder: sadece loopback diye tanımlamak da eksik, capture_mode mic olabilir. Alt mikrofon çevirisi /api/ptt_mic ayrı özelliktir ve sessizce ona geçirilmedi. Menü/tooltip artık Yakalama PTT—seçili ses kaynağı der. Aktif olmayan yakalamada409, flag değişmez; Electron yanıt hatasını gösterip aktif işaretini geri alır. Sentetik backend ve response testi geçti. |
| 11 | Doğrulandı, ölçülerek düzeltildi | İlk ölçüm saniyelerce donmayı doğrulamadı ama30msparçada yaklaşık17ms sıcak maliyeti doğruladı. Yalnız indirgenmiş oran2000'i aşarsa limit_denominator(2000) uygulanıyor. Standart44100oranı160/441olarak birebir korunuyor; uç hız/çıktı uzunluğu testi eklendi. |
| 12 | Doğrulandı, düzeltildi | Overlay runtime-safety.js yükler ve whisperStorage kullanır. Storage getter'ı SecurityError benzeri hata verdiğinde requestAnswer yine fetch'e ulaşır. Kota aşımı normalde getItem okumayı bozmaz; izin/security hatası somut senaryodur. |
| 13 | Doğrulandı, düzeltildi | ai_chat bağlamında source mic/ptt→Ben, system→Karşı taraf ve varsa speaker_name birlikte korunur. Anahtar/gerçek konuşma okunmadan sentetik transcript ve mock prompt testi geçti. |

## FIR ölçümü ve neden algoritma değiştirilmedi?

Aynı proje .venv ortamında30msint16sıfır dizisi; her hız için FIRcache temizlendi, ilk çağrı ölçüldü; sonra100çağrı ortalaması alındı. Süreler sistem yüküne bağlı tek koşu ölçümüdür.

| Giriş Hz | İlk çağrı ms | Sonraki çağrı ortalaması ms |
|---|---:|---:|
|44100|2.368|0.084|
|44101|169.606|16.948|
|48001|238.481|17.765|

882021/960021katsayı hesabı doğru; scipy polyphase işlem yaptığı için her parçada bütün katsayılarla naif convolution varsayımı yanlış. İlk ölçülen sıcak maliyet30msbütçenin önemli kısmıydı, fakat rapordaki saniyelerce kilitlenme değildi.

Devam ölçümünde yalnız patolojik oran için2000payda sınırı uygulandı.8–192kHz taramasında örneklenen en kötü yaklaşım hatası 250ppm'dir (191952Hz);30saniyelik PTT'de oran kaynaklı yaklaşık7.5msüst sınırıdır. Önceki125ppm iddiası eksik taramaya dayanıyordu ve yanlıştı. 30ms parça çıktı uzunluğu480'den en fazla1örnek sapma testiyle sınırlandı. Bu makinedeki tek tekrar ölçümü:44100=4.501/0.096ms,44101=9.460/0.208ms,48001=0.229/0.129ms (soğuk/sıcak100çağrı ortalaması). Süreler sistem yüküne bağlıdır; gerçek standart dışı cihaz, uzun ses ve tanıma kalitesi hâlâ fiziksel test ister.

Global PTT için ayrıca her isteğe5sn zaman aşımı eklendi; abort sonrası error'ın ikinci hata/rollback üretmediği sentetik testle doğrulandı.

1:1'e yuvarlanan15999/16001Hz için FIR kurulumundaki ValueError ayrıca düzeltildi: sesin bağımsız kopyası döndürülüyor. Tam8000..192000tamsayı hız taraması oran hatasını250ppm, paydayı2000 ve payı4000ile sınırlayan regresyon testine alındı. Bu oran sınırı, parça başına örnek yuvarlamasının bütün birikimli etkilerini ölçmüş olmak anlamına gelmez.

## Testler ve teslim sınırı

- 28smoke+15report+10followup+4third+9fourth+15complete+10new =91Python testi geçti.
- Altı Node test dosyası geçti; yeni test_new_report_frontend.js gerçek kaynak fonksiyonlarını VM/mock üzerinden çalıştırır.
- Render edilmiş index/overlay inline JS kontrolü mevcut report suite içinde; main.js node --check, buyedektir/transkribe/yeni test py_compile ve pyflakes temiz.
- Canlı OpenAI/DeepL çağrısı, API ücretli eval'i, model indirme, ses kaydı, gerçek tkinter/Electron penceresi, GPU ve8saat soak yapılmadı. Bunlar mock test başarısından türetilmedi.
- Önceden kirli arşiv dosyaları ve kişisel ayarlar korunur; commit'e dahil edilmez. Portable çıktı yeniden üretilir ve kaynaklarla karşılaştırılır.
