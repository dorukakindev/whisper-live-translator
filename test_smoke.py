#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kalici regresyon paketi (pytest GEREKTIRMEZ).

Calistir:  python test_smoke.py
Cikis kodu: hepsi gecerse 0, bir test patlarsa 1.

Kapsam:
  1. 15 dil okunus tablosu (_normalize_turkish_pronunciation)
  2. Halusinasyon filtresi (cok dilli)
  3. Answer-mode sozlesmesi (paralel cevap + ai_options_partial streaming + dedup)
  4. Ayar sinirlari (update_settings: inf/nan/absurt reddi)
  5. Kurtarma parser'i (_salvage_answer_options)
  8-9. Ses tamponu ust sinirlari (MAX_UTTERANCE_S / MAX_PTT_S) — gercek
       _capture_audio thread'i sahte PyAudio ile calistirilarak dogrulanir
       (buyedektir.log'da kayitli gercek 29 GiB cokmesinin regresyon testi)

Not: import ~5-40sn surer (torch yok ama faster-whisper var). Normaldir.
"""
import io
import json
import logging
import os
import queue as _queue_mod
import subprocess
import sys
import tempfile
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
# Regresyon paketi gercek .env veya konusmaci profilini okumaz; tum state gecici
# dizindedir ve canli API dogrulamasi kapatilir.
_import_state = tempfile.TemporaryDirectory(prefix='whisper-smoke-')
os.environ['WHISPER_SKIP_DOTENV'] = '1'
os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = os.path.join(
    _import_state.name, 'speaker_profiles.json'
)
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'

print("buyedektir import ediliyor (yavas olabilir)...")
import buyedektir

_failures = []


def check(cond, msg):
    if not cond:
        _failures.append(msg)
        print(f"  FARK: {msg}")


def make_client():
    client = buyedektir.app.test_client()
    client.environ_base['HTTP_X_WHISPER_TOKEN'] = buyedektir.APP_TOKEN
    return client


# ── 1. Okunus tablosu ──────────────────────────────────────────────
def test_pronunciation():
    N = buyedektir._normalize_turkish_pronunciation
    cases = [
        # (dil, girdi, beklenen)
        ('ja', 'hon wo yomimasu', 'hon-o yomimas'),   # wo->o edat baglanma
        ('ja', 'kore wa', 'kore-va'),
        ('ja', 'hajimemashite', 'hacimemaşte'),       # mashite devoicing
        ('ja', 'arigatou gozaimashita', 'arigatoo gozaimaşta'),  # mashita korundu
        ('ja', 'watashi wa ni juu go sai desu', 'vataşi-va ni-cuu go sai-des'),  # 'ni' SAYI (20), edat degil
        ('ja', 'gakkou ni ikimasu', 'gakkoo-ni ikimas'),         # 'ni' GERCEK edat -> baglanir
        ('zh', 'nı↘↗hao↘↗', 'nıhao'),                 # ton oku temizligi
        ('zh', 'nıhao / voşı', 'nıhao / voşı'),        # slash korunur
        ('es', 'mucho', 'muço'),                        # ch->ç
        ('es', 'casa', 'kasa'),                         # sert c->k
        ('ar', 'shukran', 'şukran'),                    # sh->ş
        ('ar', 'el shams', 'eşşams'),                   # gunes harfi asimilasyonu
        ('ru', 'что это', 'şto eto'),                   # düzensiz что->şto
        ('ru', 'почта', 'poçta'),                       # 'чта' etkilenmez
        ('it', 'giorno', 'corno'),                      # yumusak g
        ('it', 'ciao', 'çao'),
        ('pt', 'chamo', 'şamu'),
        ('de', 'ich', 'ih'),
        ('el', 'ευχαριστώ', 'efharisto'),               # ευ sessizden once ef
        ('el', 'εύκολο', 'efkolo'),                     # aksanli diftong
        ('ka', 'მადლობა', 'madloba'),
        ('sk', 'žena', 'jena'),
        ('sk', 'cena', 'tsena'),
        ('da', 'æble', 'eble'),
        ('sv', 'sjö', 'şö'),
        ('ko', 'annyeonghaseyo', 'annyonghaseyo'),
        ('fr', 'bonjur', 'bonjur'),                     # passthrough (agresif donusum yok)
        ('ja', 'Itai', 'itai'),                         # buyuk I -> i (dotless 'ı' DEGIL)
        ('ru', 'Igor', 'igor'),                         # generic fallback'te de buyuk I -> i
        ('ja', 'İyi', 'iyi'),                           # noktali İ -> i (hala dogru)
        ('tr', 'merhaba', ''),                          # Turkce -> okunus bos
    ]
    for lang, inp, exp in cases:
        out = N(inp, lang)
        check(out == exp, f"okunus {lang} {inp!r} -> {out!r} (beklenen {exp!r})")


# ── 2. Halusinasyon filtresi ───────────────────────────────────────
def test_hallucination():
    H = buyedektir.transcriber._is_likely_hallucination
    positives = [
        'ご視聴ありがとうございました。',
        'チャンネル登録お願いします',
        'Продолжение следует...',
        'İzlediğiniz için teşekkürler.',
        'Thank you.',
        '구독과 좋아요 부탁드립니다',
        'Subtítulos realizados por la comunidad de Amara.org',
        # initial_prompt yankisi (B6): tam metin ve tek cumle parcasi
        'Bu Türkçe bir konuşmadır. Lütfen sadece Türkçe yazıya dökün.',
        'Lütfen sadece Türkçe yazıya dökün.',
        'これは日本語の会話です。日本語のみで文字起こしをしてください。',
        # CJK tekrar dongusu (B7): boslukyok, 4+ ardisik tekrar, len(cleaned)>=12 esigini gecmeli
        'ありがとうありがとうありがとうありがとう',
        '你好你好你好你好你好你好',  # 6x "你好" = 12 karakter
    ]
    for p in positives:
        check(H(p) is True, f"halusinasyon YAKALANMADI: {p!r}")
    negatives = [
        'こんにちは、今日は天気がいいですね。仕事は順調ですか？',
        'Merhaba, bugün nasılsın? İşler yolunda mı?',
        'ありがとうございます、とても助かりました',
        'Gracias por la ayuda de ayer, fue muy útil para mi trabajo',
        'Привет, как у тебя дела сегодня? Что нового на работе?',
        # dogal kisa tekrar (2x) CJK tekrar filtresini yanlis tetiklememeli
        'はいはい、わかりました',
    ]
    for n in negatives:
        check(H(n) is False, f"gercek konusma YANLIS FILTRELENDI: {n!r}")


# ── 3. Answer-mode sozlesmesi (paralel + streaming + dedup) ─────────
def test_answer_contract():
    app = buyedektir.app
    client = make_client()
    sio = buyedektir.socketio.test_client(
        app, auth={'token': buyedektir.APP_TOKEN}
    )
    sio.get_received()  # baglanti olaylarini temizle
    responder = buyedektir.transcriber.openai_responder
    saved_key = responder.api_key
    saved_fn = responder.answer_question
    responder.api_key = 'test-key'
    parallel_barrier = threading.Barrier(2)
    answer_threads = set()
    answer_threads_lock = threading.Lock()

    def fake(text, **kw):
        with answer_threads_lock:
            answer_threads.add(threading.get_ident())
        parallel_barrier.wait(timeout=2)
        if 'kisa olumlu' in text:  # 1. paralel cagri (2 secenek)
            opts = [
                {'translation': 'Hai sou desu', 'turkish': 'Evet oyle', 'romanized': 'hay soo des'},
                {'translation': 'Hontou?', 'turkish': 'Gercekten mi?', 'romanized': 'hontoo'},
            ]
        else:  # 2. paralel cagri (2 secenek; biri tekrar -> dedup testi)
            opts = [
                {'translation': 'Hai sou desu', 'turkish': 'Evet oyle', 'romanized': 'hay soo des'},  # tekrar (dedup test)
                {'translation': 'Ganbatte', 'turkish': 'Kolay gelsin', 'romanized': 'ganbatte'},
            ]
        return {'response': json.dumps({'options': opts, 'detected_lang': 'ja'})}
    responder.answer_question = fake

    try:
        # request_id ILE: kismi olaylar gelmeli, dedup uygulanmali
        r = client.post('/api/generate_ai_response', json={
            'text': 'Genki?', 'mode': 'answer', 'target_lang': 'ja', 'tone': 'arkadasca',
            'request_id': 'smoke-1'
        }).get_json()
        check(r.get('success') is True, f"answer success degil: {r}")
        check(len(answer_threads) >= 2,
              f"answer cagrilari gercekten paralel degil: thread={answer_threads}")
        # 4 ham secenek - 1 tekrar = 3 benzersiz
        result_options = r.get('options', [])
        check(len(result_options) == 3, f"dedup sonrasi secenek sayisi={len(result_options)} (beklenen 3)")
        translations = [opt.get('translation') for opt in result_options]
        check(
            set(translations) == {'Hai sou desu', 'Hontou?', 'Ganbatte'},
            f"dedup yanlis secenekleri korudu: {translations}"
        )
        check(
            translations.count('Hai sou desu') == 1,
            f"tekrar eden secenek tekilleştirilmedi: {translations}"
        )
        events = [e for e in sio.get_received() if e['name'] == 'ai_options_partial']
        check(len(events) == 2, f"kismi olay sayisi={len(events)} (beklenen 2)")
        for e in events:
            check(e['args'][0].get('request_id') == 'smoke-1', "kismi olay request_id yanlis")

        # request_id OLMADAN: kismi olay gitmemeli (geri uyumluluk)
        sio.get_received()
        r2 = client.post('/api/generate_ai_response', json={
            'text': 'Genki?', 'mode': 'answer', 'target_lang': 'ja', 'tone': 'arkadasca'
        }).get_json()
        check(r2.get('success') is True, "request_id'siz answer basarisiz")
        ev2 = [e for e in sio.get_received() if e['name'] == 'ai_options_partial']
        check(len(ev2) == 0, f"request_id yokken {len(ev2)} kismi olay gitti (beklenen 0)")

        # Iki model cagrisi da bozuk JSON dondururse ham metin Turkce anlam gibi
        # gosterilmemeli; istemci acik bir yeniden-dene hatasi almali.
        malformed = '<model-output>gecersiz-json</model-output>'
        responder.answer_question = lambda *a, **k: {'response': malformed}
        r3 = client.post('/api/generate_ai_response', json={
            'text': 'Genki?', 'mode': 'answer', 'target_lang': 'ja', 'tone': 'arkadasca'
        }).get_json()
        check(r3.get('success') is False, f"bozuk JSON basarili sayildi: {r3}")
        check(r3.get('fallback') is True, f"bozuk JSON fallback etiketi yok: {r3}")
        check(malformed not in json.dumps(r3), "ham AI ciktisi istemciye sizdi")

        for translate_mode in ('translate_dual', 'translate'):
            translated = client.post('/api/generate_ai_response', json={
                'text': 'Merhaba', 'mode': translate_mode, 'target_lang': 'ja'
            }).get_json()
            check(
                translated.get('success') is False and translated.get('fallback') is True,
                f"{translate_mode} bozuk JSON'u basarili saydi: {translated}"
            )
            check(
                malformed not in json.dumps(translated),
                f"{translate_mode} ham AI ciktisini istemciye sizdirdi"
            )

        # Gecerli JSON kabugu ama zorunlu ceviri alanlari bos ise de basari sayilmasin.
        responder.answer_question = lambda *a, **k: {'response': '{"translation":"","turkish":""}'}
        empty_dual = client.post('/api/generate_ai_response', json={
            'text': 'Merhaba', 'mode': 'translate_dual', 'target_lang': 'ja'
        }).get_json()
        check(empty_dual.get('success') is False,
              f"bos translate_dual alanlari basarili sayildi: {empty_dual}")
    finally:
        responder.answer_question = saved_fn
        responder.api_key = saved_key


# ── 3b. Auto modda script-tespitli stil daraltmasi (B5) ──────────────
def test_conversation_tools_contract():
    client = make_client()
    responder = buyedektir.transcriber.openai_responder
    saved_key, saved_fn = responder.api_key, responder.answer_question
    calls = []
    responder.api_key = 'test-key'
    def fake(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {'response': json.dumps({'options': [
            {'translation': 'Hai', 'turkish': 'Evet', 'romanized': 'Hay'}
        ], 'detected_lang': 'ja'})}
    responder.answer_question = fake
    try:
        for length, marker, cap in [('short', '3–8', 1000), ('normal', '8–20', 1000), ('detailed', '20–45', 1800)]:
            calls.clear()
            result = client.post('/api/generate_ai_response', json={
                'text':'Genki desu ka?', 'mode':'answer', 'target_lang':'ja', 'response_length':length
            }).get_json()
            check(result.get('success'), f'{length} cevap alınamadı')
            check(len(calls) == 2, 'Uzunluk iki paralel çağrıyı korumalı')
            check(all(marker in p and k['max_tokens'] == cap for p, k in calls), 'Uzunluk iki çağrıya da uygulanmalı')
            check(all(p.index('CEVAP UZUNLUĞU') < p.index('MESAJ:') for p, _ in calls), 'Değişken mesaj sonda kalmalı')
        calls.clear()
        invalid = client.post('/api/generate_ai_response', json={'text':'Merhaba', 'response_length':'unknown'})
        check(invalid.status_code == 400 and not calls, 'Geçersiz uzunluk AI çağırmamalı')
        responder.answer_question = lambda *a, **k: {'response': json.dumps({
            'translation':'少し遅れます。', 'turkish':'Biraz gecikeceğim.', 'romanized':'Sukoşi okuremas.'})}
        result = client.post('/api/generate_ai_response', json={
            'text':'Biraz gecikeceğim.', 'mode':'translate_dual', 'target_lang':'ja'
        }).get_json()
        check(result.get('native') == '少し遅れます。', 'Yazılı cevap için ayrı native alanı gerekli')
        check(result.get('turkish') == 'Biraz gecikeceğim.' and result.get('romanized'), 'Anlam ve okunuş gerekli')
        check(result.get('translation', '').startswith('Line1:'), 'Eski çeviri istemcisi uyumlu kalmalı')
    finally:
        responder.api_key, responder.answer_question = saved_key, saved_fn


def test_auto_mode_style_narrowing():
    """target_lang='auto' iken eskiden TUM dillerin (ja+es+fr+ar+zh+ru) stil/
    telaffuz kurallari AYNI prompta giriyordu (celisen kurallar: Arapca 'ASLA
    tire kullanma' + Japonca'nin tire gerektirmesi gibi). Script'ten tespit
    edilebilen bir dilde (_detect_script_lang) artik yalniz o dilin rehberi
    kullanilmali; Latin alfabeli/tespit edilemeyen metinde eski genis-kapsam
    davranis (tum dil rehberleri) korunmali."""
    client = make_client()
    responder = buyedektir.transcriber.openai_responder
    saved_key = responder.api_key
    saved_fn = responder.answer_question
    responder.api_key = 'test-key'

    captured_prompts = []

    def fake(text, **kw):
        captured_prompts.append(text)
        opts = [{'translation': 'Genki desu', 'turkish': 'Iyiyim', 'romanized': 'genki des'}]
        return {'response': json.dumps({'options': opts, 'detected_lang': 'ja'})}
    responder.answer_question = fake

    try:
        # Acikca Japonca script'li mesaj + target_lang='auto': stil DARALMALI,
        # Arapca/Cince rehberleri PROMPT'a hic girmemeli.
        captured_prompts.clear()
        r = client.post('/api/generate_ai_response', json={
            'text': '元気ですか？今日は何してましたか？',
            'mode': 'answer', 'target_lang': 'auto', 'tone': 'arkadasca'
        }).get_json()
        check(r.get('success') is True, f"auto+ja script answer basarisiz: {r}")
        check(len(captured_prompts) >= 1, "auto+ja script: hicbir cagri yakalanmadi")
        for p in captured_prompts:
            check('JAPONCA (ja)' in p, "auto+ja script: Japonca rehberi PROMPT'ta yok")
            check('ARAPÇA (ar)' not in p, "auto+ja script: alakasiz Arapca rehberi hala PROMPT'ta")
            check('ÇİNCE (zh)' not in p, "auto+ja script: alakasiz Cince rehberi hala PROMPT'ta")
            check('ASLA resmi, kitabi veya edebi haber dili (Fusha) kullanma' not in p,
                  "auto+ja script: celisen Arapca stil kurali hala PROMPT'ta")

        # Latin alfabeli/tespit edilemeyen metin: ESKI genis-kapsam davranis korunmali
        # (birden fazla dil rehberi birlikte gelir).
        captured_prompts.clear()
        r2 = client.post('/api/generate_ai_response', json={
            'text': 'Hello, how are you doing today my friend?',
            'mode': 'answer', 'target_lang': 'auto', 'tone': 'arkadasca'
        }).get_json()
        check(r2.get('success') is True, f"auto+latin answer basarisiz: {r2}")
        check(len(captured_prompts) >= 1, "auto+latin: hicbir cagri yakalanmadi")
        for p in captured_prompts:
            check('JAPONCA (ja)' in p and 'ARAPÇA (ar)' in p and 'ÇİNCE (zh)' in p,
                  "auto+latin: tespit edilemeyen metinde genis-kapsam rehber davranisi bozuldu")
    finally:
        responder.answer_question = saved_fn
        responder.api_key = saved_key


# ── 3c. Çift yönlü konuşma hafızası (conversation_turns) ─────────────
def test_bidirectional_conversation_memory():
    """AI eskiden yalniz karsi tarafin soylediklerini biliyordu; kullanicinin
    Alt-PTT ile soyledikleri ve secip 'sesli okudugunu' onayladigi cevaplar
    hic hafizaya girmiyordu (ayni oneriler tekrar tekrar cikiyordu). Bu test:
    (1) /api/mark_said 'me' turu ekliyor mu, (2) context_block PROMPT'ta rol
    etiketleriyle ([Ben]/[Karşı taraf]) dogru gorunuyor mu, (3) /api/clear
    conversation_turns'u da sifirliyor mu."""
    client = make_client()
    t = buyedektir.transcriber
    responder = t.openai_responder
    saved_key = responder.api_key
    saved_fn = responder.answer_question
    saved_turns = list(t.conversation_turns)
    responder.api_key = 'test-key'
    t.conversation_turns.clear()

    captured_prompts = []

    def fake(text, **kw):
        captured_prompts.append(text)
        opts = [{'translation': 'Genki desu', 'turkish': 'Iyiyim', 'romanized': 'genki des'}]
        return {'response': json.dumps({'options': opts, 'detected_lang': 'ja'})}
    responder.answer_question = fake

    try:
        # /api/mark_said metin gerektirir, bos istek reddedilmeli
        empty_r = client.post('/api/mark_said', json={'text': ''}).get_json()
        check(empty_r.get('success') is False, "mark_said bos metni kabul etti")

        # Gecerli cagri 'me' turu eklemeli (turkish alaniyla birlikte)
        before = len(t.conversation_turns)
        r = client.post('/api/mark_said', json={
            'text': 'Genki desu', 'turkish': 'İyiyim',
        }).get_json()
        check(r.get('success') is True, f"mark_said basarisiz: {r}")
        check(len(t.conversation_turns) == before + 1,
              f"mark_said tur eklemedi (once={before}, sonra={len(t.conversation_turns)})")
        last = t.conversation_turns[-1]
        check(last['role'] == 'me', f"mark_said rolu yanlis: {last['role']!r}")
        check(last['text'] == 'Genki desu', f"mark_said metni yanlis: {last['text']!r}")
        check(last['turkish'] == 'İyiyim', f"mark_said turkish alani yanlis: {last['turkish']!r}")

        # Karsi taraf turu da ekleyip PROMPT'ta rol etiketleriyle gorunuyor mu bak
        t.conversation_turns.append({'role': 'other', 'text': '元気ですか？', 'turkish': None})
        captured_prompts.clear()
        r2 = client.post('/api/generate_ai_response', json={
            'text': '元気ですか？', 'mode': 'answer', 'target_lang': 'ja', 'tone': 'arkadasca',
        }).get_json()
        check(r2.get('success') is True, f"answer basarisiz: {r2}")
        check(len(captured_prompts) >= 1, "conversation_turns testi: hicbir cagri yakalanmadi")
        for p in captured_prompts:
            check('[Ben]: Genki desu (İyiyim)' in p,
                  f"PROMPT'ta 'Ben' turu rol-etiketli gorunmuyor: {p[-400:]!r}")
            check('[Karşı taraf]: 元気ですか' in p,
                  f"PROMPT'ta 'Karşı taraf' turu rol-etiketli gorunmuyor: {p[-400:]!r}")
            check('ZATEN soyledigi' in p,
                  "PROMPT'ta tekrar-etmeme talimati yok")

        # /api/clear conversation_turns'u da sifirlamali
        check(len(t.conversation_turns) > 0, "test kurulumu: conversation_turns bos olmamali")
        clear_r = client.post('/api/clear').get_json()
        check(clear_r.get('success') is True, "clear basarisiz")
        check(len(t.conversation_turns) == 0,
              f"/api/clear conversation_turns'u sifirlamadi (kalan={len(t.conversation_turns)})")
    finally:
        responder.answer_question = saved_fn
        responder.api_key = saved_key
        t.conversation_turns.clear()
        t.conversation_turns.extend(saved_turns)


# ── 4. Ayar sinirlari ──────────────────────────────────────────────
def test_settings_bounds():
    t = buyedektir.transcriber
    saved = t.silence_duration
    try:
        t.silence_duration = buyedektir.DEFAULTS['silence_duration']
        for bad in (None, float('inf'), float('nan'), 999, -1, 0, 'abc'):
            t.update_settings({'silence_duration': bad})
            check(t.silence_duration == buyedektir.DEFAULTS['silence_duration'],
                  f"gecersiz silence_duration {bad!r} mevcut degeri degistirdi: {t.silence_duration}")
        t.update_settings({'silence_duration': 3.0})
        check(t.silence_duration == 3.0, f"gecerli 3.0 reddedildi -> {t.silence_duration}")
        t.update_settings({})
        check(t.silence_duration == 3.0,
              f"eksik silence_duration mevcut degeri degistirdi -> {t.silence_duration}")
        t.update_settings({'silence_duration': float('inf')})
        check(t.silence_duration == 3.0,
              f"inf mevcut gecerli degeri degistirdi -> {t.silence_duration}")
    finally:
        t.silence_duration = saved


# ── 5. Kurtarma parser'i ───────────────────────────────────────────
def test_salvage():
    salvage = buyedektir._salvage_answer_options
    # Kesik JSON: ilk obje tam, ikinci yarim
    raw = '{"detected_lang":"ja","options":[{"translation":"Hai","turkish":"Evet","romanized":"hay"},{"translation":"Iie","turki'
    opts, detected = salvage(raw)
    check(len(opts) >= 1, f"kurtarma 0 secenek dondurdu: {opts}")
    check(opts[0].get('turkish') == 'Evet', f"kurtarilan secenek yanlis: {opts[:1]}")
    check(detected == 'ja', f"kurtarilan detected_lang={detected!r} (beklenen 'ja')")


# ── 5a. Es zamanli dosya yazimlari ────────────────────────────────────────
def test_serialized_file_writes():
    """Transkript append'leri kaybolmasin; konusmaci profili her zaman tam JSON kalsin."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_file = buyedektir.TRANSCRIPT_FILE
        saved_max = buyedektir.TRANSCRIPT_MAX_BYTES
        transcript_path = os.path.join(tmp_dir, 'transcriptions.txt')
        buyedektir.TRANSCRIPT_FILE = transcript_path
        buyedektir.TRANSCRIPT_MAX_BYTES = 1024 * 1024

        def append_worker(worker_id):
            for index in range(40):
                buyedektir._append_transcript(f"{worker_id}:{index}\n")

        try:
            threads = [
                threading.Thread(target=append_worker, args=(worker_id,))
                for worker_id in range(6)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            with open(transcript_path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()
            check(len(lines) == 240, f"es zamanli transkript satiri={len(lines)} (beklenen 240)")
            check(len(set(lines)) == 240, "es zamanli transkript yaziminda tekrar/kayip var")
        finally:
            buyedektir.TRANSCRIPT_FILE = saved_file
            buyedektir.TRANSCRIPT_MAX_BYTES = saved_max

        diarizer = buyedektir.SpeakerDiarizer.__new__(buyedektir.SpeakerDiarizer)
        diarizer.speaker_names = {'0': 'Konuşmacı 1'}
        diarizer.profile_file = os.path.join(tmp_dir, 'speaker_profiles.json')
        diarizer._profile_lock = threading.RLock()
        diarizer._profile_load_failed = False
        diarizer.hf_token = None

        def rename_worker(worker_id):
            for index in range(20):
                diarizer.update_speaker_name('0', f'Ad {worker_id}-{index}')

        threads = [
            threading.Thread(target=rename_worker, args=(worker_id,))
            for worker_id in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        with open(diarizer.profile_file, 'r', encoding='utf-8') as f:
            profile = json.load(f)
        check(profile.get('names', {}).get('0', '').startswith('Ad '),
              f"konusmaci profili gecersiz: {profile}")
        check('hf_token' not in profile, 'HF token profil dosyasina yazildi')
        leftovers = [name for name in os.listdir(tmp_dir) if name.endswith('.tmp')]
        check(not leftovers, f"profil gecici dosyasi kaldi: {leftovers}")

        # Eski profil semasi adlari koruyarak gizli token alanini temizlemeli.
        legacy_path = os.path.join(tmp_dir, 'legacy-speaker-profiles.json')
        with open(legacy_path, 'w', encoding='utf-8') as stream:
            json.dump({'names': {'0': 'Ayse'}, 'hf_token': 'hf_' + 'x' * 30}, stream)
        old_env = os.environ.get('WHISPER_SPEAKER_PROFILE_FILE')
        os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = legacy_path
        try:
            migrated = buyedektir.SpeakerDiarizer()
            check(migrated.speaker_names == {'0': 'Ayse'}, 'eski profil adlari korunmadi')
            check(migrated.hf_token is None, 'eski profil tokeni bellege alindi')
            with open(legacy_path, encoding='utf-8') as stream:
                migrated_payload = json.load(stream)
            check(migrated_payload == {'names': {'0': 'Ayse'}},
                  f'eski profil token alani temizlenmedi: {migrated_payload.keys()}')
        finally:
            if old_env is None:
                os.environ.pop('WHISPER_SPEAKER_PROFILE_FILE', None)
            else:
                os.environ['WHISPER_SPEAKER_PROFILE_FILE'] = old_env


def test_partial_emit_session_guard():
    """Partial emit, session kontrolu ile ayni lifecycle kritik bolgesinde olmali."""
    t = buyedektir.transcriber
    saved = {
        'model': t.current_model,
        'session_id': t._session_id,
        'utterance_seq': t._utterance_seq,
        'is_running': t.is_running,
        'partial_inflight': t._partial_inflight,
        'partial_state_seq': t._partial_state_seq,
        'partial_previous_text': t._partial_previous_text,
        'partial_interval_current': t._partial_interval_current,
        'partial_snapshot_current': t._partial_snapshot_s_current,
        'partial_busy_skips': t._partial_model_busy_skips,
        'final_pending': t._final_model_pending.is_set(),
        'hallucination': t._is_likely_hallucination,
        'emit': buyedektir.socketio.emit,
    }
    emitted = []

    class FakeSegment:
        text = 'Merhaba'

    class FakeModel:
        def transcribe(self, *args, **kwargs):
            return [FakeSegment()], None

    def fake_emit(name, data):
        if name != 'partial_transcription':
            return
        acquired = t._lifecycle_lock.acquire(blocking=False)
        if acquired:
            t._lifecycle_lock.release()
        emitted.append({'data': data, 'lock_held': not acquired})

    try:
        t.current_model = FakeModel()
        t._session_id = 4242
        t._utterance_seq = 7
        t.is_running = True
        t._partial_inflight = True
        t._final_model_pending.clear()
        t._is_likely_hallucination = lambda text: False
        buyedektir.socketio.emit = fake_emit
        audio = buyedektir.np.ones(1600, dtype=buyedektir.np.int16)

        t._transcribe_partial(audio, 4242, 7)
        check(len(emitted) == 1, f"guncel partial emit edilmedi: {emitted}")
        check(emitted[0]['lock_held'], "partial emit lifecycle kilidi disinda yapildi")
        check(emitted[0]['data'].get('stable_text') == '',
              f"ilk partial kararlı sayildi: {emitted[0]['data']}")
        check(emitted[0]['data'].get('draft_text') == 'Merhaba',
              f"ilk partial taslak alani yanlis: {emitted[0]['data']}")

        t._transcribe_partial(audio, 4242, 7)
        check(len(emitted) == 2, f"ikinci partial emit edilmedi: {emitted}")
        check(emitted[1]['data'].get('stable_text') == 'Merhaba',
              f"teyit edilen partial kararlı olmadi: {emitted[1]['data']}")

        t._transcribe_partial(audio, 4241, 7)
        check(len(emitted) == 2, "eski session partial'i emit edildi")

        # Final/mic modeli kullaniyorsa partial kilitte BEKLEMEMELI: olay atlanir,
        # model kilidi ayni thread'de tutulurken deadlock olmadan doner.
        before_skips = t._partial_model_busy_skips
        t._model_lock.acquire()
        try:
            t._transcribe_partial(audio, 4242, 7)
        finally:
            t._model_lock.release()
        check(len(emitted) == 2, "model mesgulken partial emit edildi")
        check(t._partial_model_busy_skips == before_skips + 1,
              "model-mesgul partial atlama sayaci artmadi")
    finally:
        t.current_model = saved['model']
        t._session_id = saved['session_id']
        t._utterance_seq = saved['utterance_seq']
        t.is_running = saved['is_running']
        t._partial_inflight = saved['partial_inflight']
        t._partial_state_seq = saved['partial_state_seq']
        t._partial_previous_text = saved['partial_previous_text']
        t._partial_interval_current = saved['partial_interval_current']
        t._partial_snapshot_s_current = saved['partial_snapshot_current']
        t._partial_model_busy_skips = saved['partial_busy_skips']
        if saved['final_pending']:
            t._final_model_pending.set()
        else:
            t._final_model_pending.clear()
        t._is_likely_hallucination = saved['hallucination']
        buyedektir.socketio.emit = saved['emit']


def test_stable_partial_and_glossary_contract():
    stable, draft = buyedektir._stable_partial_parts(
        'Merhaba nası', 'Merhaba nasılsın bugün'
    )
    check((stable, draft) == ('Merhaba', 'nasılsın bugün'),
          f"kelime sinirli partial yanlis: {(stable, draft)}")
    stable, draft = buyedektir._stable_partial_parts('今日は天', '今日は天気です')
    check((stable, draft) == ('今日は天', '気です'),
          f"bosluksuz partial yanlis: {(stable, draft)}")
    check(buyedektir._stable_partial_parts('', 'ilk tahmin') == ('', 'ilk tahmin'),
          "ilk partial tamamen taslak olmali")

    raw_entries = [
        {'source': '  OpenAI\nLabs ', 'target': 'OpenAI',
         'pronunciation': 'opın ey ay', 'lang': 'EN'},
        {'source': 'openai labs', 'target': 'tekrar', 'lang': 'en'},
        {'source': '渋谷', 'target': '渋谷', 'pronunciation': 'şibuya', 'lang': 'ja'},
        {'source': 'Geçersiz', 'lang': 'not-a-lang'},
        {'source': ''},
    ]
    entries = buyedektir._sanitize_glossary_entries(raw_entries)
    check(len(entries) == 3, f"sozluk ayiklama/dedup yanlis: {entries}")
    check(entries[0]['source'] == 'OpenAI Labs' and entries[0]['lang'] == 'en',
          f"sozluk normalizasyonu yanlis: {entries[0]}")
    check(entries[-1]['lang'] == 'auto',
          f"gecersiz dil auto olmadi: {entries[-1]}")
    ja_prompt = buyedektir._format_glossary_prompt(entries, 'ja')
    check('渋谷' in ja_prompt and 'OpenAI Labs' not in ja_prompt,
          f"hedef dil sozluk filtresi yanlis: {ja_prompt}")
    override = buyedektir._apply_exact_pronunciation_override(
        '渋谷', 'yanlış', 'ja', entries
    )
    check(override == 'şibuya', f"tam okunus override uygulanmadi: {override}")

    summary = buyedektir._latency_summary([10, 20, 30, 40, 100])
    check(summary == {
        'count': 5, 'last_ms': 100.0, 'p50_ms': 30.0, 'p95_ms': 100.0
    }, f"gecikme ozeti yanlis: {summary}")

    transcriber = buyedektir.transcriber
    saved_interval = transcriber._partial_interval_current
    saved_window = transcriber._partial_snapshot_s_current
    try:
        transcriber._partial_interval_current = transcriber.PARTIAL_INTERVAL
        transcriber._partial_snapshot_s_current = transcriber.PARTIAL_SNAPSHOT_S
        slow_budget = transcriber._adapt_partial_budget(2000)
        check(slow_budget['interval_s'] > transcriber.PARTIAL_INTERVAL,
              f"yavas partial araligi buyumedi: {slow_budget}")
        check(slow_budget['snapshot_s'] < transcriber.PARTIAL_SNAPSHOT_S,
              f"yavas partial penceresi kuculmedi: {slow_budget}")
        for _ in range(20):
            fast_budget = transcriber._adapt_partial_budget(100)
        check(fast_budget['interval_s'] == transcriber.PARTIAL_INTERVAL,
              f"hizli partial taban araliga donmedi: {fast_budget}")
    finally:
        transcriber._partial_interval_current = saved_interval
        transcriber._partial_snapshot_s_current = saved_window

    saved_entries = transcriber.get_glossary_snapshot()
    client = make_client()
    try:
        response = client.post('/api/glossary', json={'entries': raw_entries})
        data = response.get_json()
        check(response.status_code == 200 and data.get('count') == 3,
              f"sozluk endpoint sozlesmesi yanlis: {response.status_code} {data}")
        invalid = client.post('/api/glossary', json={'entries': {'source': 'x'}})
        check(invalid.status_code == 400,
              f"sozluk endpoint liste disi girdiyi reddetmedi: {invalid.status_code}")
    finally:
        transcriber.set_glossary(saved_entries)


def test_shared_state_snapshots_are_isolated():
    """API/AI okuyuculari canli deque nesnelerini ve ic dict'leri paylasmamali."""
    transcriber = buyedektir.transcriber
    saved_transcriptions = transcriber.transcriptions
    saved_turns = transcriber.conversation_turns
    try:
        transcriber.transcriptions = buyedektir.deque([
            {'id': 1, 'text': 'bir'},
            {'id': 2, 'text': 'iki'},
        ], maxlen=1000)
        transcriber.conversation_turns = buyedektir.deque([
            {'role': 'other', 'text': 'eski', 'turkish': None},
            {'role': 'me', 'text': 'yeni', 'turkish': 'anlam'},
        ], maxlen=20)

        records = transcriber.get_transcriptions_snapshot(limit=1)
        turns = transcriber.get_conversation_snapshot(limit=1)
        check([record['id'] for record in records] == [2],
              f"transkript snapshot limiti yanlis: {records}")
        check([turn['text'] for turn in turns] == ['yeni'],
              f"konusma snapshot limiti yanlis: {turns}")
        check(transcriber.get_transcriptions_snapshot(limit=0) == [],
              "sifir limit tum transkriptleri dondurdu")

        records[0]['text'] = 'snapshot degisti'
        turns[0]['text'] = 'snapshot degisti'
        check(transcriber.transcriptions[-1]['text'] == 'iki',
              "transkript snapshot'i canli kaydi degistirdi")
        check(transcriber.conversation_turns[-1]['text'] == 'yeni',
              "konusma snapshot'i canli kaydi degistirdi")

        client = make_client()
        payload = client.get('/api/transcriptions').get_json()
        check([record['id'] for record in payload['transcriptions']] == [1, 2],
              f"transkript endpoint snapshot'i yanlis: {payload}")
    finally:
        transcriber.transcriptions = saved_transcriptions
        transcriber.conversation_turns = saved_turns


def test_pause_and_flush_contract():
    """Beklemede Simdi Gonder sahte basari vermemeli; UI/API durumu tutarli olmali."""
    transcriber = buyedektir.transcriber
    saved_running = transcriber.is_running
    saved_paused = transcriber.is_paused
    saved_flush = transcriber.flush_now
    client = make_client()
    try:
        with transcriber._lifecycle_lock:
            transcriber.is_running = False
            transcriber.is_paused = False
            transcriber.flush_now = False
        inactive = client.post('/api/pause', json={'paused': True})
        check(inactive.status_code == 409 and not inactive.get_json()['success'],
              f"pasif yakalama bekletmeyi kabul etti: {inactive.status_code}")

        with transcriber._lifecycle_lock:
            transcriber.is_running = True
        paused = client.post('/api/pause', json={'paused': True})
        check(paused.status_code == 200 and paused.get_json()['paused'] is True,
              f"aktif yakalama bekletilemedi: {paused.status_code}")
        blocked_flush = client.post('/api/flush')
        check(blocked_flush.status_code == 409 and not blocked_flush.get_json()['success'],
              f"beklemede flush sahte basari verdi: {blocked_flush.status_code}")
        check(transcriber.flush_now is False, "beklemede flush bayragi acildi")

        resumed = client.post('/api/pause', json={'paused': False})
        accepted_flush = client.post('/api/flush')
        check(resumed.status_code == 200 and accepted_flush.status_code == 200,
              "devam ettikten sonra flush kabul edilmedi")
        check(transcriber.flush_now is True, "aktif flush bayragi acilmadi")
    finally:
        with transcriber._lifecycle_lock:
            transcriber.is_running = saved_running
            transcriber.is_paused = saved_paused
            transcriber.flush_now = saved_flush


def test_mic_frame_snapshot_and_translation_workers():
    recorder = buyedektir.MicRecorder(rate=16000)
    recorder.is_recording = True
    recorder.thread = None
    recorder.stop_stream = lambda: None
    with recorder._frames_lock:
        recorder.frames = [
            buyedektir.np.ones(80, dtype=buyedektir.np.int16),
            buyedektir.np.ones(40, dtype=buyedektir.np.int16),
        ]
    audio = recorder.stop()
    check(audio is not None and len(audio) == 120,
          f"mic frame snapshot uzunlugu={0 if audio is None else len(audio)} (beklenen 120)")
    with recorder._frames_lock:
        check(not recorder.frames, "mic frame snapshot sonrasi buffer temizlenmedi")
    check(buyedektir.transcriber.translate_executor._max_workers == 2,
          "canli ceviri executor'i iki worker kullanmiyor")


def test_diarization_is_late_and_nonblocking():
    """Pyannote sonucu finalden sonra ayni kaydi guncelleyip slotu birakmali."""
    t = buyedektir.transcriber
    saved = {
        'transcriptions': t.transcriptions,
        'session_id': t._session_id,
        'generation': t._result_generation,
        'slot': t._diarize_slot,
        'emit': buyedektir.socketio.emit,
        'speaker_names': t.diarizer.speaker_names,
    }
    emitted = []

    class DoneFuture:
        @staticmethod
        def result():
            return '0', 'Ayşe'

    try:
        t._session_id = 909
        t.diarizer.speaker_names = {'0': 'Ayşe'}
        t._result_generation = 33
        t.transcriptions = buyedektir.deque([
            {'id': 77, 'text': 'Merhaba', 'speaker_id': None, 'speaker_name': None}
        ], maxlen=1000)
        t._diarize_slot = threading.BoundedSemaphore(1)
        check(t._diarize_slot.acquire(blocking=False), "test diarization slotu alinamadi")
        buyedektir.socketio.emit = lambda name, data: emitted.append((name, data))

        t._finish_diarization(DoneFuture(), 77, 909, 33)
        record = t.transcriptions[0]
        check(record['speaker_id'] == '0' and record['speaker_name'] == 'Ayşe',
              f"gecikmeli konusmaci sonucu kayda islenmedi: {record}")
        check(any(name == 'speaker_identified' for name, _ in emitted),
              f"speaker_identified emit edilmedi: {emitted}")
        released = t._diarize_slot.acquire(blocking=False)
        check(released, "diarization slotu callback sonrasi birakilmadi")
        if released:
            t._diarize_slot.release()
    finally:
        t.transcriptions = saved['transcriptions']
        t._session_id = saved['session_id']
        t._result_generation = saved['generation']
        t._diarize_slot = saved['slot']
        t.diarizer.speaker_names = saved['speaker_names']
        buyedektir.socketio.emit = saved['emit']


# ── 5b. /api/clear sonrasi transkript id'si CAKISMAMALI ─────────────
def test_transcription_id_survives_clear():
    """/api/clear yalniz goruntu sayacini (stats['total_transcriptions']) sifirlar;
    transcription['id'] uretimi HIC sifirlanmayan _next_transcription_id'den gelir.
    Eskiden id de stats'tan uretiliyordu: clear sonrasi yeni transkriptler 1'den
    baslar, 10-30sn suren eski bir async ceviri YENI olusan ayni id'li kayda
    yanlislikla yapisirdi (bkz. buyedektir.py _translate_async)."""
    client = make_client()
    t = buyedektir.transcriber
    saved_next_id = t._next_transcription_id
    try:
        t._next_transcription_id = 42
        r = client.post('/api/clear').get_json()
        check(r.get('success') is True, f"/api/clear basarisiz: {r}")
        check(t.stats['total_transcriptions'] == 0,
              f"goruntu sayaci sifirlanmadi: {t.stats['total_transcriptions']}")
        check(t._next_transcription_id == 42,
              f"_next_transcription_id clear ile SIFIRLANDI (goruldu: {t._next_transcription_id}, "
              f"beklenen 42 — id uretimi hala korunuyor olmali)")
    finally:
        t._next_transcription_id = saved_next_id


# ── 6. Ceviri backlog atlama ───────────────────────────────────────
def test_segment_join_and_speech_onset():
    from types import SimpleNamespace
    from unittest.mock import patch
    from contextlib import ExitStack

    join = lambda parts: buyedektir._join_transcription_segments(
        SimpleNamespace(text=part) for part in parts
    )
    check(join(['Bugün', 'toplantıya gelemem.']) == 'Bugün toplantıya gelemem.',
          'Whisper parça sınırı cümleyi bölmemeli')
    check(join(['Merhaba.', 'Nasılsın?']) == 'Merhaba. Nasılsın?',
          'model noktalaması korunmalı')
    check(join([' ', 'Hello', ',', 'world!']) == 'Hello, world!',
          'boş parça ve ayrı noktalama birleştirilmedi')
    check(join(['こんにちは', '。']) == 'こんにちは。', 'Japonca noktalama ayrıldı')

    t = buyedektir.transcriber
    np = buyedektir.np
    # 12 sessiz kareden yalnız son 6 kare (180 ms) konuşmaya eklenmeli.
    frames = iter(list(range(1, 13)) + [100, 101, 102] + list(range(20, 28)))
    captured = []

    class Stream:
        def read(self, count, **kwargs):
            try:
                value = next(frames)
            except StopIteration:
                t.is_running = False
                value = 0
            return np.full(count, value, dtype=np.int16).tobytes()

        def stop_stream(self):
            pass

        def close(self):
            pass

    stream = Stream()
    audio = SimpleNamespace(open=lambda **kwargs: stream, terminate=lambda: None)
    with ExitStack() as stack:
        for name, value in {
                'is_running': True, '_session_id': 888, 'is_paused': False,
                'ptt_active': False, 'flush_now': False, 'partial_enabled': False,
                'silence_duration': 0.09, 'adaptive_silence': False, '_utterance_seq': 0,
                '_active_audio_stream': None, '_active_audio_p': None}.items():
            stack.enter_context(patch.object(t, name, value))
        stack.enter_context(patch.object(buyedektir.pyaudio, 'PyAudio', return_value=audio))
        stack.enter_context(patch.object(t, '_resolve_capture_device', return_value=(0, {
            'maxInputChannels': 1, 'defaultSampleRate': 16000, 'name': 'Test'})))
        stack.enter_context(patch.object(t, '_enqueue_audio', side_effect=lambda data, *args: captured.append(data.copy())))
        stack.enter_context(patch.object(buyedektir, '_vad_is_speech', side_effect=lambda vad, data, rate: data[0] >= 100))
        stack.enter_context(patch.object(buyedektir.socketio, 'emit'))
        t._capture_audio(0, 888)
    check(len(captured) == 1, f'konuşma tek parça olmalı: {len(captured)}')
    if captured:
        check(captured[0][::480].tolist() == [7, 8, 9, 10, 11, 12, 100, 101, 102, 20, 21, 22],
              f'konuşma başlangıcı kayıp veya eski sessizlik sınırsız: {captured[0][::480].tolist()}')


def test_clear_capture_generation():
    from unittest.mock import patch
    t = buyedektir.transcriber
    with patch.object(t, 'audio_queue', _queue_mod.Queue()), \
            patch.object(t, '_session_id', 333), \
            patch.object(t, '_result_generation', 12):
        t._enqueue_audio('eski ses', 333, 11)
        t._enqueue_audio('eski oturum', 332, 12)
        check(t.audio_queue.empty(), 'eski ses sıfırlanmış kuyruğa eklendi')
        t._enqueue_audio('yeni ses', 333, 12)
        check(t.audio_queue.get_nowait() == 'yeni ses', 'güncel ses kayboldu')
        with patch.object(t, 'current_model') as model:
            t._transcribe_partial(buyedektir.np.zeros(480), 333, t._utterance_seq, 11)
            check(not model.transcribe.called, 'eski önizleme modele gönderildi')


def test_translation_backlog():
    t = buyedektir.transcriber
    saved_sess = t._session_id
    saved_generation = t._result_generation
    saved_latest = t._latest_translate_submit_id
    saved_tr = t.translator.translate
    saved_emit = buyedektir.socketio.emit
    saved_records = list(t.transcriptions)
    t._session_id = 1
    t._result_generation = 7
    t._latest_translate_submit_id = 100
    translated = []
    emitted = []
    t.translator.translate = lambda text, *a, **k: (translated.append(text), 'x')[1]
    buyedektir.socketio.emit = lambda event, payload=None, **_kw: emitted.append((event, payload))
    t.transcriptions.clear()
    t.transcriptions.extend([{'id': 95, 'text': 'a'}, {'id': 100, 'text': 'b'}])
    try:
        request_snapshot = {
            'provider': 'openai_reseller', 'enabled': True, 'source_lang': 'TR',
            'target_lang': 'EN', 'deepl_api_key': None, 'openai': {},
        }
        t._translate_async(90, 'eski-90', request_snapshot, session_id=1, result_generation=7)
        t._translate_async(94, 'eski-94', request_snapshot, session_id=1, result_generation=7)
        t._translate_async(95, 'guncel-95', request_snapshot, session_id=1, result_generation=7)
        t._translate_async(100, 'guncel-100', request_snapshot, session_id=1, result_generation=7)
        t._translate_async(100, 'eski-oturum', request_snapshot, session_id=999, result_generation=7)
        t._translate_async(100, 'eski-nesil', request_snapshot, session_id=1, result_generation=6)
        check(translated == ['guncel-95', 'guncel-100'],
              f"backlog atlama yanlis: {translated} (beklenen ['guncel-95','guncel-100'])")
        translation_events = [payload for event, payload in emitted
                              if event == 'transcription_translation']
        check([event.get('id') for event in translation_events] == [95, 100],
              f"ceviri socket olayi eksik/tekrarli: {translation_events}")
        check([record.get('translation') for record in t.transcriptions] == ['x', 'x'],
              f"bellek ceviri guncellemesi yanlis: {list(t.transcriptions)}")
        check(all(record.get('translation_status') == 'done' for record in t.transcriptions),
              'tamamlanan çevirilerin durumu kaydedilmedi')
        t.transcriptions.append({'id': 90, 'text': 'eski'})
        t._translate_async(90, 'eski', request_snapshot, session_id=1, result_generation=7)
        check(t.transcriptions[-1]['translation_status'] == 'skipped', 'atlanmış çeviri görünür değil')
        t.translator.translate = lambda *args, **kwargs: None
        t._translate_async(100, 'hata', request_snapshot, session_id=1, result_generation=7)
        check(t.transcriptions[1]['translation_status'] == 'failed', 'başarısız çeviri bekliyor görünüyor')
        event_count = len(emitted)
        t._set_translation_status(100, 'pending', 999, 7)
        check(len(emitted) == event_count and t.transcriptions[1]['translation_status'] == 'failed',
              'eski oturum çeviri durumunu değiştirdi')
    finally:
        t._session_id = saved_sess
        t._result_generation = saved_generation
        t._latest_translate_submit_id = saved_latest
        t.translator.translate = saved_tr
        buyedektir.socketio.emit = saved_emit
        t.transcriptions.clear()
        t.transcriptions.extend(saved_records)


# ── 7. Resample tasma kirpmasi (int16 sarma onleme) ────────────────
def test_resample_clip():
    np = buyedektir.np
    # Tama yakin, tek keskin gecisli adim -> FIR filtresi Gibbs tasmasi uretir.
    sig = np.concatenate([np.full(2205, 32000), np.full(2205, -32000)]).astype(np.int16)
    fl = buyedektir.signal.resample_poly(sig, 160, 441,
                                         window=buyedektir._resample_filter(160, 441))
    check(np.max(np.abs(fl)) > 32767, "test girdisi tasma uretmedi (test gecersiz)")
    out = buyedektir._resample_int16(sig, 44100, 16000)
    check(out.min() >= -32768 and out.max() <= 32767,
          f"resample ciktisi int16 araligini asti: min={out.min()} max={out.max()}")
    over = fl > 32767
    check(bool(np.all(out[over] == 32767)),
          "tasan ornekler 32767'ye kirpilmadi (sarma riski)")


# ── 8. Kismi onizleme snapshot kirpmasi (O(n^2) tampon buyumesi onlemi) ──
def test_partial_snapshot_cap():
    t = buyedektir.transcriber
    np = buyedektir.np
    chunk_seconds = 0.03  # gercek CHUNK_DURATION_MS (30ms) ile ayni

    # 60sn'lik tampon (2000 chunk) simule et; her chunk'i indeksiyle isaretle.
    buf = [np.full(10, i, dtype=np.int16) for i in range(2000)]
    snap = t._partial_snapshot(buf, chunk_seconds)
    expected_chunks = int(t.PARTIAL_SNAPSHOT_S / chunk_seconds)
    check(len(snap) == expected_chunks * 10,
          f"snapshot uzunlugu={len(snap)} (beklenen {expected_chunks * 10}, "
          f"PARTIAL_SNAPSHOT_S={t.PARTIAL_SNAPSHOT_S})")
    check(int(snap[-1]) == 1999, f"snapshot son ornegi yanlis: {snap[-1]} (beklenen 1999)")
    check(int(snap[0]) == 2000 - expected_chunks,
          f"snapshot ilk ornegi yanlis: {snap[0]} (beklenen {2000 - expected_chunks})")

    # Tampon PARTIAL_SNAPSHOT_S'den KISAYSA tumu donmeli (mevcut davranis korunur)
    short_buf = buf[:5]
    short_snap = t._partial_snapshot(short_buf, chunk_seconds)
    check(len(short_snap) == 50, f"kisa tampon tumuyle donmedi: {len(short_snap)} (beklenen 50)")

    # chunk_seconds=0 (native rate okunamadi vb.) tumunu donsun, ZeroDivisionError atmasin
    zero_snap = t._partial_snapshot(short_buf, 0)
    check(len(zero_snap) == 50, f"chunk_seconds=0 fallback yanlis: {len(zero_snap)} (beklenen 50)")


# ── 8b. Akilli bolme: MAX_UTTERANCE_S kesimini en sessiz noktaya kaydir ──
def test_quiet_split_index():
    """MAX_UTTERANCE_S zorunlu bolmesi kelimeyi ortadan kesmesin: son
    SPLIT_SEARCH_S penceresindeki en dusuk enerjili chunk sinirindan bolunur.
    Bu test _find_quiet_split_index'i sentetik tamponla dogrular (model/ses yok)."""
    t = buyedektir.transcriber
    np = buyedektir.np
    chunk_seconds = 0.03

    # 850 chunk (~25.5sn) gurultulu tampon; SON pencerede (son ~50 chunk) tek bir
    # SESSIZ chunk yerlestir. Bolme TAM o sessiz chunk'ta olmali.
    n = 850
    buf = [np.full(10, 8000, dtype=np.int16) for _ in range(n)]
    tail_chunks = int(t.SPLIT_SEARCH_S / chunk_seconds)  # ~50
    quiet_at = n - 10  # pencere icinde, sona yakin ama son degil
    buf[quiet_at] = np.zeros(10, dtype=np.int16)  # en sessiz chunk

    idx = t._find_quiet_split_index(buf, chunk_seconds)
    check(idx == quiet_at, f"bolme sessiz chunk'ta degil: idx={idx} (beklenen {quiet_at})")
    # Bolunen kuyruk pencereden kisa olmali, gonderilen kisim buyuk olmali
    check(idx >= n - tail_chunks, f"bolme pencere disinda: idx={idx}, pencere basi={n - tail_chunks}")
    check(idx >= 1, "bolme en az 1 chunk gondermeli (bos segment olmamali)")

    # Sessiz nokta YOKSA (hepsi ayni enerji) pencere basindaki ilk chunk secilir,
    # yine de tum tamponu gondermez (kelime-ortasi kesimden iyi, deterministik).
    buf_flat = [np.full(10, 8000, dtype=np.int16) for _ in range(n)]
    idx_flat = t._find_quiet_split_index(buf_flat, chunk_seconds)
    check(idx_flat == n - tail_chunks,
          f"duz-enerji bolmesi pencere basinda degil: idx={idx_flat} (beklenen {n - tail_chunks})")

    # Cok kisa tampon / chunk_seconds=0: tum tamponu gonder (len doner, eski davranis)
    check(t._find_quiet_split_index([], chunk_seconds) == 0, "bos tampon 0 donmedi")
    short = [np.zeros(10, dtype=np.int16) for _ in range(3)]
    check(t._find_quiet_split_index(short, 0) == 3, "chunk_seconds=0 fallback yanlis (tumu gonderilmeli)")


# ── Sahte PyAudio: _capture_audio'yu GERCEK thread'inde, gercek donanim ────
# olmadan calistirmak icin. read() gercek zamanli (time.sleep) hiz keser ki
# _capture_audio dongusu gercek mikrofon gibi ilerlesin.
class _FakeStream:
    def __init__(self, frames_per_buffer, channels):
        self.frames_per_buffer = frames_per_buffer
        self.channels = channels

    def read(self, n, exception_on_overflow=False):
        time.sleep(n / 16000.0)
        arr = buyedektir.np.random.randint(-20000, 20000, size=n * self.channels, dtype='int16')
        return arr.tobytes()

    def stop_stream(self):
        pass

    def close(self):
        pass


class _FakePyAudio:
    def __init__(self, *a, **k):
        pass

    def get_host_api_info_by_type(self, *a, **k):
        raise RuntimeError('test ortaminda WASAPI yok')

    def get_device_info_by_index(self, idx):
        return {'maxInputChannels': 1, 'defaultSampleRate': 16000,
                'name': 'FakeDevice', 'isLoopbackDevice': False}

    def open(self, format=None, channels=1, rate=16000, input=True,
              input_device_index=None, frames_per_buffer=480):
        return _FakeStream(frames_per_buffer, channels)

    def terminate(self):
        pass


def _run_fake_capture(t, run_seconds, setup_fn):
    """_capture_audio'yu sahte PyAudio ile ayri thread'de calistirir, run_seconds
    sonra durdurur ve join eder. setup_fn(t) capture baslamadan once cagrilir
    (orn. ptt_active=True veya vad.is_speech sahtelemesi icin). Kuyrukta biriken
    segmentleri (numpy array listesi) dondurur. Tum degistirilen singleton
    durumunu finally'de geri yukler; logger gurultusunu (binlerce flush satiri
    olabilir) INFO altina cekip test ciktisini kirletmez."""
    saved = {
        'pyaudio': buyedektir.pyaudio.PyAudio,
        'vad_is_speech': t.vad.is_speech,
        'queue': t.audio_queue,
        'session_id': t._session_id,
        'is_running': t.is_running,
        'partial_enabled': t.partial_enabled,
        'ptt_active': t.ptt_active,
        'log_level': buyedektir.logger.level,
    }
    buyedektir.pyaudio.PyAudio = _FakePyAudio
    t.audio_queue = _queue_mod.Queue(maxsize=500)
    t.partial_enabled = False
    t._session_id = 777777
    t.is_running = True
    buyedektir.logger.setLevel(logging.ERROR)
    setup_fn(t)
    try:
        th = threading.Thread(target=t._capture_audio, args=(0, 777777), daemon=True)
        th.start()
        time.sleep(run_seconds)
        t.is_running = False
        t.ptt_active = False
        th.join(timeout=3)
        still_alive = th.is_alive()
        segments = []
        while not t.audio_queue.empty():
            segments.append(t.audio_queue.get_nowait())
        return segments, still_alive
    finally:
        buyedektir.pyaudio.PyAudio = saved['pyaudio']
        t.vad.is_speech = saved['vad_is_speech']
        t.audio_queue = saved['queue']
        t._session_id = saved['session_id']
        t.is_running = saved['is_running']
        t.partial_enabled = saved['partial_enabled']
        t.ptt_active = saved['ptt_active']
        buyedektir.logger.setLevel(saved['log_level'])


# ── 9. MAX_UTTERANCE_S zorlamasi (kesintisiz konusma/muzik) ───────────────
def test_max_utterance_forced_flush():
    """buyedektir.log'da kayitli GERCEK cokmenin regresyon testi: kesintisiz
    seste (VAD hic sessizlik gormez) audio_buffer ~20dk'ya buyumus, kismi
    transkripsiyon 'Unable to allocate 29.0 GiB' hatasi vermisti. VAD'i hep
    'konusma var' donecek sekilde sahteleyip MAX_UTTERANCE_S asilinca segment
    zorla bolunuyor mu dogrular."""
    t = buyedektir.transcriber
    saved_max_utt = t.MAX_UTTERANCE_S
    saved_seq = t._utterance_seq

    def setup(t):
        t.vad.is_speech = lambda *a, **k: True  # SUREKLI konusma
        t.MAX_UTTERANCE_S = 0.15                # hizli test icin kucuk esik

    try:
        segments, still_alive = _run_fake_capture(t, run_seconds=1.0, setup_fn=setup)
        check(not still_alive, 'capture thread zamaninda durdu')
        check(len(segments) >= 3,
              f'MAX_UTTERANCE_S zorlamasi coklu segment uretti (n={len(segments)}, beklenen >=3)')
        max_seconds = max((len(s) / 16000.0 for s in segments), default=0.0)
        check(max_seconds <= t.MAX_UTTERANCE_S * 2,
              f'segment suresi sinirsiz BUYUMEDI (max={max_seconds:.3f}sn, '
              f'sinir={t.MAX_UTTERANCE_S}sn) — cokme senaryosu regresyonu')
        check(t._utterance_seq > saved_seq + 2,
              f'_utterance_seq coklu kez artti ({saved_seq} -> {t._utterance_seq})')
    finally:
        t.MAX_UTTERANCE_S = saved_max_utt
        t._utterance_seq = saved_seq


# ── 10. MAX_PTT_S zorlamasi (tus birakma olayi kacirilirsa) ───────────────
def test_max_ptt_forced_flush():
    """PTT (Ctrl basili tutma) suresiz birikmesin: tus birakma olayi
    kacirilirsa (pencere blur/OS event kaybi) ptt_buffer MAX_PTT_S'te
    zorla bosaltilmali. ptt_active=True baslangictan itibaren sabit tutulur
    (gercek birakma olayi simule edilmez); bu, senaryoyu en kotu durumda test eder."""
    t = buyedektir.transcriber
    saved_max_ptt = t.MAX_PTT_S

    def setup(t):
        t.MAX_PTT_S = 0.15
        t.ptt_active = True  # capture basladiginda tus zaten basili

    try:
        segments, still_alive = _run_fake_capture(t, run_seconds=1.0, setup_fn=setup)
        check(not still_alive, 'capture thread zamaninda durdu (ptt)')
        check(len(segments) >= 3,
              f'MAX_PTT_S zorlamasi coklu segment uretti (n={len(segments)}, beklenen >=3)')
        max_seconds = max((len(s) / 16000.0 for s in segments), default=0.0)
        check(max_seconds <= t.MAX_PTT_S * 2,
              f'ptt segment suresi sinirsiz BUYUMEDI (max={max_seconds:.3f}sn, sinir={t.MAX_PTT_S}sn)')
    finally:
        t.MAX_PTT_S = saved_max_ptt


def test_api_token_and_model_load_lock():
    # Dis bir web sayfasinin token'siz form POST'u durum degistirememeli.
    raw_client = buyedektir.app.test_client()
    denied = raw_client.post('/api/clear')
    check(denied.status_code == 403, f"token'siz POST reddedilmedi: {denied.status_code}")
    denied_get = raw_client.get('/api/transcriptions')
    check(denied_get.status_code == 403,
          f"token'siz transkript GET reddedilmedi: {denied_get.status_code}")
    allowed = make_client().post('/api/clear')
    check(allowed.status_code == 200, f"token'li POST gecmedi: {allowed.status_code}")
    settings_response = make_client().get('/api/settings')
    check(settings_response.status_code == 200, 'tokenli GET /api/settings gecmedi')
    check('silence_duration' in (settings_response.get_json().get('settings') or {}),
          'GET /api/settings runtime snapshot dondurmedi')
    health = raw_client.get('/healthz')
    check(health.status_code == 200, 'tokensiz /healthz proses gozlemine kapali')
    health_data = health.get_json()
    check(set(health_data) == {
        'ok', 'model_loaded', 'capture_running', 'executors_alive', 'last_error'
    }, f'healthz gizli/fazla alan dondurdu: {set(health_data)}')
    with buyedektir._health_error_lock:
        previous_health_error = buyedektir._last_health_error
    try:
        buyedektir._record_health_error('synthetic test: gizli ayrinti')
        error = raw_client.get('/healthz').get_json()['last_error']
        check(error['code'] == 'synthetictestgizliayrinti',
              f'health hata kodu temizlenmedi: {error}')
        check(set(error) == {'code', 'at'}, f'health hata yapisi gereksiz alan tasiyor: {error}')
    finally:
        with buyedektir._health_error_lock:
            buyedektir._last_health_error = previous_health_error

    # Cift model yukleme ayni anda iki constructor/VRAM tahsisi baslatmamali.
    t = buyedektir.transcriber
    original = t._load_model_unlocked
    entered = threading.Event()
    release = threading.Event()

    def blocked_loader(*_args, **_kwargs):
        entered.set()
        release.wait(timeout=2)
        return {'success': True}

    t._load_model_unlocked = blocked_loader
    first = {}
    worker = threading.Thread(
        target=lambda: first.update(t.load_model('tiny')),
        daemon=True,
    )
    try:
        worker.start()
        check(entered.wait(timeout=1), 'ilk model yukleme kilide girmedi')
        second = t.load_model('base')
        check(second.get('success') is False,
              f'eszamanli ikinci model yukleme reddedilmedi: {second}')
    finally:
        release.set()
        worker.join(timeout=2)
        t._load_model_unlocked = original


def test_ai_request_rate_limit():
    slots = []
    with buyedektir.app.app_context():
        try:
            first, error = buyedektir._begin_ai_request('answer', 'merhaba', 'req-1', '42')
            check(first is not None and error is None, 'ilk AI slotu alinamadi')
            slots.append(first)
            duplicate, duplicate_error = buyedektir._begin_ai_request(
                'answer', 'merhaba', 'req-2', '42'
            )
            check(duplicate is None and duplicate_error[1] == 409,
                  'ayni transkriptin ikinci aktif AI istegi reddedilmedi')
            second, error = buyedektir._begin_ai_request('answer', 'diger', 'req-3', '43')
            check(second is not None and error is None, 'ikinci kuresel AI slotu alinamadi')
            slots.append(second)
            overflow, overflow_error = buyedektir._begin_ai_request(
                'answer', 'ucuncu', 'req-4', '44'
            )
            check(overflow is None and overflow_error[1] == 429,
                  'kuresel AI in-flight ust siniri uygulanmadi')
        finally:
            for slot in slots:
                buyedektir._finish_ai_request(slot)


def test_ai_chat_validation_and_identity():
    from unittest.mock import patch
    client = make_client()
    for question in (None, [], {}, 7, True, '', '   '):
        response = client.post('/api/ai_chat', json={'action': 'question', 'question': question})
        check(response.status_code == 400, f'ai_chat gecersiz soru reddedilmedi: {question!r}')
    check(client.post('/api/ai_chat', json={'action': []}).status_code == 400,
          'ai_chat gecersiz action reddedilmedi')
    responder = buyedektir.transcriber.openai_responder
    identities = []
    original_begin = buyedektir._begin_ai_request

    def capture_identity(kind, text, request_id=''):
        identities.append(text)
        return original_begin(kind, text, request_id)

    with patch.object(responder, 'api_key', 'test-only'), \
            patch.object(responder, 'answer_question', return_value={'response': 'Yanıt'}) as answer, \
            patch.object(buyedektir.transcriber, 'get_transcriptions_snapshot',
                         return_value=[{'text': 'Toplantı yarın.'}]), \
            patch.object(buyedektir, '_begin_ai_request', side_effect=capture_identity):
        for question in ('Ne zaman?', 'Nerede?', 'x' * 1100):
            response = client.post('/api/ai_chat', json={'action': 'question', 'question': question})
            check(response.status_code == 200 and response.json['success'], 'ai_chat gecerli soru basarisiz')
        check(identities[0] != identities[1], 'farkli sorular ayni istek saniliyor')
        check(answer.call_args.args[0].endswith('x' * 1000), 'uzun soru sinirlanmadi')
        check(not buyedektir._ai_active_keys, 'ai_chat slotu serbest birakilmadi')


def test_transkribe_helpers():
    import transkribe

    check(transkribe.remove_overlap(['Merhaba dünya'], '... dünya yeniden') == 'yeniden',
          'remove_overlap noktalama tokenini filtrelemedi')
    check(transkribe.remove_overlap(['Bugün hava güzel'], 'güzel gerçekten') == 'gerçekten',
          'remove_overlap belirgin tek kelimelik ortusmeyi kaldirmadi')
    check(transkribe.remove_overlap(['I am ready'], 'I agree') == 'I agree',
          'remove_overlap tek harfli dogal baslangici yanlis sildi')

    with tempfile.TemporaryDirectory() as tmp_dir:
        model_root = os.path.join(tmp_dir, 'models--Test--faster-whisper-demo', 'snapshots')
        older = os.path.join(model_root, 'older')
        newer = os.path.join(model_root, 'newer')
        os.makedirs(older)
        os.makedirs(newer)
        for folder in (older, newer):
            with open(os.path.join(folder, 'model.bin'), 'wb') as stream:
                stream.write(b'x')
        os.utime(older, (1000, 1000))
        os.utime(newer, (2000, 2000))
        saved_models_dir = transkribe.MODELS_DIR
        transkribe.MODELS_DIR = tmp_dir
        try:
            models = transkribe.find_models()
            check(list(models.values()) == [newer],
                  f'find_models en yeni snapshoti secmedi: {models}')
        finally:
            transkribe.MODELS_DIR = saved_models_dir

    history = make_client().get('/api/transcriptions').get_json()
    check(history.get('instance_id') == buyedektir.INSTANCE_ID,
          f"transkript endpoint instance kimligi vermedi: {history.keys()}")


def test_capture_open_after_stop_is_stale():
    """Cihaz open'i Stop'tan sonra donerse capture_started yaymamali."""
    t = buyedektir.transcriber
    entered = threading.Event()
    release = threading.Event()
    emitted = []

    class FakeStream:
        def is_active(self): return True
        def stop_stream(self): pass
        def close(self): pass

    class FakePyAudio:
        def get_device_info_by_index(self, _index):
            return {'maxInputChannels': 1, 'defaultSampleRate': 16000, 'name': 'Sahte'}

        def open(self, **_kwargs):
            entered.set()
            release.wait(timeout=2)
            return FakeStream()

        def terminate(self): pass

    saved_py_audio = buyedektir.pyaudio.PyAudio
    saved_emit = buyedektir.socketio.emit
    saved_session = t._session_id
    saved_running = t.is_running
    saved_active_stream = t._active_audio_stream
    saved_active_p = t._active_audio_p
    try:
        buyedektir.pyaudio.PyAudio = FakePyAudio
        buyedektir.socketio.emit = lambda event, payload=None, **_kw: emitted.append(event)
        with t._lifecycle_lock:
            t._session_id = saved_session + 100
            session_id = t._session_id
            t.is_running = True
            t._active_audio_stream = None
            t._active_audio_p = None
        worker = threading.Thread(target=t._capture_audio, args=(0, session_id), daemon=True)
        worker.start()
        check(entered.wait(timeout=1), 'sahte ses cihazi open asamasina gelmedi')
        with t._lifecycle_lock:
            t.is_running = False
        release.set()
        worker.join(timeout=2)
        check(not worker.is_alive(), 'stale capture thread kapanmadi')
        check('capture_started' not in emitted,
              f'Stop sonrasi capture_started yayildi: {emitted}')
    finally:
        release.set()
        buyedektir.pyaudio.PyAudio = saved_py_audio
        buyedektir.socketio.emit = saved_emit
        with t._lifecycle_lock:
            t._session_id = saved_session
            t.is_running = saved_running
            t._active_audio_stream = saved_active_stream
            t._active_audio_p = saved_active_p


def test_ai_config_tests_connection_once():
    responder = buyedektir.transcriber.openai_responder
    saved_set = responder.set_api_key
    saved_test = responder.test_connection
    calls = []
    try:
        responder.set_api_key = lambda key: (calls.append(key), True)[1]
        responder.test_connection = lambda: (_ for _ in ()).throw(
            AssertionError('test_connection ikinci kez cagrildi')
        )
        response = make_client().post(
            '/api/ai_response_config', json={'openai_key': 'test-key'}
        ).get_json()
        check(response.get('success') is True, f'AI config endpoint basarisiz: {response}')
        check(calls == ['test-key'], f'AI config set_api_key sayisi yanlis: {calls}')
    finally:
        responder.set_api_key = saved_set
        responder.test_connection = saved_test


def test_openai_compatible_reseller_config():
    normalize = buyedektir._normalize_openai_chat_url
    check(
        normalize('https://api.shuaiapi.com/')
        == 'https://api.shuaiapi.com/v1/chat/completions',
        'reseller kok URL chat completions adresine donusmedi',
    )
    check(
        normalize('https://api.shuaiapi.com/v1')
        == 'https://api.shuaiapi.com/v1/chat/completions',
        'reseller /v1 URL yanlis donustu',
    )
    check(
        normalize('https://user:secret@api.shuaiapi.com/')
        == buyedektir._DEFAULT_OPENAI_CHAT_URL,
        'URL icindeki kimlik bilgisi reddedilmedi',
    )

    names = ('OPENAI_BASE_URL', 'OPENAI_MODEL', 'OPENAI_RESPONSE_MODEL')
    saved = {name: os.environ.get(name) for name in names}
    try:
        os.environ['OPENAI_BASE_URL'] = 'https://oai.sb/'
        os.environ['OPENAI_MODEL'] = 'gpt-5.4'
        os.environ['OPENAI_RESPONSE_MODEL'] = 'gpt-5.4'
        responder = buyedektir.OpenAIResponder()
        check(responder.base_url == buyedektir._DEFAULT_OPENAI_CHAT_URL,
              f'ana AI resmi endpoint yerine gitti: {responder.base_url}')
        check(responder.reseller_base_url == 'https://oai.sb/v1/chat/completions',
              f'reseller ceviri endpointi yuklenmedi: {responder.reseller_base_url}')
        with responder._config_lock:
            responder.api_key = 'official-response-key'
        check(not responder.translation_is_configured('openai_reseller'),
              'reseller ceviri resmi cevap anahtarina geri dusmemeli')
        reseller_snapshot = responder.snapshot_translation_request('openai_reseller')
        check(reseller_snapshot.get('api_key') is None,
              'reseller snapshot resmi cevap anahtarini tasimamali')
        connection_urls = []
        original_post = buyedektir._http_session.post
        class ConnectionResponse:
            status_code = 200
            text = ''
        try:
            buyedektir._http_session.post = lambda url, **kwargs: (
                connection_urls.append(url) or ConnectionResponse()
            )
            check(responder.test_connection(), 'resmi ana AI baglanti testi basarisiz')
        finally:
            buyedektir._http_session.post = original_post
        check(connection_urls == [buyedektir._DEFAULT_OPENAI_CHAT_URL],
              f'ana AI baglanti testi resmi endpoint disina gitti: {connection_urls}')
        check(responder.model == 'gpt-5.4',
              f'reseller ceviri modeli yuklenmedi: {responder.model}')
        check(responder.response_model == 'gpt-5.4',
              f'reseller cevap modeli yuklenmedi: {responder.response_model}')
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_translation_provider_snapshot_is_immutable():
    """Kuyruktaki reseller isi, ayar resmi OpenAI'a gecse bile eski URL+anahtar
    ciftiyle gitmeli. Aksi halde resmi anahtar reseller sunucusuna sizabilir."""
    responder = buyedektir.OpenAIResponder()
    calls = []
    original_post = buyedektir._http_session.post

    class FakeResponse:
        status_code = 200
        text = ''

        @staticmethod
        def json():
            return {'choices': [{'message': {'content': 'hello'}}], 'usage': {}}

    def fake_post(url, headers=None, **_kwargs):
        calls.append((url, (headers or {}).get('Authorization')))
        return FakeResponse()

    try:
        with responder._config_lock:
            responder.reseller_base_url = 'https://reseller.invalid/v1/chat/completions'
            responder.api_key = 'response-key'
        responder.configure_translation('openai_reseller', 'reseller-key')
        queued = responder.snapshot_translation_request()
        responder.configure_translation('openai_official', 'official-key')
        buyedektir._http_session.post = fake_post

        result = responder.answer_question(
            'çevir', model_type='translation', translation_snapshot=queued,
        )
        check(result and result.get('response') == 'hello',
              f'snapshot ceviri sonucu beklenmedik: {result}')
        check(calls == [(
            'https://reseller.invalid/v1/chat/completions', 'Bearer reseller-key'
        )], f'kuyruk URL/anahtari ayar degisiminden etkilendi: {calls}')
    finally:
        buyedektir._http_session.post = original_post


def test_translation_settings_snapshot_is_atomic():
    translator = buyedektir.DeepLTranslator()
    translator.enabled = True
    translator.provider = 'deepl'
    translator.source_lang = 'TR'
    translator.target_lang = 'EN'
    translator.api_key = 'old-deepl-key'
    queued = translator.snapshot_request()
    captured = []
    original_post = buyedektir._http_session.post

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {'translations': [{'text': 'hello'}]}

    def fake_post(url, headers=None, data=None, **_kwargs):
        captured.append((url, headers, data))
        return FakeResponse()

    try:
        with translator._config_lock:
            translator.enabled = False
            translator.source_lang = 'JA'
            translator.target_lang = 'DE'
            translator.api_key = 'new-deepl-key'
        buyedektir._http_session.post = fake_post
        result = translator.translate('merhaba', request_snapshot=queued)
        check(result == 'hello', f'kuyruktaki enabled snapshot korunmadi: {result!r}')
        check(len(captured) == 1, f'DeepL snapshot istegi sayisi yanlis: {len(captured)}')
        if captured:
            _url, headers, data = captured[0]
            check(headers.get('Authorization') == 'DeepL-Auth-Key old-deepl-key',
                  f'DeepL snapshot anahtari degisti: {headers}')
            check(data.get('source_lang') == 'TR' and data.get('target_lang') == 'EN',
                  f'DeepL snapshot dil cifti degisti: {data}')
    finally:
        buyedektir._http_session.post = original_post


def test_speaker_reset_invalidates_inflight_result():
    """Reset'ten once baslayan yavas diarization profili sonradan diriltmemeli."""
    # identify_speaker torch'u tembel import eder; bu testin 1sn'lik yarisi model
    # kutuphanesinin ilk import suresini degil, pipeline yarisi davranisini olcer.
    __import__('torch')
    entered = threading.Event()
    release = threading.Event()

    class Turn:
        duration = 1.0

    class Diarization:
        @staticmethod
        def itertracks(yield_label=False):
            return iter([(Turn(), None, 'SPEAKER_00')])

    def slow_pipeline(_audio):
        entered.set()
        release.wait(timeout=2)
        return type('DiarizeOutput', (), {
            'speaker_diarization': Diarization()
        })()

    with tempfile.TemporaryDirectory() as tmp_dir:
        diarizer = buyedektir.SpeakerDiarizer.__new__(buyedektir.SpeakerDiarizer)
        diarizer.enabled = True
        diarizer.is_ready = True
        diarizer.pipeline = slow_pipeline
        diarizer.speaker_names = {}
        diarizer.profile_file = os.path.join(tmp_dir, 'speaker_profiles.json')
        diarizer._profile_lock = threading.RLock()
        diarizer._profile_load_failed = False
        diarizer._profile_generation = 0
        diarizer.hf_token = None
        result = []
        worker = threading.Thread(
            target=lambda: result.append(
                diarizer.identify_speaker(buyedektir.np.zeros(160, dtype=buyedektir.np.int16))
            ),
            daemon=True,
        )
        try:
            worker.start()
            check(entered.wait(timeout=3), 'diarization worker baslamadi')
            diarizer.reset()
            release.set()
            worker.join(timeout=2)
            check(result == [(None, None)], f'reset eski sonucu iptal etmedi: {result}')
            check(diarizer.speaker_names == {},
                  f'reset sonrasi profil yeniden olustu: {diarizer.speaker_names}')
            with open(diarizer.profile_file, encoding='utf-8') as profile_stream:
                profile = json.load(profile_stream)
            check(profile == {'names': {}},
                  'reset sonrasi bos profil korunmadi veya token alani yazildi')
        finally:
            release.set()
            worker.join(timeout=2)


def test_verified_report_regressions():
    """19/15 Eylul raporlarindan dogrulanan API ve dil regresyonlari."""
    client = make_client()
    transcriber = buyedektir.transcriber
    responder = transcriber.openai_responder

    unauth = buyedektir.socketio.test_client(buyedektir.app)
    check(not unauth.is_connected(), 'tokensiz Socket.IO baglantisi kabul edildi')
    auth = buyedektir.socketio.test_client(
        buyedektir.app, auth={'token': buyedektir.APP_TOKEN})
    check(auth.is_connected(), 'tokenli Socket.IO baglantisi reddedildi')
    auth.disconnect()

    check(transcriber._detect_script_lang('This is a long Latin sentence with Я') is None,
          'tek yabanci harf Latin metnin dilini ele gecirdi')
    check(transcriber._detect_script_lang('こんにちは世界', 'ja') == 'ja',
          'gercek Japonca script algilanmadi')

    old_translation = transcriber.translator.snapshot_request()
    with responder._config_lock:
        old_key = responder.translation_api_keys.get('anthropic')
        responder.translation_api_keys['anthropic'] = 'keep-me'
    try:
        invalid = client.post('/api/translation_settings', json={
            'provider': 'anthropic', 'enabled': 'false',
            'sourceLang': 'TR', 'targetLang': ['JA']
        })
        check(invalid.status_code == 400, 'gecersiz ceviri ayari kabul edildi')
        valid = client.post('/api/translation_settings', json={
            'provider': 'anthropic', 'enabled': True,
            'sourceLang': 'TR', 'targetLang': 'JA'
        })
        check(valid.status_code == 200, 'gecerli ceviri ayari reddedildi')
        check(responder.translation_api_keys['anthropic'] == 'keep-me',
              'apiKey alani olmayan ayar mevcut Claude anahtarini sildi')
        key_status = client.get('/api/status').get_json()['translation_key_available']
        check(key_status.get('anthropic') is True,
              'backend ceviri anahtari varligi UI durumuna tasinmadi')
    finally:
        with transcriber.translator._config_lock:
            transcriber.translator.enabled = old_translation['enabled']
            transcriber.translator.provider = old_translation['provider']
            transcriber.translator.source_lang = old_translation['source_lang']
            transcriber.translator.target_lang = old_translation['target_lang']
        with responder._config_lock:
            responder.translation_api_keys['anthropic'] = old_key

    bad_text = client.post('/api/generate_ai_response', json={
        'text': 123, 'mode': 'answer', 'target_lang': 'ja'})
    bad_lang = client.post('/api/generate_ai_response', json={
        'text': 'Merhaba', 'mode': 'answer', 'target_lang': ['ja']})
    check(bad_text.status_code == 400 and not bad_text.get_json()['success'],
          'string olmayan AI metni kontrollu reddedilmedi')
    check(bad_lang.status_code == 400, 'string olmayan hedef dil kontrollu reddedilmedi')

    saved_answer = responder.answer_question
    saved_response_key = responder.api_key
    saved_context = transcriber.get_translation_context
    context_ids = []
    responder.api_key = 'test-key'
    responder.answer_question = lambda *_a, **_k: {'response': json.dumps({
        'translation': 'Hello', 'turkish': 'Merhaba', 'romanized': 'helo',
        'detected_lang': 'tr'
    })}
    transcriber.get_translation_context = lambda before_id: context_ids.append(before_id) or ''
    try:
        invalid_context = client.post('/api/generate_ai_response', json={
            'text': 'Merhaba', 'mode': 'translate_dual', 'target_lang': 'en',
            'transcript_id': 'gecersiz'
        })
        check(invalid_context.status_code == 200 and context_ids == [],
              'gecersiz transcript_id onceki kaydi baglama katti')
        numeric_context = client.post('/api/generate_ai_response', json={
            'text': 'Merhaba', 'mode': 'translate_dual', 'target_lang': 'en',
            'transcript_id': '42'
        })
        check(numeric_context.status_code == 200 and context_ids == [42],
              'sayisal string transcript_id kontrollu int olarak kullanilmadi')
    finally:
        responder.answer_question = saved_answer
        responder.api_key = saved_response_key
        transcriber.get_translation_context = saved_context

    with responder._config_lock:
        old_provider = responder.response_provider
        old_anthropic_key = responder.anthropic_api_key
        responder.response_provider = 'anthropic'
        responder.anthropic_api_key = 'claude-only'
    old_answer = responder.answer_question
    with transcriber._lifecycle_lock:
        old_records = list(transcriber.transcriptions)
        transcriber.transcriptions.clear()
        transcriber.transcriptions.append({
            'id': 999001, 'source': 'system', 'text': 'Hello there'
        })
    responder.answer_question = lambda *_a, **_k: {'response': 'Kısa özet'}
    try:
        chat = client.post('/api/ai_chat', json={'action': 'summary'}).get_json()
        check(chat.get('success') is True and chat.get('response') == 'Kısa özet',
              'Claude-only kullanicida ai_chat kapali kaldi')
    finally:
        responder.answer_question = old_answer
        with responder._config_lock:
            responder.response_provider = old_provider
            responder.anthropic_api_key = old_anthropic_key
        with transcriber._lifecycle_lock:
            transcriber.transcriptions.clear()
            transcriber.transcriptions.extend(old_records)

    old_running = transcriber.is_running
    old_ptt = transcriber.ptt_active
    old_sequences = dict(transcriber._ptt_sequences)
    old_retired = {
        source: buyedektir.deque(clients, maxlen=clients.maxlen)
        for source, clients in transcriber._ptt_retired_clients.items()
    }
    try:
        transcriber.is_running = True
        client.post('/api/ptt', json={
            'active': False, 'source': 'smoke', 'sequence': 2,
            'client': 'first-page'})
        stale = client.post('/api/ptt', json={
            'active': True, 'source': 'smoke', 'sequence': 1,
            'client': 'first-page'}).get_json()
        check(stale.get('stale') is True and transcriber.ptt_active is False,
              'gecikmis PTT start komutu stop sonrasinda uygulandi')
        reloaded = client.post('/api/ptt', json={
            'active': True, 'source': 'smoke', 'sequence': 1,
            'client': 'reloaded-page'}).get_json()
        check(reloaded.get('stale') is not True and transcriber.ptt_active is True,
              'sayfa yenilendikten sonra PTT komutu stale sayildi')
        old_stop = client.post('/api/ptt', json={
            'active': False, 'source': 'smoke', 'sequence': 3,
            'client': 'first-page'}).get_json()
        check(old_stop.get('stale') is True and transcriber.ptt_active is True,
              'eski sayfanin gec stop komutu yeni sayfanin PTT tutusunu kesti')
        old_start = client.post('/api/ptt', json={
            'active': True, 'source': 'smoke', 'sequence': 4,
            'client': 'first-page'}).get_json()
        check(old_start.get('stale') is True and transcriber.ptt_active is True,
              'emekli sayfanin gec start komutu PTT sahipligini geri aldi')
        client.post('/api/ptt', json={
            'active': False, 'source': 'smoke', 'sequence': 2,
            'client': 'reloaded-page'})
        check(transcriber.ptt_active is False,
              'yeni sayfanin stop komutu uygulanmadi')
    finally:
        transcriber.is_running = old_running
        transcriber.ptt_active = old_ptt
        transcriber._ptt_sequences = old_sequences
        transcriber._ptt_retired_clients = old_retired


def test_anthropic_provider_contract():
    """Claude secimi, ayrik anahtarlar ve Messages sozlesmesi agsiz dogrulanir."""
    responder = buyedektir.OpenAIResponder()
    check(responder.set_response_provider('anthropic'), 'Claude cevap saglayicisi secilemedi')
    check(not responder.set_response_provider('unknown'), 'gecersiz AI saglayicisi kabul edildi')
    check(responder.set_response_model('claude-sonnet-4-6'), 'Claude cevap modeli secilemedi')
    check(responder.set_model('claude-haiku-4-5-20251001'), 'Claude ceviri modeli secilemedi')
    with responder._config_lock:
        responder.anthropic_api_key = 'response-only-key'
        responder.api_key = 'openai-response-key'
    responder.configure_translation('anthropic', 'translation-only-key')
    queued = responder.snapshot_translation_request('anthropic')
    check(queued['api_key'] == 'translation-only-key', 'Claude ceviri anahtari snapshotta yok')
    check(responder.anthropic_api_key == 'response-only-key',
          'Claude ceviri anahtari cevap anahtarini ezdi')
    calls = []
    original_post = buyedektir._http_session.post
    class FakeResponse:
        status_code = 200
        text = ''
        @staticmethod
        def json():
            return {'content': [{'type': 'text', 'text': '{"ok":true}'}],
                    'usage': {'input_tokens': 10, 'output_tokens': 4}}
    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()
    try:
        buyedektir._http_session.post = fake_post
        answer = responder.answer_question('Merhaba', json_mode=True)
        translation = responder.answer_question(
            'Cevir', model_type='translation', translation_snapshot=queued)
        check(answer and answer['response'] == '{"ok":true}' and
              answer['source'] == 'anthropic', 'Claude cevap ayrismasi basarisiz')
        check(translation and translation['source'] == 'anthropic',
              'Claude ceviri snapshoti cagrilmadi')
        check(len(calls) == 2, f'Claude cagri sayisi yanlis: {len(calls)}')
        for url, kwargs in calls:
            check(url == buyedektir._ANTHROPIC_MESSAGES_URL,
                  'Claude resmi Messages endpointine gitmedi')
            check(kwargs['headers'].get('anthropic-version') == '2023-06-01',
                  'Claude API surum basligi eksik')
            check('Authorization' not in kwargs['headers'],
                  'Claude anahtari OpenAI Authorization basligina girdi')
            check('system' in kwargs['json'] and
                  kwargs['json']['messages'][0]['role'] == 'user' and
                  'max_tokens' in kwargs['json'] and
                  'response_format' not in kwargs['json'],
                  'Claude Messages govdesi gecersiz')
        check(calls[0][1]['headers']['x-api-key'] == 'response-only-key',
              'Claude cevap anahtari kullanilmadi')
        check(calls[1][1]['headers']['x-api-key'] == 'translation-only-key',
              'Claude ceviri anahtari karisti')
        check(responder.session_tokens['total'] == 28,
              'Claude input/output token sayaci yanlis')
    finally:
        buyedektir._http_session.post = original_post


def main():
    for fn in (test_pronunciation, test_hallucination, test_answer_contract,
               test_conversation_tools_contract,
               test_auto_mode_style_narrowing, test_bidirectional_conversation_memory,
               test_settings_bounds, test_salvage, test_serialized_file_writes,
               test_partial_emit_session_guard,
               test_stable_partial_and_glossary_contract,
               test_shared_state_snapshots_are_isolated,
               test_pause_and_flush_contract,
               test_mic_frame_snapshot_and_translation_workers,
               test_diarization_is_late_and_nonblocking,
               test_transcription_id_survives_clear,
               test_segment_join_and_speech_onset,
               test_clear_capture_generation,
               test_translation_backlog, test_resample_clip, test_partial_snapshot_cap,
               test_quiet_split_index,
               test_max_utterance_forced_flush, test_max_ptt_forced_flush,
               test_api_token_and_model_load_lock,
               test_ai_request_rate_limit,
               test_ai_chat_validation_and_identity,
               test_transkribe_helpers,
               test_capture_open_after_stop_is_stale,
               test_ai_config_tests_connection_once,
               test_openai_compatible_reseller_config,
               test_anthropic_provider_contract,
               test_translation_provider_snapshot_is_immutable,
               test_translation_settings_snapshot_is_atomic,
               test_speaker_reset_invalidates_inflight_result,
               test_verified_report_regressions):
        print(f"-> {fn.__name__}")
        try:
            fn()
        except Exception as e:
            _failures.append(f"{fn.__name__} ISTISNA: {e}")
            print(f"  ISTISNA: {e}")
    print()
    if _failures:
        print(f"BASARISIZ: {len(_failures)} sorun")
        return 1
    # Eski rapor turlarindaki ayrik unittest dosyalari geriye donuk kanit olarak
    # archive'de kalir; kalici tek giris noktasi yine bu smoke komutudur.
    archive_dir = os.path.join(os.path.dirname(__file__), 'tests', 'archive')
    archived_suites = tuple(
        os.path.join(archive_dir, name) for name in (
            'test_complete_audit.py',
            'test_followup_regressions.py',
            'test_fourth_report.py',
            'test_new_report.py',
            'test_report_regressions.py',
            'test_third_report.py',
        )
    ) + (
        # Es-zamanlilik/lifecycle audit paketi tests/ altinda kalici durur.
        os.path.join(os.path.dirname(__file__), 'tests', 'test_concurrency_audit.py'),
    )
    child_env = os.environ.copy()
    child_env['PYTHONPATH'] = os.path.dirname(__file__) + os.pathsep + child_env.get('PYTHONPATH', '')
    for path in archived_suites:
        suite = os.path.relpath(path, os.path.dirname(__file__))
        print(f"-> {suite}")
        result = subprocess.run([sys.executable, path], cwd=os.path.dirname(__file__),
                                env=child_env, check=False)
        if result.returncode:
            print(f"BASARISIZ: {suite} cikis kodu {result.returncode}")
            return result.returncode
    print("TUM TESTLER GECTI")
    return 0


if __name__ == '__main__':
    sys.exit(main())
