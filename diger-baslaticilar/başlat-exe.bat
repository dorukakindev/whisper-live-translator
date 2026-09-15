@echo off
REM Whisper Pro - Portable Executable Başlatıcı
REM Bu dosya dist klasöründeki hazır .exe dosyasını çalıştırır

cd /d "%~dp0.."

echo.
echo ========================================
echo  Whisper Pro (Portable) Başlatılıyor...
echo ========================================
echo.

REM Portable exe'yi çalıştır
if exist "dist\Whisper-Pro-win32-x64\Whisper-Pro.exe" (
    start "" "dist\Whisper-Pro-win32-x64\Whisper-Pro.exe"
    echo Whisper Pro icin baslatma istegi gonderildi.
    echo.
) else (
    echo.
    echo HATA: Whisper-Pro.exe bulunamadı!
    echo Lütfen önce şu komutu çalıştırın:
    echo   npm run build
    echo.
    pause
)
