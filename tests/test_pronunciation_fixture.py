"""Türkçe okunuş (romanization) uygunluk fixture'ı.

Urun amaci: kullanici yabancı dildeki cevabi Turkce okunustan sesli okur.
Bu dosya desteklenen her dil icin temsili sentetik ornegi (yerli yazi +
latinize girdi) normalize hattindan gecirip okunabilirlik sozlesmesini kilitler:

  * her rehber dilde okunus uretilir (bos cikmaz),
  * cikti yalniz Turkce-okunabilir karakterlerden olusur,
  * Japonca hece birlestirme tireleri korunur, diger dillerde kacak tire olmaz,
  * Latin disi alfabe girdisi (script dilleri) okunusa cevrilir,
  * bos/bozuk model ciktisi patlamaz ve sessizce ele alinir,
  * dil degisimi ayni girdiyi farkli kurala gore normallestirir.

Not: bu fixture otomatik olcumdur; dogal telaffuz KALITESINI (anadil kulaginin
degerlendirmesi) kantilamaz — yalnizca sozlesme/regresyon bozulmalarini yakalar.
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
os.environ.setdefault('WHISPER_SKIP_DOTENV', '1')
os.environ['WHISPER_SKIP_API_VERIFY'] = '1'

import buyedektir as b  # noqa: E402

N = b._normalize_turkish_pronunciation
F = b._finalize_pronunciation

GUIDE_LANGS = sorted(b.PRONUNCIATION_GUIDES.keys())

# (dil, latinize veya yerli-yazi girdi) -> beklenen okunus (sabitlenmis)
PINNED = [
    ('ar', 'shukran', 'şukran'),
    ('da', 'mange tak', 'mange tak'),
    ('de', 'danke sehr', 'danke sehr'),
    ('el', 'efharisto poli', 'efharisto poli'),
    ('en', 'thank you very much', 'thank you very much'),
    ('es', 'gracias amigo', 'grasyas amigo'),
    ('fi', 'kiitos paljon', 'kiitos palyon'),
    ('fr', 'merci beaucoup', 'merci beaucoup'),
    ('it', 'grazie mille', 'gratsie mille'),
    ('ja', 'arigatou gozaimasu', 'arigatoo gozaimas'),
    ('ja', 'kore wa', 'kore-va'),            # hece birlestirme tiresi korunur
    ('ja', 'hon wo yomimasu', 'hon-o yomimas'),
    ('ka', 'gmadlobt', 'gmadlobt'),
    ('ko', 'gamsahamnida', 'gamsahamnida'),
    ('pt', 'obrigado', 'obrigadu'),
    ('ru', 'spasibo bolshoye', 'spasibo bolshoye'),
    ('sk', 'djakujem', 'dyakuyem'),
    ('sv', 'tack sa mycket', 'tack sa mycket'),
    ('zh', 'xie xie ni', 'şie şie ni'),
]

# Latin disi yazidan dogrudan okunus ureten script dilleri
NATIVE_PINNED = [
    ('ru', 'что это', 'şto eto'),
    ('el', 'ευχαριστώ', 'efharisto'),
    ('ka', 'მადლობა', 'madloba'),
]

# Bos/bozuk model ciktisi: patlamamali; beklenen davranis sabitlendi.
BROKEN = [
    ('', 'ja', ''),
    ('   ', 'en', ''),
    ('!!!', 'ru', '!!'),
    ('123', 'zh', '123'),
    ('привет', 'en', ''),     # latinize olmayan kiril -> okunus uretemez, bos
    ('みなさん', 'ja', ''),     # kana -> romaji beklenir, bos (belgelenmis)
    ('-kore-', 'ja', '-kore-'),  # kenar tireleri su an korunur (kozmetik, belgelenmis)
]


class PronunciationFixtureTests(unittest.TestCase):
    def test_all_guide_languages_covered_by_samples(self):
        covered = {lang for lang, _inp, _exp in PINNED + NATIVE_PINNED}
        missing = set(GUIDE_LANGS) - covered
        self.assertFalse(missing,
                         f'rehberde olup fixture\'da ornegi olmayan diller: {missing}')

    def test_pinned_outputs(self):
        for lang, inp, expected in PINNED:
            with self.subTest(lang=lang, inp=inp):
                self.assertEqual(N(inp, lang), expected)

    def test_native_script_inputs(self):
        for lang, inp, expected in NATIVE_PINNED:
            with self.subTest(lang=lang, inp=inp):
                self.assertEqual(N(inp, lang), expected)

    def test_output_charset_is_turkish_readable(self):
        """Uretilen okunus sadece sesli okunabilir karakter tasimali."""
        allowed_extra = set(' /-')
        for lang, inp, _exp in PINNED + NATIVE_PINNED:
            out = N(inp, lang)
            with self.subTest(lang=lang, inp=inp):
                for ch in out:
                    if ch in allowed_extra:
                        continue
                    self.assertTrue(b._is_turkish_readable_char(ch),
                                    f'{lang}: okunamayan karakter {ch!r} -> {out!r}')
                self.assertNotIn('  ', out, f'{lang}: cift bosluk -> {out!r}')

    def test_japanese_keeps_hyphens_others_do_not(self):
        ja_out = N('kore wa hon wo yomu', 'ja')
        self.assertIn('-', ja_out, 'Japonca hece tiresi kayboldu')
        for lang in GUIDE_LANGS:
            if lang == 'ja':
                continue
            out = N('kore-wa hon-o', lang)
            with self.subTest(lang=lang):
                self.assertNotIn('-', out,
                                 f'{lang}: tire korunmamali -> {out!r}')

    def test_broken_or_empty_model_output_is_safe(self):
        for inp, lang, expected in BROKEN:
            with self.subTest(lang=lang, inp=inp):
                self.assertEqual(N(inp, lang), expected)
        # >%30 yabanci karakter iceren bozuk cikti finalize'da bosaltilir
        self.assertEqual(F('ありがとうございます'), '')

    def test_language_switch_changes_rules(self):
        """Ayni latinize dizi farkli dilde farkli okunusa donusmeli."""
        out_ja = N('wo', 'ja')
        out_other = N('wo', 'es')
        self.assertNotEqual(out_ja, out_other,
                            'dil degisimi kural farkini yansitmiyor')

    def test_finalize_shared_cleanup(self):
        self.assertEqual(F('ni3 hao3'), 'ni hao')       # ton rakami
        self.assertEqual(F('¿Que tal?'), 'kue tal?')    # ¿/¡ temizligi + q->k
        self.assertEqual(F('whiskey question'), 'viskey kuestion')
        self.assertEqual(F('baaang'), 'baang')          # 3+ harf tekrari
        self.assertEqual(F('   '), '')                  # sadece bosluk

    def test_no_crash_on_adversarial_inputs(self):
        for inp in ['-' * 50, '\x00abc', 'a' * 5000, '…漢字…', '😀emoji😀',
                    '\n\ttab', 'e\u0301', 'hello\u2028world']:
            for lang in ('ja', 'en', 'ru', 'zh'):
                with self.subTest(inp=repr(inp), lang=lang):
                    N(inp, lang)          # patlamamasi yeterli
                    F(inp)


if __name__ == '__main__':
    unittest.main(verbosity=2)
