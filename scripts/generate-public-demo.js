'use strict';

// Produces public demo media from the real Electron UI with offline synthetic data.
const {app, BrowserWindow} = require('electron');
const {spawnSync} = require('child_process');
const fs = require('fs');
const path = require('path');

const rootDir = path.resolve(__dirname, '..');
const outputDir = path.join(rootDir, 'docs', 'media');
const workDir = path.join(rootDir, 'artifacts', 'public-demo');

function fixtureHtml() {
    let html = fs.readFileSync(path.join(rootDir, 'templates', 'index.html'), 'utf8');
    html = html.replace('<script src="/static/socket.io.min.js"></script>', '');
    html = html.replace('<script src="/static/runtime-safety.js"></script>',
        `<script>${fs.readFileSync(path.join(rootDir, 'static', 'runtime-safety.js'), 'utf8')}</script>`);
    for (const name of ['html-utils.js', 'cockpit.js', 'live-flow.js', 'reading-mode.js', 'quick-phrases.js']) {
        html = html.replace(`<script src="/static/${name}"></script>`,
            `<script>${fs.readFileSync(path.join(rootDir, 'static', name), 'utf8')}</script>`);
    }
    html = html.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">',
        `<style>${fs.readFileSync(path.join(rootDir, 'static', 'whisper-pro-theme.css'), 'utf8')}</style>`);
    html = html.replace('{{ app_token|tojson }}', '"public-demo-token"');
    html = html.replace('socket = io();', 'socket={connected:true,_events:{},on(n,f){this._events[n]=f;}};');
    html = html.replace('window.onload = async function () {', 'window.onload = async function () { return;');
    html = html.replace('</head>', `<style>
      .public-demo-badge{position:fixed;right:18px;bottom:16px;z-index:9999;padding:8px 12px;
        border:1px solid rgba(114,150,255,.48);border-radius:10px;color:#b9caff;
        background:rgba(10,16,28,.92);font:600 12px/1.2 Inter,Segoe UI,sans-serif}
      .public-demo-badge strong{color:#fff}
      body.public-demo .readiness-panel,body.public-demo .ai-chat-container,
      body.public-demo .pipeline-details,body.public-demo .history-disclosure{display:none!important}
      body.public-demo .transcription-list{min-height:515px!important}
    </style></head>`);
    html = html.replace('</body>',
        '<script>window.fetch=async()=>({ok:true,json:async()=>({success:true,transcriptions:[]})});</script></body>');
    return html;
}

function setText(selector, value) {
    return `{const el=document.querySelector(${JSON.stringify(selector)});if(el)el.textContent=${JSON.stringify(value)};}`;
}

