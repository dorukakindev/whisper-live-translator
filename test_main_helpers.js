'use strict';

const assert = require('assert');
const path = require('path');
const {
    isOwnedWhisperBackend,
    isExpectedBackendResponse,
    listeningPidFromNetstat,
    restrictWindowNavigation,
} = require('./main_helpers');

const appDir = path.resolve(__dirname);
const script = path.join(appDir, 'buyedektir.py');

assert.strictEqual(
    isOwnedWhisperBackend(`python.exe "${script}" --whisper-electron-child`, appDir),
    true,
    'Whisper child komut satiri taninmadi',
);
assert.strictEqual(
    isOwnedWhisperBackend('python.exe other_project.py --port 5000', appDir),
    false,
    'Yabanci Python sureci Whisper child sanildi',
);
assert.strictEqual(
    isOwnedWhisperBackend(`python.exe "${script}"`, appDir),
    false,
    'Sahiplik isareti olmayan eski/yabanci Python sureci oldurulebilir',
);

assert.strictEqual(isExpectedBackendResponse(200, { backend_nonce: 'a' }, 'a'), true);
assert.strictEqual(isExpectedBackendResponse(200, { backend_nonce: 'old' }, 'new'), false);
assert.strictEqual(isExpectedBackendResponse(500, { backend_nonce: 'a' }, 'a'), false);
assert.strictEqual(isExpectedBackendResponse(200, null, 'a'), false);

for (const label of ['LISTENING', 'DINLENIYOR', 'ABHOREN']) {
    assert.strictEqual(listeningPidFromNetstat(`TCP 127.0.0.1:5000 0.0.0.0:0 ${label} 123`, 5000), '123');
    assert.strictEqual(listeningPidFromNetstat(`TCP [::]:5000 [::]:0 ${label} 123`, 5000), '123');
}
for (const line of [
    'TCP 127.0.0.1:50000 0.0.0.0:0 LISTENING 123',
    'TCP 127.0.0.1:5010 127.0.0.1:5000 ESTABLISHED 123',
    'TCP 127.0.0.1:5000 127.0.0.1:7777 ESTABLISHED 123',
    'UDP 127.0.0.1:5000 *:* 123',
    'TCP 127.0.0.1:5000 0.0.0.0:0 LISTENING 0',
    'TCP 127.0.0.1:5000 0.0.0.0:0 LISTENING 123&bad',
]) assert.strictEqual(listeningPidFromNetstat(line, 5000), null);

const events = new Map();
let popup;
restrictWindowNavigation({
    on: (name, handler) => events.set(name, handler),
    setWindowOpenHandler: handler => { popup = handler; },
}, 'http://localhost:5000');
for (const name of ['will-navigate', 'will-redirect']) {
    for (const url of ['http://localhost:5000/', 'http://localhost:5000/overlay#test']) {
        events.get(name)({ preventDefault: () => assert.fail('Yerel sayfa engellendi') }, url);
    }
    for (const url of ['https://example.com', 'http://localhost:50000', 'http://localhost.evil:5000',
        'http://localhost:5000@evil.test', 'http://user@localhost:5000', 'file:///test', 'data:text/html,test', 'invalid']) {
        let prevented = false;
        events.get(name)({ preventDefault: () => { prevented = true; } }, url);
        assert(prevented, url);
    }
}
assert.deepStrictEqual(popup({ url: 'http://localhost:5000/' }), { action: 'deny' });
console.log('main_helpers testleri gecti');
