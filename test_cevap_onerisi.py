#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Okunuş kalitesi eval seti — GERÇEK OpenAI API'sini çağırır, ücretlidir.

`test_smoke.py`'nin aksine bu dosya pytest/CI'da OTOMATİK ÇALIŞMAZ: canlı bir
API anahtarı gerektirir ve her çalıştırmada gerçek para harcar. Prompt/okunuş
kuralları değiştirdikten sonra ELLE çalıştırılıp regresyon var mı bakılır.

Eskiden bu dosya buyedektir.py'deki prompt kurulumunu exec() ile KOPYALAYIP
yeniden inşa ediyordu — kod değiştikçe bu kopya ESKİYORDU (buyedektir.py'ye
yapılan bir değişiklik burada yansımayabiliyordu). Artık buyedektir modülünü
DOĞRUDAN import edip Flask test client ile GERÇEK /api/generate_ai_response
route'unu çağırıyor; test edilen kod ile üretimdeki kod HER ZAMAN aynı.

Ayrıca eskiden yalnız insan gözüyle okumak için sonuçları basıyordu. Şimdi her
cevap seçeneği otomatik kontrollerden geçiyor: Türkçe sızıntısı var mı, tire
kuralı ihlal edilmiş mi, okunuşta yabancı script (kanji/Arapça/Kiril/...)
kalmış mı. Sonunda TÜM TESTLER GEÇTİ / N SORUN formatında özet + exit code.

