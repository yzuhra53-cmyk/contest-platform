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

Talaba kirish sahifasida familiya-ismini yoza boshlaydi: 3 harfdan keyin ustoz kiritgan ro‘yxatdan mos ismlar guruhi bilan chiqadi (HEMIS ID ko‘rsatilmaydi). O‘zini tanlab Tab yoki Enter bossa, F.I.Sh. va guruh to‘ladi, HEMIS ID ham ro‘yxatdan o‘zi yoziladi (F.I.Sh. va guruh bitta talabaga to‘liq mos kelsa). Kirish faqat HEMIS ID, F.I.Sh. va guruh ro‘yxatdagi bitta talabaga mos kelsa beriladi (katta-kichik harf, ortiqcha bo‘shliq va apostrof turlari hisobga olinmaydi). Bir vaqtda faqat bitta qurilmadan kirish mumkin: yangi qurilmadan kirilsa, eskisi chiqarib yuboriladi va ochiq urinishda bu qoidabuzarlik sifatida qayd etiladi.

Talabalarni ustoz sahifasidan alohida, `.xlsx` yoki `.csv` fayllaridan import qilish mumkin. Jadvalda `HEMIS ID`, `F.I.O`, `Guruh` ustunlari bo‘lishi kerak; Excel faylida sarlavha birinchi qator bo‘lishi shart emas. CSV UTF-8/UTF-8 BOM va Windows-1251 kodlashini, vergul/nuqta-vergul/tab ajratkichlarini qabul qiladi.

Savollar bazasida kod natijasini topish testlari va dasturlash masalalari mavjud. Python 3 yoki C++17 yechimlari ichki judge (`judge.py`) orqali avtomatik baholanadi. Vaqt serverda tekshiriladi, ammo masofadan topshirishda internetdan yordam olish yoki boshqa qurilmadan foydalanishni to‘liq texnik yo‘l bilan to‘sib bo‘lmaydi.

## Olimpiada masalalar banki (OB-01 … OB-30)

`problem_bank.json` da 30 ta original masala bor — oson (massiv, satr), o‘rta (prefiks yig‘indi, ikki ko‘rsatkich, binar qidiruv, Eratosfen g‘alviri, katta sonlar) va qiyin (DP, BFS, DSU, Dijkstra, LIS, topologik saralash). Har birida 9–14 ta yashirin test: qo‘lda yozilgan chegaraviy holatlar, tasodifiy testlar va 100 KB gacha katta testlar (samarasiz yechim vaqt limitidan o‘tmaydi).

Ilova ishga tushganda bank masalalari **Savollar** bazasiga avtomatik qo‘shiladi (Render’da ham). Har bir masala bir marta qo‘shiladi: ustoz uni o‘chirsa, qayta paydo bo‘lmaydi. Kontest yaratishda «Python / C++ kod yozish» turini tanlab, `[OB-..]` masalalarini belgilang.

Bankni o‘zgartirish yoki yangi masala qo‘shish: `tools/build_problem_bank.py` da masala (shart, generator, etalon yechim) yozing, so‘ng

```powershell
uv run python tools/build_problem_bank.py
uv run python tools/validate_problem_bank.py
```

Birinchisi testlarni etalon yechimni ishga tushirib yaratadi (ko‘p masalada kichik testlar brute-force yechim bilan ham solishtiriladi). Ikkinchisi har bir etalon yechimni haqiqiy judge orqali vaqt limiti bilan o‘tkazadi va faqat namuna javobini chiqaradigan yechim rad etilishini tekshiradi.

## Kod muharriri (IDE)

Kod masalalari sahifasida professional muharrir bor (CodeMirror 5, CDN orqali):

- Python va C++ uchun rangli sintaksis, qator raqamlari, qavslarni avtomatik yopish;
- yozish paytida maslahatlar: kalit so‘zlar, standart funksiyalar, tayyor qoliplar (`n = int(input())` va h.k.) va o‘zingiz yozgan nomlar. `Ctrl+Space` — ro‘yxatni ochish, `Ctrl+/` — izoh, `Ctrl+Enter` — ishga tushirish. Bu sun’iy intellekt emas: faqat oddiy avto-to‘ldirish;
- **▶ Ishga tushirish** va konsol: kod talaba kiritgan input bilan (standart — namuna) serverdagi xavfsiz muhitda ishga tushadi, natija, xato va vaqt ko‘rsatiladi; namuna javobi bilan solishtiriladi. Bu baholanmaydi va yuborish hisoblanmaydi. Ishga tushirishlar orasida kamida `RUN_COOLDOWN_SECONDS` (standart 3) soniya bo‘ladi;
- qoralama brauzerda avtomatik saqlanadi: sahifa yangilansa ham kod yo‘qolmaydi.

