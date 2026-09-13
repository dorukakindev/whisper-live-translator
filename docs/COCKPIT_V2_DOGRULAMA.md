# Cockpit v2 doğrulama kapsamı

Bu belge mevcut `HEAD` (`ad2878a`) üzerinden yürütülen doğrulamanın canlı kontrol
listesidir. Kullanıcı verisi, gerçek API anahtarı, gerçek ses veya dış ağ kullanılmaz.

## Tasarım planı

- Renk: graphite `#090b0e`, yüzey `#151b22`, amber `#d5a35c`, cyan
  `#8fc5c2`, yeşil `#69b58b`, açık tema için mevcut karşılıkları.
- Yazı: arayüzde Segoe UI Variable; okunuşta aynı ailenin daha büyük, ağır ve
  geniş satır aralıklı biçimi. Yeni font veya ağ kaynağı yok.
- Yerleşim: masaüstünde daraltılabilir ayarlar + merkez transkript + kalıcı sağ
  cevap paneli; dar ekranda cevap paneli transkriptin altına geçer.
- İlke: görsel ağırlık yalnız okunacak fonetik metinde; native metin ve anlam
  bağlam sağlar, dekorasyon eklenmez.

```text
Masaüstü: [ ayarlar ] [ canlı konuşma akışı ] [ cevap / okunuş ]
Dar ekran: [ komutlar ] [ canlı konuşma akışı ] [ cevap / okunuş ]
```

## Kapsam tablosu

| Gereksinim | Mevcut uygulama ve kaynak konumu | Eksik veya hatalı davranış | Yapılacak değişiklik | Doğrulama yöntemi | Son durum |
|---|---|---|---|---|---|
| Merkez transkript, sağ kalıcı cevap paneli | `templates/index.html`: cevaplar transkript öğelerinin içinde | Ayrı ve kalıcı cevap yüzeyi yoktu | Kararlı sahiplikli cevap dock'u eklendi; dar ekranda alta geçiyor | Gerçek tarayıcı 5 boyut + davranış testi | Tamamlandı |
| Ayarların alanı daraltmaması | `.control-panel` sürekli 390–430 px idi | Konuşma alanı gereksiz daralıyordu | `controlsToggleBtn`, kalıcı tercih ve dar ekranda varsayılan kapalı durum eklendi | Tarayıcı masaüstü/dar ekran | Tamamlandı |
| Dört cevabın karşılaştırılması ve okunuş hiyerarşisi | `.answer-option`, gizli `ans-*` okunuş | Okunuş tıklamadan görünmüyordu | Dock en fazla dört kart gösteriyor; okunuş sürekli görünür ve en büyük metin | DOM yük testi + koyu/açık ekran görüntüsü incelemesi | Tamamlandı |
| Tek tıkla Okuma modu | `openReadingMode` vardı | Modal odak yönetimi ve kart akışı eksikti | Her kartta gerçek düğme; odak modal içine ve kapanınca açana dönüyor | 600×800 gerçek tarayıcı klavye testi | Tamamlandı |
| Cevap paneli sahipliği | `_pendingAiRequests`, `_activeAnswerRequests` | Panel hedefi/temizleme/reconnect invalidasyonu yoktu | Seçili transkript + nesil koruması + içerik anahtarı eklendi | `test_cockpit_behavior.js` A/B, stale ve clear kontrolleri | Tamamlandı |
| Partial/final okuma korunumu | Açık kartlar cevap metniyle yeniden açılıyordu | İndekse bağlı son seçenek listesi vardı | İçerik tabanlı kararlı anahtar; modal dock yeniden çiziminden bağımsız | Ters sıra ve tekrar çizim davranış testi | Tamamlandı |
| Durum şeridi doğruluğu | Metin regex'i ve 500 ms interval vardı | “Bağlanıyor” yeşil, yinelenen ARIA yazımı, 5/4 sütun hatası | Gerçek `_socketConnected`, değişiklik bazlı yazım, 5 sütun ve mevcut stats akışı | `test_cockpit_frontend.js`; 10.000 aynı değer yazımı | Tamamlandı |
| Gecikme açıklığı | Kısa ve belirsiz etiketler vardı | Kuyruk süre gibi okunabiliyor; hata halinde değer bayat kalıyordu | `ASR p95`, `Çeviri p95`, `Kuyruk`; hata halinde `Veri yok` | Stats kaynak incelemesi + durum davranış testi | Tamamlandı |
| 1–4 klavye akışı | Son render edilen inline cevaplara bağlıydı | Görünür dock, repeat ve düzenleme alanı koruması eksikti | Görünür dock düğmeleri; input/modifier/repeat korumaları | Gerçek tarayıcı input/body klavye testi + statik sözleşme | Tamamlandı |
| Modal erişilebilirliği | Basit overlay idi | Focus trap, geri dönüş ve font kontrolü yoktu | `role=dialog`, `aria-modal`, Tab döngüsü, Escape, A-/A+ ve uzun metin sarma | 600×800 modal ekranı ve gerçek odak testi | Tamamlandı |
| Timer/listener ve DOM sınırı | `MAX_DOM_ITEMS`, soket listener guard'ı vardı | Yaşam döngüsüz 500 ms cockpit intervali ve yanlış “soak” adı vardı | Interval kaldırıldı; 1.000 render/10.000 durum olayı hızlandırılmış yük olarak ayrıldı | Eski listener/DOM regresyonları + yeni yük testi | Tamamlandı; gerçek 30 dk soak çalıştırılmadı |
| Görsel doğrulama | Önceki turda yalnız CSS varsayımı vardı | Gerçek viewport ve tema kanıtı yoktu | Ağsız sentetik fixture gerçek tarayıcıda ve Electron Chromium'da çalıştırıldı | 1440×900, 1280×720, 900×700, 600×800, 380×260; koyu/açık | Tamamlandı |
| Regresyon ve paket | Eski sonuçlar vardı | Yeni kapsam sonrası yeniden koşulmalıydı | Fail-fast Python/JS zinciri, build ve SHA-256 eşliği uygulandı | 91 Python kontrolü, 9 JS dosyası, inline `node --check`, build | Tamamlandı |
| Güvenli commit | Önceki iki commit temizdi | Yeni çalışma ayrı ve denetlenebilir tutulmalıydı | Yalnız tabloda listelenen görev dosyaları açıkça stage edildi; push yapılmadı | `git diff --cached --check`, commit ve son status | Tamamlandı |

