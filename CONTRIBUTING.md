# Contributing to Whisper Pro

Thank you for helping improve Whisper Pro.

## Before opening an issue

- Search existing issues and current engineering reports.
- Reproduce on the latest default branch when possible.
- Remove credentials, personal paths, private audio, transcripts, and speaker data.
- State whether evidence came from simulation, a unit-level test, or real hardware/provider use.

## Development setup

Follow [Installation](docs/INSTALLATION.md), then use `npm start` for the full app or `.venv\Scripts\python.exe buyedektir.py` for the backend.

The codebase and existing comments are primarily Turkish. Match surrounding code when editing. Public-facing documentation should be English.

## Guidelines

- Keep changes focused and preserve behavior outside their scope.
- Never commit `.env`, credentials, transcripts, speaker profiles, model caches, virtual environments, `node_modules`, or `dist`.
- Escape user/model data before inserting it into HTML or JavaScript.
- Keep the backend on localhost unless a complete remote-security design is implemented.
- Add meaningful regression coverage for bug fixes.
- Do not claim real audio, GPU, provider, or packaged-app validation unless performed.
- Preserve LF line endings in `buyedektir.py`.

## Validation

```powershell
.venv\Scripts\python.exe -m py_compile buyedektir.py
.venv\Scripts\python.exe -m pyflakes buyedektir.py
.venv\Scripts\python.exe test_translation_worker.py
.venv\Scripts\python.exe test_live_audio.py
.venv\Scripts\python.exe test_smoke.py
npm run scan
npm run audit:history
git diff --check
```

Run relevant `test_*.js` files for frontend changes. `test_cevap_onerisi.py` can make a paid API call and is not part of the default offline suite.

Pull requests should describe the problem and root cause, solution and trade-offs, changed files, exact test results, unrun checks, configuration/dependency changes, and known limitations. Use synthetic or anonymized test data.
