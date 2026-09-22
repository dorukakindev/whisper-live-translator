const {app, BrowserWindow} = require('electron');
const assert = require('assert');
const fs = require('fs');
const path = require('path');

// Capture yasam dongusu (frontend tarafi): sahte socket + fetch uzerinden
// start/stop/hata/eski-oturum/duplicate/yeniden-baglanma senaryolari.
// Ama node --check ile syntax dogrulanabilir; tam islem xvfb'de Electron'la.

const outputDir = path.join(__dirname, 'artifacts', 'capture-lifecycle');

function fixtureHtml() {
    let html = fs.readFileSync(path.join(__dirname, 'templates', 'index.html'), 'utf8');
    html = html.replace('<script src="/static/socket.io.min.js"></script>', '');
    html = html.replace('<script src="/static/runtime-safety.js"></script>',
        `<script>${fs.readFileSync(path.join(__dirname, 'static', 'runtime-safety.js'), 'utf8')}</script>`);
    for (const moduleName of ['html-utils.js', 'i18n.js', 'cockpit.js', 'live-flow.js',
                            'reading-mode.js', 'quick-phrases.js']) {
        html = html.replace(`<script src="/static/${moduleName}"></script>`,
            `<script>${fs.readFileSync(path.join(__dirname, 'static', moduleName), 'utf8')}</script>`);
    }
    html = html.replace('<link rel="stylesheet" href="/static/whisper-pro-theme.css">',
        `<style>${fs.readFileSync(path.join(__dirname, 'static', 'whisper-pro-theme.css'), 'utf8')}</style>`);
    html = html.replace('{{ app_token|tojson }}', '"fixture-token"');
    html = html.replace(/socket = io\([^)]*\);/,
        `socket = {connected:true, _events:{}, on(n,f){this._events[n]=f;}, emit(){}};`);
    html = html.replace('window.onload = async function () {', 'window.onload = async function () { return;');
    // Basit durumlu API sahtesi + cagri sayaci. startPayloadQueue her /api/start
    // cagrisinda siradaki yaniti dondurur; statusPayload /api/status icin.
    html = html.replace('</body>', `<script>
        window.__alerts = [];
        const _origShowAlert = showAlert;
        showAlert = (m, t) => { window.__alerts.push({m, t}); _origShowAlert(m, t); };
        window.__startQueue = [];
        window.__statusPayload = {capturing:false, model_loaded:true, instance_id:'fx-1',
            paused:false, session_id:null};
        window.fetch = async (url, opts) => {
            if (url === '/api/start') {
                return {ok:true, json:async()=> window.__deferredStart
                    ? await window.__deferredStart
                    : (window.__startQueue.shift() || {success:true, session_id:7})};
            }
            if (url === '/api/status') {
                return {ok:true, json:async()=> window.__statusPayload};
            }
            if (url.includes('/api/stats')) {
                return {ok:true, json:async()=> ({total_transcriptions:0,
                    latency:{}, performance:{audio_queue_size:0},
                    pipeline:{asr_active:false}})};
            }
            if (url === '/api/generate_ai_response') {
                return {ok:true, json:async()=> window.__aiDeferred
                    ? await window.__aiDeferred : {success:true, options:[]}};
            }
            return {ok:true, json:async()=> ({success:true})};
        };
        const devSel = document.getElementById('deviceSelect');
        devSel.innerHTML = '<option value="0">sahte-cihaz</option>';
        devSel.value = '0';
        _socketConnected = true;
        setupSocketListeners();  // window.onload stub'luydu; handler'lari elle bagla
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
    await new Promise(resolve => setTimeout(resolve, 200));
    const failures = [];
    const step = (name, ok, extra) => {
        if (!ok) failures.push(`${name}: ${JSON.stringify(extra)}`);
        console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`);
    };
    const run = js => win.webContents.executeJavaScript(js);

    // Yardimci: tek seferde kontrollerin tamamini oku
    const stateJs = `(() => ({
        capturing: isCapturing, paused: isPaused,
        sessionId: (typeof _captureSessionId === 'undefined' ? null : _captureSessionId),
        startDisabled: document.getElementById('startBtn').disabled,
        stopDisabled: document.getElementById('stopBtn').disabled,
        deviceDisabled: document.getElementById('deviceSelect').disabled,
        pauseDisabled: document.getElementById('pauseBtn').disabled,
        flushDisabled: document.getElementById('flushBtn').disabled,
        alertCount: window.__alerts.length,
        statusText: document.getElementById('statusText')?.textContent || '',
        timerActive: !!timerInterval
    }))()`;

    // ── 1) normal start -> normal stop (kullanici Durdur) ──────────────
    let s = await run(`(async()=>{
        window.__startQueue = [{success:true, session_id:7}];
        await startCapture();
        return ${stateJs};
    })()`);
    step('1a /api/start success -> capturing UI', s.capturing === true
        && s.sessionId === 7 && s.startDisabled && !s.stopDisabled
        && s.deviceDisabled && !s.pauseDisabled, s);

    s = await run(`(async()=>{ await stopCapture(); return ${stateJs}; })()`);
    step('1b stopCapture -> full UI reset', s.capturing === false
        && s.sessionId === null && s.stopDisabled && !s.deviceDisabled
        && s.pauseDisabled && s.flushDisabled && !s.timerActive, s);

    // ── 2/4) backend thread olimu: capture_stopped tek basina tum durumu
    //         sifirlamali (ANA HATA: eskiden sadece status+timer sifirlaniyordu) ──
    s = await run(`(async()=>{
        window.__startQueue = [{success:true, session_id:9}];
        await startCapture();
        socket._events.capture_stopped({status:'stopped', session_id:9, reason:'error'});
        return ${stateJs};
    })()`);
    step('2 capture_stopped(reason=error) -> full reset', s.capturing === false
        && s.sessionId === null && s.stopDisabled && !s.startDisabled
        && !s.deviceDisabled && s.pauseDisabled && s.flushDisabled
        && !s.timerActive, s);

    // ── 3) /api/start basarisiz -> capturing olmamali ──────────────────
    s = await run(`(async()=>{
        window.__startQueue = [{success:false, error:'Ses cihazı açılamadı'}];
        const alertsBefore = window.__alerts.length;
        await startCapture();
        const st = ${stateJs};
        return {...st, newAlerts: window.__alerts.length - alertsBefore};
    })()`);
    step('3 /api/start failure -> not capturing + alert', s.capturing === false
        && !s.startDisabled && s.newAlerts === 1, s);

    // ── 7) eski oturumun gecikmis olayi yeni oturumu kapatmamali ──────
    s = await run(`(async()=>{
        window.__startQueue = [{success:true, session_id:11}];
        await startCapture();
        socket._events.capture_stopped({status:'stopped', session_id:5, reason:'stopped'});
        socket._events.capture_started({session_id:5, device:'eski'});
        return ${stateJs};
    })()`);
    step('7 stale session events ignored', s.capturing === true
        && s.sessionId === 11 && !s.stopDisabled, s);

    // ── 9+10) guncel oturumun stopped'i + duplicate ayni olay ─────────
    s = await run(`(()=>{
        const alertsBefore = window.__alerts.length;
        socket._events.capture_stopped({status:'stopped', session_id:11, reason:'stopped'});
        socket._events.capture_stopped({status:'stopped', session_id:11, reason:'stopped'});
        const st = ${stateJs};
        return {...st, newAlerts: window.__alerts.length - alertsBefore,
            alerts: window.__alerts.slice(alertsBefore).map(a=>a.m)};
    })()`);
    step('9/10 capture_stopped resets + duplicate alerts once', s.capturing === false
        && s.sessionId === null && s.newAlerts === 1, s);

    // ── 10b) bosta iken gelen capture_stopped bildirim uretmez ─────────
    s = await run(`(()=>{
        const alertsBefore = window.__alerts.length;
        socket._events.capture_stopped({status:'stopped', session_id:3, reason:'stopped'});
        return {alerts: window.__alerts.length - alertsBefore};
    })()`);
    step('10b idle capture_stopped -> no alert', s.alerts === 0, s);

    // ── 8) yeniden baglanma: backend yakalamiyor -> uzlasma ────────────
    s = await run(`(async()=>{
        window.__startQueue = [{success:true, session_id:13}];
        await startCapture();
        window.__statusPayload = {capturing:false, model_loaded:true,
            instance_id:'fx-2', paused:false, session_id:null};
        await resyncAfterReconnect();
        return ${stateJs};
    })()`);
    step('8 resync when backend idle -> reset', s.capturing === false
        && s.sessionId === null && !s.startDisabled && s.stopDisabled, s);

    // ── 8b) resync: backend hala yakaliyor -> evlat edinme ────────────
    s = await run(`(async()=>{
        window.__statusPayload = {capturing:true, model_loaded:true,
            instance_id:'fx-1', paused:false, session_id:21};
        await resyncAfterReconnect();
        return ${stateJs};
    })()`);
    step('8b resync when backend capturing -> adopt session', s.capturing === true
        && s.sessionId === 21 && !s.stopDisabled, s);

    // ── 5) Durdur ile eszamanli backend olimu (iki yol tek noktadan) ───
    s = await run(`(async()=>{
        window.__statusPayload = {capturing:false, model_loaded:true,
            instance_id:'fx-1', paused:false, session_id:null};
        const alertsBefore = window.__alerts.length;
        // stopCapture + capture_stopped eszamanli: ikisi de endCaptureSession'dan gecmeli
        const p = stopCapture();
        socket._events.capture_stopped({status:'stopped', session_id:21, reason:'error'});
        await p;
        const st = ${stateJs};
        return {...st, newAlerts: window.__alerts.length - alertsBefore};
    })()`);
    step('5 stop + backend death same instant -> single cleanup', s.capturing === false
        && s.sessionId === null && s.stopDisabled, s);

    // ── 2b) socket 'stopped' yanit'tan once gelirse (hazir->aninda olum)
    //        success yaniti sahte 'dinleniyor'a donmemeli ─────────────────
    s = await run(`(async()=>{
        window.__deferredStart = new Promise(r=>{window.__resolveStart = r;});
        const pending = startCapture();
        await new Promise(r=>setTimeout(r,0));
        socket._events.capture_stopped({status:'stopped', session_id:31, reason:'error'});
        window.__resolveStart({success:true, session_id:31});
        window.__deferredStart = null;
        await pending;
        return ${stateJs};
    })()`);
    step('2b stopped-before-response -> no false listening', s.capturing === false
        && s.sessionId === null && s.stopDisabled, s);

    // ── R1) backend restart: eski instance'in ended-id'si yeni backend'in
    //         ayni session_id'sini yanlislikla oldurmemeli ──────────────────
    s = await run(`(async()=>{
        // fx-1'de oturum 1 ac + kapandi (ended kaydi olustu)
        window.__statusPayload = {capturing:false, model_loaded:true,
            instance_id:'fx-1', paused:false, session_id:null};
        await resyncAfterReconnect();
        window.__startQueue = [{success:true, session_id:1}];
        await startCapture();
        socket._events.capture_stopped({status:'stopped', session_id:1, reason:'stopped'});
        // Backend restart: instance fx-2
        window.__statusPayload = {capturing:false, model_loaded:true,
            instance_id:'fx-2', paused:false, session_id:null};
        await resyncAfterReconnect();
        // Yeni backend session_id'yi 1'den baslatti
        window.__startQueue = [{success:true, session_id:1}];
        const alertsBefore = window.__alerts.length;
        await startCapture();
        const st = ${stateJs};
        return {...st,
            errAlerts: window.__alerts.slice(alertsBefore)
                .filter(a=>a.t==='error').map(a=>a.m)};
    })()`);
    step('R1 restarted backend session reuse ok', s.capturing === true
        && s.sessionId === 1 && s.errAlerts.length === 0, s);

    // ── R2) pending start sirasinda eski oturumun gecikmis stopped'i ───────
    s = await run(`(async()=>{
        // Oturum 5 acti -> kullanici Durdur (backend'in stopped'i gecikecek)
        window.__startQueue = [{success:true, session_id:5}];
        await startCapture();
        await stopCapture();
        // Yeni start pending; eski oturumun stopped'i simdi gelir
        window.__deferredStart = new Promise(r=>{window.__resolveStart=r;});
        const pending = startCapture();
        await new Promise(r=>setTimeout(r,0));
        socket._events.capture_stopped({status:'stopped', session_id:5, reason:'stopped'});
        window.__resolveStart({success:true, session_id:6});
        window.__deferredStart = null;
        await pending;
        return ${stateJs};
    })()`);
    step('R2 stale stopped cannot cancel pending start', s.capturing === true
        && s.sessionId === 6 && !s.stopDisabled, s);

    // ── P1) ptt_mic_result broadcast: baska istemcinin kaydi bu sayfanin
    //         listesine ve uyarilarina sizmamali (recording_id sahipligi) ──
    s = await run(`(()=>{
        const itemsBefore = document.querySelectorAll('.transcription-item').length;
        const alertsBefore = window.__alerts.length;
        socket._events.ptt_mic_result({recording_id:'baska-uuid-1', success:true,
            id:901, original:'yabanci metin', translation:'foreign text',
            target_lang:'EN', romanized:'foreyn tekst', timestamp:'12:00:01'});
        socket._events.ptt_mic_result({recording_id:'baska-uuid-2', success:false,
            error:'uzak istemci hatasi'});
        return {items: document.querySelectorAll('.transcription-item').length - itemsBefore,
            newAlerts: window.__alerts.length - alertsBefore};
    })()`);
    step('P1a foreign ptt_mic_result ignored', s.items === 0 && s.newAlerts === 0, s);

    // Kendi kaydimizin sonucu ise islenmeli (sahiplik eslesmesi gecerli)
    s = await run(`(()=>{
        altPttRecordingId = 'benim-kayit-uuid';
        trackOwnMicId(altPttRecordingId);  // startOwnReplyMic'in yaptigi izleme
        const itemsBefore = document.querySelectorAll('.transcription-item').length;
        socket._events.ptt_mic_result({recording_id:'benim-kayit-uuid', success:true,
            id:902, original:'merhaba', translation:'hello',
            target_lang:'EN', romanized:'he-lo', timestamp:'12:00:02'});
        return {items: document.querySelectorAll('.transcription-item').length - itemsBefore,
            has9002: !!document.querySelector('[data-transcription-id="902"]')};
    })()`);
    step('P1b own ptt_mic_result renders', s.items === 1 && s.has9002, s);

    // ── P1c) ayni sayfanin iki kaydi: backend _mic_job_slots=2 oldugu icin
    //         A islenirken B baslayabilir. A'nin gec gelen sonucu bu sayfaya
    //         ait -> satir gorunmeli; yabanci istemci yine reddedilmeli.
    //         Iptal edilen B'nin sonucu ise artik kabul edilmemeli. ─────────
    s = await run(`(async()=>{
        // A baslat -> birak (sunucuda islemeye girdi)
        startOwnReplyMic();
        const idA = altPttRecordingId;
        await new Promise(r=>setTimeout(r,0));
        finishAltPtt();  // discard=false: sonuc bekleniyor -> idA pending kalir
        await new Promise(r=>setTimeout(r,0));
        // A islenirken B basla -> aktif kayit B oldu
        startOwnReplyMic();
        const idB = altPttRecordingId;
        await new Promise(r=>setTimeout(r,0));
        const itemsBefore = document.querySelectorAll('.transcription-item').length;
        const alertsBefore = window.__alerts.length;
        // A'nin gec sonucu: bu sayfaya ait -> SATIR olusmali
        socket._events.ptt_mic_result({recording_id:idA, success:true,
            id:904, original:'a sesi', translation:'a sound',
            target_lang:'EN', romanized:'ey-saund', timestamp:'12:00:04'});
        // yabanci istemcinin sonucu yine reddedilmeli
        socket._events.ptt_mic_result({recording_id:'yabanci-uuid', success:true,
            id:905, original:'yabanci', translation:'foreign', target_lang:'EN'});
        // B'yi iptal et (discard): terminal sonucu artik kabul edilmemeli
        finishAltPtt(true);
        await new Promise(r=>setTimeout(r,0));
        socket._events.ptt_mic_result({recording_id:idB, success:true,
            id:906, original:'b sesi', translation:'b sound', target_lang:'EN'});
        const pending = (typeof ownMicPendingIds === 'undefined')
            ? null : id => ownMicPendingIds.has(id);
        return {idA, idB,
            hasA: !!document.querySelector('[data-transcription-id="904"]'),
            hasForeign: !!document.querySelector('[data-transcription-id="905"]'),
            hasDiscardedB: !!document.querySelector('[data-transcription-id="906"]'),
            pendingA: pending === null ? null : pending(idA),
            pendingB: pending === null ? null : pending(idB),
            pendingForeign: pending === null ? null : pending('yabanci-uuid'),
            items: document.querySelectorAll('.transcription-item').length - itemsBefore,
            newAlerts: window.__alerts.length - alertsBefore};
    })()`);
    step('P1c late own result renders; foreign + discarded still rejected',
        s.hasA === true && s.hasForeign === false && s.hasDiscardedB === false
        && s.items === 1 && s.pendingA === false && s.pendingB === false
        && s.pendingForeign === false, s);

    // ── P1d) hizli birakma + gec basarisiz start: /api/ptt_mic 409 doner.
    //         Kullanici biraktigi icin altPttHeld=false -> catch'teki
    //         finishAltPtt(true) erken cikar; basarisiz start'in id'si
    //         yine de pending'den silinmeli (yoksa cap 4 gercek kayitlari evir). ──
    s = await run(`(async()=>{
        const origFetch = window.fetch;
        window.fetch = (url, opts) => {
            if (url === '/api/ptt_mic') {
                const body = JSON.parse(opts.body);
                if (body.active === true) {
                    return Promise.resolve({ok:false, status:409,
                        json:async()=>({success:false, error:'catisma'})});
                }
            }
            return origFetch(url, opts);
        };
        startOwnReplyMic();
        const idA = altPttRecordingId;
        finishAltPtt();            // kullanici hemen birakti (discard=false)
        await new Promise(r=>setTimeout(r,20));  // komut zinciri + 409 islesin
        window.fetch = origFetch;
        const pending = (typeof ownMicPendingIds === 'undefined') ? null
            : id => ownMicPendingIds.has(id);
        return {idA, held: altPttHeld,
            pendingA: pending === null ? null : pending(idA)};
    })()`);
    step('P1d failed start after quick release untracks id',
        s.held === false && s.pendingA === false, s);

    // ── P1e) A islenirken B'nin start'i basarisiz: yalniz B'nin id'si silinir;
    //         A pending'de kalir ve sonucu satir olarak gorunur. ─────────────
    s = await run(`(async()=>{
        const origFetch = window.fetch;
        let startCalls = 0;
        window.fetch = (url, opts) => {
            if (url === '/api/ptt_mic') {
                const body = JSON.parse(opts.body);
                if (body.active === true) {
                    startCalls++;
                    if (startCalls >= 2) {  // B'nin start'i basarisiz
                        return Promise.resolve({ok:false, status:409,
                            json:async()=>({success:false, error:'slot dolu'})});
                    }
                }
            }
            return origFetch(url, opts);
        };
        // A: basarili start + birak -> sunucuda islemede (pending)
        startOwnReplyMic();
        const idA = altPttRecordingId;
        await new Promise(r=>setTimeout(r,10));
        finishAltPtt();
        await new Promise(r=>setTimeout(r,10));
        // B: start basarisiz
        startOwnReplyMic();
        const idB = altPttRecordingId;
        await new Promise(r=>setTimeout(r,20));
        window.fetch = origFetch;
        const itemsBefore = document.querySelectorAll('.transcription-item').length;
        socket._events.ptt_mic_result({recording_id:idA, success:true,
            id:907, original:'a sonuc', translation:'a result', target_lang:'EN'});
        // B'nin hic kabul edilmeyen kaydina sonuc gelirse reddedilmeli
        socket._events.ptt_mic_result({recording_id:idB, success:true,
            id:908, original:'b sonuc', translation:'b result', target_lang:'EN'});
        const pending = (typeof ownMicPendingIds === 'undefined') ? null
            : id => ownMicPendingIds.has(id);
        return {idA, idB,
            hasA: !!document.querySelector('[data-transcription-id="907"]'),
            hasB: !!document.querySelector('[data-transcription-id="908"]'),
            pendingA: pending === null ? null : pending(idA),
            pendingB: pending === null ? null : pending(idB),
            items: document.querySelectorAll('.transcription-item').length - itemsBefore};
    })()`);
    step('P1e failed B start cannot evict pending A; A still renders',
        s.hasA === true && s.hasB === false && s.items === 1
        && s.pendingA === false && s.pendingB === false, s);

    // ── P4) satir silindikten sonra gec gelen AI/ceviri yaniti satiri
    //         geri getirmemeli (renderAiResult eksik-elemanda erken doner) ──
    s = await run(`(async()=>{
        socket._events.new_transcription({id:903, text:'satir dokuz yuz uc',
            model_language:'EN', timestamp:'12:00:03', instance_id:'fx-1'});
        const row = document.querySelector('[data-transcription-id="903"]');
        const btn = row ? row.querySelector('.ai-translate-btn') : null;
        if (!row || !btn) return {missing:true};
        transcriptionTexts['903'] = 'satir dokuz yuz uc';
        window.__aiDeferred = new Promise(r=>{window.__resolveAi = r;});
        getAIResponseById(903, 'translate', btn);
        await new Promise(r=>setTimeout(r,0));
        // Satir fetch havada iken siliniyor (kullanici Temizle/budama)
        row.remove();
        window.__resolveAi({success:true, translation:'cevirilmis',
            detected_lang:'en', options:[]});
        await new Promise(r=>setTimeout(r,10));
        return {resurrected: !!document.querySelector('[data-transcription-id="903"]'),
            suggestionBox: !!document.getElementById('ai-result-903')};
    })()`);
    step('P4 late AI result cannot resurrect removed row',
        !s.missing && !s.resurrected && !s.suggestionBox, s);

    // ── P6a) uzun gorusme: 130 transkriptte DOM 100'e budanir, metin haritasi
    //         kilit-adimda temizlenir, budanmis id tekrar eklenemez ──────────
    s = await run(`(()=>{
        for (let i = 1000; i < 1130; i++) {
            socket._events.new_transcription({id:i, text:'uzun gorusme satiri ' + i,
                model_language:'EN', timestamp:'12:01:00', instance_id:'fx-1'});
        }
        const items = document.querySelectorAll('.transcription-item').length;
        const texts = Object.keys(transcriptionTexts).map(Number);
        const keptRange = texts.filter(x => x >= 1000);
        const minKept = Math.min(...keptRange);
        // budanmis eski id yeniden gelirse reddedilmeli
        const before = document.querySelectorAll('.transcription-item').length;
        socket._events.new_transcription({id:1005, text:'budanmis geri geldi',
            model_language:'EN', timestamp:'12:01:01', instance_id:'fx-1'});
        return {items, keptCount: keptRange.length, minKept,
            hasOldTexts: texts.some(x => x < 1000),
            rejected: document.querySelectorAll('.transcription-item').length === before};
    })()`);
    // (902/903 metinleri bilincli secimler oldugu icin haritada kalabilir;
    //  yeni akisin 1000-1129 araligi tam 100 elemanla, en eski 1030'dan baslamali)
    step('P6a 130 transcripts -> DOM pruned + map synced', s.items === 100
        && s.keptCount === 100 && s.minKept === 1030 && s.rejected, s);

    // ── P6b) dil + tema degisimi hata uretmeden calisir ─────────────────
    s = await run(`(()=>{
        const errs = [];
        try {
            window.whisperI18n.setLanguage('tr');
            const trLabel = document.documentElement.dataset.uiLang;
            window.whisperI18n.setLanguage('en');
            const enLabel = document.documentElement.dataset.uiLang;
            return {trLabel, enLabel};
        } catch (e) { return {err: String(e)}; }
    })()`);
    step('P6b ui language switch', s.trLabel === 'tr' && s.enLabel === 'en', s);

    s = await run(`(()=>{
        try {
            const before = document.body.classList.contains('light-mode');
            toggleTheme();
            const mid = document.body.classList.contains('light-mode');
            const stored = whisperStorage.getItem('theme');
            toggleTheme();
            return {before, mid, stored, restored:
                document.body.classList.contains('light-mode')};
        } catch (e) { return {err: String(e)}; }
    })()`);
    step('P6c theme toggle roundtrip', s.before === false && s.mid === true
        && s.stored === 'light' && s.restored === false, s);

    // ── P6d) arama/filtre: gecmis sorgusu sonuc kartini render eder ─────
    s = await run(`(async()=>{
        const keep = window.fetch;
        window.fetch = async (url, opts) => {
            if (String(url).startsWith('/api/transcriptions')) {
                return {ok:true, json:async()=>({transcriptions:[
                    {id:1129, text:'uzun gorusme satiri 1129',
                     date:'2026-09-22', timestamp:'12:01'}]})};
            }
            return keep(url, opts);
        };
        await searchFullTranscriptHistory('1129');
        const box = document.getElementById('transcriptSearchResults');
        const shown = box.style.display !== 'none'
            && box.textContent.includes('1129');
        window.fetch = keep;
        return {shown};
    })()`);
    step('P6d history search renders match card', s.shown === true, s);

    // ── P8) XSS: zararli icerikli transkript/ceviri DOM'da sadece metin ──
    s = await run(`(()=>{
        window.__xssFired = false;
        window.__xss = () => { window.__xssFired = true; };
        socket._events.new_transcription({id:2000,
            text:'<img src=x onerror=__xss()><b>koyu</b>',
            translation:'<script>__xss()<\/script><i>it</i>',
            model_language:'EN', timestamp:'12:05:00', instance_id:'fx-1'});
        const item = document.querySelector('[data-transcription-id="2000"]');
        return {fired: window.__xssFired,
            img: !!document.querySelector('img[src=x]'),
            script: !!item && !!item.querySelector('script'),
            textKept: !!item && item.textContent.includes('koyu')};
    })()`);
    step('P8 xss payload stays inert', s.fired === false && s.img === false
        && s.script === false && s.textKept === true, s);

    await win.webContents.executeJavaScript('void 0');
    if (failures.length) {
        console.error('BASARISIZ:', failures.join(' | '));
        app.exit(1);
    } else {
        console.log('TUM CAPTURE-LIFECYCLE TESTLERI GECTI');
        app.exit(0);
    }
});
