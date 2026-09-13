#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Whisper Desktop Overlay Widget
Always-on-top transkripsiyon penceresi
Kopyalama özelliği eklendi
"""

import tkinter as tk
from tkinter import ttk, font
import socketio
import threading
import json
from datetime import datetime
import sys

class TranscriptionOverlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Whisper Live")
        
        # Pencere özellikleri
        self.width = 350
        self.height = 600
        self.root.geometry(f"{self.width}x{self.height}")
        
        # Always on top
        self.root.attributes('-topmost', True)
        
        # Yarı saydam pencere (Windows)
        if sys.platform == 'win32':
            self.root.attributes('-alpha', 0.95)
        
        # Tema değişkenleri
        self.dark_theme = True
        self.compact_mode = False
        self.auto_scroll = True
        
        # Transkripsiyon verilerini sakla
        self.all_transcriptions = []
        
        # Socket.IO client
        self.sio = socketio.Client()
        self.setup_socket_events()
        
        # UI oluştur
        self.setup_ui()
        
        # Pozisyonu ayarla (ekranın sağ kenarı)
        self.set_position('right')
        
        # Socket.IO bağlantısını başlat
        self.connect_to_server()
        
    def setup_ui(self):
        """Kullanıcı arayüzünü oluştur"""
        
        # Ana frame
        self.main_frame = tk.Frame(self.root, bg='#141928')
        self.main_frame.pack(fill='both', expand=True)
        
        # Header
        self.create_header()
        
        # Transkripsiyon alanı
        self.create_transcription_area()
        
        # Tema uygula
        self.apply_theme()
        
    def create_header(self):
        """Üst kontrol paneli"""
        header_frame = tk.Frame(self.main_frame, bg='#1e2332', height=40)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # Sol taraf - Başlık ve durum
        left_frame = tk.Frame(header_frame, bg='#1e2332')
        left_frame.pack(side='left', padx=10, pady=5)
        
        # Durum göstergesi
        self.status_dot = tk.Canvas(left_frame, width=8, height=8, 
                                   bg='#1e2332', highlightthickness=0)
        self.status_dot.pack(side='left', padx=(0, 8))
        self.status_indicator = self.status_dot.create_oval(0, 0, 8, 8, 
                                                           fill='#ef4444', 
                                                           outline='')
        
        # Başlık
        tk.Label(left_frame, text="Whisper Live", 
                fg='white', bg='#1e2332', 
                font=('Segoe UI', 11, 'bold')).pack(side='left')
        
        # Sağ taraf - Kontrol butonları
        right_frame = tk.Frame(header_frame, bg='#1e2332')
        right_frame.pack(side='right', padx=10, pady=5)
        
        # Butonlar
        buttons = [
            ("📋", self.copy_all_transcriptions, "Tümünü Kopyala"),
            ("🔄", self.toggle_compact, "Kompakt"),
            ("🎨", self.toggle_theme, "Tema"),
            ("↓", self.toggle_autoscroll, "Otomatik Kaydır"),
            ("🗑️", self.clear_transcriptions, "Temizle"),
            ("📌", self.toggle_pin, "Sabitle"),
            ("⬅", lambda: self.set_position('left'), "Sol"),
            ("➡", lambda: self.set_position('right'), "Sağ"),
            ("❌", self.close_app, "Kapat")
        ]
        
        for icon, command, tooltip in buttons:
            btn = tk.Button(right_frame, text=icon, command=command,
                          fg='white', bg='#2a2f3e', 
                          font=('Segoe UI', 10),
                          width=2, height=1,
                          relief='flat', cursor='hand2')
            btn.pack(side='left', padx=2)
            
            # Hover efekti
            btn.bind('<Enter>', lambda e, b=btn: b.config(bg='#667eea'))
            btn.bind('<Leave>', lambda e, b=btn: b.config(bg='#2a2f3e'))
            
            # Tooltip oluştur
            self.create_tooltip(btn, tooltip)
            
    def create_tooltip(self, widget, text):
        """Basit tooltip oluştur"""
        def on_enter(event):
            tooltip = tk.Toplevel(self.root)
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, 
                           background="#ffffe0", 
                           relief='solid', 
                           borderwidth=1,
                           font=('Segoe UI', 9))
            label.pack()
            widget.tooltip = tooltip
            
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
                
        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)
    
    def create_transcription_area(self):
        """Transkripsiyon görüntüleme alanı"""
        
        # Scrolled Text widget
        text_frame = tk.Frame(self.main_frame, bg='#141928')
        text_frame.pack(fill='both', expand=True, padx=10, pady=(5, 10))
        
        # Text widget with scrollbar
        self.text_widget = tk.Text(text_frame, 
                                  bg='#141928',
                                  fg='white',
                                  font=('Consolas', 10),
                                  wrap='word',
                                  relief='flat',
                                  padx=10,
                                  pady=10,
                                  insertbackground='white')
        
        scrollbar = ttk.Scrollbar(text_frame, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)
        
        self.text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Tag'ler tanımla
        self.text_widget.tag_configure('timestamp', 
                                      foreground='#9ca3af', 
                                      font=('Consolas', 8))
        self.text_widget.tag_configure('speaker', 
                                      foreground='#93bbff', 
                                      font=('Consolas', 9, 'bold'))
        self.text_widget.tag_configure('text', 
                                      foreground='#e5e7eb', 
                                      font=('Consolas', 10))
        self.text_widget.tag_configure('translation', 
                                      foreground='#93c5fd', 
                                      font=('Consolas', 9, 'italic'))
        self.text_widget.tag_configure('success_msg', 
                                      foreground='#10b981', 
                                      font=('Consolas', 9, 'italic'))
        
        # Başlangıç mesajı
        self.show_empty_state()
        
    def show_empty_state(self):
        """Boş durum mesajı"""
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, "\n\n\n", 'text')
        self.text_widget.insert(tk.END, "        🎙️ Bekleniyor...\n\n", 'speaker')
        self.text_widget.insert(tk.END, "   Ana uygulamadan ses yakalamayı\n", 'text')
        self.text_widget.insert(tk.END, "           başlatın\n\n", 'text')
        self.text_widget.insert(tk.END, "      http://localhost:5000", 'timestamp')
        
    def copy_all_transcriptions(self):
        """Tüm transkripsiyonları panoya kopyala"""
        
        # Eğer boş durum mesajı varsa veya hiç transkripsiyon yoksa
        if not self.all_transcriptions:
            # Text widget'tan mevcut metni al
            all_text = self.text_widget.get(1.0, tk.END).strip()
            
            # Eğer sadece boş durum mesajı varsa, uyarı göster
            if "Bekleniyor" in all_text:
                self.show_copy_message("Kopyalanacak transkripsiyon yok!", success=False)
                return
        
        # Tüm transkripsiyonları formatla
        if self.all_transcriptions:
            formatted_text = "=== WHISPER LIVE TRANSKRİPSİYONLAR ===\n\n"
            
            for trans in self.all_transcriptions:
                formatted_text += f"[{trans.get('timestamp', '')}] "
                
                if trans.get('speaker_name'):
                    formatted_text += f"{trans['speaker_name']}: "
                    
                formatted_text += f"{trans['text']}\n"
                
                if trans.get('translation'):
                    formatted_text += f"   → {trans['translation']}\n"
                    
                formatted_text += "\n"
        else:
            # Text widget'tan direkt al
            formatted_text = self.text_widget.get(1.0, tk.END).strip()
        
        # Panoya kopyala
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(formatted_text)
            self.root.update()  # Clipboard'u güncelle
            
            # Başarı mesajı göster
            self.show_copy_message("✅ Tüm konuşmalar kopyalandı!")
            
        except Exception as e:
            self.show_copy_message(f"Kopyalama hatası: {str(e)}", success=False)
    
    def scroll_to_bottom(self):
        """Text widget'ı en alta kaydır"""
        self.text_widget.update_idletasks()
        self.text_widget.see(tk.END)
        self.text_widget.yview_moveto(1.0)
    
    def show_copy_message(self, message, success=True):
        """Kopyalama mesajını göster"""
        # Mevcut konumu kaydet
        current_pos = self.text_widget.yview()
        
        # Mesajı en alta ekle
        self.text_widget.insert(tk.END, f"\n{message}\n", 'success_msg' if success else 'timestamp')
        
        # 2 saniye sonra mesajı kaldır
        self.root.after(2000, lambda: self.remove_copy_message(current_pos))
    
    def remove_copy_message(self, restore_pos):
        """Kopyalama mesajını kaldır"""
        # Son 2 satırı kontrol et ve kopyalama mesajını bul
        content = self.text_widget.get("end-3l", "end-1c")
        if "kopyalandı" in content or "Kopyalama hatası" in content or "Kopyalanacak" in content:
            # Son 2 satırı sil
            self.text_widget.delete("end-3l", "end-1c")
        
        # Pozisyonu geri yükle
        self.text_widget.yview_moveto(restore_pos[0])
    
    def add_transcription(self, data):
        """Yeni transkripsiyon ekle"""
        
        # Veriyi sakla
        self.all_transcriptions.append(data)
        
        # İlk transkripsiyon geldiğinde boş mesajı temizle
        if "Bekleniyor" in self.text_widget.get(1.0, tk.END):
            self.text_widget.delete(1.0, tk.END)
        
        # Zaman damgası
        timestamp = data.get('timestamp', datetime.now().strftime('%H:%M:%S'))
        self.text_widget.insert(tk.END, f"[{timestamp}] ", 'timestamp')
        
        # Konuşmacı
        if data.get('speaker_name'):
            self.text_widget.insert(tk.END, f"{data['speaker_name']}: ", 'speaker')
        
        # Metin
        self.text_widget.insert(tk.END, f"{data['text']}\n", 'text')
        
        # Çeviri
        if data.get('translation'):
            self.text_widget.insert(tk.END, f"   ➜ {data['translation']}\n", 'translation')
        
        self.text_widget.insert(tk.END, "\n")
        
        # Otomatik kaydırma
        if self.auto_scroll:
            self.text_widget.see(tk.END)
        
        # Eski kayıtları temizle (100 satırdan fazla olmasın)
        lines = self.text_widget.get(1.0, tk.END).count('\n')
        if lines > 100:
            # İlk transkripsiyonu listeden de kaldır
            if len(self.all_transcriptions) > 50:
                self.all_transcriptions = self.all_transcriptions[-50:]
            self.text_widget.delete(1.0, '10.0')
    
    def setup_socket_events(self):
        """Socket.IO event handler'ları"""
        
        @self.sio.event
        def connect():
            print("✅ Sunucuya bağlandı")
            self.update_status(True)
            
        @self.sio.event
        def disconnect():
            print("❌ Bağlantı koptu")
            self.update_status(False)
            
        @self.sio.event
        def new_transcription(data):
            # UI thread'inde güncelle
            self.root.after(0, lambda: self.add_transcription(data))
            
        @self.sio.event
        def capture_started(data):
            self.update_status(True)
            
        @self.sio.event
        def capture_stopped(data):
            self.update_status(False)
    
    def connect_to_server(self):
        """Socket.IO sunucusuna bağlan"""
        def connect_thread():
            try:
                self.sio.connect('http://localhost:5000')
            except Exception as e:
                print(f"Bağlantı hatası: {e}")
                self.root.after(5000, self.connect_to_server)  # 5 saniye sonra tekrar dene
        
        thread = threading.Thread(target=connect_thread, daemon=True)
        thread.start()
    
    def update_status(self, is_active):
        """Durum göstergesini güncelle"""
        color = '#10b981' if is_active else '#ef4444'
        self.status_dot.itemconfig(self.status_indicator, fill=color)
    
    def toggle_compact(self):
        """Kompakt mod"""
        self.compact_mode = not self.compact_mode
        if self.compact_mode:
            self.text_widget.config(font=('Consolas', 8))
            self.root.geometry(f"300x400")
        else:
            self.text_widget.config(font=('Consolas', 10))
            self.root.geometry(f"{self.width}x{self.height}")
    
    def toggle_theme(self):
        """Tema değiştir"""
        self.dark_theme = not self.dark_theme
        self.apply_theme()
    
    def apply_theme(self):
        """Temayı uygula"""
        if self.dark_theme:
            bg_color = '#141928'
            fg_color = '#e5e7eb'
            header_bg = '#1e2332'
        else:
            bg_color = '#ffffff'
            fg_color = '#1f2937'
            header_bg = '#f8f9fa'
        
        self.main_frame.config(bg=bg_color)
        self.text_widget.config(bg=bg_color, fg=fg_color)
        
        # Header frame'i güncelle
        for widget in self.main_frame.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.config(bg=header_bg if widget.winfo_y() == 0 else bg_color)
    
    def toggle_autoscroll(self):
        """Otomatik kaydırma"""
        self.auto_scroll = not self.auto_scroll
    
    def toggle_pin(self):
        """Always on top"""
        current = self.root.attributes('-topmost')
        self.root.attributes('-topmost', not current)
    
    def clear_transcriptions(self):
        """Transkripsiyon temizle"""
        self.all_transcriptions = []
        self.show_empty_state()
    
    def set_position(self, position):
        """Pencere pozisyonu"""
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        if position == 'left':
            x = 0
            y = (screen_height - self.height) // 2
        elif position == 'right':
            x = screen_width - self.width
            y = (screen_height - self.height) // 2
        elif position == 'top':
            x = (screen_width - self.width) // 2
            y = 0
        elif position == 'bottom':
            x = (screen_width - self.width) // 2
            y = screen_height - self.height - 40  # Taskbar için boşluk
        else:
            return
        
        self.root.geometry(f"{self.width}x{self.height}+{x}+{y}")
    
    def close_app(self):
        """Uygulamayı kapat"""
        if self.sio.connected:
            self.sio.disconnect()
        self.root.destroy()
    
    def run(self):
        """Uygulamayı başlat"""
        
        # Klavye kısayolları
        self.root.bind('<Control-q>', lambda e: self.toggle_compact())
        self.root.bind('<Control-t>', lambda e: self.toggle_theme())
        self.root.bind('<Control-s>', lambda e: self.toggle_autoscroll())
        self.root.bind('<Control-l>', lambda e: self.clear_transcriptions())
        self.root.bind('<Control-c>', lambda e: self.copy_all_transcriptions())  # Kopyalama kısayolu
        self.root.bind('<Control-a>', lambda e: self.select_all_text())  # Tümünü seç
        self.root.bind('<Escape>', lambda e: self.close_app())
        
        # Pencereyi sürükleme
        def start_move(event):
            self.x = event.x
            self.y = event.y
            
        def on_move(event):
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")
        
        # Header'ı sürüklenebilir yap
        for widget in self.main_frame.winfo_children():
            if isinstance(widget, tk.Frame) and widget.winfo_y() == 0:
                widget.bind('<Button-1>', start_move)
                widget.bind('<B1-Motion>', on_move)
        
        self.root.mainloop()
    
    def select_all_text(self):
        """Text widget'taki tüm metni seç"""
        self.text_widget.tag_add('sel', '1.0', 'end')
        self.text_widget.mark_set('insert', '1.0')
        self.text_widget.see('insert')
        return 'break'  # Default davranışı engelle

