'use strict';

/*
 * Whisper Pro paketleme betigi (electron-packager Node API).
 *
 * NEDEN AYRI BIR BETIK: eskiden "npm run build" dogrudan
 * `electron-packager . ...` calistiriyordu; bu, --ignore listesi olmadigi
 * icin PROJE KOKUNU OLDUGU GIBI kopyaliyordu. Gercek bir pakette
 * api.txt/OPENAI.txt/"token (2).txt" (anahtar boyutunda dolu dosyalar),
 * kisisel transcriptions.txt, buyedektir.log ve archive/ bulundu.
 * package.json'daki eski "build" config blogu (files/win/portable)
 * electron-builder sozdizimidir; electron-packager onu HIC OKUMAZ --
 * sizintinin asil sebebi buydu (yaniltici, gorunuste calisan ama fiilen
 * hicbir seyi filtrelemeyen config).
 *
 * KARA LISTE yerine BEYAZ LISTE: gelecekte kazayla olusan yeni bir dosya
 * (bu sizintiya yol acanlarla ayni turden) bir kara listede unutulabilir;
 * beyaz listede ise listede ACIKCA yoksa otomatik disarida kalir.
 */

const path = require('path');
const fs = require('fs');
const packager = require('electron-packager');

const KEEP_FILES = new Set([
  'main.js',
  'main_helpers.js',
  'preload.js',
  'buyedektir.py',
  'audio_diagnostics.py',
  'requirements.txt',
  'package.json',
]);
const KEEP_DIRS = ['templates', 'assets', 'node_modules', 'static'];

function isKept(name) {
  // fs-extra'nin copy filtresi kok dizinin KENDISI icin bos string ('') ile
  // bir kez cagrilir (kopyalamanin ilk adimi); reddedilirse alt gezinme hic
  // baslamiyor. Kok her zaman "girilebilir" sayilmali; asil eleme alt
  // dosya/klasorlerde KEEP_FILES/KEEP_DIRS ile yapilir.
  if (name === '') return true;
  // electron-packager sürümüne göre başta '/' veya '\\' gelebilir.
  // Tek biçime indirgemezsek beyaz liste geçerli kaynakları yanlışlıkla atar.
  const normalized = String(name).replace(/\\/g, '/').replace(/^\/+/, '');
  if (KEEP_FILES.has(normalized)) return true;
  return KEEP_DIRS.some((dir) => normalized === dir || normalized.startsWith(dir + '/'));
}

// Paket olustuktan SONRA hassas/kisisel gorunumlu dosya adlarini tarayan
// guvenlik agi. Beyaz liste zaten bunlari disarida birakmali; bu tarama
// build.js'in kendisinde gelecekte yapilacak bir hata icin ikinci savunma
// katmanidir (orn. KEEP_DIRS icine yanlislikla genis bir klasor eklenirse).
const SUSPECT_PATTERNS = [
  /token/i,
  /^api\.txt$/i,
  /openai\.txt$/i,
  /\.env(\..*)?$/i,
  /^transcriptions?\.txt/i,
  /^speaker_profiles\.json$/i,
  /\.log$/i,
  /secret/i,
  /credential/i,
];
const SECRET_PATTERNS = [
  /\b(?:sk-|csk-|gsk_|hf_)[A-Za-z0-9_-]{20,}\b/g,
  /\bAIza[A-Za-z0-9_-]{25,}\b/g,
  /\b[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}:fx\b/ig,
];

function isPlaceholderSecret(value) {
  const body = value.replace(/^(?:sk-|csk-|gsk_|hf_|AIza)/i, '');
  return /^x+$/i.test(body) || /(?:example|your[_-]?key|buraya)/i.test(value);
}

