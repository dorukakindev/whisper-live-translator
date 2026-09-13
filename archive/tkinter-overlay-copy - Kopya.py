#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper Web Arayüzü + DeepL Çeviri + Konuşmacı Tanıma (Pyannote) + Context Carry-over + Gelişmiş Ayarlar
Gerekli kütüphaneler:
pip install flask flask-socketio faster-whisper pyaudiowpatch numpy webrtcvad requests pyannote.audio torch torchaudio
"""

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO, emit
import os
import sys
import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel
import webrtcvad
import threading
import queue
import time
import json
import requests
from datetime import datetime
import pickle
from collections import deque

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whisper-secret-key-2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# HTML Template (Orijinal tasarım korunarak yeni ayarlar eklendi)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Whisper + DeepL + Konuşmacı Tanıma Pro</title>
    <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary: #667eea; --secondary: #764ba2; --success: #10b981;
            --danger: #ef4444; --warning: #f59e0b; --dark: #1f2937;
            --light: #f3f4f6; --deepl: #0f2b46;
            --speaker1: #3b82f6; --speaker2: #10b981; --speaker3: #f59e0b;
            --speaker4: #ef4444; --speaker5: #8b5cf6; --speaker6: #ec4899;
            --speaker7: #14b8a6; --speaker8: #f97316;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            min-height: 100vh; color: var(--dark);
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; color: white; padding: 30px 0; animation: fadeIn 0.5s; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; text-shadow: 2px 2px 4px rgba(0,0,0,0.2); display: flex; align-items: center; justify-content: center; gap: 15px; }
        .main-grid { display: grid; grid-template-columns: 380px 1fr; gap: 20px; margin-top: 20px; }
        @media (max-width: 768px) { .main-grid { grid-template-columns: 1fr; } }
        .card { background: white; border-radius: 15px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); animation: slideUp 0.5s; }
        .control-panel { position: sticky; top: 20px; height: fit-content; max-height: 90vh; overflow-y: auto; }
        
        /* Orijinal CSS sınıfları korundu */
        .context-indicator { margin-bottom: 20px; padding: 12px; background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%); border-radius: 10px; border: 2px solid #0284c7; font-size: 12px; }
        .model-language-settings, .speaker-settings { margin-bottom: 20px; padding: 15px; background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%); border-radius: 10px; border: 2px solid #fbbf24; }
        .translation-settings { margin-bottom: 20px; padding: 15px; background: linear-gradient(135deg, #e8f4fd 0%, #e3f2fd 100%); border-radius: 10px; border: 2px solid #90caf9; }
        .model-selector { margin-bottom: 20px; padding: 15px; background: linear-gradient(135deg, #f0f0ff 0%, #faf0ff 100%); border-radius: 10px; border: 2px solid #e0e0ff; }
        
        /* Yeni eklenen CSS stilleri (Gelişmiş ayarlar için) */
        .advanced-settings-panel { margin-bottom: 20px; padding: 15px; background: #f3f4f6; border-radius: 10px; border: 1px solid #d1d5db; }
        .advanced-settings-panel h4 { margin-bottom: 12px; color: #374151; font-size: 14px; display: flex; align-items: center; gap: 5px; }
        .hotwords-input { width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 6px; font-size: 12px; margin-bottom: 10px; }
        
        .language-radio-group { display: flex; gap: 15px; flex-wrap: wrap; }
        .language-radio { display: flex; align-items: center; gap: 5px; padding: 8px 12px; background: white; border-radius: 8px; border: 2px solid #e5e7eb; cursor: pointer; transition: all 0.3s; }
        .language-radio.selected { background: #fef3c7; border-color: #fbbf24; }
        
        .toggle-switch { position: relative; width: 50px; height: 24px; background: #ccc; border-radius: 24px; cursor: pointer; transition: background 0.3s; }
        .toggle-switch.active { background: var(--success); }
        .toggle-slider { position: absolute; top: 2px; left: 2px; width: 20px; height: 20px; background: white; border-radius: 50%; transition: transform 0.3s; }
        .toggle-switch.active .toggle-slider { transform: translateX(26px); }
        
        .model-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
        .model-option { padding: 10px; border: 2px solid #e0e0e0; border-radius: 8px; cursor: pointer; text-align: center; }
        .model-option.selected { border-color: var(--primary); background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%); }
        .model-option.installed::after { content: '✓'; position: absolute; top: 5px; right: 5px; color: var(--success); font-weight: bold; }
        
        .btn { width: 100%; padding: 12px 20px; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; transition: all 0.3s; display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 10px; }
        .btn-primary { background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%); color: white; }
        .btn-danger { background: var(--danger); color: white; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        
        .setting-item { margin-bottom: 12px; }
        .setting-item label { display: block; font-size: 12px; color: #666; margin-bottom: 4px; font-weight: 600; }
        .setting-item input[type="range"] { width: 100%; }
        .setting-value { font-size: 12px; color: var(--primary); float: right; }
        
        .transcription-item { padding: 15px; background: #f8f9fa; border-radius: 10px; margin-bottom: 15px; animation: fadeIn 0.5s; border-left: 4px solid var(--primary); }
        .transcription-item.with-translation { border-left-color: var(--deepl); }
        .transcription-time { font-size: 12px; color: #666; }
        .transcription-original { font-size: 16px; margin: 10px 0; }
        .transcription-translation { font-size: 15px; color: #1a365d; padding: 10px; background: #e8f4fd; border-radius: 8px; }
        
        .status-dot { width: 12px; height: 12px; border-radius: 50%; margin-right: 10px; display: inline-block; }
        .status-dot.inactive { background: var(--danger); }
        .status-dot.active { background: var(--success); }
        
        /* Speaker badges */
        .speaker-badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; color: white; margin-right: 10px; }
        .speaker-1 { background-color: var(--speaker1); } .speaker-2 { background-color: var(--speaker2); }
        
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><span>🎙️</span><span>Whisper + DeepL + Konuşmacı Tanıma</span><span>👥</span></h1>
            <p>Gelişmiş Ayarlar ile Gerçek Zamanlı Transkripsiyon</p>
        </div>
        
        <div id="alerts"></div>
        
        <div class="main-grid">
            <!-- Sol Panel -->
            <div class="card control-panel">
                <div class="context-indicator">
                    <h4>🔄 Context Carry-over</h4>
                    <div>Bağlam Hafızası: <span id="contextCount" style="font-weight:bold; color:#0284c7;">0</span> / 10 kayıt</div>
                </div>
                
                <div class="model-language-settings">
                    <h3>🌐 Model Dili</h3>
                    <div class="language-radio-group">
                        <div class="language-radio selected"><input type="radio" id="langTr" name="whisperLang" value="tr" checked><label for="langTr">🇹🇷 Türkçe</label></div>
                        <div class="language-radio"><input type="radio" id="langEn" name="whisperLang" value="en"><label for="langEn">🇬🇧 İngilizce</label></div>
                        <div class="language-radio"><input type="radio" id="langDe" name="whisperLang" value="de"><label for="langDe">🇩🇪 Almanca</label></div>
                    </div>
                </div>
                
                <div class="speaker-settings">
                    <h3>👥 Konuşmacı Tanıma</h3>
                    <div style="display:flex; align-items:center; gap:10px; margin-bottom:10px;">
                        <div class="toggle-switch" id="speakerToggle" onclick="toggleSpeakerDiarization()"><div class="toggle-slider"></div></div>
                        <span id="speakerToggleText">Kapalı</span>
                    </div>
                    <div id="hfTokenContainer" style="display:none; margin-top:10px;">
                        <input type="password" id="hfToken" placeholder="Hugging Face Token" style="width:100%; padding:8px; border:1px solid #ccc; border-radius:4px;" onchange="saveHFToken(this.value)">
                        <div id="hfStatus" style="font-size:11px; margin-top:5px;"></div>
                    </div>
                    <div id="speakersListContainer" style="display:none;">
                         <div id="speakersList" style="font-size:12px;"></div>
                         <button class="btn" style="background:#6c757d; color:white; font-size:12px; padding:5px;" onclick="resetSpeakers()">Sıfırla</button>
                    </div>
                </div>

                <div class="translation-settings">
                    <h3>🌍 DeepL Çeviri</h3>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <div class="toggle-switch" id="translationToggle" onclick="toggleTranslation()"><div class="toggle-slider"></div></div>
                        <span id="translationToggleText">Kapalı</span>
                    </div>
                    <div id="deeplSettingsPanel" style="display:none; margin-top:10px;">
                        <input type="password" id="deeplApiKey" placeholder="DeepL API Key" style="width:100%; padding:8px; margin-bottom:5px;" onchange="saveDeepLKey(this.value)">
                    </div>
                </div>
                
                <!-- Model Seçimi -->
                <div class="model-selector">
                    <h3>🤖 Model Seçimi</h3>
                    <div class="model-grid">
                        <div class="model-option" data-model="tiny" onclick="selectModel('tiny')">Tiny</div>
                        <div class="model-option" data-model="base" onclick="selectModel('base')">Base</div>
                        <div class="model-option" data-model="small" onclick="selectModel('small')">Small</div>
                        <div class="model-option selected" data-model="medium" onclick="selectModel('medium')">Medium</div>
                        <div class="model-option" data-model="turbo" onclick="selectModel('turbo')">Turbo</div>
                    </div>
                    <button class="btn btn-primary" onclick="loadSelectedModel()">Model Yükle</button>
                    <div style="display:flex; align-items:center; margin-top:10px;">
                         <div class="status-dot inactive" id="statusDot"></div>
                         <span id="statusText" style="font-size:12px;">Model yüklenmedi</span>
                    </div>
                </div>
                
                <!-- YENİ EKLENEN GELİŞMİŞ AYARLAR PANELİ -->
                <div class="advanced-settings-panel">
                    <h4>🛠️ Gelişmiş Whisper Ayarları</h4>
                    
                    <div class="setting-item">
                        <label>Özel Kelimeler (Hotwords)</label>
                        <input type="text" class="hotwords-input" id="hotwords" placeholder="Şirket adı, Proje X, Terimler..." onchange="updateAdvancedSettings()">
                    </div>

                    <div class="setting-item">
                        <label>
                            Beam Size (Hız vs Kalite)
                            <span class="setting-value" id="beamSizeValue">5</span>
                        </label>
                        <input type="range" id="beamSize" min="1" max="10" value="5" step="1" oninput="document.getElementById('beamSizeValue').textContent=this.value" onchange="updateAdvancedSettings()">
                        <div style="font-size:10px; color:#666;">Düşük=Hızlı, Yüksek=Doğru</div>
                    </div>

                    <div class="setting-item">
                        <label>
                            Tekrar Cezası (Repetition Penalty)
                            <span class="setting-value" id="repValue">1.0</span>
                        </label>
                        <input type="range" id="repetitionPenalty" min="1.0" max="2.0" value="1.0" step="0.1" oninput="document.getElementById('repValue').textContent=this.value" onchange="updateAdvancedSettings()">
                    </div>

                    <div class="setting-item">
                        <label>
                            Halüsinasyon Filtresi (Threshold)
                            <span class="setting-value" id="logProbValue">-1.0</span>
                        </label>
                        <input type="range" id="logProbThreshold" min="-2.0" max="0.0" value="-1.0" step="0.1" oninput="document.getElementById('logProbValue').textContent=this.value" onchange="updateAdvancedSettings()">
                        <div style="font-size:10px; color:#666;">-0.5 önerilir (Sessizlikteki saçma yazıları engeller)</div>
                    </div>
                    
                    <div class="setting-item" style="display:flex; align-items:center; justify-content:space-between;">
                        <label style="margin:0;">Düşük Gecikme Modu</label>
                        <input type="checkbox" id="lowLatency" onchange="updateAdvancedSettings()">
                    </div>
                </div>

                <div class="device-selector" style="margin-bottom:15px;">
                    <label>Ses Kaynağı:</label>
                    <select id="deviceSelect" style="width:100%; padding:8px;"><option>Yükleniyor...</option></select>
                </div>
                
                <div class="control-buttons">
                    <button class="btn btn-primary" id="startBtn" onclick="startCapture()" disabled>▶️ Başlat</button>
                    <button class="btn btn-danger" id="stopBtn" onclick="stopCapture()" disabled>⏹️ Durdur</button>
                </div>
                
                <button class="btn btn-secondary" style="background:#6c757d; color:white;" onclick="clearTranscriptions()">🗑️ Temizle</button>
            </div>
            
            <!-- Sağ Panel -->
            <div class="card transcription-area">
                <div class="transcription-controls" style="display:flex; justify-content:space-between; margin-bottom:10px;">
                    <h2>📝 Sonuçlar</h2>
                    <button class="btn btn-secondary" style="width:auto; padding:5px 15px;" onclick="downloadTranscriptions()">💾 İndir</button>
                </div>
                <div class="transcription-list" id="transcriptionList">
                    <div class="empty-state" style="text-align:center; padding:40px; color:#999;">
                        <p>Kayıt yok. Başlat butonuna tıklayın.</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const socket = io();
        let selectedModel = 'medium';
        let speakerDiarizationEnabled = false;
        let translationEnabled = false;
        let translationSettings = { apiKey: '', enabled: false };
        let advancedSettings = {
            beam_size: 5,
            hotwords: '',
            repetition_penalty: 1.0,
            log_prob_threshold: -1.0,
            low_latency: false,
            vad_level: 2,
            silence_duration: 2.0
        };

        window.onload = async function() {
            await loadDevices();
            loadSettings();
            setupSocket();
            
            // Radio buttons listener
            document.querySelectorAll('input[name="whisperLang"]').forEach(r => {
                r.addEventListener('change', function() {
                    document.querySelectorAll('.language-radio').forEach(d => d.classList.remove('selected'));
                    this.parentElement.classList.add('selected');
                });
            });
        };

        function setupSocket() {
            socket.on('new_transcription', (data) => {
                addTranscription(data);
                document.getElementById('contextCount').textContent = data.context_size || 0;
            });
            socket.on('capture_started', () => {
                document.getElementById('statusText').textContent = '🔴 Dinleniyor...';
                document.getElementById('statusDot').className = 'status-dot active';
            });
            socket.on('capture_stopped', () => {
                document.getElementById('statusText').textContent = 'Hazır (Durduruldu)';
                document.getElementById('statusDot').className = 'status-dot inactive';
            });
        }

        // --- Gelişmiş Ayarlar Fonksiyonları ---
        function updateAdvancedSettings() {
            advancedSettings.hotwords = document.getElementById('hotwords').value;
            advancedSettings.beam_size = parseInt(document.getElementById('beamSize').value);
            advancedSettings.repetition_penalty = parseFloat(document.getElementById('repetitionPenalty').value);
            advancedSettings.log_prob_threshold = parseFloat(document.getElementById('logProbThreshold').value);
            advancedSettings.low_latency = document.getElementById('lowLatency').checked;
            
            // Sunucuya gönder
            fetch('/api/update_settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(advancedSettings)
            });
        }

        // --- Orijinal Fonksiyonların Entegrasyonu ---
        
        async function loadDevices() {
            const res = await fetch('/api/devices');
            const devices = await res.json();
            const select = document.getElementById('deviceSelect');
            select.innerHTML = '';
            devices.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.id;
                opt.text = d.name;
                select.appendChild(opt);
            });
        }

        function selectModel(model) {
            selectedModel = model;
            document.querySelectorAll('.model-option').forEach(el => el.classList.remove('selected'));
            document.querySelector(`[data-model="${model}"]`).classList.add('selected');
        }

        async function loadSelectedModel() {
            document.getElementById('statusText').textContent = 'Model yükleniyor...';
            const res = await fetch('/api/load_model', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({model: selectedModel})
            });
            const data = await res.json();
            if(data.success) {
                document.getElementById('statusText').textContent = `Hazır - ${selectedModel}`;
                document.getElementById('startBtn').disabled = false;
                document.querySelector(`[data-model="${selectedModel}"]`).classList.add('installed');
            } else {
                alert('Model yüklenemedi: ' + data.error);
            }
        }

        function startCapture() {
            const deviceId = document.getElementById('deviceSelect').value;
            const lang = document.querySelector('input[name="whisperLang"]:checked').value;
            
            document.getElementById('startBtn').disabled = true;
            document.getElementById('stopBtn').disabled = false;
            
            fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    device_id: parseInt(deviceId),
                    settings: advancedSettings,
                    whisper_language: lang,
                    speaker_diarization: speakerDiarizationEnabled
                })
            });
        }

        function stopCapture() {
            fetch('/api/stop', {method: 'POST'});
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
        }

        function addTranscription(data) {
            const list = document.getElementById('transcriptionList');
            if(list.querySelector('.empty-state')) list.innerHTML = '';
            
            const item = document.createElement('div');
            item.className = 'transcription-item';
            
            let speakerHtml = '';
            if(data.speaker_name) {
                // Speaker rengi için basit hash
                const colorId = (data.speaker_id.replace(/\D/g,'') || 1) % 8 + 1;
                item.classList.add(`speaker-${colorId}`);
                speakerHtml = `<span class="speaker-badge speaker-${colorId}">👤 ${data.speaker_name}</span>`;
            }

            let translationHtml = '';
            if(data.translation) {
                item.classList.add('with-translation');
                translationHtml = `<div class="transcription-translation">🌍 ${data.translation}</div>`;
            }

            item.innerHTML = `
                <div class="transcription-header">
                    <div>
                        ${speakerHtml}
                        <span class="transcription-time">🕐 ${data.timestamp}</span>
                    </div>
                    <div style="font-size:10px; opacity:0.7;">${Math.round(data.confidence*100)}%</div>
                </div>
                <div class="transcription-original">${data.text}</div>
                ${translationHtml}
            `;
            list.insertBefore(item, list.firstChild);
        }

        function clearTranscriptions() {
            fetch('/api/clear', {method: 'POST'});
            document.getElementById('transcriptionList').innerHTML = '<div class="empty-state" style="text-align:center; padding:40px; color:#999;"><p>Kayıtlar temizlendi.</p></div>';
            document.getElementById('contextCount').textContent = '0';
        }
        
        // --- Helper Functions ---
        function loadSettings() {
            if(localStorage.getItem('hfToken')) document.getEleme