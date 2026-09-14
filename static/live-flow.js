"use strict";

// Canlı akışın ekran ve kayıt sürümü sahipliği burada tutulur.
window._transcriptRevisions = window._transcriptRevisions || {};
let _followTranscript = true;
let _audioTestBusy = false;

function updateTranscriptFollow() {
    const list = document.getElementById('transcriptionList');
    if (!list) return;
    _followTranscript = list.scrollTop <= 24 && !list.querySelector('.transcript-editor');
    document.getElementById('backToLive').hidden = _followTranscript;
}

function backToLiveTranscript() {
    const list = document.getElementById('transcriptionList');
    _followTranscript = true;
    list.scrollTo({top: 0, behavior: 'auto'});
    document.getElementById('backToLive').hidden = true;
}

function preserveTranscriptPosition(change) {
    const list = document.getElementById('transcriptionList');
    if (!list) return change();
    const following = _followTranscript && !list.querySelector('.transcript-editor');
    const top = list.getBoundingClientRect().top;
    const anchor = [...list.children].find(el => el.getBoundingClientRect().bottom > top + 1);
    const offset = anchor?.getBoundingClientRect().top;
    const result = change();
    if (following) list.scrollTop = 0;
    else if (anchor?.isConnected) list.scrollTop += anchor.getBoundingClientRect().top - offset;
    document.getElementById('backToLive').hidden = following;
    return result;
}

function transcriptNode(id) {
    return [...document.querySelectorAll('[data-transcription-id]')].find(el => el.dataset.transcriptionId === String(id));
}

function decorateTranscript(data) {
    if (!data || data.id == null) return;
    const item = transcriptNode(data.id);
    if (!item) return;
    window._transcriptRevisions[data.id] = Math.max(window._transcriptRevisions[data.id] || 0, data.revision || 0);
    item.dataset.revision = String(window._transcriptRevisions[data.id]);
    if (['mic', 'ptt'].includes(data.source) || item.querySelector('.transcript-edit-button')) return;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'copy-btn transcript-edit-button';
    button.textContent = 'Metni düzelt';
    button.setAttribute('onclick', `openTranscriptEditor(${Number(data.id)})`);
    item.querySelector('.transcription-header')?.append(button);
}

function openTranscriptEditor(id) {
    const item = transcriptNode(id);
    if (!item) return;
    if (item.querySelector('.transcript-editor')) {
        item.querySelector('textarea').focus();
        return;
    }
    const editor = document.createElement('form');
    editor.className = 'transcript-editor';
    editor.noValidate = true;
    editor.dataset.revision = String(window._transcriptRevisions[id] || 0);
    editor.dataset.refreshAnswer = String(Boolean(item.querySelector('.answer-option') || _replyTargetId === String(id)));
    editor.setAttribute('onsubmit', `event.preventDefault();saveTranscriptCorrection(${Number(id)})`);
    editor.innerHTML = `<label for="correct-text-${Number(id)}">Duyulan metin</label>
        <textarea id="correct-text-${Number(id)}" rows="4" maxlength="4000" style="resize: none" aria-describedby="correct-status-${Number(id)}"></textarea>
        <div class="correction-actions"><button type="submit">Düzelt ve çevir</button><button type="button" onclick="closeTranscriptEditor(${Number(id)})">Vazgeç</button></div>
        <p id="correct-status-${Number(id)}" role="status">Mevcut cevap önerileri de yenilenir.</p>`;
    editor.querySelector('textarea').value = transcriptionTexts[id] || '';
    item.append(editor);
    _followTranscript = false;
    document.getElementById('backToLive').hidden = false;
    editor.querySelector('textarea').focus({preventScroll: true});
    editor.scrollIntoView({block: 'nearest'});
}

function closeTranscriptEditor(id) {
    const item = transcriptNode(id);
    if (item?.querySelector('.transcript-editor')?.dataset.busy === 'true') return;
    item?.querySelector('.transcript-editor')?.remove();
    item?.querySelector('.transcript-edit-button')?.focus({preventScroll: true});
    updateTranscriptFollow();
}

