'use strict';

const path = require('path');

function normalizeCommandLine(value) {
    return String(value || '').replace(/\\/g, '/').toLowerCase();
}

function isOwnedWhisperBackend(commandLine, appDir) {
    const normalized = normalizeCommandLine(commandLine);
    const expectedScript = normalizeCommandLine(path.resolve(appDir, 'buyedektir.py'));
    const hasScriptName = /(?:^|[\s"'])[^\s"']*buyedektir\.py(?:[\s"']|$)/.test(normalized);
    return normalized.includes('--whisper-electron-child')
        && (normalized.includes(expectedScript) || hasScriptName);
}

function isExpectedBackendResponse(statusCode, payload, expectedNonce) {
    return statusCode === 200
        && Boolean(payload)
        && payload.backend_nonce === expectedNonce;
}

function listeningPidFromNetstat(line, port) {
    const parts = line.trim().split(/\s+/);
    // Durum etiketi Windows diline baglidir; TCP dinleyicinin uzak ucu sifirdir.
    if (parts.length !== 5 || parts[0].toUpperCase() !== 'TCP'
        || !parts[1].endsWith(`:${port}`)
        || !['0.0.0.0:0', '[::]:0'].includes(parts[2])
        || !/^[1-9]\d*$/.test(parts[4])) return null;
    return parts[4];
}

function restrictWindowNavigation(contents, appUrl) {
    const origin = new URL(appUrl).origin;
    const guard = (event, url) => {
        try {
            const target = new URL(url);
            if (target.origin === origin && !target.username && !target.password) return;
        } catch (_) { /* Gecersiz adres de engellenir. */ }
        event.preventDefault();
    };
    contents.on('will-navigate', guard);
    contents.on('will-redirect', guard);
    contents.setWindowOpenHandler(() => ({ action: 'deny' }));
}

module.exports = {
    isOwnedWhisperBackend,
    isExpectedBackendResponse,
    listeningPidFromNetstat,
    restrictWindowNavigation,
};
