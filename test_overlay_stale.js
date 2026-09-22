'use strict';
// Overlay (oyun ustunde gosterim) bayat-veri reddi: bayat revision, yanlis
// instance, clear sonrasi gecikmis ceviri ve mic/ptt kaynaklari HUD'a
// dusmemeli. Gercek Windows oyun/overlay davranisini kanitlamaz — Xvfb
// altinda yalniz DOM seviyesi sahiplik sozlesmesi dogrulanir.
const {app, BrowserWindow} = require('electron');
const fs = require('fs');
const path = require('path');

const outputDir = path.join(__dirname, 'artifacts', 'overlay-stale');

function fixtureHtml() {
    let html = fs.readFileSync(path.join(__dirname, 'templates', 'overlay.html'), 'utf8');
    for (const moduleName of ['socket.io.min.js', 'runtime-safety.js', 'html-utils.js', 'i18n.js']) {
        html = html.replace(`<script src="/static/${moduleName}"></script>`,
            `<script>${fs.readFileSync(path.join(__dirname, 'static', moduleName), 'utf8')}</script>`);
    }
    html = html.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">',
        `<style>${fs.readFileSync(path.join(__dirname, 'static', 'whisper-pro-theme.css'), 'utf8')}</style>`);
    html = html.replace('{{ app_token|tojson }}', '"fixture-token"');
    html = html.replace(/socket = io\([^)]*\);/,
        `socket = {connected:true, _events:{}, on(n,f){this._events[n]=f;}, emit(){}};`);
    return html;
}

app.setPath('userData', path.join(outputDir, 'electron-profile'));
app.disableHardwareAcceleration();
app.whenReady().then(async () => {
    fs.mkdirSync(outputDir, {recursive: true});
    const fixturePath = path.join(outputDir, 'overlay-fixture.html');
    fs.writeFileSync(fixturePath, fixtureHtml(), 'utf8');
    const win = new BrowserWindow({show:false, webPreferences:{sandbox:true, contextIsolation:true, backgroundThrottling:false}});
    await win.loadFile(fixturePath);
    await new Promise(resolve => setTimeout(resolve, 150));
    const failures = [];
    const step = (name, ok, extra) => {
        if (!ok) failures.push(`${name}: ${JSON.stringify(extra)}`);
        console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`);
    };
    const run = js => win.webContents.executeJavaScript(js);

    // 1) normal transkript HUD'a duser
    let s = await run(`(()=>{
        socket._events.new_transcription({id:1, text:'merhaba duni', source:'system',
            revision:0, instance_id:'inst-A'});
        return document.body.textContent.includes('merhaba duni');
    })()`);
    step('overlay renders live transcript', s === true, s);

    // 2) bayat revision ceviri reddedilir
    s = await run(`(()=>{
        socket._events.transcription_translation({id:1, revision:99,
            translation:'bayat ceviri'});
        return document.body.textContent.includes('bayat ceviri');
    })()`);
    step('stale-revision translation dropped', s === false, s);

    // 3) goruntulenen satir disinda id ile ceviri dusmez
    s = await run(`(()=>{
        socket._events.transcription_translation({id:7, revision:0,
            translation:'baska satir ceviri'});
        return document.body.textContent.includes('baska satir ceviri');
    })()`);
    step('foreign-id translation dropped', s === false, s);

    // 4) eski (dusuk id) transkript ekranin yerini alamaz
    s = await run(`(()=>{
        socket._events.new_transcription({id:0, text:'eski satir', source:'system',
            revision:0, instance_id:'inst-A'});
        return document.body.textContent.includes('eski satir');
    })()`);
    step('older transcript cannot displace', s === false, s);

    // 5) farkli backend instance correction guncelleme yapmaz
    s = await run(`(()=>{
        socket._events.transcription_corrected({id:1, text:'baska inst satiri',
            source:'system', revision:1, instance_id:'inst-Z'});
        return document.body.textContent.includes('baska inst satiri');
    })()`);
    step('foreign-instance correction dropped', s === false, s);

    // 6) mic/ptt kaynakli satirlar overlay'e girmez
    s = await run(`(()=>{
        socket._events.new_transcription({id:9, text:'ptt ses kaydi',
            source:'ptt', revision:0, instance_id:'inst-A'});
        socket._events.new_transcription({id:10, text:'mic dict',
            source:'mic', revision:0, instance_id:'inst-A'});
        return document.body.textContent.includes('ptt ses kaydi')
            || document.body.textContent.includes('mic dict');
    })()`);
    step('mic/ptt sources filtered', s === false, s);

    // 7) clear sonrasi gecikmis ceviri yeni gostergeyi kirletemez
    s = await run(`(()=>{
        socket._events.transcriptions_cleared();
        const cleared = !document.body.textContent.includes('merhaba duni');
        // clear aninda HUD'daki son bilinen id sifirlanir mi? yeni kayit icin
        // socket._events.transcription_translation ile ayni id+rev gonder
        socket._events.transcription_translation({id:1, revision:0,
            translation:'clearda kalan ceviri'});
        const late = document.body.textContent.includes('clearda kalan ceviri');
        return {cleared, late};
    })()`);
    step('cleared + late translation cannot resurrect', s.cleared && !s.late, s);

    // 8) yeni instance transkripti render edilir; baska instance correction'i ezmez
    s = await run(`(()=>{
        socket._events.new_transcription({id:20, text:'inst-B satir',
            source:'system', revision:0, instance_id:'inst-B'});
        const bShown = document.body.textContent.includes('inst-B satir');
        socket._events.transcription_corrected({id:20, text:'inst-C satir',
            source:'system', revision:1, instance_id:'inst-C'});
        return {bShown,
            bKept: document.body.textContent.includes('inst-B satir'),
            cDropped: !document.body.textContent.includes('inst-C satir')};
    })()`);
    step('instance-B shown, instance-C correction dropped',
        s.bShown === true && s.bKept === true && s.cDropped === true, s);

    await win.webContents.executeJavaScript('void 0');
    if (failures.length) {
        console.error('BASARISIZ:', failures.join(' | '));
        app.exit(1);
    } else {
        console.log('TUM OVERLAY-STALE TESTLERI GECTI');
        app.exit(0);
    }
});
