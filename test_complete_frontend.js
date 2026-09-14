'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync('templates/index.html', 'utf8');
function part(start, end) {
    const a = html.indexOf(start), b = html.indexOf(end, a + start.length);
    assert(a >= 0 && b > a, start);
    return html.slice(a, b);
}
async function main() {
    let socketWarnings = 0;
    const listeners = [];
    const socketContext = vm.createContext({
        socket: null,
        showAlert: () => socketWarnings++,
        applyRuntimeSettings() {}
    });
    vm.runInContext(part('        function setupSocketListeners()', '        // Yeniden baglanma sonrasi'), socketContext);
    socketContext.setupSocketListeners();
    assert.strictEqual(socketWarnings, 1);
    socketContext.socket = {on: name => listeners.push(name)};
    socketContext.setupSocketListeners();
    const listenerCount = listeners.length;
    socketContext.setupSocketListeners();
    assert(listenerCount > 0);
    assert.strictEqual(listeners.length, listenerCount);

    const editor = {value: ''};
    const ctx = vm.createContext({document: {getElementById: id => id === 'glossaryEditor' ? editor : null}});
    vm.runInContext(part('        function parseGlossaryEditor()', '        async function saveGlossary'), ctx);
    const entries = [{source: 'A|B', target: 'C\\D', pronunciation: 'okunuş', lang: 'ja'}];
    ctx.renderGlossaryEditor(entries);
    assert.deepStrictEqual(JSON.parse(JSON.stringify(ctx.parseGlossaryEditor())), entries);
    editor.value = '\n'.repeat(120) + 'test | result | sound | en';
    assert.strictEqual(ctx.parseGlossaryEditor().length, 1);
    editor.value = 'C:\\Docs | path | | en';
    assert.strictEqual(ctx.parseGlossaryEditor()[0].source, 'C:\\Docs');

    const storageWindow = {};
    Object.defineProperty(storageWindow, 'localStorage', {get() {throw Error('denied');}});
    let notices = 0;
    storageWindow.showAlert = () => notices++;
    vm.runInNewContext(fs.readFileSync('static/runtime-safety.js', 'utf8'), {window: storageWindow, document: {readyState: 'complete'}, console: {warn() {}}});
    assert.strictEqual(storageWindow.whisperStorage.getItem('missing'), null);
    assert.strictEqual(storageWindow.whisperStorage.setItem('x', 1), false);
    assert.strictEqual(storageWindow.whisperStorage.getItem('x'), '1');
    storageWindow.whisperStorage.removeItem('x');
    assert.strictEqual(storageWindow.whisperStorage.getItem('x'), null);
    assert.strictEqual(notices, 1);

    const parts = {};
    const preview = {innerHTML: '', querySelector: selector => parts[selector] || (parts[selector] = {textContent:''})};
    const pv = vm.createContext({document: {getElementById: id => id === 'transcriptionList' ? {querySelector: () => null} : preview}, escapeHtml: String, clearTimeout() {}, setTimeout() {}, clearPartialPreview() {}});
    vm.runInContext('let _partialHideTimer = null;\n' + part('        function showPartialPreview(', '        function clearPartialPreview('), pv);
    for (const [text, stable, draft, sep] of [['これは日本語', 'これは', '日本語', ''], ['hello world', 'hello', 'world', ' '], ['東京 test', '東京', 'test', ' '], ['testing', 'test', 'ing', '']]) {
        pv.showPartialPreview({text, stable_text: stable, draft_text: draft});
        assert.strictEqual(parts['.partial-stable'].textContent, stable + sep, text);
        assert.strictEqual(parts['.partial-draft'].textContent, draft, text);
    }

    const result = {style: {}, querySelector: () => ({classList: {contains: () => true}}), querySelectorAll: () => []};
    const render = vm.createContext({
        document: {getElementById: () => result},
        window: {},
        escapeHtml: String,
        escapeJsString: String,
        breathGroupHtml: String,
        whisperStorage: {getItem: () => null, setItem: () => true}
    });
    vm.runInContext(part('        function renderAiResult(', '        // Theme Management'), render);
    render.renderAiResult(1, 'answer', {options: [{translation: 'Hello', turkish: 'Merhaba', romanized: 'helo'}]}, 'en', 'English', true);
    assert(result.innerHTML.includes('ai-suggestion-box collapsed'));

    const requests = [], restores = [];
    const settings = vm.createContext({AbortController, setTimeout, clearTimeout, showAlert() {}, fetch: (path, options) => new Promise(resolve => requests.push({resolve, options}))});
    vm.runInContext(part('        const runtimeSettingWrites', '        // Çeviri durumunu güncelle'), settings);
    const first = settings.persistRuntimeSettings('/api/test', {value: 1}, {value: 0}, s => restores.push(s.value));
    const second = settings.persistRuntimeSettings('/api/test', {value: 2}, {value: 1}, s => restores.push(s.value));
    await new Promise(setImmediate);
    assert.strictEqual(requests.length, 1);
    requests[0].resolve({ok: false, json: async () => ({success: false})});
    await first;
    await new Promise(setImmediate);
    assert.strictEqual(requests.length, 2);
    requests[1].resolve({ok: false, json: async () => ({success: false})});
    await second;
    assert.deepStrictEqual(restores, [0]);
    const third = settings.persistRuntimeSettings('/api/test', {value: 3}, {value: 0}, s => restores.push(s.value));
    await new Promise(setImmediate);
    requests[2].resolve({ok: true, json: async () => ({success: true})});
    await third;
    const fourth = settings.persistRuntimeSettings('/api/test', {value: 4}, {value: 3}, s => restores.push(s.value));
    await new Promise(setImmediate);
    requests[3].resolve({ok: false, json: async () => ({success: false})});
    await fourth;
    assert.deepStrictEqual(restores, [0, 3]);

    const launcher = fs.readFileSync('main.js', 'utf8');
    const EventEmitter = require('events');
    const probe = new EventEmitter();
    let aborted = 0, now = 0, quits = 0;
    probe.end = () => {};
    probe.setHeader = (name, value) => {
        assert.strictEqual(name, 'X-Whisper-Token');
        assert.strictEqual(value, 'test-token');
    };
    probe.abort = () => { aborted++; probe.emit('error', Error('aborted')); };
    const timers = [];
    const readiness = vm.createContext({isQuitting: false, activeBackendNonce: 'test', APP_TOKEN: 'test-token', PORT: 5000,
        serverReadyRetries: 0, Date: {now: () => now}, Buffer,
        require: () => ({net: {request: () => probe}}),
        setTimeout: (fn, ms) => {timers.push({fn, ms}); return timers.length;}, clearTimeout() {},
        dialog: {showErrorBox() {}}, app: {quit: () => quits++}});
    vm.runInContext(launcher.slice(launcher.indexOf('function checkServerReady('), launcher.indexOf('function createMenu()')), readiness);
    readiness.checkServerReady('test');
    assert.strictEqual(timers[0]?.ms, 5000);
    timers[0].fn();
    assert.strictEqual(aborted, 1);
    assert.strictEqual(readiness.serverReadyRetries, 1);
    assert.strictEqual(timers.length, 2); // abort error ikinci retry uretmemeli.
    now = 61000;
    timers[1].fn();
    timers[2].fn();
    assert.strictEqual(quits, 1);
    const closing = vm.createContext({isQuitting: true});
    vm.runInContext(launcher.slice(launcher.indexOf('function startPythonServer()'), launcher.indexOf('function checkServerReady(')), closing);
    // Kapanis sonrasi gecikmis restart, port temizligine veya spawn'a ulasmamali.
    closing.startPythonServer();
    let probes = 0;
    const probeContext = vm.createContext({
        __dirname: 'D:\\synthetic', path: require('path').win32,
        process: {env: {WHISPER_PYTHON: 'D:\\synthetic\\python.exe'}},
        require: name => name === 'fs' ? {existsSync: () => true} : {
            execFileSync(cmd, args, options) {
                probes++;
                assert.strictEqual(options.timeout, 5000);
                assert(args[1].includes('find_spec'));
            }
        }
    });
    vm.runInContext(launcher.slice(launcher.indexOf('let cachedPythonCommand'), launcher.indexOf('function createWindow()')), probeContext);
    assert.strictEqual(probeContext.getPythonCommand(), 'D:\\synthetic\\python.exe');
    assert.strictEqual(probeContext.getPythonCommand(), 'D:\\synthetic\\python.exe');
    assert.strictEqual(probes, 1);
    console.log('Tam denetim frontend testleri gecti');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
