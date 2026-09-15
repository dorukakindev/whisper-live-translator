# Security policy

## Supported versions

Security fixes are applied to the latest revision on the default branch. Older commits and locally built binaries are not maintained as separate supported releases.

## Reporting a vulnerability

Use GitHub's **Security** tab to submit a private vulnerability report. If private reporting is unavailable, contact the repository owner through their GitHub profile and ask for a private reporting channel.

Never put API keys, access tokens, private audio, transcripts, speaker profiles, or personal data in a public issue. Include the affected commit, component, synthetic reproduction, impact, and required preconditions when possible. An acknowledgement is expected within seven days; disclosure timing will be coordinated after the issue is understood.

## Security boundaries

- The backend binds to `127.0.0.1` by default. Do not expose it directly to a LAN or the internet.
- The local app token is not a remote-access authentication system.
- Credentials belong only in ignored local configuration.
- Cloud-assisted features send text to the provider chosen by the user. See [Privacy](docs/PRIVACY.md).

## Release checks

```powershell
npm run scan
npm run audit:history
```

If history scanning reports a credential candidate, revoke it first. Removing it from the latest revision is insufficient because old Git objects remain accessible. History rewriting and force-pushing are destructive coordination steps and require an explicit plan.
