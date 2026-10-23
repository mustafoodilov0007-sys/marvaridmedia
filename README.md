# 💎 Marvarid Media — premium kino bot

Tarjima kinolar, multfilmlar va musiqalar uchun to'liq tayyor Telegram bot: rangli (premium) tugmalar,
bot ichidagi **🌐 sayt** (Mini App), majburiy obuna, raqamli qidiruv, seriallar, premium emoji,
donat va Premium sotish tizimi.

Bot **faqat Python** bilan ishlaydi — hech qanday qo'shimcha kutubxona o'rnatish shart emas.

---

## 🚀 Ishga tushirish (3 qadam)

### 1-qadam. Botni kanalga admin qiling (majburiy!)
Telegram → **@tarjimakino_va_multfilimlar** kanali → ✏️ Tahrirlash → **Administratorlar** →
**Admin qo'shish** → botingizni qidiring → quyidagi huquqlarni yoqing:
- ✅ Xabarlarni joylash (kanalga e'lon qilish uchun)
- ✅ Havola orqali taklif qilish (zayavkali kanallar uchun)

> Bot kanalda admin bo'lmasa, majburiy obunani tekshira olmaydi. Bot buni o'zi aniqlab, admin panelda ogohlantiradi.

### 2-qadam. Python o'rnating (bir marta)
**Windows:** https://www.python.org/downloads/ → «Download Python 3» → o'rnatish oynasida
**«Add python.exe to PATH»** belgisini albatta qo'ying.

### 3-qadam. Botni ishga tushiring
- **Windows:** papkani oching va **`start.bat`** faylini ikki marta bosing.
  Qora oynada `✅ Bot ishga tushdi` yozuvi chiqsa — tayyor. **Oynani yopmang.**
- **Linux server:** `bash start.sh` (yoki `python3 bot.py`).

So'ng Telegram'da botga **/start** yozing — siz admin bo'lganingiz uchun menyuda
**👨‍💻 Admin panel** tugmasi bo'ladi (yoki **/admin** buyrug'i).

> ⚠️ Kompyuterda ishga tushirilsa, bot faqat kompyuter yoniq va oyna ochiq paytda ishlaydi.
> 24/7 ishlashi uchun serverga joylang (pastda yo'riqnoma bor).

Barcha sozlamalar **`.env`** faylida allaqachon yozilgan: token, adminlar
(7741577083, 8843883500), majburiy kanal va karta raqami.
**`.env` faylini hech kimga bermang** — unda bot tokeni bor. Token begona qo'lga tushsa:
@BotFather → `/revoke` → yangi tokenni `.env` dagi `BOT_TOKEN` ga yozing.

---

## ✨ Foydalanuvchi imkoniyatlari

| | |
|---|---|
| 🌐 **Sayt** | Bot ichida ochiladigan sayt: 🎬 Kinolar, 🧸 Multfilmlar, 🎵 Musiqalar bo'limlari, qidiruv, Yangi/Top. Tanlansa — bot chatga yuboradi |
| 🔢 **Kod bo'yicha** | Kino kodini yuborsa — kino darhol keladi |
| 🔎 **Nom bo'yicha** | `1. 2. 3. …` ro'yxat chiqadi, pastda **raqamli tugmalar** — raqam bosilsa o'sha kino keladi |
| 🔤 Aqlli qidiruv | Lotin/kirill, `o'`/`oʻ`, katta-kichik harf farqi yo'q; xato yozilsa ham («avatr») topadi |
| 📺 Seriallar | Qismlar ro'yxati (poster bilan), kino ostida `⬅️ 1-qism · 📋 Qismlar · 3-qism ➡️` |
| 🔥 🆕 🎲 | Top, yangi va tasodifiy kinolar |
| 📤 Ulashish | Do'stiga havola yuboradi — havola bosilsa kino to'g'ridan-to'g'ri ochiladi |
| 🔗 Deep link | `t.me/BOTINGIZ?start=15` — obunadan o'tgach 15-kodli kino avtomatik keladi |
| 💝 Qo'llab-quvvatlash | Karta (bir bosishda nusxalanadi) + chek yuborish, yoki Telegram Stars |
| 💎 Premium | Tarif tanlash, karta yoki Stars orqali to'lov |
| ✍️ Murojaat | Adminlarga yozish, kino so'rash — admin bot orqali javob qaytaradi |

**Premium dizayn:** obuna oynasida qizil «➕ Obuna bo'lish» (obuna bo'lgan kanal — yashil «✅»)
va ko'k «🔄 Tekshirish» tugmalari, ro'yxatlarda ko'k raqamlar, yashil ⬅️ ➡️ va qizil ❌ —
Telegram'ning yangi rangli tugmalari. Eski Telegram versiyalarida tugmalar oddiy rangda ko'rinadi.