function applyTranscriptCorrection(record) {
    if (!record || record.id == null || typeof record.text !== 'string') return;
    if (record.instance_id && _backendInstanceId && record.instance_id !== _backendInstanceId) return;
    const id = String(record.id);
    const revision = Number(record.revision || 0);
    if (revision <= (window._transcriptRevisions[id] || 0)) return;
    preserveTranscriptPosition(() => {
        window._transcriptRevisions[id] = revision;
        transcriptionTexts[id] = record.text;
        for (const [requestId, pending] of Object.entries(window._pendingAiRequests || {})) {
            if (String(pending.id) === id) delete window._pendingAiRequests[requestId];
        }
        if (window._activeAnswerRequests) delete window._activeAnswerRequests[id];
        const item = transcriptNode(id);
        if (item) {
            item.dataset.revision = String(revision);
            item.querySelector('.transcription-original').textContent = record.text;
            item.querySelector('.transcription-translation')?.remove();
            const ai = document.getElementById('ai-result-' + id);
            if (ai) { ai.replaceChildren(); ai.style.display = 'none'; }
            item.querySelectorAll('.ai-translate-btn, .ai-answer-btn').forEach(button => {
                button.disabled = false; button.style.display = '';
                button.textContent = button.classList.contains('ai-answer-btn') ? 'Cevap öner' : 'Çevir';
            });
            updateTranscriptTranslationStatus(item, record.translation_status || 'pending');
            if (record.translation) appendInlineTranslationToItem(item, record.translation, record.target_lang);
        }
        if (_replyTargetId === id) {
            if (document.getElementById('readingOverlay')?.classList.contains('visible')) closeReadingMode();
            _replyGeneration++;
            _replyTargetText = record.text;
            setCockpitValue('replyCockpitSource', record.text);
            setCockpitValue('replyCockpitProgress', 'Metin düzeltildi');
            setCockpitValue('replyCockpitOptions', 'Düzeltilmiş metin için cevaplar yeniden hazırlanabilir.');
        }
    });
}

async function saveTranscriptCorrection(id) {
    const editor = transcriptNode(id)?.querySelector('.transcript-editor');
    if (!editor || editor.dataset.busy === 'true') return;
    const input = editor.querySelector('textarea');
    const text = input.value.trim();
    const status = editor.querySelector('[role="status"]');
    if (!text || text.length > 4000) {
        input.setAttribute('aria-invalid', 'true');
        status.textContent = '1–4000 karakterlik bir metin yaz.'; input.focus(); return;
    }
    input.removeAttribute('aria-invalid');
    editor.dataset.busy = 'true';
    editor.setAttribute('aria-busy', 'true');
    editor.querySelectorAll('button').forEach(button => { button.disabled = true; });
    status.textContent = 'Düzeltme kaydediliyor…';
    const refreshAnswer = editor.dataset.refreshAnswer === 'true';
    const generation = _hydrationGeneration;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch('/api/transcriptions/' + Number(id) + '/correct', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, signal: controller.signal,
            body: JSON.stringify({text, revision: Number(editor.dataset.revision)})
        });
        const data = await response.json();
        if (!editor.isConnected || generation !== _hydrationGeneration) return;
        if (response.status === 409 && data.record) {
            applyTranscriptCorrection(data.record);
            editor.dataset.revision = String(data.record.revision);
            throw new Error('Kayıt değişti; güncel metin üstte. Taslağını kontrol edip tekrar kaydet.');
        }
        if (!response.ok || !data.success) throw new Error(data.error || 'Düzeltme kaydedilemedi.');
        applyTranscriptCorrection(data.record);
        editor.dataset.busy = 'false';
        closeTranscriptEditor(id);
        const button = transcriptNode(id)?.querySelector('.ai-answer-btn');
        if (refreshAnswer && button) getAIResponseById(id, 'answer', button);
    } catch (error) {
        status.textContent = error.name === 'AbortError' ? 'İstek zaman aşımına uğradı. Taslağın korundu; yeniden deneyebilirsin.' : error.message;
    } finally {
        clearTimeout(timer);
        editor.dataset.busy = 'false'; editor.removeAttribute('aria-busy');
        editor.querySelectorAll('button').forEach(button => { button.disabled = false; });
    }
}

const _addLiveTranscription = addTranscription;
addTranscription = function(data, ...args) {
    return preserveTranscriptPosition(() => {
        const item = data?.id == null ? null : transcriptNode(data.id);
        if (item && (data.revision || 0) < (window._transcriptRevisions[data.id] || 0)) return;
        if (item && (data.revision || 0) > (window._transcriptRevisions[data.id] || 0)) applyTranscriptCorrection(data);
        else _addLiveTranscription(data, ...args);
        decorateTranscript(data);
        for (const id of Object.keys(window._transcriptRevisions)) {
            if (!Object.hasOwn(transcriptionTexts, id)) delete window._transcriptRevisions[id];
        }
    });
};
for (const name of ['showPartialPreview', 'clearPartialPreview', 'appendInlineTranslationToItem']) {
    const original = window[name];
    window[name] = (...args) => preserveTranscriptPosition(() => original(...args));
}

