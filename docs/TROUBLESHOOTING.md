# Troubleshooting

## Old frontend code still appears

Restart the Python backend or Electron app after changing `templates/index.html` or `buyedektir.py`. Rebuild `dist`; packaged files do not follow source changes.

## Node.js or Python dependencies are missing

Install Node.js from its official distribution, open a new PowerShell window, and run `npm ci --no-audit --no-fund`. For Python:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -c "import faster_whisper; print('OK')"
```

Packages installed into another global Python do not repair this `.venv`.

## Torch reports a DLL error

Verify 64-bit Python and compatible Torch/torchaudio packages. Recreate environments copied from another computer. Use official packages, never loose DLL downloads.

## No microphone or system audio appears

Check Windows microphone privacy, the selected Sound device, loopback support, and stop/start listening after changing devices. Run `.venv\Scripts\python.exe audio_diagnostics.py` for device diagnostics.

## Transcription is slow

Try a smaller model, close GPU-heavy applications, confirm whether logs report CPU or GPU inference, and verify that any NVIDIA Torch build matches the driver.

## AI reply, translation, or diarization fails

Confirm the correct provider credential, restart after `.env` changes, and check provider quota/model/network status. OpenAI, DeepL, reseller, and Hugging Face credentials are not interchangeable. Disable diarization to isolate core transcription.

## Port 5000 is busy

```powershell
$env:PORT = '5091'
.venv\Scripts\python.exe buyedektir.py
```

Keep `HOST=127.0.0.1`.

## Before asking for help

Provide commit ID, Windows/Python versions, CPU or GPU mode, exact redacted error, and validation commands. Never attach `.env`, private transcripts, profiles, or unredacted logs.
