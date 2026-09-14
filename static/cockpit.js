"use strict";

// Kullanıcının yazdığı metin yalnız açık sayfada tutulur; yerel depoya kaydedilmez.
let _ownReplyBusy = false;
let _ownMicGeneration = null;
let _readinessSnapshot = {};
let _readinessBusy = false;

async function translateOwnReply() {
    if (_ownReplyBusy) return;
    const input = document.getElementById('ownReplyText');
    const text = input.value.trim();
    const lang = document.getElementById('aiTargetLang').value;
    if (!text || text.length > 2000) {
        setCockpitValue('ownReplyStatus', '1–2000 karakter arasında Türkçe bir cümle yaz.');
        input.setAttribute('aria-invalid', 'true');
        input.focus();
        return;
    }
    if (!lang || lang === 'auto') {
        setCockpitValue('ownReplyStatus', 'Üst şeritten karşı tarafın dilini seç.');
        document.getElementById('otherPartyLang').focus();
        return;
    }
    input.removeAttribute('aria-invalid');
    _ownReplyBusy = true;
    const button = document.getElementById('ownReplyTranslate');
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    const id = 'own-' + crypto.randomUUID();
    selectReplyTarget(id, text, true);
    const generation = _replyGeneration;
    const label = getSelectedTargetLanguageLabel();
    setCockpitValue('ownReplyStatus', 'Çeviri hazırlanıyor…');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);
    try {
        const response = await fetch('/api/generate_ai_response', {
            method:'POST', headers:{'Content-Type':'application/json'}, signal:controller.signal,
            body:JSON.stringify({text, mode:'translate_dual', target_lang:lang, request_id:id})
        });
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Çeviri alınamadı. Tekrar dene.');
        if (!data.native || !data.romanized) throw new Error('Okunuş alınamadı. Tekrar dene.');
        if (generation === _replyGeneration && document.getElementById('aiTargetLang').value === lang) {
            renderReplyCockpit(id, [{translation:data.native, turkish:data.turkish || text, romanized:data.romanized}], lang, label, false);
            document.getElementById('replyComposerPanel').open = false;
            setCockpitValue('ownReplyStatus', 'Çeviri hazır. Okunuşu seslendirebilirsin.');
        } else {
            setCockpitValue('ownReplyStatus', 'Seçim değiştiği için eski çeviri gösterilmedi. Yeniden çevirebilirsin.');
        }
    } catch (error) {
        const message = error.name === 'AbortError' ? 'Çeviri zaman aşımına uğradı. Tekrar dene.' : error.message;
        setCockpitValue('ownReplyStatus', message);
        if (generation === _replyGeneration) {
            setCockpitValue('replyCockpitProgress', 'Çeviri alınamadı');
            setCockpitValue('replyCockpitOptions', 'Metnin korundu. Çevir düğmesiyle tekrar deneyebilirsin.');
        }
    } finally {
        clearTimeout(timer);
        _ownReplyBusy = false;
        button.disabled = false;
        button.removeAttribute('aria-busy');
    }
}

function toggleOwnReplyMic() {
    if (altPttHeld) finishAltPtt();
    else startOwnReplyMic();
}

function updateOwnMicButton() {
    const button = document.getElementById('ownReplyMic');
    if (!button) return;
    button.textContent = altPttHeld ? 'Bitir ve çevir' : 'Mikrofonla söyle';
    button.setAttribute('aria-pressed', String(altPttHeld));
    setCockpitValue('ownReplyStatus', altPttHeld ? 'Türkçe konuş. Bitir ve çevir düğmesine bas.' : 'Ses işleniyor; sonuç konuşma akışında da görünür.');
}

function showOwnMicResult(data) {
    if (data?.recording_id !== altPttRecordingId || _ownMicGeneration === null) return;
    if (!data?.success) {
        setCockpitValue('ownReplyStatus', data?.error || 'Ses işlenemedi. Tekrar dene.');
        return;
    }
    setCockpitValue('ownReplyStatus', 'Sesin çevrildi. Konuşma akışından okuma modunu açabilirsin.');
    if (!data.romanized || !data.translation || _ownMicGeneration !== _replyGeneration) return;
    const lang = String(data.target_lang || '').toLowerCase();
    if (lang !== document.getElementById('aiTargetLang').value) return;
    _ownMicGeneration = null;
    document.getElementById('replyComposerPanel').open = false;
    const id = 'mic-' + data.id;
    selectReplyTarget(id, data.original, true);
    renderReplyCockpit(id, [{translation:data.translation, turkish:data.original, romanized:data.romanized}], lang, getSelectedTargetLanguageLabel(), false);
}

