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
        addTranscription({id:1,text:'会議のあと、駅で会えますか？',translation:'Toplantıdan sonra istasyonda buluşabilir miyiz?',target_lang:'TR',timestamp:'14:32',model_language:'JA',source_lang:'ja',confidence:.96});
        selectReplyTarget(1, transcriptionTexts[1], true);
        renderAiResult(1,'answer',{success:true,detected_lang:'ja',options:[
          {translation:'はい、会議のあと駅で会いましょう。',turkish:'Evet, toplantıdan sonra istasyonda buluşalım.',romanized:'Hay, kaigi-no ato eki-de aymaşo.',language:'ja'},
          {translation:'もちろんです。何時がいいですか？',turkish:'Elbette. Saat kaç uygun?',romanized:'Moçiron-des. Nan-ci ga ii-des-ka?',language:'ja'},
          {translation:'少し遅れるかもしれません。',turkish:'Biraz gecikebilirim.',romanized:'Sukoşi okureru kamo şiremasen.',language:'ja'},
          {translation:'駅の北口で待っています。',turkish:'İstasyonun kuzey çıkışında bekliyorum.',romanized:'Eki-no kita-guçi-de matteymas.',language:'ja'}
        ]},'auto','Japonca',false);
        document.getElementById('otherPartyLang').value = 'ja';
        document.getElementById('aiTargetLang').value = 'ja';
        renderQuickPhrases();
        updateCockpitStatus();
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
    const win = new BrowserWindow({show:false, webPreferences:{sandbox:true, contextIsolation:true, backgroundThrottling:false}});
    await win.loadFile(fixturePath);
    win.showInactive();
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
    const readingChecks = await win.webContents.executeJavaScript(`(() => {
        const opener = document.querySelector('.reply-read-button');
        opener.focus(); opener.click();
        changeReadingFont(0.3);
        document.dispatchEvent(new KeyboardEvent('keydown', {key:'2',bubbles:true}));
        const remembered = _readingFontScale === 1.3;
        changeReadingFont(NaN);
        const finite = Number.isFinite(_readingFontScale);
        let generated = false;
        const answer = document.querySelector('.ai-answer-btn');
        const original = answer.onclick;
        answer.onclick = () => {generated = true;};
        document.dispatchEvent(new KeyboardEvent('keydown', {key:'c',bubbles:true}));
        answer.onclick = original;
        closeReadingMode();
        const focusRestored = document.activeElement === opener;
        whisperStorage.removeItem('readingFontScale');
        return {remembered,finite,focusRestored,blocked:!generated};
    })()`);
    assert.deepStrictEqual(readingChecks, {remembered:true,finite:true,focusRestored:true,blocked:true});
    const selectionChecks = await win.webContents.executeJavaScript(`(() => {
        const host = document.getElementById('replyCockpitOptions');
        const buttons = [...host.querySelectorAll('.reply-choice')];
        buttons[2].focus(); buttons[2].click();
        const selectedText = host.querySelector('.reply-option-card:not([hidden]) .reply-option-pronunciation').textContent;
        const onlyOne = host.querySelectorAll('.reply-option-card:not([hidden])').length === 1;
        const pressed = buttons[2].getAttribute('aria-pressed') === 'true';
        const selectedKey = host.dataset.selectedKey;
        const data = [{translation:'少し遅れるかもしれません。',turkish:'Biraz gecikebilirim.',romanized:'Sukoşi okureru kamo şiremasen.',language:'ja'},
          {translation:'はい、会議のあと駅で会いましょう。',turkish:'Evet, toplantıdan sonra istasyonda buluşalım.',romanized:'Hay, kaigi-no ato eki-de aymaşo.',language:'ja'}];
        renderReplyCockpit(1, data, 'ja', 'Japonca', false);
        const preserved = host.dataset.selectedKey === selectedKey && host.querySelector('.reply-option-card:not([hidden]) .reply-option-pronunciation').textContent === selectedText;
        const choiceFocus = document.activeElement.classList.contains('reply-choice') && document.activeElement.getAttribute('aria-pressed') === 'true';
        return {onlyOne,pressed,preserved,choiceFocus};
    })()`);
    assert.deepStrictEqual(selectionChecks, {onlyOne:true,pressed:true,preserved:true,choiceFocus:true});
    // Sonraki ekran kontrolleri dört seçenekli ilk durumu kullanır.
    await win.loadFile(fixturePath);
    await new Promise(resolve => setTimeout(resolve, 150));
    const designChecks = await win.webContents.executeJavaScript(`(() => {
        document.body.classList.add('controls-collapsed');
        const main = document.querySelector('.transcription-area').getBoundingClientRect();
        toggleControlPanel();
        const stableWidth = main.width === document.querySelector('.transcription-area').getBoundingClientRect().width;
        const close = document.querySelector('.settings-heading button');
        const closeBox = close.getBoundingClientRect();
        const closeVisible = closeBox.top >= 0 && closeBox.bottom <= innerHeight;
        close.focus(); close.click();
        const returned = document.activeElement.id === 'controlsToggleBtn';
        const box = document.querySelector('.ai-suggestion-box');
        const header = box.querySelector('.suggestion-toggle');
        const headerFits = header.getBoundingClientRect().bottom <= box.getBoundingClientRect().bottom;
        toggleSuggestionBox(box.id);
        const expanded = getComputedStyle(box.querySelector('.suggestion-content')).display !== 'none';
        toggleSuggestionBox(box.id);
        const details = document.querySelector('.history-disclosure');
        details.open = true;
        const filters = details.querySelector('.transcript-history-filters');
        const filtersVisible = filters.getBoundingClientRect().height > 0;
        details.open = false;
        return {stableWidth,returned,headerFits,expanded,filtersVisible,closeVisible};
    })()`);
    assert.deepStrictEqual(designChecks, {stableWidth:true,returned:true,headerFits:true,expanded:true,filtersVisible:true,closeVisible:true});
    const searchClear = await win.webContents.executeJavaScript(`(async () => {
        const input = document.getElementById('transcriptSearchInput');
        const originalFetch = window.fetch;
        let finish;
        window.fetch = () => new Promise(resolve => { finish = resolve; });
        input.value = 'önceki sorgu';
        input.dispatchEvent(new Event('input', {bubbles:true}));
        const clearVisible = !document.getElementById('transcriptSearchClear').hidden;
        const pending = searchFullTranscriptHistory(input.value);
        document.getElementById('transcriptSearchClear').click();
        finish({ok:true,json:async()=>({transcriptions:[{id:1,text:'Eski sonuç'}]})});
        await pending;
        window.fetch = originalFetch;
        return {clearVisible,empty:input.value === '',focused:document.activeElement === input,
            staleHidden:document.getElementById('transcriptSearchResults').style.display === 'none'};
    })()`);
    assert.deepStrictEqual(searchClear, {clearVisible:true,empty:true,focused:true,staleHidden:true});
    await win.webContents.executeJavaScript(`toggleLatencyDetails(); window.scrollTo(0, 0); document.querySelector('.control-panel').scrollTop = 0;`);

    for (const [width, height] of sizes) {
        win.setSize(width, height);
        await win.webContents.executeJavaScript(`document.body.classList.remove('controls-collapsed'); window.scrollTo(0, 0);`);
        await new Promise(resolve => setTimeout(resolve, 250));
        const geometry = await win.webContents.executeJavaScript(`({
            overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
            transcript: !!document.querySelector('.transcription-area'),
            cockpit: !!document.querySelector('.reply-cockpit'),
            buttons: [...document.querySelectorAll('#replyCockpitOptions .reply-option-card:not([hidden]) button, #replyCockpitOptions .reply-choice')].every(b=>b.getBoundingClientRect().width>0)
        })`);
        assert.strictEqual(geometry.overflow, false, width + 'px yatay tasma');
        assert(geometry.transcript && geometry.cockpit && geometry.buttons);
        const image = await win.webContents.capturePage();
        fs.writeFileSync(path.join(outputDir, `${width}x${height}-dark.png`), image.toPNG());
        // Gizlenen ayarlar dar ekranda ikinci bir sütun bırakmamalı.
        await win.webContents.executeJavaScript(`document.body.classList.add('controls-collapsed')`);
        const layout = await win.webContents.executeJavaScript(`(() => {
            const panel = document.querySelector('.transcription-area').getBoundingClientRect();
            const reply = document.querySelector('.reply-cockpit').getBoundingClientRect();
            const filters = document.querySelector('.transcript-history-filters');
            return {width: innerWidth, right: Math.max(panel.right, reply.right),
                stacked: reply.top >= panel.bottom,
                filtersFit: filters.scrollWidth <= filters.clientWidth};
        })()`);
        assert(layout.right <= layout.width, width + 'px kapalı ayarlarda taşma');
        assert(layout.filtersFit, width + 'px arama filtrelerinde taşma');
        if (layout.width <= 980) assert(layout.stacked, width + 'px tek sütun düzeni');
        await win.webContents.executeJavaScript(`window.scrollTo(0, 0)`);
        await new Promise(resolve => setTimeout(resolve, 250));
        fs.writeFileSync(path.join(outputDir, `${width}x${height}-focused.png`),
            (await win.webContents.capturePage()).toPNG());
        await win.webContents.executeJavaScript(`document.body.classList.remove('controls-collapsed')`);
    }

    win.setSize(1440, 900);
    await win.webContents.executeJavaScript(`document.body.classList.add('light-mode', 'controls-collapsed'); updateThemeButton(true)`);
    await new Promise(resolve => setTimeout(resolve, 500));
    fs.writeFileSync(path.join(outputDir, '1440x900-light.png'), (await win.webContents.capturePage()).toPNG());
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
    const readingFooter = await win.webContents.executeJavaScript(`(() => {
        const dialog = document.querySelector('.reading-dialog');
        dialog.scrollTop = dialog.scrollHeight;
        const close = dialog.querySelector('.reading-close-btn').getBoundingClientRect();
        const controls = dialog.querySelectorAll('.reading-audio-actions button');
        let slowRate = null;
        const originalSpeak = speakText;
        speakText = (_text, _lang, rate) => {slowRate = rate;};
        controls[1].click();
        speakText = originalSpeak;
        return {slowRate,closeVisible:close.top >= 0 && close.bottom <= innerHeight,
            audioVisible:controls[2].getBoundingClientRect().bottom <= innerHeight};
    })()`);
    assert.deepStrictEqual(readingFooter, {slowRate:0.65,closeVisible:true,audioVisible:true});
    const favoriteChecks = await win.webContents.executeJavaScript(`(() => {
        closeReadingMode();
        whisperStorage.setItem(FAVORITES_KEY, JSON.stringify([null, 3, {translation:7},
            {translation:'Merhaba',turkish:{bad:true}},
            {translation:'こんにちは',turkish:'İyi günler',romanized:'Konniçiva',lang:'ja'}]));
        renderFavorites();
        const sanitized = loadFavorites().length === 2 && loadFavorites()[0].turkish === '';
        document.getElementById('favoritesSearch').value = 'İYİ';
        renderFavorites();
        const filtered = document.querySelectorAll('#favoritesList .mini-card').length === 1;
        const deleteButton = document.querySelector('#favoritesList button[title="Kalıplardan sil"]');
        saveFavorite('Yeni kayıt','','','tr');
        deleteButton.click();
        const correctDelete = loadFavorites().map(f=>f.translation).join('|') === 'Yeni kayıt|Merhaba';
        deleteFavorite(-1);
        const invalidDeleteIgnored = loadFavorites().length === 2;
        document.getElementById('favoritesSearch').value = '';
        const options = [{translation:'こんにちは',turkish:'Merhaba',romanized:'Konniçiva',language:'ja'}];
        selectReplyTarget('regression','Odak testi',true);
        renderReplyCockpit('regression',options,'ja','Japonca',true);
        document.querySelector('[data-reply-action="save"]').click();
        const savedFromCard = loadFavorites()[0].romanized === 'Konniçiva';
        document.querySelector('[data-reply-action="listen"]').focus();
        renderReplyCockpit('regression',options,'ja','Japonca',false);
        const actionPreserved = document.activeElement.dataset.replyAction === 'listen';
        const opener = document.querySelector('.reply-read-button');
        opener.focus(); opener.click();
        renderReplyCockpit('regression',options,'ja','Japonca',false);
        closeReadingMode();
        const replacedFocus = !opener.isConnected && document.activeElement.classList.contains('reply-read-button');
        whisperStorage.removeItem(FAVORITES_KEY);
        return {sanitized,filtered,correctDelete,invalidDeleteIgnored,savedFromCard,actionPreserved,replacedFocus};
    })()`);
    assert.deepStrictEqual(favoriteChecks, {sanitized:true,filtered:true,correctDelete:true,
        invalidDeleteIgnored:true,savedFromCard:true,actionPreserved:true,replacedFocus:true});
    const translationChecks = await win.webContents.executeJavaScript(`(() => {
        addTranscription({id:999,text:'Translation status test',translation_status:'pending'},true);
        const item = document.querySelector('[data-transcription-id="999"]');
        const pending = item.querySelector('.translation-status-note')?.textContent.includes('sırada');
        addTranscription({id:999,text:'Translation status test',translation_status:'failed'},true);
        const failed = item.querySelector('.translation-status-note')?.textContent.includes('yeniden');
        updateTranscriptTranslationStatus(item,'skipped');
        const skipped = item.querySelector('.translation-status-note')?.textContent.includes('atlandı');
        appendInlineTranslationToItem(item,'Çeviri sonucu','TR');
        updateTranscriptTranslationStatus(item,'failed');
        const completed = !item.querySelector('.translation-status-note');
        return {pending,failed,skipped,completed};
    })()`);
    assert.deepStrictEqual(translationChecks, {pending:true,failed:true,skipped:true,completed:true});
    const toolsChecks = await win.webContents.executeJavaScript(`(async () => {
        const oldFetch = window.fetch;
        const input = document.getElementById('ownReplyText');
        const button = document.getElementById('ownReplyTranslate');
        document.getElementById('aiTargetLang').value = 'ja';
        document.getElementById('replyComposerPanel').open = true;
        input.value = ' ';
        await translateOwnReply();
        const validation = input.getAttribute('aria-invalid') === 'true' && document.activeElement === input;
        input.value = 'Biraz gecikeceğim.';
        let finish, requestBody, count = 0;
        window.fetch = (url, init) => { count++; requestBody = JSON.parse(init.body); return new Promise(resolve => {finish=resolve;}); };
        const pending = translateOwnReply();
        await translateOwnReply();
        const busy = button.disabled && count === 1 && requestBody.mode === 'translate_dual' && requestBody.target_lang === 'ja';
        finish({ok:true,json:async()=>({success:true,native:'少し遅れます。',turkish:input.value,romanized:'Sukoşi okuremas.'})});
        await pending;
        const success = document.querySelector('.reply-option-pronunciation').textContent === 'Sukoşi okuremas.' && !button.disabled && input.value === 'Biraz gecikeceğim.';
        window.fetch = async()=>{throw new Error('Bağlantı hatası');};
        await translateOwnReply();
        const failure = !button.disabled && input.value === 'Biraz gecikeceğim.' && document.getElementById('ownReplyStatus').textContent.includes('Bağlantı');
        window.fetch = () => new Promise(resolve => {finish=resolve;});
        const stale = translateOwnReply();
        selectReplyTarget('new-choice','Yeni seçim',true);
        renderReplyCockpit('new-choice',[{translation:'New',turkish:'Yeni',romanized:'Nyu'}],'en','İngilizce',false);
        finish({ok:true,json:async()=>({success:true,native:'Old',romanized:'Eski',turkish:'Eski'})});
        await stale;
        const staleIgnored = document.querySelector('.reply-option-pronunciation').textContent === 'Nyu';
        const beforeQuick = count;
        renderQuickPhrases();
        document.querySelector('.quick-phrase-choice').click();
        const quick = count === beforeQuick && document.querySelector('.reply-option-pronunciation').textContent === QUICK_PHRASES.ja[0].o;
        document.getElementById('aiTargetLang').value = 'fi'; renderQuickPhrases();
        const unavailable = !document.querySelector('.quick-phrase-choice') && document.getElementById('quickPhrasesList').textContent.includes('hazır kalıp yok');
        document.getElementById('aiTargetLang').value = 'ja'; renderQuickPhrases();
        const micCalls = [];
        window.fetch = async (url, init) => {micCalls.push(JSON.parse(init.body)); return {ok:true,json:async()=>({success:true,processing:micCalls.length>1})};};
        toggleOwnReplyMic(); await altPttCommandChain;
        const micActive = altPttHeld && document.getElementById('ownReplyMic').getAttribute('aria-pressed') === 'true';
        toggleOwnReplyMic(); await altPttCommandChain;
        const micStops = !altPttHeld && micCalls.length === 2 && micCalls[0].active && !micCalls[1].active && micCalls[0].recording_id === micCalls[1].recording_id;
        showOwnMicResult({success:true,recording_id:altPttRecordingId,id:123,original:'Merhaba',translation:'こんにちは',romanized:'Konniçiva',target_lang:'JA'});
        const micResult = document.querySelector('.reply-option-pronunciation').textContent === 'Konniçiva';
        document.getElementById('deviceSelect').innerHTML = '<option value="0">Test ses cihazı</option>';
        updateReadiness({model_loaded:true,model_name:'tiny',ai_key_status:'unverified'});
        const unverified = document.getElementById('readyAi').textContent.includes('Henüz doğrulanmadı') && document.getElementById('readinessSummary').textContent === '2/3 hazır';
        updateReadiness({ai_key_status:'valid'});
        const ready = document.getElementById('readinessSummary').textContent === '3/3 hazır';
        window.fetch = async()=>{throw new Error('offline');};
        await refreshReadiness();
        const offline = document.getElementById('readinessSummary').textContent.includes('başarısız') && !document.getElementById('readinessRefresh').disabled;
        window.fetch = oldFetch;
        return {validation,busy,success,failure,staleIgnored,quick,unavailable,micActive,micStops,micResult,unverified,ready,offline};
    })()`);
    assert(Object.values(toolsChecks).every(Boolean), JSON.stringify(toolsChecks));
    await win.loadFile(fixturePath);
    win.setSize(1440, 900);
    await win.webContents.executeJavaScript(`document.body.classList.add('controls-collapsed'); document.getElementById('cockpitLatencyDetails').hidden=true; document.getElementById('replyComposerPanel').open=true; document.getElementById('ownReplyText').value='Biraz gecikeceğim, beni bekler misin?'; renderQuickPhrases();`);
    await new Promise(resolve => setTimeout(resolve, 800));
    fs.writeFileSync(path.join(outputDir,'1440x900-composer.png'), (await win.webContents.capturePage()).toPNG());
    win.setSize(600, 800);
    await win.webContents.executeJavaScript(`document.body.classList.add('light-mode'); document.getElementById('replyCockpit').scrollIntoView();`);
    await new Promise(resolve => setTimeout(resolve, 800));
    const composerColors = await win.webContents.executeJavaScript(`({surface:getComputedStyle(document.getElementById('ownReplyText')).backgroundColor, text:getComputedStyle(document.getElementById('ownReplyText')).color})`);
    assert.strictEqual(composerColors.surface, 'rgb(245, 247, 250)');
    assert.strictEqual(composerColors.text, 'rgb(23, 27, 30)');
    fs.writeFileSync(path.join(outputDir,'600x800-composer-light.png'), (await win.webContents.capturePage()).toPNG());
    win.setSize(1440, 900);
    await win.webContents.executeJavaScript(`document.body.classList.remove('light-mode'); document.getElementById('replyComposerPanel').open=false; document.getElementById('quickPhrasesPanel').open=true; document.getElementById('readinessPanel').open=true; window.scrollTo(0,0);`);
    await new Promise(resolve => setTimeout(resolve, 800));
    fs.writeFileSync(path.join(outputDir,'1440x900-tools.png'), (await win.webContents.capturePage()).toPNG());
    const emptyHtml = fixtureHtml().replace(/<script>\s*window.fetch = async url[\s\S]*?<\/script><\/body>/, '</body>');
    const emptyPath = path.join(outputDir, 'empty.html');
    fs.writeFileSync(emptyPath, emptyHtml, 'utf8');
    await win.loadFile(emptyPath);
    win.setSize(1440, 900);
    await win.webContents.executeJavaScript(`whisperStorage.removeItem('controlsCollapsed'); document.body.classList.add('controls-collapsed'); document.body.classList.remove('light-mode'); window.scrollTo(0,0);`);
    await new Promise(resolve => setTimeout(resolve, 800));
    fs.writeFileSync(path.join(outputDir, '1440x900-empty.png'), (await win.webContents.capturePage()).toPNG());
    const setupOpens = await win.webContents.executeJavaScript(`(() => {
        document.getElementById('setupModel').click();
        return !document.body.classList.contains('controls-collapsed') && document.activeElement.id === 'modelLoadBtn';
    })()`);
    assert(setupOpens, 'Kurulum adımı kapalı ayarları açmalı ve hedefe odaklanmalı');
    await win.webContents.executeJavaScript(`document.querySelector('.control-panel').scrollTop = 0`);
    await new Promise(resolve => setTimeout(resolve, 250));
    fs.writeFileSync(path.join(outputDir, '1440x900-settings.png'), (await win.webContents.capturePage()).toPNG());
    // Dar ekranda cevap alanını da görünür konumda kaydet.
    await win.loadFile(fixturePath);
    win.setSize(600, 800);
    await win.webContents.executeJavaScript(`document.body.classList.add('controls-collapsed'); document.getElementById('replyCockpit').scrollIntoView();`);
    await new Promise(resolve => setTimeout(resolve, 300));
    fs.writeFileSync(path.join(outputDir, '600x800-reply.png'), (await win.webContents.capturePage()).toPNG());
    // Yardımcı pencere aynı renk tokenlarını kullanır; kapanış platform işidir.
    let overlay = fs.readFileSync(path.join(__dirname, 'templates', 'overlay.html'), 'utf8');
    overlay = overlay.replace('<script src="/static/socket.io.min.js"></script>', '<script>function io(){return {on(){}};}</script>');
    for (const name of ['runtime-safety.js', 'html-utils.js']) overlay = overlay.replace(`<script src="/static/${name}"></script>`, `<script>${fs.readFileSync(path.join(__dirname,'static',name),'utf8')}</script>`);
    overlay = overlay.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">', `<style>${fs.readFileSync(path.join(__dirname,'static','whisper-pro-theme.css'),'utf8')}</style>`).replace('{{ app_token|tojson }}','"fixture-token"');
    const overlayPath = path.join(outputDir, 'overlay.html');
    fs.writeFileSync(overlayPath, overlay);
    await win.loadFile(overlayPath);
    win.setSize(480, 520);
    await win.webContents.executeJavaScript(`document.body.classList.remove('light-mode'); renderTranscript({id:1,text:'会議のあと、駅で会えますか？',translation:'Toplantıdan sonra istasyonda buluşabilir miyiz?'});`);
    const overlayColor = await win.webContents.executeJavaScript(`getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()`);
    assert.strictEqual(overlayColor, '#7296ff');
    await new Promise(resolve => setTimeout(resolve, 250));
    fs.writeFileSync(path.join(outputDir, '480x520-overlay.png'), (await win.webContents.capturePage()).toPNG());
    win.close();
    console.log('Gercek Chromium Cockpit davranis ve gorsel testleri gecti:', outputDir);
    app.quit();
}).catch(error => { console.error(error); app.exit(1); });
