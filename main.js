const { app, BrowserWindow, Menu, Tray, dialog, globalShortcut, ipcMain, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const crypto = require('crypto');
const {
    isOwnedWhisperBackend,
    isExpectedBackendResponse,
    listeningPidFromNetstat,
    restrictWindowNavigation,
} = require('./main_helpers');

// Donanım hızlandırmayı kapat (GPU/CUDA çakışmalarını önlemek için)
app.disableHardwareAcceleration();

// Ana süreç çökme yakalayıcıları
process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception in Main Process:', err);
    // app.exit(1) 'will-quit'i TETIKLEMEZ; Python child'i once dogrudan oldur
    // (port'u henuz acmamis olabilir -> port-bazli temizlik onu kaciririr).
    killChildPython();
    killOrphanedPythonProcesses();
    app.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection in Main Process at:', promise, 'reason:', reason);
});

let store;
try {
    const Store = require('electron-store');
    store = new Store();
} catch (e) {
    console.warn('electron-store not available:', e.message);
    store = null;
}

let mainWindow;
let overlayWindow;
let overlayLocked = false;
let overlayLockShortcut = false;

function setOverlayLocked(locked) {
    if (!overlayWindow || overlayWindow.isDestroyed()) return false;
    // Kilit kısayolu alınamadıysa fareyi kilitleme; kullanıcı çıkışsız kalmasın.
    if (locked && !overlayLockShortcut) return false;
    overlayLocked = Boolean(locked);
    overlayWindow.setIgnoreMouseEvents(overlayLocked, {forward: true});
    overlayWindow.setFocusable(!overlayLocked);
    overlayWindow.webContents.send('overlay-state', {locked: overlayLocked, lockShortcut: overlayLockShortcut});
    return true;
}

