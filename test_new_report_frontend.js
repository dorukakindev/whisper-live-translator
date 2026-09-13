'use strict';
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const html = fs.readFileSync('templates/index.html', 'utf8');
function extract(text, start, end) {
    const a = text.indexOf(start), b = text.indexOf(end, a + start.length);
    assert(a >= 0 && b > a, start);
    return text.slice(a, b);
}
const translations = vm.createContext({escapeHtml: s => String(s).replace(/</g, '&lt;'), escapeJsString: String});
vm.runInContext(extract(html, '        function buildTranslationResultHtml(', '        function toggleSuggestionBox('), translations);
const single = translations.buildTranslationResultHtml('Hello: world', 'English', 'en');
assert(single.includes('copyResponseText'));
assert(single.includes('speakText'));
assert(single.includes('Hello: world'));
assert(!single.includes('🇹🇷 Türkçe:'));
assert(translations.buildTranslationResultHtml('First line\nSecond line', 'English', 'en').includes('First line\nSecond line'));
assert(translations.buildTranslationResultHtml('Hello\nTürkçe: Merhaba', 'English', 'en').includes('🇹🇷 Türkçe:'));

const events = {}, name = {textContent: 'Old'}, icon = {textContent: 'K'};
const badge = {querySelector: () => name};
Object.defineProperty(badge, 'textContent', {set() {throw Error('Badge structure erased');}});
const ctx = vm.createContext({socket: {on: (event, fn) => events[event] = fn}, speakers: {'1': {name: 'Old'}},
    document: {querySelectorAll: () => [{dataset: {speakerId: '1'}, querySelector: () => badge}]},
    renderSpeakerSummary() {}, applyRuntimeSettings() {}});
vm.runInContext(extract(html, '        function setupSocketListeners()', '        // Yeniden baglanma sonrasi'), ctx);
ctx.setupSocketListeners(); events.speaker_updated({speaker_id: 1, speaker_name: 'New'});
assert.strictEqual(name.textContent, 'New'); assert.strictEqual(icon.textContent, 'K');

const main = fs.readFileSync('main.js', 'utf8');
const EventEmitter = require('events');
const pttRequest = new EventEmitter();
pttRequest.setHeader = () => {};
pttRequest.end = () => {};
let pttWarning = '';
const pttTimers = [];
const pttCtx = vm.createContext({Buffer, globalPttActive: true, isQuitting: false, tray: {setToolTip() {}}, PORT: 5000, APP_TOKEN: 'test',
    require: () => ({net: {request: () => pttRequest}}), console,
    setTimeout: (fn, ms) => {pttTimers.push({fn, ms}); return pttTimers.length;}, clearTimeout() {},
    dialog: {showErrorBox: (title, message) => pttWarning = message}});
vm.runInContext('let globalPttRequestSerial = 0;\n' + extract(main, 'function sendPttRequest(', 'function toggleGlobalPtt()'), pttCtx);
pttCtx.sendPttRequest(true);
const response = new EventEmitter();
pttRequest.emit('response', response);
response.emit('data', Buffer.from(JSON.stringify({success: false, error: 'Önce ses yakalamayı başlatın'})));
response.emit('end');
assert.strictEqual(pttCtx.globalPttActive, false);
assert(pttWarning.includes('başlatın'));
assert.strictEqual(pttTimers[0].ms, 5000);
const hangingRequest = new EventEmitter();
hangingRequest.setHeader = () => {}; hangingRequest.end = () => {};
let aborts = 0; hangingRequest.abort = () => {aborts++; hangingRequest.emit('error', Error('aborted'));};
pttCtx.require = () => ({net: {request: () => hangingRequest}});
pttCtx.globalPttActive = true; pttWarning = '';
pttCtx.sendPttRequest(true);
pttTimers[1].fn();
assert.strictEqual(aborts, 1);
assert.strictEqual(pttCtx.globalPttActive, false);
assert(pttWarning.includes('5 saniyede'));
let menu;
const menuCtx = vm.createContext({mainWindow: null, isDev: false,
    Menu: {buildFromTemplate: t => {menu = t; return t;}, setApplicationMenu() {}}});
vm.runInContext(extract(main, 'function createMenu()', 'function createTray()'), menuCtx);
menuCtx.createMenu();
for (const window of [null, {isDestroyed: () => true}]) {
    menuCtx.mainWindow = window;
    for (const section of menu) for (const item of section.submenu || []) {
        if (['Toggle Window', 'Reload', 'Dev Tools', 'About'].includes(item.label)) item.click();
    }
}

let overlayCreates = 0;
const overlayToggleCtx = vm.createContext({overlayWindow: {isDestroyed: () => true}, createOverlayWindow: () => overlayCreates++});
vm.runInContext(extract(main, 'function toggleOverlayWindow()', 'const GLOBAL_PTT_ACCELERATOR'), overlayToggleCtx);
overlayToggleCtx.toggleOverlayWindow();
assert.strictEqual(overlayCreates, 1);
assert.strictEqual(overlayToggleCtx.overlayWindow, null);

const overlay = fs.readFileSync('templates/overlay.html', 'utf8');
assert(overlay.includes('src="/static/runtime-safety.js"'));
const win = {};
Object.defineProperty(win, 'localStorage', {get() {throw Error('denied');}});
let sent = false;
const overlayCtx = vm.createContext({window: win, document: {readyState: 'complete', getElementById: () => null}, console: {warn() {}},
    lastTranscriptId: 1, lastTranscriptText: 'Hello', backendInstanceId: 'test',
    fetch: (url, options) => {assert.strictEqual(JSON.parse(options.body).target_lang, 'auto'); sent = true; return Promise.resolve({json: async () => ({success: true, options: []})});}});
vm.runInContext(fs.readFileSync('static/runtime-safety.js', 'utf8'), overlayCtx);
overlayCtx.whisperStorage = win.whisperStorage;
vm.runInContext(extract(overlay, '        function requestAnswer()', '        async function hydrateLatestTranscript()').replace('{{ app_token|tojson }}', '"synthetic"'), overlayCtx);
overlayCtx.requestAnswer(); assert(sent);
console.log('13 maddelik rapor frontend testleri gecti');
