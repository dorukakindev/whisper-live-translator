# Privacy and data flow

Use Whisper Pro only when you have the legal right and participants' consent to capture or process audio.

## Local processing

Microphone or Windows system audio is captured locally. faster-whisper performs speech recognition locally; voice activity detection and most transcript processing also run on the computer. Logs, transcripts, and speaker profiles may be stored locally.

Git ignores `.env`, `transcriptions.txt`, rotated transcripts, logs, and `speaker_profiles.json`. Ignoring a file does not encrypt or delete it.

## Optional cloud processing

When enabled, transcript text may be sent to OpenAI for replies or translation, DeepL for translation, or an explicitly selected compatible provider. Provider retention, regional processing, and account terms are controlled by current provider policies and user configuration.

Hugging Face credentials are used to obtain optional diarization model artifacts. Diarization inference is intended to run locally after model loading, subject to installed third-party behavior.

## Credentials and retention

- Store secrets only in ignored local configuration.
- Never send `.env`, logs, transcripts, or speaker profiles with bug reports.
- If a credential is committed, revoke it immediately; later deletion does not remove Git history.
- Run `npm run scan` and `npm run audit:history` before publishing a fork.

`transcriptions.txt`, `speaker_profiles.json`, and Electron/browser local storage can contain sensitive conversation data, profiles, preferences, favorites, and glossary terms. Back up or delete them according to your own policy, with Whisper Pro closed.

The backend defaults to `127.0.0.1`. Do not bind it to a LAN/public interface without a separately reviewed authentication, authorization, transport-security, and cross-origin design.

Transcription, translation, attribution, and AI replies can be inaccurate. Do not use them as the sole basis for medical, legal, financial, safety-critical, employment, or identity decisions.
