'use strict';

// Cockpit'in saf sahiplik kurallarını gerçek uygulama fonksiyonlarıyla sınar.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const cockpit = fs.readFileSync('static/cockpit.js', 'utf8');
function section(start, end) {
    const a = cockpit.indexOf(start), b = cockpit.indexOf(end, a + start.length);
    assert(a >= 0 && b > a, start); return cockpit.slice(a, b);
}

const nodes = new Map();
let textWrites = 0;
function node(id) {
    if (!nodes.has(id)) {
        let text = '';
        nodes.set(id, {id, innerHTML:'', dataset:{}, querySelector(){return null;},
            get textContent(){return text;}, set textContent(value){textWrites++; text=String(value);}});
    }
    return nodes.get(id);
}
const document = {
    activeElement: null,
    getElementById: id => node(id),
    querySelector: () => null,
    querySelectorAll: () => []
};
const ctx = vm.createContext({
    document, window:{_pendingAiRequests:{x:1},_activeAnswerRequests:{y:2}},
    transcriptionTexts:{A:'Mesaj A',B:'Mesaj B'}, _replyTargetId:null, _replyTargetText:'', _replyGeneration:0,
    escapeHtml:s=>String(s), escapeJsString:s=>String(s), CSS:{escape:String}, console,
    mergeUniqueAnswerOptions:(a,b)=>b
});
vm.runInContext(section('function setCockpitValue(', '// 1-4 tuslari'), ctx);

ctx.selectReplyTarget('A','Mesaj A',true);
const genA = ctx._replyGeneration;
ctx.selectReplyTarget('B','Mesaj B',true);
assert(ctx._replyGeneration > genA);
ctx.renderReplyCockpit('A',[{translation:'Gecikmiş A',romanized:'A'}],'ja','Japonca',false);
assert(!node('replyCockpitOptions').innerHTML.includes('Gecikmiş A'));
ctx.renderReplyCockpit('B',[{translation:'B yanıtı',turkish:'B anlamı',romanized:'Be okunuş'}],'ja','Japonca',true);
assert(node('replyCockpitOptions').innerHTML.includes('Be okunuş'));
ctx.renderReplyCockpit('B',[{translation:'B yanıtı',turkish:'B anlamı',romanized:'Be okunuş'}],'ja','Japonca',false);
assert.strictEqual((node('replyCockpitOptions').innerHTML.match(/reply-option-card/g)||[]).length,1);
ctx.invalidateReplyCockpit('Geçmiş temizlendi.');
assert.strictEqual(ctx._replyTargetId,null);
assert.strictEqual(Object.keys(ctx.window._pendingAiRequests).length,0);
assert.strictEqual(Object.keys(ctx.window._activeAnswerRequests).length,0);

const keyA = ctx.answerStableKey({translation:'İYİ günler!',romanized:'i-yi'});
const keyB = ctx.answerStableKey({translation:'İYİ günler!',romanized:'i-yi'});
assert.strictEqual(keyA,keyB);
const writesBefore = textWrites;
for (let i=0; i<10000; i++) ctx.setCockpitValue('replyCockpitProgress','Hazır','active');
assert.strictEqual(textWrites-writesBefore,1,'degismeyen aria/status metni tekrar yazilmamali');
ctx.selectReplyTarget('B','Mesaj B',true);
for (let i=0; i<1000; i++) ctx.renderReplyCockpit('B',Array.from({length:8},(_,n)=>({translation:`Yanıt ${n}`,romanized:`Okunuş ${n}`})),'ja','Japonca',false);
assert((node('replyCockpitOptions').innerHTML.match(/reply-option-card/g)||[]).length<=4);
console.log('Cockpit sahiplik, stale/temizleme, kararlı kimlik ve hızlandırılmış yük testleri geçti');
