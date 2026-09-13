'use strict';

// Cockpit durum/klavye akisinin API veya Electron olmadan sentetik regresyon testi.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync('templates/index.html', 'utf8');
const cockpit = fs.readFileSync('static/cockpit.js', 'utf8');
const readingMode = fs.readFileSync('static/reading-mode.js', 'utf8');
const appSource = html + cockpit + readingMode;

assert(html.includes('id="cockpitFlowState"'));
assert(html.includes('id="cockpitLatencyState"'));
assert(html.includes('class="answer-option-toggle"'));
assert(appSource.includes('class="reply-read-button"'));
assert(appSource.includes("if (e.key === 'Escape')"));
assert(!appSource.includes('_cockpitStatusInterval'));

const values = {
    connectionState: {textContent: 'Bağlı'},
    statusText: {textContent: 'Model hazır'},
    cockpitFlowState: {textContent: '', dataset: {}}, cockpitConnectionState: {textContent: '', dataset: {}},
    cockpitTargetLanguage: {textContent: '', dataset: {}}, cockpitCaptureState: {textContent: '', dataset: {}},
    cockpitLatencyState: {textContent: '', dataset: {}},
    aiTargetLang: {selectedOptions: [{textContent: '🇯🇵 Japonca'}]},
    captureModeSelect: {value: 'system'}
};
const ctx = vm.createContext({
    document: {getElementById: id => values[id]},
    isCapturing: false, isPaused: false, _socketConnected: false, _cockpitStats: null,
    console
});
const start = cockpit.indexOf('function setCockpitValue(');
const end = cockpit.indexOf('function toggleControlPanel()', start);
assert(start >= 0 && end > start);
vm.runInContext(cockpit.slice(start, end), ctx);
ctx.updateCockpitStatus();
assert.strictEqual(values.cockpitFlowState.textContent, 'Model hazır');
assert.strictEqual(values.cockpitTargetLanguage.textContent, '🇯🇵 Japonca');
assert.strictEqual(values.cockpitConnectionState.textContent, 'Bağlı değil');
assert.strictEqual(values.cockpitLatencyState.textContent, 'Veri yok');

ctx.isCapturing = true;
ctx.updateCockpitStatus();
assert.strictEqual(values.cockpitFlowState.textContent, 'Konuşmayı dinliyor');
assert.strictEqual(values.cockpitCaptureState.textContent, 'Sistem sesi · dinleniyor');
ctx.isPaused = true;
ctx.updateCockpitStatus();
assert.strictEqual(values.cockpitFlowState.textContent, 'Akış bekletildi');
assert.strictEqual(values.cockpitCaptureState.textContent, 'Sistem sesi · bekletildi');
ctx._socketConnected = true;
ctx._cockpitStats = {asr: '120 ms', translation: '—', queue: 0};
ctx.updateCockpitStatus();
assert.strictEqual(values.cockpitConnectionState.textContent, 'Bağlı');
assert.strictEqual(values.cockpitLatencyState.textContent, '● Hızlı · p95 120 ms');
assert.strictEqual(values.cockpitLatencyState.dataset.state, 'active');
ctx._cockpitStats = {asr: '2.1 sn', translation: '—', queue: 0};
ctx.updateCockpitStatus();
assert.strictEqual(values.cockpitLatencyState.textContent, '◆ Orta · p95 2100 ms');
assert.strictEqual(values.cockpitLatencyState.dataset.state, 'warn');
ctx._cockpitStats = {asr: '3.2 sn', translation: '—', queue: 0};
ctx.updateCockpitStatus();
assert.strictEqual(values.cockpitLatencyState.textContent, '▲ Yavaş · p95 3200 ms');
assert.strictEqual(values.cockpitLatencyState.dataset.state, 'error');
console.log('Cockpit durum ve semantik sozlesme testleri gecti');
