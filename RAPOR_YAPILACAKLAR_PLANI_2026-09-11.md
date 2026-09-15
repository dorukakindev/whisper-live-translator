# Whisper Pro — Yapılacaklar ve Uygulama Planı

> Tarih: 2026-09-11 · Kaynak: Tam kapsam kod incelemesi (kod DEĞİŞTİRİLMEDİ, yalnızca raporlandı)
> Kapsam: `buyedektir.py`, `templates/index.html`, `templates/overlay.html`, `main.js`, `build.js`, test paketi, canlı backend doğrulaması
> Bu belge, inceleme sohbetindeki TÜM bulgu ve önerileri önceliklendirilmiş uygulama planına dönüştürür.

---

## 0. Doğrulama Durumu (inceleme anında bizzat çalıştırıldı)

| Test | Sonuç |
|---|---|
| `python -m py_compile` + `pyflakes` (buyedektir.py, transkribe.py, launcher_whisper.py, _gen_phrases.py) | ✅ Temiz |
| `test_smoke.py` (28 senaryo) | ✅ TÜM TESTLER GEÇTİ |
| 6 Python regresyon dosyası (48 unittest) | ✅ Hepsi OK |
| 9 Node frontend/regresyon testi | ✅ Hepsi geçti |
| `test_cockpit_browser.js` (gerçek Electron/Chromium, 5 ekran boyutu) | ✅ Geçti |
| `node --check` main.js / preload.js / main_helpers.js / build.js | ✅ Temiz |
| `index.html` inline script'leri (Jinja render edilerek) | ✅ Sözdizimi temiz |
| Canlı backend (PORT=5099): `GET /` → 200, `GET /api/stats` → 200 | ✅ Çalışıyor |
| OpenAI anahtar doğrulaması (canlı) | ❌ **401 invalid_api_key — anahtar geçersiz** |

---

## 1. Hedefler

1. Kullanıcının hissettiği en büyük sorunları önce çözmek (AI önerisi çalışmıyor, sessizlik eşiği kayması).
2. Güvenlik boşluklarını kapatmak (tokensuz GET API'leri, rate-limit).
3. UX'i okunuş-okuma senaryosuna göre optimize etmek.
4. Tek dosya mimarisini sürdürülebilir hale getirmek (sabitleri tekilleştirme, test konsolidasyonu).

---

## 2. Aşama 1 — Acil (tahmini toplam ~1-2 saat)

### Görev 1.1 — Geçersiz OpenAI anahtarını yenile [ORTAM]
- **Yer:** `.env` → `OPENAI_API_KEY`
- **Yapılacak:** Yeni anahtar alınıp `.env`'e yazılacak; backend yeniden başlatılacak.
- **Doğrulama:** Log'da "OpenAI API key basariyla dogrulandi" satırı; UI'dan bir cevap önerisi alınacak.

### Görev 1.2 — `silence_duration` fallback bug'ı [BUG · ORTA]
- **Yer:** `buyedektir.py:3134-3137` (`update_settings`)
- **Sorun:** Geçersiz/eksik girdide fallback `2.0`; gerçek varsayılan `buyedektir.py:2553`'te `1.2` ve UI slider'ı (`index.html:2152`) 1.2. Bozuk istek sessizlik eşiğini 1.2 → 2.0 sn'ye kaydırıyor, segmentler geç kesiliyor.
- **Yapılacak:** Fallback mevcut değer (`self.silence_duration`) veya sabit `DEFAULT_SILENCE_DURATION = 1.2` olacak; `vad_level` fallback'i de aynı desenle denetlenecek (şu an doğru: 2).
- **Doğrulama:** `test_smoke.py` içinde `update_settings` sınır testlerine `None`/`inf`/eksik alan vakaları eklenecek; tüm testler geçecek.

### Görev 1.3 — API anahtarı UI uyarı rozeti [EKLEME]
- **Yer:** `index.html` header + `/api/status` (veya yeni bir durum alanı)
- **Yapılacak:** Geçersiz/eksik anahtar durumunda kalıcı, kapatılabilir uyarı rozeti ("AI önerileri kapalı — anahtar geçersiz"). Şu an durum yalnız log'da.
- **Doğrulama:** Geçersiz anahtarla başlatınca rozet görünüyor; geçerli anahtarla kayboluyor.

### Görev 1.4 — GET API'lerine token kontrolü [GÜVENLİK · DÜŞÜK-ORTA]
- **Yer:** `buyedektir.py:83-92` (`require_local_app_token`)
- **Sorun:** `/api/transcriptions` (tüm konuşma geçmişi) ve `/api/stats` tokensuz okunabiliyor. CORS same-origin olduğundan web sayfaları okuyamaz; ama yerel süreçler ve `HOST=0.0.0.0` durumunda LAN okuyabilir.
- **Yapılacak:** GET'ler de token isteyecek (UI ve overlay zaten `APP_TOKEN`'a sahip); en azından `HOST != 127.0.0.1` iken zorunlu. `BACKEND_NONCE` boşken (Electron dışı çalıştırma, `buyedektir.py:65`) `/api/check_models` davranışı `main_helpers.isExpectedBackendResponse` ile uyumlu tutulacak.
- **Doğrulama:** Tokensuz `curl /api/transcriptions` → 403; UI'dan geçmiş yine düzgün yükleniyor.