ipcMain.handle('overlay-control', (event, action) => {
    const sender = event.sender;
    if (![mainWindow?.webContents, overlayWindow?.webContents].includes(sender)
            || event.senderFrame !== sender.mainFrame) return {success: false};
    if (action === 'open') { createOverlayWindow(); return {success: Boolean(overlayWindow)}; }
    if (action === 'lock') return {success: setOverlayLocked(!overlayLocked), locked: overlayLocked};
    if (action === 'close' && overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.close();
    return {success: true, locked: overlayLocked, lockShortcut: overlayLockShortcut};
});
let pythonProcess;
let tray;
let serverReady = false;
let isQuitting = false;
let pythonRestartCount = 0;   // crash-restart sonsuz dongusunu sinirla
let serverReadyRetries = 0;   // checkServerReady sayaci (fonksiyon disinda; sifirlanmasin)
let activeBackendNonce = null;
let backendStableTimer = null;
let globalPttEnabled = false; // opt-in, varsayilan KAPALI (bkz. setGlobalPttEnabled)
let globalPttActive = false;  // toggle durumu: PTT su an acik mi
const APP_TOKEN = crypto.randomBytes(32).toString('hex');

const isDev = (process.env.DEBUG || '').trim() === '*';
const isMac = process.platform === 'darwin';
function readDotEnvValue(name) {
    // Backend python-dotenv ile ayni .env dosyasini okur. Electron PORT'u
    // yalniz process.env'den alirsa .env'deki farkli portta iki taraf ayrisir.
    try {
        const fs = require('fs');
        const envPath = path.join(__dirname, '.env');
        if (!fs.existsSync(envPath)) return '';
        const line = fs.readFileSync(envPath, 'utf8')
            .split(/\r?\n/)
            .find((entry) => entry.trim().startsWith(`${name}=`));
        if (!line) return '';
        return line.slice(line.indexOf('=') + 1).trim().replace(/^['"]|['"]$/g, '');
    } catch (e) {
        return '';
    }
}
const configuredPort = process.env.PORT || readDotEnvValue('PORT') || '5000';
const requestedPort = Number.parseInt(configuredPort, 10);
const PORT = Number.isInteger(requestedPort) && requestedPort >= 1 && requestedPort <= 65535
    ? requestedPort
    : 5000;
if (String(PORT) !== String(configuredPort)) {
    console.warn(`Gecersiz PORT=${configuredPort}; 5000 kullaniliyor.`);
}

function killOrphanedPythonProcesses() {
    const { execSync } = require('child_process');
    let safeToStart = true;
    try {
        const cmd = process.platform === 'win32' 
            ? `netstat -ano | findstr :${PORT}`
            : `lsof -i :${PORT} -t`;
        
        const output = execSync(cmd).toString().trim();
        if (output) {
            console.log(`Port ${PORT} is in use. Cleaning up...`);
            if (process.platform === 'win32') {
                const lines = output.split('\n').map(line => line.trim()).filter(Boolean);
                for (const line of lines) {
                    const pid = listeningPidFromNetstat(line, PORT);
                    if (!pid) continue;
                    // Yalniz python surecini oldur: alakasiz bir uygulama 5000'i
                    // tutuyorsa ASLA dokunma (yanlis surec oldurme riskini onler).
                    let image = '';
                    try {
                        image = execSync(`tasklist /fi "PID eq ${pid}" /nh /fo csv`).toString().toLowerCase();
                    } catch (e) { image = ''; }
                    if (!image.includes('python')) {
                        console.warn(`Port ${PORT} python disi bir surec (${pid}) tarafindan tutuluyor; oldurulmuyor.`);
                        safeToStart = false;
                        continue;
                    }
                    let commandLine = '';
                    try {
                        commandLine = execSync(
                            `powershell.exe -NoProfile -Command "(Get-CimInstance Win32_Process -Filter 'ProcessId = ${pid}').CommandLine"`
                        ).toString().trim();
                    } catch (e) { commandLine = ''; }
                    if (!isOwnedWhisperBackend(commandLine, __dirname)) {
                        console.warn(`Port ${PORT} yabanci bir Python sureci (${pid}) tarafindan tutuluyor; oldurulmuyor.`);
                        safeToStart = false;
                        continue;
                    }
                    console.log(`Killing python process ${pid} listening on port ${PORT}`);
                    execSync(`taskkill /pid ${pid} /f /t`);
                }
            } else {
                const pids = output.split('\n').map(p => p.trim()).filter(p => /^\d+$/.test(p) && p !== '0');
                for (const pid of pids) {
                    let commandLine = '';
                    try { commandLine = execSync(`ps -p ${pid} -o command=`).toString().trim(); } catch (e) { commandLine = ''; }
                    if (!isOwnedWhisperBackend(commandLine, __dirname)) {
                        console.warn(`Port ${PORT} yabanci bir surec (${pid}) tarafindan tutuluyor; oldurulmuyor.`);
                        safeToStart = false;
                        continue;
                    }
                    console.log(`Killing Whisper python process ${pid} listening on port ${PORT}`);
                    execSync(`kill -9 ${pid}`);
                }
            }
        }
    } catch (e) {
        // Port is not in use or netstat failed, ignore
    }
    return safeToStart;
}

function killChildPython() {
    // Spawn ettigimiz Python child'ini DOGRUDAN oldur (port-bazli temizlikten farkli:
    // child portu henuz acmamis olsa bile yakalar). will-quit ve uncaughtException paylasir.
    if (!pythonProcess || !pythonProcess.pid) return;
    try {
        if (process.platform === 'win32') {
            const { spawnSync } = require('child_process');
            spawnSync('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t']);
        } else {
            pythonProcess.kill('SIGTERM');
        }
    } catch (e) {
        console.error('Error killing child Python:', e);
    }
}

let cachedPythonCommand = null;
function getPythonCommand() {
    const fs = require('fs');
    const { execFileSync } = require('child_process');
    if (cachedPythonCommand) return cachedPythonCommand;
    const requiredImports = "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ('flask','flask_socketio','webrtcvad','pyaudiowpatch','numpy','scipy','requests','faster_whisper')) else 1)";
    const usabilityCache = new Map();
    const isUsablePython = (cmd) => {
        if (usabilityCache.has(cmd)) return usabilityCache.get(cmd);
        try {
            execFileSync(cmd, ['-c', requiredImports], { stdio: 'ignore', timeout: 5000 });
            cachedPythonCommand = cmd;
            usabilityCache.set(cmd, true);
            return true;
        } catch (e) {
            usabilityCache.set(cmd, false);
            return false;
        }
    };

    // Acikca verilen Python her seyden once gelir.
    const explicitPython = process.env.WHISPER_PYTHON;
    if (explicitPython && fs.existsSync(explicitPython) && isUsablePython(explicitPython)) {
        return explicitPython;
    }

    // Gelistirme kokundeki venv'i ve dist/resources/app'ten yukariya dogru
    // cikarken bulunabilecek proje venv'ini ara. Boylece repo icinde uretilen
    // portable paket, bagimliliklari eksik global Python'a yanlislikla dusmez.
    const searchRoots = [];
    let searchDir = __dirname;
    for (let depth = 0; depth < 6; depth += 1) {
        searchRoots.push(searchDir);
        const parent = path.dirname(searchDir);
        if (parent === searchDir) break;
        searchDir = parent;
    }
    const venvCandidates = [];
    for (const root of searchRoots) {
        venvCandidates.push(
            path.join(root, '.venv', 'Scripts', 'python.exe'),
            path.join(root, '.venv', 'bin', 'python'),
            path.join(root, 'venv', 'Scripts', 'python.exe'),
            path.join(root, 'venv', 'bin', 'python'),
        );
    }
    for (const p of venvCandidates) {
        try {
            if (fs.existsSync(p) && isUsablePython(p)) return p;
        } catch (e) { /* yok say */ }
    }

    // PATH'te yalniz surumu degil, uygulamanin temel bagimliliklarini da dogrula.
    for (const cmd of ['python', 'python3', 'py']) {
        if (isUsablePython(cmd)) return cmd;
    }
    return null;
}

function createWindow() {
    const savedWindowState = store ? store.get('windowState', {
        width: 1400,
        height: 900,
        x: undefined,
        y: undefined
    }) : {
        width: 1400,
        height: 900,
        x: undefined,
        y: undefined
    };

    mainWindow = new BrowserWindow({
        ...savedWindowState,
        minWidth: 800,
        minHeight: 600,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        icon: path.join(__dirname, 'assets', 'icon.ico'),
        show: false
    });

    restrictWindowNavigation(mainWindow.webContents, `http://localhost:${PORT}`);

    // Save window state on close
    mainWindow.on('close', (event) => {
        // Tray varsa kapatma X'i pencereyi tepsiye gizler (uygulama arka planda
        // calismaya devam eder). Tray ikonu yuklenemediyse (createTray() basarisiz
        // olursa 'tray' hic atanmaz, bkz. asagidaki 'minimize' handler'iyla ayni
        // kontrol) gizlemek pencereyi KALICI OLARAK kaybettirir — geri getirecek
        // hicbir yol kalmaz. Bu durumda normal kapanisa izin ver.
        if (!isQuitting && tray) {
            event.preventDefault();
            mainWindow.hide();
        } else if (!isQuitting) {
            isQuitting = true;
        }
        if (store) {
            store.set('windowState', {
                width: mainWindow.getBounds().width,
                height: mainWindow.getBounds().height,
                x: mainWindow.getBounds().x,
                y: mainWindow.getBounds().y
            });
        }
    });

    // Start Python process
    startPythonServer();

    // Arayüz çökme dinleyicileri
    mainWindow.webContents.on('render-process-gone', (event, details) => {
        console.error('Renderer process gone:', details);
        dialog.showErrorBox('Arayüz Çöktü', `Arayüz süreci beklenmedik şekilde sonlandı (Sebep: ${details.reason}). Uygulama kapatılacak.`);
        app.quit();
    });

    mainWindow.on('unresponsive', () => {
        console.warn('Window became unresponsive');
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    mainWindow.on('minimize', (event) => {
        // Tray varsa simge durumunda tepsiye gizle. Tray YOKSA normal minimize
        // birak; aksi halde pencere gizlenir ve geri getirilemez (kaybolur).
        if (tray) {
            event.preventDefault();
            mainWindow.hide();
        }
    });

    // Show window when ready
    mainWindow.once('ready-to-show', () => {
        if (serverReady && mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.show();
        }
    });

    createMenu();
    createTray();

    // NOT: Ctrl+Shift+I icin ONCEDEN buraya bir globalShortcut.register cagrisi
    // vardi. globalShortcut SISTEM GENELINDEDIR — bu uygulama arka planda/
    // odak disindayken bile calisir ve baska programlardaki (tarayici, IDE vb.)
    // AYNI DevTools kisayolunu gasp ederdi. Menudeki 'Dev Tools' ogesi zaten ayni
    // tuş bileşimini (Ctrl+Shift+I) pencere-kapsamli accelerator olarak sagliyor
    // (bkz. createMenu()) — global kayda gerek yok.
}

// ─────────────────────────────────────────────────────────────────────────
// Mini overlay penceresi: cercevesiz, her zaman ustte, ana pencereden BAGIMSIZ
// kucuk bir BrowserWindow. /overlay route'unu yukler (bkz. buyedektir.py) —
// aninin transkript+ceviri+AI okunus onerisini gosterir; kullanicinin gorusme/
// oyun sirasinda tam pencereye gecmeden goz atmasi icindir.
// ─────────────────────────────────────────────────────────────────────────
function createOverlayWindow() {
    if (!serverReady) {
        dialog.showErrorBox('Sunucu Hazır Değil', 'Overlay açmadan önce ana pencerenin yüklenmesini bekleyin.');
        return;
    }
    if (overlayWindow && !overlayWindow.isDestroyed()) {
        setOverlayLocked(false);
        overlayWindow.showInactive();
        return;
    }
    overlayWindow = null;

    const savedOverlayState = store ? store.get('overlayState', {
        width: 520, height: 240, x: undefined, y: undefined
    }) : { width: 520, height: 240, x: undefined, y: undefined };
    const area = screen.getPrimaryDisplay().workArea;
    const width = Math.min(area.width, Math.max(320, Number(savedOverlayState.width) || 520));
    const height = Math.min(area.height, Math.max(220, Number(savedOverlayState.height) || 240));
    // Ekran çıkarıldıysa pencere kaybolmasın; yalnız görünür kayıtlı konumu kullan.
    const visible = screen.getAllDisplays().some(d => Number.isFinite(savedOverlayState.x)
        && Number.isFinite(savedOverlayState.y) && savedOverlayState.x >= d.workArea.x
        && savedOverlayState.y >= d.workArea.y && savedOverlayState.x + width <= d.workArea.x + d.workArea.width
        && savedOverlayState.y + height <= d.workArea.y + d.workArea.height);

    overlayWindow = new BrowserWindow({
        width, height,
        x: visible ? savedOverlayState.x : area.x + Math.round((area.width - width) / 2),
        y: visible ? savedOverlayState.y : area.y + area.height - height - 48,
        minWidth: 320,
        minHeight: 220,
        frame: false,
        alwaysOnTop: true,
        transparent: true,
        skipTaskbar: true,
        resizable: true,
        show: false,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });
    overlayLocked = false;
    overlayWindow.setAlwaysOnTop(true, 'screen-saver');
    overlayLockShortcut = globalShortcut.register('CommandOrControl+Shift+L', () => setOverlayLocked(!overlayLocked));

    restrictWindowNavigation(overlayWindow.webContents, `http://localhost:${PORT}`);
    overlayWindow.loadURL(`http://localhost:${PORT}/overlay`);
    overlayWindow.once('ready-to-show', () => {
        if (overlayWindow && !overlayWindow.isDestroyed()) overlayWindow.showInactive();
    });

    overlayWindow.on('close', () => {
        if (store && overlayWindow) {
            store.set('overlayState', {
                width: overlayWindow.getBounds().width,
                height: overlayWindow.getBounds().height,
                x: overlayWindow.getBounds().x,
                y: overlayWindow.getBounds().y
            });
        }
    });
    overlayWindow.on('closed', () => {
        if (overlayLockShortcut) globalShortcut.unregister('CommandOrControl+Shift+L');
        overlayLockShortcut = false;
        overlayLocked = false;
        overlayWindow = null;
    });
}

function toggleOverlayWindow() {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.close();
    } else {
        overlayWindow = null;
        createOverlayWindow();
    }
}

// ─────────────────────────────────────────────────────────────────────────
// Global Push-to-Talk (opt-in, varsayilan KAPALI).
//
// ONEMLI TASARIM NOTU: Uygulama icindeki MEVCUT PTT (Ctrl/Alt BASILI TUTMA)
// yalniz Electron penceresi ODAKTAYKEN calisir (renderer'daki DOM keydown/
// keyup dinleyicileri). Electron'un globalShortcut API'si ise sistem genelinde
// TEK BASISTA tetiklenen "accelerator"lardir — global bir "tus birakildi"
// olayi YOKTUR; yani ayni "basili tut" davranisini baska bir uygulamaya
// (oyun/goruntulu gorusme) odaklanmisken BIREBIR tasimak Electron'da mumkun
// degildir. Bu yuzden global PTT AYRI bir ac/kapa (toggle) mekanizmasi olarak
// uygulandi: kisayola HER basista PTT acilir/kapanir, basili tutmaya gerek
// yoktur. Varsayilan KAPALI (tepsi menusunden acilir); secilen tus kombi-
// nasyonu (Ctrl+Shift+Space) yaygin uygulama kisayollariyla celisme riskini
// azaltmak icin bilerek sıradışı secildi ama HER oyun/uygulamada CAKISMAYACAGI
// GARANTI EDILEMEZ — kullanici kendi ortaminda test etmeli.
const GLOBAL_PTT_ACCELERATOR = 'CommandOrControl+Shift+Space';
let globalPttRequestSerial = 0;

function sendPttRequest(active) {
    const { net } = require('electron');
    const serial = ++globalPttRequestSerial;
    const fail = (message) => {
        if (serial !== globalPttRequestSerial || isQuitting) return;
        globalPttActive = false;
        if (tray) tray.setToolTip('Whisper Pro');
        dialog.showErrorBox('Yakalama PTT', message);
    };
    try {
        const request = net.request({
            method: 'POST',
            url: `http://localhost:${PORT}/api/ptt`
        });
        request.setHeader('Content-Type', 'application/json');
        request.setHeader('X-Whisper-Token', APP_TOKEN);
        let settled = false;
        const timeout = setTimeout(() => {
            if (settled) return;
            settled = true;
            request.abort();
            fail('Ses yakalama sunucusu 5 saniyede yanıt vermedi.');
        }, 5000);
        request.on('error', () => {
            if (settled) return;
            settled = true;
            clearTimeout(timeout);
            fail('Ses yakalama sunucusuna ulaşılamadı.');
        });
        request.on('response', response => {
            const chunks = [];
            response.on('data', chunk => chunks.push(Buffer.from(chunk)));
            response.on('end', () => {
                if (settled) return;
                settled = true;
                clearTimeout(timeout);
                try {
                    const data = JSON.parse(Buffer.concat(chunks).toString('utf8'));
                    if (!data.success) fail(data.error || 'PTT isteği uygulanamadı.');
                } catch (_) { fail('PTT yanıtı okunamadı.'); }
            });
        });
        request.end(JSON.stringify({ active }));
    } catch (err) {
        console.error('Global PTT istegi gonderilemedi:', err);
        fail('PTT isteği gönderilemedi.');
    }
}

function toggleGlobalPtt() {
    globalPttActive = !globalPttActive;
    sendPttRequest(globalPttActive);
    if (tray) {
        tray.setToolTip(globalPttActive ? 'Whisper Pro — Yakalama PTT AKTİF' : 'Whisper Pro');
    }
}

function setGlobalPttEnabled(enabled) {
    if (enabled === globalPttEnabled) return;
    if (enabled) {
        const ok = globalShortcut.register(GLOBAL_PTT_ACCELERATOR, toggleGlobalPtt);
        if (!ok) {
            dialog.showErrorBox('Kısayol Kaydedilemedi',
                `${GLOBAL_PTT_ACCELERATOR} kısayolu başka bir uygulama tarafından kullanılıyor olabilir.`);
            return;
        }
        globalPttEnabled = true;
    } else {
        globalShortcut.unregister(GLOBAL_PTT_ACCELERATOR);
        globalPttEnabled = false;
        if (globalPttActive) {
            globalPttActive = false;
            sendPttRequest(false); // acik kalmis bir PTT'yi kapatarak birak
        }
    }
}

function startPythonServer() {
    // Crash backoff zamanlayicisi kapanis basladiktan sonra tetiklenebilir.
    if (isQuitting) return;
    // Port 5000'i işgal eden eski yetim süreçleri temizle
    serverReady = false;
    serverReadyRetries = 0;
    const backendNonce = crypto.randomBytes(24).toString('hex');
    activeBackendNonce = backendNonce;
    if (!killOrphanedPythonProcesses()) {
        isQuitting = true;
        dialog.showErrorBox(
            'Port Kullanımda',
            `Port ${PORT} başka bir uygulama tarafından kullanılıyor. ` +
            'Whisper Pro güvenlik nedeniyle o uygulamaya bağlanmadı.'
        );
        app.quit();
        return;
    }

    const cmd = getPythonCommand();
    if (!cmd) {
        isQuitting = true;
        dialog.showErrorBox(
            'Python Bağımlılıkları Bulunamadı',
            'Whisper Pro için gerekli Python ortamı bulunamadı. Proje içindeki .venv klasörünü koruyun veya WHISPER_PYTHON ile doğru python.exe yolunu belirtin.'
        );
        app.quit();
        return;
    }
    console.log(`Starting Python: ${cmd} buyedektir.py`);

    pythonProcess = spawn(cmd, [path.join(__dirname, 'buyedektir.py'), '--whisper-electron-child'], {
        cwd: __dirname,
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: false,
        // Electron'un kontrol ettigi port ile Flask'in dinledigi port kesin
        // ayni olsun; .env/process.env oncelik farki sessiz startup asmasin.
        env: {
            ...process.env,
            PORT: String(PORT),
            WHISPER_APP_TOKEN: APP_TOKEN,
            WHISPER_BACKEND_NONCE: backendNonce
        }
    });

    if (!pythonProcess.pid) {
        isQuitting = true;  // async 'error' eventi cift dialog/quit yapmasin (asagi bak)
        dialog.showErrorBox('Error', 'Failed to start Flask server. Make sure Python is installed.');
        app.quit();
        return;
    }

    pythonProcess.stdout.on('data', (data) => {
        if (isDev) console.log(`[Flask] ${data.toString().trim()}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`[Flask Error] ${data.toString().trim()}`);
    });

    pythonProcess.on('error', (err) => {
        if (isQuitting) return;  // !pid dali zaten ele aldiysa tekrar dialog/quit yapma
        console.error('Failed to start Python process:', err);
        isQuitting = true;
        dialog.showErrorBox('Error', `Failed to start server: ${err.message}`);
        app.quit();
    });

    pythonProcess.on('close', (code) => {
        // Hazirliktan once cokmusse ortam yeniden kontrol edilmeli.
        if (!serverReady) cachedPythonCommand = null;
        console.log(`Python process exited with code ${code}`);
        pythonProcess = null;
        serverReady = false;
        activeBackendNonce = null;
        if (backendStableTimer) {
            clearTimeout(backendStableTimer);
            backendStableTimer = null;
        }
        // Backend cokunce onun PTT durumu da sifirlanir. Main-process bayragi acik
        // kalirsa yeniden baslatilan backend'e ilk kisayol ters komut gonderirdi.
        globalPttActive = false;
        if (tray) tray.setToolTip('Whisper Pro');
        if (!isQuitting && mainWindow) {
            if (pythonRestartCount < 3) {
                pythonRestartCount++;
                console.warn(`Flask kapandi (code ${code}); yeniden baslatiliyor (${pythonRestartCount}/3)...`);
                // Artan gecikme (backoff): tight crash-restart dongusunu onler
                setTimeout(startPythonServer, 1500 * pythonRestartCount);
            } else {
                dialog.showErrorBox('Server Error',
                    'Flask sunucusu tekrar tekrar cokuyor (3 deneme asildi). ' +
                    'Python kurulumu/bagimliliklarini kontrol edin.');
                isQuitting = true;
                app.quit();
            }
        }
    });

    // Ilk acilista oldugu gibi crash sonrasi spawn'da da hazirligi izle.
    checkServerReady(backendNonce);
}

function checkServerReady(expectedNonce, deadline = Date.now() + 60000) {
    if (isQuitting || expectedNonce !== activeBackendNonce) return;
    const { net } = require('electron');
    const request = net.request(`http://localhost:${PORT}/api/check_models`);
    request.setHeader('X-Whisper-Token', APP_TOKEN);
    // Deneme sayisina ek olarak duvar saati siniri var; askida HTTP de sinirli.
    // Soguk acilista
    // backend importlari (torch/faster-whisper) 40-50sn surebiliyor; eski 15sn
    // siniri bu durumda uygulamayi "baglanilamadi" deyip kapatiyordu.
    const maxRetries = 120;
    let settled = false;
    const timeout = setTimeout(() => {
        if (settled) return;
        settled = true;
        request.abort();
        retryOrFail('Flask hazirlik istegi zaman asimina ugradi (60 sn).');
    }, Math.max(1, Math.min(5000, deadline - Date.now())));

    const retryOrFail = (message) => {
        if (isQuitting || expectedNonce !== activeBackendNonce) return;
        serverReadyRetries++;
        if (serverReadyRetries < maxRetries && Date.now() < deadline) {
            setTimeout(() => checkServerReady(expectedNonce, deadline), 500);
        } else {
            dialog.showErrorBox('Connection Error', message);
            app.quit();
        }
    };

    request.on('response', (response) => {
        const chunks = [];
        response.on('data', (chunk) => chunks.push(Buffer.from(chunk)));
        response.on('end', () => {
            if (settled) return;
            settled = true;
            clearTimeout(timeout);
            if (isQuitting || expectedNonce !== activeBackendNonce) return;
            let payload = null;
            try {
                payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            } catch (e) {
                payload = null;
            }

            if (isExpectedBackendResponse(response.statusCode, payload, expectedNonce)) {
                console.log('Flask server is ready!');
                serverReady = true;
                serverReadyRetries = 0;
                // 30sn ayakta kalan backend'i saglikli say. Boylece aralikli cokmeler
                // omur boyu birikmez, fakat hizli crash-loop yine 3 denemede kesilir.
                const readyProcess = pythonProcess;
                if (backendStableTimer) clearTimeout(backendStableTimer);
                backendStableTimer = setTimeout(() => {
                    if (pythonProcess === readyProcess && serverReady) pythonRestartCount = 0;
                    backendStableTimer = null;
                }, 30000);
                if (mainWindow && !mainWindow.isDestroyed()) {
                    mainWindow.loadURL(`http://localhost:${PORT}`);
                    mainWindow.show();
                }
            } else {
                retryOrFail(
                    `Port ${PORT} beklenen Whisper backend kimliğini vermiyor ` +
                    `(statü ${response.statusCode}). Başka bir uygulama bu portu tutuyor olabilir.`
                );
            }
        });
    });

    request.on('error', (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeout);
        retryOrFail(
            'Flask sunucusuna bağlanılamadı (60 sn). Python ve bağımlılıkları kontrol edin.'
        );
    });

    request.end();
}

function createMenu() {
    const template = [
        {
            label: 'File',
            submenu: [
                {
                    label: 'Exit',
                    accelerator: 'CmdOrCtrl+Q',
                    click: () => {
                        isQuitting = true;
                        app.quit();
                    }
                }
            ]
        },
        {
            label: 'View',
            submenu: [
                {
                    label: 'Toggle Window',
                    accelerator: 'CmdOrCtrl+H',
                    click: () => {
                        if (!mainWindow || mainWindow.isDestroyed()) return;
                        if (mainWindow.isVisible()) {
                            mainWindow.hide();
                        } else {
                            mainWindow.show();
                        }
                    }
                },
                {
                    label: 'Oyun Çevirisi Göster/Gizle (Ctrl+Shift+O)',
                    click: () => toggleOverlayWindow()
                },
                { type: 'separator' },
                {
                    label: 'Reload',
                    accelerator: 'CmdOrCtrl+R',
                    click: () => { if (mainWindow && !mainWindow.isDestroyed()) mainWindow.reload(); }
                },
                { type: 'separator' },
                {
                    label: 'Dev Tools',
                    accelerator: isDev ? 'F12' : 'Ctrl+Shift+I',
                    click: () => { if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.toggleDevTools(); }
                }
            ]
        },
        {
            label: 'Help',
            submenu: [
                {
                    label: 'About',
                    click: () => {
                        if (!mainWindow || mainWindow.isDestroyed()) return;
                        dialog.showMessageBox(mainWindow, {
                            type: 'info',
                            title: 'About Whisper Pro',
                            message: 'Whisper Pro',
                            detail: 'Speech-to-Text with AI\nVersion 1.0.0'
                        });
                    }
                }
            ]
        }
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

function createTray() {
    try {
        const trayIconPath = path.join(__dirname, 'assets', 'tray-icon.ico');
        tray = new Tray(trayIconPath);
    } catch (e) {
        console.warn('Tray icon not found, skipping tray');
        return;
    }

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Open',
            click: () => {
                if (!mainWindow || mainWindow.isDestroyed()) return;
                mainWindow.show();
                mainWindow.focus();
            }
        },
        {
            label: 'Settings',
            click: () => {
                if (!mainWindow || mainWindow.isDestroyed()) return;
                mainWindow.show();
                mainWindow.focus();
            }
        },
        { type: 'separator' },
        {
            label: 'Mini Overlay Göster/Gizle',
            type: 'checkbox',
            checked: false,
            click: (menuItem) => {
                toggleOverlayWindow();
                // Pencere kullanicinin X'e basmasiyla da kapanabilir; checkbox
                // durumunu asil pencere varligina gore geri esitle.
                menuItem.checked = !!overlayWindow;
            }
        },
        {
            label: `Yakalama PTT — seçili ses kaynağı (${GLOBAL_PTT_ACCELERATOR})`,
            type: 'checkbox',
            checked: false,
            click: (menuItem) => {
                setGlobalPttEnabled(menuItem.checked);
                menuItem.checked = globalPttEnabled; // kayit basarisiz olursa geri al
            }
        },
        { type: 'separator' },
        {
            label: 'Quit',
            click: () => {
                isQuitting = true;
                app.quit();
            }
        }
    ]);

    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
        if (!mainWindow || mainWindow.isDestroyed()) return;
        if (mainWindow.isVisible()) {
            mainWindow.hide();
        } else {
            mainWindow.show();
            mainWindow.focus();
        }
    });

    tray.setToolTip('Whisper Pro');
}

// Tek instance: ayni anda yalnizca bir kopya calissin. Ikinci kez acilirsa
// yeni kopya kapanir ve mevcut pencere one getirilir (port/pencere cakismasini onler).
const gotSingleInstanceLock = app.requestSingleInstanceLock();
if (!gotSingleInstanceLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        if (mainWindow && !mainWindow.isDestroyed()) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            if (!mainWindow.isVisible()) mainWindow.show();
            mainWindow.focus();
        }
    });
    app.on('ready', () => {
        createWindow();
        globalShortcut.register('CommandOrControl+Shift+O', toggleOverlayWindow);
    });
}

app.on('window-all-closed', () => {
    if (!isMac) {
        isQuitting = true;
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('before-quit', () => {
    isQuitting = true;
});

app.on('will-quit', () => {
    globalShortcut.unregisterAll();
    killChildPython();
});
