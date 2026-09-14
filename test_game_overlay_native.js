'use strict';
// Windows/Electron üzerinde gerçek pencere ve preload köprüsü; oyun verisi kullanmaz.
const {app, BrowserWindow, screen, globalShortcut, ipcMain} = require('electron');
const fs = require('fs');
const path = require('path');
const http = require('http');
const assert = require('assert');
app.disableHardwareAcceleration();
app.whenReady().then(async () => {
    const html = fs.readFileSync('artifacts/cockpit-v2/overlay.html');
    const server = http.createServer((_req, res) => {res.setHeader('Content-Type', 'text/html; charset=utf-8'); res.end(html);});
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    const environment = {BrowserWindow, screen, globalShortcut, ipcMain, path,
        __dirname, store: null, mainWindow: null, overlayWindow: null, overlayLocked: false,
        overlayLockShortcut: false, serverReady: true, PORT: server.address().port,
        restrictWindowNavigation() {}, dialog: {showErrorBox() {throw Error('not ready');}}};
    const source = fs.readFileSync('main.js', 'utf8');
    const factory = new Function(...Object.keys(environment),
        source.slice(source.indexOf('function setOverlayLocked('), source.indexOf('let pythonProcess;')) +
        source.slice(source.indexOf('function createOverlayWindow()'), source.indexOf('function toggleOverlayWindow()')) +
        'return {createOverlayWindow, get overlayWindow(){return overlayWindow}, get overlayLockShortcut(){return overlayLockShortcut}};');
    const ctx = factory(...Object.values(environment));
    try {
        ctx.createOverlayWindow();
        const win = ctx.overlayWindow;
        await new Promise(resolve => win.webContents.once('did-finish-load', resolve));
        await win.webContents.executeJavaScript(`renderTranscript({id:1,source:'system',text:'Stay behind cover. I will watch the entrance.',translation:'Siperde kal. Girişi ben kontrol edeceğim.'}); setConnected(true);`);
        assert(win.isAlwaysOnTop());
        assert(ctx.overlayLockShortcut, 'Kilit kısayolu alınamadı');
        const locked = await win.webContents.executeJavaScript(`window.electronAPI.overlayControl('lock')`);
        assert(locked.success && locked.locked);
        assert.strictEqual(win.isFocusable(), false);
        await new Promise(resolve => setTimeout(resolve, 250));
        fs.writeFileSync('artifacts/cockpit-v2/native-game-locked.png', (await win.webContents.capturePage()).toPNG());
        const unlocked = await win.webContents.executeJavaScript(`window.electronAPI.overlayControl('lock')`);
        assert(unlocked.success && !unlocked.locked);
        assert(win.isFocusable());
        await new Promise(resolve => {win.once('closed', resolve); win.close();});
        assert(!globalShortcut.isRegistered('CommandOrControl+Shift+L'));
        console.log('Gerçek Electron pencere, preload, üstte tutma ve kilit kontrolleri geçti');
    } finally {
        if (ctx.overlayWindow && !ctx.overlayWindow.isDestroyed()) ctx.overlayWindow.close();
        server.close(); globalShortcut.unregisterAll(); app.quit();
    }
}).catch(error => {console.error(error); app.exit(1);});
