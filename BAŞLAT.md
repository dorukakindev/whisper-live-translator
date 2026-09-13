# 🚀 Whisper Pro - Başlatma Rehberi

Bu klasörde 3 adet başlatma dosyası vardır. Hangi durumda hangiyi kullanacağını öğren:

---

## 📋 Başlatma Dosyaları

### 1. **başlat.bat** ⭐ (En Sık Kullanılan)
```
çalıştır → npm start → Electron uygulaması açılır
```

**Kullanım:**
- Geliştirme sırasında
- Kod değişiklikleri yapıyorsan
- `npm start` komutu çalıştırmak istemiyorsan

**Nasıl:**
- `başlat.bat` dosyasına double-click
- Flask backend + Electron UI açılıyor
- Tray icon görünüyor
- Kod değişiklikleri test edebilirsin

---

### 2. **başlat-exe.bat** (Portable Version)
```
çalıştır → dist klasöründe .exe ara → Electron uygulaması açılır
```

**Kullanım:**
- `npm run build` yaptıktan sonra
- Portable .exe'yi çalıştırmak istiyorsan
- İnşaat (build) sürecini atlamak istiyorsan

**Nasıl:**
- `başlat-exe.bat` dosyasına double-click
- dist klasöründe Whisper-Pro.exe aranır
- Bulunursa doğrudan çalıştırılır

---

### 3. **başlat-release.bat** (Taşınabilir)
```
çalıştır → Bulunduğu yerdeki Whisper-Pro.exe açılır
```

**Kullanım:**
- dist klasöründe kopyalandığında
- Folder'ı başka yere taşıyıp çalıştırmak istiyorsan
- USB stick'te çalıştırmak istiyorsan

**Nasıl:**
- `başlat-release.bat` dosyasını dist/Whisper-Pro-win32-x64 klasörüne kopyala
- Oradan çalıştır
- Folder'ın tamamını Windows'un başka yerine taşıyabilirsin

---

## 🔄 Workflow

### Geliştirme Mode (Development)
```
başlat.bat → npm start → Electron + Flask → Kod değiştir
```

### Release Mode (Production)
```
npm run build → başlat-exe.bat → Portable app çalışıyor
```

### Taşınabilir App (USB/Disk)
```
dist/Whisper-Pro-win32-x64/ → başlat-release.bat → Folder'ı taşı → Çalıştır
```

---

## 🛠️ Troubleshooting

### ❌ "npm is not recognized"
- Node.js kurulu değil
- Çözüm: https://nodejs.org/ indir ve kur

### ❌ "Python is not recognized"
- Python kurulu değil
- Çözüm: https://python.org/ indir ve kur

### ❌ "Whisper-Pro.exe bulunamadı"
- Build yapılmamış
- Çözüm: `npm run build` komutunu çalıştır

### ❌ Flask server çalışmıyor
- Port 5000 kullanımda
- Çözüm: `netstat -ano | find "5000"` ile kontrol et, değiştir

---

## 💡 İpuçları

- **Hızlı Başlat:** `başlat.bat` → En kolay yol
- **Taşınabilir:** `dist/Whisper-Pro-win32-x64/` → Tüm dosyasını taşı
- **Desktop Shortcut:** `başlat.bat` kısayolunu oluştur
- **Auto-Start:** Windows Startup klasörüne .bat kopyası koy

---

## 📦 Dosya Yapısı

```
Whisper Live/
├── başlat.bat              ← Geliştirme başlatıcısı
├── başlat-exe.bat          ← Portable exe başlatıcısı
├── başlat-release.bat      ← Taşınabilir version
├── main.js                 ← Electron main process
├── buyedektir.py           ← Flask backend
├── package.json
├── dist/
│   └── Whisper-Pro-win32-x64/
│       ├── Whisper-Pro.exe  ← Taşınabilir executable
│       ├── main.js
│       ├── buyedektir.py
│       └── ...
└── templates/
    └── index.html
```

---

## ✨ Sonuç

Sadece **`başlat.bat`** dosyasına double-click et ve Whisper Pro açılsın! 🎉