---

## 👨‍💻 Admin panel

### 🎬 Kino qo'shish
1. **Video** yoki **fayl** yuboring (kanaldan forward qilsangiz ham bo'ladi).
2. Bot so'raydi: **🎬 Kino** yoki **🧸 Multfilm** — tanlang (saytda va menyuda shu bo'limda chiqadi).
   Musiqa — alohida **🎵 Musiqa qo'shish** bo'limida (audio yuborilsa bot o'zi o'sha yerga o'tkazadi).
3. **Kod** yuboring (yoki «🆕 Avtomatik kod» tugmasi).
4. **Nomi** → 5. **Ma'lumot** (janr, yil, til; o'tkazib yuborsa bo'ladi) → 6. **Poster** (ixtiyoriy).
7. **✅ Saqlash** yoki **💎 Premium kino sifatida saqlash**.

Saqlangach: **📢 Kanalga e'lon qilish** — kanalga poster + ma'lumot + yashil «🎬 Tomosha qilish» tugmali post joylanadi.

💡 **Tezkor usul:** hech qanday bo'limga kirmasdan botga video yuboring (yoki forward qiling) — bot turini
(kino/multfilm) so'raydi. Audio yuborsangiz — avtomatik 🎵 Musiqa bo'lib qo'shiladi.

Eski kinolar yangilanishdan keyin avtomatik **🎬 Kino** turida qoladi. Turini o'zgartirish:
**🗑️ Kino o'chirish** → kod → **🏷 Turini o'zgartirish**.

### 📺 Serial qo'shish
1-qismni oddiy kino kabi qo'shing → **«➕ Keyingi qismni qo'shish»** → qolgan qismlarni ketma-ket
yuboring (birdaniga forward qilsa ham bo'ladi) — avtomatik 2-, 3-, 4-qism bo'lib saqlanadi → **🏁 Tugatish**.
Band kodni yuborsangiz ham bot o'sha kinoga qism qo'shishni taklif qiladi.

### 🎵 Musiqa qo'shish (birdaniga ko'p)
Admin paneldagi **🎵 Musiqa qo'shish** → 10, 20, 50 ta musiqani birdaniga tashlang (yoki kanaldan forward qiling)
→ **🏁 Tugatish**. Har biri avtomatik saqlanadi:
- **Nomi** — fayldagi ijrochi va qo'shiq nomi, bo'lmasa fayl nomi (`01_Shahzoda_-_Yoningdaman_(sayt.uz).mp3` → `Shahzoda - Yoningdaman`);
- qo'shiq ichida **muqova** bo'lsa — saytda rasm sifatida chiqadi;
- bazada bor qo'shiq qayta qo'shilmaydi.

**Musiqalar kodsiz** — kino/multfilm kodlari (1, 2, 3...) bilan aralashmaydi, nomi bo'yicha topiladi.
Ichki havola: `t.me/BOT?start=m5`. Turini o'zgartirish (🏷) da kino ↔ multfilm kodi saqlanadi.

### 🎞 Shorts (saytda)
**🗑️ Kino o'chirish** → kod → **🎞 Shorts qo'shish** → qisqa **video** (treyler, parcha) yoki **rasm** yuboring
(bir nechtasini ketma-ket ham bo'ladi) → **🏁 Tugatish**. Kino saqlangandan keyin chiqadigan tugma orqali ham qo'shsa bo'ladi.
Saytdagi **Shorts** bo'limida TikTok kabi tepaga surib ko'riladi, «▶ To'liq ko'rish» bosilsa bot kinoni yuboradi.
Video **20 MB** dan kichik bo'lsin (Telegram bot kattaroq faylni saytga bera olmaydi).

### ⚡️ Eski kinolarni tez ko'chirish (ommaviy qo'shish)
**🎬 Kino qo'shish → ⚡️ Ommaviy qo'shish** → kanal/guruhdan kinolarni birdaniga forward qiling.
Bot har bir post izohidan **kodni** (`Kod: 45`, `Kino kodi: 45`, `#45`) va **nomni** (birinchi qator)
o'zi oladi. Kanaldagi eski postlardagi kodlar saqlanib qoladi. Izohdagi kod band bo'lsa — o'sha kinoga
yangi qism qo'shiladi.

### 🗑️ Kino o'chirish (va tahrirlash)
Kod yoki nom yuboring → kino kartasi: butunlay o'chirish, bitta qismni o'chirish (qolganlari
qayta raqamlanadi), nom / ma'lumot / posterni o'zgartirish, Premium qilish, qism qo'shish, e'lon qilish.

### 🔗 Majburiy kanallar
Kanal **@useri**, havolasi yoki ID raqamini yuboring (yopiq kanal uchun — kanaldan postni forward qiling).
Bot kanalda admin ekanini tekshiradi, so'ng turini so'raydi:
- **Oddiy** — foydalanuvchi kanalga a'zo bo'lishi kerak;
- **📨 Zayavka** — kanalga qo'shilish so'rovini yuborishning o'zi yetarli (homiy kanallar uchun qulay);
- **🌍 Havola** (Instagram, YouTube…) — tugma sifatida ko'rinadi, obuna tekshirilmaydi.

### ✉️ Xabar yuborish
Istalgan xabarni yuboring (matn, rasm, video…) → ko'rinishini tekshiring →
**🔘 Tugma qo'shish** (`Matn - https://havola`, bir qatorda bir nechta: `A - link | B - link`) →
**🎯 Auditoriya** (hammaga / premiumsizlarga — reklama uchun / faqat premiumlarga) →
**📤 Usul** (nusxa yoki forward) → **✅ Yuborish**.

💎 **Premium emoji:** xabar matnida premium (animatsiyali) emoji ishlatsangiz, ular obunachilarga ham
shunday boradi. Tugma matni boshiga premium emoji qo'ysangiz — u tugma ikonkasiga aylanadi.
Shart: **bot egasi** (@BotFather'da botni yaratgan akkaunt) **Telegram Premium**'ga ega bo'lishi kerak.
Tekshirish uchun botga **/emoji** yozing va premium emoji yuboring — bot qaytargan emoji animatsiyali
bo'lsa, hammasi ishlayapti. Bu buyruq emoji ID raqamlarini ham ko'rsatadi. Jarayon jonli ko'rinadi, istalgan payt **⏹ To'xtatish** mumkin.
Botni bloklaganlar avtomatik belgilanadi.

### 👮 Adminlar
`.env` dagi bosh adminlar 👑 o'chirilmaydi. Yangi admin qo'shish: ID raqamini yuboring yoki
uning xabarini forward qiling (ID ni bilish uchun u botga **/id** yozsin).
Adminlarni faqat bosh adminlar qo'sha/o'chira oladi.

### ⚙️ Matnlar
Start xabari, obuna xabari, kino izohi (pastki qism), donat va premium matnlari, karta raqami,
karta egasi, e'lon kanali. Matnni yozganda qalin/kursiv/havola formatlash saqlanadi.
O'zgaruvchilar: `{name}` — foydalanuvchi ismi, `{brand}` — brend, `{bot}` — bot useri,
`{card}` — karta, `{holder}` — karta egasi. **♻️ Standart holatga qaytarish** tugmasi bor.

**🔒 Kontent himoyasi** (standart: yoqilgan) — oddiy foydalanuvchilar kinoni saqlay olmaydi va
forward qila olmaydi; Premium a'zolar va adminlar bundan mustasno. Shu yerda o'chirish mumkin.

### 💎 Premiumlar
- **📋 Tariflar** — standart: 1 oy 10 000 so'm / 50 ⭐, 3 oy 25 000 / 120 ⭐, 6 oy 45 000 / 220 ⭐,
  1 yil 80 000 / 400 ⭐. Yangi tarif: `kun narx stars`, masalan `30 10000 50`.
- **Karta orqali:** foydalanuvchi chek yuboradi → barcha adminlarga rasm bilan keladi →
  **✅ Tasdiqlash** → premium avtomatik yoqiladi (bir admin tasdiqlasa, boshqalarida ham belgilanadi).
- **⭐ Telegram Stars orqali:** to'lov avtomatik, admin aralashuvisiz yoqiladi. Qaytarish: `/refund TO'LOV_ID`.
- **🎁 Premium berish** (sovg'a) va **🚫 Premiumni olish**, **👥 Premiumlar** ro'yxati.
- Muddat tugashiga 1 kun qolganda eslatma, tugagach xabar avtomatik yuboriladi.
- Premium imtiyozlari: majburiy obunasiz kirish, 💎 premium kinolar, reklamasiz (auditoriya tanlovi),
  kinoni saqlash/ulashish.

> ℹ️ Telegram qoidalariga ko'ra bot ichida sotiladigan raqamli xizmatlar uchun rasmiy to'lov usuli —
> **Telegram Stars**. Karta orqali premium sotish bu qoidaga to'liq mos emas; xavotir bo'lsa,
> **💎 Premiumlar → 💳 Karta** tugmasi bilan o'chirib qo'yishingiz mumkin. Donat (ixtiyoriy yordam) bunga kirmaydi.

### 📊 Statistika
Foydalanuvchilar (faol, bloklagan, bugun/hafta/oy), kinolar, ko'rishlar, premium va donatlar,
top-5 kino va **❓ topilmagan so'rovlar** (qaysi kinoni qo'shish kerakligini ko'rsatadi).
**💾 Zaxira nusxa** — butun bazani fayl qilib yuboradi (haftada bir marta olib qo'ying).

---

## 🚂 Railway'ga joylash (24/7)

Railway uchun `marvarid_kino_bot_railway` papkasidan foydalaning — unda `.env` yo'q (token GitHub'ga
chiqib ketmasligi uchun), `Dockerfile` esa bor.

1. **GitHub** → `+` → **New repository** → nomi `marvarid-kino-bot` → **Private** → **Create repository**.
2. Repozitoriy sahifasida **uploading an existing file** → papka ichidagi **hamma** fayl va `app` papkasini
   sudrab tashlang → **Commit changes**.
3. **Railway** → **New Project** → **GitHub Repository** → `marvarid-kino-bot` ni tanlang
   (birinchi marta GitHub'ga ruxsat berish so'raladi).
4. Servis → **Variables** → **Raw Editor** → quyidagini qo'ying → **Update Variables**:
   ```
   BOT_TOKEN=...
   ADMINS=7741577083,8843883500
   CHANNELS=https://t.me/tarjimakino_va_multfilimlar
   CARD_NUMBER=5614681215325527
   CARD_HOLDER=A.O.
   BRAND_NAME=Marvarid Media
   ```
5. **Volume (majburiy!):** loyiha maydonida bo'sh joyda o'ng tugma (yoki `Ctrl+K`) → **Volume** →
   servisni tanlang → Mount path: **`/app/data`**. Busiz har yangilanishda baza o'chib ketadi
   (bot bu holatda adminlarga ogohlantirish yuboradi).
6. Servis → **Settings** → **Restart Policy: Always**. **Serverless** o'chiq qolsin.
7. Yuqorida chiqqan **Deploy** tugmasini bosing → **Deployments → View Logs** da
   `✅ Bot ishga tushdi` chiqishi kerak.

⚠️ Bir token bilan faqat **bitta** nusxa ishlashi kerak — Railway'da ishga tushgach, kompyuterdagi
`start.bat` oynasini yoping. Kodni yangilash: GitHub'ga yangi fayllarni yuklang — Railway o'zi qayta joylaydi,
baza Volume'da saqlanib qoladi.

## 🌐 Saytni (Mini App) yoqish

Sayt bot bilan birga ishlaydi, alohida hosting kerak emas. Faqat bot **HTTPS manzilga** ega bo'lishi kerak:

- **Railway:** servis → **Settings → Networking → Generate Domain** (port so'ralsa: `8080`).
  Railway `PORT` va `RAILWAY_PUBLIC_DOMAIN` ni o'zi qo'yadi — boshqa hech narsa shart emas. Qayta Deploy.
- **VPS:** domen + HTTPS (masalan nginx/Caddy) orqali `PORT` ga yo'naltiring va `.env` ga yozing:
  `WEBAPP_URL=https://sayt.domen.uz` va `PORT=8080`.
- **Kompyuter (start.bat):** HTTPS manzil bo'lmagani uchun sayt o'chiq turadi, bot esa odatdagidek ishlaydi.

Yoqilgach logda `🌐 Sayt ishga tushdi` chiqadi, foydalanuvchi menyusida **🌐 Sayt** tugmasi va
**/sayt** buyrug'i paydo bo'ladi. Saytda majburiy obuna va Premium qoidalari botdagidek ishlaydi.

## 📱 Android ilova

`android/` papkasida — saytni ochadigan Android ilova (katalog, Shorts, qidiruv; «Ko'rish» bosilsa
Telegram'da bot ochiladi va kinoni yuboradi). Kod GitHub'ga yuklanganda **GitHub Actions** APK'ni o'zi yig'adi:
**GitHub → Releases → android-latest → MarvaridMedia.apk**.

- Imzo kaliti GitHub Secrets'da bo'lsa (`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`) —
  imzolangan APK chiqadi (yangilanishlar ustidan o'rnatiladi). Bo'lmasa — sinov (debug) APK.
- Sayt manzili: `android/app/build.gradle.kts` dagi `siteUrl`.
- Ikonka (512px): `android/play/icon-512.png`.
- Sayt Telegram'dan tashqarida (ilova yoki brauzer) mehmon rejimida ishlaydi: `/pub/...` API.

## 🔄 Botni yangilash (yangi versiya kelganda)

Yangilanish arxivida `.env` bo'lmaydi — tokeningiz va bazangiz o'zgarmaydi.

- **Railway:** GitHub'dagi repozitoriy → **Add file → Upload files** → yangi papka ichidagi hamma narsani
  sudrab tashlang → **Commit changes**. Railway 1–2 daqiqada o'zi qayta joylaydi, kinolar Volume'da saqlanib qoladi.
- **Kompyuter:** `start.bat` oynasini yoping → yangi fayllarni eski papkaga nusxalang («Almashtirish») →
  `start.bat` ni qayta ishga tushiring.

So'ng Telegram'da **/start** (adminlar **/admin**) bosing — yangi menyu chiqadi.

## 🖥 Boshqa serverga joylash (VPS)

Istalgan Linux VPS'da (Python 3.8+ bor):

```bash
# fayllarni serverga yuklang, masalan /root/marvarid_kino_bot
cd /root/marvarid_kino_bot
python3 bot.py        # sinab ko'rish (Ctrl+C — to'xtatish)
```

Doimiy ishlashi uchun `/etc/systemd/system/marvarid.service` fayli:

```ini
[Unit]
Description=Marvarid Media kino bot
After=network-online.target

[Service]
WorkingDirectory=/root/marvarid_kino_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10
RestartPreventExitStatus=2

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload && systemctl enable --now marvarid
journalctl -u marvarid -f     # loglarni ko'rish
```

---

## ❓ Muammolar

| Belgi | Yechim |
|---|---|
| `BOT_TOKEN noto'g'ri` | `.env` dagi tokenni @BotFather'dan qayta nusxalang |
| `Bot boshqa joyda ham ishga tushirilgan` | Shu token bilan ishlayotgan boshqa dastur/eski botni to'xtating |
| Obuna tekshirilmayapti | Bot kanalda admin emas — 1-qadamni bajaring |
| `Python topilmadi` | Python'ni «Add python.exe to PATH» belgisi bilan qayta o'rnating |
| Telegram'ga ulanib bo'lmayapti | Internetni tekshiring; kerak bo'lsa `.env` ga `PROXY=http://...` yozing |

Loglar: `data/bot.log`. Baza: `data/bot.db`.

## 📁 Fayllar
```
bot.py            — ishga tushirish
.env              — sozlamalar (token, adminlar, kanal, karta)
start.bat         — Windows uchun ishga tushirish
start.sh          — Linux uchun ishga tushirish
Dockerfile        — Railway / Docker uchun
app/              — bot kodi (handlers/ — bo'limlar, webapp.py — sayt serveri)
app/web/          — sayt sahifasi (index.html)
data/             — baza va loglar (avtomatik yaratiladi)
```
