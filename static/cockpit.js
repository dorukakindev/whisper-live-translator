"use strict";

// Cevap kokpiti ve klavye akışı; index.html global durum sözleşmesini kullanır.
function setCockpitValue(id, text, state = '') {
    const el = document.getElementById(id);
    if (!el) return;
    if (el.textContent !== text) el.textContent = text;
    if (el.dataset.state !== state) el.dataset.state = state;
}

// Karar, kullaniciya gosterilen metni ayrıştırmaz; socket ve runtime
// durumunun kendisini kullanir. Boylece "Baglaniyor" yanlislikla yesil olmaz.
function updateCockpitStatus() {
    const backend = document.getElementById('statusText');
    const backendText = String(backend?.textContent || 'Hazır').trim();
    const active = Boolean(isCapturing);
    const mode = document.getElementById('captureModeSelect')?.value === 'mic' ? 'Mikrofon' : 'Sistem sesi';
    setCockpitValue('cockpitConnectionState', _socketConnected ? 'Bağlı' : 'Bağlı değil', _socketConnected ? 'active' : 'error');
    setCockpitValue('cockpitCaptureState', active ? `${mode} · ${isPaused ? 'bekletildi' : 'dinleniyor'}` : `${mode} · kapalı`, active && !isPaused ? 'active' : (isPaused ? 'warn' : ''));
    setCockpitValue('cockpitFlowState', active ? (isPaused ? 'Akış bekletildi' : 'Konuşmayı dinliyor') : backendText, active && !isPaused ? 'active' : (isPaused ? 'warn' : ''));
    const target = document.getElementById('aiTargetLang');
    setCockpitValue('cockpitTargetLanguage', target?.selectedOptions?.[0]?.textContent?.trim() || 'Otomatik');
    const stats = _cockpitStats;
    const forcedLag = (
        typeof _laggingUntil !== 'undefined' && Date.now() < _laggingUntil
    ) || Boolean(stats?.queue > 0);
    const latencyToMs = value => {
        const text = String(value || '');
        const number = Number.parseFloat(text.replace(',', '.'));
        if (!Number.isFinite(number)) return 0;
        return /sn\b/.test(text) ? number * 1000 : number;
    };
    const measuredWorst = Number(stats?.worstMs);
    const worstMs = Number.isFinite(measuredWorst)
        ? measuredWorst
        : Math.max(latencyToMs(stats?.asr), latencyToMs(stats?.translation));
    const latencyState = !stats ? 'warn' : (forcedLag || worstMs >= 3000
        ? 'error' : (worstMs >= 1000 ? 'warn' : 'active'));
    const healthLabel = !stats ? 'Veri yok' : (latencyState === 'error'
        ? 'Yavaş' : (latencyState === 'warn' ? 'Orta' : 'Hızlı'));
    const latencyText = !stats ? healthLabel
        : `${latencyState === 'error' ? '▲' : (latencyState === 'warn' ? '◆' : '●')} ${healthLabel} · p95 ${Math.round(worstMs)} ms`;
    setCockpitValue('cockpitLatencyState', latencyText, latencyState);
    const latencyEl = document.getElementById('cockpitLatencyState');
    if (latencyEl && stats) {
        latencyEl.title = `ASR p95 ${stats.asr} · Çeviri p95 ${stats.translation} · Kuyruk ${stats.queue}`;
    }
    const details = document.getElementById('cockpitLatencyDetails');
    if (details) {
        details.textContent = stats
            ? `ASR p95: ${stats.asr}. Çeviri p95: ${stats.translation}. Bekleyen ses: ${stats.queue}.`
            : 'Henüz gecikme ölçümü yok.';
    }
}

function toggleLatencyDetails() {
    const trigger = document.getElementById('cockpitLatencyState');
    const details = document.getElementById('cockpitLatencyDetails');
    if (!trigger || !details) return;
    const opening = details.hidden;
    details.hidden = !opening;
    trigger.setAttribute('aria-expanded', String(opening));
}

document.getElementById('cockpitLatencyState')?.addEventListener?.('click', toggleLatencyDetails);

function toggleControlPanel() {
    const collapsed = document.body.classList.toggle('controls-collapsed');
    const button = document.getElementById('controlsToggleBtn');
    if (button) {
        button.setAttribute('aria-expanded', String(!collapsed));
        button.title = collapsed ? 'Ayar panelini aç' : 'Ayar panelini daralt';
    }
    whisperStorage.setItem('controlsCollapsed', collapsed ? 'true' : 'false');
}

function answerStableKey(option) {
    return [option.romanized, option.translation, option.turkish]
        .map(value => String(value || '').normalize('NFC').trim().toLocaleLowerCase('tr-TR'))
        .join('|');
}

function selectReplyTarget(id, text, reset = false) {
    const nextId = String(id);
    if (reset || _replyTargetId !== nextId) {
        _replyGeneration++;
        document.getElementById('replyCockpitOptions').innerHTML = '<div class="reply-cockpit-empty">Cevaplar hazırlanıyor.</div>';
    }
    _replyTargetId = nextId;
    _replyTargetText = String(text || transcriptionTexts[id] || '').trim();
    setCockpitValue('replyCockpitSource', _replyTargetText || `Transkript ${nextId}`);
    setCockpitValue('replyCockpitProgress', 'Hazırlanıyor');
}

