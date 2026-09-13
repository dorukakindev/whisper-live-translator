#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Flask uygulamasını başlatan script
"""
import subprocess
import sys
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("WHISPER + KIMI-K2.5 UYGULAMASI BASLATILIYOR")
print("=" * 60)
print()
print("[INFO] Flask uygulamasi baslatiliyor...")
print("[INFO] Tarayici adresi: http://localhost:5000")
print("[INFO] Durmak icin: Ctrl+C")
print()

# buyedektir.py'yi çalıştır
subprocess.run([sys.executable, "buyedektir.py"])
