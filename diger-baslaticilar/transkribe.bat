@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" transkribe.py %*
) else (
    python transkribe.py %*
)
