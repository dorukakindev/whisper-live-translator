// templates/ icindeki inline <script> bloklarinin sozdizimini dogrular.
// Repo'da frontend derleme adimi yok; tek dogrulama noktasi bu betiktir.
// Jinja sablonu tarayiciya degil render'a gider: `{{ app_token|tojson }}`
// degerini `""`, diger `{{ ... }}` bloklarini `null`, `{% ... %}` etiketlerini
// bos string olarak degistirip saf JS'i vm ile derler (calistirmaz).
// Kullanim: node scripts/check-inline-scripts.js [template ...]

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const DEFAULT_TEMPLATES = [
    'templates/index.html',
    'templates/overlay.html',
];

// Dis baglantili <script src=...> bloklari atlanir; sadece inline govde alinir.
const SCRIPT_RE = /<script(?![^>]*\bsrc\b)[^>]*>([\s\S]*?)<\/script>/gi;

function stripJinja(source) {
    return source
        .replace(/\{\{\s*app_token\s*\|\s*tojson\s*\}\}/g, '""')
        .replace(/\{\{[\s\S]*?\}\}/g, 'null')
        .replace(/\{%[\s\S]*?%\}/g, '');
}

function checkTemplate(file) {
    const html = fs.readFileSync(file, 'utf8');
    const failures = [];
    let count = 0;
    for (const match of html.matchAll(SCRIPT_RE)) {
        count += 1;
        const block = stripJinja(match[1]);
        if (!block.trim()) continue;
        const line = html.slice(0, match.index).split('\n').length;
        try {
            new vm.Script(block, {filename: `${file}#script-${count}@L${line}`});
        } catch (err) {
            failures.push(`  ${file} script #${count} (satir ${line}): ${err.message}`);
        }
    }
    return {count, failures};
}

function main() {
    const targets = process.argv.slice(2).length
        ? process.argv.slice(2)
        : DEFAULT_TEMPLATES;
    const allFailures = [];
    let total = 0;
    for (const rel of targets) {
        const file = path.isAbsolute(rel) ? rel : path.join(ROOT, rel);
        const {count, failures} = checkTemplate(file);
        total += count;
        allFailures.push(...failures);
    }
    if (allFailures.length) {
        console.error('INLINE SCRIPT KONTROLU BASARISIZ:');
        console.error(allFailures.join('\n'));
        process.exit(1);
    }
    console.log(`INLINE SCRIPT KONTROLU GECTI: ${total} blok (${targets.join(', ')})`);
}

main();