---

## 3. Aşama 2 — Kısa vade (~yarım gün)

### Görev 2.1 — AI endpoint rate-limit [EKLEME · GÜVENLİK]
- **Yer:** `buyedektir.py:4997` (`/api/generate_ai_response`), `buyedektir.py:5544` (`/api/ai_chat`)
- **Sorun:** Hız sınırsız. `_ai_executor` 4 worker; her istek 2 paralel OpenAI çağrısı × 60 sn okuma timeout'u (`buyedektir.py:1631`). 30 sn `as_completed` timeout'u sonrası `future.cancel()` yalnızca bekleyenleri iptal ediyor (`buyedektir.py:5294-5297`) — takılan çağrılar arka planda yaşamaya devam edip havuzu dolduruyor.
- **Yapılacak:** Transcript başına 1 aktif istek kilidi + `request_id` dedup + küresel in-flight sayacı.
- **Doğrulama:** Aynı transcript'e hızlı çift tıklamada tek istek sunucuya gidiyor.

### Görev 2.2 — Gecikme sağlığı göstergesi [EKLEME · UX]
- **Yer:** `index.html` header; veri: `transcription_lagging` olayı + `/api/stats` p95 değerleri
- **Yapılacak:** 🟢 <1sn / 🟡 1-3sn / 🔴 >3sn rozet. "Neden cevap gelmiyor?" sorusunu görünür kılar.
- **Doğrulama:** Manuel gecikme enjeksiyonu (test) ile rozet renk değişimi.