function updateReadiness(status = {}) {
    _readinessSnapshot = {..._readinessSnapshot, ...status};
    const state = _readinessSnapshot;
    const model = state.model_loaded === true;
    const device = document.getElementById('deviceSelect');
    const hasDevice = Boolean(device?.value) && Number.isInteger(Number(device.value));
    const aiState = state.ai_key_status || 'unknown';
    const aiLabels = {valid:'Doğrulandı', missing:'Anahtar ekle', checking:'Doğrulanıyor', invalid:'Anahtarı düzelt', unverified:'Henüz doğrulanmadı', unavailable:'Hizmete ulaşılamıyor'};
    setCockpitValue('readyModel', model ? `Model · ${state.model_name || 'Yüklü'}` : 'Model · Seç ve yükle', model ? 'active' : 'warn');
    setCockpitValue('readyDevice', hasDevice ? `Ses · ${device.selectedOptions[0]?.textContent}` : 'Ses · Cihaz seç', hasDevice ? 'active' : 'warn');
    setCockpitValue('readyAi', 'AI · ' + (aiLabels[aiState] || 'Kontrol edilmedi'), aiState === 'valid' ? 'active' : 'warn');
    const count = Number(model) + Number(hasDevice) + Number(aiState === 'valid');
    setCockpitValue('readinessSummary', _socketConnected ? `${count}/3 hazır` : 'Bağlantı yok');
}

async function refreshReadiness() {
    if (_readinessBusy) return;
    _readinessBusy = true;
    const button = document.getElementById('readinessRefresh');
    button.disabled = true;
    setCockpitValue('readinessStatus', 'Kontrol ediliyor…');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
        const response = await fetch('/api/status', {signal:controller.signal});
        if (!response.ok) throw new Error('Durum alınamadı');
        updateReadiness(await response.json());
        setCockpitValue('readinessStatus', 'Eksik adımı açmak için ilgili düğmeye bas. Ses cihazının seçili olması ses sinyali alındığını doğrulamaz.');
    } catch (error) {
        _readinessSnapshot = {};
        updateReadiness();
        setCockpitValue('readinessSummary', 'Kontrol başarısız');
        setCockpitValue('readinessStatus', 'Sunucuya ulaşılamadı. Yeniden kontrol et.');
    } finally {
        clearTimeout(timeout);
        button.disabled = false;
        _readinessBusy = false;
    }
}

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
    if (typeof updateReadiness === 'function') updateReadiness();
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



