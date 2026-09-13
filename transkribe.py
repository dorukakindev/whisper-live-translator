#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import threading
import queue
import tkinter as tk
from contextlib import ExitStack
from tkinter import ttk, filedialog, scrolledtext, messagebox
from faster_whisper import WhisperModel

MODELS_DIR = os.path.join(os.path.dirname(__file__), "whisper_models")

# Model klasörlerini otomatik tara
def find_models():
    models = {}
    if not os.path.isdir(MODELS_DIR):
        return models
    for entry in os.listdir(MODELS_DIR):
        snapshots_dir = os.path.join(MODELS_DIR, entry, "snapshots")
        if not os.path.isdir(snapshots_dir):
            continue
        snapshots = sorted(
            os.listdir(snapshots_dir),
            key=lambda snap: (
                os.path.getmtime(os.path.join(snapshots_dir, snap)),
                snap
            ),
            reverse=True
        )
        for snap in snapshots:
            model_bin = os.path.join(snapshots_dir, snap, "model.bin")
            if os.path.isfile(model_bin):
                # Güzel isim üret: models--Systran--faster-whisper-large-v3 → large-v3 (Systran)
                parts = entry.replace("models--", "").split("--")
                if len(parts) >= 2:
                    org = parts[0]
                    name = "--".join(parts[1:]).replace("faster-whisper-", "")
                    label = f"{name}  [{org}]"
                else:
                    label = entry
                models[label] = os.path.join(snapshots_dir, snap)
                break  # her model icin en yeni gecerli snapshot
    return models

def detect_device():
    try:
        import torch
        if torch.cuda.is_available():
            name = torch.cuda.get_device_name(0)
            return "cuda", f"CUDA  ({name})"
    except Exception:
        pass
    return "cpu", "CPU"


def remove_overlap(history, new_text):
    """
    Yeni segmentin tamamı veya başı, son N flush'tan biriyle örtüşüyorsa sil.
    history: son flushed metinlerin listesi (en yeni sonda).
    """
    if not new_text:
        return new_text
    new_lower = new_text.lower().strip()
    new_pairs = [
        (word, word.casefold().strip('.,!?;:…“”"()[]'))
        for word in new_text.split()
    ]
    new_pairs = [(word, normalized) for word, normalized in new_pairs if normalized]
    new_words = [word for word, _ in new_pairs]
    new_lower_words = [normalized for _, normalized in new_pairs]

    for prev_text in reversed(history):
        if not prev_text:
            continue
        prev_lower = prev_text.lower().strip()

        # Bir kelimenin baska bir kelime icinde gecmesi tekrar kaniti degildir.
        if new_lower == prev_lower:
            return ""

        # Başı önceki segmentin sonuyla örtüşüyor
        prev_words = [
            normalized for normalized in (
                w.casefold().strip('.,!?;:…“”"()[]') for w in prev_text.split()
            ) if normalized
        ]
        max_overlap = min(10, len(prev_words), len(new_words))
        for n in range(max_overlap, 0, -1):
            # Tek kelimelik tekrar ancak belirgin bir kelimeyse silinir; "a", "I"
            # gibi kisa ve dogal baslangiclar yanlis pozitif olmasin.
            if (n > 1 or len(new_lower_words[0]) >= 4) and prev_words[-n:] == new_lower_words[:n]:
                remainder = " ".join(new_words[n:]).strip()
                return remainder if remainder else ""

    return new_text


def merge_overlapping_cues(cues):
    """Birlesik ciktilarda cakisan zamanlari metin silmeden tek cue'da topla."""
    merged = []
    for start, end, text in sorted(cues, key=lambda cue: cue[0]):
        if merged and start < merged[-1][1]:
            prev_start, prev_end, prev_text = merged[-1]
            merged[-1] = (prev_start, max(prev_end, end), prev_text + ' ' + text)
        else:
            merged.append((start, end, text))
    return merged