function setupScript() {
    const labels = [
        ['.brand-eyebrow', 'Speak across languages'],
        ['.brand-subtitle', 'Live translation and conversation assistant'],
        ['#connectionState', 'Connected'],
        ['#gameModeBtn', 'Game mode'],
        ['#controlsToggleBtn .header-action-label', 'Settings'],
        ['#pauseBtn .header-action-label', 'Pause'],
        ['#flushBtn .header-action-label', 'Send now'],
        ['#themeBtn .theme-label', 'Light'],
        ['.transcription-controls .section-kicker', 'OTHER PARTY'],
        ['.transcription-controls h2', 'Conversation'],
        ['#liveAudioState', 'Listening to system audio']
    ];
    return `(() => {
      document.body.classList.add('controls-collapsed','public-demo');
      ${labels.map(([selector,value])=>setText(selector,value)).join('\n')}
      const badge=document.createElement('div');badge.className='public-demo-badge';
      badge.innerHTML='<strong>Whisper Pro</strong> - synthetic demo';document.body.appendChild(badge);
      document.querySelector('.session-own-language span').textContent='Your language';
      document.querySelector('.session-own-language strong').textContent='English';
      document.querySelector('.session-target-language label').textContent='Other party';
      const language=document.getElementById('otherPartyLang');language.value='de';
      language.options[language.selectedIndex].text='German';
      const start=document.getElementById('startBtn');start.childNodes[start.childNodes.length-1].nodeValue=' Start';
      const stop=document.getElementById('stopBtn');
      if(stop)stop.childNodes[stop.childNodes.length-1].nodeValue=' Stop';
      const headerButtons=document.querySelectorAll('.transcription-controls button');
      if(headerButtons[0])headerButtons[0].textContent='Reset';
      if(headerButtons[headerButtons.length-1])headerButtons[headerButtons.length-1].textContent='Download';
      const search=document.getElementById('transcriptSearchInput');search.placeholder='Search conversations...';
      const list=document.getElementById('transcriptionList');list.innerHTML='';
      if(typeof seenTranscriptionIds!=='undefined')seenTranscriptionIds.clear();
      if(typeof transcriptionTexts!=='undefined')Object.keys(transcriptionTexts).forEach(key=>delete transcriptionTexts[key]);
      [
        {id:101,text:'K\\u00f6nnen wir das Treffen auf morgen Vormittag verschieben?',translation:'Could we move the meeting to tomorrow morning?',target_lang:'EN',timestamp:'10:42:18',model_language:'DE',source_lang:'de',confidence:.98},
        {id:102,text:'Ich kann den \\u00fcberarbeiteten Entwurf vor Mittag schicken.',translation:'I can send the revised design before noon.',target_lang:'EN',timestamp:'10:42:31',model_language:'DE',source_lang:'de',confidence:.97},
        {id:103,text:'Das passt f\\u00fcr mich. Bitte f\\u00fcge die Hinweise zur Barrierefreiheit hinzu.',translation:'That works for me. Please include the accessibility notes.',target_lang:'EN',timestamp:'10:42:47',model_language:'DE',source_lang:'de',confidence:.99}
      ].forEach(row=>addTranscription(row,true));
      document.querySelectorAll('.translation-label').forEach(el=>el.textContent='English translation');
      document.querySelectorAll('.transcript-edit-button').forEach(el=>el.textContent='Edit text');
      document.querySelectorAll('.ai-translate-btn').forEach(el=>el.textContent='Translate');
      document.querySelectorAll('.ai-answer-btn').forEach(el=>el.textContent='Suggest reply');
      selectReplyTarget(103,transcriptionTexts[103],true);
      renderReplyCockpit(103,[
        {translation:'Nat\\u00fcrlich. Ich f\\u00fcge die Hinweise hinzu und sende alles vor Mittag.',turkish:'Absolutely. I will add the notes and send everything before noon.',romanized:'Naturlih. Ih fuge di hin-vay-ze hinsu unt zende alles for mittag.',language:'de'},
        {translation:'Gern. M\\u00f6chtest du eine Checkliste oder eine kurze Zusammenfassung?',turkish:'Of course. Would you prefer a checklist or a short summary?',romanized:'Gern. Mohtezt du ayne chek-liste oda ayne kurtse tsuzammenfassung?',language:'de'},
        {translation:'Ja, ich nehme sie auf und teile das Dokument gleich.',turkish:'Yes. I will include them and share the document shortly.',romanized:'Ya, ih ney-me zi auf unt tayle das dokument glayh.',language:'de'}
      ],'de','German',false);
      ${setText('.reply-cockpit .section-kicker','YOUR REPLY')}
      ${setText('#replyCockpitTitle','Reply suggestions')}
      ${setText('#replyCockpitProgress','3 suggestions ready')}
      ${setText('label[for="responseLength"]','Reply length')}
      const length=document.getElementById('responseLength');
      length.options[0].text='Short';length.options[1].text='Normal';length.options[2].text='Detailed';
      const composer=document.querySelector('#replyComposerPanel summary');
      composer.childNodes[0].nodeValue='Write or speak your own reply ';composer.querySelector('span').textContent='Translate from English';
      const phrases=document.querySelector('#quickPhrasesPanel summary');
      phrases.childNodes[0].nodeValue='Quick phrases ';phrases.querySelector('.quick-hint').textContent='Repeat that - Please speak more slowly';
      document.querySelectorAll('.reply-option-number').forEach((el,i)=>el.textContent='Option '+(i+1));
      document.querySelectorAll('.reply-reading-label').forEach(el=>el.innerHTML='Say it like this <span>phonetic guide</span>');
      document.querySelectorAll('[data-reply-action="read"]').forEach(el=>el.textContent='Reading mode');
      document.querySelectorAll('[data-reply-action="copy"]').forEach(el=>el.textContent='Copy guide');
      document.querySelectorAll('[data-reply-action="listen"]').forEach(el=>el.textContent='Listen');
      document.querySelectorAll('[data-reply-action="save"]').forEach(el=>el.textContent='Save phrase');
      document.querySelectorAll('.reply-option-native .reply-detail-label').forEach(el=>el.textContent='Original reply');
      document.querySelectorAll('.reply-option-meaning .reply-detail-label').forEach(el=>el.textContent='Meaning in English');
      document.querySelector('.reply-cockpit-footer').textContent='Press 1-3 for reading mode - Esc to close';
      window.scrollTo(0,0);
      return {cards:document.querySelectorAll('.reply-option-card').length,rows:document.querySelectorAll('.transcription-item').length};
    })()`;
}