function toggleControlPanel() {
    const collapsed = document.body.classList.toggle('controls-collapsed');
    const button = document.getElementById('controlsToggleBtn');
    if (button) {
        button.setAttribute('aria-expanded', String(!collapsed));
        button.title = collapsed ? 'Ayar panelini aç' : 'Ayar panelini daralt';
    }
    whisperStorage.setItem('controlsCollapsed', collapsed ? 'true' : 'false');
    if (collapsed && document.getElementById('controlPanel')?.contains(document.activeElement)) button?.focus();
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
        document.getElementById('replyCockpitOptions').dataset.selectedKey = '';
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
    const previousAction = document.activeElement?.dataset?.replyAction || 'read';
    const previousChoice = document.activeElement?.classList?.contains('reply-choice');
    const previousScroll = host.scrollTop;
    const unique = mergeUniqueAnswerOptions([], options || []).slice(0, 4);
    if (!unique.length) {
        host.innerHTML = '<div class="reply-cockpit-empty">Kullanılabilir cevap alınamadı.</div>';
        setCockpitValue('replyCockpitProgress', partial ? 'Bekleniyor' : 'Sonuç yok');
        return;
    }
    const selectedKey = host.dataset.selectedKey || previousKey || '';
    const selectedIndex = Math.max(0, unique.findIndex(option => answerStableKey(option) === selectedKey));
    host.dataset.selectedKey = answerStableKey(unique[selectedIndex]);
    const choices = '<div class="reply-choice-list" role="group" aria-label="Cevap seçenekleri">' + unique.map((option, index) =>
        `<button type="button" class="reply-choice" data-choice-index="${index}" aria-pressed="${index === selectedIndex}" aria-controls="reply-option-${index}" onclick="selectCockpitOption(${index})"><span class="reply-choice-number">${index + 1}</span><span>${escapeHtml(option.turkish || option.translation || 'Cevap ' + (index + 1))}</span></button>`
    ).join('') + '</div>';
    host.innerHTML = choices + unique.map((opt, idx) => {
        const nativeText = String(opt.translation || opt.turkish || '');
        const meaning = opt.turkish && opt.turkish.trim() !== nativeText.trim() ? opt.turkish : '';
        const pronunciation = String(opt.romanized || nativeText);
        const lang = String(opt.language || effectiveLang || '');
        const key = answerStableKey(opt);
        return `<article class="reply-option-card" id="reply-option-${idx}" data-answer-key="${escapeHtml(key)}" ${idx === selectedIndex ? '' : 'hidden'}>
            <div class="reply-option-topline"><span class="reply-option-number">Seçenek ${idx + 1}</span><span class="reply-option-language">${escapeHtml(langLabel || lang)}</span></div>
            <div class="reply-reading-label">Böyle söyle <span>Türkçe okunuş</span></div><div class="reply-option-pronunciation">${escapeHtml(pronunciation)}</div>
            <div class="reply-detail-grid"><div class="reply-option-native"><span class="reply-detail-label">Orijinal cümle</span><span dir="auto">${escapeHtml(nativeText)}</span></div>
            ${meaning ? `<div class="reply-option-meaning"><span class="reply-detail-label">Türkçe anlamı</span>${escapeHtml(meaning)}</div>` : ''}
            </div><div class="reply-option-actions">
                <button type="button" class="reply-read-button" data-reply-action="read" onclick="openReadingMode('${escapeJsString(pronunciation)}','${escapeJsString(nativeText)}','${escapeJsString(meaning)}','${escapeJsString(lang)}')">Okuma modu</button>
                <button type="button" data-reply-action="copy" onclick="copyResponseText('${escapeJsString(pronunciation)}')">Okunuşu kopyala</button>
                <button type="button" data-reply-action="listen" onclick="speakText('${escapeJsString(nativeText)}','${escapeJsString(lang)}')">Dinle</button>
                <button type="button" data-reply-action="save" onclick="saveFavorite('${escapeJsString(nativeText)}','${escapeJsString(opt.turkish || '')}','${escapeJsString(opt.romanized || '')}','${escapeJsString(lang)}')">Kalıplara kaydet</button>
            </div>
        </article>`;
    }).join('');
    setCockpitValue('replyCockpitProgress', partial ? 'Diğer seçenekler hazırlanıyor' : `${unique.length} seçenek hazır`);
    host.scrollTop = previousScroll;
    if (previousChoice) host.querySelector('.reply-choice[aria-pressed="true"]')?.focus({preventScroll:true});
    if (previousKey) host.querySelector(`[data-answer-key="${CSS.escape(previousKey)}"] [data-reply-action="${CSS.escape(previousAction)}"]`)?.focus({preventScroll:true});
}

// Seçim yalnız görünümü değiştirir; yeni AI isteği oluşturmaz.
function selectCockpitOption(index) {
    const host = document.getElementById('replyCockpitOptions');
    const cards = Array.from(host.querySelectorAll('.reply-option-card'));
    if (!Number.isInteger(index) || !cards[index]) return;
    cards.forEach((card, i) => { card.hidden = i !== index; });
    host.querySelectorAll('.reply-choice').forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
    host.dataset.selectedKey = cards[index].dataset.answerKey;
}

function clearTranscriptSearch() {
    const input = document.getElementById('transcriptSearchInput');
    input.value = '';
    _searchGeneration++;
    filterVisibleTranscriptions('');
    document.getElementById('transcriptSearchClear').hidden = true;
    input.focus();
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
    if (e.repeat || document.getElementById('readingOverlay')?.classList.contains('visible')) return;
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

// Ayar paneli kapanınca klavye odağı açıcıya döner.
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !document.body.classList.contains('controls-collapsed')
        && !document.getElementById('readingOverlay')?.classList.contains('visible')) {
        toggleControlPanel();
        e.preventDefault();
    }
});
