'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync(path.join(__dirname, 'templates/index.html'), 'utf8');
async function run() {
    // Arama kutusu, tarih ve konuşmacı filtreleri aynı küçük DOM sahtesini kullanır.
    const results = {style: {}, innerHTML: '', value: ''};
    const requests = [];
    const ctx = vm.createContext({document: {getElementById: () => results}, URLSearchParams,
        escapeHtml: String, console, showAlert() {},
        fetch() {return new Promise(resolve => requests.push(resolve));}});
    const start = html.indexOf('        let _searchGeneration = 0;');
    const end = html.indexOf('        // Durum güncelle', start);
    vm.runInContext(html.slice(start, end), ctx);
    const old = ctx.searchFullTranscriptHistory('old');
    const latest = ctx.searchFullTranscriptHistory('new');
    requests[1]({json: async () => ({transcriptions: [{text: 'new result'}]})});
    await latest;
    requests[0]({json: async () => ({transcriptions: [{text: 'old result'}]})});
    await old;
    assert(results.innerHTML.includes('new result'));
    assert(!results.innerHTML.includes('old result'));
    const pending = ctx.searchFullTranscriptHistory('old');
    await ctx.searchFullTranscriptHistory('');
    requests[2]({json: async () => ({transcriptions: [{text: 'old result'}]})});
    await pending;
    assert.strictEqual(results.style.display, 'none');
    const object = {}; object[123] = 'test';
    assert(object.hasOwnProperty('123')); delete object['123'];
    assert.strictEqual(Object.keys(object).length, 0);
    let timeout;
    const button = {disabled: false, textContent: 'Answer', style: {}};
    const ai = vm.createContext({window: {}, AbortController, console,
        document: {getElementById: () => ({value: 'ja'})},
        getSelectedTargetLanguageLabel: () => 'Japanese', showAlert() {},
        setTimeout(fn, milliseconds) {assert.strictEqual(milliseconds, 60000); timeout = fn; return 1;},
        clearTimeout() {},
        fetch(_url, options) {return new Promise((_resolve, reject) => {
            options.signal.addEventListener('abort', () => reject(Object.assign(new Error('timeout'), {name: 'AbortError'})));
        });}});
    const aiStart = html.indexOf('        async function getAIResponse(id,');
    const aiEnd = html.indexOf('        // Hem nihai HTTP', aiStart);
    vm.runInContext(html.slice(aiStart, aiEnd), ai);
    const call = ai.getAIResponse(1, 'Hello', 'answer', button);
    assert.strictEqual(button.disabled, true);
    timeout();
    await call;
    assert.strictEqual(button.disabled, false);
    assert.strictEqual(button.textContent, 'Answer');
    assert.strictEqual(Object.keys(ai.window._pendingAiRequests).length, 0);
    assert.strictEqual(Object.keys(ai.window._activeAnswerRequests).length, 0);
    console.log('Arama siralamasi ve nesne anahtari testleri gecti');
}
run().catch(error => {console.error(error); process.exitCode = 1;});
