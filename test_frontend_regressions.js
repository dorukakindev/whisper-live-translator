'use strict';
// Gercek HTML'deki fonksiyonlari DOM/cihaz/ag yerine kucuk sahtelerle calistir.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, 'templates/index.html'), 'utf8');
const overlay = fs.readFileSync(path.join(__dirname, 'templates/overlay.html'), 'utf8');
const htmlUtils = fs.readFileSync(path.join(__dirname, 'static/html-utils.js'), 'utf8');
assert(html.includes('/static/html-utils.js'));
assert(overlay.includes('/static/html-utils.js'));
assert(!html.includes('function escapeHtml('));
assert(!overlay.includes('function escapeHtml('));
const htmlUtilsContext = vm.createContext({});
vm.runInContext(htmlUtils, htmlUtilsContext);
assert.strictEqual(htmlUtilsContext.escapeHtml('<a & "b">'), '&lt;a &amp; &quot;b&quot;&gt;');
assert(overlay.includes("event.key === 'theme'"));
assert(html.includes('const pttClientId ='));
assert((html.match(/client:\s*pttClientId/g) || []).length >= 2,
    'PTT istemci kimligi normal ve unload komutlarinda gonderilmeli');
function between(from, to) {
    const start = html.indexOf(from);
    const end = html.indexOf(to, start + from.length);
    assert(start >= 0 && end > start, `${from}: kaynak siniri bulunamadi`);
    return html.slice(start, end);
}
for (const file of ['index.html', 'overlay.html']) {
    const source = fs.readFileSync(path.join(__dirname, 'templates', file), 'utf8');
    const blocks = [...source.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
    assert(blocks.length > 0);
    for (const block of blocks) {
        const code = block[1].replace(/\{\{\s*app_token\s*\|\s*tojson\s*\}\}/g, '"test-token"');
        assert.doesNotThrow(() => new vm.Script(code, {filename: file}), undefined, file);
    }
}
const textContext = vm.createContext({ escapeHtml: String, escapeJsString: String });
vm.runInContext(between('        function buildTranslationResultHtml(', '        async function '), textContext);
const rendered = textContext.buildTranslationResultHtml('Note: bring water\nTürkçe: Su getir', 'English', 'en');
assert(rendered.includes('Note: bring water'));
const labelled = textContext.buildTranslationResultHtml('Hedef: Note: bring water\nTürkçe: Su getir', 'English', 'en');
assert(labelled.includes('Note: bring water'));
assert(!labelled.includes('Hedef: Note:'));

const pruneContext = vm.createContext({ MAX_DOM_ITEMS: 2 });
vm.runInContext('let transcriptionTexts = {1:"a",2:"b",3:"c"}; const seenTranscriptionIds = new Set(["1","2","3"]); let prunedTranscriptionId = -1;', pruneContext);
vm.runInContext(between('        function pruneTranscriptionList(', '        function insertTranscriptionById('), pruneContext);
const list = { children: [] };
list.children = [3, 2, 1].map(id => ({ dataset: {transcriptionId: String(id)}, classList: {contains: () => false}, remove() {list.children.pop();} }));
Object.defineProperty(list, 'lastChild', {get: () => list.children.at(-1)});
pruneContext.pruneTranscriptionList(list);
assert.strictEqual(vm.runInContext('seenTranscriptionIds.size', pruneContext), 2);
assert.strictEqual(vm.runInContext('prunedTranscriptionId', pruneContext), 1);

// Yeniden yuklenen sistem/mikrofon/PTT satirlari sayaci arttirmamali.
const count = {textContent: '50'};
const renderedItems = [];
const hydrationList = {querySelector: () => null};
const hydration = vm.createContext({
    prunedTranscriptionId: -1, seenTranscriptionIds: new Set(), transcriptionTexts: {},
    escapeHtml: String, escapeJsString: String, speakerDiarizationEnabled: false,
    showAlert() {}, clearPartialPreview() {}, filterVisibleTranscriptions() {},
    updateStats() {throw new Error('Gecmis yuklenirken sayac degismemeli');},
    insertTranscriptionById(_list, item) {renderedItems.push(item);}, pruneTranscriptionList() {},
    document: {querySelector: () => null,
        getElementById(id) {return id === 'totalCount' ? count : id === 'transcriptionList' ? hydrationList : null;},
        createElement() {return {style: {}, dataset: {}, classList: {add() {}}, setAttribute() {}};}}
});
vm.runInContext(between('        function renderPttTranscription(', '        // Hızlı sıfırla'), hydration);
for (const [id, source] of [[1, 'system'], [2, 'mic'], [3, 'ptt']]) {
    hydration.addTranscription({id, source, success: true, text: 'Merhaba', original: 'Merhaba', translation: 'Hello', target_lang: 'EN'}, true);
}
assert.strictEqual(count.textContent, '50');
assert.strictEqual(renderedItems.length, 3);
assert.strictEqual(renderedItems[2].dataset.transcriptionId, '3');
hydration.addTranscription({id: 3, source: 'ptt', success: true}, true);
assert.strictEqual(renderedItems.length, 3, 'PTT gecmisi iki kez eklenmemeli');

async function pttTest() {
    const events = {}, windowEvents = {}, timers = new Map(), requests = [];
    let nextTimer = 0;
    const ctx = vm.createContext({
        console, crypto: require('crypto'), showAlert() {}, cancelPendingPtt() {}, pttHeld: false,
        _replyGeneration: 0, _ownMicGeneration: null, updateOwnMicButton() {}, setCockpitValue() {},
        setTimeout(fn) {timers.set(++nextTimer, fn); return nextTimer;},
        clearTimeout(id) {timers.delete(id);},
        document: {activeElement: null, addEventListener(type, fn) {events[type] = fn;},
            getElementById(id) {return {value: id === 'aiTargetLang' ? 'ja' : ''};}},
        window: {addEventListener(type, fn) {windowEvents[type] = fn;}},
        async fetch(url, opts) {requests.push({url, ...opts}); return {ok:true, json: async () => ({success:true})};}
    });
    vm.runInContext(between('        let altPttHeld = false;', '        function getRomanizedLabel('), ctx);
    const event = (key, extra = {}) => ({key, preventDefault() {}, ...extra});
    events.keydown(event('Alt'));
    events.keydown(event('Tab', {altKey:true}));
    assert.strictEqual(timers.size, 0, 'Alt+Tab kayit baslatmamali');
    assert.strictEqual(requests.length, 0);
    events.keydown(event('Alt'));
    const fire = [...timers.values()][0]; timers.clear(); fire();
    await vm.runInContext('altPttCommandChain', ctx);
    assert.strictEqual(JSON.parse(requests[0].body).target_lang, 'ja');
    events.keyup(event('Alt'));
    await vm.runInContext('altPttCommandChain', ctx);
    assert.strictEqual(JSON.parse(requests[1].body).active, false);
    assert.strictEqual(requests[1].keepalive, true);
    events.keydown(event('Alt'));
    windowEvents.blur();
    assert.strictEqual(timers.size, 0, 'blur bekleyen kaydi iptal etmeli');
    events.keydown(event('Alt'));
    const fireUnload = [...timers.values()][0]; timers.clear(); fireUnload();
    await vm.runInContext('altPttCommandChain', ctx);
    const activeId = JSON.parse(requests.at(-1).body).recording_id;
    const beforeUnloadCount = requests.length;
    windowEvents.beforeunload();
    assert.strictEqual(requests.length, beforeUnloadCount + 1, 'Unload iptali Promise zincirini beklememeli');
    const unload = JSON.parse(requests.at(-1).body);
    assert.strictEqual(unload.recording_id, activeId);
    assert.strictEqual(unload.discard, true);
    await vm.runInContext('altPttCommandChain', ctx);
}
pttTest().then(() => console.log('Frontend rapor regresyonlari gecti')).catch(error => {console.error(error); process.exitCode = 1;});
