---
version: alpha
name: Whisper Pro
description: Türkçe okunuşla yabancı dilde canlı görüşme konsolu
colors:
  primary: '#7296ff'
  background: '#101521'
  surface: '#192131'
  text: '#edf2fc'
  translation: '#91cbd7'
  reader: '#f1f5ff'
  readerText: '#213151'
typography:
  sans:
    fontFamily: 'Segoe UI Variable Text, Segoe UI, sans-serif'
  reading:
    fontFamily: 'Arial, Segoe UI, sans-serif'
  mono:
    fontFamily: 'Consolas, monospace'
rounded:
  DEFAULT: '10px'
  sm: '6px'
  lg: '14px'
spacing:
  panel: '20px'
  control: '8px'
components:
  reader:
    backgroundColor: '#f1f5ff'
    textColor: '#213151'
---

# Whisper Pro tasarım sistemi

## Overview

Windows'ta görüşme sırasında kullanılan ürün arayüzü. Kullanıcı Türkçe bilir, karşı tarafın dilini bilmese de Türkçe harfli okunuşu seslendirir. Kaynak: AGENTS.md, BASLANGIC.md, buyedektir.py cevap modu sözleşmesi. Kullanıcının 14 Eylül 2026 geri bildirimi önceki yeşil kart düzenini yeterince programa uygun bulmadı; bu revizyon o tasarımın yerine geçer.

Referans dünyası: simultane tercüman masası; ses kontrol şeridi, gelen konuşma ve tek bir açık okuma yüzeyi. İmza öğesi koyu konsol üzerindeki açık renkli, büyük puntolu okunuş yüzeyidir. Pazarlama sayfası, istatistik panosu veya eşit ağırlıklı dört kart görünümü kullanılmaz. Arayüz dili Türkçe; yabancı alfabeler konuşma içeriğidir, Japonya pazarı veya Japonca arayüz varsayılmaz.

Token sahibi Model B: static/whisper-pro-theme.css içindeki --wp-* değişkenleri. Bu belge değerleri ve gerekçeleri yansıtır; CSS → eski --primary/--bg-* aliasları → ortak bileşenler tek çalışma yoludur. Electron ve Flask aynı HTML/CSS'yi kullanır.

## Colors

primary → --wp-accent, background → --wp-canvas, surface → --wp-surface, text → --wp-text, translation → --wp-translation. reader ve readerText → --wp-reader / --wp-reader-text. Mavi eylemi, camgöbeği çeviriyi belirtir; hata/kayıt durumu ayrı semantik değişkenlerde kalır. Okuma zemini iki temada da açık ve mürekkepli kalır. Açık tema beyaz/gri yüzeyler ve koyu mavi eylemler kullanır. Durum metinleri renk olmadan da anlaşılır.

## Typography

Arayüzde sans, okunuşta reading, küçük ölçümlerde mono ailesi. Kontroller 12–14 px; bölüm başlıkları 17–20 px; okunuş 32–42 px. Yabancı metinde sistemin Japonca/Arapça/Çince font fallback'i kullanılır; yabancı cümle ve okunuş kırpılmaz. Kullanıcı Türkçe olduğu için okunuş italik veya dekoratif harflerle verilmez.

## Layout

Üstte küçük uygulama başlığı, altında sürekli erişilebilir dil ve kayıt şeridi. Masaüstünde sol gelen konuşma, sağ cevap seçimi + tek açık okuma kartı. Durumlar altta kompakt şeritte. 980 px altında paneller üst üste; her eylem ulaşılabilir. Ayarlar kapatılabilir, modal olmayan sabit paneldir. Konuşma ve cevap alanları mevcut bağımsız kaydırma davranışını korur; kısa pencerede içerik kaydırılır.

## Elevation & Depth

Temel yüzeyler düz ve ince kenarlıklıdır. Gölge yalnız ayar paneli ve okuma diyaloğu gibi üst katmanlarda. Animasyon canlı sesin durumunu göstermek içindir; ortam animasyonu yoktur.

## Shapes

Kontroller 6 px, paneller 14 px. Küçük durum işaretleri dışında geniş hap düğmeler yoktur. Okuma alanı kart yığını gibi görünmez.

## Components

Cevap sahibi static/cockpit.js renderReplyCockpit; seçenekler yerel seçim düğmeleridir, aynı anda bir okunuş görünür. Seçim kısmi/nihai cevapta kararlı metin anahtarıyla korunur. 1–4 mevcut okuma diyaloğunu açar. Okuma modu sahibi static/reading-mode.js; kopyalama, dinleme ve kaydetme mevcut işlevleri çağırır.

Native select ve tarih alanları Windows/Electron popup davranışını kullanır; uygulamaya özel popup geometrisi vaat edilmez. Toast sahibi showAlert, saklama whisperStorage, HTML kaçış sahibi html-utils.js. Backend istek/oturum sahipliği yeniden uygulanmaz. Başlat/Durdur mevcut DOM düğmeleridir; kopyaları oluşturulmaz, mevcut disabled durumunu ve API akışını korur.

