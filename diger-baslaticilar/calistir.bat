@echo off
cd /d "%~dp0.."

REM Proje-ici sanal ortami (.venv, Python 3.11) tercih et: tum bagimliliklar
REM (webrtcvad, faster-whisper, torch...) ORADA kurulu. PATH'teki "python"
REM baska bir surume (orn. 3.14) isaret edebilir ve o surumde bu paketler
REM yoktur -> "ModuleNotFoundError: No module named 'webrtcvad'". Bu yuzden
REM once venv python'u dene, yoksa PATH'teki python'a dus.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" buyedektir.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" buyedektir.py
) else (
    echo UYARI: .venv bulunamadi, PATH'teki python kullaniliyor.
    echo Eksik modul hatasi alirsaniz: .venv\Scripts\python.exe -m pip install -r requirements.txt
    python buyedektir.py
)
pause
