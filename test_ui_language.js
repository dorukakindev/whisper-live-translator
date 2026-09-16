'use strict';

// Gerçek Chromium DOM'unda varsayılan İngilizce, Türkçe geçişi ve içerik koruması.
const {app, BrowserWindow} = require('electron');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const root = __dirname;
const output = path.join(root, 'artifacts', 'ui-language');

function inlineShared(html) {
    html = html.replace('<script src="/static/socket.io.min.js"></script>',
        '<script>window.__events={};function io(){return {connected:true,on(n,f){window.__events[n]=f;}};}</script>');
    for (const name of ['runtime-safety.js','html-utils.js','i18n.js','cockpit.js','live-flow.js','reading-mode.js','quick-phrases.js']) {
        html = html.replace(`<script src="/static/${name}"></script>`,
            `<script>${fs.readFileSync(path.join(root,'static',name),'utf8')}</script>`);
    }
    return html.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">',
        `<style>${fs.readFileSync(path.join(root,'static','whisper-pro-theme.css'),'utf8')}</style>`)
        .replace('{{ app_token|tojson }}','"i18n-test-token"');
}

function mainFixture() {
    let html = inlineShared(fs.readFileSync(path.join(root,'templates','index.html'),'utf8'));
    html = html.replace('window.onload = async function () {','window.onload = async function () { return;');
    return html.replace('</body>',`<script>
      window.fetch=async()=>({ok:true,json:async()=>({success:true,transcriptions:[]})});
    </script></body>`);
}

function overlayFixture() {
    let html = inlineShared(fs.readFileSync(path.join(root,'templates','overlay.html'),'utf8'));
    return html.replace('<script>\n        // Bu overlay',`<script>
      window.fetch=async()=>({ok:true,json:async()=>({success:true,instance_id:'i18n',transcriptions:[]})});
      window.electronAPI={overlayControl:async()=>({success:true,locked:false}),onOverlayState(){}};
    </script><script>
        // Bu overlay`);
}

async function inspectMain(win) {
    return win.webContents.executeJavaScript(`(() => {
      addTranscription({id:44,text:'Kapat',translation:'Ayarlar',timestamp:'10:00',model_language:'TR',source_lang:'tr',confidence:.99},true);
      const content=()=>({source:document.querySelector('.transcription-original')?.textContent,translationPreserved:document.querySelector('.transcription-translation')?.textContent.includes('Ayarlar')});
      const english={lang:document.documentElement.lang,selected:uiLanguage.value,settings:document.querySelector('#controlsToggleBtn .header-action-label').textContent,game:gameModeBtn.textContent,conversation:document.querySelector('.transcription-controls h2').textContent,content:content()};
      whisperI18n.setLanguage('tr');
      const turkish={lang:document.documentElement.lang,selected:uiLanguage.value,settings:document.querySelector('#controlsToggleBtn .header-action-label').textContent,game:gameModeBtn.textContent,conversation:document.querySelector('.transcription-controls h2').textContent,content:content()};
      whisperI18n.setLanguage('en');
      const dynamic=document.createElement('button');dynamic.textContent='Çeviri hazırlanıyor…';document.body.appendChild(dynamic);
      return new Promise(resolve=>setTimeout(()=>resolve({english,turkish,dynamic:dynamic.textContent,stored:whisperStorage.getItem('whisperUiLanguage')}),0));
    })()`);
}

app.setPath('userData',path.join(output,'profile'));
app.disableHardwareAcceleration();
app.whenReady().then(async()=>{
    fs.mkdirSync(output,{recursive:true});
    const mainPath=path.join(output,'main.html');
    const overlayPath=path.join(output,'overlay.html');
    fs.writeFileSync(mainPath,mainFixture(),'utf8');
    fs.writeFileSync(overlayPath,overlayFixture(),'utf8');
    const main=new BrowserWindow({show:false,width:1440,height:900,webPreferences:{sandbox:true,contextIsolation:true,backgroundThrottling:false}});
    await main.loadFile(mainPath);
    const state=await inspectMain(main);
    assert.deepStrictEqual(state.english,{lang:'en',selected:'en',settings:'Settings',game:'Game Mode',conversation:'Conversation',content:{source:'Kapat',translationPreserved:true}});
    assert.deepStrictEqual(state.turkish,{lang:'tr',selected:'tr',settings:'Ayarlar',game:'Oyun modu',conversation:'Konuşma akışı',content:{source:'Kapat',translationPreserved:true}});
    assert.strictEqual(state.dynamic,'Preparing translation…');
    assert.strictEqual(state.stored,'en');
    const overlay=new BrowserWindow({show:false,width:760,height:446,webPreferences:{sandbox:true,contextIsolation:true,backgroundThrottling:false}});
    await overlay.loadFile(overlayPath);
    const overlayState=await overlay.webContents.executeJavaScript(`({lang:document.documentElement.lang,appearance:document.querySelector('#hudSettings summary').textContent,lock:lockBtn.textContent,empty:document.getElementById('emptyHint').textContent})`);
    assert.deepStrictEqual(overlayState,{lang:'en',appearance:'Appearance',lock:'Lock to game',empty:'Stay in the game. Translation appears here.Enable system audio and translation in the main window, then press Start. Translated dialogue will appear here.'});
    console.log('Default English, Turkish switch, persistence, overlay, and content preservation passed.');
    main.close();overlay.close();app.quit();
}).catch(error=>{console.error(error);app.exit(1);});
