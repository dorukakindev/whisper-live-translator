import os
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("KIMI_API_KEY"),
    base_url="https://llm.ssilistre.dev/v1"
)

# Test: Turkce cevap + Japonca ceviri + Romanji
text = "I just need to see Messi against Cristiano in the final World Cup."

# 1. Turkce cevap
response = client.chat.completions.create(
    model="kimi-k2.5",
    messages=[{"role": "user", "content": f"Asagidaki metne kisaca Turkce cevap ver:\n{text}"}],
    temperature=0.2, max_tokens=200
)
turkish = response.choices[0].message.content.strip()
print("[Turkce]", turkish)

# 2. Japonca ceviri
trans_response = client.chat.completions.create(
    model="kimi-k2.5",
    messages=[{"role": "user", "content": f"Translate to Japanese. Only the translation:\n{turkish}"}],
    temperature=0.1, max_tokens=300
)
japanese = trans_response.choices[0].message.content.strip()
print("[Japonca]", japanese)

# 3. Romanji
romaji_response = client.chat.completions.create(
    model="kimi-k2.5",
    messages=[{"role": "user", "content": f"Convert to romaji only:\n{japanese}"}],
    temperature=0.1, max_tokens=200
)
romaji = romaji_response.choices[0].message.content.strip()
print("[Romaji]", romaji)
