# 🎬 Marvarid Watch — kinoni saytning o'zida ko'rsatadigan alohida sayt

Bu **alohida loyiha**: hozirgi bot va saytga umuman bog'liq emas (faqat katalogni — nom, poster, janr — o'qib oladi).
Kinolar bulutdagi omborda (Cloudflare R2) turadi, sayt ularni pleyerda o'ynatadi. Noutbuk o'chiq bo'lsa ham ishlayveradi.

**Nimalar bor:** hozirgi saytning dizayni, qidiruv, janr/yil/davlat filtrlari, 3D "Haftaning TOP'i", pleyer
(to'xtagan joydan davom etish, keyingi qism, tezlik, kichik oyna, klaviatura), serial qismlari,
admin panel (`/admin`) — kinoni brauzerdan, **telefondan ham** yuklash.

---

## 1-qadam. Cloudflare R2 (video ombori)

1. https://dash.cloudflare.com ga kiring (akkaunt bo'lmasa — bepul oching), chap menyuda **R2 Object Storage** → kartani ulang
   (10 GB bepul; undan ortig'i taxminan $0,015 / GB / oy; **ko'rishlar uchun trafik puli YO'Q**).
2. **Create bucket** → nom: masalan `kinolar` → yarating.
3. **R2 → Manage API Tokens → Create API token**: ruxsat **Object Read & Write**, bucket: `kinolar`.
   Chiqqan **Access Key ID**, **Secret Access Key** va **S3 endpoint** (`https://<hisob-id>.r2.cloudflarestorage.com`) ni saqlab qo'ying.
   (Bularni hech kimga yubormang, faqat Railway'ga kiriting.)
4. **Bucket → Settings → CORS Policy** ga shuni qo'ying (`SAYT_MANZILI` o'rniga ko'rish saytingiz manzilini yozing):

```json
[
  {
    "AllowedOrigins": ["https://SAYT_MANZILI"],
    "AllowedMethods": ["GET", "PUT", "HEAD"],
    "AllowedHeaders": ["*"],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

> `ExposeHeaders: ETag` majburiy — busiz katta fayl yuklanmaydi.

5. *(Ixtiyoriy, tezroq)* Bucket → **Settings → Public access** → `r2.dev` yoki o'z domeningizni ulang va shu manzilni
   `PUBLIC_VIDEO_BASE` ga yozing. Yozmasangiz ham ishlaydi (sayt vaqtinchalik imzolangan havola beradi).

## 2-qadam. Railway'da yangi servis

> ⚠️ Hozirgi bot servisiga **tegmang**. Yangi servis yarating.

1. Railway → loyiha → **New → GitHub Repo** → `marvaridmedia` repozitoriyasi.
2. Servis sozlamalari: **Branch = `watch-site`**, **Root Directory = `watch`** (shunda `main` dagi o'zgarishlar bu servisga ta'sir qilmaydi, aksincha ham).
3. **Volumes → Add Volume** → Mount path: `/app/data` (baza shu yerda saqlanadi).
4. **Variables** (kerakli):

| O'zgaruvchi | Qiymat |
|---|---|
| `ADMIN_PASSWORD` | admin panel paroli (uzun, murakkab) |
| `SOURCE_URL` | hozirgi sayt manzili: `https://marvaridmedia-production.up.railway.app` |
| `S3_ENDPOINT` | `https://<hisob-id>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | `kinolar` |
| `S3_ACCESS_KEY` | R2 Access Key ID |
| `S3_SECRET_KEY` | R2 Secret Access Key |
| `SITE_BRAND` | *(ixtiyoriy)* sayt nomi, standart: `Marvarid Media` |
| `BOT_USERNAME` | *(ixtiyoriy)* `Marvaridmediyabot` — topilmagan kino uchun «So'rash» tugmasi botga olib boradi |
| `PUBLIC_VIDEO_BASE` | *(ixtiyoriy)* ochiq bucket manzili |
| `UPLOAD_PART_MB` | *(ixtiyoriy)* yuklash bo'lagi, standart 16 |

5. **Settings → Networking → Generate Domain** — shu manzil ko'rish saytingiz. Uni 1-qadamdagi CORS'dagi `SAYT_MANZILI` ga yozing.

## 3-qadam. Birinchi kinoni qo'yish

1. `https://<sayt>/admin` → parolni kiriting.
2. **🔄 Katalogni yangilash** — kinolar ro'yxati hozirgi saytdan olinadi (keyin har 6 soatda o'zi yangilanadi).
3. Kerakli kino qatorida **⬆️ Video yuklash** → faylni tanlang → yuklash tugagach kino saytda darhol chiqadi.
   Serial uchun har bir qismni ketma-ket **➕ Keyingi qism** bilan yuklang.
4. Videosi yo'q kinolar ochiq saytda **ko'rinmaydi**. **👁 Ko'rinadi / 🚫 Yashirin** tugmasi bilan istalgan kinoni vaqtincha yashirish mumkin.

Yangi kinoning nomi, posteri, janri — avvalgidek **botdan** kiritiladi; bu yerga faqat video qo'shiladi.

---

## Video tayyorlash (muhim!)

- Eng yaxshi format: **MP4 (H.264 video + AAC ovoz)**. Barcha telefon va brauzerlarda ishlaydi.
- MP4 **"faststart"** bo'lsin, aks holda ko'rish boshlanishi sekin bo'ladi (admin panel buni o'zi aniqlab ogohlantiradi).
  Tuzatish (kompyuterda, qayta kodlamasdan, bir necha soniya):

```bash
ffmpeg -i kirish.mp4 -c copy -movflags +faststart chiqish.mp4
```

- Boshqa formatlar (MKV, AVI, HEVC/H.265) ko'p brauzerlarda o'ynamaydi — avval MP4 ga o'giring:

```bash
ffmpeg -i kirish.mkv -c:v libx264 -crf 22 -preset medium -c:a aac -b:a 128k -movflags +faststart chiqish.mp4
```

- Hajm haqida: 1 soatlik 720p film ≈ 1–1,5 GB. 100 ta film ≈ 100–150 GB ≈ $1,5–2,5 / oy (R2).
- Yuklash paytida sahifani yopmang. Fayl 16 MB bo'laklarga bo'linib yuboriladi; bo'lak xato bersa, o'zi qayta urinadi.

## ⚠️ Huquqiy eslatma

Faqat **o'zingizga tegishli yoki tarqatish huquqi bor** kontentni joylang. Cloudflare va Railway shartlari mualliflik huquqi
buzilishini taqiqlaydi: shikoyat kelsa, akkaunt va ombor o'chirilishi, hamma videolar yo'qolishi mumkin.

---

## Texnik ma'lumot

- Faqat Python standart kutubxonasi (hech qanday paket o'rnatilmaydi). Fayllar: `server.py` (HTTP), `s3.py` (R2/S3 imzo va multipart),
  `api.py` (ochiq API), `catalog.py` (katalog sinxronizatsiyasi), `db.py` (SQLite), `web/admin.html`, `web/index.html` (yig'ma).
- Video **serverdan o'tmaydi**: brauzer bo'laklarni to'g'ridan-to'g'ri R2 ga yuboradi; ko'rishda ham R2 dan oladi.
  Railway faqat sahifa va ma'lumotlar bazasini beradi — shuning uchun arzon.
- `STORAGE=local` (S3 sozlanmasa avtomatik) — videolar server diskida; faqat sinov uchun, ko'p ma'lumot uchun R2 ishlating.
- Bosh sahifa (`web/index.html`) hozirgi saytning (`app/web/index.html`) nusxasidan yasaladi:
  hozirgi sayt dizayni o'zgarsa, `python build_site.py` ni ishga tushiring (hozirgi saytga TEGMAYDI, faqat o'qiydi).
- Testlar: `python -m unittest discover tests`.
- Lokal sinov: `ADMIN_PASSWORD=parol SOURCE_URL=https://... python server.py` → http://localhost:8080
