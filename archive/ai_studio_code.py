#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper Web Arayüzü + DeepL Çeviri + Konuşmacı Tanıma (Pyannote) + Context Carry-over
Gerekli kütüphaneler:
pip install flask flask-socketio faster-whisper pyaudiowpatch numpy webrtcvad requests pyannote.audio torch torchaudio
Not: Hugging Face token gerekli (ücretsiz): https://huggingface.co/settings/tokens
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

# HTML Template (Model dil seçimi ve DeepL toggle güncellemeleri)
HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Whisper + DeepL + Konuşmacı Tanıma Pro</title>
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
            
            /* Konuşmacı renkleri */
            --speaker1: #3b82f6;
            --speaker2: #10b981;
            --speaker3: #f59e0b;
            --speaker4: #ef4444;
            --speaker5: #8b5cf6;
            --speaker6: #ec4899;
            --speaker7: #14b8a6;
            --speaker8: #f97316;
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
        
        /* Context Carry-over Göstergesi */
        .context-indicator {
            margin-bottom: 20px;
            padding: 12px;
            background: linear-gradient(135deg, #e0f2fe 0%, #bae6fd 100%);
            border-radius: 10px;
            border: 2px solid #0284c7;
            font-size: 12px;
        }
        
        .context-indicator h4 {
            color: #0c4a6e;
            font-size: 14px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .context-status {
            color: #075985;
            font-size: 11px;
            margin-top: 5px;
        }
        
        .context-count {
            font-weight: bold;
            color: #0284c7;
        }
        

        /* Whisper Prompt Ayarları */
        .whisper-prompt-settings {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #ddd6fe 0%, #c4b5fd 100%);
            border-radius: 10px;
            border: 2px solid #8b5cf6;
        }
        
        .whisper-prompt-settings h3 {
            margin-bottom: 12px;
            color: #5b21b6;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .prompt-textarea {
            width: 100%;
            min-height: 80px;
            padding: 10px;
            border: 2px solid #c4b5fd;
            border-radius: 8px;
            font-family: monospace;
            font-size: 13px;
            resize: vertical;
            background: white;
        }
        
        .prompt-textarea:focus {
            outline: none;
            border-color: #8b5cf6;
        }
        
        .prompt-info {
            margin-top: 8px;
            font-size: 11px;
            color: #6b21a8;
        }
        
        .prompt-examples {
            margin-top: 10px;
            padding: 8px;
            background: white;
            border-radius: 6px;
            font-size: 11px;
            color: #6b21a8;
        }
        
        .prompt-examples strong {
            display: block;
            margin-bottom: 4px;
        }
        
        /* Arama Kutusu */
        .search-box {
            margin-bottom: 20px;
            position: relative;
        }
        
        .search-input {
            width: 100%;
            padding: 12px 40px 12px 15px;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .search-icon {
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: #9ca3af;
            font-size: 18px;
        }
        
        .search-results-info {
            margin-top: 8px;
            font-size: 12px;
            color: #6b7280;
            font-style: italic;
        }
        
        .highlight {
            background-color: #fef08a;
            padding: 2px 4px;
            border-radius: 3px;
            font-weight: 600;
        }


        /* Transkript Düzenleme */
        .transcription-item.editable {
            cursor: text;
        }
        
        .transcription-text.editing {
            background: #fff9e6;
            border: 2px dashed var(--primary);
            padding: 8px;
            border-radius: 6px;
            outline: none;
        }
        
        .edit-controls {
            display: none;
            margin-top: 8px;
            gap: 8px;
        }
        
        .transcription-item.editing .edit-controls {
            display: flex;
        }
        
        .btn-save-edit {
            background: var(--success);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .btn-cancel-edit {
            background: var(--danger);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        
        /* Favori İşaretleme */
        .favorite-btn {
            position: absolute;
            top: 15px;
            right: 45px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 20px;
            transition: all 0.3s;
        }
        
        .favorite-btn:not(.favorited) {
            opacity: 0.3;
        }
        
        .favorite-btn:hover {
            opacity: 1;
            transform: scale(1.2);
        }
        
        .favorite-btn.favorited {
            opacity: 1;
            filter: drop-shadow(0 0 3px #fbbf24);
        }
        
        /* Kopyalama Butonu */
        .copy-btn {
            position: absolute;
            top: 15px;
            right: 15px;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 18px;
            opacity: 0.3;
            transition: all 0.3s;
        }
        
        .copy-btn:hover {
            opacity: 1;
            transform: scale(1.1);
        }
        
        .copy-btn.copied {
            opacity: 1;
            color: var(--success);
        }
        
        /* Sentiment Badge */
        .sentiment-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            margin-left: 8px;
        }
        
        .sentiment-positive {
            background: #d1fae5;
            color: #065f46;
        }
        
        .sentiment-negative {
            background: #fee2e2;
            color: #991b1b;
        }
        
        .sentiment-neutral {
            background: #e5e7eb;
            color: #4b5563;
        }
        
        /* Oturum Geçmişi Panel */
        .session-history-panel {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
            border-radius: 10px;
            border: 2px solid #818cf8;
        }
        
        .session-history-panel h3 {
            margin-bottom: 12px;
            color: #3730a3;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .sessions-list {
            max-height: 150px;
            overflow-y: auto;
            background: white;
            border-radius: 8px;
            padding: 8px;
        }
        
        .session-item {
            padding: 8px 12px;
            margin-bottom: 6px;
            background: #f9fafb;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .session-item:hover {
            background: #e0e7ff;
            transform: translateX(3px);
        }
        
        .session-item.active {
            background: #818cf8;
            color: white;
        }
        
        .session-date {
            font-size: 11px;
            color: #6b7280;
        }
        
        .session-item.active .session-date {
            color: white;
        }
        
        /* Prompt Templates */
        .prompt-templates {
            margin-top: 12px;
            padding: 10px;
            background: white;
            border-radius: 8px;
        }
        
        .template-btn {
            display: block;
            width: 100%;
            padding: 8px;
            margin-bottom: 6px;
            background: #f3f4f6;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            cursor: pointer;
            text-align: left;
            font-size: 12px;
            transition: all 0.3s;
        }
        
        .template-btn:hover {
            background: #e5e7eb;
            border-color: var(--primary);
        }
        
        .template-btn strong {
            display: block;
            color: #374151;
            margin-bottom: 2px;
        }
        
        .template-btn span {
            color: #6b7280;
            font-size: 11px;
        }
        
        /* VAD Tuning */
        .vad-tuning {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-radius: 10px;
            border: 2px solid #fbbf24;
        }
        
        .vad-tuning h3 {
            margin-bottom: 12px;
            color: #92400e;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .vad-slider {
            margin-bottom: 12px;
        }
        
        .vad-slider label {
            display: block;
            font-size: 13px;
            color: #78350f;
            margin-bottom: 6px;
        }
        
        .vad-slider input[type="range"] {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: #fde68a;
            outline: none;
        }
        
        .vad-slider input[type="range"]::-webkit-slider-thumb {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #f59e0b;
            cursor: pointer;
        }
        
        .vad-value {
            display: inline-block;
            background: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            color: #92400e;
            margin-left: 8px;
        }
        
        /* Audio Visualization Canvas */
        .audio-visualization {
            margin-top: 15px;
            background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
            border-radius: 10px;
            padding: 15px;
            height: 120px;
            position: relative;
        }
        
        .audio-canvas {
            width: 100%;
            height: 90px;
            border-radius: 6px;
        }
        
        .visualization-label {
            color: #9ca3af;
            font-size: 11px;
            text-align: center;
            margin-top: 5px;
        }
        
        /* Custom Model Panel */
        .custom-model-panel {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #fce7f3 0%, #fbcfe8 100%);
            border-radius: 10px;
            border: 2px solid #ec4899;
        }
        
        .custom-model-panel h3 {
            margin-bottom: 12px;
            color: #9f1239;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .model-path-input {
            width: 100%;
            padding: 10px;
            border: 2px solid #f9a8d4;
            border-radius: 8px;
            font-size: 13px;
            font-family: monospace;
            margin-bottom: 10px;
        }
        
        .model-path-input:focus {
            outline: none;
            border-color: #ec4899;
        }
        
        .btn-load-custom {
            width: 100%;
            padding: 10px;
            background: #ec4899;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .btn-load-custom:hover {
            background: #db2777;
        }
        
        /* Copy All Button */
        .copy-all-btn {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s;
        }
        
        .copy-all-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .copy-all-btn.copied {
            background: var(--success);
        }

                /* Model Dil Seçimi */
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
        
        /* Konuşmacı Tanıma Ayarları */
        .speaker-settings {
            margin-bottom: 20px;
            padding: 15px;
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-radius: 10px;
            border: 2px solid #fbbf24;
        }
        
        .speaker-settings h3 {
            margin-bottom: 12px;
            color: #92400e;
            font-size: 16px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .speaker-toggle {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .speakers-list {
            max-height: 200px;
            overflow-y: auto;
            background: white;
            border-radius: 8px;
            padding: 10px;
        }
        
        .speaker-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 8px;
            margin-bottom: 5px;
            border-radius: 6px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
        }
        
        .speaker-avatar {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
        }
        
        .speaker-info {
            flex: 1;
            margin-left: 10px;
        }
        
        .speaker-name {
            font-weight: 600;
            font-size: 14px;
        }
        
        .speaker-count {
            font-size: 12px;
            color: #6b7280;
        }
        
        .speaker-name-input {
            padding: 4px 8px;
            border: 1px solid #d1d5db;
            border-radius: 4px;
            font-size: 13px;
            width: 120px;
        }
        
        /* Transcription item with speaker */
        .transcription-item.with-speaker {
            border-left-width: 5px;
        }
        
        .speaker-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            color: white;
            margin-right: 10px;
        }
        
        /* Speaker renkleri için dinamik stiller */
        .speaker-1 { background-color: var(--speaker1); border-left-color: var(--speaker1); }
        .speaker-2 { background-color: var(--speaker2); border-left-color: var(--speaker2); }
        .speaker-3 { background-color: var(--speaker3); border-left-color: var(--speaker3); }
        .speaker-4 { background-color: var(--speaker4); border-left-color: var(--speaker4); }
        .speaker-5 { background-color: var(--speaker5); border-left-color: var(--speaker5); }
        .speaker-6 { background-color: var(--speaker6); border-left-color: var(--speaker6); }
        .speaker-7 { background-color: var(--speaker7); border-left-color: var(--speaker7); }
        .speaker-8 { background-color: var(--speaker8); border-left-color: var(--speaker8); }
        
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
            content: '✓';
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
            margin-bottom: 10px;
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
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideUp {
            from { 
                opacity: 0;
               