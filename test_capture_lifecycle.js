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

    await win.webContents.executeJavaScript('void 0');
    if (failures.length) {
        console.error('BASARISIZ:', failures.join(' | '));
        app.exit(1);
    } else {
        console.log('TUM CAPTURE-LIFECYCLE TESTLERI GECTI');
        app.exit(0);
    }
});
