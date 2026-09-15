# Public release checklist

This repository is still private. Complete every blocking item before changing its visibility.

## Current audit status (2026-09-15)

- [x] Current source tree passes `npm run scan`.
- [x] Known local runtime data, credential files, environments, models, dependencies, and packaged output are covered by .gitignore.
- [x] English README, installation, usage, privacy, security, contribution, troubleshooting, license, and third-party notices are present.
- [ ] **BLOCKER:** Full-history scanning reports credential-shaped content in old commits.
- [ ] Confirm that every reported credential has been revoked or was never valid.
- [ ] Rewrite affected Git history only after explicit owner approval and coordination.
- [ ] Run the history scan again and require a zero exit code.
- [ ] Review screenshots, examples, issue history, releases, tags, and branch names for private data.
- [ ] Enable GitHub private vulnerability reporting and secret scanning if available.
- [ ] Review exact model and dependency terms for any binary distribution.
- [ ] Test a clean installation on a separate supported Windows account or machine.
- [ ] Decide whether historical internal engineering reports should remain public.

## Known history-scan findings

The 2026-09-15 redacted scan checked 62 reachable revisions and reported nine unique path/fingerprint combinations:

- three OpenAI-compatible key candidates in an archived translator file;
- one Google API key candidate in the same archived translator file;
- one Hugging Face token candidate copied across five archived backup files.

No credential values are reproduced here. Use:

```powershell
npm run audit:history
```

The command prints only credential type, a short SHA-256 fingerprint, commit, path, and line. A clean public-release candidate must return exit code 0.

## Safe remediation order

1. Revoke or rotate every confirmed credential at its provider.
2. Preserve a private backup and notify collaborators that history will change.
3. Remove the affected blobs from every branch and tag intended for publication.
4. Force-push only as an explicitly approved, coordinated repository-owner action.
5. Expire old clones/caches where practical and ask collaborators to reclone.
6. Run `npm run scan` and `npm run audit:history` again.
7. Review GitHub settings and only then change repository visibility.

Deleting a file in a new commit does not remove it from earlier commits. Do not treat documentation completion as authorization to make the repository public.
