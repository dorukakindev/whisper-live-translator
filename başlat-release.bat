@echo off
REM Whisper Pro - Release Executable
REM dist klasöründen doğrudan portable app'i çalıştırır
REM Bu dosyayı dist/Whisper-Pro-win32-x64 klasörüne taşıdığında da çalışır

setlocal enabledelayedexpansion

REM Şu anki dosyanın bulunduğu dizini bul
set CURRENT_DIR=%~dp0

REM dist klasöründe mi, yoksa app klasöründe mi çalıştırılıyor kontrolü
if exist "%CURRENT_DIR%Whisper-Pro.exe" (
    REM dist\Whisper-Pro-win32-x64 içinde
    echo Whisper Pro başlatılıyor...
    start "" "%CURRENT_DIR%Whisper-Pro.exe"
) else if exist "%CURRENT_DIR%dist\Whisper-Pro-win32-x64\Whisper-Pro.exe" (
    REM Proje root'unda
    echo Whisper Pro başlatılıyor...
    start "" "%CURRENT_DIR%dist\Whisper-Pro-win32-x64\Whisper-Pro.exe"
) else (
    echo HATA: Whisper-Pro.exe bulunamadı!
    echo.
    echo Lütfen şu komutu çalıştırın:
    echo   npm run build
    echo.
    pause
    exit /b 1
)

exit /b 0
