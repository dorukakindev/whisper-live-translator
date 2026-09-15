# WHISPER PRO — DERİN KOD DENETİMİ VE HATA RAPORU
**Tarih:** 2 Eylül 2026  
**Durum:** Tespit Edildi, Kodda Değişiklik Yapılmadı (Sadece Raporlama)

---

## YÖNETİCİ ÖZETİ

Bu rapor, Whisper Pro masaüstü uygulamasının tüm bileşenlerinde (`buyedektir.py`, `templates/index.html`, `templates/overlay.html`, `main.js`, `launcher_whisper.py`, `transkribe.py` ve `test_smoke.py`) gerçekleştirilen derinlemesine statik analiz, eşzamanlılık (concurrency), dil işleme boru hattı ve yaşam döngüsü denetimi sonucunda tespit edilen **30 adet doğrulanmış hatayı** içermektedir.

Tüm bulgular kod konumları, kök nedenleri, sisteme/kullanıcıya etkileri ve önerilen çözüm adımlarıyla birlikte aşağıda sunulmuştur.

---

## 1. KRİTİK SEVİYE MANTIKSAL VE VERİSEL HATALAR

### [BUG-01] Alt PTT (Bas-Konuş) Hedef Dil Tersliği ve "auto" Prompt İflası
* **Dosya & Satır:** [`templates/index.html:4504-4518`](file:///d:/Whisper%20Live/templates/index.html#L4504-L4518) ve [`buyedektir.py:4440-4458`](file:///d:/Whisper%20Live/buyedektir.py#L4440-L4458)
* **Kategori:** Mantıksal Hata / Fonksiyonel Bozukluk
* **Mekanizma:**
  `templates/index.html` içerisindeki `setAltPtt(active)` fonksiyonunda mikrofon bas-konuş başlatılırken `target_lang` olarak PC sistem sesinin giriş dili olan `whisperLang` okunmaktadır:
  ```javascript
  const inputLang = document.querySelector('input[name="whisperLang"]:checked')?.value || 'tr';
  // ...
  body: JSON.stringify({ active: active, target_lang: inputLang, device_index: deviceIndex })
  ```
  Oysa kullanıcının karşı tarafa konuşmak istediği hedef yabancı dil `aiTargetLang` (Japonca, İngilizce, Almanca vb.) seçimidir.
* **Etki:**
  1. Kullanıcı Alt tuşuna basarak mikrofona Türkçe konuştuğunda, backend'e `target_lang: 'tr'` gönderilir. `buyedektir.py:4440`'ta `if target_lang == 'tr'` şartı devreye girer: Çeviri ve Türkçe okunuş iptal edilir (`romanized = ""`) ve ekrana `🎙️ Benim Sesim (TR → TR)` basılır. Kullanıcı hiçbir zaman yabancı dilde okunuş alamaz.
  2. Eğer kullanıcı PC ses dinleme dilini "Otomatik" (`auto`) seçmişse, backend'e `target_lang: 'auto'` gider. OpenAI'a `"auto diline çevir"` istemi gönderilir, model dili anlayamaz ve hata üretir.
* **Önerilen Çözüm:** `setAltPtt` fonksiyonunda `target_lang`, `document.getElementById('aiTargetLang')?.value || 'en'` üzerinden okunmalı; 'auto' veya geçersiz değer durumunda güvenli bir varsayılana düşülmelidir.

---

### [BUG-02] Canlı İletişimde En Temel Kısa Yanıtların ("はい", "OK", "No", "Ne?", "你好") Halüsinasyon Sayılarak Silinmesi
* **Dosya & Satır:** [`buyedektir.py:2788-2790`](file:///d:/Whisper%20Live/buyedektir.py#L2788-L2790) (`WhisperWebTranscriber._is_likely_hallucination`)
* **Kategori:** Dil İşleme / Veri Kaybı
* **Mekanizma:**
  ```python
  meaningful = re.sub(r'[\s\.,!?;:\-\'"()\[\]{}…•·]', '', text)
  if len(meaningful) < 3:
      return True
  ```
  Noktalama işaretleri temizlendikten sonra karakter uzunluğu 3'ten küçükse fonksiyon doğrudan `True` (halüsinasyon) dönmektedir.
* **Etki:**
  Canlı diller arası konuşmada en çok kullanılan onay, red ve selam ifadeleri doğrudan sansürlenir ve çöpe atılır:
  * **Japonca:** `"はい"` (Hai = Evet) -> 2 karakter -> **Halüsinasyon (Silinir!)**
  * **İngilizce:** `"OK"`, `"No"`, `"Hi"`, `"Go"` -> 2 karakter -> **Halüsinasyon (Silinir!)**
  * **Türkçe:** `"Ne?"`, `"Su"`, `"Bu"`, `"Ve"`, `"Ev"` -> 2 karakter -> **Halüsinasyon (Silinir!)**
  * **Çince:** `"你好"` (Ni hao = Merhaba) -> 2 karakter -> **Halüsinasyon (Silinir!)**
  * **Çince:** `"对"` (Doğru), `"好"` (Tamam), `"是"` (Evet) -> 1 karakter -> **Halüsinasyon (Silinir!)**
  Karşı taraf "Hai" veya "OK" dediğinde Whisper bunu doğru tanısa dahi transkripsiyon boru hattı metni çöpe atar ve ekrana hiçbir şey basılmaz.
* **Önerilen Çözüm:** CJK dillerinde ideogram başına uzunluk 1 olmalıdır (`len >= 1`). Latin dillerinde ise bilinen geçerli 2 harfli kelimeler (ok, no, hi, go, ne vb.) beyaz listeye alınmalı; sadece harf içermeyen gürültüler elenmelidir.

---

### [BUG-03] Yapay Zeka Cevap Modunda Kısa Soruların Reddedilmesi (`[Yanitlanamadi: mesaj cok kisa]`)
* **Dosya & Satır:** [`buyedektir.py:4765-4775`](file:///d:/Whisper%20Live/buyedektir.py#L4765-L4775) (`/api/generate_ai_response`)
* **Kategori:** Mantıksal Hata / AI Yanıt Eksikliği
* **Mekanizma:**
  ```python
  if mode == 'answer':
      meaningful_chars = re.sub(r'[\s\.,!?;:\-\'"()\[\]{}…•·]', '', text)
      if len(meaningful_chars) < 4:
          return jsonify({
              'success': True,
              'turkish': '[Yanitlanamadi: mesaj cok kisa]', ...
  ```
* **Etki:**
  Doğu Asya dillerinde soru cümleleri çoğunlukla 1-3 karakterden ibarettir:
  * `"元気?"` (Genki? / İyi misin?) -> 2 karakter -> **Reddedilir!**
  * `"どう?"` (Dou? / Nasıl?) -> 2 karakter -> **Reddedilir!**
  * `"何?"` (Nani? / Ne?) -> 1 karakter -> **Reddedilir!**
  * `"好吗?"` (Hǎo ma? / İyi mi?) -> 2 karakter -> **Reddedilir!**
  * `"Why?"`, `"How?"`, `"Who?"` -> 3 karakter -> **Reddedilir!**
  Kullanıcı karşı tarafın sorduğu bu en doğal sorulara tıklayıp cevap önerisi istediğinde, sistem hiçbir öneri üretmeyip `[Yanitlanamadi: mesaj cok kisa]` uyarısı döndürür.
* **Önerilen Çözüm:** Karakter sayısı kontrolü dile duyarlı olmalı; CJK dilleri için sınır 1 karakter, Latin dilleri için en az 2 karakter olarak belirlenmelidir.

---

### [BUG-04] `transkribe.py` İçindeki `remove_overlap` Alt Dize Katliamı
* **Dosya & Satır:** [`transkribe.py:65-68`](file:///d:/Whisper%20Live/transkribe.py#L65-L68)
* **Kategori:** Algoritma Hatası / Veri Kaybı
* **Mekanizma:**
  ```python
  for prev_text in reversed(history):
      prev_lower = prev_text.lower().strip()
      if new_lower == prev_lower or new_lower in prev_lower:
          return ""
  ```
  `new_lower in prev_lower` şartı, kelime sınırı veya örtüşme mantığı olmadan standart bir alt dize (`substring`) aramasıdır.
* **Etki:**
  Yeni söylenen kısa bir kelime son 5 cümle içerisindeki herhangi bir kelimenin içinde geçiyorsa segment tamamen silinir.
  * *Örnek:* Önceki cümle: *"Bugün hava çok güzel ve dışarı çıkacağız."*  
    Sonraki segment: *"Ve"* veya *"Çık"* -> `new_lower in prev_lower` **True** olur ve transkripsiyondan sessizce silinir (`return ""`).
* **Önerilen Çözüm:** `new_lower in prev_lower` kaldırılmalı, yalnızca tam eşleşme veya n-gram örtüşme mantığı (`words[-n:] == new_words[:n]`) uygulanmalıdır.

---

## 2. AĞ, YAŞAM DÖNGÜSÜ VE ELEKTRON HATALARI

### [BUG-05] `launcher_whisper.py` Dosyasının Windows'ta `npm` Çalıştıramayıp Çökmesi
* **Dosya & Satır:** [`launcher_whisper.py:24-28`](file:///d:/Whisper%20Live/launcher_whisper.py#L24-L28)
* **Kategori:** İşletim Sistemi Uyumluluğu / Çökme
* **Mekanizma:**
  ```python
  subprocess.Popen(["npm", "start"], cwd=str(script_dir), ...)
  ```
  Windows üzerinde `npm`, bir ikili dosya (`.exe`) değil, bir toplu iş dosyasıdır (`npm.cmd`). `shell=True` olmadan çağrıldığında `CreateProcess` `npm` dosyasını bulamaz.
* **Etki:**
  `dist/` klasöründe derlenmiş exe bulunmadığında `python launcher_whisper.py` komutu `FileNotFoundError: [WinError 2] Sistem belirtilen dosyayı bulamıyor` hatasıyla çöker.
* **Önerilen Çözüm:** Komut Windows'ta `["npm.cmd", "start"]` şeklinde çağrılmalı veya `shell=True` parametresi eklenmelidir.

---

### [BUG-06] Sekme Kapanırken / F5 Yenilemesinde `beforeunload` Mikrofon Kapatma İsteğinin İptal Olması
* **Dosya & Satır:** [`templates/index.html:4583-4587`](file:///d:/Whisper%20Live/templates/index.html#L4583-L4587)
* **Kategori:** Yaşam Döngüsü / Donanım Kaynak Sızıntısı
* **Mekanizma:**
  ```javascript
  window.addEventListener('beforeunload', () => {
      if (altPttActive) finishAltPtt();
  });
  ```
  `finishAltPtt()`, standart asenkron `fetch('/api/ptt_mic', { method: 'POST' })` çağrısı yapmaktadır.
* **Etki:**
  Modern Chromium ve Electron motorları, sayfa kapanırken standart `fetch` isteklerini anında iptal eder (`aborted`). Kullanıcı Alt tuşuna basılı tutarken sayfayı kapatır veya F5 yaparsa, backend mikrofonun bırakıldığını öğrenemez ve 120 saniyelik emniyet süresi dolana kadar PyAudio akışını açık tutar.
* **Önerilen Çözüm:** `finishAltPtt` fetch çağrısına `{ keepalive: true }` eklenmeli veya `navigator.sendBeacon` API'si kullanılmalıdır.

---

### [BUG-07] DeepL Pro Lisanslı API Anahtarlarının Desteklenmemesi
* **Dosya & Satır:** [`buyedektir.py:1644, 1758`](file:///d:/Whisper%20Live/buyedektir.py#L1644)
* **Kategori:** Üçüncü Parti API Entegrasyonu
* **Mekanizma:**
  `DeepLTranslator` sınıfında `self.api_url = "https://api-free.deepl.com/v2/translate"` adresi sabit kodlanmıştır.
* **Etki:**
  Ücretli DeepL Pro anahtarları `:fx` eki taşımaz ve DeepL kuralları gereği yalnızca `https://api.deepl.com/v2/translate` adresini kabul eder. Free uç noktasına gönderildiğinde `403 Forbidden` döner; ücretli lisansa sahip kullanıcılar sistemi kullanamaz.
* **Önerilen Çözüm:** Anahtar kontrol edilerek `:fx` içermiyorsa `api.deepl.com` URL'sine otomatik geçiş yapılmalıdır.

---

### [BUG-08] `set_response_model` Fonksiyonunda Eski Model Takma Adlarının Kontrol Edilmemesi
* **Dosya & Satır:** [`buyedektir.py:1326-1335`](file:///d:/Whisper%20Live/buyedektir.py#L1326-L1335)
* **Kategori:** Durum Senkronizasyonu
* **Mekanizma:**
  `set_model` fonksiyonu `_legacy_aliases` kontrolü yaparken, `set_response_model` yalnızca doğrudan `allowed_models` kontrolü yapar.
* **Etki:**
  Kullanıcının tarayıcısında eski bir model adı (örn. `gpt-4o-mini`) kayıtlıysa, açılışta `loadAIConfig()` backend'e bu modeli gönderir; backend isteği reddeder (`False`) ve UI ile backend model seçimi uyuşmazlığa düşer.
* **Önerilen Çözüm:** `set_response_model` içerisine `if model_id in self._legacy_aliases: model_id = self.DEFAULT_MODEL` kontrolü eklenmelidir.

---

## 3. ARAYÜZ, DOM VE DURUM YÖNETİMİ HATALARI

### [BUG-09] PTT Mikrofon Sonuçlarına `data-transcription-id` Eklenmemesi (Arama ve Budama İflası)
* **Dosya & Satır:** [`templates/index.html:3070-3095`](file:///d:/Whisper%20Live/templates/index.html#L3070-L3095)
* **Kategori:** DOM Yönetimi / Arama Filtresi
* **Mekanizma:**
  Normal transkripsiyon öğelerine `data-transcription-id` eklenip `transcriptionTexts` haritasına işlenirken, `ptt_mic_result` ile gelen öğelere bu öznitelik atanmaz.
* **Etki:**
  1. `searchTranscriptions()` fonksiyonu `#transcriptionList .transcription-item[data-transcription-id]` seçicisini filtreler. PTT öğelerinde bu öznitelik olmadığı için arama filtresi bu öğeleri asla gizleyemez; alakasız aramalarda bile ekranda kalırlar.
  2. PTT transkriptleri backend `transcriber.transcriptions` listesine eklenmediğinden `searchFullTranscriptHistory()` geçmiş aramasında bulunamaz.
* **Önerilen Çözüm:** PTT sonucu oluşturulurken `item.dataset.transcriptionId` atanmalı ve `transcriptionTexts` içine kaydedilmelidir.

---

### [BUG-10] Sayfa Yenilemede ve Geri Yüklemede Sayaç Enflasyonu (`totalCount` Çifte Sayım)
* **Dosya & Satır:** [`templates/index.html:3744-3745`](file:///d:/Whisper%20Live/templates/index.html#L3744-L3745)
* **Kategori:** Arayüz Sayaç Hatası
* **Mekanizma:**
  `addTranscription(data, restoring = false)` fonksiyonunda `countEl.textContent = parseInt(countEl.textContent) + 1;` kodu `if (!restoring)` bloğunun dışında yer alır.
* **Etki:**
  Sayfa yüklendiğinde veya soket koptuğunda `hydrateTranscriptions()`, geçmiş transkriptleri `restoring = true` ile ekler. Her eski öğe için sayaç +1 artar. Aynı anda `updateStats()` da backend sayısını yazdığı için ekrandaki sayı iki katına çıkar; her yenilemede yapay olarak şişer.
* **Önerilen Çözüm:** Sayaç artırımı `if (!restoring)` şartı içerisine alınmalıdır.

---

### [BUG-11] Çeviri Ayrıştırmada Metin İçi İki Nokta Üst Üste (`:`) Kırpılması
* **Dosya & Satır:** [`templates/index.html:4966`](file:///d:/Whisper%20Live/templates/index.html#L4966) (`buildTranslationResultHtml`)
* **Kategori:** Metin İşleme Hatası
* **Mekanizma:**
  `targetText = normalized.replace(/^[^:]+:\s*/, '');` ifadesi satırın başından ilk `:` işaretine kadar olan her şeyi etiket sanıp siler.
* **Etki:**
  Çevrilen metin iki nokta içerdiğinde (örn. `"Note: Please bring water"`, `"Meeting: 10:00 AM"`, `"Warning: High voltage"`), metnin başındaki `"Note:"`, `"Meeting:"` veya `"Warning:"` kelimesi silinir ve kullanıcı eksik çeviri görür.
* **Önerilen Çözüm:** Yalnızca bilinen sistem ön-ekleri (örn. `/^(?:Line\s*\d+|Hedef)\s*:\s*/i`) silinmelidir.

---

### [BUG-12] Otomatik Çeviride Paralel Çifte OpenAI İsteği Gönderilmesi
* **Dosya & Satır:** [`templates/index.html:3750-3757`](file:///d:/Whisper%20Live/templates/index.html#L3750-L3757) ve [`buyedektir.py:3858-3869`](file:///d:/Whisper%20Live/buyedektir.py#L3858-L3869)
* **Kategori:** Mimari Çakışma / Fazla Maliyet
* **Mekanizma:**
  Hem sol menüdeki çeviri anahtarı hem de "Otomatik Çeviri" kutusu işaretlendiğinde; backend `_translate_async` çalıştırırken, frontend `addTranscription` da eşzamanlı olarak `POST /api/generate_ai_response` (`mode: 'translate_dual'`) çağrısı yapar.
* **Etki:**
  Aynı transkript için OpenAI'a iki ayrı istek gider; API maliyeti ikiye katlanır ve ekranda iki ayrı çeviri kutusu oluşur.
* **Önerilen Çözüm:** Frontend'deki HTTP çeviri çağrısı kaldırılmalı; çeviri işlemi yalnızca backend soket akışı üzerinden yürütülmelidir.

---

## 4. EŞZAMANLILIK VE THREADING RİSKLERİ

### [BUG-13] `MicRecorder.stop_stream()` İçinde PortAudio C-Pointer Yarış Durumu
* **Dosya & Satır:** [`buyedektir.py:2165-2178`](file:///d:/Whisper%20Live/buyedektir.py#L2165-L2178)
* **Kategori:** Thread Güvenliği / Bellek İhlali
* **Mekanizma:**
  `stop_stream()`, hem arka plan kayıt iş parçacığı (`_record` içerisindeki `finally` bloğu) hem de Flask HTTP iş parçacığı (`stop()`) tarafından aynı anda çağrılabilir. `self.stream` üzerinde hiçbir kilit yoktur.
* **Etki:**
  İki iş parçacığı aynı anda `Pa_CloseStream` PortAudio C fonksiyonuna eriştiğinde Windows üzerinde bellek erişim ihlali (Access Violation) veya PortAudio çökmesi riski doğar.
* **Önerilen Çözüm:** `self._stream_lock = threading.Lock()` eklenerek akış kapatma adımları kilit altına alınmalıdır.

---

### [BUG-14] Kanji Ağırlıklı Japonca Konuşmaların Çince (`zh`) Algılanması
* **Dosya & Satır:** [`buyedektir.py:2681-2690`](file:///d:/Whisper%20Live/buyedektir.py#L2681-L2690) (`_detect_script_lang`)
* **Kategori:** Dil Tespiti / Fonetik Bozulma
* **Mekanizma:**
  ```python
  if dominant == 'ja_kana':
      return 'ja'
  if dominant == 'zh_han':
      return 'zh'
  ```
  Japonca bir cümlede Kanji sayısı Hiragana/Katakana sayısından fazla olduğunda (örn. `"東京大学法学部卒業です"` - 9 Kanji, 2 Kana), `dominant` değişkeni `zh_han` olur.
* **Etki:**
  Çince'de asla Kana bulunamaz; ancak Kanji sayısı fazla olduğu için sistem Japonca cümleyi Çince (`zh`) olarak etiketler. Çeviri ve Türkçe telaffuz kuralları Çince Pinyin kurallarına döner ve okunuş tamamen bozulur.
* **Önerilen Çözüm:** Metinde en az 1 adet dahi Kana karakteri varsa (`counts['ja_kana'] > 0`), Kanji sayısına bakılmaksızın dil doğrudan `'ja'` olarak belirlenmelidir.

---

### [BUG-15] `transkribe.py` Arka Plan İş Parçacığından Tkinter GUI'ye Güvensiz Erişim
* **Dosya & Satır:** [`transkribe.py:259-264`](file:///d:/Whisper%20Live/transkribe.py#L259-L264) (`_log`)
* **Kategori:** GUI Thread Güvenliği
* **Mekanizma:**
  `_log` fonksiyonu arka planda çalışan `_run` iş parçacığından doğrudan `self.log.insert(...)`, `self.log.see(...)` çağrıları yapmaktadır.
* **Etki:**
  Tkinter ana döngüsü iş parçacığı güvenli (thread-safe) değildir. Arka plandan doğrudan yazılması Windows'ta Tcl kilitlenmelerine veya rastgele `Fatal Python error: PyEval_SaveThread: NULL tstate` çökmelerine sebep olur.
* **Önerilen Çözüm:** `_log` fonksiyonu `self.after(0, lambda: ...)` yapısına dönüştürülmelidir.

---

### [BUG-16] Konuşmacılar Sıfırlandığında HuggingFace Token'ının Kalıcı Olarak Silinmesi
* **Dosya & Satır:** [`buyedektir.py:2027-2036`](file:///d:/Whisper%20Live/buyedektir.py#L2027-L2036) (`SpeakerDiarizer.reset()`)
* **Kategori:** Kritik Mantıksal Hata / Kalıcı Konfigürasyon Kaybı
* **Mekanizma:**
  `buyedektir.py` içerisinde `SpeakerDiarizer.save_profiles()` hem konuşmacı adlarını hem de kullanıcının kaydettiği HuggingFace API anahtarını (`hf_token`) aynı `speaker_profiles.json` dosyasına yazmaktadır:
  ```python
  with open(tmp_path, 'w', encoding='utf-8') as f:
      json.dump({'names': self.speaker_names, 'hf_token': self.hf_token}, f)
  ```
  Ancak kullanıcı arayüzdeki "Konuşmacıları Sıfırla" butonuna bastığında çalışan `reset()` fonksiyonu dosyayı doğrudan silmektedir:
  ```python
  def reset(self):
      with self._profile_lock:
          self._profile_generation += 1
          self.speaker_names = {}
          if os.path.exists(self.profile_file):
              os.remove(self.profile_file)
  ```
* **Etki:**
  `os.remove(self.profile_file)` çağrısı `speaker_profiles.json` dosyasını diskten tamamen siler. Kullanıcı sadece konuşmacı isimlerini veya oturum konuşma geçmişini temizlemek istemiştir; fakat dosya silindiği için kaydedilmiş olan `hf_token` da diskten tamamen yok edilir! Uygulama yeniden başlatıldığında HuggingFace token'ı bulunamaz (`None` olur) ve Konuşmacı Tanıma (Pyannote) kalıcı olarak devre dışı kalır.
* **Önerilen Çözüm:** Dosyayı silmek yerine `self.save_profiles()` çağrılarak `speaker_names = {}` yapılmalı, ancak mevcut `self.hf_token` korunarak dosyaya geri yazılmalıdır.

---

### [BUG-17] `load_model` Sırasında Eski Modelin VRAM'den Boşaltılmadan Yenisinin Yüklenmesi ve Sessizce CPU'ya Düşme
* **Dosya & Satır:** [`buyedektir.py:2917-2945`](file:///d:/Whisper%20Live/buyedektir.py#L2917-L2945) (`_load_model_unlocked`)
* **Kategori:** Kaynak Yönetimi / Performans Çöküşü
* **Mekanizma:**
  Kullanıcı arayüzden model değiştirdiğinde (örn. `medium` modelden `large-v3` modeline):
  ```python
  if use_gpu:
      new_model = WhisperModel(model_name, device="cuda", ...)
  # ...
  with self._model_lock:
      old_model = self.current_model
      self.current_model = new_model
  del old_model
  ```
  `new_model` GPU üzerinde ayrılırken, eski `self.current_model` hala GPU belleğinde tutulmaktadır. İki model aynı anda VRAM'de yer kaplar.
* **Etki:**
  4 GB veya 6 GB VRAM'e sahip ekran kartlarında (GTX 1650/1660, RTX 3050, RTX 2060 vb.), iki model aynı anda belleğe sığmadığı için satır 2917'de `CUDA out of memory` (OOM) hatası patlar. Kod hemen satır 2925'teki `except Exception: use_gpu = False` bloğuna düşer ve modeli sessizce **CPU int8** modunda yükler! Kullanıcı güçlü bir ekran kartına sahip olmasına ve GPU seçmesine rağmen sistem uyarı vermeden CPU'ya düşer ve transkripsiyon gecikmesi 10 katına çıkar.
* **Önerilen Çözüm:** Yeni model yüklenmeden önce `self.current_model = None` yapılmalı, `gc.collect()` çağrılmalı, varsa `ctranslate2` CUDA bellek havuzları temizlenmeli ve ardından yeni model yüklenmelidir.

---

### [BUG-18] `stop_capture` ile `_transcribe_audio` Arasındaki Mantıksal Çelişki ve Son Konuşmanın Çöpe Atılması
* **Dosya & Satır:** [`buyedektir.py:3201-3215`](file:///d:/Whisper%20Live/buyedektir.py#L3201-L3215), [`buyedektir.py:3666`](file:///d:/Whisper%20Live/buyedektir.py#L3666) ve [`buyedektir.py:3721-3724`](file:///d:/Whisper%20Live/buyedektir.py#L3721-L3724)
* **Kategori:** Concurrency / Veri Kaybı
* **Mekanizma:**
  Transkripsiyon iş parçacığı döngüsü şu şekilde kurulmuştur:
  ```python
  while (self.is_running or not self.audio_queue.empty()) and self._session_id == session_id:
  ```
  Buradaki `or not self.audio_queue.empty()` kontrolünün amacı: Kullanıcı "Durdur" dediğinde kuyrukta bekleyen son cümlenin de çözümlenerek kullanıcıya teslim edilmesidir.  
  Ancak `stop_capture` çağrıldığında anında:
  ```python
  self.is_running = False
  self._result_generation += 1
  ```
  yapılır. `_transcribe_audio` kuyruktan aldığı son ses parçasını Whisper ile GPU'da saniyelerce transkribe eder. Fakat işlem bittiğinde hemen aşağıdaki kontrol devreye girer:
  ```python
  if (session_id != self._session_id
          or result_generation != self._result_generation
          or not self.is_running):
      continue
  ```
* **Etki:**
  `self.is_running` artık `False` olduğu ve `result_generation` arttığı için, GPU'da büyük bir emekle transkribe edilen son konuşma `continue` ile doğrudan **çöpe atılır**! Ne UI'ya basılır ne de dosyaya kaydedilir. Kullanıcının kaydı durdurmadan hemen önce söylediği son cümle tamamen kaybolur.
* **Önerilen Çözüm:** `stop_capture` esnasında normal durdurma ile zorla sıfırlama (clear/reset) ayrılmalıdır. Normal durdurmada kuyruktaki son iş parçası için transkripsiyon taahhüdüne (`commit`) izin verilmeli, yalnızca zorla sıfırlamada atılmalıdır.

---

### [BUG-19] `_detect_script_lang` İçinde Yunanca (`el`) Alfabesinin Bulunmaması ve Kiril Alfabesinin Zorla Rusça Yapılması
* **Dosya & Satır:** [`buyedektir.py:2656-2696`](file:///d:/Whisper%20Live/buyedektir.py#L2656-L2696) (`_detect_script_lang`)
* **Kategori:** Dil Tespiti Eksikliği
* **Mekanizma:**
  Uygulamanın arayüzünde Yunanca (`el`) resmi olarak desteklenen diller arasındadır. Ancak alfabe tespit fonksiyonu `ranges` sözlüğünde Yunanca (`0x0370 - 0x03FF`) karakter aralığı tanımlanmamıştır. Ayrıca Kiril alfabesi görüldüğünde metin koşulsuz olarak `'ru'` (Rusça) yapılmaktadır:
  ```python
  if dominant == 'cyr':
      return 'ru'
  ```
* **Etki:**
  1. Otomatik modda Yunanca konuşulduğunda alfabe tabanlı dil tespiti çalışmaz, metin başka bir dil sanılarak yanlış fonetik kurallara maruz kalır.
  2. Ukraynaca, Bulgarca veya Kazakça konuşulduğunda sistem dili zorla Rusça telaffuz motoruna sokar ve okunuş bozulur.
* **Önerilen Çözüm:** `ranges` içine `'el': (0x0370, 0x03FF)` eklenmeli; Kiril için Whisper dil olasılığı (`info.language`) korunmalıdır.

---

### [BUG-20] `update_speaker_name` Fonksiyonunun Mevcut Transkript Kayıtlarını ve DOM Rozetlerini Güncellememesi
* **Dosya & Satır:** [`buyedektir.py:2020-2025`](file:///d:/Whisper%20Live/buyedektir.py#L2020-L2025) ve [`templates/index.html:2544-2555`](file:///d:/Whisper%20Live/templates/index.html#L2544-L2555)
* **Kategori:** UI Senkronizasyonu / Veri Tutarsızlığı
* **Mekanizma:**
  Kullanıcı arayüzde bir konuşmacının adını güncellediğinde (örn. "Konuşmacı 1" -> "Ahmet Bey"):
  1. Backend sadece `self.speaker_names[speaker_id]` sözlüğünü günceller; `transcriber.transcriptions` hafızasındaki geçmiş konuşmalarda `speaker_name` "Konuşmacı 1" olarak kalır.
  2. Backend hiçbir WebSocket olayı yaymaz.
  3. Frontend `updateSpeakerName` fonksiyonu `#transcriptionList` içindeki DOM elemanlarını güncellemez.
* **Etki:**
  Konuşmacı adı değiştirildikten sonra bile ekrandaki mevcut konuşma balonları eski isimle ("Konuşmacı 1") kalmaya devam eder. Kullanıcı "Kayıtları İndir" dediğinde veya geçmişte arama yaptığında eski kayıtların tamamında eski isim görünür.
* **Önerilen Çözüm:** Backend'de `transcriptions` listesindeki ilgili konuşmacıya ait tüm kayıtlar güncellenmeli, soket üzerinden `speaker_updated` olayı yayınlanmalı ve frontend DOM'daki rozet metinlerini anında yenilemelidir.

---

### [BUG-21] `saveHFToken` Fonksiyonunda Token'ı Temizleme / Sıfırlama İmkânının Olmaması
* **Dosya & Satır:** [`templates/index.html:2370-2375`](file:///d:/Whisper%20Live/templates/index.html#L2370-L2375)
* **Kategori:** UI / Ayar Yönetimi Hatası
* **Mekanizma:**
  ```javascript
  function saveHFToken(token) {
      if (token) {
          localStorage.setItem('hfToken', token);
          // ... fetch('/api/hf_token') ...
      }
  }
  ```
* **Etki:**
  Kullanıcı input kutusunu temizleyip kaydetmek istediğinde (`token === ''`), `if (token)` şartı sağlanmadığı için hiçbir işlem yapılmaz. `localStorage`'daki eski token silinmez, backend'e bildirilmez. Kullanıcı arayüzden token'ı asla kaldıramaz.
* **Önerilen Çözüm:** `if (token)` yerine `if (!token)` durumu ele alınmalı; `localStorage.removeItem('hfToken')` çalıştırılmalı ve backend'e boş token gönderilerek yapılandırma sıfırlanmalıdır.

---

### [BUG-22] `downloadTranscriptions` İçinde `URL.revokeObjectURL(url)` Senkron Çağrısının İndirmeyi İptal Edebilmesi
* **Dosya & Satır:** [`templates/index.html:3887-3892`](file:///d:/Whisper%20Live/templates/index.html#L3887-L3892)
* **Kategori:** Tarayıcı API Zamanlaması / İndirme Hatası
* **Mekanizma:**
  ```javascript
  a.click();
  URL.revokeObjectURL(url);
  ```
* **Etki:**
  Chromium tabanlı tarayıcılarda `a.click()` indirme akışını asenkron olarak başlatır. Hemen alt satırda URL bellekten serbest bırakıldığında, özellikle CPU yoğun anlarda veya dosya boyutu büyükken tarayıcı "Ağ hatası / Başarısız" hatası vererek indirmeyi keser.
* **Önerilen Çözüm:** `setTimeout(() => URL.revokeObjectURL(url), 1000);` ile nesnenin serbest bırakılması geciktirilmelidir.

---

### [BUG-23] `pruneTranscriptionList` İçinde `seenTranscriptionIds` Set'inin Hiç Temizlenmemesi
* **Dosya & Satır:** [`templates/index.html:3506-3517`](file:///d:/Whisper%20Live/templates/index.html#L3506-L3517)
* **Kategori:** Bellek Sızıntısı (Memory Leak)
* **Mekanizma:**
  DOM öğe sayısı 100'ü aştığında eski transkriptler DOM'dan ve `transcriptionTexts` tablosundan silinmektedir. Ancak `seenTranscriptionIds` Set'inden silinmemektedir.
* **Etki:**
  Saatlerce açık kalan canlı çeviri oturumlarında binlerce kimlik `seenTranscriptionIds` setinde birikmeye devam eder. DOM temizlense bile bellek tüketimi sürekli artar.
* **Önerilen Çözüm:** `pruneTranscriptionList` içinde silinen öğenin id'si `seenTranscriptionIds.delete(removedId)` ile setten de düşülmelidir.

---

### [BUG-24] `_process_mic_audio` İçerisinde `conversation_turns.append` Çağrısının Kilitsiz Yapılması
* **Dosya & Satır:** [`buyedektir.py:4531-4535`](file:///d:/Whisper%20Live/buyedektir.py#L4531-L4535) (`_process_mic_audio`)
* **Kategori:** Eşzamanlılık / Veri Yarışması (Race Condition)
* **Mekanizma:**
  `buyedektir.py` genelinde `conversation_turns` erişimleri (satır 3771, 4660, 2521) `self._lifecycle_lock` ile korunmaktadır. Fakat arka planda mikrofon sesini işleyen `_process_mic_audio` fonksiyonunda:
  ```python
  if translation and translation != "[Çeviri başarısız]":
      transcriber.conversation_turns.append({
          'role': 'me', 'text': translation, 'turkish': full_text,
      })
  ```
  çağrısı hiçbir kilit alınmadan doğrudan yürütülmektedir.
* **Etki:**
  Alt-PTT ile mikrofondan konuşulduğu sırada eşzamanlı olarak `get_conversation_snapshot()` veya `_transcribe_audio` çalışırsa paylaşılan `deque` üzerinde kilitlenmesiz eşzamanlı değişiklik meydana gelir.
* **Önerilen Çözüm:** Ekleme işlemi `with transcriber._lifecycle_lock:` bloğu içine alınmalıdır.

---

### [BUG-25] `_resample_filter` İçinde Eşit Örnekleme Oranlarında Nyquist Frekans Çökmesi (`ValueError`)
* **Dosya & Satır:** [`buyedektir.py:166-168`](file:///d:/Whisper%20Live/buyedektir.py#L166-L168) ve [`buyedektir.py:173-176`](file:///d:/Whisper%20Live/buyedektir.py#L173-L176)
* **Kategori:** DSP / Matematiksel Çökme
* **Mekanizma:**
  ```python
  @lru_cache(maxsize=8)
  def _resample_filter(up, down):
      max_rate = max(up, down)
      return signal.firwin(2 * 10 * max_rate + 1, 1.0 / max_rate, window=('kaiser', 5.0))
  ```
  `up == down` olduğunda (örneğin kaynak ve hedef örnekleme oranları eşitse), `max_rate = 1` olur. `1.0 / max_rate = 1.0` değeri `signal.firwin`'e kesim frekansı (cutoff) olarak verilir. Ancak Scipy `firwin`, kesim frekansının Nyquist frekansından (`fs/2 = 1.0`) kesinlikle küçük olmasını zorunlu kılar.
* **Etki:**
  `1.0 >= 1.0` olduğu için Scipy anında şu ölümcül istisnayı fırlatır:
  `ValueError: Invalid cutoff frequency: frequencies must be greater than 0 and less than fs/2.`
  Ayrıca 11025 Hz gibi örnekleme oranlarında 30ms'lik pencere 479 örneğe düşer ve WebRTC VAD 480 örnek şartı koştuğu için VAD tamamen çöker.
* **Önerilen Çözüm:** `_resample_int16` başında `if src_rate == dst_rate: return audio` kısa devresi eklenmeli; VAD için üretilen dizi boyutu tam 480 örneğe tamamlanmalıdır (`pad`).

---

### [BUG-26] Alt-PTT Tuş Kombinasyonu Kontrolü Olmaması ve Her Alt+Tab / Alt+F4 Basışında Hayalet Kayıt Başlatılması
* **Dosya & Satır:** [`templates/index.html:4545-4560`](file:///d:/Whisper%20Live/templates/index.html#L4545-L4560)
* **Kategori:** Kullanıcı Arayüzü / Gereksiz Ağ ve API Maliyeti
* **Mekanizma:**
  Ctrl-PTT implementasyonunda (satır 4458-4482) `if (e.key !== 'Control' && e.ctrlKey)` kontrolü ve 150ms gecikme sayacı (`pttPendingTimer`) bulunurken, Alt-PTT için hiçbir gecikme sayacı veya başka tuş kombinasyonu kontrolü yapılmamıştır:
  ```javascript
  document.addEventListener('keydown', (e) => {
      if (e.key !== 'Alt') return;
      if (altPttHeld) { e.preventDefault(); return; }
      altPttHeld = true;
      queueAltPtt(true);
  });
  ```
* **Etki:**
  Kullanıcı Windows'ta başka bir uygulamaya geçmek için `Alt+Tab` bastığında veya pencereyi kapatmak için `Alt+F4` bastığında, Alt tuşuna basıldığı ilk milisaniyede derhal `active: true` isteği fırlar ve mikrofon kaydı başlar. Sekme odağı kaybettiğinde (`blur`) mikrofon alelacele kapatılır ve yarım saniyelik boş gürültü Whisper'a ve OpenAI'a gönderilir. Her pencere değişiminde gereksiz API maliyeti ve hayalet transkript oluşur.
* **Önerilen Çözüm:** Ctrl-PTT'de olduğu gibi 150ms'lik bir gecikme sayacı konulmalı; Alt basılıyken Tab veya F4 gibi başka bir tuşa basılırsa PTT derhal iptal edilmelidir.

---

### [BUG-27] `get_context_prompt()` Fonksiyonunun Kelimeleri ve Karakterleri Ortadan Rastgele Kesmesi
* **Dosya & Satır:** [`buyedektir.py:2590-2591`](file:///d:/Whisper%20Live/buyedektir.py#L2590-L2591)
* **Kategori:** Dil Modeli Şartlandırma / Halüsinasyon Tetikleyici
* **Mekanizma:**
  ```python
  if len(context_text) > 200:
      context_text = context_text[-200:]
  ```
  Metin kelime sınırına bakılmaksızın son 200 karakterden dilimlenmektedir.
* **Etki:**
  Whisper'ın `initial_prompt` parametresine yarım kelimeler (örn. "understanding" yerine "erstanding") veya çok baytlı alfabelerde parçalanmış anlamsız heceler beslenir. Whisper kod çözücüsü (decoder) bu yarım kelimeleri tamamlamaya çalışarak gerçek konuşmanın ilk kelimelerinde telafisi zor halüsinasyonlar ve tanıma hataları üretir.
* **Önerilen Çözüm:** Dilimleme işlemi kelime sınırından (`context_text.split()`) yapılmalı, hiçbir zaman kelime ortasından kesilmemelidir.

---

### [BUG-28] 0.5 Saniyeden Kısa Cümlelerin VAD Tarafından Sessizce Çöpe Atılması
* **Dosya & Satır:** [`buyedektir.py:3545-3546`](file:///d:/Whisper%20Live/buyedektir.py#L3545-L3546) (`_capture_audio`)
* **Kategori:** Ses Algılama / Veri Kaybı
* **Mekanizma:**
  ```python
  total_duration = len(audio_buffer) * chunk_seconds
  if total_duration > 0.5:
      full_audio = np.concatenate(audio_buffer)
      # ... kuyruga ekle ...
  ```
  Buffer süresi 0.5 saniyeden kısa ise ses kuyruğa konulmaz; doğrudan `audio_buffer = []` yapılarak silinir.
* **Etki:**
  Doğal konuşmada "No", "Hi", "Ja", "Oui", "Ne?" gibi kısa onay ve tepki kelimeleri 0.2 - 0.4 saniye sürer. BUG-02 ile birleştiğinde, bu kelimeler iki katmanlı bir engelle karşılaşır: Önce 0.5 saniye altı olduğu için ses kartı kuyruğundan silinir; tampon süresi uzasa bile bu kez halüsinasyon filtresi tarafından yok edilir. Kullanıcı bu kelimeleri asla transkribe ettiremez.
* **Önerilen Çözüm:** Süre eşiği 0.25 saniyeye indirilmeli veya VAD konuşma güveni yüksekse süreye bakılmaksızın iletilmelidir.

---

### [BUG-29] `main_helpers.js` İçindeki `isOwnedWhisperBackend` Fonksiyonunun Windows 8.3 Kısa Dosya Yollarında Hatalı Kapanması
* **Dosya & Satır:** [`main.js:111-121`](file:///d:/Whisper%20Live/main.js#L111-L121) ve [`main_helpers.js:9-14`](file:///d:/Whisper%20Live/main_helpers.js#L9-L14)
* **Kategori:** Başlatıcı Hatası / Kritik Başarısızlık
* **Mekanizma:**
  Electron ana sürecinde port 5000 temizliği yapılırken PowerShell üzerinden komut satırı çekilir:
  ```javascript
  function isOwnedWhisperBackend(commandLine, appDir) {
      const normalized = normalizeCommandLine(commandLine);
      const expectedScript = normalizeCommandLine(path.resolve(appDir, 'buyedektir.py'));
      return normalized.includes('--whisper-electron-child')
          && normalized.includes(expectedScript);
  }
  ```
* **Etki:**
  Windows WMI komut satırında dizin adı kısa formatta (örn. `d:\whispe~1\buyedektir.py`) yer alıyorsa veya kullanıcı adında boşluk olup 8.3 formatı kullanılıyorsa, `normalized.includes(expectedScript)` eşleşmesi başarısız olur (`false`). Electron, portu tutan sürecin Whisper'a ait olmadığını varsayar (`safeToStart = false`), ekrana "Port Kullanımda" diyaloğu basar ve uygulamayı kapatır (`app.quit()`).
* **Önerilen Çözüm:** Eşleşmede tam yol yerine script adı (`buyedektir.py`) ve çocuk süreç bayrağı (`--whisper-electron-child`) temel alınmalı veya `fs.realpath` ile normalize edilmelidir.

---

### [BUG-30] `_apply_exact_pronunciation_override` Fonksiyonunun Cümle İçi Terimleri Yoksayması
* **Dosya & Satır:** [`buyedektir.py:615-619`](file:///d:/Whisper%20Live/buyedektir.py#L615-L619)
* **Kategori:** Sözlük ve Telaffuz Bozukluğu
* **Mekanizma:**
  ```python
  target = re.sub(r'[\s\.,!?;:…]+', '', str(entry.get('target', '') or '')).casefold()
  if preferred and target and target == normalized_translation:
      return _normalize_turkish_pronunciation(preferred, lang)
  ```
* **Etki:**
  Kullanıcı sözlüğe bir terim eklediğinde, override mantığı YALNIZCA üretilen tüm cümlenin o tek terime eşit olduğu durumlarda çalışır. Yapay zekanın önerdiği cümle o kelimeyi içeriyorsa (örn. terim "arigatou", öneri "arigatou gozaimasu"), sözlükteki özel Türkçe okunuş kuralı asla uygulanmaz ve genel modele düşer.
* **Önerilen Çözüm:** Tam eşitlik yerine cümle içi terim ikamesi (regex word-boundary replacement) uygulanmalıdır.

---

## SONUÇ VE EYLEM PLANI ÖNERİSİ

Yapılan bu derin denetim sonucunda tespit edilen 30 hata;
1. **Veri Kaybı & Halüsinasyon Sansürü:** Kısa yanıtların ("OK", "はい") ve 0.5s altı seslerin silinmesi (BUG-02, BUG-03, BUG-04, BUG-18, BUG-28).
2. **Kritik Mantıksal Hatalar:** Alt-PTT dil tersliği (BUG-01), Reset ile HuggingFace token'ının kalıcı silinmesi (BUG-16), VRAM sızıntısıyla sessizce CPU'ya düşme (BUG-17).
3. **Sistem Kararlılığı ve Donma:** Eşit frekanslarda DSP çökmesi (BUG-25), Alt+Tab ile sürekli hayalet kayıt başlatılması (BUG-26), Windows 8.3 yollarında açılışta kapanma (BUG-29).

kategorilerinde uygulamanın ana vaadi olan "diller arası akıcı ve sorunsuz canlı iletişim" özelliğini doğrudan etkilemektedir.
Kullanıcı direktifi doğrultusunda **kod tabanında hiçbir değişiklik yapılmamış**, tüm bulgular analiz edilerek bu rapora kaydedilmiştir.
