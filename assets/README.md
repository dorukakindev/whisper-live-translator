# Assets Klasörü

Bu klasör app icons'ları içermeli.

## Gerekli Dosyalar

1. **icon.ico** (256x256px)
   - Electron app main window icon'u
   - Windows Explorer'da görünecek
   
2. **tray-icon.ico** (32x32px)
   - System tray icon'u
   - Taskbar'da görünecek

## Icon Oluşturma

### Hızlı Yol (Online)
1. https://icoconvert.com/ → PNG → ICO convert et

### Programmatik (Python)
```python
from PIL import Image

# 256x256 app icon
img = Image.new('RGB', (256, 256), color='blue')
img.save('icon.ico')

# 32x32 tray icon  
img_tray = Image.new('RGB', (32, 32), color='blue')
img_tray.save('tray-icon.ico')
```

### Design Önerileri
- Whisper logo
- Mavi/mor gradient
- Transparent background
- Yüksek contrast

## Temporary Solution

Build işlemi icon eksiklikle devam edebilir. Şu dosyaları dummy oluştur:
```bash
# Windows'da
copy nul icon.ico
copy nul tray-icon.ico
```

Daha sonra gerçek icons'ları ekle.