function showAudioDiagnostic(data) {
    if (!data) return;
    const labels = {ok: 'Ses geliyor', quiet: 'Ses çok düşük', no_signal: 'Sessizlik / sinyal yok', no_frames: 'Veri gelmedi · ses çalıp tekrar test et', clipping: 'Ses tepeleri kırpılıyor · sesi azalt', disconnected: 'Ses cihazı bağlantısı kesildi'};
    const level = Number.isFinite(data.rms_dbfs) ? ` · ${Math.round(data.rms_dbfs)} dBFS` : '';
    setCockpitValue('liveAudioState', (labels[data.status] || 'Ses ölçümü bekleniyor') + level, data.status);
}

async function runAudioTest() {
    if (_audioTestBusy) return;
    const value = document.getElementById('deviceSelect').value;
    if (value === '' || !Number.isInteger(Number(value))) {
        setCockpitValue('audioTestStatus', 'Önce ses cihazını seç.'); focusSetupTarget('device'); return;
    }
    const button = document.getElementById('audioTestButton');
    _audioTestBusy = true; button.disabled = true; button.setAttribute('aria-busy', 'true');
    setCockpitValue('audioTestStatus', 'Ses ölçülüyor… Seçili kaynaktan ses çal veya konuş.');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    try {
        const response = await fetch('/api/audio_test', {method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({device_id:Number(value)})});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error(data.error || 'Ses testi tamamlanamadı.');
        if (document.getElementById('deviceSelect').value !== value) throw new Error('Cihaz değişti. Yeni cihazı tekrar test et.');
        showAudioDiagnostic(data.measurement);
        setCockpitValue('audioTestStatus', document.getElementById('liveAudioState').textContent + (data.live ? ' · Canlı ölçüm' : ' · 3 saniyelik ölçüm'));
    } catch (error) {
        setCockpitValue('audioTestStatus', error.name === 'AbortError' ? 'Ses testi zaman aşımına uğradı. Cihazı kontrol et.' : error.message);
    } finally {
        clearTimeout(timer); _audioTestBusy = false; button.disabled = false; button.removeAttribute('aria-busy');
    }
}

async function setFlowPreference(key, control) {
    const requested = control.checked;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 10000);
    control.disabled = true;
    try {
        const response = await fetch('/api/update_settings', {signal:controller.signal, method:'POST', headers:{'Content-Type':'application/json'},body:JSON.stringify({[key]:requested})});
        const data = await response.json();
        if (!response.ok || !data.success) throw new Error('Ayar kaydedilemedi.');
        applyRuntimeSettings(data.settings);
        setCockpitValue('flowPreferenceStatus', 'Ayar bu oturum için güncellendi.');
    } catch (error) {
        control.checked = !requested; setCockpitValue('flowPreferenceStatus', 'Ayar kaydedilemedi. Yeniden dene.');
    } finally { clearTimeout(timer); control.disabled = false; }
}

function renderPipelineStages(pipeline) {
    if (!pipeline) return;
    const capture = !pipeline.capturing ? 'Ses yakalama kapalı' : pipeline.paused ? 'Akış bekletildi'
        : pipeline.capture_phase === 'waiting_silence' ? `Konuşmanın bitmesi bekleniyor · eşik ${pipeline.silence_seconds} sn`
        : pipeline.capture_phase === 'speaking' ? 'Konuşma alınıyor' : 'Konuşma bekleniyor';
    const asr = pipeline.asr_active ? 'Ses modelde çözümleniyor' : 'Model yeni ses bekliyor';
    const translation = pipeline.translation_active ? 'Çeviri servisinden yanıt bekleniyor' : 'Çeviri isteği yok';
    setCockpitValue('pipelineStages', `${capture}. ${asr}; sırada ${pipeline.audio_queue || 0} ses. ${translation}; sırada ${pipeline.translation_waiting || 0} çeviri.`);
    setCockpitValue('pipelineSummary', pipeline.asr_active ? 'Ses çözümleniyor'
        : pipeline.translation_active ? 'Çeviri yanıtı bekleniyor' : capture);
}
