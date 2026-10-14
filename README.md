# 💎 Marvarid Media — premium kino bot

Tarjima kinolar va multfilmlar uchun to'liq tayyor Telegram bot: rangli (premium) tugmalar,
majburiy obuna, raqamli qidiruv, seriallar, donat va Premium sotish tizimi.

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
1. **Kod** yuboring (yoki «🆕 Avtomatik kod» tugmasi).
2. **Video** yuboring (video yoki fayl; kanaldan forward qilsangiz ham bo'ladi).
3. **Nomi** → 4. **Ma'lumot** (janr, yil, til; o'tkazib yuborsa bo'ladi) → 5. **Poster** (ixtiyoriy).
6. **✅ Saqlash** yoki **💎 Premium kino sifatida saqlash**.

Saqlangach: **📢 Kanalga e'lon qilish** — kanalga poster + ma'lumot + yashil «🎬 Tomosha qilish» tugmali post joylanadi.

💡 **Tezkor usul:** hech qanday bo'limga kirmasdan botga video yuboring (yoki forward qiling) — bot darhol kod so'raydi.

### 📺 Serial qo'shish
1-qismni oddiy kino kabi qo'shing → **«➕ Keyingi qismni qo'shish»** → qolgan qismlarni ketma-ket
yuboring (birdaniga forward qilsa ham bo'ladi) — avtomatik 2-, 3-, 4-qism bo'lib saqlanadi → **🏁 Tugatish**.
Band kodni yuborsangiz ham bot o'sha kinoga qism qo'shishni taklif qiladi.

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
**📤 Usul** (nusxa yoki forward) → **✅ Yuborish**. Jarayon jonli ko'rinadi, istalgan payt **⏹ To'xtatish** mumkin.
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

## 🖥 Serverga joylash (24/7)

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

> Railway/Render kabi platformalar uchun `Procfile` bor, lekin ularda doimiy disk (volume) ulanmasa,
> qayta deploy qilinganda `data/bot.db` bazasi o'chib ketadi.

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
app/              — bot kodi (handlers/ — bo'limlar)
data/             — baza va loglar (avtomatik yaratiladi)
```
