# Assets Klasörü

Bu klasör uygulama ikonlarını içerir.

## Dosyalar

1. **icon.ico** (multi-size: 16–256px)
   - Electron app main window icon'u (`main.js` → `BrowserWindow.icon`)
   - Windows Explorer'da görünür

2. **tray-icon.ico** (16px, 32px)
   - System tray icon'u (`main.js` → tray)

İkonlar koyu lacivert zemin üzerinde gradyan ses-dalgası çubuklarından oluşur (UI başlığındaki logo ile aynı tasarım). PNG kaynak: `docs/media/whisper-pro-logo.png`.

## Icon Yeniden Üretme

Tasarımı değiştirmek istersen `/tmp/make_icon.py` benzeri bir PIL betiğiyle çok-boyutlu `.ico` yazdır:

```python
from PIL import Image
img = Image.open("logo.png")  # en az 256x256, RGBA
img.save("icon.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
img.resize((32,32)).save("tray-icon.ico", sizes=[(16,16),(32,32)])
```
