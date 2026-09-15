# Whisper Pro

Whisper Pro is a Windows desktop assistant for live conversations across languages. It captures microphone or Windows system audio, transcribes speech locally with faster-whisper, optionally translates incoming speech, and generates reply suggestions with Turkish-friendly pronunciation guides.

![Whisper Pro live conversation and reply suggestions](docs/media/whisper-pro-conversation.png)

The live workspace keeps the full conversation readable while reply suggestions stay ready beside it. Each reply includes its native wording, Turkish meaning, and a pronunciation line designed to be read aloud.

![Whisper Pro reading mode demonstration](docs/media/whisper-pro-demo.gif)

[Watch the short MP4 demo](docs/media/whisper-pro-demo.mp4) · [View reading mode at full resolution](docs/media/whisper-pro-reading-mode.png)

> The media above is rendered from the real Electron UI with synthetic conversation data and an English presentation layer. The shipping interface is currently primarily Turkish.

> [!IMPORTANT]
> This project is under active development. Never commit API keys or private transcripts, and review the known limitations before important use.

## Highlights

- Live microphone and Windows system-audio transcription
- Optional incoming-speech translation
- AI replies with native text, Turkish meaning, and Turkish-readable pronunciation
- Live partial transcription, push-to-talk tools, quick phrases, search, and export
- Optional speaker diarization and a compact game overlay
- Local-only backend by default (`127.0.0.1`)

## Requirements

Whisper Pro currently targets 64-bit Windows. Install Git, Node.js/npm, and a compatible 64-bit Python. You also need a microphone or loopback-capable audio device and storage for Python packages and downloaded models.

An OpenAI API key is needed only for AI replies or OpenAI translation. DeepL and pyannote features use separate optional credentials. CPU transcription is supported; a compatible NVIDIA GPU can improve speed substantially.

## Quick start

```powershell
git clone https://github.com/dorukakindev/whisper-live.git
Set-Location whisper-live
npm ci --no-audit --no-fund
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
npm start
```

npm start

See [Installation](docs/INSTALLATION.md), [Usage](docs/USAGE.md), [Architecture](docs/ARCHITECTURE.md), [Troubleshooting](docs/TROUBLESHOOTING.md), and the [public release checklist](PUBLIC_RELEASE_CHECKLIST.md).

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | For AI features | Reply suggestions and OpenAI translation |
| `OPENAI_MODEL` | No | Translation model override |
| `OPENAI_RESPONSE_MODEL` | No | Reply-suggestion model override |
| `DEEPL_API_KEY` | No | Optional DeepL translation |
| `HF_TOKEN` | No | Optional pyannote speaker diarization |
| `HOST` / `PORT` | No | Local backend bind address and port |

Keep `HOST=127.0.0.1`. The app is designed as a local desktop service and is not hardened for direct LAN or internet exposure.

## Data and privacy

Audio transcription runs locally. Depending on enabled features, transcript text may be sent to OpenAI, DeepL, or a user-selected compatible provider. Local transcripts and speaker profiles are ignored by Git, but remain on the computer until removed. Read [Privacy and data flow](docs/PRIVACY.md) before processing sensitive conversations.

## Development and validation

```powershell
npm start
.venv\Scripts\python.exe -m py_compile buyedektir.py
.venv\Scripts\python.exe -m pyflakes buyedektir.py
.venv\Scripts\python.exe test_translation_worker.py
.venv\Scripts\python.exe test_live_audio.py
.venv\Scripts\python.exe test_smoke.py
npm run scan
npm run audit:history
git diff --check
```

For backend-only development, run `.venv\Scripts\python.exe buyedektir.py`. See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

## Building

Run `npm run build`. Output is written to `dist/Whisper-Pro-win32-x64/`. This packages the Electron source but does not make the project-local Python environment portable. Retest on the target machine; an old `dist` directory does not update with source changes.

## Known limitations

- Windows is the only supported desktop platform today.
- Cloud features require user-supplied credentials and may incur provider charges.
- CPU transcription can be too slow for demanding real-time use with larger models.
- Speaker diarization has not been validated on every hardware configuration.
- Transcripts, translations, speaker labels, and pronunciation guides can be wrong. Verify critical information independently.
- Historical engineering notes are maintained for development continuity; current user documentation takes precedence.

## Security

Do not open a public issue containing credentials, private audio, or transcripts. Follow [SECURITY.md](SECURITY.md). Before making a fork public, run both `npm run scan` and `npm run audit:history`.

## License

Whisper Pro is licensed under the [MIT License](LICENSE). Third-party packages and downloaded models retain their own licenses and terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
