"""Tugma nomlari va standart matnlar."""


class B:
    """Pastki (reply) menyu tugmalari."""

    # foydalanuvchi menyusi
    SEARCH = "🔎 Kino qidirish"
    TOP = "🔥 Top kinolar"
    NEW = "🆕 Yangi kinolar"
    RANDOM = "🎲 Tasodifiy kino"
    PREMIUM = "💎 Premium"
    DONATE = "💝 Qo'llab-quvvatlash"
    CONTACT = "✍️ Murojaat"
    ADMIN = "👨‍💻 Admin panel"
    SITE = "🌐 Sayt"
    MOVIES = "🎬 Kinolar"
    CARTOONS = "🧸 Multfilmlar"
    MUSIC = "🎵 Musiqalar"

    # admin menyusi
    ADD_MOVIE = "🎬 Kino qo'shish"
    DEL_MOVIE = "🗑️ Kino o'chirish"
    STATS = "📊 Statistika"
    CHANNELS = "🔗 Majburiy kanallar"
    BROADCAST = "✉️ Xabar yuborish"
    ADMINS = "👮 Adminlar"
    PREMIUMS = "💎 Premiumlar"
    TEXTS = "⚙️ Matnlar"
    HOME = "🏠 Bosh menyu"


# Kontent turlari: kod → (belgi, nomi, ko'plikda)
CATEGORIES = {
    "movie": ("🎬", "Kino", "Kinolar"),
    "cartoon": ("🧸", "Multfilm", "Multfilmlar"),
    "music": ("🎵", "Musiqa", "Musiqalar"),
}


def cat_icon(category: str) -> str:
    return CATEGORIES.get(category or "movie", CATEGORIES["movie"])[0]


def cat_name(category: str) -> str:
    return CATEGORIES.get(category or "movie", CATEGORIES["movie"])[1]


# Admin «⚙️ Matnlar» bo'limidan o'zgartiriladigan matnlar.
# O'zgaruvchilar: {name} — ism, {bot} — bot useri, {brand} — brend nomi,
# {card} — karta raqami, {holder} — karta egasi.
DEFAULT_TEXTS = {
    "start_text": (
        "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
        "💎 <b>{brand}</b> rasmiy kino botiga xush kelibsiz!\n\n"
        "🔢 Kino <b>kodini</b> yuboring — kino darhol keladi.\n"
        "🔎 Yoki kino <b>nomini</b> yozing — natijalardan tanlaysiz.\n\n"
        "🍿 Yoqimli hordiq tilaymiz!"
    ),
    "sub_text": (
        "🚀📢 <b>Botdan to'liq foydalanish uchun avvalo asosiy kanalimizga obuna bo'ling!</b>\n\n"
        "✅ Kanalga obuna bo'lganingizdan so'ng botning barcha funksiyalaridan "
        "foydalanishingiz mumkin bo'ladi."
    ),
    "caption_footer": (
        "━━━━━━━━━━━━━━━\n"
        "💎 <b>{brand}</b> — eng sara tarjima kinolar\n"
        "🤖 @{bot}"
    ),
    "donate_text": (
        "💝 <b>{brand} loyihasini qo'llab-quvvatlang!</b>\n\n"
        "Biz sizga eng sara tarjima kinolar va multfilmlarni bepul yetkazib berish uchun "
        "tinimsiz mehnat qilamiz. Har qanday miqdordagi yordamingiz — loyihamiz rivoji "
        "uchun katta hissa! 🙏\n\n"
        "💳 <b>Karta raqami:</b>\n<code>{card}</code>\n"
        "👤 <b>Karta egasi:</b> {holder}\n\n"
        "✅ To'lov qilganingizdan so'ng «🧾 Chek yuborish» tugmasi orqali chekni yuboring."
    ),
    "premium_text": (
        "💎 <b>{brand} PREMIUM</b>\n\n"
        "Premium a'zolik afzalliklari:\n\n"
        "🚫 Majburiy kanallarga obuna bo'lish shart emas\n"
        "🎬 Faqat Premium a'zolar uchun maxsus kinolar\n"
        "📵 Reklama xabarlarisiz qulay foydalanish\n"
        "💾 Kinolarni saqlab olish va do'stlarga yuborish\n"
        "💖 Loyihamiz rivojiga hissa qo'shasiz"
    ),
}

# Matnlar bo'limidagi nomlar va o'zgaruvchilar
TEXT_TITLES = {
    "start_text": ("👋 Start xabari", "{name} — ism, {brand} — brend, {bot} — bot useri"),
    "sub_text": ("📢 Obuna xabari", "{name} — ism, {brand} — brend"),
    "caption_footer": ("🎬 Kino izohi", "{brand} — brend, {bot} — bot useri"),
    "donate_text": ("💝 Donat matni", "{card} — karta raqami, {holder} — karta egasi, {brand} — brend"),
    "premium_text": ("💎 Premium matni", "{brand} — brend, {bot} — bot useri"),
}

HELP_TEXT = (
    "ℹ️ <b>Botdan foydalanish</b>\n\n"
    "🔢 <b>Kino kodi</b> — kanaldagi postda ko'rsatilgan raqamni yuboring, kino darhol keladi.\n"
    "🔎 <b>Kino nomi</b> — nomini yozing, ro'yxatdagi raqamni tanlang.\n\n"
    "🔥 <b>Top kinolar</b> — eng ko'p ko'rilganlar\n"
    "🆕 <b>Yangi kinolar</b> — yangi qo'shilganlar\n"
    "🎲 <b>Tasodifiy kino</b> — omadingizni sinab ko'ring\n"
    "🌐 <b>Sayt</b> — kinolar, multfilmlar va musiqalar katalogi\n"
    "💎 <b>Premium</b> — majburiy obunasiz va reklamasiz\n"
    "💝 <b>Qo'llab-quvvatlash</b> — loyihamizga yordam\n"
    "✍️ <b>Murojaat</b> — kino so'rash yoki taklif yuborish"
)

TERMS_TEXT = (
    "📜 <b>Foydalanish shartlari</b>\n\n"
    "1. Premium obuna tanlangan muddatga beriladi va muddat tugagach avtomatik o'chadi.\n"
    "2. Premium imtiyozlari «💎 Premium» bo'limida ko'rsatilgan.\n"
    "3. Karta orqali to'lov chek admin tomonidan tekshirilgach faollashadi.\n"
    "4. Telegram Stars orqali to'lov darhol faollashadi.\n"
    "5. Texnik nosozlik bo'lsa, /paysupport orqali murojaat qiling — muammo hal qilinadi "
    "yoki to'lov qaytariladi.\n"
    "6. Bot ma'muriyati shartlarni o'zgartirish huquqini o'zida saqlaydi.\n\n"
    "To'lov qilish orqali siz ushbu shartlarga rozilik bildirasiz."
)

PAYSUPPORT_TEXT = (
    "🛟 <b>To'lov bo'yicha yordam</b>\n\n"
    "To'lov bilan bog'liq muammo bo'lsa, «✍️ Murojaat» tugmasi orqali yozing va "
    "to'lov chekini yoki to'lov ID raqamini qo'shing — adminlar tez orada javob berishadi.\n\n"
    "⚠️ Telegram qo'llab-quvvatlash xizmati bot orqali qilingan xaridlar bo'yicha yordam bera olmaydi."
)
