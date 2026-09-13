"""
🌐 AI Translator - Yapay Zeka Destekli Çeviri Aracı
Ekrandan alan seçip OCR ile metin çıkarır ve yapay zeka ile çeviri yapar.
Vision modelleri ile doğrudan görüntüden çeviri de yapabilir.
"""

from groq import Groq
from google import genai
import pyautogui
from PIL import Image, ImageTk, ImageOps
import numpy as np
import base64
import io
import os
import tkinter as tk
from tkinter import ttk
import threading
import keyboard
import requests
import time

try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# --- API AYARLARI ---
API_KEY = os.environ.get('API_KEY')
DEEPL_API_KEY = os.environ.get('DEEPL_API_KEY')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
APIFREE_API_KEY = os.environ.get('APIFREE_API_KEY')
CEREBRAS_API_KEY = os.environ.get('CEREBRAS_API_KEY')

# Groq Client
client = Groq(api_key=API_KEY)

# Gemini Client
try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Gemini Client Init Error: {e}")
    gemini_client = None


class TranslatorGUI:
    # Model Mapping
    MODEL_MAP = {
        "Llama 3.2 90B Vision": "llama-3.2-90b-vision-preview",
        "Llama 3.2 11B Vision": "llama-3.2-11b-vision-preview",
        "Llama 3.3 70B": "llama-3.3-70b-versatile",
        "Llama 3.1 8B": "llama-3.1-8b-instant",
        "Maverick 17B": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "Scout 17B": "meta-llama/llama-4-scout-17b-16e-instruct",
        "GPT-OSS 120B": "openai/gpt-oss-120b",
        "Kimi K2": "moonshotai/kimi-k2-instruct-0905",
        "DeepSeek V3.2": "deepseek-ai/deepseek-v3.2",
        "Gemini 3 Flash (Vision)": "gemini-3-flash-preview",
        "Gemini 3 Flash (OCR)": "gemini-3-flash-preview",
        "Claude 4.5 Haiku": "anthropic/claude-haiku-4.5",
        "Claude 4.5 Sonnet": "anthropic/claude-sonnet-4.5",
        "Qwen 3 32B": "qwen-3-32b",
        "Qwen 3 235B": "qwen-3-235b-a22b-instruct-2507"
    }

    # Vision destekleyen modeller (doğrudan resimden çeviri)
    VISION_MODELS = ["Maverick 17B", "Scout 17B", "Llama 3.2 90B Vision", "Llama 3.2 11B Vision", "Gemini 3 Flash (Vision)"]

    # Desteklenen diller
    LANGUAGES = {
        "Türkçe": "tr",
        "İngilizce": "en",
        "Almanca": "de",
        "Fransızca": "fr",
        "İspanyolca": "es",
        "İtalyanca": "it",
        "Rusça": "ru",
        "Japonca": "ja",
        "Korece": "ko",
        "Çince": "zh",
        "Arapça": "ar",
        "Portekizce": "pt",
        "Hollandaca": "nl"
    }

    # OCR Dil Mapping
    OCR_LANG_MAP = {
        "Türkçe+İngilizce": "tur+eng",
        "Sadece Türkçe": "tur",
        "Sadece İngilizce": "eng",
        "Almanca": "deu",
        "Fransızca": "fra",
        "İspanyolca": "spa",
        "Japonca": "jpn",
        "Korece": "kor",
        "Çince": "chi_sim",
        "Arapça": "ara",
        "Rusça": "rus"
    }

    def __init__(self, root):
        self.root = root
        self.root.title("🌐 AI Translator - Yapay Zeka Çeviri")
        self.root.geometry("900x700")
        self.root.configure(bg='#1a1a2e')

        self.selected_region = None
        self.session = requests.Session()
        self.total_tokens = 0

        # === HEADER ===
        header_frame = tk.Frame(root, bg='#16213e', height=80)
        header_frame.pack(fill='x')
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="🌐 AI TRANSLATOR 🌐",
            font=('Arial', 24, 'bold'),
            bg='#16213e',
            fg='#00d9ff'
        )
        title_label.pack(pady=20)

        subtitle_label = tk.Label(
            header_frame,
            text="OCR + Yapay Zeka Destekli Çeviri",
            font=('Arial', 10),
            bg='#16213e',
            fg='#7a8b9e'
        )
        subtitle_label.place(relx=0.5, rely=0.75, anchor='center')

        # === BUTON ALANI ===
        button_frame = tk.Frame(root, bg='#1a1a2e')
        button_frame.pack(pady=10)

        self.select_btn = tk.Button(
            button_frame,
            text="📍 Alan Seç",
            command=self.start_selection,
            font=('Arial', 14, 'bold'),
            bg='#00d9ff',
            fg='#1a1a2e',
            activebackground='#00b8d4',
            cursor='hand2',
            padx=30,
            pady=12,
            relief='flat'
        )
        self.select_btn.pack(side='left', padx=10)

        self.translate_btn = tk.Button(
            button_frame,
            text="🌍 Çevir",
            command=self.translate,
            font=('Arial', 14, 'bold'),
            bg='#00ff88',
            fg='#1a1a2e',
            activebackground='#00dd70',
            cursor='hand2',
            padx=30,
            pady=12,
            relief='flat',
            state='disabled'
        )
        self.translate_btn.pack(side='left', padx=10)

        # === AYARLAR ===
        settings_frame = tk.Frame(root, bg='#1a1a2e')
        settings_frame.pack(pady=10)

        # Model Seçimi
        tk.Label(settings_frame, text="Model:", font=('Arial', 12), bg='#1a1a2e', fg='#e0e0e0').pack(side='left', padx=5)
        self.model_var = tk.StringVar(value="Llama 3.3 70B")
        self.model_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.model_var,
            values=list(self.MODEL_MAP.keys()),
            state="readonly",
            font=('Arial', 11),
            width=20
        )
        self.model_combo.pack(side='left', padx=5)

        # OCR Dil Seçimi
        tk.Label(settings_frame, text="OCR Dili:", font=('Arial', 12), bg='#1a1a2e', fg='#e0e0e0').pack(side='left', padx=(15, 5))
        self.ocr_lang_var = tk.StringVar(value="Türkçe+İngilizce")
        self.ocr_combo = ttk.Combobox(
            settings_frame,
            textvariable=self.ocr_lang_var,
            values=list(self.OCR_LANG_MAP.keys()),
            state="readonly",
            font=('Arial', 11),
            width=16
        )
        self.ocr_combo.pack(side='left', padx=5)

        # == DİL SEÇİMİ ==
        lang_frame = tk.Frame(root, bg='#1a1a2e')
        lang_frame.pack(pady=5)

        # Kaynak Dil
        tk.Label(lang_frame, text="Kaynak:", font=('Arial', 12), bg='#1a1a2e', fg='#e0e0e0').pack(side='left', padx=5)
        self.source_lang_var = tk.StringVar(value="İngilizce")
        self.source_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.source_lang_var,
            values=["Otomatik Algıla"] + list(self.LANGUAGES.keys()),
            state="readonly",
            font=('Arial', 11),
            width=14
        )
        self.source_combo.pack(side='left', padx=5)

        # Swap butonu
        self.swap_btn = tk.Button(
            lang_frame,
            text="⇄",
            command=self.swap_languages,
            font=('Arial', 14, 'bold'),
            bg='#0f3460',
            fg='#00d9ff',
            activebackground='#16213e',
            cursor='hand2',
            padx=10,
            pady=2,
            relief='flat'
        )
        self.swap_btn.pack(side='left', padx=10)

        # Hedef Dil
        tk.Label(lang_frame, text="Hedef:", font=('Arial', 12), bg='#1a1a2e', fg='#e0e0e0').pack(side='left', padx=5)
        self.target_lang_var = tk.StringVar(value="Türkçe")
        self.target_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.target_lang_var,
            values=list(self.LANGUAGES.keys()),
            state="readonly",
            font=('Arial', 11),
            width=14
        )
        self.target_combo.pack(side='left', padx=5)

        # Vision Mode Checkbox
        self.vision_var = tk.BooleanVar(value=False)
        self.vision_check = tk.Checkbutton(
            lang_frame,
            text="👁️ Vision (Resimden)",
            variable=self.vision_var,
            font=('Arial', 10),
            bg='#1a1a2e',
            fg='#ff9f43',
            selectcolor='#0f3460',
            activebackground='#1a1a2e',
            activeforeground='#ff9f43'
        )
        self.vision_check.pack(side='left', padx=(15, 5))

        # DeepL checkbox
        self.use_deepl_var = tk.BooleanVar(value=False)
        self.deepl_check = tk.Checkbutton(
            lang_frame,
            text="🌐 DeepL",
            variable=self.use_deepl_var,
            font=('Arial', 10),
            bg='#1a1a2e',
            fg='#00d9ff',
            selectcolor='#0f3460',
            activebackground='#1a1a2e',
            activeforeground='#00d9ff'
        )
        self.deepl_check.pack(side='left', padx=(5, 5))

        # === DURUM ===
        self.status_label = tk.Label(
            root,
            text="Başlamak için alan seçin | Kısayol: Ctrl+Alt+T",
            font=('Arial', 11),
            bg='#1a1a2e',
            fg='#7a8b9e'
        )
        self.status_label.pack(pady=5)

        # === SONUÇ ALANI ===
        result_frame = tk.Frame(root, bg='#0f3460', padx=20, pady=20)
        result_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # Kaydırılabilir metin alanı
        canvas = tk.Canvas(result_frame, bg='#0f3460', highlightthickness=0)
        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas, bg='#0f3460')

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Hoşgeldin mesajı
        welcome_label = tk.Label(
            self.scrollable_frame,
            text="👋 Hoş geldiniz!\n\nBaşlamak için 'Alan Seç' butonuna tıklayın.\n\nKısayol: Ctrl+Alt+T ile seçili alanı çevir.",
            font=('Arial', 12),
            bg='#0f3460',
            fg='#7a8b9e',
            justify='center'
        )
        welcome_label.pack(pady=50)

        # === FOOTER ===
        footer_frame = tk.Frame(root, bg='#0f3460', pady=8)
        footer_frame.pack(fill='x', padx=20, pady=(0, 5))

        self.stats_label = tk.Label(
            footer_frame,
            text="📊 Token: 0",
            font=('Arial', 9),
            bg='#0f3460',
            fg='#7a8b9e'
        )
        self.stats_label.pack()

        # === HOTKEYS ===
        keyboard.add_hotkey('ctrl+alt+t', self.hotkey_translate)

    def hotkey_translate(self):
        """Ctrl+Alt+T ile çeviri başlat"""
        if self.selected_region:
            self.root.after(0, self.translate)

    def swap_languages(self):
        """Kaynak ve hedef dili değiştir"""
        source = self.source_lang_var.get()
        target = self.target_lang_var.get()

        if source != "Otomatik Algıla":
            self.target_lang_var.set(source)
            self.source_lang_var.set(target)

    def start_selection(self):
        self.status_label.config(text="Alan seçiliyor...")
        self.root.withdraw()
        self.root.after(200, self.create_selection_overlay)

    def create_selection_overlay(self):
        self.overlay = tk.Toplevel()
        self.overlay.attributes('-fullscreen', True)
        self.overlay.attributes('-alpha', 0.3)
        self.overlay.configure(bg='black')

        self.canvas = tk.Canvas(self.overlay, bg='black', highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)

        instruction = tk.Label(
            self.overlay,
            text="Çevirmek istediğiniz alanı seçin",
            font=('Arial', 16, 'bold'),
            bg='black',
            fg='white'
        )
        instruction.place(relx=0.5, rely=0.05, anchor='center')

        self.start_x = None
        self.start_y = None
        self.rect = None

        self.canvas.bind('<Button-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='#00d9ff', width=3
        )

    def on_drag(self, event):
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        end_x = event.x
        end_y = event.y

        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        width = x2 - x1
        height = y2 - y1

        self.overlay.destroy()

        if width > 10 and height > 10:
            self.selected_region = (x1, y1, width, height)
            self.root.deiconify()
            self.status_label.config(text=f"✅ Alan seçildi: {width}x{height} piksel")
            self.translate_btn.config(state='normal', bg='#00ff88')
            self.select_btn.config(bg='#7a8b9e')
        else:
            self.root.deiconify()
            self.status_label.config(text="❌ Geçersiz alan! Tekrar deneyin.")

    def optimize_image_for_ocr(self, image):
        """OCR için görüntüyü iyileştirir"""
        try:
            gray_image = image.convert('L')
            np_image = np.array(gray_image)
            avg_brightness = np.mean(np_image)

            if avg_brightness < 128:
                gray_image = ImageOps.invert(gray_image)

            if gray_image.width < 1000:
                scale_factor = 2
                new_size = (gray_image.width * scale_factor, gray_image.height * scale_factor)
                gray_image = gray_image.resize(new_size, Image.Resampling.LANCZOS)

            return gray_image
        except Exception as e:
            print(f"OCR optimizasyon hatası: {e}")
            return image

    def compress_image_to_base64(self, image, quality=85):
        """Görüntüyü JPEG formatında sıkıştırıp base64 döndürür"""
        buffer = io.BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        max_dim = 1024
        if max(image.width, image.height) > max_dim:
            image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def translate_with_deepl(self, text, target_lang='TR'):
        """DeepL API ile çeviri"""
        try:
            url = "https://api-free.deepl.com/v2/translate"
            data = {
                'auth_key': DEEPL_API_KEY,
                'text': text,
                'target_lang': target_lang.upper()
            }
            print(f"DeepL Request: target_lang={target_lang.upper()}, text_len={len(text)}")
            response = self.session.post(url, data=data, timeout=15)

            print(f"DeepL Response: status={response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"DeepL Success: {result}")
                return result['translations'][0]['text']
            else:
                print(f"DeepL Error Response: {response.text}")
                return None
        except Exception as e:
            print(f"DeepL Exception: {e}")
            return None

    def translate(self):
        if not self.selected_region:
            return

        self.translate_btn.config(state='disabled')
        self.status_label.config(text="🌍 Çeviri yapılıyor...")

        # Temizle
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        threading.Thread(target=self.translate_thread, daemon=True).start()

    def translate_thread(self):
        try:
            model_choice = self.model_var.get()
            source_lang = self.source_lang_var.get()
            target_lang = self.target_lang_var.get()
            use_vision = self.vision_var.get()
            use_deepl = self.use_deepl_var.get()

            # Ekran görüntüsü al
            screenshot = pyautogui.screenshot(region=self.selected_region)

            # Görüntüyü optimize et
            max_size = 800
            quality = 70

            if screenshot.width > max_size or screenshot.height > max_size:
                ratio = min(max_size/screenshot.width, max_size/screenshot.height)
                new_size = (int(screenshot.width * ratio), int(screenshot.height * ratio))
                screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)

            base64_image = self.compress_image_to_base64(screenshot, quality=quality)

            original_text = ""
            translated_text = ""

            # === VISION MODU ===
            if use_vision and model_choice in self.VISION_MODELS:
                self.root.after(0, lambda: self.status_label.config(text="👁️ Vision ile çeviri yapılıyor..."))

                target_lang_name = target_lang

                vision_prompt = f"""You are a professional translator. Look at this image and:
1. Extract ALL text you see in the image
2. Translate it to {target_lang_name}

OUTPUT FORMAT:
ORIGINAL TEXT:
[The exact text from the image]

TRANSLATION ({target_lang_name}):
[The translation]

NOTES:
[Any context or notes about the translation, if needed]"""

                model_id = self.MODEL_MAP.get(model_choice)

                if "gemini" in model_id:
                    gemini_contents = [
                        {"text": vision_prompt},
                        {"inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64_image
                        }}
                    ]

                    response = gemini_client.models.generate_content(
                        model=model_id,
                        contents=gemini_contents
                    )
                    result_text = response.text.strip()

                    if hasattr(response, 'usage_metadata'):
                        self.total_tokens += response.usage_metadata.total_token_count
                else:
                    content_payload = [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]

                    response = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": content_payload}],
                        temperature=0.3,
                        max_tokens=2000
                    )
                    result_text = response.choices[0].message.content.strip()

                    if hasattr(response, 'usage') and response.usage:
                        self.total_tokens += response.usage.total_tokens

                # Sonucu göster
                self.root.after(0, lambda: self.display_result(result_text, "", is_vision=True))

            # === OCR + AI MODU ===
            else:
                # OCR ile metin çıkar
                if not OCR_AVAILABLE:
                    self.root.after(0, lambda: self.show_error("⚠️ OCR (pytesseract) yüklü değil!\n\npip install pytesseract"))
                    return

                self.root.after(0, lambda: self.status_label.config(text="📝 OCR ile metin çıkarılıyor..."))

                ocr_image = self.optimize_image_for_ocr(screenshot)
                ocr_lang = self.OCR_LANG_MAP.get(self.ocr_lang_var.get(), "tur+eng")

                try:
                    custom_config = r'--oem 3 --psm 6'
                    original_text = pytesseract.image_to_string(ocr_image, lang=ocr_lang, config=custom_config).strip()
                except Exception as e:
                    print(f"OCR Error: {e}")
                    original_text = pytesseract.image_to_string(ocr_image, lang='eng', config=custom_config).strip()

                if not original_text:
                    self.root.after(0, lambda: self.show_error("⚠️ Görüntüden metin çıkarılamadı!\n\nDaha net bir görüntü seçin veya Vision modellerini deneyin."))
                    return

                print(f"OCR Çıktısı:\n{original_text}")

                # DeepL ile çevir
                if use_deepl:
                    self.root.after(0, lambda: self.status_label.config(text="🌐 DeepL ile çevriliyor..."))
                    target_code = self.LANGUAGES.get(target_lang, "tr").upper()
                    translated_text = self.translate_with_deepl(original_text, target_code)

                    if translated_text:
                        self.root.after(0, lambda: self.display_result(original_text, translated_text))
                    else:
                        self.root.after(0, lambda: self.show_error("⚠️ DeepL çevirisi başarısız!"))
                    return

                # AI ile çevir
                self.root.after(0, lambda: self.status_label.config(text=f"🤖 {model_choice} ile çevriliyor..."))

                target_lang_name = target_lang
                source_lang_name = source_lang if source_lang != "Otomatik Algıla" else "kaynak dil"

                translate_prompt = f"""You are a professional translator. Translate the following text from {source_lang_name} to {target_lang_name}.

RULES:
- Translate naturally, not word-by-word
- Keep the meaning and tone
- If there are technical terms, translate them appropriately
- Do NOT add explanations unless necessary

TEXT TO TRANSLATE:
{original_text}

TRANSLATION:"""

                model_id = self.MODEL_MAP.get(model_choice)

                # API çağrısı
                if "gemini" in model_id:
                    response = gemini_client.models.generate_content(
                        model=model_id,
                        contents=[{"text": translate_prompt}]
                    )
                    translated_text = response.text.strip()

                    if hasattr(response, 'usage_metadata'):
                        self.total_tokens += response.usage_metadata.total_token_count

                elif any(x in model_id for x in ["anthropic", "deepseek", "kimi"]):
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {APIFREE_API_KEY}"
                    }
                    payload = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": translate_prompt}],
                        "max_tokens": 2000,
                        "temperature": 0.3
                    }
                    try:
                        response = self.session.post(
                            "https://api.apifree.ai/v1/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=60  # Kimi K2 yavaş olabilir
                        )
                        if response.status_code == 200:
                            resp_json = response.json()
                            # Error in response body kontrolü (API bazen 200 ile error döner)
                            if 'error' in resp_json or 'code' in resp_json:
                                print(f"API Error in response: {resp_json}")
                                raise Exception(f"API Error: {resp_json.get('error', resp_json)}")
                            # API response format kontrolü
                            if 'choices' in resp_json and len(resp_json['choices']) > 0:
                                translated_text = resp_json['choices'][0]['message']['content'].strip()
                            elif 'content' in resp_json:
                                translated_text = resp_json['content'].strip()
                            elif 'text' in resp_json:
                                translated_text = resp_json['text'].strip()
                            else:
                                print(f"Beklenmeyen API yanıt formatı: {resp_json}")
                                raise Exception("Beklenmeyen yanıt formatı")
                        else:
                            print(f"API Error ({response.status_code}): {response.text}")
                            # Fallback to Groq
                            self.root.after(0, lambda: self.status_label.config(text="⚠️ API hatası, Llama 3.3 deneniyor..."))
                            response = client.chat.completions.create(
                                model="llama-3.3-70b-versatile",
                                messages=[{"role": "user", "content": translate_prompt}],
                                temperature=0.3,
                                max_tokens=2000
                            )
                            translated_text = response.choices[0].message.content.strip()
                    except Exception as api_error:
                        print(f"APIfree Error: {api_error}")
                        # Fallback to Groq
                        self.root.after(0, lambda: self.status_label.config(text="⚠️ Bağlantı hatası, Llama 3.3 deneniyor..."))
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "user", "content": translate_prompt}],
                            temperature=0.3,
                            max_tokens=2000
                        )
                        translated_text = response.choices[0].message.content.strip()

                elif any(x in model_id for x in ["qwen", "llama3.1-8b"]):
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {CEREBRAS_API_KEY}"
                    }
                    payload = {
                        "model": model_id,
                        "messages": [{"role": "user", "content": translate_prompt}],
                        "max_completion_tokens": 2000,
                        "temperature": 0.3,
                        "stream": False
                    }
                    response = self.session.post(
                        "https://api.cerebras.ai/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    if response.status_code == 200:
                        translated_text = response.json()['choices'][0]['message']['content'].strip()
                    else:
                        print(f"Cerebras Error: {response.text}")

                else:
                    # Groq API
                    response = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": translate_prompt}],
                        temperature=0.3,
                        max_tokens=2000
                    )
                    translated_text = response.choices[0].message.content.strip()

                    if hasattr(response, 'usage') and response.usage:
                        self.total_tokens += response.usage.total_tokens

                # Sonucu göster
                self.root.after(0, lambda: self.display_result(original_text, translated_text))

            # UI güncelle
            self.root.after(0, lambda: self.status_label.config(text="✅ Çeviri tamamlandı!", fg='#00ff88'))
            self.root.after(0, lambda: self.translate_btn.config(state='normal'))
            self.root.after(0, lambda: self.stats_label.config(text=f"📊 Token: {self.total_tokens}"))

            # Panoya kopyala
            self.root.after(0, lambda: self.copy_to_clipboard(translated_text if translated_text else ""))

            # Ses bildirimi
            try:
                import winsound
                winsound.Beep(1000, 100)
            except:
                pass

        except Exception as e:
            print(f"Çeviri hatası: {e}")
            self.root.after(0, lambda: self.show_error(f"❌ Hata: {str(e)}"))
            self.root.after(0, lambda: self.translate_btn.config(state='normal'))

    def display_result(self, original, translated, is_vision=False):
        """Sonucu göster"""
        # Temizle
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if is_vision:
            # Vision modu - tek metin
            result_label = tk.Label(
                self.scrollable_frame,
                text=original,
                font=('Arial', 11),
                bg='#0f3460',
                fg='#ffffff',
                justify='left',
                wraplength=800
            )
            result_label.pack(pady=10, padx=10, anchor='w')
        else:
            # OCR + AI modu - iki panel
            # Orijinal metin
            orig_frame = tk.Frame(self.scrollable_frame, bg='#16213e', padx=10, pady=10)
            orig_frame.pack(fill='x', pady=5, padx=5)

            orig_title = tk.Label(
                orig_frame,
                text="📄 ORİJİNAL METİN:",
                font=('Arial', 12, 'bold'),
                bg='#16213e',
                fg='#00d9ff'
            )
            orig_title.pack(anchor='w')

            orig_text = tk.Label(
                orig_frame,
                text=original,
                font=('Arial', 11),
                bg='#16213e',
                fg='#b0b0b0',
                justify='left',
                wraplength=800
            )
            orig_text.pack(anchor='w', pady=5)

            # Çeviri
            trans_frame = tk.Frame(self.scrollable_frame, bg='#1a3a5c', padx=10, pady=10)
            trans_frame.pack(fill='x', pady=5, padx=5)

            trans_title = tk.Label(
                trans_frame,
                text="🌍 ÇEVİRİ:",
                font=('Arial', 12, 'bold'),
                bg='#1a3a5c',
                fg='#00ff88'
            )
            trans_title.pack(anchor='w')

            trans_text = tk.Label(
                trans_frame,
                text=translated,
                font=('Arial', 12),
                bg='#1a3a5c',
                fg='#ffffff',
                justify='left',
                wraplength=800
            )
            trans_text.pack(anchor='w', pady=5)

    def show_error(self, message):
        """Hata göster"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        error_label = tk.Label(
            self.scrollable_frame,
            text=message,
            font=('Arial', 12),
            bg='#0f3460',
            fg='#ff6b6b',
            justify='center'
        )
        error_label.pack(pady=50)

        self.status_label.config(text="❌ Hata oluştu", fg='#ff6b6b')
        self.translate_btn.config(state='normal')

    def copy_to_clipboard(self, text):
        """Metni panoya kopyala"""
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
        except:
            pass


def main():
    root = tk.Tk()
    app = TranslatorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
