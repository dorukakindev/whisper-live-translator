'use strict';

// Ağ gecikmesi, sıfırlama ve kullanıcı yeni soru yazarken yanıt gelmesi.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('templates/index.html', 'utf8');
const start = html.indexOf('        let _aiChatRequest = null;');
const end = html.indexOf('        function regenerateAnswer(', start);
assert(start > 0 && end > start);
const nodes = {};
for (const id of ['aiQuestionInput', 'aiChatResult', 'aiChatResultHeader', 'aiChatResultText', 'summaryBtn', 'aiAskBtn']) {
    nodes[id] = {value:'İlk soru', textContent:'', disabled:false, setAttribute(){},
        classList:{add(){}, remove(){}}};
}
let requests = [], timeout, hasTranscript = true;
const ctx = vm.createContext({
    document: {getElementById:id => nodes[id], querySelector:() => hasTranscript ? {} : null},
    AbortController, console,
    setTimeout:fn => {timeout = fn; return 1;}, clearTimeout(){}, showAlert(){},
    fetch:(_url, options) => new Promise((resolve, reject) => {
        requests.push({resolve, options});
        options.signal.addEventListener('abort', () => reject(Object.assign(new Error(), {name:'AbortError'})));
    })
});
vm.runInContext(html.slice(start, end), ctx);
const result = text => ({ok:true,json:async() => ({success:true,response:text})});

(async () => {
    const first = ctx.askQuestion();
    await ctx.getSummary();
    assert.strictEqual(requests.length, 1, 'Özet ve soru aynı anda gönderilmemeli');
    assert(nodes.aiAskBtn.disabled && nodes.summaryBtn.disabled);
    nodes.aiQuestionInput.value = 'Yeni sorum';
    requests[0].resolve(result('İlk yanıt'));
    await first;
    assert.strictEqual(nodes.aiQuestionInput.value, 'Yeni sorum', 'Yeni taslak korunmalı');
    assert.strictEqual(nodes.aiChatResultText.textContent, 'İlk yanıt');
    assert(!nodes.aiAskBtn.disabled && !nodes.summaryBtn.disabled);

    const stale = ctx.askQuestion();
    ctx.invalidateAiChat();
    const fresh = ctx.getSummary();
    requests[1].resolve(result('Eski yanıt'));
    await stale;
    assert(nodes.aiAskBtn.disabled, 'Eski isteğin finally bloğu yeni kilidi açmamalı');
    assert.strictEqual(nodes.aiChatResultText.textContent, '');
    requests[2].resolve(result('Yeni özet'));
    await fresh;
    assert.strictEqual(nodes.aiChatResultText.textContent, 'Yeni özet');

    const slow = ctx.askQuestion();
    timeout();
    await slow;
    assert(nodes.aiChatResultText.textContent.includes('süresi doldu'));
    assert(!nodes.aiAskBtn.disabled);
    hasTranscript = false;
    await ctx.getSummary();
    assert.strictEqual(requests.length, 4, 'Geçici önizleme özet isteği başlatmamalı');
    console.log('AI sohbet eşzamanlılık, taslak koruma, sıfırlama ve timeout testleri geçti');
})().catch(error => {console.error(error); process.exitCode = 1;});
