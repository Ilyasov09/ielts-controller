# IELTS Controller — Telegram bot

IELTS tayyorgarligini kuzatadigan shaxsiy bot. Har bir skill natijasini qayd etadi, IELTS bandini
hisoblaydi va kanalga post qiladi. Bundan tashqari har kuni countdown chiqaradi, statistika, streak,
poll va broadcast vazifalarini bajaradi.

**Talablar:** Python **3.9+** (3.9 / 3.10 / 3.12 / 3.14 da sinovdan o‘tgan), PostgreSQL.
Texnologiyalar: Aiogram 3, SQLAlchemy 2 (async), asyncpg, APScheduler, openpyxl, fpdf2.

---

## 1. Tayyorgarlik

1. [@BotFather](https://t.me/BotFather) da yangi bot oching va **token** oling.
2. Botni kanalingizga **admin** qiling va quyidagi huquqlarni bering:
   - **Post messages** — natija, countdown, poll va broadcast postlari uchun;
   - **Edit messages** — poll tugmalaridagi ovozlar sonini yangilash uchun;
   - **Delete messages** (ixtiyoriy) — History'dan postni kanaldan ham o‘chirish uchun.
3. Docker ishlatsangiz — `.env.example` faylidan nusxa olib, `.env` deb nomlang va to‘ldiring.
   Dockersiz ishga tushirsangiz — buning hojati yo‘q, `python main.py` `.env` ni o‘zi yaratadi (pastga qarang).

```bash
cp .env.example .env
```

`ADMIN_IDS` ni bo‘sh qoldirsangiz, botga **birinchi** `/start` bosgan odam uning egasi bo‘ladi.
Boshqa hech kim botdan foydalana olmaydi. Begona kishi `/start` bossa, bot unga o‘z Telegram ID sini ko‘rsatadi.

## 2. Ishga tushirish

### Variant A — Docker Compose (tavsiya)

```bash
docker compose up -d --build
```

Loglarni ko‘rish:

```bash
docker compose logs -f bot
```

PostgreSQL ham avtomatik ko‘tariladi, ma'lumotlar `pgdata` volume'da saqlanadi.
Boshqa Python versiyasida yig‘ish: `docker compose build --build-arg PYTHON_VERSION=3.13`.

### Variant B — Dockersiz (eng oson)

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python main.py
```

`.env` fayli bo‘lmasa, bot terminalda o‘zi savollar beradi va `.env` ni yaratadi:

1. **BOT_TOKEN** — kiritilgan token Telegram orqali darhol tekshiriladi;
2. **ADMIN_IDS** — Enter bossangiz, botga birinchi `/start` bosgan odam egasi bo‘ladi;
3. **Baza** — PostgreSQL (host/port/foydalanuvchi/parol, ulanish shu zahoti tekshiriladi) yoki SQLite;
4. **Vaqt zonasi**, Daily Report va Countdown vaqtlari.

`[qavs ichidagi]` qiymat Enter bosilganda olinadigan standartdir. Ctrl+C bossangiz, sozlash bekor qilinadi va `.env` o‘zgarmaydi.

Sozlamalarni keyin qayta kiritish (eski qiymatlar standart sifatida taklif qilinadi):

```bash
.venv/bin/python main.py --setup
```

Jadvallar birinchi ishga tushishda avtomatik yaratiladi.

> SQLite tanlansa, `aiosqlite` paketi kerak: `.venv/bin/pip install aiosqlite`.

### Variant C — Android telefon (Termux)

1. **Termux** ni F-Droid yoki GitHub'dan o‘rnating (Play Market'dagi versiya eskirgan va ishlamaydi).
   Telefon qayta yonganda avtomatik ishga tushishi uchun **Termux:Boot** ilovasini ham o‘rnating va bir marta oching.
2. Loyiha papkasini telefonga ko‘chiring, masalan `~/ielts` ga (git yoki `termux-setup-storage` orqali).
3. O‘rnating (birinchi marta 5–15 daqiqa):

```bash
cd ~/ielts && bash install-termux.sh
```

4. Birinchi ishga tushirish — terminalda sozlash savollari beriladi. Baza uchun **2) SQLite** ni tanlang:

```bash
python main.py
```

Bot javob berishini tekshirib, Ctrl+C bilan to‘xtating.

5. Doimiy ishlatish (wake-lock va xato bo‘lsa avtomatik qayta ishga tushirish bilan, log `bot.log` da):

```bash
./run-termux.sh
```

**Android bot ishlayotgan Termux'ni o‘chirib qo‘ymasligi uchun:**
- Sozlamalar → Ilovalar → Termux → Batareya → **«Cheklanmagan» / «Optimallashtirmaslik»**;
- Termux bildirishnomasi doim turishi kerak — uni yopmang;
- Xiaomi/Redmi/POCO, Huawei, Samsung'da qo‘shimcha: Termux uchun **Autostart** ni yoqing va Termux'ni so‘nggi ilovalar ro‘yxatida **qulflang**.

**Termux bo‘yicha eslatmalar:**
- `install-termux.sh` Pillow va matplotlib'ni `pkg` orqali o‘rnatadi (telefonda kompilyatsiya qilinmaydi). Python kutubxonalari esa Termux User Repository'ning tayyor wheel'laridan olinadi. pydantic `2.12.5` ga mahkamlangan, chunki uning tayyor wheel'i bor.
- Agar pip `pydantic-core` ni kompilyatsiya qilmoqchi bo‘lib xato bersa, `pkg install rust` ni o‘rnatib, qaytadan urinib ko‘ring. Skript buni o‘zi ham taklif qiladi.
- matplotlib o‘rnatilmasa ham bot ishlayveradi: faqat grafiklar chiqmaydi, haftalik hisobot esa matn ko‘rinishida yuboriladi.
- Telefon internetsiz qolsa, bot ulanish tiklanishini kutadi. Rejalashtirilgan postlar 1 soatgacha kechiksa ham baribir yuboriladi.

## 3. Birinchi sozlash (`/start`)

1. **Kanal ulash.** «📢 Kanalni tanlash» tugmasini bosing yoki kanaldan postni forward qiling, yoki `@username` / `-100…` ID ni yuboring.
   Bot o‘zi kanalda admin ekanini va post yuborish huquqi borligini tekshiradi.
2. **Imtihon sanasi** — `DD.MM.YYYY` formatida (o‘tkazib yuborsa ham bo‘ladi, keyin ⚙️ Settings yoki ⏳ Exam Countdown orqali kiritiladi).
3. **Kunlik hisobot vaqti** — har kuni shu vaqtda bot sizga 📚 Daily Report menyusini yuboradi.

## 4. Modullar

| Menyu | Nima qiladi |
|---|---|
| 📚 **Daily Report** | Reading (faqat Academic) / Listening / Writing / Speaking. Har bir natija alohida saqlanadi va kanalga **alohida post** bo‘lib chiqadi. Bir kunda bir skillga cheksiz natija kiritish mumkin. Rasm ixtiyoriy. |
| 📊 **Statistics** | Daily / Weekly (7 kun) / Monthly (30 kun) / Custom oralig‘i. O‘rtacha va eng yaxshi bandlar, mocklar soni, vaqt, faol kunlar, taxminiy overall band va oldingi davr bilan solishtirish. Shu yerdan **📈 progress grafigi** (skill bandlari + kunlik vaqt), PDF yoki Excel olinadi. |
| 🔔 **Kechki eslatma** | Bugun hisobot kiritilmagan bo‘lsa, belgilangan vaqtda (standart 22:00) streak uzilmasligi haqida eslatadi. Dam olish kunlari yuborilmaydi. Settings'da vaqtini o‘zgartirish yoki o‘chirish mumkin. |
| 📊 **Haftalik hisobot** | Har hafta (standart: yakshanba 20:00) kanalga oxirgi 7 kun natijalari va progress grafigi chiqadi: mocklar, vaqt, o‘rtacha bandlar, o‘tgan hafta bilan farq. Kun va vaqt Settings'da sozlanadi. U yerda yoqish/o‘chirish, «Ko‘rish» (oldin o‘zingizga yuborish) va «Hozir kanalga» tugmalari ham bor. |
| ⏳ **Exam Countdown** | Har kuni belgilangan vaqtda kanalga alohida countdown posti chiqadi. «📤 Hozir yuborish» tugmasi ham bor. |
| 🔥 **Streak System** | Kunda kamida 1 ta natija kiritilsa, streak davom etadi. Ko‘rsatiladi: joriy va eng uzun streak, jami faol kunlar, topshirish foizi, 7/30/60/100 kunlik rekordlar. Dam olish kunlari (haftalik yoki aniq sana) streakni uzmaydi. |
| 🗂 **History** | Barcha natijalar sahifalab ko‘rsatiladi. Natijani bazadan (xohlasangiz kanaldan ham) o‘chirish mumkin. |
| 🎯 **Study Planner** | Kunlik maqsad: har bir skill bo‘yicha mocklar soni va jami daqiqa. Bajarilish foizi Daily Report va statistikada ko‘rinadi. |
| 🗳 **Poll Creator** | Post matni → tugmalar → preview → kanalga yuborish. Tugmalar 3 ustunda joylashadi, har birida ovozlar soni qavsda ko‘rinadi: «2 soat (5)». Bir kishi faqat bitta ovoz beradi, lekin uni boshqa variantga ko‘chira oladi. Menyuda avvalgi polllar ro‘yxati bor: natijani foizda ko‘rish va **pollni yopish** mumkin. Yopilganda kanaldagi postdan tugmalar olib tashlanadi va o‘rniga yakuniy natija foizlarda yoziladi. `/poll` — darhol yangi poll. |
| 📢 **Broadcast** | Rejim yoqilgach, botga yuborilgan har qanday xabar (matn, rasm, video, audio, hujjat, sticker, GIF, album) kanalga caption va formatlashi bilan birga xuddi o‘zidek ko‘chiriladi. Chiqish: `/cancel`. |
| 📤 **Export Reports** | Bugun / 7 kun / 30 kun / barchasi / custom davr uchun PDF yoki Excel. |
| ⚙️ **Settings** | Kanal, imtihon sanasi, report vaqti, countdown vaqti, dam olish kunlari. |

Har bir skill hisobotida natijadan keyin **sarflangan vaqt** so‘raladi (o‘tkazib yuborish mumkin) — «kunlik tayyorgarlik vaqti» statistikasi shundan hisoblanadi.

Istalgan bosqichda menyu tugmasini bossangiz yoki `/cancel` yozsangiz, joriy amal to‘xtaydi.

## 5. Band hisoblash

Listening va Academic Reading uchun rasmiy 40 savollik konversiya jadvallari ishlatiladi
([services/band_calculator.py](services/band_calculator.py)). Botda Reading faqat Academic;
General Training jadvali kodda saqlab qolingan, lekin ishlatilmaydi.
Savollar soni 40 bo‘lmasa, natija 40 ga proporsional moslab hisoblanadi va adminga «taxminiy» deb ko‘rsatiladi.

> Eslatma: rasmiy jadvalda Listening **32/40 = 7.5** (30–31 = 7.0). Spetsifikatsiyadagi «32/40 → 7.0»
> misoli shu jadvalga mos kelmaydi. Boshqa jadval kerak bo‘lsa, `LISTENING_TABLE` ni o‘zgartiring.

## 6. Loyiha tuzilmasi

```
main.py                  ishga tushirish, dispatcher, buyruqlar
config.py                .env sozlamalari
database/                models, ulanish, avtomatik migratsiya, CRUD (repository.py)
handlers/                start, menu, daily, listening, reading, writing, speaking, report_flow,
                         countdown, statistics (+export), streak, history, planner, poll, broadcast, settings
services/                band_calculator, channel, scheduler, statistics, streak, planner, reports,
                         charts (grafik), weekly (haftalik post), access
keyboards/               main, skills, poll, admin
utils/                   dates, validators
```

## 7. Eslatmalar

- FSM holati xotirada saqlanadi: bot qayta ishga tushsa, chala qolgan hisobot qaytadan boshlanadi. Saqlangan natijalar yo‘qolmaydi.
- Bot belgilangan vaqtda o‘chiq bo‘lgan bo‘lsa, qayta yonganda o‘sha kungi countdown, Daily Report va (shu kuni bo‘lsa) haftalik hisobot yuboriladi. Bitta kunda post ikki marta chiqmaydi.
- Yangi versiyaga o‘tganda baza o‘zi yangilanadi: yangi ustunlar avtomatik qo‘shiladi, eski natijalar saqlanib qoladi.
- Vaqt zonasi `.env` dagi `TIMEZONE` orqali belgilanadi (standart: `Asia/Tashkent`).
