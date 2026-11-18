# Bilim.Arena

Flask, SQLAlchemy va SQLite/PostgreSQL asosidagi olimpiada/test platformasi.

## Mahalliy ishga tushirish

Python 3.13 va `uv` o‘rnatilgan PowerShell oynasida:

```powershell
uv sync
Copy-Item .env.example .env
uv run python app.py
```

Ilova `http://127.0.0.1:5000` manzilida ochiladi. `.env` ichida `SECRET_KEY` va kuchli `ADMIN_PASSWORD` ni belgilang. Standart ustoz paroli yo‘q: `ADMIN_PASSWORD` bo‘sh bo‘lsa, ilova har ishga tushganda konsolga vaqtinchalik parol chiqaradi (Render'da esa ishga tushmaydi). Noto‘g‘ri parol 5 marta kiritilsa, shu IP 15 daqiqaga bloklanadi.

Talaba **HEMIS ID va shaxsiy kirish kodi** bilan kiradi. Ustoz **Talabalar** sahifasida «Kodsizlar uchun kod yaratish (Excel)» tugmasini bosib, kodlar ro‘yxatini yuklab oladi va talabalarga tarqatadi. Bazada faqat kod xeshi saqlanadi, shuning uchun kodni yo‘qotgan talabaga «Yangi kod» tugmasi bilan yangisi beriladi.

Talabalarni ustoz sahifasidan alohida, `.xlsx` yoki `.csv` fayllaridan import qilish mumkin. Jadvalda `HEMIS ID`, `F.I.O`, `Guruh` ustunlari bo‘lishi kerak; Excel faylida sarlavha birinchi qator bo‘lishi shart emas. CSV UTF-8/UTF-8 BOM va Windows-1251 kodlashini, vergul/nuqta-vergul/tab ajratkichlarini qabul qiladi.

Savollar bazasida kod natijasini topish testlari va dasturlash masalalari mavjud. Python 3 yoki C++17 yechimlari ichki judge (`judge.py`) orqali avtomatik baholanadi. Vaqt serverda tekshiriladi, ammo masofadan topshirishda internetdan yordam olish yoki boshqa qurilmadan foydalanishni to‘liq texnik yo‘l bilan to‘sib bo‘lmaydi.

## Kontest vaqti va reyting

Kontest yaratishda (yoki keyin «Vaqt va reyting sozlamalari» orqali) ixtiyoriy **boshlanish** va **tugash** vaqtini Toshkent vaqtida belgilash mumkin. Boshlanishgacha talaba kontestni ocha olmaydi; tugash vaqtida barcha urinishlar yakunlanadi, hatto shaxsiy taymer hali tugamagan bo‘lsa ham. Vaqt mintaqasi `APP_UTC_OFFSET_HOURS` (standart 5).

Har bir kontestning **Reyting** sahifasi bor (har 30 soniyada yangilanadi, Excel'ga eksport qilinadi):

- **Kod yozish** — ICPC uslubi: yechilgan masalalar soni, teng bo‘lsa jarima. Jarima = har bir yechilgan masala uchun boshlagandan qabul qilingungacha o‘tgan daqiqalar + har bir noto‘g‘ri urinish uchun 20 daqiqa (kompilyatsiya va tizim xatolari hisobga olinmaydi).
- **Output testi** — to‘g‘ri javoblar soni, teng bo‘lsa kamroq sarflangan vaqt.

«Reyting talabalarga ko‘rinsin» belgilansa, talabalar ham jonli reytingni ko‘radi.

## Proktoring va Safe Exam Browser

Kontest sozlamalarida ikki bayroq bor:

**Kamera + kod kuzatuvi (proktoring).** Talaba kontestni ochganda kameraga ruxsat beradi; ruxsatsiz sahifa yopiq turadi. Har 10 soniyada kameradan bitta kadr (320 px JPEG) va yozayotgan kodi serverga yuboriladi. OpenCV (Haar cascade) har bir kadrda yuzlarni sanaydi: yuz yo‘q yoki bir nechta yuz bo‘lsa, ogohlantirish kadri bilan saqlanadi. Boshqa tab/dasturga o‘tish, oynadan chiqish, kod joylashtirish (paste — bloklanadi), kamera uzilishi ham qayd qilinadi. Kamera 60 soniyadan ko‘p ishlamasa, kod yuborish va javoblarni avtomatik saqlash to‘xtaydi.

Ustoz **Kontestlar → 📹 Kuzatuv** sahifasida barcha talabalarning oxirgi kadri va kodini jonli ko‘radi (har 5 soniyada yangilanadi); muammoli talabalar qizil bo‘lib yuqoriga chiqadi. Har bir talabaning hodisalar tarixi kadrlar bilan alohida sahifada. Joy tejash uchun har bir talabadan faqat oxirgi kadr va shubhali kadrlar saqlanadi; ular `PROCTOR_RETENTION_DAYS` (standart 30) kundan keyin o‘chadi yoki «Kadrlarni o‘chirish» tugmasi bilan darhol o‘chiriladi. **Talabalarni kamera kuzatuvi haqida oldindan ogohlantiring.**

Kamera faqat HTTPS (Render) yoki `localhost` orqali ishlaydi.

**Faqat Safe Exam Browser orqali.** Veb-sayt o‘zi talaba kompyuterida boshqa dastur yoki AI’ni bloklay olmaydi — buni [Safe Exam Browser](https://safeexambrowser.org) (bepul, Windows/macOS) qiladi: kiosk rejimi, boshqa dasturlar va saytlar yopiq. Sozlash:

1. SEB Config Tool’da yangi konfiguratsiya: *Start URL* = sayt manzili (masalan `https://<sayt>/login`), *Use Browser Exam Key and Configuration Key* yoqilgan; proktoring ishlatilsa, kamera ruxsatini yoqing (*Browser → Enable camera*). URL filtrda faqat sayt domenini ruxsat eting.
2. Konfiguratsiyani `.seb` fayl qilib saqlang va talabalarga tarqating (yoki saytga joylab, `sebs://` havolasini `SEB_START_LINK` ga yozing).
3. Config Tool ko‘rsatgan **Config Key** ni `SEB_CONFIG_KEYS` muhit o‘zgaruvchisiga yozing. Server har so‘rovdagi `X-SafeExamBrowser-ConfigKeyHash` sarlavhasini SHA256(URL + Config Key) bilan solishtiradi. Kalit berilmasa, faqat User-Agent tekshiriladi — buni soxtalashtirish oson, shuning uchun kalitni albatta kiriting.

Cheklov: hech qanday tizim talabaning telefoni yoki ikkinchi qurilmasini to‘liq to‘sa olmaydi — kamera kuzatuvi shu uchun.

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

## Kod masalalarini tekshirish

Talaba yuborgan kod ichki judge (`judge.py`) orqali tekshiriladi. Yechim fon oqimida navbatga qo‘yiladi, sahifa natija chiqquncha o‘zi yangilanadi; bir vaqtda `JUDGE_MAX_PARALLEL` ta yechim tekshiriladi. Har bir test uchun vaqt (`JUDGE_TIME_LIMIT`) va xotira (`JUDGE_MEMORY_MB`) cheklovi bor. Har bir yuborish tarixda saqlanadi va ustoz **Kod yechimlari** sahifasida barcha urinishlarni ko‘radi.

**Muhim:** izolyatsiya faqat Docker konteynerida (root + `runner` foydalanuvchisi + `prlimit`) ishlaydi. Windows'da yoki Docker'siz lokal ishga tushirilganda talaba kodi server huquqlari bilan bajariladi — buni faqat sinov uchun ishlating. Ilova `--workers 1` bilan ishlashi kerak (navbat va login cheklovi bitta jarayon xotirasida).

Kontest vaqti tugagan, lekin talaba qaytib kirmagan urinishlar ustoz natijalar sahifasini ochganda avtomatik baholanadi.

40 ta boshlang‘ich masalani bazaga bir marta qo‘shish:

```powershell
uv run python seed_40_problems.py
```

Masalalar 3–4 ta maxfiy test bilan kiritiladi. Ustoz **Savollar** sahifasidan ularni kontestga tanlaydi; mavjud chiqish testi alohida qoladi.
