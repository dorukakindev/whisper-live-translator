# Whisper Live'ı başlatma

Güncel kaynak sürümünü açmak için proje kökündeki **`başlat.bat`**
dosyasına çift tıkla.

```text
D:\Whisper Live\başlat.bat
```

Bu dosya Electron uygulamasını ve Python backend'ini birlikte başlatır. Kaynak
kodda yapılan son değişiklikler bu yolla kullanılır.

## İlk kurulum

`npm` bulunamadı hatası alınırsa Node.js ve proje bağımlılıklarının kurulması
gerekir. Python ortamı için proje içindeki `.venv` klasörü kullanılır.

## Hazır EXE

`dist\Whisper-Pro-win32-x64\Whisper-Pro.exe` yalnız son paketleme sırasında
oluşturulan sürümdür. Kaynak kod değişince kendiliğinden güncellenmez.

Normal kullanımda ihtiyaç duyulmayan EXE, backend ve komut satırı başlatıcıları
`diger-baslaticilar` klasöründe tutulur.
