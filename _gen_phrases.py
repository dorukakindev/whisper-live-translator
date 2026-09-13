#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Hazir kalip cumle paketini uretir: okunuslari buyedektir.py'nin
_normalize_turkish_pronunciation motorundan gecirir (elle yazma yok -> tutarli).
Cikti: QUICK_PHRASES JS objesi (index.html'e gomulecek)."""
import io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import buyedektir as B
N = B._normalize_turkish_pronunciation

# Turkce etiketler (kullaniciya gosterilen "ne demek")
LABELS = [
    "Merhaba", "Teşekkür ederim", "Evet", "Hayır", "Anlamadım",
    "Tekrar eder misin?", "Biraz yavaş konuşur musun?", "Bir saniye lütfen",
    "Memnun oldum", "Affedersiniz",
    "Nasılsın?", "İyiyim, ya sen?", "Adın ne?", "Nerelisin?", "Rica ederim",
    "Görüşürüz", "Tamam", "Yardım eder misin?",
]

# Her dil icin: (soylenecek YEREL metin [TTS bunu okur], okunus_girdisi [N'e verilecek fonetik/yerel])
# Latin yazili dillerde okunus_girdisi = yerel metin; Latin-disi (ja/ko/zh/ar/ru) icin romanize girdi.
DATA = {
    'ja': [
        ('こんにちは', 'konnichiwa'), ('ありがとうございます', 'arigatou gozaimasu'),
        ('はい', 'hai'), ('いいえ', 'iie'), ('わかりません', 'wakarimasen'),
        ('もう一度お願いします', 'mou ichido onegaishimasu'),
        ('ゆっくり話してください', 'yukkuri hanashite kudasai'),
        ('ちょっと待ってください', 'chotto matte kudasai'),
        ('はじめまして', 'hajimemashite'), ('すみません', 'sumimasen'),
        ('元気ですか？', 'genki desu ka'), ('元気です、あなたは？', 'genki desu, anata wa'),
        ('お名前は？', 'onamae wa'), ('どこから来ましたか？', 'doko kara kimashita ka'),
        ('どういたしまして', 'douitashimashite'), ('またね', 'mata ne'),
        ('大丈夫です', 'daijoubu desu'), ('手伝ってくれますか？', 'tetsudatte kuremasu ka'),
    ],
    'en': [
        ('Hello', 'helov'), ('Thank you', 'tenk yu'), ('Yes', 'yes'), ('No', 'nov'),
        ("I don't understand", 'ay dont andırstend'), ('Can you repeat that?', 'ken yu ripiit dat'),
        ('Can you speak slowly?', 'ken yu spiik slovli'), ('One moment please', 'van moment pliiz'),
        ('Nice to meet you', 'nays tu miit yu'), ('Excuse me', 'ikskyuz mi'),
        ('How are you?', 'hav ar yu'), ("I'm good, and you?", 'aym gud end yu'),
        ("What's your name?", 'vats yor neym'), ('Where are you from?', 'ver ar yu from'),
        ("You're welcome", 'yor velkım'), ('See you', 'sii yu'),
        ('OK', 'okey'), ('Can you help me?', 'ken yu help mi'),
    ],
    'es': [
        ('Hola', 'Hola'), ('Gracias', 'Gracias'), ('Sí', 'Si'), ('No', 'No'),
        ('No entiendo', 'No entiendo'), ('¿Puedes repetir?', 'Puedes repetir'),
        ('¿Puedes hablar más despacio?', 'Puedes hablar mas despacio'),
        ('Un momento por favor', 'Un momento por favor'),
        ('Mucho gusto', 'Mucho gusto'), ('Perdón', 'Perdon'),
        ('¿Cómo estás?', 'Como estas'), ('Bien, ¿y tú?', 'Bien y tu'),
        ('¿Cómo te llamas?', 'Como te llamas'), ('¿De dónde eres?', 'De donde eres'),
        ('De nada', 'De nada'), ('Hasta luego', 'Hasta luego'),
        ('Vale', 'Vale'), ('¿Puedes ayudarme?', 'Puedes ayudarme'),
    ],
    'de': [
        ('Hallo', 'Hallo'), ('Danke schön', 'Danke schoen'), ('Ja', 'Ja'), ('Nein', 'Nein'),
        ('Ich verstehe nicht', 'Ich verstehe nicht'), ('Kannst du das wiederholen?', 'Kannst du das wiederholen'),
        ('Kannst du langsamer sprechen?', 'Kannst du langsamer sprechen'),
        ('Einen Moment bitte', 'Einen Moment bitte'),
        ('Freut mich', 'Freut mich'), ('Entschuldigung', 'Entschuldigung'),
        ("Wie geht's?", 'Wie gehts'), ('Gut, und dir?', 'Gut und dir'),
        ('Wie heißt du?', 'Wie heisst du'), ('Woher kommst du?', 'Woher kommst du'),
        ('Gern geschehen', 'Gern geschehen'), ('Bis später', 'Bis spaeter'),
        ('Okay', 'Okay'), ('Kannst du mir helfen?', 'Kannst du mir helfen'),
    ],
    'fr': [
        ('Bonjour', 'bonjur'), ('Merci', 'mersi'), ('Oui', 'vi'), ('Non', 'non'),
        ('Je ne comprends pas', 'jö nö kompron pa'), ('Tu peux répéter?', 'tü pö repete'),
        ('Tu peux parler lentement?', 'tü pö parle lantman'), ('Un moment, s’il te plaît', 'an moman sil tö ple'),
        ('Enchanté', 'anşante'), ('Excuse-moi', 'eksküz mua'),
        ('Ça va?', 'sa va'), ('Bien, et toi?', 'byan e tua'),
        ("Comment tu t'appelles?", 'koman tü tapel'), ("Tu viens d'où?", 'tü vyan du'),
        ('De rien', 'dö ryan'), ('À bientôt', 'a byanto'),
        ("D'accord", 'dakor'), ("Tu peux m'aider?", 'tü pö mede'),
    ],
    'it': [
        ('Ciao', 'Ciao'), ('Grazie', 'Grazie'), ('Sì', 'Si'), ('No', 'No'),
        ('Non capisco', 'Non capisco'), ('Puoi ripetere?', 'Puoi ripetere'),
        ('Puoi parlare più lentamente?', 'Puoi parlare piu lentamente'),
        ('Un momento per favore', 'Un momento per favore'),
        ('Piacere', 'Piacere'), ('Scusa', 'Scusa'),
        ('Come stai?', 'Come stai'), ('Bene, e tu?', 'Bene e tu'),
        ('Come ti chiami?', 'Come ti chiami'), ('Di dove sei?', 'Di dove sei'),
        ('Prego', 'Prego'), ('A presto', 'A presto'),
        ('Va bene', 'Va bene'), ('Puoi aiutarmi?', 'Puoi aiutarmi'),
    ],
    'pt': [
        ('Olá', 'Ola'), ('Obrigado', 'Obrigado'), ('Sim', 'Sim'), ('Não', 'Nao'),
        ('Não entendo', 'Nao entendo'), ('Pode repetir?', 'Pode repetir'),
        ('Pode falar devagar?', 'Pode falar devagar'), ('Um momento por favor', 'Um momento por favor'),
        ('Prazer', 'Prazer'), ('Desculpe', 'Desculpe'),
        ('Como está?', 'Como esta'), ('Bem, e você?', 'Bem e voce'),
        ('Como se chama?', 'Como se chama'), ('De onde é?', 'De onde e'),
        ('De nada', 'De nada'), ('Até logo', 'Ate logo'),
        ('Está bem', 'Esta bem'), ('Pode me ajudar?', 'Pode me ajudar'),
    ],
    'ru': [
        ('Здравствуйте', 'zdrastvuyte'), ('Спасибо', 'spasiba'), ('Да', 'da'), ('Нет', 'nyet'),
        ('Я не понимаю', 'ya nye panimayu'), ('Повторите, пожалуйста', 'paftarite pajalsta'),
        ('Говорите медленнее, пожалуйста', 'gavarite myedlenneye pajalsta'),
        ('Одну минуту', 'adnu minutu'), ('Очень приятно', 'oçin priyatna'), ('Извините', 'izvinite'),
        ('Как дела?', 'kak dela'), ('Хорошо, а у тебя?', 'haraşo a u tebya'),
        ('Как тебя зовут?', 'kak tebya zavut'), ('Откуда ты?', 'atkuda tı'),
        ('Пожалуйста', 'pajalsta'), ('До свидания', 'da svidaniya'),
        ('Хорошо', 'haraşo'), ('Можешь помочь?', 'mojeş pamoç'),
    ],
    'ko': [
        ('안녕하세요', 'annyeonghaseyo'), ('감사합니다', 'kamsahamnida'), ('네', 'ne'), ('아니요', 'aniyo'),
        ('이해하지 못했어요', 'ihaehaji mothaesseoyo'), ('다시 말해 주세요', 'dasi malhae juseyo'),
        ('천천히 말해 주세요', 'cheoncheonhi malhae juseyo'), ('잠시만요', 'jamsimanyo'),
        ('반갑습니다', 'bangapseumnida'), ('실례합니다', 'sillyehamnida'),
        ('어떻게 지내세요?', 'eotteoke jinaeseyo'), ('잘 지내요', 'jal jinaeyo'),
        ('이름이 뭐예요?', 'ireumi mwoyeyo'), ('어디에서 왔어요?', 'eodieseo wasseoyo'),
        ('천만에요', 'cheonmaneyo'), ('또 봐요', 'tto bwayo'),
        ('네, 좋아요', 'ne, joayo'), ('도와줄 수 있어요?', 'dowajul su isseoyo'),
    ],
    'zh': [
        ('你好', 'ni hao'), ('谢谢', 'şie şie'), ('是', 'şı'), ('不是', 'bu şı'),
        ('我不明白', 'vo bu mingbay'), ('请再说一遍', 'çing dzay şuo yibyen'),
        ('请说慢一点', 'çing şuo man yidyen'), ('请稍等', 'çing şao dıng'),
        ('很高兴认识你', 'hın gaoşing rınşı ni'), ('对不起', 'duy bu çi'),
        ('你好吗？', 'ni hao ma'), ('我很好，你呢？', 'vo hın hao, ni nı'),
        ('你叫什么名字？', 'ni cyao şınme mingdzı'), ('你是哪里人？', 'ni şı nali rın'),
        ('不客气', 'bu kıçi'), ('再见', 'dzaycyen'),
        ('好的', 'hao dı'), ('你能帮我吗？', 'ni nıng bang vo ma'),
    ],
    'ar': [
        ('مرحبا', 'marhaba'), ('شكرا', 'shukran'), ('نعم', 'naam'), ('لا', 'la'),
        ('لا أفهم', 'la afham'), ('ممكن تعيد؟', 'mumkin tiid'),
        ('احكي شوي شوي', 'ihki şvay şvay'), ('لحظة من فضلك', 'lahza min fadlak'),
        ('تشرفنا', 'tasharrafna'), ('عفوا', 'afwan'),
        ('كيف حالك؟', 'kif halak'), ('بخير، وأنت؟', 'biheyr, vinta'),
        ('ما اسمك؟', 'ma ismak'), ('من أين أنت؟', 'min eyn inta'),
        ('العفو', 'al afw'), ('مع السلامة', 'maa salama'),
        ('تمام', 'tamam'), ('ممكن تساعدني؟', 'mumkin tsaidni'),
    ],
}

out = {}
for lang, items in DATA.items():
    arr = []
    for (translation, okunus_in) in items:
        ok = N(okunus_in, lang)
        arr.append({'t': translation, 'o': ok})
    out[lang] = arr

# Etiketleri dile ekle (her dilde ayni sirada)
result = {}
for lang, arr in out.items():
    result[lang] = [{'tr': LABELS[i], 't': e['t'], 'o': e['o']} for i, e in enumerate(arr)]

# Insan-okunabilir onizleme
for lang in result:
    print(f"\n=== {lang} ===")
    for e in result[lang]:
        print(f"  {e['tr']:<24} | {e['t']:<28} | {e['o']}")

# JS ciktisi (ayri dosyaya)
with io.open('_quick_phrases.json', 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=0)
print("\n[_quick_phrases.json yazildi]")
