'use strict';

// Produces English public screenshots from the real Game Mode overlay with offline synthetic data.
const {app, BrowserWindow} = require('electron');
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const outputDir = path.join(rootDir, 'docs', 'media');
const workDir = path.join(rootDir, 'artifacts', 'public-game-demo');

function fixtureHtml() {
    let html = fs.readFileSync(path.join(rootDir, 'templates', 'overlay.html'), 'utf8');
    html = html.replace('<script src="/static/socket.io.min.js"></script>',
        '<script>window.overlayEvents={};function io(){return {on(name,fn){overlayEvents[name]=fn;}};}</script>');
    for (const name of ['runtime-safety.js', 'html-utils.js', 'i18n.js']) {
        html = html.replace(`<script src="/static/${name}"></script>`,
            `<script>${fs.readFileSync(path.join(rootDir, 'static', name), 'utf8')}</script>`);
    }
    html = html.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">',
        `<style>${fs.readFileSync(path.join(rootDir, 'static', 'whisper-pro-theme.css'), 'utf8')}</style>`);
    html = html.replace('{{ app_token|tojson }}', '"public-game-demo-token"');
    html = html.replace('</head>', `<style>
      .public-demo-badge{position:fixed;right:12px;top:10px;z-index:9999;padding:4px 7px;
        border:1px solid rgba(114,150,255,.42);border-radius:6px;color:#b9caff;
        background:rgba(10,16,28,.88);font:600 9px/1.2 Inter,Segoe UI,sans-serif}
    </style></head>`);
    html = html.replace('<script>', `<script>
      window.fetch=async()=>({ok:true,json:async()=>({success:true,instance_id:'public-demo',transcriptions:[]})});
      window.electronAPI={overlayControl:async()=>({success:true,locked:false}),onOverlayState() {}};
    </script><script>`);
    return html;
}

function setText(selector, value) {
    return `{const el=document.querySelector(${JSON.stringify(selector)});if(el)el.textContent=${JSON.stringify(value)};}`;
}

function setupScript() {
    return `(() => {
      setConnected(true);
      renderTranscript({id:1,instance_id:'public-demo',revision:0,source:'system',
        text:'Die Wache kommt zurück. Wir müssen einen anderen Weg finden.',
        translation:'The guard is coming back. We need to find another route.',
        translation_status:'translated'});
      ${setText('#hudConnection','Live translation')}
      ${setText('#aiBtn','Suggest reply')}
      ${setText('#hudSettings summary','Appearance')}
      ${setText('#hudMode','Position the overlay, then lock it')}
      ${setText('#lockBtn','Lock to game')}
      ${setText('#closeBtn','')}
      const labels=document.querySelectorAll('#hudSettings .controls label');
      if(labels[0])labels[0].childNodes[0].nodeValue='Text ';
      if(labels[1])labels[1].childNodes[0].nodeValue='Background ';
      if(labels[2])labels[2].lastChild.nodeValue=' Original text';
      const help=document.querySelector('#hudSettings p');
      if(help)help.textContent='Drag the header to move. Ctrl+Shift+O: show or hide. Ctrl+Shift+L: click-through game lock. Borderless-windowed mode is recommended.';
      const badge=document.createElement('div');badge.className='public-demo-badge';badge.textContent='SYNTHETIC DEMO';document.body.appendChild(badge);
      document.body.style.setProperty('--hud-font','27px');
      return {translation:document.querySelector('.translation-text')?.textContent,settings:Boolean(document.getElementById('hudSettings'))};
    })()`;
}

async function capture(win, name) {
    await new Promise(resolve => setTimeout(resolve, 250));
    fs.writeFileSync(path.join(outputDir, name), (await win.webContents.capturePage()).toPNG());
}

app.setPath('userData', path.join(workDir, 'electron-profile'));
app.disableHardwareAcceleration();
app.whenReady().then(async () => {
    fs.mkdirSync(outputDir, {recursive: true});
    fs.mkdirSync(workDir, {recursive: true});
    const fixture = path.join(workDir, 'game-demo.html');
    fs.writeFileSync(fixture, fixtureHtml(), 'utf8');
    const win = new BrowserWindow({show: false, width: 760, height: 446,
        webPreferences: {sandbox: true, contextIsolation: true, backgroundThrottling: false}});
    await win.loadFile(fixture);
    const state = await win.webContents.executeJavaScript(
        `(()=>{try{return {ok:true,value:${setupScript()}}}catch(error){return {ok:false,error:String(error),stack:error.stack}}})()`);
    if (!state.ok || !state.value.translation || !state.value.settings) {
        throw new Error('Game demo renderer failed: ' + JSON.stringify(state));
    }
    await capture(win, 'whisper-pro-game-mode.png');
    await win.webContents.executeJavaScript(`document.getElementById('hudSettings').open=true;`);
    const layout = await win.webContents.executeJavaScript(`(() => {
      const settings=document.getElementById('hudSettings').getBoundingClientRect();
      const translation=document.querySelector('.translation-text').getBoundingClientRect();
      return {innerWidth,innerHeight,scrollHeight:document.documentElement.scrollHeight,
        settingsBottom:Math.round(settings.bottom),translationBottom:Math.round(translation.bottom)};
    })()`);
    if (layout.settingsBottom > layout.innerHeight || layout.scrollHeight > layout.innerHeight) {
        throw new Error('Game demo content is clipped: ' + JSON.stringify(layout));
    }
    console.log('Game demo geometry:', JSON.stringify(layout));
    await capture(win, 'whisper-pro-game-mode-settings.png');
    console.log('Public Game Mode media generated.');
    win.close();
    app.quit();
}).catch(error => { console.error(error); app.exit(1); });