Proktoringli kontestda muharrirga kod joylashtirish (paste/drop) ham bloklanadi va qayd etiladi.

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

**Qulflangan rejim.** Kontest faqat to‘liq ekranda ochiladi va talaba uni tugatmaguncha shu sahifada qoladi: sahifani yopish yoki boshqa manzilga o‘tishdan oldin brauzer ogohlantiradi, «Orqaga» tugmasi ishlamaydi, F5/Ctrl+R, Ctrl+F, Ctrl+P, Ctrl+S, Ctrl+U, F12 va dasturchi vositalari bloklanadi, masala matnini nusxalab bo‘lmaydi. Chrome va Edge’da to‘liq ekranda Keyboard Lock ham yoqiladi: Ctrl+T/W/N, Alt+Tab ushlanadi va chiqish uchun Esc’ni uzoq bosib turish kerak. To‘liq ekrandan chiqish «To‘liq ekran rejimidan chiqdi» qoidabuzarligi sifatida yoziladi va qaytmaguncha kontest yopiq turadi. Brauzer sahifasi kompyuterni to‘liq qulflay olmaydi (masalan, Ctrl+Alt+Del yoki telefon), to‘liq qulf uchun Safe Exam Browser kerak.

**Ekran kuzatuvi.** Talaba kontestni ochganda **butun ekranini** ulashadi (brauzer oynasida «Butun ekran / Entire screen»). Faqat bitta oyna yoki tab tanlansa, qabul qilinmaydi. Har 10 soniyada ekran rasmi (1280 px JPEG) ustozga yuboriladi. Talaba oynadan chiqsa, 1,5 soniyadan keyin olingan ekran rasmi shu hodisaga dalil sifatida biriktiriladi: ustoz boshqa brauzer yoki AI sayti ochilganini ko‘radi. Ulashish to‘xtatilsa, «Ekran ulashish to‘xtatildi» qoidabuzarligi yoziladi va qayta ulashmaguncha kontest yopiq turadi; 60 soniyadan ko‘p ekran rasmi kelmasa, yechim yuborish to‘xtaydi. Ekran kuzatuvi kameradan mustaqil ishlaydi, shuning uchun kamerasiz kompyuterlarda ham qo‘llash mumkin. Bu brauzer ichida ishlaydi va Safe Exam Browser bilan birga ishlatilmaydi: SEB ekran ulashishni o‘zi bloklaydi. Kompyuterda Chrome, Edge yoki Firefox kerak.

Kamera faqat HTTPS (Render) yoki `localhost` orqali ishlaydi.

