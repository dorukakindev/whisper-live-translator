'use strict';
// HTML attribute parser'i ve JS calistirmasini ayri katmanlarda gercekten dene.
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const {spawnSync} = require('child_process');
const html = fs.readFileSync(path.join(__dirname, 'templates/index.html'), 'utf8');
const from = html.indexOf('        function escapeJsString(');
const to = html.indexOf('        function getSelectedTargetLanguageLabel(', from);
const ctx = vm.createContext({});
vm.runInContext(html.slice(from, to), ctx);
const values = ['Test &apos; end', 'It\'s a test', 'Test &quot; end', '&amp;apos;', '&#39;); injected = true; //', '\\"\n\r', '\u2028\u2029', '<tag>', '東京'];
const buttons = values.map(value => `<button onclick="capture('${ctx.escapeJsString(value)}')">x</button>`).join('');
const parser = `import sys,json
from html.parser import HTMLParser
class Parser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'button': self.handlers.append(dict(attrs)['onclick'])
p=Parser(); p.handlers=[]; p.feed(sys.stdin.read()); print(json.dumps(p.handlers))`;
const parsed = spawnSync(path.join(__dirname, '.venv/Scripts/python.exe'), ['-X', 'utf8', '-c', parser], {input: buttons, encoding: 'utf8'});
assert.strictEqual(parsed.status, 0, parsed.error ? parsed.error.message : parsed.stderr);
const handlers = JSON.parse(parsed.stdout);
assert.strictEqual(handlers.length, values.length);
handlers.forEach((handler, index) => {
    let received;
    const sandbox = vm.createContext({capture(value) {received = value;}, injected: false});
    vm.runInContext(handler, sandbox);
    assert.strictEqual(sandbox.injected, false);
    assert.strictEqual(received, values[index]);
});
const mergeFrom = html.indexOf('        function mergeUniqueAnswerOptions(');
const mergeTo = html.indexOf('        let _hydrationInFlight', mergeFrom);
const mergeContext = vm.createContext({});
vm.runInContext(html.slice(mergeFrom, mergeTo), mergeContext);
const merged = mergeContext.mergeUniqueAnswerOptions(
    [{translation: 'Café'}, {translation: '東京'}],
    [{translation: 'Cafe\u0301'}, {translation: '大阪'}, {translation: '東京'}]
);
assert.deepStrictEqual(Array.from(merged, option => option.translation), ['Café', '東京', '大阪']);
console.log('HTML entity / onclick round-trip testleri gecti');
