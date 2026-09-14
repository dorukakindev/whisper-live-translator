'use strict';
// Oyun penceresinin fare kilidi, konum kurtarma ve odak sözleşmesi.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync('main.js', 'utf8');
const calls = [];
let options;
const handlers = {};
const fakeWindow = {
    isDestroyed: () => false,
    webContents: {send: (...args) => calls.push(['send', ...args])},
    setIgnoreMouseEvents: (...args) => calls.push(['mouse', ...args]),
    setFocusable: flag => calls.push(['focusable', flag]),
    setAlwaysOnTop: (...args) => calls.push(['top', ...args]),
    loadURL() {}, once: (name, fn) => { handlers[name] = fn; },
    on: (name, fn) => { handlers[name] = fn; },
    showInactive: () => calls.push(['showInactive']),
    getBounds: () => ({x: 10, y: 20, width: 520, height: 300}),
};
const ctx = vm.createContext({
    overlayWindow: null, overlayLocked: false, overlayLockShortcut: false,
    serverReady: true, PORT: 5000, __dirname: '.', path: require('path'),
    dialog: {showErrorBox() { throw Error('unexpected'); }},
    store: {get: () => ({x: 9000, y: -400, width: 520, height: 300}), set() {}},
    screen: {getPrimaryDisplay: () => ({workArea: {x: 0, y: 0, width: 1920, height: 1080}}),
        getAllDisplays: () => [{workArea: {x: 0, y: 0, width: 1920, height: 1080}}]},
    BrowserWindow: function(opts) { options = opts; return fakeWindow; },
    globalShortcut: {register: () => true, unregister: key => calls.push(['unregister', key])},
    restrictWindowNavigation() {},
});
vm.runInContext(source.slice(source.indexOf('function setOverlayLocked('), source.indexOf("ipcMain.handle('overlay-control'")), ctx);
vm.runInContext(source.slice(source.indexOf('function createOverlayWindow()'), source.indexOf('function toggleOverlayWindow()')), ctx);
ctx.createOverlayWindow();
assert(options.x >= 0 && options.x + options.width <= 1920);
assert(options.y >= 0 && options.y + options.height <= 1080);
assert.strictEqual(options.webPreferences.nodeIntegration, false);
assert.strictEqual(options.webPreferences.contextIsolation, true);
handlers['ready-to-show']();
assert(calls.some(c => c[0] === 'showInactive'));
assert(ctx.setOverlayLocked(true));
assert(calls.some(c => c[0] === 'mouse' && c[1] === true));
assert(calls.some(c => c[0] === 'focusable' && c[1] === false));
ctx.createOverlayWindow();
assert.strictEqual(ctx.overlayLocked, false);
ctx.overlayLockShortcut = false;
assert.strictEqual(ctx.setOverlayLocked(true), false);
ctx.overlayLockShortcut = true;
handlers.closed();
assert.strictEqual(ctx.overlayWindow, null);
assert(calls.some(c => c[0] === 'unregister'));
console.log('Oyun overlay pencere, kilit ve konum testleri geçti');
