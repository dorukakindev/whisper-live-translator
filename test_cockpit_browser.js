'use strict';

// Gercek Electron/Chromium DOM'u ile agsiz Cockpit v2 davranis ve goruntu testi.
const {app, BrowserWindow} = require('electron');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const outputDir = path.join(__dirname, 'artifacts', 'cockpit-v2');
const sizes = [[1440, 900], [1280, 720], [900, 700], [600, 800], [380, 260]];

function fixtureHtml() {
    let html = fs.readFileSync(path.join(__dirname, 'templates', 'index.html'), 'utf8');
    html = html.replace('<script src="/static/socket.io.min.js"></script>', '');
    html = html.replace('<script src="/static/runtime-safety.js"></script>',
        `<script>${fs.readFileSync(path.join(__dirname, 'static', 'runtime-safety.js'), 'utf8')}</script>`);
    for (const moduleName of ['html-utils.js', 'cockpit.js', 'reading-mode.js', 'quick-phrases.js']) {
        html = html.replace(`<script src="/static/${moduleName}"></script>`,
            `<script>${fs.readFileSync(path.join(__dirname, 'static', moduleName), 'utf8')}</script>`);
    }
    html = html.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">',
        `<style>${fs.readFileSync(path.join(__dirname, 'static', 'whisper-pro-theme.css'), 'utf8')}</style>`);
    html = html.replace('{{ app_token|tojson }}', '"fixture-token"');
    html = html.replace('socket = io();', `socket = {connected:true, _events:{}, on(n,f){this._events[n]=f;}};`);
    html = html.replace('window.onload = async function () {', 'window.onload = async function () { return;');
    html = html.replace('</body>', `<script>
        window.fetch = async url => ({ok:true, json:async()=> url.includes('stats')
            ? {total_transcriptions:2, latency:{asr:{p95_ms:420},translation:{p95_ms:710}},performance:{audio_queue_size:0}}
            : {success:true, transcriptions:[]}});
        _socketConnected = true;
        updateCockpitStatus();
        const setupStepCount = document.querySelectorAll('.setup-step').length;
        document.getElementById('setupModel').click();
        const setupTargetFocused = document.activeElement?.id === 'modelLoadBtn';
        addTranscription({id:1,text:'Bugün toplantıdan sonra istasyonda buluşabilir miyiz?',timestamp:'14:32',model_language:'TR',source_lang:'tr',confidence:.96});
        selectReplyTarget(1, transcriptionTexts[1], true);
        renderAiResult(1,'answer',{success:true,detected_lang:'ja',options:[
          {translation:'はい、会議のあと駅で会いましょう。',turkish:'Evet, toplantıdan sonra istasyonda buluşalım.',romanized:'Hay, kaigi-no ato eki-de aymaşo.',language:'ja'},
          {translation:'もちろんです。何時がいいですか？',turkish:'Elbette. Saat kaç uygun?',romanized:'Moçiron-des. Nan-ci ga ii-des-ka?',language:'ja'},
          {translation:'少し遅れるかもしれません。',turkish:'Biraz gecikebilirim.',romanized:'Sukoşi okureru kamo şiremasen.',language:'ja'},
          {translation:'駅の北口で待っています。',turkish:'İstasyonun kuzey çıkışında bekliyorum.',romanized:'Eki-no kita-guçi-de matteymas.',language:'ja'}
        ]},'auto','Japonca',false);
        updateStats();
        const firstReading = document.querySelector('.reply-read-button');
        document.getElementById('cockpitLatencyState').click();
        const latencyDetailsVisible = !document.getElementById('cockpitLatencyDetails').hidden;
        firstReading.click();
        const readingBefore = document.querySelector('.reading-okunus').textContent;
        renderReplyCockpit(99,[{translation:'Gecikmiş',turkish:'Eski',romanized:'Eski-okunuş'}],'ja','Japonca',false);
        const staleIgnored = !document.getElementById('replyCockpitOptions').textContent.includes('Gecikmiş');
        const readingPreserved = document.querySelector('.reading-okunus').textContent === readingBefore;
        closeReadingMode();
        window.__cockpitSelfTest = {staleIgnored, readingPreserved, latencyDetailsVisible,
            setupStepCount, setupTargetFocused,
            duplicateIds:[...document.querySelectorAll('[id]')].map(x=>x.id).filter((x,i,a)=>a.indexOf(x)!==i)};
    </script></body>`);
    return html;
}

