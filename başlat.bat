@echo off
REM Whisper Pro - Başlatma Dosyası
REM Bu dosya Whisper Pro uygulamasını başlatır

cd /d "%~dp0"

echo.
echo ========================================
echo  Whisper Pro Başlatılıyor...
echo ========================================
echo.

REM npm start komutunu çalıştır
call npm.cmd start

if errorlevel 1 (
    echo.
    echo HATA: npm start başarısız oldu.
    echo Lütfen aşağıdakileri kontrol edin:
    echo 1. Node.js ve npm kurulu mu?
    echo 2. package.json dosyası mevcut mu?
    echo.
    pause
)