function invalidateReplyCockpit(message = 'Bir transkript seçin.') {
    _replyGeneration++;
    _replyTargetId = null;
    _replyTargetText = '';
    window._pendingAiRequests = {};
    window._activeAnswerRequests = {};
    setCockpitValue('replyCockpitSource', message);
    setCockpitValue('replyCockpitProgress', '');
    const options = document.getElementById('replyCockpitOptions');
    if (options) options.innerHTML = '<div class="reply-cockpit-empty">Henüz seçili bir konuşma yok.</div>';
}

function renderReplyCockpit(id, options, effectiveLang, langLabel, partial) {
    if (_replyTargetId !== String(id)) return;
    const host = document.getElementById('replyCockpitOptions');
    if (!host) return;
    const previousKey = document.activeElement?.closest?.('.reply-option-card')?.dataset.answerKey || '';
    const unique = mergeUniqueAnswerOptions([], options || []).slice(0, 4);
    if (!unique.length) {
        host.innerHTML = '<div class="reply-cockpit-empty">Kullanılabilir cevap alınamadı.</div>';
        setCockpitValue('replyCockpitProgress', partial ? 'Bekleniyor' : 'Sonuç yok');
        return;
    }
    host.innerHTML = unique.map((opt, idx) => {
        const nativeText = String(opt.translation || opt.turkish || '');
        const meaning = opt.turkish && opt.turkish.trim() !== nativeText.trim() ? opt.turkish : '';
        const pronunciation = String(opt.romanized || nativeText);
        const lang = String(opt.language || effectiveLang || '');
        const key = answerStableKey(opt);
        return `<article class="reply-option-card" data-answer-key="${escapeHtml(key)}">
            <div class="reply-option-topline"><span class="reply-option-number">Seçenek ${idx + 1}</span><span class="reply-option-language">${escapeHtml(langLabel || lang)}</span></div>
            <div class="reply-option-pronunciation">${escapeHtml(pronunciation)}</div>
            <div class="reply-option-native">${escapeHtml(nativeText)}</div>
            ${meaning ? `<div class="reply-option-meaning">${escapeHtml(meaning)}</div>` : ''}
            <div class="reply-option-actions">
                <button type="button" class="reply-read-button" onclick="openReadingMode('${escapeJsString(pronunciation)}','${escapeJsString(nativeText)}','${escapeJsString(meaning)}','${escapeJsString(lang)}')">Okuma modu</button>
                <button type="button" onclick="copyResponseText('${escapeJsString(pronunciation)}')">Okunuşu kopyala</button>
                <button type="button" onclick="speakText('${escapeJsString(nativeText)}','${escapeJsString(lang)}')">Dinle</button>
            </div>
        </article>`;
    }).join('');
    setCockpitValue('replyCockpitProgress', partial ? 'Diğer seçenekler hazırlanıyor' : `${unique.length} seçenek hazır`);
    if (previousKey) host.querySelector(`[data-answer-key="${CSS.escape(previousKey)}"] .reply-read-button`)?.focus();
}

// 1-4 tuslari yalniz gorunur cevap kokpitindeki okuma dugmelerini acar.
document.addEventListener('keydown', (e) => {
    const ae = document.activeElement;
    const tag = (ae && ae.tagName ? ae.tagName : '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (ae && ae.isContentEditable)) return;
    if (e.ctrlKey || e.altKey || e.metaKey || e.repeat) return;
    const n = parseInt(e.key, 10);
    if (!n || n < 1 || n > 4) return;
    const button = document.querySelectorAll('#replyCockpitOptions .reply-read-button')[n - 1];
    if (button) { button.click(); e.preventDefault(); }
});

// 'C' tusu: en yeni sistem transkriptinin cevap onerisini fareye dokunmadan
// iste. Temel dongu (mesaj gelir -> oneri iste -> okunusu oku) tek fare
// adimina bagliydi; bu, o adimi klavyeden de acar.
document.addEventListener('keydown', (e) => {
    if (e.key !== 'c' && e.key !== 'C') return;
    const ae = document.activeElement;
    const tag = (ae && ae.tagName ? ae.tagName : '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || (ae && ae.isContentEditable)) return;
    if (e.ctrlKey || e.altKey || e.metaKey) return;
    // Secici SADECE gercek data-transcription-id'li ogelerin icindeki
    // .ai-answer-btn'i bulur; boylece 'partialPreview' (id yok, buton yok)
    // ve mikrofon dikte ogeleri (buton hic basilmaz) otomatik atlanir,
    // en yeni SISTEM transkriptine iner (DOM'da en ustte, en yeni oncelikli).
    const btn = document.querySelector('#transcriptionList .transcription-item[data-transcription-id] .ai-answer-btn');
    if (btn) {
        btn.click();
        e.preventDefault();
    }
});
