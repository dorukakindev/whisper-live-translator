#!/usr/bin/env node

/* Scan reachable Git history without printing discovered credentials. */
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const patterns = [
  ['OpenAI-compatible API key', /\b(?:sk-|csk-|gsk_)[A-Za-z0-9_-]{20,}\b/g],
  ['Hugging Face token', /\bhf_[A-Za-z0-9_-]{20,}\b/g],
  ['GitHub token', /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g],
  ['Google API key', /\bAIza[A-Za-z0-9_-]{25,}\b/g],
  ['AWS access key', /\bAKIA[0-9A-Z]{16}\b/g],
  ['Private key header', /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/g],
];

function git(args, noMatchIsEmpty = false) {
  try {
    return execFileSync('git', args, {
      encoding: 'utf8',
      maxBuffer: 256 * 1024 * 1024,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (error) {
    if (noMatchIsEmpty && error.status === 1) return '';
    const detail = error.stderr ? String(error.stderr).trim() : error.message;
    throw new Error('git ' + args.join(' ') + ' failed: ' + detail);
  }
}

function isPlaceholder(value) {
  const normalized = value.toLowerCase();
  const body = normalized.replace(/^(?:sk-|csk-|gsk_|hf_|gh[pousr]_|aiza)/, '');
  return /^x+$/.test(body) ||
    /(?:example|your[_-]?(?:api[_-]?)?key|placeholder|replace[_-]?me|buraya)/.test(normalized);
}

const revisions = git(['rev-list', '--all']).split(/\r?\n/).filter(Boolean);
const findings = new Map();

for (const revision of revisions) {
  const rows = git([
    'grep', '-I', '-n',
    '-e', 'sk-', '-e', 'csk-', '-e', 'gsk_', '-e', 'hf_',
    '-e', 'ghp_', '-e', 'gho_', '-e', 'ghu_', '-e', 'ghs_', '-e', 'ghr_',
    '-e', 'AIza', '-e', 'AKIA', '-e', 'PRIVATE KEY', revision,
  ], true);

  for (const row of rows.split(/\r?\n/)) {
    const match = row.match(/^([^:]+):(.+?):(\d+):(.*)$/);
    if (!match) continue;
    const [, commit, file, line, content] = match;

    for (const [kind, pattern] of patterns) {
      pattern.lastIndex = 0;
      for (const candidate of content.matchAll(pattern)) {
        const value = candidate[0];
        if (isPlaceholder(value)) continue;
        const digest = crypto.createHash('sha256').update(value).digest('hex').slice(0, 12);
        const id = kind + '|' + digest + '|' + file;
        if (!findings.has(id)) {
          findings.set(id, { kind, digest, commit: commit.slice(0, 12), file, line });
        }
      }
    }
  }
}

if (!findings.size) {
  console.log('Git history scan passed: ' + revisions.length + ' revisions checked.');
  process.exit(0);
}

console.error(
  'Git history scan failed: ' + findings.size +
  ' unique credential candidate(s) found across ' + revisions.length +
  ' revisions. Values are redacted.',
);
for (const item of findings.values()) {
  console.error(
    '- ' + item.kind + ' sha256:' + item.digest +
    ' at ' + item.commit + ':' + item.file + ':' + item.line,
  );
}
console.error('Revoke confirmed credentials before rewriting or publishing history.');
process.exit(1);