function scanForLeaks(rootDir, sourceMode = false) {
  const leaks = [];
  const skippedSourceDirs = new Set([
    '.git', '.venv', 'venv', 'node_modules', 'dist', 'artifacts', '.claude', '.codex',
    'whisper_models'
  ]);
  const allowedLocalFiles = new Set([
    '.env', '.env.example', 'speaker_profiles.json', 'transcriptions.txt', 'buyedektir.log'
  ]);
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (sourceMode && skippedSourceDirs.has(entry.name)) continue;
        walk(full);
      } else {
        const rel = path.relative(rootDir, full).replace(/\\/g, '/');
        const isThirdParty = rel.split('/').includes('node_modules');
        const allowedLocal = sourceMode && allowedLocalFiles.has(rel);
        if (!isThirdParty && !allowedLocal
            && (SUSPECT_PATTERNS.some((re) => re.test(entry.name))
                || /^1\s*saat\.txt$/i.test(entry.name))) {
          leaks.push(full);
        }
        // Kendi metin kaynaklarinin ICERIGINI de tara. node_modules ve ikili
        // dosyalar hem bize ait degil hem de ornek anahtar metinleri tasiyabilir.
        if (!isThirdParty && !allowedLocal
            && (sourceMode
              ? /\.(?:js|py|html|json|txt)$/i.test(entry.name)
              : /\.(?:js|py|html|json)$/i.test(entry.name))) {
          const content = fs.readFileSync(full, 'utf8');
          const hasSecret = SECRET_PATTERNS.some((re) => {
            re.lastIndex = 0;
            return Array.from(content.matchAll(re))
              .some((match) => !isPlaceholderSecret(match[0]));
          });
          if (hasSecret) leaks.push(full + ' [icerik]');
        }
      }
    }
  }
  walk(rootDir);
  return leaks;
}

function warnIfDistStale() {
  const appRoot = path.join(
    __dirname, 'dist', 'Whisper-Pro-win32-x64', 'resources', 'app'
  );
  const packagedMain = path.join(appRoot, 'main.js');
  if (!fs.existsSync(packagedMain)) return;
  const distTime = fs.statSync(packagedMain).mtimeMs;
  const stale = [...KEEP_FILES]
    .map((name) => path.join(__dirname, name))
    .filter((file) => fs.existsSync(file) && fs.statSync(file).mtimeMs > distTime);
  if (stale.length) {
    console.warn(
      'UYARI: dist kaynaklardan eski (' + stale.length + ' dosya). Paket yenileniyor...'
    );
  }
}

function scanSourceOrFail() {
  const leaks = scanForLeaks(__dirname, true);
  if (!leaks.length) {
    console.log('Kaynak depo guvenlik taramasi temiz.');
    return true;
  }
  console.error('GUVENLIK: kaynak depoda hassas gorunumlu dosya/icerik bulundu:');
  leaks.forEach((file) => console.error('  - ' + path.relative(__dirname, file)));
  return false;
}

async function build() {
  warnIfDistStale();
  if (!scanSourceOrFail()) {
    process.exitCode = 1;
    return;
  }
  const appPaths = await packager({
    dir: '.',
    name: 'Whisper-Pro',
    platform: 'win32',
    arch: 'x64',
    out: 'dist',
    overwrite: true,
    asar: false,
    ignore: (file) => !isKept(file),
  });

  console.log('Paketlendi:');
  appPaths.forEach((p) => console.log('  ' + p));

  // Bu cikti Electron'u paketler; 2.7 GB'lik Whisper/Torch Python ortamini
  // gommez. Klasor proje disina tasinacaksa kullaniciya sessizce "portable"
  // vaadi vermek yerine gereken kurulumu paketin icinde acikca birak.
  const runtimeNote = [
    'Whisper Pro Python çalışma zamanı notu',
    '',
    'Bu Electron paketi Python yorumlayıcısını ve yaklaşık 2.7 GB model/ML bağımlılıklarını içermez.',
    'Bu klasörde .venv oluşturup requirements.txt dosyasını kurun veya WHISPER_PYTHON',
    'ortam değişkenini gerekli paketlerin kurulu olduğu python.exe yoluna ayarlayın.',
    '',
    'Örnek:',
    '  py -m venv .venv',
    '  .venv\\Scripts\\python.exe -m pip install -r resources\\app\\requirements.txt',
  ].join('\r\n');
  appPaths.forEach((p) => {
    fs.writeFileSync(path.join(p, 'PYTHON-GEREKSINIMI.txt'), runtimeNote, 'utf8');
  });

  let allLeaks = [];
  for (const appPath of appPaths) {
    allLeaks = allLeaks.concat(scanForLeaks(appPath));
  }

  if (allLeaks.length) {
    console.error('\n!!! GUVENLIK: pakette hassas/kisisel gorunumlu dosya(lar) bulundu:');
    allLeaks.forEach((f) => console.error('  - ' + f));
    console.error('\nbuild.js icindeki KEEP_FILES/KEEP_DIRS listesini kontrol edin.');
    process.exitCode = 1;
    return;
  }

  console.log('Guvenlik taramasi temiz: hassas/kisisel dosya adi bulunamadi.');
}

if (process.argv.includes('--scan-source')) {
  if (!scanSourceOrFail()) process.exitCode = 1;
} else {
  build().catch((err) => {
    console.error(err);
    process.exitCode = 1;
  });
}