**Faqat Safe Exam Browser orqali.** Veb-sayt o‘zi talaba kompyuterida boshqa dastur yoki AI’ni bloklay olmaydi — buni [Safe Exam Browser](https://safeexambrowser.org) (bepul, Windows/macOS) qiladi: kiosk rejimi, boshqa dasturlar va saytlar yopiq. Sozlash:

1. SEB Config Tool’da yangi konfiguratsiya: *Start URL* = sayt manzili (masalan `https://<sayt>/login`), *Use Browser Exam Key and Configuration Key* yoqilgan; proktoring ishlatilsa, kamera ruxsatini yoqing (*Browser → Enable camera*). URL filtrda faqat sayt domenini ruxsat eting.
2. Konfiguratsiyani `.seb` fayl qilib saqlang va talabalarga tarqating (yoki saytga joylab, `sebs://` havolasini `SEB_START_LINK` ga yozing).
3. Config Tool ko‘rsatgan **Config Key** ni `SEB_CONFIG_KEYS` muhit o‘zgaruvchisiga yozing. Server har so‘rovdagi `X-SafeExamBrowser-ConfigKeyHash` sarlavhasini SHA256(URL + Config Key) bilan solishtiradi. Kalit berilmasa, faqat User-Agent tekshiriladi — buni soxtalashtirish oson, shuning uchun kalitni albatta kiriting.

Cheklov: hech qanday tizim talabaning telefoni yoki ikkinchi qurilmasini to‘liq to‘sa olmaydi — kamera kuzatuvi shu uchun.

## Qat’iy rejim

- **Bitta qurilma.** Talaba boshqa qurilma yoki brauzerdan kirsa, oldingi sessiya darhol bekor bo‘ladi; ochiq urinish bo‘lsa, bu qoidabuzarlik sifatida qayd qilinadi.
- **Qoidabuzarlik limiti** (kontest sozlamasi, yangi kontestlarda standart 5). Oynadan chiqish, kadrda yuz yo‘qligi yoki bir nechta yuz, paste, kamera uzilishi, SEB’siz kirish, boshqa qurilmadan kirish sanaladi (bir xil hodisa 30 soniyada bir marta). Limitga yetganda urinish avtomatik yakunlanadi va shu paytgacha to‘g‘ri bo‘lganlar baholanadi. Talaba ekranida hisoblagich ko‘rinib turadi.
- **Savollar tartibi** Output testida har bir talabaga aralashtirib beriladi.
- **Yechim yuborish oralig‘i** — kamida 20 soniya (`SUBMIT_COOLDOWN_SECONDS`), tanlab-tekshirib ko‘rishni cheklaydi.
- Yangi kontestlarda proktoring standart yoqilgan; `SEB_CONFIG_KEYS` sozlangan bo‘lsa, SEB ham standart yoqiladi.

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

## Doimiy ishlaydigan server (24/7)

Bepul Render rejasida servis 15 daqiqa so‘rov bo‘lmasa uxlaydi (birinchi kirish ~1 daqiqa kutadi), bepul PostgreSQL esa 30 kundan keyin o‘chiriladi. Talabalar istalgan paytda kirib topshira olishi uchun `render.yaml` pullik rejalarga o‘tkazilgan:

| Qism | Reja | Nima beradi |
|---|---|---|
| Web servis | `starter` | uxlamaydi, 24/7 |
| PostgreSQL | `basic-256mb`, 5 GB disk | doimiy saqlash, kunlik zaxira |

Narxlarni [render.com/pricing](https://render.com/pricing) da tekshiring (taxminan oyiga $7 + $6 atrofida). Bir vaqtda 50+ talaba C++ yozadigan olimpiadalarda web servisni `standard` rejaga ko‘tarish tavsiya qilinadi — kompilyatsiya va kamera tahlili CPU talab qiladi.

Yoqish tartibi:

1. Render Dashboard → **Billing** bo‘limida to‘lov kartasini qo‘shing (buni faqat hisob egasi qila oladi).
2. `main` branchga push qilingach, Blueprint `render.yaml` ni o‘qib, rejalarni yangilaydi. Agar servis Blueprint’siz yaratilgan bo‘lsa, Dashboard’da servis → **Settings → Instance Type → Starter**, bazada **Upgrade** ni qo‘lda tanlang.
3. Eski bepul baza muddati o‘tgan bo‘lsa, yangi baza bo‘sh ochiladi: talabalarni Excel’dan qayta import qiling.
4. Environment bo‘limida `ADMIN_PASSWORD` (kuchli parol) va SEB ishlatilsa `SEB_CONFIG_KEYS` ni kiriting.
5. `https://<sayt>/health` `{"status": "ok"}` qaytarishini tekshiring.

Kamera faqat HTTPS orqali ishlaydi — Render buni avtomatik beradi.

## Kod masalalarini tekshirish

Talaba yuborgan kod ichki judge (`judge.py`) orqali tekshiriladi. Yechim fon oqimida navbatga qo‘yiladi, sahifa natija chiqquncha o‘zi yangilanadi; bir vaqtda `JUDGE_MAX_PARALLEL` ta yechim tekshiriladi. Har bir test uchun vaqt (`JUDGE_TIME_LIMIT`) va xotira (`JUDGE_MEMORY_MB`) cheklovi bor. Har bir yuborish tarixda saqlanadi va ustoz **Kod yechimlari** sahifasida barcha urinishlarni ko‘radi.

**Muhim:** izolyatsiya faqat Docker konteynerida (root + `runner` foydalanuvchisi + `prlimit`) ishlaydi. Windows'da yoki Docker'siz lokal ishga tushirilganda talaba kodi server huquqlari bilan bajariladi — buni faqat sinov uchun ishlating. Ilova `--workers 1` bilan ishlashi kerak (navbat va login cheklovi bitta jarayon xotirasida).

Kontest vaqti tugagan, lekin talaba qaytib kirmagan urinishlar ustoz natijalar sahifasini ochganda avtomatik baholanadi.

40 ta boshlang‘ich masalani bazaga bir marta qo‘shish:

```powershell
uv run python seed_40_problems.py
```

Masalalar 3–4 ta maxfiy test bilan kiritiladi. Ustoz **Savollar** sahifasidan ularni kontestga tanlaydi; mavjud chiqish testi alohida qoladi.
