"use strict";

// Büyük punto okuma diyaloğu ve erişilebilir klavye odağı.
// --- Okuma modu: okunusu buyuk puntoyla tam ekran goster ---
function openReadingMode(okunus, translation, meaning, lang) {
    let ov = document.getElementById('readingOverlay');
    if (!ov?.classList.contains('visible')) _readingModeOpener = document.activeElement;
    if (!ov) {
        ov = document.createElement('div');
        ov.id = 'readingOverlay';
        ov.className = 'reading-overlay';
        ov.setAttribute('role', 'dialog');
        ov.setAttribute('aria-modal', 'true');
        ov.setAttribute('aria-labelledby', 'readingModeTitle');
        ov.addEventListener('click', (e) => {
            if (e.target === ov) closeReadingMode();
        });
        document.body.appendChild(ov);
    }
    if (!ov.classList.contains('visible')) {
        ov.dataset.openerKey = _readingModeOpener?.closest?.('.reply-option-card')?.dataset.answerKey || '';
    }
    const savedScale = Number(whisperStorage.getItem('readingFontScale'));
    _readingFontScale = Number.isFinite(savedScale) && savedScale >= 0.7 && savedScale <= 1.6 ? savedScale : 1;
    window.speechSynthesis?.cancel();
    // ' / ' nefes bolmelerini ayri satirlara cevir: okumasi daha rahat
    const lines = String(okunus || '').split(/\s*\/\s*/).filter(Boolean);
    ov.innerHTML = `
        <div class="reading-dialog">
            <div class="reading-toolbar">
                <h2 id="readingModeTitle">Okuma modu</h2>
                <div>
                    <button type="button" aria-label="Okunuş yazısını küçült" onclick="changeReadingFont(-0.1)">A−</button>
                    <button type="button" aria-label="Okunuş yazısını büyüt" onclick="changeReadingFont(0.1)">A+</button>
                    <button type="button" class="reading-close-btn" aria-label="Okuma modunu kapat" onclick="closeReadingMode()">Kapat</button>
                </div>
            </div>
            <div class="reading-okunus" tabindex="0" style="--reading-scale: ${_readingFontScale.toFixed(1)}">${lines.map(l => escapeHtml(l)).join('<br>')}</div>
            ${translation ? `<div class="reading-translation">${escapeHtml(translation)}</div>` : ''}
            ${meaning ? `<div class="reading-meaning">${escapeHtml(meaning)}</div>` : ''}
            ${translation ? `<div class="reading-audio-actions">
                <button type="button" class="reading-speak-btn" onclick="speakText('${escapeJsString(translation)}', '${escapeJsString(lang || '')}')">Dinle</button>
                <button type="button" class="reading-speak-btn" onclick="speakText('${escapeJsString(translation)}', '${escapeJsString(lang || '')}', 0.65)">Yavaş dinle</button>
                <button type="button" class="reading-speak-btn" onclick="window.speechSynthesis?.cancel()">Sesi durdur</button>
            </div>` : ''}
            <div class="reading-hint">1–4 ile seçenek değiştir · Esc ile kapat</div>
        </div>
    `;
    ov.classList.add('visible');
    document.body.classList.add('reading-mode-open');
    ov.querySelector('.reading-close-btn')?.focus();
}

function changeReadingFont(delta) {
    const change = Number(delta);
    if (!Number.isFinite(change)) return;
    _readingFontScale = Math.round(Math.min(1.6, Math.max(0.7, _readingFontScale + change)) * 10) / 10;
    whisperStorage.setItem('readingFontScale', _readingFontScale.toFixed(1));
    const text = document.querySelector('#readingOverlay .reading-okunus');
    if (text) text.style.setProperty('--reading-scale', _readingFontScale.toFixed(1));
}

function closeReadingMode() {
    const ov = document.getElementById('readingOverlay');
    if (!ov || !ov.classList.contains('visible')) return;
    window.speechSynthesis?.cancel();
    ov.classList.remove('visible');
    document.body.classList.remove('reading-mode-open');
    if (_readingModeOpener && _readingModeOpener.isConnected && typeof _readingModeOpener.focus === 'function') {
        _readingModeOpener.focus();
    } else {
        // Kısmi cevap akışı kartı yeniden oluşturmuş olabilir.
        const replacement = ov.dataset.openerKey
            ? document.querySelector(`[data-answer-key="${CSS.escape(ov.dataset.openerKey)}"] .reply-read-button`)
            : null;
        (replacement || document.getElementById('controlsToggleBtn'))?.focus();
    }
    _readingModeOpener = null;
}

document.addEventListener('keydown', (e) => {
    const ov = document.getElementById('readingOverlay');
    if (!ov?.classList.contains('visible')) return;
    if (e.key === 'Escape') {
        e.preventDefault();
        closeReadingMode();
        return;
    }
    if (e.key !== 'Tab') return;
    const focusable = Array.from(ov.querySelectorAll('button, [tabindex]:not([tabindex="-1"])'))
        .filter(el => !el.disabled && el.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
        e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault(); first.focus();
    }
});