if (process.argv.includes('--generate')) {
    fs.mkdirSync(outputDir, {recursive: true});
    fs.writeFileSync(path.join(outputDir, 'fixture.html'), fixtureHtml(), 'utf8');
    console.log('Fixture hazirlandi');
    process.exit(0);
}

app.setPath('userData', path.join(outputDir, 'electron-profile'));
app.disableHardwareAcceleration();
app.whenReady().then(async () => {
    fs.mkdirSync(outputDir, {recursive: true});
    const fixturePath = path.join(outputDir, 'fixture.html');
    fs.writeFileSync(fixturePath, fixtureHtml(), 'utf8');
    const win = new BrowserWindow({show:false, webPreferences:{sandbox:true, contextIsolation:true}});
    await win.loadFile(fixturePath);
    await new Promise(resolve => setTimeout(resolve, 150));
    const initial = await win.webContents.executeJavaScript(`({
        cards: document.querySelectorAll('.reply-option-card').length,
        duplicateIds: [...document.querySelectorAll('[id]')].map(x=>x.id).filter((x,i,a)=>a.indexOf(x)!==i),
        listenerBound: socket._whisperListenersBound || false
    })`);
    assert.strictEqual(initial.cards, 4);
    assert.deepStrictEqual(initial.duplicateIds, []);
    const ownership = await win.webContents.executeJavaScript('window.__cockpitSelfTest');
    assert.deepStrictEqual(ownership, {staleIgnored:true, readingPreserved:true,
        latencyDetailsVisible:true, setupStepCount:4, setupTargetFocused:true,
        duplicateIds:[]});

    for (const [width, height] of sizes) {
        win.setSize(width, height);
        await new Promise(resolve => setTimeout(resolve, 80));
        const geometry = await win.webContents.executeJavaScript(`({
            overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
            transcript: !!document.querySelector('.transcription-area'),
            cockpit: !!document.querySelector('.reply-cockpit'),
            buttons: [...document.querySelectorAll('#replyCockpitOptions button')].every(b=>b.getBoundingClientRect().width>0)
        })`);
        assert.strictEqual(geometry.overflow, false, width + 'px yatay tasma');
        assert(geometry.transcript && geometry.cockpit && geometry.buttons);
        const image = await win.webContents.capturePage();
        fs.writeFileSync(path.join(outputDir, `${width}x${height}-dark.png`), image.toPNG());
    }

    await win.webContents.executeJavaScript(`document.body.classList.add('light-mode'); openReadingMode(
        'Sukoşi okureru kamo şiremasen. Çok uzun bir okunuş satırı taşmadan devam etmeli.',
        '少し遅れるかもしれません。','Biraz gecikebilirim.','ja')`);
    win.setSize(600, 800);
    await new Promise(resolve => setTimeout(resolve, 80));
    const modal = await win.webContents.executeJavaScript(`({
        role: document.getElementById('readingOverlay').getAttribute('role'),
        visible: document.getElementById('readingOverlay').classList.contains('visible'),
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        focused: document.activeElement.className
    })`);
    assert.strictEqual(modal.role, 'dialog'); assert(modal.visible); assert.strictEqual(modal.overflow, false);
    assert(modal.focused.includes('reading-close-btn'));
    fs.writeFileSync(path.join(outputDir, '600x800-light-reading.png'), (await win.webContents.capturePage()).toPNG());
    win.close();
    console.log('Gercek Chromium Cockpit davranis ve gorsel testleri gecti:', outputDir);
    app.quit();
}).catch(error => { console.error(error); app.exit(1); });
