# Yeni Codex oturumu ve format sonrası başlangıç

Bu dosya konuşma geçmişi olmadan çalışmaya devam etmek içindir. Önce [AGENTS.md](AGENTS.md), sonra [güncel devir notu](DEVIR-NOTU.md) okunmalıdır. Repo: [dorukakindev/whisper-live](https://github.com/dorukakindev/whisper-live). Son doğrulanan dal `main`; yeni oturum gerçek dalı ve uzak adresi yeniden kontrol etmelidir.

## Kullanıcının çalışma tercihleri

- Ana değerlendirme için GPT-6 Astra kullan; yeterli olan sınırları belli kodlama işlerinde maliyeti azaltmak için GPT-5.6 Sol tercih edilebilir. Bu tercih uygulamanın çeviri modelini değiştirmez.

- GitHub bağlantısı gerektiren işlemlerden önce Proxifier açıksa kapat. Kullanıcının son talebi: Proxifier’ı tekrar açma; fetch/push ve uzak HEAD doğrulaması sonrasında da kapalı bırak. Bu tercih sonraki oturumlarda geçerlidir ve eski devir notlarındaki yeniden açma talimatının yerini alır.

- Kullanıcı hata bulup düzeltmeni, tasarım ve transkripsiyon/çeviri deneyimini geliştirmeni istiyor. Makul ve geri alınabilir uygulama kararlarında ilerle; yalnız öneri listesi bırakma.
- Gereken araç, paket ve modelleri çalışmak için indirebilir ve kurabilirsin. Önce mevcut kurulumu kontrol et; gereksiz yeniden kurulum yapma. Python için proje `.venv` ortamını, Node için kilit dosyasını kullan. Resmi dağıtım kaynaklarını kullan; sürüm ve Windows/GPU uyumluluğunu kurulum anındaki resmi belgelerden doğrula.
- Bu izin ücretli satın alma veya hizmet aboneliği, bilgisayarı formatlama, kişisel verileri silme ya da güvenlik ayarlarını gelişigüzel kapatma izni değildir. Hesap girişini gerektiren adımda kullanıcıdan giriş yapmasını iste; şifre/token isteme, çıktılara dökme.
- Türkçe iletişim kur, Türkçe kod yorumlarıyla mevcut üslubu koru. Okunuşlar Türkçe bilen kişinin yabancı dilde rahatça sesli cevap verebilmesi içindir.
- Her düzeltme grubu sonunda test, tarihli devir, commit ve push tamamlanmalıdır. Başarısız test ve yarım işleri açıkça yaz; hiçbir zaman kanıtsız başarı iddia etme.

## Format öncesi korunacaklar

GitHub yalnız takip edilen ve push edilmiş dosyaları geri getirir. `.gitignore` kapsamındaki `.env`, konuşma geçmişi, konuşmacı profilleri, tarayıcı/Electron yerel ayarları ve favoriler GitHub'dan geri gelmez. İsteniyorsa bunların kullanıcı tarafından güvenli özel yedeği alınmalıdır; GitHub'a eklenmemelidir. `.venv`, `node_modules`, `dist` ve indirilen modeller yeniden üretilebilir; eski sanal ortamı yeni Windows'a taşımak yerine yeniden oluştur.

Bu rehberin yazılması özel yedek alındığı anlamına gelmez. Formatı Codex otomatik başlatmamalıdır.

## Temiz Windows üzerinde kurulum

1. Git, Node.js/npm ve uyumlu 64 bit Python kurulumunu kontrol et. Önceki ortam Python 3.12 kullanıyordu; bu bir sürüm kilidi değildir. Depodaki bağımlılıklarla uyumluluğu doğrula. Paket kurulumu için gerekirse resmi Windows native runtime bileşenlerini kur; rastgele DLL sitelerinden dosya indirme.
2. GitHub hesabıyla erişimi sağla. HTTPS kimlik doğrulamasında Git Credential Manager veya GitHub CLI kullanılabilir; tokenı remote URL'ye veya komuta yapıştırma.
3. Uygun bir çalışma klasöründe klonla, ardından Codex'te bu klasörü proje olarak aç:

```powershell
git clone https://github.com/dorukakindev/whisper-live.git
Set-Location whisper-live
git status --short
git branch --show-current
git rev-parse HEAD
git remote -v
```

4. Node bağımlılıklarını kilit dosyasından, Python bağımlılıklarını ayrı ortamda kur:

```powershell
npm ci --no-audit --no-fund
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install pyflakes
```

`py -3.12` yoksa kurulu uyumlu Python'un gerçek yoluyla venv oluştur. Yukarıdaki tam temiz kurulum bu belge çalışmasında denenmedi. `requirements.txt` çoğu paketi alt sınırla belirtir; gelecekte aynı paket sürümleri kurulmayabilir. Torch, torchaudio, pyannote ve GPU/CUDA uyumluluğunu ayrı doğrula; requirements yorumlarını makinenin sürücüsü için garanti sayma. GPU olmadan CPU çalışmasını önce doğrulamak yararlıdır.

5. `.env` yoksa `.env.example` dosyasından yerelde oluştur; mevcut `.env` üzerine yazma. Örnek anahtarları gerçek sır sanma. Kullanıcı gerçek anahtarları yalnız yerel `.env` içine girmelidir; Codex bunları devir notuna veya loga kopyalamamalıdır. Reseller örnek adresini yalnız gerçekten kullanılan sağlayıcı için yapılandır. Anahtarsız AI özelliklerinin çalışmaması beklenir. `HF_TOKEN` konuşmacı tanıma için opsiyoneldir.
6. Native importları kontrol et:

```powershell
.venv/Scripts/python.exe -c "import torch; print(torch.__version__)"
.venv/Scripts/python.exe -c "import faster_whisper; print('faster-whisper import başarılı')"
```

Önceki makinede Torch `c10.dll` / WinError 1114 çözülememişti; CPU paketine geçiş de sorunu çözmedi. Yeni makinede aynı sorun varmış veya çözülmüş gibi davranma. Minimal import, Python mimarisi, paket sürümleri ve resmi runtime gereksinimleriyle teşhis et.

7. `npm start` tam uygulamayı başlatır. Backend'i tek başına denemek için `.venv/Scripts/python.exe buyedektir.py` kullan. Model ilk kullanımda indirilebilir; indirme tamamlanmadan hata/başarı kararı verme. Sistem sesi/mikrofon aygıtını gerçek makineden seç; eski aygıt numaralarını kullanma. Windows dil seslerinin bulunması TTS için ayrıca gerekir.

## Her düzeltmeden sonra çalışma ve GitHub sırası

1. Başlangıç HEAD kimliğini kaydet. `git fetch origin` ile uzak durumu öğren. Yeni dal gerekiyorsa `codex/` öneki kullan; mevcut dalı neden olmadan değiştirme. Başka çalışmaların üzerine yazma, force push veya yıkıcı reset yapma.
2. Kök nedeni belirle, küçük ve ilgili değişikliği yap. Hata için anlamlı regresyon testi ekle; yalnız uygulama ayrıntısını tekrar eden testler üretme.
3. Değişikliğe uygun kontrolleri çalıştır:

```powershell
.venv/Scripts/python.exe -m py_compile buyedektir.py
.venv/Scripts/python.exe -m pyflakes buyedektir.py
.venv/Scripts/python.exe test_translation_worker.py
.venv/Scripts/python.exe test_live_audio.py
.venv/Scripts/python.exe test_smoke.py
npm run scan
git diff --check
```

Ön yüz değiştiyse inline JavaScript'i çıkarıp Jinja yer tutucularını test değeriyle değiştirerek `node --check` çalıştır; ilgili `test*.js` dosyalarını ve `node_modules/.bin/electron.cmd test_cockpit_browser.js` testini çalıştır. Gerçek HTTP kontrolünde ayrı boş bir port kullan; kök sayfa ve `/api/settings` yanıtını doğrula. Gerçek mikrofon/sağlayıcı testi yapılmadıysa simülasyonu uçtan uca başarı olarak gösterme. HTML/backend değişiminde backend'i yeniden başlat.

4. Diff ve gizli bilgi taramasını incele. Yalnız ilgili dosyaları açıkça `git add -- dosya...` ile sahnele. Kod commit'ini oluştur; `git rev-parse HEAD` çıktısı bitiş kod commit'idir. Kimlik eksikse global ayarı gelişigüzel değiştirme; önceki çalışmalarda komuta özel `git -c user.name=Codex -c user.email=codex@localhost commit -m 'Açıklama'` kullanıldı. Mevcut kullanıcı kimliği varsa koru.
5. `docs/devir/YYYY-MM-DD-HHMM.md` oluştur (Europe/Istanbul). Önceki notu silme. Repo/dal, başlangıç-bitiş kod commitleri, dosyalar/amaç, hatalar/kök neden/kanıt, kullanım, test komutları/sonuçları/çalıştırılmayanlar, bağımlılıklar/ayar/şema, bilinen sorunlar/sonraki adımlar ve commit/push durumunu yaz. Kökteki `DEVIR-NOTU.md` güncel bağlantısını ve arşivini güncelle.
6. Belgeleri ayrı commit et. Yalnız belge çalışması varsa kod değişmediğini ve başlangıç/bitiş kod kimliğinin aynı olduğunu belirt. Notun kendi SHA'sını içine yazmaya çalışarak sonsuz amend döngüsü oluşturma.
7. Çalışılan dalı `origin` üzerine push et. Uzakta yeni commit varsa inceleyip güvenli şekilde bütünleştir; ezme. Giriş veya yetki engeli varsa gerçek hatayı ve gönderilmemiş commitleri bildir.
8. `git ls-remote origin refs/heads/<dal>` çıktısını `git rev-parse HEAD` ile karşılaştır; `git status --short` ile kalan değişiklikleri kontrol et. Push başarılı olmadan “GitHub'a yüklendi” deme. Son yanıtta repo linki, tarihli nota doğrudan GitHub linki ve push edilen tam SHA'yı ver.

## Mevcut doğrulama sınırları

Son kod çalışmasında yeni regresyonlar ve gerçek Chromium arayüz kontrolleri geçti. Ayrı backend'de `/` ve tokenlı `/api/settings` 200 doğrulandı. Portable paket üretildi, hassas dosya taraması ve değişen dosyaların kaynak/paket eşleşmesi doğrulandı. Tam smoke 33/34 geçti; kalan konuşmacı testi Torch c10.dll WinError 1114 nedeniyle çalışmadı. Uzun gerçek görüşme, ücretli sağlayıcı, GPU/diarization ve yeni bilgisayarda portable'ın uçtan uca çalışması doğrulanmadı. Ayrıntıları [devir arşivinden](DEVIR-NOTU.md) oku.

Son paketleme sistem Node 26 ile tamamlanmadığından mevcut makinedeki bundled Node 24.19.0 kullanıldı. Yeni bilgisayarda eski bundled mutlak yolu geçerli sayma; çalışan Node kurulumunu doğrula. Python ortamı son çalışmada 3.11 idi; temiz kurulum örneğindeki 3.12 bir zorunluluk değildir. Yeni makinede uyumlu bağımlılıkları kur ve test et.

## Yeni bilgisayarda devam mesajı

Depoyu klonlayıp Codex'te proje klasörünü açtıktan sonra şu talimat yeterlidir:

> AGENTS.md, BASLANGIC.md ve DEVIR-NOTU.md içindeki güncel notu oku. Gerçek makineyi ve Git durumunu kontrol et, proje bağımlılıklarını ayrı ortamda kur, testleri çalıştır ve Whisper Pro geliştirmesine devam et. Proxifier'ı yeniden açma. Eski makinenin Torch DLL sorununu yeni makinede varsayma; yeniden doğrula.

GitHub'da kaynak kod, testler, paketleme dosyaları, gereksinimler, tasarım ve tarihli devir notları vardır. `.env`, transkriptler, konuşmacı profilleri, tarayıcı/Electron localStorage içindeki favoriler/terim sözlüğü/ayarlar, modeller, sanal ortam ve portable exe GitHub'dan geri gelmez. Yerel verileri korumak gerekiyorsa format öncesi güvenli özel yedek al; anahtarları GitHub'a koyma. Bu rehber özel yedeğin alındığı veya yeni makinede kurulumun denendiği anlamına gelmez.

`dist` kaynakla kendiliğinden güncellenmez. Portatif exe istenirse testlerden sonra `npm run build` çalıştır, üretilen paketi ayrıca dene; yalnız kaynak push ederek exe güncellendiğini söyleme.