async function capture(win, name) {
    await new Promise(resolve=>setTimeout(resolve,350));
    fs.writeFileSync(path.join(outputDir,name),(await win.webContents.capturePage()).toPNG());
}

function createVideo() {
    const overview=path.join(outputDir,'whisper-pro-conversation.png');
    const reading=path.join(outputDir,'whisper-pro-reading-mode.png');
    const mp4=path.join(outputDir,'whisper-pro-demo.mp4');
    const gif=path.join(outputDir,'whisper-pro-demo.gif');
    const fit='scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0d1421,setsar=1';
    let result=spawnSync('ffmpeg',['-y','-loop','1','-t','4','-i',overview,'-loop','1','-t','4','-i',reading,
      '-filter_complex',`[0:v]${fit}[a];[1:v]${fit}[b];[a][b]xfade=transition=fade:duration=0.6:offset=3.4,format=yuv420p[v]`,
      '-map','[v]','-r','30','-t','7.4','-c:v','libx264','-crf','22','-movflags','+faststart',mp4],{encoding:'utf8'});
    if(result.status!==0)throw new Error('ffmpeg MP4 failed: '+result.stderr);
    result=spawnSync('ffmpeg',['-y','-i',mp4,'-filter_complex',
      '[0:v]fps=10,scale=960:-1:flags=lanczos,split[x][z];[x]palettegen=max_colors=128[p];[z][p]paletteuse=dither=bayer:bayer_scale=3',
      '-loop','0',gif],{encoding:'utf8'});
    if(result.status!==0)throw new Error('ffmpeg GIF failed: '+result.stderr);
}

app.setPath('userData',path.join(workDir,'electron-profile'));
app.disableHardwareAcceleration();
app.whenReady().then(async()=>{
    fs.mkdirSync(outputDir,{recursive:true});fs.mkdirSync(workDir,{recursive:true});
    const fixture=path.join(workDir,'public-demo.html');fs.writeFileSync(fixture,fixtureHtml(),'utf8');
    const win=new BrowserWindow({show:false,width:1440,height:900,
      webPreferences:{sandbox:true,contextIsolation:true,backgroundThrottling:false}});
    await win.loadFile(fixture);
    const state=await win.webContents.executeJavaScript(
      `(()=>{try{return {ok:true,value:${setupScript()}}}catch(error){return {ok:false,error:String(error),stack:error.stack}}})()`);
    if(!state.ok)throw new Error('Demo renderer failed: '+state.error+'\n'+state.stack);
    if(state.value.cards!==3||state.value.rows!==3)throw new Error('Demo fixture did not render: '+JSON.stringify(state.value));
    const layout=await win.webContents.executeJavaScript(`(()=>{const el=document.querySelector('.brand-lockup');
      const box=el.getBoundingClientRect();return {width:box.width,height:box.height,display:getComputedStyle(el).display,
      visibility:getComputedStyle(el).visibility,text:el.textContent.trim(),viewport:innerWidth}})()`);
    console.log('Demo brand geometry:',JSON.stringify(layout));
    await capture(win,'whisper-pro-conversation.png');
    await win.webContents.executeJavaScript(`openReadingMode(
      'Naturlih. Ih fuge di hin-vay-ze hinsu unt zende alles for mittag.',
      'Nat\\u00fcrlich. Ich f\\u00fcge die Hinweise hinzu und sende alles vor Mittag.',
      'Absolutely. I will add the notes and send everything before noon.','de');
      document.getElementById('readingModeTitle').textContent='Reading mode';
      const close=document.querySelector('.reading-close-btn');close.textContent='Close';close.setAttribute('aria-label','Close');
      document.querySelectorAll('.reading-audio-actions button').forEach((el,i)=>el.textContent=['Listen','Listen slowly','Stop'][i]);
      document.querySelector('.reading-hint').textContent='Read the phonetic guide aloud to answer naturally in German.';`);
    await capture(win,'whisper-pro-reading-mode.png');
    win.close();createVideo();
    console.log('Public demo media generated:',fs.readdirSync(outputDir).filter(name=>name.startsWith('whisper-pro-')).join(', '));
    app.quit();
}).catch(error=>{console.error(error);app.exit(1);});
