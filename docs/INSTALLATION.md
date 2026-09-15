# Installation

## Prerequisites

Install Git, Node.js/npm, and a compatible 64-bit Python on Windows. Python 3.12 is a reasonable starting point, not a strict lock. Native packages such as Torch, torchaudio, PyAudioWPatch, and pyannote must support the selected Python version.

## Install

```powershell
git clone https://github.com/dorukakindev/whisper-live.git
Set-Location whisper-live
npm ci --no-audit --no-fund
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install pyflakes
Copy-Item .env.example .env
notepad .env
```

If Python 3.12 is unavailable, use another compatible interpreter. Recreate the virtual environment after moving to a new Windows installation; do not copy an old `.venv`.

Add only credentials for features you use. Never paste credentials into Git commands, remote URLs, documentation, issues, logs, or screenshots. Leave `HOST=127.0.0.1`.

## Validate native imports

```powershell
.venv\Scripts\python.exe -c "import torch; print(torch.__version__)"
.venv\Scripts\python.exe -c "import faster_whisper; print('faster-whisper import OK')"
```

For DLL failures, confirm that Python and native packages are 64-bit and compatible. Use official package sources, never third-party DLL download sites. For NVIDIA acceleration, follow the official PyTorch selector and rerun validation.

## Start

Run npm start for the full desktop application and the project Python executable for backend-only work.

Speaker diarization is optional and lazy-loaded. It requires an appropriate Hugging Face token and acceptance of model-specific access terms.

## Update

```powershell
git pull --ff-only
npm ci --no-audit --no-fund
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Preserve `.env` and local data. Restart after Python/template changes. Rebuild `dist` if using a packaged copy.
