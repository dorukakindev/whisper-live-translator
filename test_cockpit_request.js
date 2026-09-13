'use strict';

// AI istek yasam dongusunu gercek uygulama fonksiyonuyla, dis ag olmadan sinar.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const html = fs.readFileSync('templates/index.html', 'utf8');
const start = html.indexOf('        async function getAIResponse(');
const end = html.indexOf('        // Hem nihai HTTP yanıtı', start);
assert(start >= 0 && end > start, 'getAIResponse bulunamadi');
const modelStart = html.indexOf('        async function loadSelectedModel()');
const modelEnd = html.indexOf('        // Yüklü modelleri kontrol et', modelStart);
assert(modelStart >= 0 && modelEnd > modelStart, 'loadSelectedModel bulunamadi');

function button() {
    return {disabled:false, textContent:'Cevapla', style:{display:''}};
}

async function runCase(fetchImpl, timerImpl) {
    const alerts = [];
    const renders = [];
    const nodes = {
        aiTargetLang: {value:'ja'},
        aiResponseTone: {value:'arkadasca'}
    };
    const ctx = vm.createContext({
        window:{_activeAnswerRequests:{},_pendingAiRequests:{}},
        document:{getElementById:id=>nodes[id]},
        performance:{now:()=>100}, Date, Math, JSON, console,
        AbortController, fetch:fetchImpl,
        setTimeout:timerImpl || setTimeout,
        clearTimeout:id => { if (typeof id === 'object') clearTimeout(id); },
        _replyGeneration:0,
        getSelectedTargetLanguageLabel:()=> 'Japonca',
        renderAiResult:(...args)=>renders.push(args),
        showAlert:(message,type)=>alerts.push({message,type})
    });
    ctx.selectReplyTarget = () => { ctx._replyGeneration += 1; };
    vm.runInContext(html.slice(start, end), ctx);
    const control = button();
    await ctx.getAIResponse('T1','Sentetik mesaj','answer',control);
    assert.strictEqual(Object.keys(ctx.window._pendingAiRequests).length,0,'pending istek temizlenmeli');
    assert.strictEqual(Object.keys(ctx.window._activeAnswerRequests).length,0,'sahiplik kaydi temizlenmeli');
    return {alerts,renders,control};
}

(async () => {
    const modelAlerts = [];
    const modelCard = {classList:{add(){},remove(){},contains(){return false;}}};
    const modelNodes = {
        useCpuToggle:{checked:false}, downloadProgress:{classList:{add(){},remove(){}}},
        statusText:{textContent:''}, statusDot:{className:''}, startBtn:{disabled:true}
    };
    const modelCtx = vm.createContext({
        selectedModel:'small', JSON, console,
        document:{
            querySelector:selector => selector === '[data-model="small"]' ? modelCard : null,
            getElementById:id => modelNodes[id]
        },
        fetch:async()=>({json:async()=>({success:true,device:'cpu'})}),
        showAlert:(message,type)=>modelAlerts.push({message,type})
    });
    vm.runInContext(html.slice(modelStart, modelEnd), modelCtx);
    await modelCtx.loadSelectedModel();
    assert(modelAlerts.some(a=>a.type==='success' && a.message.includes('small')),
        'model yukleme basarisi request kimliginden bagimsiz olmali');
    assert.strictEqual(modelNodes.startBtn.disabled,false);

    const empty = await runCase(async () => ({json:async()=>({success:true,options:[]})}));
    assert.strictEqual(empty.renders.length,1,'bos basarili yanit render yoluna gitmeli');
    assert.strictEqual(empty.renders[0][2].options.length,0);
    assert.strictEqual(empty.renders[0][2].client_final_ms,0,
        'nihai istemci suresi AI cevap akisinda hesaplanmali');

    const apiError = await runCase(async () => ({json:async()=>({success:false,error:'Sentetik API hatasi'})}));
    assert(apiError.alerts.some(a=>a.message==='Sentetik API hatasi'));
    assert.strictEqual(apiError.control.disabled,false);
    assert.strictEqual(apiError.control.textContent,'Cevapla');

    let timeoutCallback;
    const timedOut = await runCase((url, options) => new Promise((resolve,reject) => {
        options.signal.addEventListener('abort',()=>reject(Object.assign(new Error('aborted'),{name:'AbortError'})));
        queueMicrotask(()=>timeoutCallback());
    }), callback => { timeoutCallback=callback; return 1; });
    assert(timedOut.alerts.some(a=>a.message.includes('zaman aşımına')));
    assert.strictEqual(timedOut.control.disabled,false);

    console.log('Model yükleme ile Cockpit boş sonuç, API hata, timeout ve istek temizleme testleri geçti');
})().catch(error => { console.error(error); process.exit(1); });