if __name__ == "__main__":
    print("="*50)
    print("WHISPER DESKTOP OVERLAY")
    print("="*50)
    print("🎙️ Always-on-top transkripsiyon penceresi")
    print("")
    print("🌍 ÇEVİRİ ÖZELLİĞİ:")
    print("  • Çevrilmemiş satıra tıklayın")
    print("  • 'Türkçe'ye Çevir' butonuna basın")
    print("  • DeepL ile anında çeviri!")
    print("")
    print("Klavye kısayolları:")
    print("  Ctrl+D : DeepL API Key ayarla 🔑")
    print("  Ctrl+C : Tüm konuşmaları kopyala 📋")
    print("  Ctrl+A : Tümünü seç")
    print("  Ctrl+Q : Kompakt mod")
    print("  Ctrl+T : Tema değiştir")
    print("  Ctrl+S : Otomatik kaydırma")
    print("  Ctrl+L : Temizle")
    print("  ESC    : Kapat")
    print("")
    print("⚠️ DeepL API Key gerekli!")
    print("   Ctrl+D ile key'inizi girin veya")
    print("   Kod içinde deepl_api_key değişkenini ayarlayın")
    print("")
    print("⚠️ Ana uygulama çalışıyor olmalı:")
    print("   http://localhost:5000")
    print("="*50)
    
    # Gerekli kütüphaneleri kontrol et
    try:
        import socketio
    except ImportError:
        print("\n❌ python-socketio kurulu değil!")
        print("📦 Kurmak için: pip install python-socketio[client]")
        sys.exit(1)
    
    app = TranscriptionOverlay()
    app.run()