def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class App(tk.Tk):
    def __init__(self, initial_file=None):
        super().__init__()
        self.title("Whisper Transkripsiyon")
        self.geometry("760x560")
        self.resizable(True, True)
        self.configure(bg="#1e1e2e")
        self._model = None
        self._loaded_model_key = None  # hangi model yüklü
        self._running = False
        self._cancel_event = threading.Event()
        self._last_output_paths = []
        self._models = find_models()
        self._default_device, self._cuda_label = detect_device()
        self._ui_events = queue.Queue()
        self._build_ui()
        self.after(50, self._drain_ui_events)

        if initial_file:
            self.file_var.set(initial_file)

    def _build_ui(self):
        PAD = 12
        BG = "#1e1e2e"
        PANEL = "#2a2a3e"
        ACCENT = "#7c6af7"
        FG = "#cdd6f4"
        ENTRY_BG = "#313244"

        # --- Dosya seçimi ---
        file_frame = tk.Frame(self, bg=BG)
        file_frame.pack(fill="x", padx=PAD, pady=(PAD, 4))

        tk.Label(file_frame, text="Dosya:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left")

        self.file_var = tk.StringVar()
        entry = tk.Entry(file_frame, textvariable=self.file_var, bg=ENTRY_BG, fg=FG,
                         insertbackground=FG, relief="flat", font=("Segoe UI", 10))
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6), ipady=5)

        tk.Button(file_frame, text="Gözat", bg=ACCENT, fg="white", relief="flat",
                  font=("Segoe UI", 10), padx=10,
                  command=self._browse).pack(side="left")

        # --- Model + Cihaz ---
        model_frame = tk.Frame(self, bg=BG)
        model_frame.pack(fill="x", padx=PAD, pady=4)

        tk.Label(model_frame, text="Model:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left")

        model_names = sorted(self._models.keys())
        default_model = next((m for m in model_names if "turbo" in m.lower()),
                             next((m for m in model_names if "large" in m.lower()),
                                  model_names[0] if model_names else ""))
        self.model_var = tk.StringVar(value=default_model)
        model_box = ttk.Combobox(model_frame, textvariable=self.model_var,
                                 values=model_names, state="readonly",
                                 font=("Segoe UI", 10), width=36)
        model_box.pack(side="left", padx=(4, 16))
        model_box.bind("<<ComboboxSelected>>", lambda e: self._on_model_change())

        # Cihaz
        tk.Label(model_frame, text="Cihaz:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left")
        device_values = [self._cuda_label, "CPU"] if self._default_device == "cuda" else ["CPU"]
        self.device_var = tk.StringVar(value=device_values[0])
        device_box = ttk.Combobox(model_frame, textvariable=self.device_var,
                                  values=device_values, state="readonly",
                                  font=("Segoe UI", 10), width=22)
        device_box.pack(side="left", padx=(4, 0))
        device_box.bind("<<ComboboxSelected>>", lambda e: self._on_model_change())

        # --- Ayarlar ---
        settings_frame = tk.Frame(self, bg=BG)
        settings_frame.pack(fill="x", padx=PAD, pady=4)

        # Dil
        tk.Label(settings_frame, text="Dil:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left")
        self.lang_var = tk.StringVar(value="auto")
        lang_box = ttk.Combobox(settings_frame, textvariable=self.lang_var, width=10,
                                values=["auto", "tr", "en", "de", "fr", "es", "it", "ja", "zh", "ar"],
                                state="readonly", font=("Segoe UI", 10))
        lang_box.pack(side="left", padx=(4, 16))

        # Çıktı formatı
        tk.Label(settings_frame, text="Çıktı:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left")
        self.fmt_srt = tk.BooleanVar(value=True)
        self.fmt_txt = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="SRT", variable=self.fmt_srt,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       font=("Segoe UI", 10)).pack(side="left", padx=(4, 4))
        tk.Checkbutton(settings_frame, text="TXT", variable=self.fmt_txt,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       font=("Segoe UI", 10)).pack(side="left", padx=(0, 16))

        # Cümle birleştirme
        self.merge_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings_frame, text="Cümle birleştir", variable=self.merge_var,
                       bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG,
                       font=("Segoe UI", 10)).pack(side="left", padx=(0, 10))

        # Max karakter
        tk.Label(settings_frame, text="Maks karakter:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        self.max_chars_var = tk.IntVar(value=120)
        chars_spin = tk.Spinbox(settings_frame, from_=60, to=300, increment=10,
                                textvariable=self.max_chars_var,
                                width=4, bg=ENTRY_BG, fg=FG, buttonbackground=PANEL,
                                relief="flat", font=("Segoe UI", 10))
        chars_spin.pack(side="left", padx=(4, 0))

        # --- Başlat butonu ---
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", padx=PAD, pady=4)

        self.start_btn = tk.Button(btn_frame, text="▶  Başlat", bg=ACCENT, fg="white",
                                   relief="flat", font=("Segoe UI", 11, "bold"),
                                   padx=20, pady=6, command=self._start)
        self.start_btn.pack(side="left")

        self.status_lbl = tk.Label(btn_frame, text="", bg=BG, fg="#a6e3a1",
                                   font=("Segoe UI", 10))
        self.status_lbl.pack(side="left", padx=12)

        self.time_lbl = tk.Label(btn_frame, text="", bg=BG, fg="#89b4fa",
                                 font=("Segoe UI", 10))
        self.time_lbl.pack(side="right", padx=4)

        # --- Progress bar ---
        prog_frame = tk.Frame(self, bg=BG)
        prog_frame.pack(fill="x", padx=PAD, pady=(0, 2))

        self.progress = ttk.Progressbar(prog_frame, mode="determinate", maximum=100)
        self.progress.pack(side="left", fill="x", expand=True)

        self.pct_lbl = tk.Label(prog_frame, text="", bg=BG, fg=FG,
                                font=("Segoe UI", 9), width=6)
        self.pct_lbl.pack(side="left", padx=(6, 0))

        # --- Log alanı ---
        self.log = scrolledtext.ScrolledText(self, bg=PANEL, fg=FG, font=("Consolas", 9),
                                             relief="flat", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))

        # --- Çıktı dosyaları ---
        out_frame = tk.Frame(self, bg=BG)
        out_frame.pack(fill="x", padx=PAD, pady=(0, PAD))

        tk.Label(out_frame, text="Çıktı:", bg=BG, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        self.out_lbl = tk.Label(out_frame, text="—", bg=BG, fg="#89b4fa", font=("Segoe UI", 9))
        self.out_lbl.pack(side="left", padx=6)
        self.copy_out_btn = tk.Button(out_frame, text="Yolu Kopyala", bg=PANEL, fg=FG,
                                      relief="flat", state="disabled",
                                      command=self._copy_output_paths)
        self.copy_out_btn.pack(side="right", padx=4)
        self.open_out_btn = tk.Button(out_frame, text="Klasörü Aç", bg=PANEL, fg=FG,
                                      relief="flat", state="disabled",
                                      command=self._open_output_folder)
        self.open_out_btn.pack(side="right", padx=4)

        # Stil
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=ENTRY_BG, background=PANEL,
                        foreground=FG, selectbackground=ACCENT)
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT)

        # Model yok uyarısı
        if not self._models:
            self._log("UYARI: whisper_models klasöründe model bulunamadı!")

    def _on_model_change(self):
        # Model veya cihaz değişince cache'i temizle
        self._model = None
        self._loaded_model_key = None

    def _browse(self):
        path = filedialog.askopenfilename(
            filetypes=[("Ses/Video", "*.mp3 *.mp4 *.wav *.m4a *.mkv *.webm *.ogg"),
                       ("Tüm dosyalar", "*.*")]
        )
        if path:
            self.file_var.set(path)

    def _log(self, msg):
        self._ui_events.put(('log', msg))

    def _drain_ui_events(self):
        # Worker hicbir Tk metoduna (after dahil) dokunmaz.
        for _ in range(200):
            try:
                event, value = self._ui_events.get_nowait()
            except queue.Empty:
                break
            if event == 'log':
                self._append_log(value)
            elif event == 'progress':
                self.progress.configure(value=value)
                self.pct_lbl.configure(text=f'{value:.0f}%')
            elif event == 'status':
                self.status_lbl.config(text=value[0], fg=value[1])
            elif event == 'time':
                self.time_lbl.config(text=value)
            elif event == 'done':
                self._done(*value)
        self.after(50, self._drain_ui_events)

    def _append_log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start(self):
        if self._running:
            self._cancel_event.set()
            self.start_btn.config(state="disabled", text="İptal ediliyor…")
            self.status_lbl.config(text="İptal bekleniyor…", fg="#f9e2af")
            return
        file_path = self.file_var.get().strip()
        if not file_path or not os.path.exists(file_path):
            self.status_lbl.config(text="Geçerli bir dosya seç!", fg="#f38ba8")
            return
        if not self.fmt_srt.get() and not self.fmt_txt.get():
            self.status_lbl.config(text="En az bir çıktı formatı seç!", fg="#f38ba8")
            return
        if not self._models:
            self.status_lbl.config(text="Model bulunamadı!", fg="#f38ba8")
            return

        base = os.path.splitext(file_path)[0]
        targets = [
            path for enabled, path in (
                (self.fmt_srt.get(), base + ".srt"),
                (self.fmt_txt.get(), base + ".txt"),
            ) if enabled and os.path.exists(path)
        ]
        if targets and not messagebox.askyesno(
                "Dosyanın üzerine yazılsın mı?",
                "Şu çıktı dosyaları zaten var:\n\n"
                + "\n".join(os.path.basename(path) for path in targets)
                + "\n\nÜzerlerine yazmak istiyor musunuz?"):
            return

        self._running = True
        self._cancel_event.clear()
        self.start_btn.config(state="normal", text="İptal")
        self.status_lbl.config(text="Çalışıyor...", fg="#a6e3a1")
        self.time_lbl.config(text="")
        self.out_lbl.config(text="—")
        self._last_output_paths = []
        self.copy_out_btn.config(state="disabled")
        self.open_out_btn.config(state="disabled")
        self.progress["value"] = 0
        self.pct_lbl.config(text="")
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

        options = {
            'model': self.model_var.get(), 'device': self.device_var.get(),
            'lang': self.lang_var.get(), 'merge': self.merge_var.get(),
            'max_chars': self.max_chars_var.get(),
            'srt': self.fmt_srt.get(), 'txt': self.fmt_txt.get(),
        }
        threading.Thread(target=self._run, args=(file_path, options), daemon=True).start()

    def _set_progress(self, pct):
        self._ui_events.put(('progress', pct))

    def _set_status(self, text, color="#a6e3a1"):
        self._ui_events.put(('status', (text, color)))

    def _set_time(self, text):
        self._ui_events.put(('time', text))

    def _run(self, file_path, options):
        import time as _time
        try:
            selected_model = options['model']
            model_path = self._models.get(selected_model)
            device_label = options['device']
            device = "cuda" if "CUDA" in device_label else "cpu"
            compute_type = "float16" if device == "cuda" else "int8"
            model_key = (selected_model, device)

            if self._model is None or self._loaded_model_key != model_key:
                self._log(f"Model yükleniyor: {selected_model}  [{device.upper()}]...")
                self._set_status("Model yükleniyor...")
                self._model = WhisperModel(model_path, device=device, compute_type=compute_type)
                self._loaded_model_key = model_key
                self._log("Model hazır.\n")
            else:
                self._log(f"Model zaten yüklü: {selected_model}  [{device.upper()}]\n")

            lang = options['lang']
            kwargs = {}
            if lang != "auto":
                kwargs["language"] = lang

            self._log(f"Transkripsiyon başlıyor: {os.path.basename(file_path)}")
            self._set_status("Transkripsiyon...")
            t0 = _time.time()

            segments, info = self._model.transcribe(
                file_path,
                word_timestamps=False,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                compression_ratio_threshold=2.4,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                **kwargs
            )
            total_dur = info.duration or 1.0

            self._log(f"Algılanan dil: {info.language} ({info.language_probability:.0%})  |  Süre: {total_dur:.1f}s\n")

            # Merge modunda önce segmentleri biriktiriyoruz ama canlı loga yazıyoruz
            do_merge = options['merge']
            SENTENCE_END = ('.', '?', '!', '…', '..."', '."', '?"', '!"')
            MAX_CHARS = options['max_chars']
            MIN_CHARS = 25  # bu kadardan kısa cümle tek başına flush olmaz

            buf_text = ""
            buf_start = None
            buf_end = None
            processed = []
            flush_history = []  # son 5 flushed metin

            for seg in segments:
                if getattr(self, '_cancel_event', None) is not None and self._cancel_event.is_set():
                    self._log("\nİşlem kullanıcı tarafından iptal edildi.")
                    self._ui_events.put(('done', (None, 'İptal edildi')))
                    return
                text = seg.text.strip()
                if not text:
                    continue

                # Tekrar tespiti: son flush geçmişine bakarak örtüşen kısmı sil
                text = remove_overlap(flush_history, text)
                if not text:
                    continue

                # İlerleme güncelle
                pct = min(seg.end / total_dur * 100, 99)
                elapsed = _time.time() - t0
                eta = (elapsed / (pct / 100) - elapsed) if pct > 0 else 0
                self._set_progress(pct)
                self._set_status(f"İşleniyor...  {format_timestamp(seg.end)} / {format_timestamp(total_dur)}")
                self._set_time(f"Geçen: {elapsed:.0f}s  |  Kalan: ~{eta:.0f}s")

                if do_merge:
                    if buf_start is None:
                        buf_start = seg.start
                    buf_end = seg.end
                    buf_text = (buf_text + " " + text).strip() if buf_text else text

                    ends_sentence = buf_text.endswith(SENTENCE_END)
                    too_long = len(buf_text) > MAX_CHARS
                    long_enough = len(buf_text) >= MIN_CHARS

                    if too_long or (ends_sentence and long_enough):
                        processed.append((buf_start, buf_end, buf_text))
                        self._log(f"[{format_timestamp(buf_start)}] {buf_text}")
                        flush_history.append(buf_text)
                        if len(flush_history) > 5:
                            flush_history.pop(0)
                        buf_text = ""
                        buf_start = None
                        buf_end = None
                else:
                    processed.append((seg.start, seg.end, text))
                    self._log(f"[{format_timestamp(seg.start)}] {text}")
                    flush_history.append(text)
                    if len(flush_history) > 5:
                        flush_history.pop(0)

            # Birleştirme modunda kalan buffer'ı ekle
            if getattr(self, '_cancel_event', None) is not None and self._cancel_event.is_set():
                self._log("\nİşlem kullanıcı tarafından iptal edildi.")
                self._ui_events.put(('done', (None, 'İptal edildi')))
                return
            if do_merge and buf_text:
                processed.append((buf_start, buf_end, buf_text))
                self._log(f"[{format_timestamp(buf_start)}] {buf_text}")

            if do_merge:
                processed = merge_overlapping_cues(processed)

            # Dosyalara yaz
            base = os.path.splitext(file_path)[0]
            srt_path = base + ".srt"
            txt_path = base + ".txt"

            # Iki cikti secenegi birbirinden bagimsizdir; yazim ortasinda hata
            # olsa bile acilan tum dosyalar ExitStack ile mutlaka kapatilir.
            with ExitStack() as stack:
                srt_file = (
                    stack.enter_context(open(srt_path, "w", encoding="utf-8"))
                    if options['srt'] else None
                )
                txt_file = (
                    stack.enter_context(open(txt_path, "w", encoding="utf-8"))
                    if options['txt'] else None
                )

                for i, (t_start, t_end, text) in enumerate(processed, start=1):
                    start = format_timestamp(t_start)
                    end = format_timestamp(t_end)
                    if srt_file:
                        srt_file.write(f"{i}\n{start} --> {end}\n{text}\n\n")
                    if txt_file:
                        txt_file.write(f"[{start} --> {end}] {text}\n")

            elapsed_total = _time.time() - t0
            outputs = []
            if options['srt']:
                outputs.append(os.path.basename(srt_path))
            if options['txt']:
                outputs.append(os.path.basename(txt_path))
            self._last_output_paths = [
                path for enabled, path in (
                    (options['srt'], srt_path), (options['txt'], txt_path)
                ) if enabled
            ]

            self._log(f"\n✓ Tamamlandı. {len(processed)} segment  |  {elapsed_total:.1f}s")
            self._ui_events.put(('done', (True, '  |  '.join(outputs))))

        except Exception as e:
            error_message = str(e)
            self._log(f"\nHata: {error_message}")
            # Tk bilesenlerine yalniz ana thread'deki kuyruk tuketicisi dokunur.
            self._ui_events.put(('done', (False, error_message)))

    def _done(self, success, msg):
        self._running = False
        self._cancel_event.clear()
        self.progress["value"] = 100 if success else 0
        self.pct_lbl.config(text="100%" if success else "")
        self.time_lbl.config(text="")
        self.start_btn.config(state="normal", text="▶  Başlat")
        if success:
            self.status_lbl.config(text="Tamamlandı", fg="#a6e3a1")
            self.out_lbl.config(text=msg, fg="#89b4fa")
            self.copy_out_btn.config(state="normal")
            self.open_out_btn.config(state="normal")
        elif success is None:
            self.status_lbl.config(text="İptal edildi", fg="#f9e2af")
            self.out_lbl.config(text=msg, fg="#f9e2af")
        else:
            self.status_lbl.config(text="Hata oluştu", fg="#f38ba8")
            self.out_lbl.config(text=msg, fg="#f38ba8")

    def _copy_output_paths(self):
        if not self._last_output_paths:
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(self._last_output_paths))
        self.status_lbl.config(text="Çıktı yolu panoya kopyalandı", fg="#a6e3a1")

    def _open_output_folder(self):
        if self._last_output_paths:
            os.startfile(os.path.dirname(self._last_output_paths[0]))


if __name__ == "__main__":
    initial = sys.argv[1] if len(sys.argv) > 1 else None
    app = App(initial_file=initial)
    app.mainloop()