## Başlangıç riskleri

1. `whisper-pro-theme.css` HTML içi stillerden sonra yükleniyor; yeni yerleşim
   kuralları tema dosyasında tanımlanmazsa ezilebilir.
2. Cevaplar bugün transkript DOM'una bağlı; kaynak öğe budanınca kalıcı panelin
   ayrıca sahiplik ve yaşam döngüsü yönetmesi gerekir.
3. Global klavye olayları ile PTT ve kart içi düğmeler çakışabilir.
4. Okuma modu yeniden render'dan bağımsız tutulmazsa kullanıcının okuduğu metin
   değişebilir veya modal kapanabilir.
5. Gerçek Electron ve sistem sesi testi sentetik tarayıcı testinden farklıdır;
   kanıt kapsamları teslimde ayrı raporlanacaktır.

## Son doğrulama kanıtı

- Gerçek tarayıcı: dış ağsız fixture 1440×900, 1280×720, 900×700,
  600×800 ve Electron overlay varsayılanı olan 380×260 boyutlarında koyu ve açık
  temada incelendi. Dört uzun kart, açık ayarlar, taşma ve kaydırma kontrol edildi.
  380×260'ta bulunan tooltip yatay taşması düzeltildikten sonra tekrar ölçüldü.
- Klavye: input içindeki `1` yok sayıldı; gövde üzerindeki `1` görünür ilk cevabın
  Okuma modunu açtı; Shift+Tab modal içinde kaldı; Escape kapattı ve odağı açan
  düğmeye döndürdü.
- Hızlandırılmış yük: 10.000 aynı durum güncellemesi tek DOM metin yazımı yaptı;
  1.000 cevap render'ında dock dört kartı aşmadı. Bu sonuç gerçek zamanlı soak
  değildir. 30 dakikalık gerçek soak çalıştırılmadı.
- Electron: ağsız fixture doğru Electron çalıştırıcısıyla ve donanım hızlandırması
  kapalı çalıştırıldı. Beş viewport, dört kart, yatay taşma, görünür düğmeler,
  benzersiz DOM kimlikleri, stale sonuç reddi, okuma metninin korunması ve açık
  temadaki modal doğrulandı; ekran görüntüleri `artifacts/cockpit-v2` altında üretildi.
- Python: `.venv` ile `py_compile`, `pyflakes`, `test_smoke.py` ve altı kalıcı
  regresyon dosyası geçti (toplam 91 kontrol).
- Frontend: dokuz JS regresyon/davranış dosyası geçti. `test_frontend_regressions.js`
  Jinja `app_token` yerine sentetik değer koyup hem `index.html` hem `overlay.html`
  inline script bloklarını `node --check` ile doğruladı.
- Paket: `npm.cmd run build` geçti; build güvenlik taraması hassas/kişisel dosya
  adı bulmadı. Paketlenmiş `templates/index.html` ve
  `static/whisper-pro-theme.css` SHA-256 değerleri kaynak dosyalarla eşleşti.