Klavye odağı görünürdür; seçili cevap aria-pressed ile belirtilir. Bekleme/boş/hata mesajları yazıyla görünür, kaydırma ve seçili cevap akış sırasında korunur. Düğmeler hover/pressed/disabled durumlarına sahiptir. Scrollbar tüm kaydırma alanlarına global uygulanır, forced-colors sistem renklerine döner. Aramalar özel konuşma içerebildiğinden URL'ye yazılmaz.

## Do's and Don'ts

- Okunuşu ekrandaki baskın metin yap; yabancı metin ve Türkçe anlamı etiketle.
- Dil ve kayıt kontrolünü ayarlara gizleme.
- Gerçek bağlantı/dinleme durumunu kullan; dekoratif canlılık veya uydurma görüşme içeriği gösterme.
- Aynı cevabı iki panelde açık tekrarlama; eski ayrıntılara erişimi koru.
## Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | Native select, index.html | DESIGN.md, Windows popup | native | Electron klavye ve dil seçimi |
| Date | Native input type=date | DESIGN.md, Windows popup | native | Geçmiş arama kontrolleri |
| Form | index.html mevcut ayar fonksiyonları | AGENTS.md, backend API | yerel ayarlar | test_cockpit_request.js |
| Scrollbar | whisper-pro-theme.css global baseline | DESIGN.md | bağımsız panel kaydırması | Chromium computed style |
| Toast | index.html showAlert | Mevcut bildirim sözleşmesi | success, warning, error | test_cockpit_request.js |

Tek ana görüşme ekranı ve salt okunur yardımcı overlay vardır; veri tablosu/CRUD rota ailesi bulunmadığından ayrı UX-CONTRACT.md üretilmez. Bu tablo mevcut sahipleri kaydeder. Native dialog veya yeni veri saklama politikası eklenmez. Overlay aynı --wp-* tokenlarını alias ile kullanır. Seçenek anahtarları, onay/ret kararları ve ağ hatalarının sahipleri mevcut API akışıdır.

## Görüşme araçları

Kullanıcının istediği dört araç ana ekrana eklendi. Kendi cevabını yaz veya söyle bölümü native details ile açılır; sonuç aynı açık okunuş kartına gelir. Bölüm başlangıçta kapalıdır, böylece canlı cevap okunurken yazı alanı okunuşu aşağı itmez. Yazılı çeviri başarılıysa bölüm kapanır; taslak bellekte kalır, kalıcı depoya yazılmaz. Ctrl+Enter IME dışında çevirir. Mikrofon düğmesi Alt ile aynı kayıt sıralamasını kullanır; bitirince çevirir, pencere odağı kaybolunca kayıt iptal edilir.

Hızlı kalıplar ayarlardan ana ekrana taşındı. Dile göre mevcut üretilmiş okunuşlar korunur; seçmek ağ isteği yapmadan ortak kartı açar. Dinleme, kopyalama ve kaydetme ortak kartın eylemleridir. Öneri uzunluğu native select ile Kısa/Normal/Detaylı seçilir, yalnız bu tercih yerel depoda saklanır. Hedefler yaklaşık 3–8 / 8–20 / 20–45 kelime olup iki paralel AI isteğine uygulanır; yazılı çeviri metni özetlenmez.

Görüşmeye hazırlık açıldığında model ve AI durumu sunucudan alınır; ses satırı seçili cihazı gösterir. Ayrı Ses testi düğmesi kısa PCM ölçümü yapar; sessiz WASAPI cihazından örnek gelmemesi bağlantı arızası sayılmaz. Doğrulanmamış anahtar hazır sayılmaz. Eksik satır ilgili mevcut ayara odaklanır. Yeniden kontrol hata/bekleme durumları yazılıdır. Native details ve select klavye davranışları korunur. Yeni kontrol renkleri mevcut --wp-* tokenlarını kullanır; sağ panel tüm araçlar ve cevap için tek kaydırma sahibidir.

## Canlı ses ve metin akışı

Uyarlanabilir duraklama ve önceki üç konuşmayı çeviriye bağlam olarak verme hazırlık bölümünden açılıp kapanır; başlangıçta açıktır. Canlı taslak aynı DOM öğesinde güncellenir ve kesinleşmediği yazıyla belirtilir. Geçmişi okuyan kişinin görünür satırı yeni metin/çeviri geldiğinde korunur; Canlıya dön en yeni satıra taşır.

Karşı tarafın metni yerinde düzenlenir. Ağ hatası taslağı silmez; başka penceredeki düzeltmeyle çakışmada güncel sürüm gösterilir, kullanıcı taslağı korunur. Kaydetme yeni çeviri ve varsa ilgili cevap önerilerini yeniler. Eski sürümün sonuçları gösterilmez. İşlem ayrıntıları konuşmanın bitmesini bekleme, yazıya dökme, çeviri servisi ve kuyruk sayılarını sunar; ölçülmeyen ağ gecikmesi hakkında iddiada bulunmaz. Kontroller ortak renk ve odak tokenlarını kullanır.
