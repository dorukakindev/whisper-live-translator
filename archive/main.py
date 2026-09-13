#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper Ultimate Studio: Custom Control Edition
Özellikler:
- Kullanıcı tarafından değiştirilebilir Whisper Parametreleri (Beam, Temp, Prompt vb.)
- Akıllı Bekleme ve Sessizlik Yönetimi
- Gelişmiş Prompt Yönetimi (Kullanıcı Prompt + Bağlam Hafızası)
- Resampling ve Donanım Uyumluluğu

Gerekli Kütüphaneler:
pip install flask flask-socketio faster-whisper pyaudiowpatch numpy requests pyannote.audio torch torchaudio psutil scipy noisereduce
"""

from flask import Flask, render_template_string, jsonify, request
from flask_socketio import SocketIO
import time
import queue
import threading
import numpy as np
import pyaudiowpatch as pyaudio
from faster_whisper import WhisperModel
import requests
from datetime import datetime
from collections import deque
import psutil
import torch
from scipy.signal import butter, lfilter
import noisereduce as nr

# --- AYARLAR (Varsayılan) ---
SILENCE_TIMEOUT_MS = 1000   # Sessizlik toleransı
MIN_AUDIO_MS = 800          # Min ses uzunluğu
MAX_AUDIO_MS = 20000        # Max buffer süresi

app = Flask(__name__)
app.config['SECRET_KEY'] = 'whisper-control-v1'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# --- SİNYAL İŞLEME ---
class AudioDSP:
    @staticmethod
    def process(data, fs=16000, enable_nr=False):
        # 1. Float çevir
        audio = data.astype(np.float32) / 32768.0
        
        # 2. Bandpass (İnsan Sesi Aralığı)
        nyq = 0.5 * fs
        b, a = butter(5, [85.0/nyq, 3400.0/nyq], btype='band')
        audio = lfilter(b, a, audio)
        
        # 3. Normalize
        m = np.max(np.abs(audio))
        if m > 0: audio = audio / m * 0.90
        
        # 4. Noise Reduction (Opsiyonel)
        if enable_nr:
            try: audio = nr.reduce_noise(y=audio, sr=fs, stationary=True, prop_decrease=0.7)
            except: pass
            
        return audio.astype(np.float32)

# --- ARAYÜZ ---
HTML = '''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Whisper Custom Control</title>
    <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
    <style>
        :root { --p: #3b82f6; --bg: #0f172a; --panel: #1e293b; --txt: #f8fafc; --acc: #60a5fa; }
        * { box-sizing: border-box; outline:none; }
        body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--txt); margin:0; padding:15px; height:100vh; overflow:hidden; }
        
        .layout { display: grid; grid-template-columns: 340px 1fr; gap: 15px; height: 100%; }
        .sidebar { overflow-y:auto; display:flex; flex-direction:column; gap:12px; padding-right:5px; }
        .main { background: var(--panel); border-radius: 12px; border:1px solid #334155; display: flex; flex-direction: column; height:100%; overflow:hidden; }
        .panel { background: var(--panel); border: 1px solid #334155; border-radius: 10px; padding: 12px; }

        h2 { font-size:0.75rem; text-transform:uppercase; color:#94a3b8; border-bottom:1px solid #334155; padding-bottom:5px; margin:0 0 10px 0; letter-spacing:1px; font-weight:700; }
        label { display:block; font-size:0.8rem; color:#cbd5e1; margin-bottom:4px; }
        
        /* Form Elements */
        input, select, textarea { width:100%; background:#0f172a; border:1px solid #475569; color:white; padding:8px; border-radius:6px; margin-bottom:10px; font-size:0.85rem; font-family:inherit; transition:0.2s; }
        input:focus, select:focus, textarea:focus { border-color:var(--p); box-shadow:0 0 0 2px rgba(59,130,246,0.2); }
        textarea { resize:vertical; min-height:60px; }
        
        /* Slider Input */
        .range-wrap { display:flex; align-items:center; gap:10px; margin-bottom:10px; }
        input[type=range] { margin:0; cursor:pointer; }
        .val-badge { background:#0f172a; padding:2px 6px; border-radius:4px; font-size:0.75rem; color:var(--acc); min-width:35px; text-align:center; border:1px solid #334155; }

        /* Buttons */
        .btn-group { display:flex; gap:10px; }
        button { flex:1; padding:10px; border-radius:6px; border:none; font-weight:600; cursor:pointer; font-size:0.9rem; transition:0.2s; }
        .btn-start { background: #10b981; color: white; } .btn-start:hover { background: #059669; }
        .btn-stop { background: #ef4444; color: white; } .btn-stop:hover { background: #dc2626; }
        .btn-sec { background: #334155; color: white; } .btn-sec:hover { background: #475569; }
        button:disabled { opacity:0.5; cursor:not-allowed; }

        /* Collapsible */
        details { background:#0f172a; padding:8px; border-radius:6px; margin-bottom:8px; border:1px solid #334155; }
        summary { cursor:pointer; font-size:0.8rem; color:var(--acc); font-weight:bold; list-style:none; }
        summary::after { content: "+"; float:right; }
        details[open] summary::after { content: "-"; }

        /* Feed */
        .feed { flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column; gap:15px; }
        .msg { background:#0f172a; padding:12px; border-radius:8px; border-left:4px solid var(--p); position:relative; animation:fadeIn 0.3s; }
        .meta { display:flex; justify-content:space-between; font-size:0.75rem; color:#64748b; margin-bottom:6px; }
        .content { font-size:1.05rem; line-height:1.5; color:#e2e8f0; }
        
        /* Header Stats */
        .header { padding:10px 15px; background:#1e293b; border-bottom:1px solid #334155; display:flex; justify-content:space-between; font-size:0.8rem; color:#94a3b8; }
        .active-dot { width:8px; height:8px; background:#ef4444; border-radius:50%; display:inline-block; margin-right:5px; animation:blink 1s infinite; display:none; }

        @keyframes fadeIn { from { opacity:0; transform:translateY(10px); } to { opacity:1; transform:translateY(0); } }
        @keyframes blink { 50% { opacity:0.4; } }
    </style>
</head>
<body>
    <div class="layout">
        <!-- SOL PANEL -->
        <div class="sidebar">
            <div class="panel">
                <h1 style="margin:0; font-size:1.2rem; background:linear-gradient(to right, #3b82f6, #8b5cf6); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Whisper Control</h1>
            </div>

            <!-- Kaynak & Kontrol -->
            <div class="panel">
                <h2>Mikrofon & Kayıt</h2>
                <label>Giriş Cihazı</label>
                <select id="devSel"><option>Yükleniyor...</option></select>
                
                <label>AI Gürültü Azaltma</label>
                <select id="nrSel">
                    <option value="0">Kapalı (Daha Hızlı)</option>
                    <option value="1">Açık (Sabit Gürültüyü Siler)</option>
                </select>

                <div class="btn-group">
                    <button id="bStart" class="btn-start" onclick="start()">BAŞLAT</button>
                    <button id="bStop" class="btn-stop" onclick="stop()" disabled>DURDUR</button>
                </div>
            </div>

            <!-- Gelişmiş Whisper Ayarları -->
            <div class="panel" style="border-color:#3b82f6;">
                <h2 style="color:#60a5fa">🤖 Gelişmiş Whisper Ayarları</h2>
                
                <label>Custom Prompt (Özel Kelimeler)</label>
                <textarea id="promptInp" placeholder="Örn: Aselsan, SQL, Python, toplantı notu."></textarea>
                
                <details>
                    <summary>🛠️ Parametre Detayları</summary>
                    <div style="margin-top:10px;">
                        
                        <label>Beam Size (1-10)</label>
                        <div class="range-wrap">
                            <input type="range" id="beamInp" min="1" max="10" value="5" oninput="updVal('beamVal', this.value)">
                            <div class="val-badge" id="beamVal">5</div>
                        </div>
                        <div style="font-size:0.7rem; color:#64748b; margin-bottom:8px;">
                            Yüksek değer = Daha doğru ama yavaş.<br>Düşük değer = Hızlı ama hata yapabilir.
                        </div>

                        <label>Temperature (0.0 - 1.0)</label>
                        <div class="range-wrap">
                            <input type="range" id="tempInp" min="0" max="1" step="0.1" value="0" oninput="updVal('tempVal', this.value)">
                            <div class="val-badge" id="tempVal">0.0</div>
                        </div>
                        <div style="font-size:0.7rem; color:#64748b; margin-bottom:8px;">
                            0.0 = Halüsinasyon yok, sadık.<br>0.8+ = Yaratıcı (Toplantı için 0 önerilir).
                        </div>
                        
                        <label>No Speech Threshold</label>
                        <div class="range-wrap">
                            <input type="range" id="nstInp" min="0.1" max="0.9" step="0.1" value="0.3" oninput="updVal('nstVal', this.value)">
                            <div class="val-badge" id="nstVal">0.3</div>
                        </div>

                    </div>
                </details>
            </div>

            <div class="panel">
                <h2>Model & Dil</h2>
                <select id="modelSel">
                    <option value="base">Base</option>
                    <option value="small">Small</option>
                    <option value="medium" selected>Medium (Önerilen)</option>
                    <option value="turbo">Turbo</option>
                    <option value="large-v3">Large v3</option>
                </select>
                <select id="langSel">
                    <option value="tr">Türkçe</option>
                    <option value="en">English</option>
                    <option value="de">Deutsch</option>
                </select>
                <button class="btn-sec" onclick="load()">Modeli Yükle</button>
            </div>
            
            <button class="btn-sec" onclick="dl()">⬇️ TXT İndir</button>
        </div>

        <!-- SAĞ PANEL -->
        <div class="main">
            <div class="header">
                <div>
                    <span id="recDot" class="active-dot"></span>
                    <span id="statusTxt">Hazır</span>
                </div>
                <div id="sysStat">CPU: 0%</div>
            </div>
            <div id="feed" class="feed">
                <div style="text-align:center; padding-top:100px; opacity:0.5;">
                    Sohbet akışı burada görünecek...
                </div>
            </div>
        </div>
    </div>

    <script>
        const socket = io();

        // Init
        socket.on('connect', () => {
            fetch('/api/devices').then(r=>r.json()).then(d=>{
                const s = document.getElementById('devSel'); s.innerHTML='';
                d.forEach(x => { let o=document.createElement('option'); o.value=x.id; o.text=x.name; s.appendChild(o); });
            });
        });

        // Sys Stats
        socket.on('sys', d => document.getElementById('sysStat').innerText = `CPU: ${d.cpu}% | MEM: ${d.mem}%`);

        // Result
        socket.on('result', d => {
            const f = document.getElementById('feed');
            if(f.innerText.includes('akışı burada')) f.innerHTML = '';
            
            let html = `
                <div class="msg">
                    <div class="meta">
                        <span>⏰ ${d.time}</span>
                        <span>Doğruluk: ${(d.conf*100).toFixed(0)}%</span>
                    </div>
                    <div class="content" contenteditable="true">${d.text}</div>
                </div>`;
            f.insertAdjacentHTML('afterbegin', html);
        });

        // Functions
        function updVal(id, val) { document.getElementById(id).innerText = val; }

        async function load() {
            let m = document.getElementById('modelSel').value;
            alert('Model yükleme isteği gönderildi...');
            await fetch('/api/load', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({model:m})});
            alert('Model Hazır!');
        }

        async function start() {
            let conf = {
                dev: document.getElementById('devSel').value,
                lang: document.getElementById('langSel').value,
                model: document.getElementById('modelSel').value,
                nr: document.getElementById('nrSel').value == '1',
                // WHISPER PARAMS
                prompt: document.getElementById('promptInp').value,
                beam: parseInt(document.getElementById('beamInp').value),
                temp: parseFloat(document.getElementById('tempInp').value),
                nst: parseFloat(document.getElementById('nstInp').value)
            };

            let r = await fetch('/api/start', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(conf)});
            if((await r.json()).ok) {
                document.getElementById('bStart').disabled = true;
                document.getElementById('bStop').disabled = false;
                document.getElementById('recDot').style.display = 'inline-block';
                document.getElementById('statusTxt').innerText = "KAYITTA (Sessizlik Bekleniyor)";
                document.getElementById('statusTxt').style.color = "#ef4444";
                
                // Disable inputs during recording
                document.getElementById('modelSel').disabled = true;
                document.getElementById('beamInp').disabled = true;
            }
        }

        async function stop() {
            await fetch('/api/stop', {method:'POST'});
            document.getElementById('bStart').disabled = false;
            document.getElementById('bStop').disabled = true;
            document.getElementById('recDot').style.display = 'none';
            document.getElementById('statusTxt').innerText = "HAZIR";
            document.getElementById('statusTxt').style.color = "#94a3b8";
            
            // Enable
            document.getElementById('modelSel').disabled = false;
            document.getElementById('beamInp').disabled = false;
        }

        function dl() {
            let t = document.getElementById('feed').innerText;
            let blob = new Blob([t], {type:'text/plain'});
            let url = URL.createObjectURL(blob);
            let a = document.createElement('a'); a.href=url; a.download='kayitlar.txt'; a.click();
        }
    </script>
</body>
</html>
'''

# --- ENGINE ---
class Engine:
    def __init__(self):
        self.running = False
        self.model = None
        self.q = queue.Queue()
        self.context = deque(maxlen=5) # Son 5 transkripsiyon
        threading.Thread(target=self._sys, daemon=True).start()

    def load_model(self, name):
        try:
            d = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = WhisperModel(name, device=d, compute_type="float16" if d=="cuda" else "int8")
            return True
        except Exception as e: return str(e)

    def start(self, conf):
        if not self.model: self.load_model(conf['model'])
        self.conf = conf
        self.running = True
        
        # Threads
        threading.Thread(target=self._capture, args=(int(conf['dev']),), daemon=True).start()
        threading.Thread(target=self._transcribe, daemon=True).start()
        return True

    def stop(self): self.running = False

    def _sys(self):
        while True:
            time.sleep(2)
            socketio.emit('sys', {'cpu': psutil.cpu_percent(), 'mem': psutil.virtual_memory().percent})

    def _capture(self, dev):
        p = pyaudio.PyAudio()
        stream = None
        consecutive_errors = 0
        try:
            info = p.get_device_info_by_index(dev)
            rate = int(info['defaultSampleRate'])
            ch = info['maxInputChannels']
            
            chunk_size = int(rate * 0.03) # 30ms chunks
            stream = p.open(format=pyaudio.paInt16, channels=ch, rate=rate, input=True, input_device_index=dev, frames_per_buffer=chunk_size)
            
            buf = []
            silence_ticks = 0
            speaking = False
            
            # Parametreler (Hardcoded thresholds for stability)
            thresh = 250
            target_rate = 16000
            max_silence_ticks = int(SILENCE_TIMEOUT_MS / 30)

            while self.running:
                try:
                    raw = stream.read(chunk_size, exception_on_overflow=False)
                    consecutive_errors = 0
                except OSError:
                    consecutive_errors += 1
                    if consecutive_errors >= 50:
                        self.running = False
                        break
                    time.sleep(0.05)
                    continue
                
                data = np.frombuffer(raw, dtype=np.int16)
                
                # Stereo->Mono
                if ch > 1: data = data.reshape(-1, ch).mean(axis=1).astype(np.int16)
                
                # Resample -> 16000
                if rate != target_rate:
                    new_len = int(len(data) * target_rate / rate)
                    data = np.interp(np.linspace(0, len(data), new_len), np.arange(len(data)), data).astype(np.int16)

                # VAD / Sessizlik Mantığı
                if np.abs(data).mean() > thresh:
                    speaking = True
                    silence_ticks = 0
                    buf.append(data)
                else:
                    if speaking:
                        silence_ticks += 1
                        buf.append(data)
                        
                        if silence_ticks > max_silence_ticks:
                            # Cümle Bitti
                            full = np.concatenate(buf)
                            if len(full) > target_rate * (MIN_AUDIO_MS/1000):
                                self.q.put(full)
                            
                            # Sıfırla
                            buf = []
                            silence_ticks = 0
                            speaking = False
                
                # Buffer şişmesi koruması
                if len(buf) * 30 > MAX_AUDIO_MS:
                    if buf: self.q.put(np.concatenate(buf))
                    buf = []
                    speaking = False

        finally:
            try:
                if stream is not None:
                    stream.close()
            finally:
                p.terminate()

    def _transcribe(self):
        while self.running:
            try:
                audio_raw = self.q.get(timeout=1)
                
                # 1. DSP Processing
                proc = AudioDSP.process(audio_raw, enable_nr=self.conf['nr'])
                
                # 2. PROMPT Hazırlama (Kullanıcı + Bağlam)
                user_prompt = self.conf.get('prompt', '')
                ctx_hist = " ".join(self.context)
                # Modeli yönlendirmek için en etkili yol: Özel isimler + Son cümle
                full_prompt = f"{user_prompt} Konuşmanın devamı: {ctx_hist}"

                # 3. WHISPER PARAMETRELERİNİ UYGULA
                segs, _ = self.model.transcribe(
                    proc,
                    language=self.conf['lang'],
                    initial_prompt=full_prompt,             # DİNAMİK PROMPT
                    beam_size=self.conf.get('beam', 5),     # DİNAMİK BEAM
                    temperature=self.conf.get('temp', 0.0), # DİNAMİK TEMP
                    no_speech_threshold=self.conf.get('nst', 0.3),
                    vad_filter=True
                )

                txt = " ".join([s.text for s in segs]).strip()
                prob = segs[0].avg_logprob if segs else 0
                confidence = np.exp(prob) # Yaklaşık güven skoru

                if not txt: continue
                self.context.append(txt)

                socketio.emit('result', {
                    'text': txt,
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'conf': confidence
                })

            except queue.Empty: continue
            except Exception as e: print("Err:",e)

# Flask Rotaları
engine = Engine()

@app.route('/')
def index(): return render_template_string(HTML)

@app.route('/api/devices')
def devices(): 
    # Device listeleme (engine sınıfından çek)
    p = pyaudio.PyAudio()
    devs = []
    try:
        for i in range(p.get_device_count()):
            try:
                info = p.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0: devs.append({'id': i, 'name': info['name']})
            except: pass
        # Loopback
        try:
            w = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            o = p.get_device_info_by_index(w["defaultOutputDevice"])
            if not o["isLoopbackDevice"]:
                for l in p.get_loopback_device_info_generator():
                    if o["name"] in l["name"]:
                        devs.insert(0, {'id': l["index"], 'name': f"📢 SISTEM ({l['name']})"})
                        break
        except: pass
    finally: p.terminate()
    return jsonify(devs)

@app.route('/api/load', methods=['POST'])
def load(): return jsonify({'ok': engine.load_model(request.json['model'])})

@app.route('/api/start', methods=['POST'])
def start(): return jsonify({'ok': engine.start(request.json)})

@app.route('/api/stop', methods=['POST'])
def stop(): engine.stop(); return jsonify({'ok': True})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5000)
