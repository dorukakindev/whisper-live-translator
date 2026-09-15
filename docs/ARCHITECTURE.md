# Architecture

Whisper Pro is an Electron desktop application with a local Flask and Flask-SocketIO backend. The browser UI and backend communicate over localhost.

## Process model

```text
Electron main process
  |
  +-- launches and supervises the Python backend
  |
  +-- loads the local web UI
          |
          +-- HTTP settings and action endpoints
          +-- Socket.IO live transcription and AI events

Python backend
  |
  +-- audio capture
  +-- voice activity detection
  +-- faster-whisper transcription
  +-- optional translation workers
  +-- optional speaker diarization
  +-- AI reply generation
```

The Electron entry point is `main.js`. The principal backend is `buyedektir.py`. The main UI is `templates/index.html` with scripts and styles under `static/`.

## Live audio pipeline

1. The capture worker reads microphone or Windows system-loopback audio.
2. Audio is downmixed, resampled to 16 kHz, and segmented with WebRTC VAD.
3. Complete utterances enter a bounded queue; old work can be dropped under sustained load to keep the live view current.
4. faster-whisper produces the final transcript.
5. Optional translation and diarization run on separate workers so they do not intentionally block transcription.
6. Socket.IO events update the conversation UI.

Live partial transcription uses snapshots from the active utterance. Partial results are previews only: they do not enter transcript history, files, translation, or AI response generation. A final transcript replaces the preview.

A monotonic session identifier prevents workers from an earlier start/stop cycle from leaking results into a newer session. Whisper model access is serialized because partial, final, microphone, and warm-up operations share one model instance.

## AI reply flow

The reply endpoint creates multiple styles in parallel. Partial Socket.IO events can show completed options before the final HTTP response returns. Results are merged, parsed, salvaged when possible, and deduplicated.

The primary use case is read-aloud communication: each suggestion can contain native text, Turkish meaning, and a Turkish-readable pronunciation. Language-specific pronunciation rules are applied only for the selected target language.

## Local state

Potentially sensitive runtime state is intentionally excluded from Git:

- `.env` for provider credentials;
- `transcriptions.txt` and rotated transcript files;
- `speaker_profiles.json`;
- Electron/browser local settings, favorites, and glossary entries;
- model caches, virtual environments, dependencies, logs, and packaged output.

See [Privacy](PRIVACY.md) for data-flow details.

## Packaging

`npm run build` uses `build.js` and an explicit allowlist to create an Electron package. It also scans for suspicious filenames and credential patterns. The packaged Electron source still expects a compatible Python runtime and dependencies; it is not a fully self-contained Python distribution.

## Standalone utility

`transkribe.py` is a separate Tkinter application for transcribing media files. It does not share the live application's UI or runtime pipeline.

## Trust boundaries

The backend is designed for localhost. Cloud providers receive text only when their features are enabled. Provider responses, transcript text, and all user-controlled strings must be treated as untrusted before insertion into HTML or JavaScript.

For implementation details and current limitations, inspect the source and latest engineering handoff notes rather than assuming this overview is exhaustive.