Çalıştır:  python test_cevap_onerisi.py
Çıkış kodu: hepsi geçerse 0, bir sorun varsa 1.
"""
import io
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("buyedektir import ediliyor (yavaş olabilir, ~5-40sn)...")
import buyedektir

app = buyedektir.app
transcriber = buyedektir.transcriber
responder = transcriber.openai_responder

if not responder.api_key:
    sys.exit(
        "OPENAI_API_KEY bulunamadı (.env dosyasına ekleyin veya ortam değişkeni "
        "olarak tanımlayın). Bu script gerçek API'yi çağırdığı için anahtar şart."
    )

_failures = []


def check(cond, msg):
    if not cond:
        _failures.append(msg)
        print(f"  FARK: {msg}")


# ── Türkçe sızıntı sezgisi ──────────────────────────────────────────
# 'translation' alanı hedef dilde olmalı; model bazen (özellikle meta
# mesajlarda) yanlışlıkla TÜRKÇE üretiyor (buyedektir.py'deki 'MUTLAK DIL
# KURALI' yorumunun bahsettiği bilinen hata). Bu kelimeler Türkçeye özgü ve
# hedef dildeki gerçek bir cümlede rastlantıyla geçmesi son derece
# olasılık dışı; geçerlerse güçlü bir Türkçe-sızıntı işaretidir.
_TR_TELLS = (
    'değil', 'çok', 'teşekkür', 'merhaba', 'nasılsın', 'evet', 'hayır',
    'iyiyim', 'görüşürüz', 'lütfen', 'tamam mı', 'ne haber',
)


def turkish_leak_words(text):
    low = str(text or '').lower()
    return [w for w in _TR_TELLS if w in low]


# Yunanca script aralığı: _detect_script_lang bunu KAPSAMIYOR (sadece
# ja/zh/ko/ar/he/th/hi/ka/cyr taniyor), bu yüzden ayrı kontrol.
_GREEK_RE = re.compile(r'[Ͱ-Ͽ]')


def foreign_script_lang(text):
    """Metinde baskın yabancı script varsa dil kodu, yoksa None döner.
    buyedektir'in kendi script-tespit mantığını (_detect_script_lang) yeniden
    kullanır — ayrı bir tespit tablosu icat etmek yerine üretim kodunun
    KENDİSİYLE tutarlı kalır."""
    detected = transcriber._detect_script_lang(text)
    if detected:
        return detected
    if _GREEK_RE.search(str(text or '')):
        return 'el'
    return None


# ── Altın küme: her dil için gerçekçi bir "karşı taraf ne dedi" mesajı ──
# (dil, mesaj, ton). auto+script vakaları B5'in (script-tespitli stil
# daraltma) canlı API üzerinden de doğru çalıştığını sınar.
GOLDEN_CASES = [
    ('ja', '今日はどこに行きましたか？', 'arkadasca'),
    ('ar', 'شو عم تعمل هلق؟', 'arkadasca'),
    ('zh', '你今天吃饭了吗？', 'arkadasca'),
    ('ru', 'Как прошёл твой день?', 'arkadasca'),
    ('es', '¿Qué planes tienes para el fin de semana?', 'arkadasca'),
    ('en', 'What do you think about this idea?', 'arkadasca'),
    ('de', 'Wie war dein Tag heute?', 'arkadasca'),
    ('fr', "Qu'est-ce que tu fais ce soir?", 'arkadasca'),
    ('ko', '오늘 뭐 했어요?', 'arkadasca'),
    ('it', 'Cosa hai fatto oggi?', 'arkadasca'),
    ('pt', 'O que você vai fazer amanhã?', 'arkadasca'),
    ('el', 'Τι κάνεις σήμερα;', 'arkadasca'),
    ('sk', 'Ako sa máš dnes?', 'arkadasca'),
    ('da', 'Hvordan har du det i dag?', 'arkadasca'),
    ('sv', 'Vad gjorde du igår?', 'arkadasca'),
    ('fi', 'Mitä teit tänään?', 'arkadasca'),
    ('ka', 'რას აკეთებ დღეს?', 'arkadasca'),
    ('ja', 'お仕事について教えてください。', 'resmi'),  # resmi ton varyasyonu
    ('auto', '元気ですか？今日は何してましたか？', 'arkadasca'),  # B5: script'ten ja tespiti
    ('auto', 'كيف حالك اليوم؟', 'arkadasca'),  # B5: script'ten ar tespiti
]


def run_case(lang, message, tone):
    label = f"{lang}/{tone}: {message[:40]}"
    print(f"\n{'=' * 70}\n{label}")
    client = app.test_client()
    client.environ_base['HTTP_X_WHISPER_TOKEN'] = buyedektir.APP_TOKEN
    r = client.post('/api/generate_ai_response', json={
        'text': message, 'mode': 'answer', 'target_lang': lang, 'tone': tone,
    }).get_json()

    if not r.get('success'):
        check(False, f"[{label}] istek başarısız: {r.get('error')}")
        return

    options = r.get('options') or []
    check(len(options) >= 1, f"[{label}] hiç seçenek dönmedi")
    if not options:
        return

    # auto modda modelin GERÇEKTEN tespit ettiği dil; tire/script kontrolleri
    # o dile göre yapılmalı (hedef 'auto' kelimesinin kendisine göre değil).
    effective_lang = r.get('detected_lang') or lang
    if lang == 'auto':
        print(f"  (auto -> tespit edilen dil: {effective_lang!r})")

    for i, opt in enumerate(options, 1):
        translation = opt.get('translation', '') or ''
        romanized = opt.get('romanized', '') or ''
        print(f"  {i}. {translation}")
        print(f"     Okunuş: {romanized}")

        check(bool(translation.strip()), f"[{label}] seçenek {i}: translation boş")
        check(bool(romanized.strip()), f"[{label}] seçenek {i}: romanized boş")

        # Tire kuralı: yalnız Japonca'da tire beklenir/serbesttir; diğer TÜM
        # dillerde ASLA tire olmamalı (buyedektir.py'nin kendi kuralı).
        if effective_lang != 'ja' and '-' in romanized:
            check(False, f"[{label}] seçenek {i}: tire kuralı ihlal edildi (ja değil): {romanized!r}")

        # Okunuşta yabancı script kalmamalı (normalizasyon transliterasyonu
        # tamamlayamamış demektir — kullanıcı okuyamaz).
        leaked_script = foreign_script_lang(romanized)
        check(leaked_script is None,
              f"[{label}] seçenek {i}: okunuşta yabancı script kaldı "
              f"({leaked_script}): {romanized!r}")

        # Çince ton işareti/oku sızıntısı (ekstra güvenlik ağı).
        check(not re.search(r'[↗↘→]|[0-9](?=[a-zA-Zçşğıöü])', romanized),
              f"[{label}] seçenek {i}: okunuşta ton işareti/rakamı kaldı: {romanized!r}")

        # Türkçe sızıntısı: 'translation' hedef dilde olmalı, Türkçe DEĞİL.
        tr_words = turkish_leak_words(translation)
        check(not tr_words,
              f"[{label}] seçenek {i}: translation Türkçe sızıntısı içeriyor "
              f"{tr_words}: {translation!r}")

        # Script-tabanlı diller icin translation GERÇEKTEN o script'te mi?
        script_langs = {'ja', 'zh', 'ar', 'ko', 'ru', 'el', 'ka'}
        if effective_lang in script_langs:
            detected = foreign_script_lang(translation)
            # ru/ka gibi bazilari cyr/ka donerken tam kod eslesmeyebilir
            # (orn. cyr->'ru'); en azindan HERHANGI bir script tespit
            # edilmis olmasi yeterli (Latin/ASCII kalmamis demektir).
            check(detected is not None,
                  f"[{label}] seçenek {i}: translation {effective_lang} script'inde "
                  f"görünmüyor (Türkçe/İngilizce sızıntısı olabilir): {translation!r}")


def main():
    for lang, message, tone in GOLDEN_CASES:
        try:
            run_case(lang, message, tone)
        except Exception as e:
            _failures.append(f"{lang}/{message[:30]} İSTİSNA: {e}")
            print(f"  İSTİSNA: {e}")

    print(f"\n{'=' * 70}")
    if _failures:
        print(f"BAŞARISIZ: {len(_failures)} sorun")
        return 1
    print("TÜM TESTLER GEÇTİ")
    return 0


if __name__ == '__main__':
    sys.exit(main())
