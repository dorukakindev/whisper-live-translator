'use strict';
const assert = require('assert');
const vm = require('vm');
const fs = require('fs');
const source = fs.readFileSync('static/cockpit.js', 'utf8');
const attrs = {};
const button = {disabled:false, textContent:'', setAttribute:(k,v)=>attrs[k]=v, removeAttribute:k=>delete attrs[k]};
const actions = [];
let finish, requests=0, fail=false, refreshed=0;
const ctx = vm.createContext({document:{getElementById:()=>button}, AbortController, setTimeout, clearTimeout,
    window:{electronAPI:{overlayControl: async action=>{actions.push(action);return {success:true};}}},
    showAlert(){}, hydrateRuntimeSettings:()=>{refreshed++;},
    fetch:async (_url, options)=>{requests++;const enabled=JSON.parse(options.body).enabled;
        if(fail) throw Error('offline');
        if(enabled) await new Promise(resolve=>{finish=resolve;});
        return {ok:true,json:async()=>({success:true,settings:{game_mode:enabled}})};},
});
vm.runInContext(source.slice(0,source.indexOf('async function openGameOverlay()')),ctx);
ctx.applyRuntimeSettings = settings=>ctx.renderGameMode(settings);
(async()=>{
    const opening=ctx.toggleGameMode();
    await new Promise(resolve=>setImmediate(resolve));
    await ctx.toggleGameMode();
    assert.strictEqual(requests,1); assert(button.disabled);
    finish(); await opening;
    assert.strictEqual(attrs['aria-pressed'],'true'); assert(!button.disabled);
    await ctx.toggleGameMode();
    assert.strictEqual(attrs['aria-pressed'],'false'); assert(actions.includes('close'));
    fail=true; await ctx.toggleGameMode();
    assert.strictEqual(attrs['aria-pressed'],'false'); assert(!button.disabled); assert.strictEqual(refreshed,1);
    console.log('Oyun modu aç/kapat, çift tıklama ve hata toparlama testleri geçti');
})().catch(error=>{console.error(error);process.exitCode=1;});