### Görev 2.3 — `GET /api/settings` + ayar senkronizasyonu [EKLEME]
- **Yer:** `buyedektir.py` routes; `index.html:3444` (ayarlar yalnız localStorage'da)
- **Sorun:** İki pencere/sekme açılınca ayarlar ayrışıyor; son yazan kazanıyor. `GET /api/settings` şu an 404.
- **Yapılacak:** GET endpoint'i + ayar değişiminin socket olayıyla yayınlanması.
- **Doğrulama:** İki sekmede birinde eşiği değiştirince diğeri güncelleniyor.

### Görev 2.4 — Dışa aktarma butonu [EKLEME · UX]
- **Yer:** `index.html` geçmiş paneli; veri zaten hazır (`transcriptions.txt`, `/api/transcriptions`)
- **Yapılacak:** "İndir (.txt / .srt / .json)" butonu.
- **Doğrulama:** Üç format da inip içerik tam.

### Görev 2.5 — Aramayı tüm geçmişe genişletme [GELİŞTİRME]
- **Yer:** `index.html:4224` (mini arama yalnız DOM'daki ~100 öğede)
- **Yapılacak:** `/api/transcriptions` üzerinden backend araması + tarih/konuşmacı filtresi.
- **Doğrulama:** 500+ kayıtta 1 sn altında sonuç.

### Görev 2.6 — Log hijyeni [GELİŞTİRME]
- **Yer:** `buyedektir.py:5293` (debug'da kaybolan emit hatası), `buyedektir.py:1654` (`response.text[:1000]` logu)
- **Yapılacak:** Kritik yutulan hatalar `warning`+ seviyesine çekilecek; hata gövdesi loglanırken konuşma içeriği maskelemenecek.

---

## 4. Aşama 3 — Orta vade (1-2 hafta, sırayla bağımsız görevler)

### Görev 3.1 — Okunuş birincil hiyerarşi [TASARIM]
- **Yer:** `index.html:5845-5851` (okunuş toggle arkasında), cockpit kartları
- **Yapılacak:** Okunuş varsayılan görünür + daha büyük punto + artırılmış satır aralığı. Temel senaryo "okunuşa bakıp sesli okumak" — göz zaman baskısında en büyük metne gider.

### Görev 3.2 — Partial → final geçiş animasyonu [TASARIM]
- **Yer:** `index.html` partial önizleme mantığı (`new_transcription` değiştiriyor)
- **Yapılacak:** Önizleme satırı final satırla aynı konumda opacity/transform geçişiyle dönüşecek; okuma ritmi bozulmayacak.

### Görev 3.3 — Overlay tema entegrasyonu [TASARIM]
- **Yer:** `templates/overlay.html` (kendi inline stillerini taşıyor)
- **Yapılacak:** Overlay `whisper-pro-theme.css` değişkenlerine bağlanacak; açık/koyu geçişte tutarlı olacak.

### Görev 3.4 — Erişilebilirlik denetimi [TASARIM]
- **Yapılacak:** Açık temada konuşmacı badge kontrastları WCAG AA; focus-visible halkaları; 1-4 kısayol çiplerinin okuma modu dahil her yerde çalıştığının doğrulanması (64 inline onclick / 16 addEventListener dengesine dikkat).

### Görev 3.5 — PTT dalga formu geri bildirimi [EKLEME]
- **Yer:** `index.html`; veri zaten `voice_activity` olayında akıyor
- **Yapılacak:** Kayıt sırasında mini seviye göstergesi ("sesim gidiyor" güveni).

### Görev 3.6 — Okunuş kalite geri bildirimi [EKLEME]
- **Yapılacak:** Okunuş başına 👍/👎; toplanan veriyle `PRONUNCIATION_GUIDES` / `_normalize_turkish_pronunciation` iyileştirme döngüsü.

### Görev 3.7 — `/healthz` endpoint'i [EKLEME]
- **Yapılacak:** Model yüklü mü, executor'lar canlı mı, son hata — Electron `checkServerReady` ve teşhis bundan beslenecek.

---

## 5. Aşama 4 — Mimari borç (uzun vade, tek tek ve bağımsız)

### Görev 4.1 — Sabitleri tekilleştirme [MİMARİ · ÖNCE BU]
- **Sorun:** Görev 1.2'deki bug'ın kök nedeni — varsayılanlar iki yerde tanımlı.
- **Yapılacak:** `buyedektir.py` bölünmeden tüm sabitler/varsayılanlar tek tabloda toplanacak (`DEFAULTS = {...}`). Dosya 5162 satır / 156 fonksiyon.

### Görev 4.2 — Frontend modüllerine ayrıştırma [MİMARİ]
- **Yapılacak:** `index.html` (~6000 satır) içinden `QUICK_PHRASES`, cockpit ve okuma modu `static/` altına ayrı dosyalara çıkacak (build adımı gerekmez). Jinja render etmeden doğrudan `node --check` yapılabilir hale gelir.

### Görev 4.3 — Test konsolidasyonu [MİMARİ]
- **Sorun:** Kökte 18 `test_*` dosyası + 12 rapor; hangi sözleşmenin korunduğu belirsiz.
- **Yapılacak:** `test_smoke.py` tek otorite ilan edilecek; kalıcı regresyonlar oraya taşınacak; geri kalan `tests/archive/`'e; raporlar `docs/archive/`'e.

### Görev 4.4 — build.js senkron uyarısı [MİMARİ]
- **Yapılacak:** Kaynak dosyalar `dist/`'ten yeni ise build uyarısı ("dist eskimiş, npm run build çalıştır").

### Görev 4.5 — `.env` temizliği [MİMARİ]
- **Yapılacak:** Ölü `MINIMAX_*` anahtarları kaldırılacak (kod zaten yok sayıyor — geri bağlanmasın).

---

## 6. Bilinçli olarak YAPILMAYACAKLAR (incelemede bilinçli tasarım bulundu)

- `buyedektir.py`'ın tam modül bölünmesi — prompt sırası / prefix caching / thread sözleşmeleri hassas; test güvencesi olmadan bölünmeyecek (önce 4.1).
- Prompt kural bloklarının yeniden sıralanması (AGENTS.md uyarısı: statik bloklar ÖNCE, değişken içerik SONRA — OpenAI prefix caching).
- `dist/`'in elle güncellenmesi — daima `npm run build`.

---

## 7. Her görevin genel kabul kriterleri

1. `python -m py_compile buyedektir.py` ve `python -m pyflakes buyedektir.py` temiz.
2. `python test_smoke.py` → exit 0 (TÜM TESTLER GECTİ).
3. Görev frontend'e dokunduysa: inline script'ler Jinja-render edilerek `node --check`'ten geçmeli + ilgili `test_*frontend*.js` çalışmalı.
4. Görev görsel davranışa dokunduysa: `test_cockpit_browser.js` çalışmalı.
5. Backend değişikliğinde canlı duman testi: `PORT=509x python buyedektir.py` → `GET /` 200 + ilgili endpoint doğrulaması.
6. Dosya LF satır sonları korunacak; yorumlar Türkçe, mevcut yoğunluk/üslupla uyumlu olacak (AGENTS.md).

---

## 8. Özet matris

| # | Görev | Tür | Önem | Aşama | Durum |
|---|---|---|---|---|---|
| 1.1 | OpenAI anahtarı yenile | Ortam | Kritik | 1 | ☐ |
| 1.2 | silence_duration fallback | Bug | Orta | 1 | ☐ |
| 1.3 | API anahtarı UI rozeti | Ekleme | Orta | 1 | ☐ |
| 1.4 | GET API token | Güvenlik | Orta | 1 | ☐ |
| 2.1 | AI rate-limit | Ekleme | Orta | 2 | ☐ |
| 2.2 | Gecikme göstergesi | Ekleme/UX | Orta | 2 | ☐ |
| 2.3 | GET /api/settings | Ekleme | Düşük | 2 | ☐ |
| 2.4 | Dışa aktar butonu | Ekleme/UX | Düşük | 2 | ☐ |
| 2.5 | Geçmiş araması | Geliştirme | Düşük | 2 | ☐ |
| 2.6 | Log hijyeni | Geliştirme | Düşük | 2 | ☐ |
| 3.1 | Okunuş hiyerarşisi | Tasarım | Orta | 3 | ☐ |
| 3.2 | Partial→final geçişi | Tasarım | Düşük | 3 | ☐ |
| 3.3 | Overlay teması | Tasarım | Düşük | 3 | ☐ |
| 3.4 | Erişilebilirlik | Tasarım | Düşük | 3 | ☐ |
| 3.5 | PTT seviye göstergesi | Ekleme | Düşük | 3 | ☐ |
| 3.6 | Okunuş 👍/👎 | Ekleme | Düşük | 3 | ☐ |
| 3.7 | /healthz | Ekleme | Düşük | 3 | ☐ |
| 4.1 | Sabit tekilleştirme | Mimari | Orta | 4 | ☐ |
| 4.2 | Frontend modülleri | Mimari | Düşük | 4 | ☐ |
| 4.3 | Test konsolidasyonu | Mimari | Orta | 4 | ☐ |
| 4.4 | build.js uyarısı | Mimari | Düşük | 4 | ☐ |
| 4.5 | .env temizliği | Mimari | Düşük | 4 | ☐ |

---

## §10 Tasarım & UX Detay Planı

> Bu bölüm, incelemedeki tasarım önerilerini Aşama 3 görevlerinin (3.1–3.4, 3.5)
> tek satırlık özetinden çıkarıp uygulanabilir detaya indirir. Önce mevcut
> tasarımın KORUNMASI gereken güçlü yanları listelenmiştir — değişiklikler
> bunları bozmamalıdır.

### 10.0 Mevcut Tasarımın Güçlü Yanları (korunacaklar)

İnceleme sırasında doğrulanan, iyi kurgulanmış tasarım kararları:

| Özellik | Konum | Neden iyi |
|---|---|---|
| Okuma modu (`openReadingMode`) | `index.html:5097` | A−/A+ punto kontrolü, tam ekran, `aria-label`'lı butonlar — temel kullanım senaryosuna (yüksek sesle okuma) doğrudan hizmet ediyor |
| `aria-expanded` + `aria-controls` | `index.html:5836` | Cevap seçeneği toggle'ları erişilebilirlik açısından doğru bağlanmış |
| `runtime-safety.js` depolama düşüşü | `static/runtime-safety.js` | localStorage dolu/kapalıysa bellek içi Map'e düşer + kullanıcıya uyarı gösterir — sessiz veri kaybı yok |
| Boş durum ekranları | `index.html:4048`, `4092` | SVG ikon + yol gösterici metin ("Başlat butonuna tıklayın") |
| `transcription_lagging` uyarısı | `buyedektir.py:3789` → UI | Kuyruk dolunca kullanıcı bilgilendiriliyor |
| Okunuş kapsülü (`.okunus-capsule`) | `index.html:5848` | Okunuş metni görsel olarak ayrıştırılmış |
| Kısayol çipleri (1-4) | `index.html:5837` | Cevap seçeneklerinde klavye kısayolu ipucu görünür |
| 5 ekran boyutunda görsel test | `test_cockpit_browser.js` (1440×900 → 380×260) | Responsive davranış testle korunuyor |
| Tema geçişi kalıcı | `index.html:5879-5884` | `whisperStorage` üzerinden saklanıyor |

### 10.1 Okunuş Hiyerarşisi (Aşama 3 / Görev 3.1 detayı)

**Problem:** Uygulamanın varoluş sebebi "kullanıcının okunuşa bakıp yüksek sesle okuması" — ama okunuş metni cevap kartında toggle arkasında gizli (`index.html:5845-5851`, `display:none` başlangıcı) ve cockpit'te native metinle benzer görsel ağırlıkta.

**Önerilen değişiklikler:**

1. **Okunuş varsayılan olarak açık:** `hasOkunus` true ise `display:block` ile başlasın; kullanıcı isterse kapatsın (tercih `whisperStorage`'da hatırlansın). Zaman baskısı altında her cevap için ekstra tık = kaybedilen saniye.
2. **Punto hiyerarşisi:** okunuş metni native metinden ~%15-20 büyük ve `font-weight: 600`; native metin ikincil (küçültülmüş, düşük opaklık). Göz önce okunacak metne gitmeli.
3. **Satır aralığı:** okunuş için `line-height: 1.6+` (hecelemeyi kolaylaştırır).
4. **Soluk grupları:** PTT prompt'u zaten `' / '` soluk grupları üretiyor (`buyedektir.py:4699`) — bu gruplar UI'da görsel olarak ayrılsın (örn. `/` karakterine ayrı renk/aralık), tek uzun satır yerine soluk soluk okunabilir bloklar.

**Doğrulama:** `test_cockpit_browser.js` fixture'ına okunuş görünürlük assertion'ı; 5 boyutta ekran görüntüsü karşılaştırması.

### 10.2 Partial → Final Geçiş Sürekliliği (Aşama 3 / Görev 3.2 detayı)

**Problem:** Gri önizleme satırı `new_transcription` geldiğinde yerini final satıra bırakıyor; satır konumu/içeriği sıçrarsa kullanıcının okuma ritmi bozulur.

**Öneri:** Önizleme satırı final satırla **aynı DOM konumunda** dönüşsün: metin içeriği yerinde güncellensin, gri→normal renk geçişi `transition: color/opacity 200ms` ile yumuşatılsın. Satır boyu değişimi (reflow) kaçınılmazsa liste `scroll anchoring` ile kullanıcının baktığı yeri korusun (`overflow-anchor` desteği kontrol edilmeli).

**Doğrulama:** partial→final akışını simüle eden bir frontend regresyon testi (mevcut `test_*_frontend.js` kalıbında): önizleme satırının final ile aynı `data-id`'ye bağlandığını ve DOM'da tek satır kaldığını doğrula.

### 10.3 Overlay Tema Tutarlılığı (Aşama 3 / Görev 3.3 detayı)

**Problem:** `overlay.html` kendi inline stillerini taşıyor; ana pencere açık temaya geçince overlay koyu kalıyor (ya da tersi).

**Öneri:** Overlay'in renklerini `whisper-pro-theme.css`'teki CSS değişkenlerine (`var(--bg)`, `var(--text-muted)` vb.) bağla; tema değişimini overlay'e ilet (aynı `localStorage` anahtarı iki pencerede de okunabilir — `storage` event'i ile canlı senkron, ya da overlay açılışında oku).

**Doğrulama:** Ana pencerede tema değiştir → overlay aynı paleti göstersin (manuel kontrol; Electron'da iki pencere fixture'ı).

### 10.4 Erişilebilirlik Denetimi (Aşama 3 / Görev 3.4 detayı)

**Bulgular:**
- 64 inline `onclick`'e karşı 16 `addEventListener` (`index.html`) — klavye odağı ve ekran okuyucu davranışı tutarsız olabilir.
- Konuşmacı badge renkleri (`speaker-${speaker.color}`, `index.html:3905`) açık temada sarı/turuncu tonlarında kontrast riski taşıyor.

**Öneri:**
1. Açık ve koyu temada tüm metin/badge çiftlerini WCAG AA'ya (4.5:1) göre denetle; yetmeyen badge renklerine koyu metin veya koyu kenarlık ver.
2. `:focus-visible` halkalarının tema CSS'inde tanımlı olduğunu doğrula; yoksa ekle (klavyeyle Tab gezintisinde odak görünmeli).
3. 1-4 kısayollarının okuma modu açıkken de çalıştığını doğrula; okuma modunda Escape ile kapanma zaten var mı kontrol et.
4. Yeni etkileşimlerde inline `onclick` yerine `addEventListener` tercih et (mevcutları zorla göçürmeye gerek yok).

**Doğrulama:** Kontrast ölçümü (devtools/Lighthouse) + Tab ile tam tur klavye gezintisi.

### 10.5 İlk Açılış / Boş Durum Zenginleştirme (yeni tasarım önerisi)

**Problem:** "Henüz kayıt yok" ekranı (`index.html:4048`) pasif; ilk açılışta kullanıcı neyin eksik olduğunu (model? cihaz? API anahtarı?) kendi başına bulmak zorunda.

**Öneri:** Boş durum ekranını **kurulum kontrol listesine** dönüştür:
- ✅/⚠️ Model yüklü mü (değilse "Model seç ve indir" bağlantısı)
- ✅/⚠️ Ses cihazı seçili mi
- ✅/⚠️ OpenAI anahtarı geçerli mi (Görev 1.3'teki kalıcı uyarı rozetinin boş-durum karşılığı)
- Son adım: "Başlat" butonu

**Doğrulama:** `test_cockpit_browser.js` fixture'ına boş-durum varyantı.

### 10.6 Gecikme Sağlığı Göstergesi — görsel detay (Aşama 2 / Görev 2.2'nin tasarım yüzü)

Header'da küçük, sözsüz bir rozet: 🟢 <1 sn / 🟡 1-3 sn / 🔴 >3 sn (ASR p95 + çeviri p95'in kötüsü). Tıklayınca `/api/stats` detaylarını gösteren mini popover. Renk körü dostu: renge ek olarak metin ("hızlı/yavaş") veya ikon şekli değişsin.

### 10.7 Küçük Tutarlılık Notları

| # | Gözlem | Öneri |
|---|---|---|
| a | `index.html` içinde inline `style="..."` kullanımı yaygın (örn. `index.html:4230`, `4760`) | Yeni işlerde tema değişkenli class'lar; mevcutları toplu göç ettirmeye gerek yok |
| b | `overlay.html` ayrı bir escapeHtml implementasyonu taşıyor (`overlay.html:256-260`, DOM-tabanlı) | Davranış `index.html:5344` ile aynı; tek ortak `static/` modülüne taşınabilir (Görev 4.2 kapsamında) |
| c | Boş durum SVG'leri iki yerde tekrar (`index.html:4048` ve `4092`) | Tek partial/fonksiyona indir |
| d | Alert sistemi (`index.html:5970`) artık eski alert'leri silmiyor (yorum satırında belirtilmiş) | Uzun oturumlarda alert birikimine üst sınır (örn. son 5) konulmalı |

---

## §9 İkinci Geçiş (GLM) Bulguları — 2026-09-11

> İlk rapordan sonra bağımsız ikinci inceleme geçişi. Bu turda ilk geçişte derinlemesine
> bakılmayan dosyalar incelendi: `transkribe.py`, `overlay.html`, `static/runtime-safety.js`,
> `build.js`, `launcher_whisper.py`, `_gen_phrases.py`, `.bat` dosyaları, `main.js` tamamı,
> `buyedektir.py`'nin capture/PTT/diarization/çeviri-worker/MicRecorder bölümleri,
> git çalışma ağacı durumu ve depo kökü.

### 9.1 Yeni Bug / Güvenlik Bulguları

| # | Önem | Bulgu | Konum | Öneri |
|---|---|---|---|---|
| B1 | **Kritik (yerel)** | `1 saat.txt` dosyasında **açık metin OpenAI API anahtarı** (`sk-proj-...`) duruyor. `.gitignore` kapsıyor (commit'lenmez) ama klasör yedeklendiğinde/paylaşıldığında sızar; ayrıca hangi anahtarın geçerli olduğu belirsizleşiyor (`.env`'deki anahtar canlı testte 401 verdi). | `D:\Whisper Live\1 saat.txt` | Dosyayı silin veya anahtarı `.env`'e taşıyın; iki anahtarın da rotasyonunu düşünün. build.js beyaz listesi pakete almayı zaten önlüyor — sorun yalnızca yerel hijyen. |
| B2 | Orta | `speaker_profiles.json` içinde **açık metin HuggingFace token'ı** saklanıyor (tasarım gereği — diarization kalıcılığı). Gitignore kapsıyor; yerel risk B1 ile aynı kategori. | `speaker_profiles.json` | Kabul edilebilir tasarım; dokümantasyonda (AGENTS.md) açıkça belirtilmesi yeterli. |
| B3 | Orta | `archive/__pycache__yedek/` altındaki dosyalar **git'te izleniyor ve working tree'de değiştirilmiş durumda** (`git status`: M). Dizin adı `__pycache__` ile karışıyor ama gitignore kuralı (`__pycache__/`) birebir eşleşmediği için kapsamıyor. | `archive/__pycache__yedek/` | `git rm -r --cached archive/__pycache__yedek` + `.gitignore`'a `archive/__pycache__yedek/` ekle; commitlenmemiş değişiklikleri netleştirip temiz bir ağaca kavuşun. |
| B4 | Düşük | Kökte 0-byte çöp dosyalar: `npm`, `npm run`, `whisper-pro@1.0.0` (yanlış kabuk yönlendirmesi sonucu oluşmuş; gitignore'da belgelenmiş). | depo kökü | Yerelden silinebilir; gitignore kaydı kalabilir. |
| B5 | Düşük | `.claude/worktrees/` altında **iki eski AI worktree'sü** duruyor (toplam ~5 MB; her biri uygulamanın eski bir kopyası + kendi `transcriptions.txt`/`buyedektir.log'ları). İçlerinde `.env` veya anahtar **yok** (doğrulandı) — sadece yer/hijyen meselesi. | `.claude/worktrees/` | `git worktree list` → kullanılmayanlar `git worktree remove`; tamamen eskiyse klasör silinebilir. |
| B6 | Düşük | `remove_overlap()` (`transkribe.py`): (a) `all(new_lower_words[:n])` — noktalaması silinince boş string'e düşen token, örtüşme tespitini o tur için sessizce devre dışı bırakır; (b) `range(max_overlap, 1, -1)` döngüsü 1 kelimelik örtüşmeyi hiç test etmez. | `transkribe.py:51-73` | (a) boş tokenlar önceden filtrelenmeli; (b) 1-kelime örtüşme bilinçli tercihsise koda not düşülmeli. |
| B7 | Düşük | `find_models()` (`transkribe.py`): aynı modelin birden fazla snapshot'ı varsa `os.listdir` sırasına (deterministik olmayan) göre ilkini seçer. | `transkribe.py:15-32` | Snapshot'lar tarih/sürüm sırasına göre sıralanıp en yenisi seçilmeli. |
| B8 | Düşük (UX) | `transkribe.py`: uzun transkripsiyon iptal butonu yok; çıktı dosyaları mevcut `.srt`/`.txt`'nin **üzerine soru sormadan** yazar. | `transkribe.py` `_run`/dosya yazma | "İptal" bayrağı (segment döngüsünde kontrol) + üzerine yazmadan önce onay veya otomatik yedek (`.srt.bak`). |

### 9.2 İkinci Geçişte Doğrulanan "Sorun Değil" Noktaları

Bu turda şüphelenilen ama **sorun çıkmadığı doğrulanan** noktalar (gelecek taramalarda
yeniden incelenmesin diye kayda geçiyor):

- **Dosya adları diskte düzgün**: `başlat.bat`, `BAŞLAT.md` vb. adlar mojibake değil (ilk
  listelemedeki bozuk görünüm yalnızca PowerShell konsol kodlamasından). İçerikler UTF-8.
- **`main.js` kısayol temizliği**: `will-quit` → `globalShortcut.unregisterAll()` +
  `killChildPython()` mevcut; kısayol/yetim süreç sızıntısı yok (`main.js:836-839`).
- **`transcriptions.txt` / `buyedektir.log` git geçmişinde yok** (`git log --follow` = 0
  commit). Worktree'lerdeki kopyalar app'in oradan çalıştırılmasından kalma runtime çıktısı.
- **Worktree'lerde `.env`/anahtar yok** — git worktree yalnızca izlenen dosyaları çıkarır.
- **`build.js` paketleme güvenliği katmanlı**: beyaz liste + paket-sonrası sızıntı taraması
  (dosya adı + içerik regex + placeholder filtresi) + `PYTHON-GEREKSINIMI.txt` notu. Model.
- **`_enqueue_audio`** (drop-oldest + `transcription_lagging` throttle), **`_translate_async`**
  (submit anı + dönüş anı çifte lag kontrolü), **`_finish_diarization`** (geciken sonuç için
  generation guard), **`MicRecorder.stop()`** (thread-join timeout + stream sahipliği) —
  hepsi doğru kurgulanmış.
- **`transkribe.py` UI/thread ayrımı**: worker thread Tk widget'ına dokunmuyor; kuyruk +
  `after(50)` tüketicisi örnek alınacak düzeyde.
- **`runtime-safety.js`** (localStorage kotası düşerse bellek-içi fallback) ve
  **`preload.js`** (yalnız `isDev`/`platform` expose) küçük ve doğru.

### 9.3 İkinci Geçiş Geliştirme Önerileri

| # | Tür | Öneri |
|---|---|---|
| G1 | Geliştirme | `transkribe.py`'ya **iptal butonu** (B8 ile birlikte): segment üreteci tüketilirken bayrak kontrolü; UI'da `_running` iken Başlat→İptal'e dönüşsün. |
| G2 | Geliştirme | `build.js` sızıntı taraması yalnız paket içine bakar; **kaynak depoya da aynı taramayı** (`npm run scan` hedefi) ekleyin — B1'deki gibi bir dosya pakete girmese bile yerelde yakalanır. |
| G3 | Ekleme | `transkribe.py` çoklu çıktı hedefi: SRT/TXT yanına panoya kopyala / açılır klasörde göster. |
| G4 | Mimari | `archive/` altındaki eski dosyalar (eski sağlayıcı kodları, `__pycache__yedek`) için tek seferlik arşiv temizliği; `archive/` zaten geliştirme dışı — git'ten çıkarıp zip'e almak depoyu hafifletir. |
| G5 | Dokümantasyon | AGENTS.md "Configuration & gotchas" bölümüne: "depoda asla düz metin anahtar taşımayın (örn. `1 saat.txt` vakası); anahtarlar yalnız `.env`" notu eklenebilir. |

### 9.4 Özet Matris Güncellemesi

| # | Görev | Tür | Önem | Aşama | Durum |
|---|---|---|---|---|---|
| 5.1 | `1 saat.txt` anahtar temizliği + rotasyon (B1) | Güvenlik | **Yüksek** | 1 (acil) | ☐ |
| 5.2 | `archive/__pycache__yedek` git'ten çıkarma (B3) | Bakım | Orta | 4 | ☐ |
| 5.3 | Eski `.claude/worktrees` temizliği (B5) | Bakım | Düşük | 4 | ☐ |
| 5.4 | Kök çöp dosya temizliği (B4) | Bakım | Düşük | 4 | ☐ |
| 5.5 | `remove_overlap` sağlamlaştırma (B6) | Düzeltme | Düşük | 4 | ☐ |
| 5.6 | `find_models` snapshot sıralaması (B7) | Düzeltme | Düşük | 4 | ☐ |
| 5.7 | transkribe.py iptal + üzerine yazma onayı (B8/G1) | Ekleme/UX | Düşük | 4 | ☐ |
| 5.8 | Kaynak depo sızıntı taraması (G2) | Geliştirme | Orta | 2 | ☐ |
| 10.5 | Boş durum → kurulum kontrol listesi (§10.5) | Tasarım | Orta | 3 | ☐ |
| 10.7 | Küçük tutarlılık düzeltmeleri a-d (§10.7) | Tasarım | Düşük | 3 | ☐ |

> Not: 5.1 ("1 saat.txt") ilk geçişin 1. aşamasına eklenmelidir — tek satırlık dosya
> silme işlemi, ama etkisi en yüksek olan madde.

*Rapor sonu. İkinci geçiş de kod değiştirmeden, yalnızca okuyarak ve test çalıştırarak
hazırlanmıştır.*
