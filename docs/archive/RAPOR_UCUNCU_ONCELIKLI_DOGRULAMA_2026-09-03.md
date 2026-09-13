# Üçüncü rapor — öncelikli doğrulama ve düzeltme

## Kapsam ve sonuç

“6 alan, 153 bug” başlıklı ek okundu. Bu belge 153 ayrı, kanıtlı kayıt sunmuyor: medium/low bölümlerinde toplu başlıklar var; bazı iddialar tekrarlanıyor. Dolayısıyla 153 hata doğrulandığı veya tamamının kapatıldığı söylenemez. Bu çalışma **öncelikli düzeltme turudur**, tam 153-madde denetimi değildir.

Önceki değişiklikler korundu. Yeni alt ajan başlatılmadı. Gerçek sağlayıcı çağrısı, model indirme, mikrofon açma, Electron başlatma veya commit yapılmadı.

## Uygulanan 7 değişiklik

| Alan | Doğrulama ve sonuç |
| --- | --- |
| Pyannote yüklemesi / yaşam döngüsü kilidi | `ensure_ready()` kilit dışına alındı. Bekleme sırasında Stop/Reset gelirse nesil kontrolü geç başlatmayı iptal ediyor. Bloklanan sahte model yüklemesi sırasında kilit alınabildi ve stop sonrası kayıt başlamadı. |
| Beklemede cihaz kopması | `except: pass` kaldırıldı; okuma hatası normal hata sayacı ve bekleme yoluna gidiyor. Sahte cihazla 50 hata sonrası çıkış, 49 bekleme, tek close/terminate doğrulandı. |
| DeepL ayar testi | Ağ testi `_config_lock` dışına taşındı; test edilen anahtar açık parametre olarak sabitlendi. Ağ yanıtı beklerken başka thread ayar kilidini alabildi. |
| Kesilmiş JSON kurtarma | `{name}` gibi string içindeki süslü parantezleri bozan düz regex yerine JSON decoder kullanıldı. Tamamlanmış seçenek, ardından yarım seçenek varken doğru kurtarıldı. |
| Geçmiş arama sırası | Arama nesli eklendi. Eski sorgu geç döndüğünde yeni sonucu ezemiyor; boş sorgu eski isteğin görünümü geri açmasını engelliyor. |
| AI HTTP isteği | 60 saniyelik AbortController sınırı eklendi; yanıt gövdesini okuma da bu sınır içinde. Timeout sonrası buton ve istek haritaları temizleniyor. Bu, sunucuda başlamış ücretli işi iptal garantisi değildir. |
| Konuşmacı baş harfleri | İki karakterlik avatar metni HTML-escape ediliyor. Önlem uygulandı, ancak rapordaki tam self-XSS zinciri yeniden üretilmedi; iki karakterlik alanın varlığı tek başına çalıştırılabilir XSS kanıtı değildir. |

## Kontrol edilen yanlış veya abartılı iddialar

- **Nesne anahtarı sızıntısı:** `transcriptionTexts` bir JavaScript nesnesidir. `object[123]` ve `object['123']` aynı özelliği kullanır. Yaz/oku/sil testi geçti; raporun “hasOwnProperty her zaman false” iddiası yanlış.
- **Her raise kilidi kalıcı sızdırır:** `_transcribe_audio` hata blokları `commit_lock_held` kontrolüyle kilidi bırakıyor. Context manager okunabilirliği iyileştirebilir; ama bu koddan rapordaki koşulsuz kalıcı sızıntı sonucu çıkarılamaz.
- **Tek yavaş paralel AI çağrısı tüm partial'ı çöpe atar:** Tamamlanan cevaplar `raws` içinde tutuluyor; `if not any(raws)` kontrolü zaten var. Arayüz de success-false cevabında birikmiş partial'ı koruyor. Önerilen temel koruma zaten mevcut.
- **Top-level JSON array AttributeError:** Parser `isinstance(parsed, dict)` kontrolü kullanıyor; array üzerinden koşulsuz `.get()` çağırmıyor. Array formatının seçenek olarak kabul edilmemesi ayrı sözleşme konusudur.
- **HOST env aktarılmıyor:** Electron child ortamında `...process.env` zaten var; backend de dotenv okuyor. Sırf `HOST` ayrı satırda yazılmadığı için ortam değişkeni aktarılmıyor iddiası doğru değil. Local-only varsayılanı korunuyor.
- **Yeniden tıklamayla sınırsız istek:** `getAIResponse` başında aktif istek kontrolü, sonunda `finally` temizliği var. Esas açık süre sınırıydı; bu turda eklendi.
- **Sayısal konuşma mutlaka halüsinasyondur:** Telefon, tarih, fiyat ve sayı söyleme geçerli kullanım. Sırf rakam oranı yüksek diye filtre eklenmedi.
- **NFKD yabancı yazıyı Türkçe okunuşa çevirir:** Unicode ayrıştırma genel transliterasyon değildir; İbranice/Tayca/Hintçe için telaffuz çözümü olarak uygulanmadı.
- **Ağ kopunca tüm pending haritaları silinsin:** HTTP isteği SocketIO bağlantısından bağımsız tamamlanabilir. Koşulsuz silme, kullanılabilir sonucu geçersiz kılabilir; timeout ile sınırlama tercih edildi.

## Açık kalan kapsam

Telaffuz normalizasyonunun dile göre idempotansı, outro filtrelerinin false-positive dengesi, Türkçe Windows netstat çıktısı, bozuk profil dosyasının kurtarılması, dosya rotasyonu/paylaşım kilidi, Electron gezinme sınırları, uzun oturum kaynak kullanımı ve özetlenmiş medium/low maddelerin tamamı bu turda bitirilmiş değildir.

Özellikle normalizasyonda raporun “tek-pass regex” önerisi tek başına idempotansı garanti etmez: ham İtalyanca `c` ile zaten Türkçeleştirilmiş `c` aynı anlamda değildir. Kapsamlı değişiklik, ham metin/okunuş sözleşmesi ve dil başına testlerle ele alınmalıdır. Kullanıcı okunuşunu bozabilecek toplu değişiklik uygulanmadı.

153 maddelik tam kapanış tablosu için kısa özet değil, her bulgunun tetikleme koşulu, kod yolu ve test kanıtını içeren asıl alt raporlar gerekir. Mevcut özette açıkça anlatılmış kalan maddeler ise bağımsız olarak ayrıca doğrulanabilir.

## Testler

- `test_third_report.py`: 4 yeni Python testi geçti.
- `test_third_frontend.js`: eski/yeni arama sırası, boş sorgu, nesne anahtarları, AI timeout ve istek temizliği geçti.
- Mevcut smoke paketinin 28 test işlevi geçti.
- Önceki rapor testleri: 15 + 10 geçti.
- Önceki iki frontend paketi ve Electron yardımcı testleri geçti.
- Python compile/pyflakes, render edilmiş HTML JavaScript kontrolleri ve `git diff --check` temiz.
- Paket yeniden oluşturuldu; paket güvenlik taraması temiz. Gerçek cihaz/API testi yapılmadı.

Değişiklikleri kullanmak için açık uygulama normal şekilde kapatılıp yeniden açılmalı. Commit oluşturulmadı; bağımsız arşiv değişiklikleri korunuyor.
