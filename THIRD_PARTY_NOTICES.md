# Third-party notices

Whisper Pro depends on open-source packages and optional downloaded models. Each retains its own license, notices, access conditions, and terms. The project MIT License does not replace them.

Important direct components include Electron, electron-store, electron-packager, electron-builder, Flask, Flask-SocketIO, faster-whisper, PyAudioWPatch, webrtcvad-wheels, pyannote.audio, PyTorch, torchaudio, NumPy, SciPy, the OpenAI Python SDK, Requests, and python-dotenv.

Authoritative dependency metadata is available through `package-lock.json`, installed Python package metadata, and upstream projects including:

- https://github.com/SYSTRAN/faster-whisper
- https://github.com/s0d3s/PyAudioWPatch
- https://github.com/daanzu/py-webrtcvad-wheels
- https://github.com/pyannote/pyannote-audio
- https://github.com/pytorch/pytorch
- https://github.com/electron/electron
- https://github.com/openai/openai-python

This file is informational, not a complete software bill of materials or legal opinion. Before distributing a binary, generate notices from the exact installed/locked dependency set because transitive packages and bundled native libraries change.

Downloaded speech and diarization models are separate artifacts. Review the model card, license, access restrictions, and acceptable-use terms for the exact revision used. API services such as OpenAI and DeepL are governed by their own terms and privacy policies.
