# Bilim.Arena

Flask, SQLAlchemy va SQLite/PostgreSQL asosidagi olimpiada/test platformasi.

## Mahalliy ishga tushirish

Python 3.13 va `uv` o‘rnatilgan PowerShell oynasida:

```powershell
uv sync
Copy-Item .env.example .env
uv run python app.py
```

Ilova `http://127.0.0.1:5000` manzilida ochiladi. `.env` ichidagi parol va maxfiy kalitni o‘zingizga moslab o‘zgartiring. Ustozning dastlabki lokal login/paroli `Zuhra` / `1211`; talaba HEMIS ID, F.I.O. va guruh ma’lumotlari bazadagi yozuvga mos kelsa kiradi.

Talabalarni ustoz sahifasidan alohida, `.xlsx` yoki `.csv` fayllaridan import qilish mumkin. Jadvalda `HEMIS ID`, `F.I.O`, `Guruh` ustunlari bo‘lishi kerak; Excel faylida sarlavha birinchi qator bo‘lishi shart emas. CSV UTF-8/UTF-8 BOM va Windows-1251 kodlashini, vergul/nuqta-vergul/tab ajratkichlarini qabul qiladi.

Savollar bazasida kod natijasini topish testlari va dasturlash masalalari mavjud. Python 3 yoki C++17 yechimlari Judge0 sozlangandan keyin avtomatik baholanadi. Judge0 manzili va tokenni `.env.example` ga emas, `.env` yoki hosting maxfiy environment variables bo‘limiga kiriting. Vaqt serverda tekshiriladi, ammo masofadan topshirishda internetdan yordam olish yoki boshqa qurilmadan foydalanishni to‘liq texnik yo‘l bilan to‘sib bo‘lmaydi.

## GitHub'ga tayyorlash

Kutubxonalar ro‘yxatini `requirements.txt` ga yozish va keyin yangilash:

```powershell
uv sync
uv export --format requirements-txt --no-dev --output-file requirements.txt
```

`requirements.txt` va `uv.lock` ni GitHub'ga qo‘shing. `.gitignore` virtual muhit, `.idea`, `.env`, SQLite bazalari, yuklangan Excel/CSV fayllar hamda Python keshlarini chetga chiqaradi. Maxfiy ma’lumotlarni repozitoriyga commit qilmang.

Yangi GitHub repozitoriysi yaratilgach, loyiha katalogida:

```powershell
git init
git add .
git status
git commit -m "Prepare Flask contest platform for deployment"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

`git status` natijasida `.env`, `instance/`, `.venv/`, `.idea/`, `.xlsx` yoki `.csv` ko‘rinsa, push qilmang: ignore qoidalarini va staging holatini tekshiring. PyCharm'da muqobil yo‘l: **VCS → Enable Version Control Integration → Git**, commit oynasida fayllarni ko‘rib chiqish, so‘ng **Git → GitHub → Share Project on GitHub** yoki **Push**.

## Render'ga deploy

Bu loyiha **Flask** (Django ham, FastAPI ham emas). `Procfile`, `render.yaml`, `.python-version`, `gunicorn` va `psycopg` Render uchun kiritilgan; Flask statik fayllarni o‘zi tarqatgani uchun WhiteNoise shart emas. `render.yaml` bilan Render Blueprint yaratib GitHub repozitoriysini ulang, `ADMIN_USERNAME` va kuchli `ADMIN_PASSWORD` ni kiriting, keyin deploy qiling. Blueprint PostgreSQL bazasini yaratib, `DATABASE_URL` ni web servisga bog‘laydi. `/health` endpoint bazaga ulanishni tekshiradi.

Ilova ishga tushganda bazada savol bo‘lmasa, `questions_data.json` faylidagi 340 ta test va kod masalasi avtomatik yuklanadi. Bazada kamida bitta savol bo‘lsa, mavjud savollar o‘zgartirilmaydi.

Render boshqaruv panelida `SECRET_KEY` maxfiy qiymat bo‘lishi kerak; Blueprint uni yaratadi. `DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD` va `SECRET_KEY` ni GitHub'ga yozmang. Ilova PostgreSQL `postgres://` va `postgresql://` URL'larini psycopg 3 formatiga moslaydi. `DEBUG` deployda o‘chirilgan; Flask `TRUSTED_HOSTS` ni Render host nomi bilan cheklaydi.

## Bepul hosting va ma’lumotlarni saqlash

Bepul web servislar ko‘pincha faollik bo‘lmaganda uxlaydi yoki resurs/ma’lumotlar saqlanishiga cheklov qo‘yadi. Shuning uchun bepul planda 24/7 ishlash kafolatlanmaydi. Doimiy ishlash uchun provayderning amaldagi rejasini tekshirib, uxlamaydigan servis va doimiy PostgreSQL saqlash rejasini tanlang. Render'ning bepul PostgreSQL muddati/limitlarini deploy vaqtida alohida tekshiring.

SQLite bazasi faqat lokal ishlab chiqish uchun. Deployda `DATABASE_URL` PostgreSQL'ga ulanadi; SQLite fayli `.gitignore` bilan repoga kiritilmaydi va Render'ning vaqtinchalik diskida saqlanmasligi kerak. Avvalgi lokal bazadagi talabalar savollari avtomatik ko‘chmaydi: ularni Excel/CSV orqali qayta import qiling yoki alohida ma’lumot migratsiyasini bajaring.

## Kod masalalarini xavfsiz tekshirish

Talaba yuborgan kod Flask/Gunicorn jarayonida emas, Judge0 CE izolyatsiyalangan sandboxida kompilyatsiya qilinib ishga tushadi. `.env` faylida `JUDGE0_URL` ni o‘zingiz boshqaradigan, autentifikatsiyalangan va tarmoqdan cheklangan Judge0 instansiga sozlang; kerak bo‘lsa `JUDGE0_API_KEY` ni kiriting. Judge0 Python 3 (language ID 71) va C++17 (54) ni ishlatadi. Web ilova har bir yashirin testni topshiradi; hammasidan o‘tgan kod qabul qilinib keyingi masalani ochadi. Judge0 sozlanmagan yoki ishlamayotgan bo‘lsa, yechim qabul qilinmaydi va talaba xato xabarini ko‘radi. Internetdagi umumiy judge manzilidan foydalanish o‘rniga maxfiylik va resurs cheklovlari nazorat qilinadigan alohida instans tavsiya qilinadi.

40 ta boshlang‘ich masalani bazaga bir marta qo‘shish:

```powershell
uv run python seed_40_problems.py
```

Masalalar 3–4 ta maxfiy test bilan kiritiladi. Ustoz **Savollar** sahifasidan ularni kontestga tanlaydi; mavjud chiqish testi alohida qoladi.
