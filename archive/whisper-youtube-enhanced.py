#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper Web Arayüzü + DeepL Çeviri + YouTube Desteği + Gelişmiş Ses İşleme
Gerekli kütüphaneler:
pip install flask flask-socketio faster-whisper pyaudiowpatch numpy webrtcvad requests scipy yt-dlp
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
import scipy.signal as signal
import yt_dlp
import tempfile
import subprocess
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whisper-secret-key-2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# HTML Template
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Whisper + DeepL + YouTube Pro</title>
    <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --dark: #1f2937;
            --light: #f3f4f6;
            --deepl: #0f2b46;
            --youtube: #ff0000;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            min-height: 100vh;
            color: var(--dark);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            text-align: center;
            color: white;
            padding: 30px 0;
            animation: fadeIn 0.5s;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.95;
        }
        
        .main-grid {
            display: grid;
            grid-template-columns: 380px 1fr;
            gap: 20px;
            margin-top: 20px;
        }
        
        @media (max-width: 768px) {
            .main-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            animation: slideUp 0.5s;
        }
        
        .control-panel {
            position: sticky;
            top: 20px;
            height: fit-content;
        }
        
        /* YouTube Panel Styles */
        .youtube-panel {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #ffe4e4 0%, #ffcccc 100%);
            border-radius: 10px;
            border: 2px solid #ff6b6b;
        }
        
        .youtube-panel h3 {
            margin-bottom: 12px;
            color: #cc0000;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .youtube-input-group {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        
        .youtube-input {
            flex: 1;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
        }
        
        .youtube-input:focus {
            outline: none;
            border-color: var(--youtube);
        }
        
        .btn-youtube {
            padding: 10px 20px;
            background: var(--youtube);
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .btn-youtube:hover:not(:disabled) {
            background: #dc0000;
            transform: translateY(-1px);
        }
        
        .btn-youtube:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .youtube-progress {
            display: none;
            margin-top: 10px;
            padding: 10px;
            background: #f8f8f8;
            border-radius: 8px;
        }
        
        .youtube-progress.active {
            display: block;
        }
        
        .youtube-progress-text {
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
        }
        
        .youtube-progress-bar {
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }
        
        .youtube-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--youtube), #ff4444);
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
        }
        
        .youtube-info {
            display: none;
            margin-top: 10px;
            padding: 10px;
            background: #fff;
            border: 1px solid #ff6b6b;
            border-radius: 8px;
        }
        
        .youtube-info.active {
            display: block;
        }
        
        .youtube-info-title {
            font-weight: 600;
            color: #333;
            margin-bottom: 5px;
            font-size: 14px;
        }
        
        .youtube-info-details {
            font-size: 12px;
            color: #666;
            line-height: 1.4;
        }
        
        .model-language-settings {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-radius: 10px;
            border: 2px solid #fbbf24;
        }
        
        .model-language-settings h3 {
            margin-bottom: 12px;
            color: #92400e;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .language-radio-group {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        
        .language-radio {
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 8px 12px;
            background: white;
            border-radius: 8px;
            border: 2px solid #e5e7eb;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .language-radio:hover {
            border-color: #fbbf24;
        }
        
        .language-radio input[type="radio"] {
            cursor: pointer;
        }
        
        .language-radio input[type="radio"]:checked + label {
            color: #92400e;
            font-weight: 600;
        }
        
        .language-radio.selected {
            background: #fef3c7;
            border-color: #fbbf24;
        }
        
        .audio-processing-settings {
            margin-bottom: 20px; 
            padding: 15px; 
            background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); 
            border-radius: 10px;
            border: 2px solid #66bb6a;
        }
        
        .audio-processing-settings h3 {
            margin-bottom: 12px;
            color: #2e7d32;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .translation-settings {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #e8f4fd 0%, #e3f2fd 100%);
            border-radius: 10px;
            border: 2px solid #90caf9;
        }
        
        .translation-settings h3 {
            margin-bottom: 12px;
            color: var(--deepl);
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .deepl-settings-panel {
            display: none;
            margin-top: 15px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            border: 1px solid #dbeafe;
        }
        
        .deepl-settings-panel.active {
            display: block;
        }
        
        .deepl-api-input {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            margin-bottom: 10px;
            font-family: monospace;
        }
        
        .deepl-api-input:focus {
            outline: none;
            border-color: var(--deepl);
        }
        
        .language-selector {
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: 10px;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .language-select {
            padding: 8px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
        }
        
        .language-select:hover {
            border-color: var(--deepl);
        }
        
        .swap-languages {
            padding: 8px 12px;
            background: var(--deepl);
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 18px;
            transition: transform 0.3s;
        }
        
        .swap-languages:hover {
            transform: rotate(180deg);
        }
        
        .translation-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .toggle-switch {
            position: relative;
            width: 50px;
            height: 24px;
            background: #ccc;
            border-radius: 24px;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .toggle-switch.active {
            background: var(--success);
        }
        
        .toggle-slider {
            position: absolute;
            top: 2px;
            left: 2px;
            width: 20px;
            height: 20px;
            background: white;
            border-radius: 50%;
            transition: transform 0.3s;
        }
        
        .toggle-switch.active .toggle-slider {
            transform: translateX(26px);
        }
        
        .translation-status {
            font-size: 12px;
            color: #666;
            margin-top: 8px;
            padding: 5px 10px;
            background: #f0f0f0;
            border-radius: 5px;
            display: none;
        }
        
        .translation-status.active {
            display: block;
        }
        
        .translation-status.success {
            background: #d1fae5;
            color: #065f46;
        }
        
        .translation-status.error {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .transcription-item {
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 15px;
            animation: fadeIn 0.5s;
            border-left: 4px solid var(--primary);
            position: relative;
        }
        
        .transcription-item.youtube-source {
            border-left-color: var(--youtube);
            background: linear-gradient(135deg, #fff5f5 0%, #ffeeee 100%);
        }
        
        .transcription-item.with-translation {
            border-left-color: var(--deepl);
        }
        
        .transcription-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .transcription-time {
            font-size: 12px;
            color: #666;
        }
        
        .language-badge {
            font-size: 11px;
            padding: 2px 8px;
            background: var(--primary);
            color: white;
            border-radius: 12px;
        }
        
        .source-badge {
            font-size: 11px;
            padding: 2px 8px;
            background: var(--youtube);
            color: white;
            border-radius: 12px;
            margin-left: 5px;
        }
        
        .transcription-original {
            font-size: 16px;
            line-height: 1.6;
            color: #333;
            margin-bottom: 10px;
        }
        
        .transcription-translation {
            font-size: 15px;
            line-height: 1.6;
            color: #1a365d;
            padding: 10px;
            background: linear-gradient(135deg, #e8f4fd 0%, #e3f2fd 100%);
            border-radius: 8px;
            border-left: 3px solid var(--deepl);
        }
        
        .translation-label {
            font-size: 11px;
            color: var(--deepl);
            font-weight: 600;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .model-selector {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #f0f0ff 0%, #faf0ff 100%);
            border-radius: 10px;
            border: 2px solid #e0e0ff;
        }
        
        .model-selector h3 {
            margin-bottom: 10px;
            color: var(--primary);
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .model-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 10px;
        }
        
        .model-option {
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            text-align: center;
            position: relative;
        }
        
        .model-option:hover {
            border-color: var(--primary);
            background: #f8f8ff;
        }
        
        .model-option.selected {
            border-color: var(--primary);
            background: linear-gradient(135deg, #667eea20 0%, #764ba220 100%);
        }
        
        .model-option.downloading {
            border-color: var(--warning);
            background: #fff9e6;
            cursor: not-allowed;
        }
        
        .model-option.installed::after {
            content: '✔';
            position: absolute;
            top: 5px;
            right: 5px;
            color: var(--success);
            font-weight: bold;
        }
        
        .model-name {
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 4px;
        }
        
        .model-size {
            font-size: 11px;
            color: #666;
        }
        
        .model-speed {
            font-size: 11px;
            color: #999;
            margin-top: 2px;
        }
        
        .download-progress {
            margin-top: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 8px;
            display: none;
        }
        
        .download-progress.active {
            display: block;
        }
        
        .progress-bar {
            height: 20px;
            background: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
            margin-top: 5px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--primary), var(--secondary));
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 12px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse 2s infinite;
        }
        
        .status-dot.inactive {
            background: var(--danger);
        }
        
        .status-dot.active {
            background: var(--success);
        }
        
        .status-dot.processing {
            background: var(--warning);
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .device-selector {
            margin-bottom: 20px;
        }
        
        .device-selector label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #555;
        }
        
        .device-selector select {
            width: 100%;
            padding: 10px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            background: white;
            cursor: pointer;
            transition: border-color 0.3s;
        }
        
        .device-selector select:hover {
            border-color: var(--primary);
        }
        
        .control-buttons {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .btn {
            flex: 1;
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            color: white;
        }
        
        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-danger {
            background: var(--danger);
            color: white;
        }
        
        .btn-danger:hover:not(:disabled) {
            background: #dc2626;
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .settings-panel {
            margin-bottom: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
        }
        
        .settings-panel h4 {
            margin-bottom: 10px;
            color: #555;
            font-size: 14px;
        }
        
        .setting-item {
            margin-bottom: 15px;
        }
        
        .setting-item label {
            display: block;
            font-size: 12px;
            color: #666;
            margin-bottom: 4px;
        }
        
        .setting-item input[type="range"] {
            width: 100%;
        }
        
        .setting-value {
            font-size: 12px;
            color: var(--primary);
            float: right;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }
        
        .stat-card {
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: var(--primary);
        }
        
        .stat-label {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        
        .transcription-area {
            min-height: 500px;
        }
        
        .transcription-controls {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }
        
        .transcription-list {
            max-height: 600px;
            overflow-y: auto;
            padding-right: 10px;
        }
        
        .transcription-item:hover {
            background: #e9ecef;
            transform: translateX(5px);
            transition: all 0.3s;
        }
        
        .transcription-confidence {
            position: absolute;
            top: 15px;
            right: 15px;
            font-size: 11px;
            color: #999;
        }
        
        .voice-indicator {
            height: 80px;
            background: linear-gradient(135deg, #f0f0f0 0%, #e0e0e0 100%);
            border-radius: 10px;
            margin-top: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        
        .voice-bars {
            display: flex;
            gap: 3px;
            height: 100%;
            align-items: center;
        }
        
        .voice-bar {
            width: 4px;
            background: var(--primary);
            border-radius: 2px;
            transition: height 0.1s;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }
        
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.3;
        }
        
        .tooltip {
            position: relative;
            display: inline-block;
            cursor: help;
        }
        
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 200px;
            background-color: #555;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 8px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 12px;
        }
        
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideUp {
            from { 
                opacity: 0;
                transform: translateY(20px);
            }
            to { 
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .alert {
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            animation: slideDown 0.3s;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .alert-success {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }
        
        .alert-error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        
        .alert-info {
            background: #dbeafe;
            color: #1e40af;
            border: 1px solid #bfdbfe;
        }
        
        .alert-warning {
            background: #fed7aa;
            color: #92400e;
            border: 1px solid #fdba74;
        }
        
        @keyframes slideDown {
            from {
                opacity: 0;
                transform: translateY(-10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                <span>🎙️</span>
                <span>Whisper + DeepL + YouTube</span>
                <span>🌍</span>
            </h1>
            <p>Gerçek zamanlı transkripsiyon, çeviri ve YouTube desteği</p>
        </div>
        
        <div id="alerts"></div>
        
        <div class="main-grid">
            <!-- Sol Panel - Kontroller -->
            <div class="card control-panel">
                
                <!-- YouTube Panel -->
                <div class="youtube-panel">
                    <h3>
                        📺 YouTube Transkripsiyon
                        <span class="tooltip">ℹ️
                            <span class="tooltiptext">YouTube videolarını transkribe edin</span>
                        </span>
                    </h3>
                    
                    <!-- Cookie Import Bölümü -->
                    <div style="margin-bottom: 15px; padding: 10px; background: #fff; border-radius: 8px;">
                        <label style="font-size: 13px; color: #666; display: block; margin-bottom: 8px;">
                            🍪 Cookie Dosyası (YouTube bot koruması için gerekli)
                        </label>
                        <input type="file" 
                               id="cookieFile" 
                               accept=".txt"
                               style="display: none;"
                               onchange="uploadCookieFile(this)">
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <button onclick="document.getElementById('cookieFile').click()" 
                                    style="padding: 8px 15px; background: #ff9800; color: white; border: none; border-radius: 5px; cursor: pointer; font-size: 13px;">
                                📁 Cookie Dosyası Seç
                            </button>
                            <span id="cookieStatus" style="font-size: 12px; color: #666;">
                                Dosya seçilmedi
                            </span>
                        </div>
                        <div style="margin-top: 8px; font-size: 11px; color: #999;">
                            Chrome'da "Get cookies.txt LOCALLY" eklentisi ile export edin
                        </div>
                    </div>
                    
                    <!-- YouTube Model Seçimi -->
                    <div style="margin-bottom: 15px; padding: 10px; background: #fff; border-radius: 8px;">
                        <label style="font-size: 13px; color: #666; display: block; margin-bottom: 8px;">
                            🤖 YouTube için Model Seçimi
                        </label>
                        <select id="youtubeModelSelect" style="width: 100%; padding: 8px; border: 2px solid #e0e0e0; border-radius: 6px; font-size: 13px;">
                            <option value="tiny">Tiny (39 MB) - Çok Hızlı</option>
                            <option value="base">Base (74 MB) - Hızlı</option>
                            <option value="small">Small (244 MB) - Dengeli</option>
                            <option value="medium" selected>Medium (769 MB) - İyi</option>
                            <option value="large-v3">Large-v3 (1.5 GB) - En İyi</option>
                            <option value="turbo">Turbo (809 MB) - Hızlı+İyi</option>
                        </select>
                        <div id="youtubeModelStatus" style="margin-top: 5px; font-size: 11px; color: #666;">
                            Seçili model: Medium
                        </div>
                    </div>
                    
                    <div class="youtube-input-group">
                        <input type="text" 
                               id="youtubeUrl" 
                               class="youtube-input" 
                               placeholder="YouTube URL veya Video ID">
                        <button class="btn-youtube" id="youtubeBtn" onclick="processYouTube()">
                            <span>▶</span> İşle
                        </button>
                    </div>
                    <div style="margin-top:8px; display:flex; align-items:center; gap:8px; background:#fff; padding:8px; border-radius:6px;">
                        <input type="checkbox" id="exportSrt" />
                        <label for="exportSrt" style="font-size:13px; color:#444;">Zaman damgalı SRT olarak dışa aktar</label>
                    </div>
                    
                    <div class="youtube-progress" id="youtubeProgress">
                        <div class="youtube-progress-text" id="youtubeProgressText">Video indiriliyor...</div>
                        <div class="youtube-progress-bar">
                            <div class="youtube-progress-fill" id="youtubeProgressFill">0%</div>
                        </div>
                    </div>
                    
                    <div class="youtube-info" id="youtubeInfo">
                        <div class="youtube-info-title" id="youtubeTitle"></div>
                        <div class="youtube-info-details" id="youtubeDetails"></div>
                    </div>
                </div>
                
                <!-- Model Dil Seçimi -->
                <div class="model-language-settings">
                    <h3>
                        🌍 Model Dili
                        <span class="tooltip">ℹ️
                            <span class="tooltiptext">Konuşmanın hangi dilde olduğunu belirtin</span>
                        </span>
                    </h3>
                    
                    <div class="language-radio-group">
                        <div class="language-radio">
                            <input type="radio" id="langTr" name="whisperLang" value="tr" checked>
                            <label for="langTr">🇹🇷 Türkçe</label>
                        </div>
                        <div class="language-radio">
                            <input type="radio" id="langEn" name="whisperLang" value="en">
                            <label for="langEn">🇬🇧 İngilizce</label>
                        </div>
                        <div class="language-radio">
                            <input type="radio" id="langDe" name="whisperLang" value="de">
                            <label for="langDe">🇩🇪 Almanca</label>
                        </div>
                    </div>
                </div>
                
                <!-- Ses İşleme Ayarları -->
                <div class="audio-processing-settings">
                    <h3>
                        🎧 Ses İşleme (Dizi/Film)
                        <span class="tooltip">ℹ️
                            <span class="tooltiptext">Transkripsiyon kalitesini artırır</span>
                        </span>
                    </h3>
                    
                    <!-- Gürültü Azaltma -->
                    <div class="setting-item">
                        <label>
                            Gürültü Azaltma
                            <span class="setting-value" id="noiseValue">0.5</span>
                        </label>
                        <input type="range" id="noiseReduction" 
                               min="0" max="1" step="0.1" value="0.5" 
                               onchange="updateSetting('noise_level', this.value)">
                        <div style="font-size: 11px; color: #666;">
                            0=Kapalı | 0.5=Orta | 1=Maksimum
                        </div>
                    </div>
                    
                    <!-- Ses Dengeleme -->
                    <div class="setting-item">
                        <label>
                            <input type="checkbox" id="dynamicCompression" checked
                                   onchange="updateSetting('compression', this.checked)">
                            Ses Dengeleme (Fısıltı/Bağırma)
                        </label>
                    </div>
                    
                    <!-- Konuşma Güçlendirme -->
                    <div class="setting-item">
                        <label>
                            <input type="checkbox" id="speechEnhance" checked
                                   onchange="updateSetting('enhance_speech', this.checked)">
                            Diyalog Netleştirme
                        </label>
                    </div>
                    
                    <!-- Pre-emphasis -->
                    <div class="setting-item">
                        <label>
                            Pre-emphasis (Tiz Vurgu)
                            <span class="setting-value" id="preemphValue">0.97</span>
                        </label>
                        <input type="range" id="preemphasis" 
                               min="0" max="1" step="0.01" value="0.97" 
                               onchange="updateSetting('preemphasis', this.value)">
                        <div style="font-size: 11px; color: #666;">
                            Konsonantları belirginleştirir
                        </div>
                    </div>
                </div>
                
                <!-- DeepL Çeviri Ayarları -->
                <div class="translation-settings">
                    <h3>
                        🌍 DeepL Çeviri
                        <span class="tooltip">ℹ️
                            <span class="tooltiptext">Otomatik çeviri için DeepL servisi</span>
                        </span>
                    </h3>
                    
                    <div class="translation-toggle">
                        <label>Çeviri Servisi:</label>
                        <div class="toggle-switch" id="translationToggle" onclick="toggleTranslation()">
                            <div class="toggle-slider"></div>
                        </div>
                        <span id="translationToggleText">Kapalı</span>
                    </div>
                    
                    <!-- DeepL Ayarları Paneli (Toggle açıkken görünür) -->
                    <div class="deepl-settings-panel" id="deeplSettingsPanel">
                        <input type="password" 
                               class="deepl-api-input" 
                               id="deeplApiKey"
                               placeholder="DeepL API Key (xxxxx-xxxxx-xxxxx:fx)"
                               onchange="saveDeepLKey(this.value)">
                        
                        <div class="language-selector">
                            <select class="language-select" id="sourceLang" onchange="updateLanguageSettings()">
                                <option value="TR">🇹🇷 Türkçe</option>
                                <option value="EN">🇬🇧 İngilizce</option>
                                <option value="DE">🇩🇪 Almanca</option>
                                <option value="FR">🇫🇷 Fransızca</option>
                                <option value="ES">🇪🇸 İspanyolca</option>
                                <option value="IT">🇮🇹 İtalyanca</option>
                                <option value="RU">🇷🇺 Rusça</option>
                                <option value="JA">🇯🇵 Japonca</option>
                                <option value="ZH">🇨🇳 Çince</option>
                            </select>
                            
                            <button class="swap-languages" onclick="swapLanguages()">⇄</button>
                            
                            <select class="language-select" id="targetLang" onchange="updateLanguageSettings()">
                                <option value="EN">🇬🇧 İngilizce</option>
                                <option value="TR">🇹🇷 Türkçe</option>
                                <option value="DE">🇩🇪 Almanca</option>
                                <option value="FR">🇫🇷 Fransızca</option>
                                <option value="ES">🇪🇸 İspanyolca</option>
                                <option value="IT">🇮🇹 İtalyanca</option>
                                <option value="RU">🇷🇺 Rusça</option>
                                <option value="JA">🇯🇵 Japonca</option>
                                <option value="ZH">🇨🇳 Çince</option>
                            </select>
                        </div>
                        
                        <div style="font-size: 11px; color: #666; margin-top: 8px;">
                            <a href="https://www.deepl.com/pro#developer" target="_blank" style="color: var(--deepl);">
                                🔑 DeepL Free API Key almak için tıklayın
                            </a>
                        </div>
                    </div>
                    
                    <div class="translation-status" id="translationStatus">
                        Çeviri servisi hazır değil
                    </div>
                </div>
                
                <!-- Model Seçimi -->
                <div class="model-selector">
                    <h3>
                        🤖 Model Seçimi
                        <span class="tooltip">ℹ️
                            <span class="tooltiptext">Daha büyük model = Daha iyi doğruluk ama daha yavaş</span>
                        </span>
                    </h3>
                    <div class="model-grid">
                        <div class="model-option" data-model="tiny" onclick="selectModel('tiny')">
                            <div class="model-name">Tiny</div>
                            <div class="model-size">39 MB</div>
                            <div class="model-speed">Çok Hızlı</div>
                        </div>
                        <div class="model-option" data-model="base" onclick="selectModel('base')">
                            <div class="model-name">Base</div>
                            <div class="model-size">74 MB</div>
                            <div class="model-speed">Hızlı</div>
                        </div>
                        <div class="model-option" data-model="small" onclick="selectModel('small')">
                            <div class="model-name">Small</div>
                            <div class="model-size">244 MB</div>
                            <div class="model-speed">Dengeli</div>
                        </div>
                        <div class="model-option selected" data-model="medium" onclick="selectModel('medium')">
                            <div class="model-name">Medium</div>
                            <div class="model-size">769 MB</div>
                            <div class="model-speed">İyi</div>
                        </div>
                        <div class="model-option" data-model="large-v3" onclick="selectModel('large-v3')">
                            <div class="model-name">Large-v3</div>
                            <div class="model-size">1.5 GB</div>
                            <div class="model-speed">En İyi</div>
                        </div>
                        <div class="model-option" data-model="turbo" onclick="selectModel('turbo')">
                            <div class="model-name">Turbo</div>
                            <div class="model-size">809 MB</div>
                            <div class="model-speed">Hızlı+İyi</div>
                        </div>
                    </div>
                    <div class="download-progress" id="downloadProgress">
                        <div id="downloadText">Model indiriliyor...</div>
                        <div class="progress-bar">
                            <div class="progress-fill" id="progressFill">0%</div>
                        </div>
                    </div>
                    <button class="btn btn-primary" onclick="loadSelectedModel()" style="width: 100%; margin-top: 10px;">
                        Model Yükle
                    </button>
                </div>
                
                <!-- Durum Göstergesi -->
                <div class="status-indicator">
                    <div class="status-dot inactive" id="statusDot"></div>
                    <span id="statusText">Model seçin ve yükleyin</span>
                </div>
                
                <!-- Ses Cihazı Seçimi -->
                <div class="device-selector">
                    <label for="deviceSelect">Ses Kaynağı:</label>
                    <select id="deviceSelect">
                        <option value="">Yükleniyor...</option>
                    </select>
                </div>
                
                <!-- Kontrol Butonları -->
                <div class="control-buttons">
                    <button class="btn btn-primary" id="startBtn" onclick="startCapture()" disabled>
                        <span>▶️</span> Başlat
                    </button>
                    <button class="btn btn-danger" id="stopBtn" onclick="stopCapture()" disabled>
                        <span>⏹️</span> Durdur
                    </button>
                </div>
                
                <!-- Ayarlar -->
                <div class="settings-panel">
                    <h4>⚙️ Ayarlar</h4>
                    
                    <!-- VAD Hassasiyeti -->
                    <div class="setting-item">
                        <label>
                            VAD Hassasiyeti
                            <span class="setting-value" id="vadValue">0.4</span>
                        </label>
                        <input type="range" id="vadLevel" 
                               min="0.1" max="0.9" step="0.1" value="0.4" 
                               onchange="updateSetting('vad', this.value)">
                        <div style="font-size: 11px; color: #666; margin-top: 4px;">
                            0.1=Çok hassas | 0.4=İdeal | 0.9=Az hassas
                        </div>
                    </div>
                    
                    <!-- Sessizlik Süresi -->
                    <div class="setting-item">
                        <label>
                            Sessizlik Süresi (saniye)
                            <span class="setting-value" id="silenceValue">0.8</span>
                        </label>
                        <input type="range" id="silenceDuration" 
                               min="0.3" max="3.0" step="0.1" value="0.8" 
                               onchange="updateSetting('silence', this.value)">
                        <div style="font-size: 11px; color: #666; margin-top: 4px;">
                            0.3=Çok hızlı | 0.8=İdeal | 3.0=Çok yavaş
                        </div>
                    </div>
                    
                    <!-- Minimum Konuşma Süresi -->
                    <div class="setting-item">
                        <label>
                            Minimum Konuşma Süresi (saniye)
                            <span class="setting-value" id="minSpeechValue">0.3</span>
                        </label>
                        <input type="range" id="minSpeechDuration" 
                               min="0.1" max="1.0" step="0.1" value="0.3" 
                               onchange="updateSetting('min_speech', this.value)">
                        <div style="font-size: 11px; color: #666; margin-top: 4px;">
                            Bundan kısa sesler yok sayılır
                        </div>
                    </div>
                </div>
                
                <!-- Temizle Butonu -->
                <button class="btn btn-secondary" onclick="clearTranscriptions()" style="width: 100%; margin-bottom: 20px;">
                    <span>🗑️</span> Temizle
                </button>
                
                <!-- İstatistikler -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-value" id="totalCount">0</div>
                        <div class="stat-label">Toplam Kayıt</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" id="sessionTime">00:00</div>
                        <div class="stat-label">Süre</div>
                    </div>
                </div>
                
                <!-- Ses Göstergesi -->
                <div class="voice-indicator" id="voiceIndicator">
                    <div class="voice-bars" id="voiceBars"></div>
                </div>
            </div>
            
            <!-- Sağ Panel - Transcriptions -->
            <div class="card transcription-area">
                <div class="transcription-controls">
                    <h2>📝 Transkripsiyon & Çeviri Sonuçları</h2>
                    <div>
                        <button class="btn btn-secondary" onclick="downloadTranscriptions()">
                            <span>💾</span> İndir
                        </button>
                    </div>
                </div>
                
                <div class="transcription-list" id="transcriptionList">
                    <div class="empty-state">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                        </svg>
                        <p>Henüz kayıt yok</p>
                        <p style="font-size: 14px; margin-top: 10px;">Model seçip yükledikten sonra başlat butonuna tıklayın veya YouTube linki girin</p>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Socket.IO bağlantısı
        const socket = io();
        
        // Global değişkenler
        let isCapturing = false;
        let sessionStartTime = null;
        let timerInterval = null;
        let selectedModel = 'medium';
        let modelStatus = {};
        let settings = {
            silence_duration: 0.8,
            vad_threshold: 0.4,
            min_speech_duration: 0.3,
            noise_level: 0.5,
            compression: true,
            enhance_speech: true,
            preemphasis: 0.97
        };
        let translationSettings = {
            enabled: false,
            apiKey: '',
            sourceLang: 'TR',
            targetLang: 'EN'
        };
        
        // Sayfa yüklendiğinde
        window.onload = async function() {
            createVoiceBars();
            setupSocketListeners();
            await loadDevices();
            await checkInstalledModels();
            loadTranslationSettings();
            loadAudioProcessingSettings();
            
            // Model dil seçimi listener'ları
            document.querySelectorAll('input[name="whisperLang"]').forEach(radio => {
                radio.addEventListener('change', function() {
                    localStorage.setItem('whisperLanguage', this.value);
                    
                    // Seçili radio'nun parent div'ine selected class ekle
                    document.querySelectorAll('.language-radio').forEach(div => {
                        div.classList.remove('selected');
                    });
                    this.parentElement.classList.add('selected');
                });
            });
            
            // Saved model dilini yükle
            const savedWhisperLang = localStorage.getItem('whisperLanguage') || 'tr';
            document.querySelector(`input[name="whisperLang"][value="${savedWhisperLang}"]`).checked = true;
            document.querySelector(`input[name="whisperLang"][value="${savedWhisperLang}"]`).parentElement.classList.add('selected');
            
            // YouTube model seçimi listener
            document.getElementById('youtubeModelSelect').addEventListener('change', function() {
                const selectedModel = this.value;
                const modelNames = {
                    'tiny': 'Tiny',
                    'base': 'Base',
                    'small': 'Small',
                    'medium': 'Medium',
                    'large-v3': 'Large-v3',
                    'turbo': 'Turbo'
                };
                document.getElementById('youtubeModelStatus').textContent = `Seçili model: ${modelNames[selectedModel]}`;
            });
            
            // YouTube URL input'una Enter tuşu desteği
            document.getElementById('youtubeUrl').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    processYouTube();
                }
            });
        };
        
        // Cookie dosyası yükleme
        async function uploadCookieFile(input) {
            const file = input.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('cookie_file', file);
            
            try {
                const response = await fetch('/api/upload_cookies', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('cookieStatus').innerHTML = 
                        `<span style="color: #10b981;">✅ ${file.name} yüklendi</span>`;
                    showAlert('Cookie dosyası başarıyla yüklendi!', 'success');
                } else {
                    document.getElementById('cookieStatus').innerHTML = 
                        `<span style="color: #ef4444;">❌ Yükleme başarısız</span>`;
                    showAlert(`Cookie yükleme hatası: ${data.error}`, 'error');
                }
            } catch (error) {
                showAlert(`Hata: ${error.message}`, 'error');
            }
        }
        
        // YouTube işleme
        async function processYouTube() {
            const url = document.getElementById('youtubeUrl').value.trim();
            console.log('[YT] processYouTube clicked, url=', url);
            
            if (!url) {
                showAlert('Lütfen bir YouTube URL veya Video ID girin', 'error');
                return;
            }
            
            // Cookie kontrolü
            const cookieStatus = document.getElementById('cookieStatus').textContent;
            if (!cookieStatus.includes('✅')) {
                if (!confirm('Cookie dosyası yüklenmemiş. YouTube bot koruması nedeniyle video indirilemeyebilir. Devam etmek istiyor musunuz?')) {
                    return;
                }
            }
            
            const youtubeBtn = document.getElementById('youtubeBtn');
            const progressEl = document.getElementById('youtubeProgress');
            const progressText = document.getElementById('youtubeProgressText');
            const progressFill = document.getElementById('youtubeProgressFill');
            const infoEl = document.getElementById('youtubeInfo');
            
            youtubeBtn.disabled = true;
            progressEl.classList.add('active');
            progressText.textContent = 'Video bilgileri alınıyor...';
            progressFill.style.width = '10%';
            
            try {
                // Model dilini al
                const whisperLang = document.querySelector('input[name="whisperLang"]:checked').value;
                
                // YouTube için seçili modeli al
                const youtubeModel = document.getElementById('youtubeModelSelect').value;
                
                // Model yüklendiğini göster
                progressText.textContent = `${youtubeModel} modeli yükleniyor...`;
                progressFill.style.width = '15%';
                
                console.log('[YT] sending request to /api/youtube_transcribe', { url, whisperLang, youtubeModel, export_srt: document.getElementById('exportSrt').checked });
                const response = await fetch('/api/youtube_transcribe', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        url: url,
                        whisper_language: whisperLang,
                        model: youtubeModel,  // Model bilgisini gönder
                        export_srt: document.getElementById('exportSrt').checked
                    })
                });
                console.log('[YT] response status', response.status);
                
                const data = await response.json();
                console.log('[YT] response json', data);
                
                if (data.success) {
                    progressText.textContent = 'İşlem başarıyla tamamlandı!';
                    progressFill.style.width = '100%';
                    progressFill.textContent = '100%';
                    
                    // Video bilgilerini göster
                    if (data.video_info) {
                        document.getElementById('youtubeTitle').textContent = data.video_info.title;
                        document.getElementById('youtubeDetails').textContent = 
                            `Süre: ${data.video_info.duration} | Yükleyen: ${data.video_info.uploader}`;
                        infoEl.classList.add('active');
                    }
                    
                    showAlert('YouTube videosu başarıyla işlendi!', 'success');
                    if (data.srt_path) {
                        showAlert(`SRT oluşturuldu: ${data.srt_path}`, 'success');
                    }
                    
                    setTimeout(() => {
                        progressEl.classList.remove('active');
                        document.getElementById('youtubeUrl').value = '';
                        progressFill.style.width = '0%';
                    }, 3000);
                } else {
                    showAlert(`Hata: ${data.error}`, 'error');
                    progressEl.classList.remove('active');
                }
            } catch (error) {
                showAlert(`Hata: ${error.message}`, 'error');
                progressEl.classList.remove('active');
            } finally {
                youtubeBtn.disabled = false;
            }
        }
        
        // Ses işleme ayarlarını yükle
        function loadAudioProcessingSettings() {
            // Saved settings
            const savedNoiseLevel = localStorage.getItem('noiseLevel');
            const savedCompression = localStorage.getItem('compression');
            const savedEnhanceSpeech = localStorage.getItem('enhanceSpeech');
            const savedPreemphasis = localStorage.getItem('preemphasis');
            
            if (savedNoiseLevel !== null) {
                document.getElementById('noiseReduction').value = savedNoiseLevel;
                document.getElementById('noiseValue').textContent = savedNoiseLevel;
                settings.noise_level = parseFloat(savedNoiseLevel);
            }
            
            if (savedCompression !== null) {
                document.getElementById('dynamicCompression').checked = savedCompression === 'true';
                settings.compression = savedCompression === 'true';
            }
            
            if (savedEnhanceSpeech !== null) {
                document.getElementById('speechEnhance').checked = savedEnhanceSpeech === 'true';
                settings.enhance_speech = savedEnhanceSpeech === 'true';
            }
            
            if (savedPreemphasis !== null) {
                document.getElementById('preemphasis').value = savedPreemphasis;
                document.getElementById('preemphValue').textContent = savedPreemphasis;
                settings.preemphasis = parseFloat(savedPreemphasis);
            }
        }
        
        // DeepL API Key kaydet
        function saveDeepLKey(apiKey) {
            translationSettings.apiKey = apiKey;
            localStorage.setItem('deeplApiKey', apiKey);
            
            if (apiKey) {
                // API key'i sunucuya gönder
                fetch('/api/deepl_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({api_key: apiKey})
                }).then(response => response.json())
                  .then(data => {
                    if (data.success) {
                        updateTranslationStatus('API key kaydedildi', 'success');
                    } else {
                        updateTranslationStatus('API key geçersiz', 'error');
                    }
                });
            }
        }
        
        // Çeviri ayarlarını yükle
        function loadTranslationSettings() {
            // Çeviri etkin mi?
            const savedEnabled = localStorage.getItem('translationEnabled') === 'true';
            
            if (savedEnabled) {
                translationSettings.enabled = true;
                document.getElementById('translationToggle').classList.add('active');
                document.getElementById('translationToggleText').textContent = 'Açık';
                document.getElementById('deeplSettingsPanel').classList.add('active');
            }
            
            // API key varsa yükle
            const savedApiKey = localStorage.getItem('deeplApiKey');
            if (savedApiKey) {
                document.getElementById('deeplApiKey').value = savedApiKey;
                translationSettings.apiKey = savedApiKey;
                if (translationSettings.enabled) {
                    saveDeepLKey(savedApiKey);
                }
            }
            
            // Dil ayarlarını yükle (DeepL için)
            const savedSourceLang = localStorage.getItem('sourceLang') || 'TR';
            const savedTargetLang = localStorage.getItem('targetLang') || 'EN';
            
            document.getElementById('sourceLang').value = savedSourceLang;
            document.getElementById('targetLang').value = savedTargetLang;
            
            translationSettings.sourceLang = savedSourceLang;
            translationSettings.targetLang = savedTargetLang;
        }
        
        // Dilleri değiştir
        function swapLanguages() {
            const sourceLang = document.getElementById('sourceLang');
            const targetLang = document.getElementById('targetLang');
            
            const temp = sourceLang.value;
            sourceLang.value = targetLang.value;
            targetLang.value = temp;
            
            updateLanguageSettings();
        }
        
        // Dil ayarlarını güncelle
        function updateLanguageSettings() {
            const sourceLang = document.getElementById('sourceLang').value;
            const targetLang = document.getElementById('targetLang').value;
            
            translationSettings.sourceLang = sourceLang;
            translationSettings.targetLang = targetLang;
            
            localStorage.setItem('sourceLang', sourceLang);
            localStorage.setItem('targetLang', targetLang);
            
            // Sunucuya gönder
            fetch('/api/translation_settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(translationSettings)
            });
        }
        
        // Çeviri toggle
        function toggleTranslation() {
            const toggle = document.getElementById('translationToggle');
            const text = document.getElementById('translationToggleText');
            const panel = document.getElementById('deeplSettingsPanel');
            
            translationSettings.enabled = !translationSettings.enabled;
            
            if (translationSettings.enabled) {
                toggle.classList.add('active');
                text.textContent = 'Açık';
                panel.classList.add('active');
                
                // API key kontrolü
                if (!translationSettings.apiKey) {
                    updateTranslationStatus('Lütfen DeepL API key girin', 'warning');
                    document.getElementById('deeplApiKey').focus();
                } else {
                    updateTranslationStatus('Çeviri aktif', 'success');
                }
            } else {
                toggle.classList.remove('active');
                text.textContent = 'Kapalı';
                panel.classList.remove('active');
                updateTranslationStatus('Çeviri devre dışı', '');
            }
            
            localStorage.setItem('translationEnabled', translationSettings.enabled);
            
            // Sunucuya gönder
            fetch('/api/translation_settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(translationSettings)
            });
        }
        
        // Çeviri durumunu güncelle
        function updateTranslationStatus(message, type) {
            const status = document.getElementById('translationStatus');
            status.textContent = message;
            status.className = 'translation-status active';
            
            if (type) {
                status.classList.add(type);
            }
            
            setTimeout(() => {
                status.classList.remove('active');
            }, 3000);
        }
        
        // Model seçimi
        function selectModel(model) {
            selectedModel = model;
            document.querySelectorAll('.model-option').forEach(el => {
                el.classList.remove('selected');
            });
            document.querySelector(`[data-model="${model}"]`).classList.add('selected');
        }
        
        // Model yükle
        async function loadSelectedModel() {
            const modelEl = document.querySelector(`[data-model="${selectedModel}"]`);
            
            if (modelEl.classList.contains('downloading')) {
                showAlert('Model zaten indiriliyor...', 'warning');
                return;
            }
            
            showAlert(`${selectedModel} modeli yükleniyor...`, 'info');
            modelEl.classList.add('downloading');
            document.getElementById('downloadProgress').classList.add('active');
            
            try {
                const response = await fetch('/api/load_model', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({model: selectedModel})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    modelEl.classList.remove('downloading');
                    modelEl.classList.add('installed');
                    document.getElementById('downloadProgress').classList.remove('active');
                    
                    showAlert(`${selectedModel} modeli başarıyla yüklendi (${data.device})`, 'success');
                    document.getElementById('statusText').textContent = `Hazır - ${selectedModel} (${data.device})`;
                    document.getElementById('statusDot').className = 'status-dot inactive';
                    document.getElementById('startBtn').disabled = false;
                } else {
                    modelEl.classList.remove('downloading');
                    document.getElementById('downloadProgress').classList.remove('active');
                    showAlert(`Model yüklenemedi: ${data.error}`, 'error');
                }
            } catch (error) {
                modelEl.classList.remove('downloading');
                document.getElementById('downloadProgress').classList.remove('active');
                showAlert(`Hata: ${error.message}`, 'error');
            }
        }
        
        // Yüklü modelleri kontrol et
        async function checkInstalledModels() {
            try {
                const response = await fetch('/api/check_models');
                const data = await response.json();
                
                data.installed.forEach(model => {
                    const modelEl = document.querySelector(`[data-model="${model}"]`);
                    if (modelEl) {
                        modelEl.classList.add('installed');
                    }
                });
                
                // Eğer yüklü model varsa otomatik seç
                if (data.current_model) {
                    selectModel(data.current_model);
                    document.getElementById('statusText').textContent = `Hazır - ${data.current_model}`;
                    document.getElementById('startBtn').disabled = false;
                }
            } catch (error) {
                console.error('Model kontrolü başarısız:', error);
            }
        }
        
        // Ses cihazlarını yükle
        async function loadDevices() {
            try {
                const response = await fetch('/api/devices');
                const devices = await response.json();
                
                const select = document.getElementById('deviceSelect');
                select.innerHTML = '';
                
                if (devices.length === 0) {
                    select.innerHTML = '<option value="">Ses cihazı bulunamadı</option>';
                    return;
                }
                
                let hasSystemAudio = false;
                
                devices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.id;
                    option.textContent = device.name;
                    
                    if (device.type === 'system') {
                        option.selected = true;
                        hasSystemAudio = true;
                    }
                    
                    select.appendChild(option);
                });
                
                if (!hasSystemAudio && devices.length > 0) {
                    select.selectedIndex = 0;
                }
                
            } catch (error) {
                console.error('Cihazlar yüklenemedi:', error);
            }
        }
        
        // Socket.IO dinleyicileri
        function setupSocketListeners() {
            socket.on('connect', () => {
                console.log('Sunucuya bağlandı');
            });
            
            socket.on('model_download_progress', (data) => {
                document.getElementById('downloadText').textContent = `Model indiriliyor: ${data.model}`;
                document.getElementById('progressFill').style.width = `${data.progress}%`;
                document.getElementById('progressFill').textContent = `${data.progress}%`;
            });
            
            socket.on('capture_started', (data) => {
                updateStatus('active', `Dinleniyor: ${data.device}`);
                startTimer();
            });
            
            socket.on('capture_stopped', () => {
                updateStatus('inactive', 'Durduruldu');
                stopTimer();
            });
            
            socket.on('voice_activity', (data) => {
                updateVoiceIndicator(data);
            });
            
            socket.on('youtube_progress', (data) => {
                const progressText = document.getElementById('youtubeProgressText');
                const progressFill = document.getElementById('youtubeProgressFill');
                
                progressText.textContent = data.status;
                progressFill.style.width = `${data.progress}%`;
                progressFill.textContent = `${data.progress}%`;
            });
            
            socket.on('new_transcription', (data) => {
                addTranscription(data);
                updateStats();
            });
            
            socket.on('error', (data) => {
                showAlert(`Hata: ${data.message}`, 'error');
            });
        }
        
        // Ayar güncelleme
        function updateSetting(setting, value) {
            if (setting === 'silence') {
                settings.silence_duration = parseFloat(value);
                document.getElementById('silenceValue').textContent = value;
            } else if (setting === 'vad') {
                settings.vad_threshold = parseFloat(value);
                document.getElementById('vadValue').textContent = value;
            } else if (setting === 'min_speech') {
                settings.min_speech_duration = parseFloat(value);
                document.getElementById('minSpeechValue').textContent = value;
            } else if (setting === 'noise_level') {
                settings.noise_level = parseFloat(value);
                document.getElementById('noiseValue').textContent = value;
                localStorage.setItem('noiseLevel', value);
            } else if (setting === 'compression') {
                settings.compression = value;
                localStorage.setItem('compression', value);
            } else if (setting === 'enhance_speech') {
                settings.enhance_speech = value;
                localStorage.setItem('enhanceSpeech', value);
            } else if (setting === 'preemphasis') {
                settings.preemphasis = parseFloat(value);
                document.getElementById('preemphValue').textContent = value;
                localStorage.setItem('preemphasis', value);
            }
            
            // Sunucuya gönder
            fetch('/api/update_settings', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(settings)
            });
        }
        
        // Yakalamayı başlat
        async function startCapture() {
            const deviceId = document.getElementById('deviceSelect').value;
            
            if (!deviceId) {
                showAlert('Lütfen bir ses cihazı seçin', 'error');
                return;
            }
            
            // Model dilini al
            const whisperLang = document.querySelector('input[name="whisperLang"]:checked').value;
            
            try {
                const response = await fetch('/api/start', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        device_id: parseInt(deviceId),
                        settings: settings,
                        whisper_language: whisperLang
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    isCapturing = true;
                    document.getElementById('startBtn').disabled = true;
                    document.getElementById('stopBtn').disabled = false;
                    document.getElementById('deviceSelect').disabled = true;
                    showAlert('Ses yakalama başladı - Konuşmalar otomatik algılanacak', 'success');
                } else {
                    showAlert('Yakalama başlatılamadı', 'error');
                }
            } catch (error) {
                showAlert(`Hata: ${error.message}`, 'error');
            }
        }
        
        // Yakalamayı durdur
        async function stopCapture() {
            try {
                const response = await fetch('/api/stop', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    isCapturing = false;
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('stopBtn').disabled = true;
                    document.getElementById('deviceSelect').disabled = false;
                    showAlert('Ses yakalama durduruldu', 'info');
                }
            } catch (error) {
                showAlert(`Hata: ${error.message}`, 'error');
            }
        }
        
        // Transcription ekle
        function addTranscription(data) {
            const list = document.getElementById('transcriptionList');
            
            // Boş durum mesajını kaldır
            if (list.querySelector('.empty-state')) {
                list.innerHTML = '';
            }
            
            const item = document.createElement('div');
            item.className = 'transcription-item';
            
            // YouTube kaynak kontrolü
            if (data.source === 'youtube') {
                item.classList.add('youtube-source');
            }
            
            // Çeviri varsa
            if (data.translation) {
                item.classList.add('with-translation');
                item.innerHTML = `
                    <div class="transcription-header">
                        <div class="transcription-time">🕐 ${data.timestamp}</div>
                        <div>
                            <span class="language-badge">${data.source_lang} → ${data.target_lang}</span>
                            ${data.source === 'youtube' ? '<span class="source-badge">YouTube</span>' : ''}
                        </div>
                    </div>
                    <div class="transcription-original">${data.text}</div>
                    <div class="transcription-translation">
                        <div class="translation-label">
                            <span>🌍</span>
                            <span>Çeviri (${data.target_lang})</span>
                        </div>
                        ${data.translation}
                    </div>
                    ${data.confidence ? `<div class="transcription-confidence">${Math.round(data.confidence * 100)}%</div>` : ''}
                `;
            } else {
                item.innerHTML = `
                    <div class="transcription-header">
                        <div class="transcription-time">🕐 ${data.timestamp}</div>
                        <div>
                            <span class="language-badge">${data.model_language || 'TR'}</span>
                            ${data.source === 'youtube' ? '<span class="source-badge">YouTube</span>' : ''}
                        </div>
                    </div>
                    <div class="transcription-original">${data.text}</div>
                    ${data.confidence ? `<div class="transcription-confidence">${Math.round(data.confidence * 100)}%</div>` : ''}
                `;
            }
            
            list.insertBefore(item, list.firstChild);
            
            // Toplam sayıyı güncelle
            const countEl = document.getElementById('totalCount');
            countEl.textContent = parseInt(countEl.textContent) + 1;
        }
        
        // Transcription'ları temizle
        async function clearTranscriptions() {
            if (!confirm('Tüm kayıtlar silinecek. Emin misiniz?')) {
                return;
            }
            
            try {
                const response = await fetch('/api/clear', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('transcriptionList').innerHTML = `
                        <div class="empty-state">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                            </svg>
                            <p>Henüz kayıt yok</p>
                            <p style="font-size: 14px; margin-top: 10px;">Başlat butonuna tıklayarak ses kaydını başlatın veya YouTube linki girin</p>
                        </div>
                    `;
                    document.getElementById('totalCount').textContent = '0';
                    showAlert('Kayıtlar temizlendi', 'success');
                }
            } catch (error) {
                showAlert(`Hata: ${error.message}`, 'error');
            }
        }
        
        // Transcription'ları indir
        function downloadTranscriptions() {
            const items = document.querySelectorAll('.transcription-item');
            if (items.length === 0) {
                showAlert('İndirilecek kayıt yok', 'error');
                return;
            }
            
            let content = 'WHISPER + DEEPL + YOUTUBE KAYITLARI\\n';
            content += '=' + '='.repeat(40) + '\\n';
            content += `Model: ${selectedModel}\\n`;
            content += `Tarih: ${new Date().toLocaleString('tr-TR')}\\n`;
            content += '=' + '='.repeat(40) + '\\n\\n';
            
            items.forEach(item => {
                const time = item.querySelector('.transcription-time').textContent;
                const original = item.querySelector('.transcription-original').textContent;
                const translation = item.querySelector('.transcription-translation');
                const isYouTube = item.classList.contains('youtube-source');
                
                content += `${time} ${isYouTube ? '[YouTube]' : '[Canlı]'}\\n`;
                content += `Orijinal: ${original}\\n`;
                if (translation) {
                    const translatedText = translation.textContent.replace(/🌍.*?Çeviri.*?\\)/, '').trim();
                    content += `Çeviri: ${translatedText}\\n`;
                }
                content += '\\n';
            });
            
            const blob = new Blob([content], {type: 'text/plain;charset=utf-8'});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `transcriptions_${selectedModel}_${new Date().toISOString().slice(0,10)}.txt`;
            a.click();
            URL.revokeObjectURL(url);
            
            showAlert('Dosya indirildi', 'success');
        }
        
        // Durum güncelle
        function updateStatus(status, text) {
            const dot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');
            
            dot.className = `status-dot ${status}`;
            statusText.textContent = text;
        }
        
        // Ses göstergesi güncelle
        function updateVoiceIndicator(data) {
            const bars = document.querySelectorAll('.voice-bar');
            
            if (data.status === 'speaking') {
                bars.forEach((bar, i) => {
                    const height = Math.random() * 60 + 10;
                    bar.style.height = `${height}px`;
                    bar.style.background = 'var(--success)';
                });
            } else if (data.status === 'processing') {
                bars.forEach(bar => {
                    bar.style.height = '30px';
                    bar.style.background = 'var(--warning)';
                });
            } else {
                bars.forEach(bar => {
                    bar.style.height = '5px';
                    bar.style.background = 'var(--primary)';
                });
            }
        }
        
        // Ses çubukları oluştur
        function createVoiceBars() {
            const container = document.getElementById('voiceBars');
            for (let i = 0; i < 25; i++) {
                const bar = document.createElement('div');
                bar.className = 'voice-bar';
                bar.style.height = '5px';
                container.appendChild(bar);
            }
        }
        
        // Zamanlayıcı
        function startTimer() {
            sessionStartTime = Date.now();
            timerInterval = setInterval(updateTimer, 1000);
        }
        
        function stopTimer() {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
        }
        
        function updateTimer() {
            if (!sessionStartTime) return;
            
            const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            
            document.getElementById('sessionTime').textContent = 
                `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }
        
        // İstatistikleri güncelle
        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                document.getElementById('totalCount').textContent = stats.total_transcriptions;
            } catch (error) {
                console.error('İstatistikler güncellenemedi:', error);
            }
        }
        
        // Uyarı göster
        function showAlert(message, type) {
            const alertDiv = document.createElement('div');
            alertDiv.className = `alert alert-${type}`;
            
            const icon = {
                'success': '✅',
                'error': '❌',
                'warning': '⚠️',
                'info': 'ℹ️'
            }[type] || 'ℹ️';
            
            alertDiv.innerHTML = `<span>${icon}</span><span>${message}</span>`;
            
            const container = document.getElementById('alerts');
            container.innerHTML = '';
            container.appendChild(alertDiv);
            
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    </script>
</body>
</html>'''

# DeepL Translator Class
class DeepLTranslator:
    def __init__(self):
        self.api_key = None
        self.api_url = "https://api-free.deepl.com/v2/translate"
        self.enabled = False
        self.source_lang = "TR"
        self.target_lang = "EN"
        
    def set_api_key(self, api_key):
        """API anahtarını ayarla"""
        self.api_key = api_key
        return self.test_api()
    
    def test_api(self):
        """API anahtarını test et"""
        if not self.api_key:
            return False
            
        try:
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"DeepL-Auth-Key {self.api_key}"},
                data={
                    "text": "Test",
                    "target_lang": "EN"
                },
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def translate(self, text, source_lang=None, target_lang=None):
        """Metni çevir"""
        if not self.api_key or not self.enabled:
            return None
            
        if not text or len(text.strip()) == 0:
            return None
            
        source = source_lang or self.source_lang
        target = target_lang or self.target_lang
        
        # Aynı dilde çeviri yapma
        if source == target:
            return None
            
        try:
            headers = {
                "Authorization": f"DeepL-Auth-Key {self.api_key}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {
                "text": text,
                "target_lang": target
            }
            
            if source and source != "AUTO":
                data["source_lang"] = source
            
            response = requests.post(
                self.api_url,
                headers=headers,
                data=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("translations"):
                    return result["translations"][0]["text"]
            
            return None
            
        except Exception as e:
            print(f"Çeviri hatası: {str(e)}")
            return None

# WhisperWebTranscriber Sınıfı
class WhisperWebTranscriber:
    def __init__(self):
        self.models_dir = "./whisper_models"
        self.current_model = None
        self.current_model_name = None
        self.is_running = False
        self.audio_queue = queue.Queue()
        self.capture_thread = None
        self.transcribe_thread = None
        self.transcriptions = []
        self.stats = {
            'total_transcriptions': 0,
            'session_start': None,
            'last_transcription': None
        }
        
        # DeepL Translator
        self.translator = DeepLTranslator()
        
        # Ses parametreleri
        self.RATE = 16000
        self.CHUNK_DURATION_MS = 30
        self.CHUNK_SIZE = int(self.RATE * self.CHUNK_DURATION_MS / 1000)
        
        # Ayarlar
        self.silence_duration = 0.8
        self.vad_threshold = 0.4
        self.min_speech_duration = 0.3
        self.vad_level = 2
        self.vad = webrtcvad.Vad(self.vad_level)
        self.whisper_language = "tr"
        
        # Ses işleme ayarları
        self.noise_level = 0.5
        self.compression_enabled = True
        self.speech_enhancement = True
        self.preemphasis = 0.97
        
        # Model bilgileri
        self.model_info = {
            'tiny': {'size': '39 MB', 'speed': 10},
            'base': {'size': '74 MB', 'speed': 7},
            'small': {'size': '244 MB', 'speed': 5},
            'medium': {'size': '769 MB', 'speed': 3},
            'large-v3': {'size': '1.5 GB', 'speed': 1},
            'turbo': {'size': '809 MB', 'speed': 4}
        }
        
        # Model klasörünü oluştur
        os.makedirs(self.models_dir, exist_ok=True)
    
    def apply_noise_filter(self, audio_array, noise_level=0.5):
        """Basit spektral gürültü azaltma"""
        if noise_level <= 0:
            return audio_array
            
        try:
            # Yüksek geçiren filtre (100Hz altını kes - müzik bass'ları)
            if noise_level > 0:
                b, a = signal.butter(2, 100, 'hp', fs=self.RATE)
                audio_array = signal.filtfilt(b, a, audio_array)
            
            # Düşük geçiren filtre (7900Hz üstünü kes - tiz gürültüler)  
            if noise_level > 0.3:
                b, a = signal.butter(2, 7900, 'lp', fs=self.RATE)
                audio_array = signal.filtfilt(b, a, audio_array)
                
            return audio_array.astype(np.int16)
        except Exception as e:
            print(f"Noise filter hatası: {str(e)}")
            return audio_array
    
    def compress_audio(self, audio_array, threshold=0.7, ratio=4):
        """Yüksek ve alçak sesleri dengele"""
        try:
            # Normalize
            max_val = np.max(np.abs(audio_array))
            if max_val > 0:
                audio_norm = audio_array.astype(np.float32) / max_val
                
                # Compression
                mask = np.abs(audio_norm) > threshold
                audio_norm[mask] = threshold + (audio_norm[mask] - threshold) / ratio
                
                return (audio_norm * 32767).astype(np.int16)
            return audio_array
        except Exception as e:
            print(f"Compression hatası: {str(e)}")
            return audio_array
    
    def enhance_speech_frequencies(self, audio_array):
        """İnsan sesi frekanslarını güçlendir (300-3400 Hz)"""
        try:
            # Bandpass filter for speech
            sos = signal.butter(4, [300, 3400], 'bandpass', fs=self.RATE, output='sos')
            enhanced = signal.sosfilt(sos, audio_array.astype(np.float32))
            
            # Mix: %70 enhanced + %30 original
            mixed = (0.7 * enhanced + 0.3 * audio_array)
            return mixed.astype(np.int16)
        except Exception as e:
            print(f"Speech enhancement hatası: {str(e)}")
            return audio_array
    
    def check_installed_models(self):
        """Yüklü modelleri kontrol et"""
        installed = []
        for model_name in self.model_info.keys():
            model_path = os.path.join(self.models_dir, model_name)
            if os.path.exists(model_path):
                installed.append(model_name)
        
        return {
            'installed': installed,
            'current_model': self.current_model_name
        }
    
    def load_model(self, model_name):
        """Model yükle veya indir"""
        try:
            socketio.emit('model_download_progress', {
                'model': model_name,
                'progress': 0
            })
            
            # GPU/CUDA dene
            try:
                print(f"{model_name} modeli GPU ile yükleniyor...")
                self.current_model = WhisperModel(
                    model_name,
                    device="cuda",
                    compute_type="float16",
                    cpu_threads=4,
                    download_root=self.models_dir
                )
                device = "GPU/CUDA"
            except:
                # CPU kullan
                print(f"{model_name} modeli CPU ile yükleniyor...")
                self.current_model = WhisperModel(
                    model_name,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=4,
                    download_root=self.models_dir
                )
                device = "CPU"
            
            self.current_model_name = model_name
            
            socketio.emit('model_download_progress', {
                'model': model_name,
                'progress': 100
            })
            
            return {'success': True, 'device': device}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def update_settings(self, settings):
        """Ayarları güncelle"""
        self.silence_duration = float(settings.get('silence_duration', 0.8))
        self.vad_threshold = float(settings.get('vad_threshold', 0.4))
        self.min_speech_duration = float(settings.get('min_speech_duration', 0.3))
        
        # Ses işleme ayarları
        self.noise_level = float(settings.get('noise_level', 0.5))
        self.compression_enabled = settings.get('compression', True)
        self.speech_enhancement = settings.get('enhance_speech', True)
        self.preemphasis = float(settings.get('preemphasis', 0.97))
        
        # VAD threshold'u webrtcvad level'a çevir (0-3 arası)
        if self.vad_threshold <= 0.3:
            self.vad_level = 3
        elif self.vad_threshold <= 0.5:
            self.vad_level = 2
        elif self.vad_threshold <= 0.7:
            self.vad_level = 1
        else:
            self.vad_level = 0
            
        self.vad = webrtcvad.Vad(self.vad_level)
        
        print(f"📊 Ayarlar güncellendi:")
        print(f"   VAD Threshold: {self.vad_threshold} (Level: {self.vad_level})")
        print(f"   Sessizlik Süresi: {self.silence_duration}s")
        print(f"   Min Konuşma Süresi: {self.min_speech_duration}s")
        print(f"   Gürültü Azaltma: {self.noise_level}")
        print(f"   Ses Dengeleme: {self.compression_enabled}")
        print(f"   Diyalog Netleştirme: {self.speech_enhancement}")
    
    def get_audio_devices(self):
        """Mevcut ses cihazlarını listele"""
        p = pyaudio.PyAudio()
        devices = []
        
        # Normal cihazlar
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    devices.append({
                        'id': i,
                        'name': info['name'],
                        'channels': info['maxInputChannels'],
                        'type': 'microphone'
                    })
            except:
                continue
        
        # WASAPI Loopback
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            if not default_speakers["isLoopbackDevice"]:
                for loopback in p.get_loopback_device_info_generator():
                    if default_speakers["name"] in loopback["name"]:
                        devices.append({
                            'id': loopback["index"],
                            'name': f"🔊 {loopback['name']} (Sistem Sesi)",
                            'channels': loopback["maxInputChannels"],
                            'type': 'system'
                        })
                        break
        except:
            pass
        
        p.terminate()
        return devices
    
    def start_capture(self, device_id=None, settings=None, whisper_language="tr"):
        """Ses yakalamayı başlat"""
        if self.is_running:
            return False
        
        if not self.current_model:
            return False
        
        if settings:
            self.update_settings(settings)
        
        self.whisper_language = whisper_language
        self.is_running = True
        self.stats['session_start'] = datetime.now().isoformat()
        
        # Thread'leri başlat
        self.capture_thread = threading.Thread(target=self._capture_audio, args=(device_id,))
        self.transcribe_thread = threading.Thread(target=self._transcribe_audio)
        
        self.capture_thread.daemon = True
        self.transcribe_thread.daemon = True
        
        self.capture_thread.start()
        self.transcribe_thread.start()
        
        return True
    
    def stop_capture(self):
        """Ses yakalamayı durdur"""
        self.is_running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2)
        if self.transcribe_thread:
            self.transcribe_thread.join(timeout=2)
        return True
    
    def _capture_audio(self, device_id):
        """Ses yakalama thread'i - Gelişmiş ses işleme ile"""
        p = pyaudio.PyAudio()
        
        try:
            if device_id is None:
                # Sistem sesi bul
                try:
                    wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
                    default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                    
                    if not default_speakers["isLoopbackDevice"]:
                        for loopback in p.get_loopback_device_info_generator():
                            if default_speakers["name"] in loopback["name"]:
                                device_id = loopback["index"]
                                break
                except:
                    pass
            
            # Cihaz bilgisi
            device_info = p.get_device_info_by_index(device_id) if device_id else None
            
            if device_info:
                channels = device_info["maxInputChannels"]
                rate = int(device_info["defaultSampleRate"])
            else:
                channels = 1
                rate = self.RATE
            
            # Stream aç
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=device_id,
                frames_per_buffer=self.CHUNK_SIZE
            )
            
            socketio.emit('capture_started', {
                'device': device_info['name'] if device_info else 'Varsayılan',
                'status': 'active'
            })
            
            audio_buffer = []
            silence_counter = 0
            
            # Ondalık silence duration'ı frame sayısına çevir
            max_silence = int(self.silence_duration * (1000 / self.CHUNK_DURATION_MS))
            
            # Minimum konuşma süresi için frame sayısı
            min_speech_frames = int(self.min_speech_duration * (1000 / self.CHUNK_DURATION_MS))
            
            while self.is_running:
                try:
                    data = stream.read(self.CHUNK_SIZE, exception_on_overflow=False)
                    
                    # Çok kanallı sesi mono'ya çevir
                    audio_array = np.frombuffer(data, dtype=np.int16)
                    if channels > 1:
                        audio_array = audio_array.reshape(-1, channels)
                        audio_array = np.mean(audio_array, axis=1).astype(np.int16)
                    
                    # Resampling
                    if rate != self.RATE:
                        factor = self.RATE / rate
                        new_length = int(len(audio_array) * factor)
                        x_old = np.linspace(0, len(audio_array), len(audio_array))
                        x_new = np.linspace(0, len(audio_array), new_length)
                        audio_array = np.interp(x_new, x_old, audio_array).astype(np.int16)
                    
                    # === SES İŞLEME ===
                    # Gürültü azaltma
                    if self.noise_level > 0:
                        audio_array = self.apply_noise_filter(audio_array, self.noise_level)
                    
                    # Ses dengeleme (compression)
                    if self.compression_enabled:
                        audio_array = self.compress_audio(audio_array)
                    
                    # Konuşma güçlendirme
                    if self.speech_enhancement:
                        audio_array = self.enhance_speech_frequencies(audio_array)
                    
                    # Pre-emphasis
                    if self.preemphasis > 0:
                        audio_array = np.append(audio_array[0], 
                                               audio_array[1:] - self.preemphasis * audio_array[:-1])
                        audio_array = audio_array.astype(np.int16)
                    
                    # Gelişmiş VAD kontrolü
                    volume = np.abs(audio_array).mean()
                    
                    # Hem webrtcvad hem de threshold kontrolü
                    try:
                        is_speech_vad = self.vad.is_speech(audio_array.tobytes(), self.RATE)
                    except:
                        is_speech_vad = False
                    
                    # Volume threshold'u VAD threshold'a göre ayarla
                    volume_threshold = 500 * (1.0 - self.vad_threshold + 0.1)
                    is_speech_volume = volume > volume_threshold
                    
                    # Her ikisini de değerlendir
                    is_speech = is_speech_vad or is_speech_volume
                    
                    if is_speech:
                        audio_buffer.append(audio_array)
                        silence_counter = 0
                        socketio.emit('voice_activity', {'status': 'speaking', 'volume': int(volume)})
                    else:
                        if audio_buffer:
                            silence_counter += 1
                            audio_buffer.append(audio_array)
                            
                            if silence_counter >= max_silence:
                                # Minimum konuşma süresi kontrolü
                                if len(audio_buffer) >= min_speech_frames:
                                    full_audio = np.concatenate(audio_buffer)
                                    self.audio_queue.put(full_audio)
                                    socketio.emit('voice_activity', {'status': 'processing'})
                                    print(f"🎤 Ses yakalandı: {len(audio_buffer)} frame")
                                else:
                                    print(f"⭕ Çok kısa ses atlandı: {len(audio_buffer)} frame")
                                
                                audio_buffer = []
                                silence_counter = 0
                        else:
                            socketio.emit('voice_activity', {'status': 'silent', 'volume': int(volume)})
                
                except Exception as e:
                    if "Input overflowed" not in str(e):
                        socketio.emit('error', {'message': str(e)})
                    continue
            
        except Exception as e:
            socketio.emit('error', {'message': f'Ses yakalama hatası: {str(e)}'})
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except:
                pass
            p.terminate()
            socketio.emit('capture_stopped', {'status': 'stopped'})
    
    def _transcribe_audio(self):
        """Transcription ve çeviri thread'i"""
        while self.is_running or not self.audio_queue.empty():
            try:
                audio_data = self.audio_queue.get(timeout=1)
                
                # Float32'ye çevir
                audio_float = audio_data.astype(np.float32) / 32768.0
                
                # Basit prompt
                language_map = {'tr': 'Türkçe', 'en': 'English', 'de': 'Deutsch'}
                language = language_map.get(self.whisper_language, 'Türkçe')
                prompt = f"{language} konuşma."
                
                # Transcribe
                segments, info = self.current_model.transcribe(
                    audio_float,
                    beam_size=5,
                    best_of=5,
                    patience=1.0,
                    length_penalty=1.0,
                    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                    compression_ratio_threshold=2.4,
                    log_prob_threshold=-1.0,
                    no_speech_threshold=0.6,
                    condition_on_previous_text=False,
                    initial_prompt=prompt,
                    language=self.whisper_language,
                    vad_filter=True,
                    vad_parameters=dict(
                        threshold=self.vad_threshold,
                        min_speech_duration_ms=int(self.min_speech_duration * 1000),
                        max_speech_duration_s=10.0,
                        min_silence_duration_ms=int(self.silence_duration * 1000),
                        speech_pad_ms=200
                    )
                )
                
                # Metni birleştir ve temizle
                full_text = ""
                for segment in segments:
                    text = segment.text.strip()
                    if text:
                        if full_text and not full_text[-1] in '.!?':
                            full_text += ". "
                        full_text += text + " "
                
                full_text = full_text.strip()
                
                # Basit düzeltmeler
                full_text = full_text.replace("  ", " ")
                full_text = full_text.replace(" .", ".")
                full_text = full_text.replace(" ,", ",")
                
                if full_text:
                    # İstatistikleri güncelle
                    self.stats['total_transcriptions'] += 1
                    self.stats['last_transcription'] = datetime.now().isoformat()
                    
                    # Model dilini göster için dil kodu map
                    language_display_map = {
                        'tr': 'TR',
                        'en': 'EN',
                        'de': 'DE'
                    }
                    
                    # Transcription kaydet
                    transcription = {
                        'id': self.stats['total_transcriptions'],
                        'text': full_text,
                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'confidence': info.language_probability if hasattr(info, 'language_probability') else None,
                        'model_language': language_display_map.get(self.whisper_language, 'TR'),
                        'source_lang': self.translator.source_lang,
                        'target_lang': self.translator.target_lang
                    }
                    
                    # Çeviri yap (eğer aktifse)
                    if self.translator.enabled and self.translator.api_key:
                        translation = self.translator.translate(full_text)
                        if translation:
                            transcription['translation'] = translation
                    
                    self.transcriptions.append(transcription)
                    
                    # WebSocket ile gönder
                    socketio.emit('new_transcription', transcription)
                    
                    # Dosyaya kaydet
                    with open("transcriptions.txt", "a", encoding="utf-8") as f:
                        lang_info = f"[{language_display_map.get(self.whisper_language, 'TR')}]"
                        f.write(f"[{transcription['timestamp']}] {lang_info} {full_text}\n")
                        if transcription.get('translation'):
                            f.write(f"    Çeviri: {transcription['translation']}\n")
                
            except queue.Empty:
                continue
            except Exception as e:
                socketio.emit('error', {'message': f'Transcription hatası: {str(e)}'})

# YouTube İşleme Sınıfı
class YouTubeProcessor:
    def __init__(self, transcriber):
        self.transcriber = transcriber
        self.temp_dir = tempfile.gettempdir()
        self.cookies_path = None  # Cookie dosya yolu
        
    def set_cookies_path(self, path):
        """Cookie dosya yolunu ayarla"""
        self.cookies_path = path
        print(f"✅ Cookie dosyası ayarlandı: {path}")
        
    def process_youtube_url(self, url, whisper_language='tr', model_name='medium', export_srt=False):
        """YouTube videosunu indir ve işle"""
        try:
            # Model yükle veya değiştir
            if not self.transcriber.current_model or self.transcriber.current_model_name != model_name:
                print(f"🤖 YouTube için {model_name} modeli yükleniyor...")
                socketio.emit('youtube_progress', {
                    'status': f'{model_name} modeli yükleniyor...',
                    'progress': 10
                })
                model_result = self.transcriber.load_model(model_name)
                if not model_result['success']:
                    return {'success': False, 'error': f'Model yüklenemedi: {model_result.get("error", "Bilinmeyen hata")}'}
                print(f"✅ {model_name} modeli yüklendi ({model_result['device']})")
            
            # yt-dlp ayarları - Bot korumasını aşmak için güncellenmiş
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                    'preferredquality': '192',
                }],
                'quiet': False,  # Hata mesajlarını görmek için
                'no_warnings': False,
                # YouTube kısıtlamalarını aşmak için ek parametreler
                'age_limit': None,
                'geo_bypass': True,
                'nocheckcertificate': True,
                # User-Agent değiştir
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                # Extractor args
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'skip': ['dash', 'hls']
                    }
                }
            }
            
            # Cookie dosyası varsa kullan
            if self.cookies_path and os.path.exists(self.cookies_path):
                ydl_opts['cookiefile'] = self.cookies_path
                print(f"🍪 Cookie dosyası kullanılıyor: {self.cookies_path}")
            elif os.path.exists('cookies.txt'):
                # Varsayılan cookies.txt varsa kullan
                ydl_opts['cookiefile'] = 'cookies.txt'
                print("🍪 cookies.txt dosyası kullanılıyor...")
            else:
                # Browser'dan otomatik cookie almayı dene
                print("⚠️ Cookie dosyası bulunamadı, tarayıcıdan alınmaya çalışılıyor...")
                for browser in ['chrome', 'firefox', 'edge', 'brave']:
                    try:
                        ydl_opts['cookiesfrombrowser'] = (browser,)
                        print(f"🍪 {browser} tarayıcısından cookies alınıyor...")
                        break
                    except:
                        continue
            
            # Video bilgilerini al
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                socketio.emit('youtube_progress', {
                    'status': 'Video bilgileri alınıyor...',
                    'progress': 20
                })
                
                info = ydl.extract_info(url, download=False)
                video_title = info.get('title', 'Unknown')
                video_duration = self._format_duration(info.get('duration', 0))
                video_uploader = info.get('uploader', 'Unknown')
                
                socketio.emit('youtube_progress', {
                    'status': f'Video indiriliyor: {video_title}',
                    'progress': 40
                })
                
                # Ses dosyasını indir
                ydl.download([url])
                
                # WAV dosyasını bul
                wav_file = os.path.join(self.temp_dir, f"{video_title}.wav")
                
                if not os.path.exists(wav_file):
                    # Dosya adında özel karakterler varsa temizle
                    import re
                    safe_title = re.sub(r'[^\w\s-]', '', video_title)
                    wav_file = os.path.join(self.temp_dir, f"{safe_title}.wav")
                
                if os.path.exists(wav_file):
                    socketio.emit('youtube_progress', {
                        'status': 'Ses dosyası işleniyor...',
                        'progress': 60
                    })
                    
                    # SRT çıktı yolu
                    try:
                        import re
                        safe_title_for_srt = re.sub(r'[^\w\s-]', '', video_title)
                    except Exception:
                        safe_title_for_srt = 'youtube_video'
                    srt_path = os.path.join(self.temp_dir, f"{safe_title_for_srt}.srt") if export_srt else None

                    # Ses dosyasını işle ve transkribe et
                    transcriptions = self._transcribe_audio_file(
                        wav_file,
                        whisper_language,
                        export_srt=export_srt,
                        srt_file_path=srt_path
                    )
                    
                    socketio.emit('youtube_progress', {
                        'status': 'Transkripsiyon tamamlandı',
                        'progress': 100
                    })
                    
                    # Geçici dosyayı sil
                    try:
                        os.remove(wav_file)
                    except:
                        pass
                    
                    return {
                        'success': True,
                        'video_info': {
                            'title': video_title,
                            'duration': video_duration,
                            'uploader': video_uploader
                        },
                        'transcriptions': transcriptions,
                        'srt_path': srt_path if export_srt else None
                    }
                else:
                    # WAV oluşmadıysa indirilen dosyayı bul ve dönüştürmeyi dene
                    try:
                        import glob, subprocess
                        # Muhtemel giriş dosyalarını tara
                        candidates = []
                        raw_patterns = [
                            os.path.join(self.temp_dir, f"{video_title}.*"),
                            os.path.join(self.temp_dir, f"{safe_title}.*")
                        ]
                        for pattern in raw_patterns:
                            candidates.extend(glob.glob(pattern))
                        # WAV hariç, en uygun dosyayı seç
                        candidates = [c for c in candidates if os.path.isfile(c) and not c.lower().endswith('.wav')]
                        if candidates:
                            input_audio = max(candidates, key=lambda p: os.path.getsize(p))
                            socketio.emit('youtube_progress', {
                                'status': 'Ses WAV formatına dönüştürülüyor...',
                                'progress': 55
                            })
                            # Hedef WAV yolu
                            target_wav = os.path.join(self.temp_dir, f"{safe_title}.wav")
                            # ffmpeg ile dönüştür
                            try:
                                subprocess.run([
                                    'ffmpeg', '-y', '-i', input_audio,
                                    '-ac', '1', '-ar', '16000',
                                    target_wav
                                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                            except Exception:
                                return {'success': False, 'error': 'Ses dosyası oluşturulamadı (ffmpeg bulunamadı veya dönüşüm hatası)'}
                            if not os.path.exists(target_wav):
                                return {'success': False, 'error': 'Ses dosyası oluşturulamadı'}
                            # Dönüşüm başarılı; transkribe et
                            socketio.emit('youtube_progress', {
                                'status': 'Ses dosyası işleniyor...',
                                'progress': 60
                            })
                            try:
                                import re
                                safe_title_for_srt = re.sub(r'[^\w\s-]', '', video_title)
                            except Exception:
                                safe_title_for_srt = 'youtube_video'
                            srt_path = os.path.join(self.temp_dir, f"{safe_title_for_srt}.srt") if export_srt else None
                            transcriptions = self._transcribe_audio_file(
                                target_wav,
                                whisper_language,
                                export_srt=export_srt,
                                srt_file_path=srt_path
                            )
                            socketio.emit('youtube_progress', {
                                'status': 'Transkripsiyon tamamlandı',
                                'progress': 100
                            })
                            # Geçici dosyaları temizle (girdi ve wav)
                            for pth in [input_audio, target_wav]:
                                try:
                                    os.remove(pth)
                                except Exception:
                                    pass
                            return {
                                'success': True,
                                'video_info': {
                                    'title': video_title,
                                    'duration': video_duration,
                                    'uploader': video_uploader
                                },
                                'transcriptions': transcriptions,
                                'srt_path': srt_path if export_srt else None
                            }
                        else:
                            return {'success': False, 'error': 'Ses dosyası oluşturulamadı (indirilen dosya bulunamadı)'}
                    except Exception as e:
                        return {'success': False, 'error': f'Ses dosyası oluşturulamadı: {str(e)}'}
                    
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _format_duration(self, seconds):
        """Saniyeyi dakika:saniye formatına çevir"""
        if not seconds:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    def _transcribe_audio_file(self, audio_file, whisper_language='tr', export_srt=False, srt_file_path=None):
        """Ses dosyasını transkribe et ve istenirse SRT olarak dışa aktar"""
        try:
            # Model yüklü mü kontrol et
            if not self.transcriber.current_model:
                socketio.emit('youtube_progress', {
                    'status': 'Model yüklenemedi!',
                    'progress': 0
                })
                return False
            
            socketio.emit('youtube_progress', {
                'status': f'Transkripsiyon başlıyor ({self.transcriber.current_model_name} modeli)...',
                'progress': 70
            })
            
            # Ses dosyasını yükle
            import wave
            with wave.open(audio_file, 'rb') as wav:
                frames = wav.readframes(-1)
                audio_array = np.frombuffer(frames, dtype=np.int16)
                sample_rate = wav.getframerate()
            
            # 16kHz'e resample et
            if sample_rate != 16000:
                from scipy import signal
                audio_array = signal.resample(audio_array, int(len(audio_array) * 16000 / sample_rate))
            
            # Float32'ye çevir
            audio_float = audio_array.astype(np.float32) / 32768.0
            
            # Dil haritası
            language_map = {'tr': 'Türkçe', 'en': 'English', 'de': 'Deutsch'}
            language = language_map.get(whisper_language, 'Türkçe')
            prompt = f"{language} konuşma."
            
            socketio.emit('youtube_progress', {
                'status': 'Model çalışıyor...',
                'progress': 80
            })
            
            # Transkribe et
            segments, info = self.transcriber.current_model.transcribe(
                audio_float,
                beam_size=5,
                best_of=5,
                patience=1.0,
                length_penalty=1.0,
                temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                compression_ratio_threshold=2.4,
                log_prob_threshold=-1.0,
                no_speech_threshold=0.6,
                condition_on_previous_text=False,
                initial_prompt=prompt,
                language=whisper_language,
                vad_filter=True,
                vad_parameters=dict(
                    threshold=0.4,
                    min_speech_duration_ms=300,
                    max_speech_duration_s=10.0,
                    min_silence_duration_ms=800,
                    speech_pad_ms=200
                )
            )
            
            socketio.emit('youtube_progress', {
                'status': 'Sonuçlar işleniyor...',
                'progress': 90
            })
            
            # Segmentleri işle
            srt_segments = []
            for segment in segments:
                text = segment.text.strip()
                if text:
                    # Transkripsiyon oluştur
                    self.transcriber.stats['total_transcriptions'] += 1
                    
                    transcription = {
                        'id': self.transcriber.stats['total_transcriptions'],
                        'text': text,
                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'source': 'youtube',
                        'model_language': whisper_language.upper(),
                        'source_lang': self.transcriber.translator.source_lang,
                        'target_lang': self.transcriber.translator.target_lang,
                        'confidence': info.language_probability if hasattr(info, 'language_probability') else None
                    }
                    
                    # SRT için zaman bilgisi ekle
                    try:
                        start_s = float(getattr(segment, 'start', 0.0))
                        end_s = float(getattr(segment, 'end', 0.0))
                    except Exception:
                        start_s, end_s = 0.0, 0.0
                    srt_segments.append({
                        'index': len(srt_segments) + 1,
                        'start': start_s,
                        'end': end_s,
                        'text': text
                    })

                    # Çeviri yap (eğer aktifse)
                    if self.transcriber.translator.enabled and self.transcriber.translator.api_key:
                        translation = self.transcriber.translator.translate(text)
                        if translation:
                            transcription['translation'] = translation
                    
                    self.transcriber.transcriptions.append(transcription)
                    
                    # WebSocket ile gönder
                    socketio.emit('new_transcription', transcription)
                    
                    # Dosyaya kaydet
                    with open("transcriptions.txt", "a", encoding="utf-8") as f:
                        f.write(f"[{transcription['timestamp']}] [YouTube] [{whisper_language.upper()}] {text}\n")
                        if transcription.get('translation'):
                            f.write(f"    Çeviri: {transcription['translation']}\n")
            
            # İstenirse SRT yaz
            if export_srt and srt_file_path:
                try:
                    self._write_srt(srt_segments, srt_file_path)
                except Exception as e:
                    socketio.emit('error', {'message': f'SRT yazma hatası: {str(e)}'})
            
            return srt_segments
            
        except Exception as e:
            socketio.emit('error', {'message': f'Transkripsiyon hatası: {str(e)}'})
            return []

    def _format_srt_time(self, seconds_float):
        """SRT zaman formatına (HH:MM:SS,mmm) çevir"""
        try:
            total_ms = int(round(seconds_float * 1000))
            hours = total_ms // 3600000
            minutes = (total_ms % 3600000) // 60000
            seconds = (total_ms % 60000) // 1000
            millis = total_ms % 1000
            return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"
        except Exception:
            return "00:00:00,000"

    def _write_srt(self, segments, file_path):
        """Segment listesinden SRT dosyası oluştur"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for seg in segments:
                start = self._format_srt_time(seg.get('start', 0.0))
                end = self._format_srt_time(seg.get('end', 0.0))
                text = seg.get('text', '').strip()
                index = seg.get('index', 1)
                f.write(f"{index}\n{start} --> {end}\n{text}\n\n")

# Global instances
transcriber = WhisperWebTranscriber()
youtube_processor = YouTubeProcessor(transcriber)

# Flask route'ları
@app.route('/')
def index():
    """Ana sayfa"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/check_models', methods=['GET'])
def check_models():
    """Yüklü modelleri kontrol et"""
    return jsonify(transcriber.check_installed_models())

@app.route('/api/load_model', methods=['POST'])
def load_model():
    """Model yükle"""
    data = request.json
    model_name = data.get('model', 'medium')
    result = transcriber.load_model(model_name)
    return jsonify(result)

@app.route('/api/devices', methods=['GET'])
def get_devices():
    """Ses cihazlarını getir"""
    devices = transcriber.get_audio_devices()
    return jsonify(devices)

@app.route('/api/update_settings', methods=['POST'])
def update_settings():
    """Ayarları güncelle"""
    settings = request.json
    transcriber.update_settings(settings)
    return jsonify({'success': True})

@app.route('/api/deepl_config', methods=['POST'])
def deepl_config():
    """DeepL API yapılandırması"""
    data = request.json
    api_key = data.get('api_key')
    
    if api_key:
        success = transcriber.translator.set_api_key(api_key)
        return jsonify({'success': success})
    
    return jsonify({'success': False, 'error': 'API key gerekli'})

@app.route('/api/translation_settings', methods=['POST'])
def translation_settings():
    """Çeviri ayarları"""
    data = request.json
    
    transcriber.translator.enabled = data.get('enabled', False)
    transcriber.translator.source_lang = data.get('sourceLang', 'TR')
    transcriber.translator.target_lang = data.get('targetLang', 'EN')
    
    if data.get('apiKey'):
        transcriber.translator.set_api_key(data['apiKey'])
    
    return jsonify({'success': True})

@app.route('/api/start', methods=['POST'])
def start_capture():
    """Yakalamayı başlat"""
    data = request.json
    device_id = data.get('device_id')
    settings = data.get('settings')
    whisper_language = data.get('whisper_language', 'tr')
    
    success = transcriber.start_capture(device_id, settings, whisper_language)
    return jsonify({'success': success})

@app.route('/api/stop', methods=['POST'])
def stop_capture():
    """Yakalamayı durdur"""
    success = transcriber.stop_capture()
    return jsonify({'success': True})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """İstatistikleri getir"""
    return jsonify(transcriber.stats)

@app.route('/api/clear', methods=['POST'])
def clear_transcriptions():
    """Transcription'ları temizle"""
    transcriber.transcriptions = []
    transcriber.stats['total_transcriptions'] = 0
    return jsonify({'success': True})

# Cookie upload endpoint'i
@app.route('/api/upload_cookies', methods=['POST'])
def upload_cookies():
    """Cookie dosyasını yükle"""
    try:
        if 'cookie_file' not in request.files:
            return jsonify({'success': False, 'error': 'Dosya bulunamadı'})
        
        file = request.files['cookie_file']
        
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Dosya seçilmedi'})
        
        if file and file.filename.endswith('.txt'):
            # Cookie dosyasını kaydet
            cookie_path = os.path.join(os.getcwd(), 'youtube_cookies.txt')
            file.save(cookie_path)
            
            # YouTube processor'a cookie yolunu set et
            youtube_processor.set_cookies_path(cookie_path)
            
            return jsonify({'success': True, 'message': 'Cookie dosyası yüklendi'})
        else:
            return jsonify({'success': False, 'error': 'Sadece .txt dosyaları kabul edilir'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# YouTube endpoint'i
@app.route('/api/youtube_transcribe', methods=['POST'])
def youtube_transcribe():
    """YouTube videosunu transkribe et"""
    data = request.json
    url = data.get('url')
    whisper_language = data.get('whisper_language', 'tr')
    model_name = data.get('model', 'medium')  # Model parametresini al
    export_srt = data.get('export_srt', False)
    
    if not url:
        return jsonify({'success': False, 'error': 'URL gerekli'})
    
    result = youtube_processor.process_youtube_url(url, whisper_language, model_name, export_srt=export_srt)
    return jsonify(result)

if __name__ == '__main__':
    print("="*60)
    print("WHISPER + DEEPL + YOUTUBE TRANSKRİPSİYON SİSTEMİ")
    print("="*60)
    print("✅ Özellikler:")
    print("   • YouTube video transkripsiyon")
    print("   • Canlı ses yakalama ve transkripsiyon")
    print("   • DeepL ile otomatik çeviri")
    print("   • Gelişmiş ses işleme")
    print("")
    print("🎬 YouTube kullanımı:")
    print("   1. YouTube URL veya Video ID girin")
    print("   2. 'İşle' butonuna tıklayın")
    print("   3. Video otomatik olarak indirilip transkribe edilecek")
    print("")
    print("📌 Gerekli kütüphaneler:")
    print("   pip install flask flask-socketio faster-whisper pyaudiowpatch numpy webrtcvad requests scipy yt-dlp")
    print("")
    print("Tarayıcınızda açın: http://localhost:5000")
    print("="*60)
    
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)