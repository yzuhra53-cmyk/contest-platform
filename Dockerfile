FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# g++ — talabalarning C++17 kodini kompilyatsiya qilish uchun.
# libpq5 — PostgreSQL drayveri (psycopg) uchun.
# util-linux — prlimit: talaba kodining protsessor vaqti va xotirasini cheklaydi.
RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ libpq5 util-linux \
    && rm -rf /var/lib/apt/lists/*

# Talaba kodi shu huquqsiz foydalanuvchi nomidan ishga tushadi (judge.py: JUDGE_RUN_USER).
RUN useradd --system --uid 10000 --no-create-home --shell /usr/sbin/nologin runner

# <bits/stdc++.h> ni oldindan kompilyatsiya qilish: Render'ning kuchsiz CPU'sida
# C++ kompilyatsiyasini bir necha barobar tezlashtiradi.
# Bayroqlar judge.py dagi CXX_FLAGS bilan bir xil bo'lishi shart.
RUN H="$(find /usr/include -path '*bits/stdc++.h' | head -n 1)"; \
    if [ -n "$H" ]; then g++ -std=c++17 -O2 -x c++-header "$H" -o "$H.gch" || true; fi

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Ilova kodi faqat root uchun: talaba kodi (runner) uni o'qiy olmaydi.
RUN chmod 700 /app

# Server root sifatida ishlaydi — judge talaba kodini `runner` ga tushirishi uchun kerak.
# --workers 1: tekshiruv navbati (JUDGE_MAX_PARALLEL) bitta jarayon ichida boshqariladi.
# --timeout 180: 20 ta test x 2 soniya + kompilyatsiya so'rov ichida bajariladi.
CMD ["sh", "-c", "exec gunicorn app:app --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 8 --timeout 180"]
