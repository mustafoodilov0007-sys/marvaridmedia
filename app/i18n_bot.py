"""🌐 Bot tili (o'zbek / ruscha / inglizcha): foydalanuvchi chiqadigan asosiy matn va tugmalar lug'at bo'yicha almashtiriladi.

Qamrov: pastki menyu, /start, yordam, qidiruv va topilmadi xabarlari, kuzatish, so'rovlar, to'lov menyusi sarlavhalari.
Lug'atda yo'q (masalan admin paneli, kino nomlari, izohlar) matnlar o'zgarmaydi. Tarjima Ctx.send/edit/answer orqali ishlaydi."""

from __future__ import annotations

import copy
import re
from typing import Dict, Optional, Tuple

LANGS = {"uz": "O'zbekcha", "ru": "Русский", "en": "English"}

# (o'zbekcha, ruscha, inglizcha). Uzunroq iboralar avval almashtiriladi.
PHRASES = [
    # pastki menyu
    ("🔎 Kino qidirish", "🔎 Поиск фильма", "🔎 Search movies"),
    ("🔥 Top kinolar", "🔥 Топ фильмов", "🔥 Top movies"),
    ("🆕 Yangi kinolar", "🆕 Новые фильмы", "🆕 New movies"),
    ("🎲 Tasodifiy kino", "🎲 Случайный фильм", "🎲 Random movie"),
    ("💝 Qo'llab-quvvatlash", "💝 Поддержать", "💝 Support us"),
    ("✍️ Murojaat", "✍️ Обращение", "✍️ Contact"),
    ("🎬 Kinolar", "🎬 Фильмы", "🎬 Movies"),
    ("🧸 Multfilmlar", "🧸 Мультфильмы", "🧸 Cartoons"),
    ("📺 Seriallar", "📺 Сериалы", "📺 Series"),
    ("🎵 Musiqalar", "🎵 Музыка", "🎵 Music"),
    ("🌐 Sayt", "🌐 Сайт", "🌐 Website"),
    ("💎 Premium olish", "💎 Получить Premium", "💎 Get Premium"),
    ("🎬 Kino nomi yoki kodi... 🍿", "🎬 Название или код фильма... 🍿", "🎬 Movie title or code... 🍿"),
    # /start
    ("✨ Assalomu alaykum, ", "✨ Здравствуйте, ", "✨ Hello, "),
    (" — kino olamiga xush kelibsiz 🍿", " — добро пожаловать в мир кино 🍿", " — welcome to the world of cinema 🍿"),
    ("Kino <b>nomi</b> yoki <b>kodini</b> yozing — qolganini o'zim hal qilaman 💫",
     "Напишите <b>название</b> или <b>код</b> фильма — остальное я сделаю сам 💫",
     "Type the movie <b>title</b> or <b>code</b> — I'll handle the rest 💫"),
    ("🌟 <b>Deyarli tayyor!</b>", "🌟 <b>Почти готово!</b>", "🌟 <b>Almost there!</b>"),
    ("Botdan to'liq foydalanish uchun kanalimizga obuna bo'ling va pastdagi tugmani bosing 👇",
     "Чтобы пользоваться ботом, подпишитесь на наш канал и нажмите кнопку ниже 👇",
     "To use the bot, subscribe to our channel and tap the button below 👇"),
    # qidiruv
    ("🔎 <b>Kino qidirish</b>", "🔎 <b>Поиск фильма</b>", "🔎 <b>Search movies</b>"),
    ("🔎 Qidirish uchun kamida <b>2 ta harf</b> yozing.", "🔎 Для поиска введите не менее <b>2 букв</b>.", "🔎 Type at least <b>2 letters</b> to search."),
    ("hozircha bazamizda yo'q.", "пока нет в нашей базе.", "is not in our library yet."),
    ("😔 Bu musiqa topilmadi (o'chirilgan bo'lishi mumkin).", "😔 Эта песня не найдена (возможно, удалена).", "😔 This song was not found (it may have been removed)."),
    ("kodli kino topilmadi.", "— фильм с таким кодом не найден.", "— no movie with this code."),
    ("📭 Hozircha bazada kinolar yo'q.", "📭 В базе пока нет фильмов.", "📭 There are no movies yet."),
    ("🍿 <b>Bugun qaysi kinoni ko'ramiz?</b>", "🍿 <b>Что посмотрим сегодня?</b>", "🍿 <b>What shall we watch today?</b>"),
    ("🎭 Hozircha o'xshash kinolar yo'q — tez orada qo'shiladi!", "🎭 Похожих фильмов пока нет — скоро добавим!", "🎭 No similar movies yet — coming soon!"),
    ("⚠️ Bu kinoning fayli topilmadi.", "⚠️ Файл этого фильма не найден.", "⚠️ This movie's file was not found."),
    ("⚠️ Kechirasiz, bu kino faylini yuborib bo'lmadi. Adminlar xabardor qilindi.",
     "⚠️ Извините, не удалось отправить файл. Администраторы уведомлены.",
     "⚠️ Sorry, the file could not be sent. Admins have been notified."),
    ("🔒 <b>Bu", "🔒 <b>Этот контент", "🔒 <b>This"),
    ("faqat Premium a'zolar uchun!</b>", "только для Premium-участников!</b>", "is for Premium members only!</b>"),
    ("💎 Premium obuna bilan ushbu va boshqa maxsus kontentdan cheklovsiz foydalaning.",
     "💎 С Premium вы получите доступ к этому и другому эксклюзивному контенту.",
     "💎 With Premium you get unlimited access to this and other exclusive content."),
    ("😔 Izlagan kinongiz topilmasa — /sorov", "😔 Не нашли фильм — /sorov", "😔 Can't find a movie — /sorov"),
    # kino ostidagi tugmalar va izoh
    ("📤 Do'stlarga ulashish", "📤 Поделиться", "📤 Share with friends"),
    ("🎭 O'xshashlari", "🎭 Похожие", "🎭 Similar"),
    ("💬 Izohlar va batafsil", "💬 Комментарии и подробности", "💬 Comments & details"),
    ("📺 Qolgan qismlar", "📺 Остальные части", "📺 More parts"),
    ("📋 Qismlar", "📋 Части", "📋 Parts"),
    ("Kod: ", "Код: ", "Code: "),
    ("🌍 Davlati: ", "🌍 Страна: ", "🌍 Country: "),
    ("📅 Yili: ", "📅 Год: ", "📅 Year: "),
    ("🎭 Janri: ", "🎭 Жанр: ", "🎭 Genre: "),
    ("🗣 Tili: ", "🗣 Язык: ", "🗣 Language: "),
    ("🎞 Sifati: ", "🎞 Качество: ", "🎞 Quality: "),
    ("-qism", "-я часть", " part"),
    # yordam
    ("ℹ️ <b>Botdan foydalanish</b>", "ℹ️ <b>Как пользоваться ботом</b>", "ℹ️ <b>How to use the bot</b>"),
    ("<b>Kino kodi</b> — kanaldagi postda ko'rsatilgan raqamni yuboring, kino darhol keladi.",
     "<b>Код фильма</b> — отправьте число из поста в канале, и фильм придёт сразу.",
     "<b>Movie code</b> — send the number from the channel post and the movie arrives instantly."),
    ("<b>Kino nomi</b> — nomini yozing, ro'yxatdagi raqamni tanlang.",
     "<b>Название</b> — напишите его и выберите номер из списка.", "<b>Title</b> — type it and pick a number from the list."),
    ("— izlagan kinongiz topilmasa, so'rang — qo'shamiz!", "— если не нашли фильм, попросите — мы добавим!", "— can't find a movie? Ask — we'll add it!"),
    ("— do'stlarni taklif qiling, har biri uchun +1 kun Premium oling", "— приглашайте друзей: +1 день Premium за каждого", "— invite friends: +1 day of Premium for each"),
    ("— sevimli janrlaringizda yangi kino chiqsa xabar olasiz", "— уведомления о новинках в любимых жанрах", "— get notified about new movies in your favorite genres"),
    ("<b>Top kinolar</b> — eng ko'p ko'rilganlar", "<b>Топ фильмов</b> — самые просматриваемые", "<b>Top movies</b> — most watched"),
    ("<b>Yangi kinolar</b> — yangi qo'shilganlar", "<b>Новые фильмы</b> — недавно добавленные", "<b>New movies</b> — recently added"),
    ("<b>Tasodifiy kino</b> — omadingizni sinab ko'ring", "<b>Случайный фильм</b> — испытайте удачу", "<b>Random movie</b> — try your luck"),
    ("<b>Sayt</b> — kinolar, multfilmlar va musiqalar katalogi", "<b>Сайт</b> — каталог фильмов, мультфильмов и музыки", "<b>Website</b> — catalog of movies, cartoons and music"),
    ("<b>Premium</b> — majburiy obunasiz va reklamasiz", "<b>Premium</b> — без обязательной подписки и рекламы", "<b>Premium</b> — no forced subscriptions or ads"),
    ("<b>Qo'llab-quvvatlash</b> — loyihamizga yordam", "<b>Поддержать</b> — помогите проекту", "<b>Support</b> — help the project"),
    ("<b>Murojaat</b> — kino so'rash yoki taklif yuborish", "<b>Обращение</b> — запросить фильм или отправить предложение", "<b>Contact</b> — request a movie or send feedback"),
    # kuzatish va so'rovlar
    ("🔔 <b>Yangi kinolardan xabardor bo'ling</b>", "🔔 <b>Узнавайте о новинках первыми</b>", "🔔 <b>Get notified about new movies</b>"),
    ("Sevimli janrlaringizni tanlang — shu janrda yangi kino qo'shilishi bilan bot sizga xabar beradi",
     "Выберите любимые жанры — бот сообщит, когда в них появится новый фильм",
     "Pick your favorite genres — the bot will tell you when a new movie is added"),
    ("Tanlangan: ", "Выбрано: ", "Selected: "),
    ("📬 Haftalik tavsiya: ", "📬 Недельная подборка: ", "📬 Weekly picks: "),
    ("yoqilgan", "включена", "on"), ("o'chiq", "выключена", "off"),
    ("✅ Tayyor", "✅ Готово", "✅ Done"),
    ("🆕 <b>Yangi kino qo'shildi!</b>", "🆕 <b>Добавлен новый фильм!</b>", "🆕 <b>New movie added!</b>"),
    ("▶️ Ko'rish", "▶️ Смотреть", "▶️ Watch"),
    ("🔔 Obunani sozlash", "🔔 Настроить подписку", "🔔 Manage subscription"),
    ("📬 <b>Bu hafta siz uchun</b>", "📬 <b>Подборка на эту неделю</b>", "📬 <b>Your picks this week</b>"),
    ("Yoqimli hordiq! 🍿", "Приятного просмотра! 🍿", "Enjoy! 🍿"),
    ("🗳 <b>Eng ko'p so'ralgan kinolar</b>", "🗳 <b>Самые запрашиваемые фильмы</b>", "🗳 <b>Most requested movies</b>"),
    ("🙋 Menga ham kerak: ", "🙋 Мне тоже нужно: ", "🙋 I want it too: "),
    ("✅ Ovozingiz qo'shildi!", "✅ Ваш голос учтён!", "✅ Your vote has been added!"),
    ("✅ <b>So'rovingiz qabul qilindi!</b>", "✅ <b>Ваш запрос принят!</b>", "✅ <b>Your request has been received!</b>"),
    ("🌐 <b>Til / Язык / Language</b>", "🌐 <b>Язык</b>", "🌐 <b>Language</b>"),
    ("✅ Til o'zgartirildi.", "✅ Язык изменён.", "✅ Language changed."),
    # premium
    ("💎 Premium tizimi hozircha faol emas.", "💎 Premium пока недоступен.", "💎 Premium is not available yet."),
    ("🎁 <b>Sovg'a!</b>", "🎁 <b>Подарок!</b>", "🎁 <b>A gift!</b>"),
    ("kunlik bepul Premium</b> berildi.", "дней бесплатного Premium</b> подарено.", "days of free Premium</b> added."),
    # tanishtiruv
    ("🧭 <b>1/3 — Qidirish</b>", "🧭 <b>1/3 — Поиск</b>", "🧭 <b>1/3 — Search</b>"),
    ("Kino <b>nomini</b> yoki kanaldagi postdagi <b>kodni</b> yozing — kino darhol keladi.",
     "Напишите <b>название</b> фильма или <b>код</b> из поста в канале — фильм придёт сразу.",
     "Type the movie <b>title</b> or the <b>code</b> from the channel post — the movie arrives instantly."),
    ("Topilmasa, /sorov bilan so'rang: kino qo'shilishi bilan xabar beramiz.", "Не нашли — попросите через /sorov: сообщим, как только добавим.", "Not found? Ask with /sorov — we'll tell you once it's added."),
    ("🧭 <b>2/3 — Sayt va saqlash</b>", "🧭 <b>2/3 — Сайт и сохранение</b>", "🧭 <b>2/3 — Website & saving</b>"),
    ("Kino ostida 👍 baho, 📤 ulashish va «💬 Izohlar va batafsil» tugmalari bor. Sayt orqali kinolarni saqlab, izoh qoldirishingiz mumkin: pastdagi «🌐 Sayt» tugmasi (yoki /sayt).",
     "Под фильмом есть кнопки 👍 оценка, 📤 поделиться и «💬 Комментарии и подробности». На сайте можно сохранять фильмы и писать комментарии: команда /sayt.",
     "Under each movie you'll find 👍 rating, 📤 share and “💬 Comments & details”. On the website you can save movies and comment: use /sayt."),
    ("🧭 <b>3/3 — Xabardor bo'ling</b>", "🧭 <b>3/3 — Будьте в курсе</b>", "🧭 <b>3/3 — Stay in the loop</b>"),
    ("Sevimli janrlaringizni tanlang — shu janrda yangi kino chiqsa, bot o'zi xabar beradi. Faqat siz xohlagan kinolar, kuniga ko'pi bilan 3 ta.",
     "Выберите любимые жанры — бот сам сообщит о новинках. Только то, что вам интересно, не более 3 в день.",
     "Pick your favorite genres — the bot will tell you about new movies. Only what you like, at most 3 a day."),
    ("Keyingisi ➡️", "Далее ➡️", "Next ➡️"),
    ("O'tkazib yuborish", "Пропустить", "Skip"),
    ("🔔 Janrlarni tanlash", "🔔 Выбрать жанры", "🔔 Pick genres"),
    ("✅ Tushunarli", "✅ Понятно", "✅ Got it"),
    ("✅ Tanishtiruv tugadi. Janrlarni tanlang 👇", "✅ Знакомство завершено. Выберите жанры 👇", "✅ Tour finished. Pick your genres 👇"),
    ("✅ Tayyor! Kino nomini yozing — qolganini o'zim bajaraman 🍿", "✅ Готово! Напишите название фильма — остальное я сделаю сам 🍿", "✅ All set! Type a movie title — I'll handle the rest 🍿"),
    # umumiy
    ("❌ Bekor qilish", "❌ Отмена", "❌ Cancel"),
    ("⬅️ Orqaga", "⬅️ Назад", "⬅️ Back"),
    ("⏳ Biroz kuting...", "⏳ Подождите...", "⏳ Please wait..."),
    ("⚠️ Kutilmagan xatolik yuz berdi. Iltimos, qaytadan urinib ko'ring.", "⚠️ Произошла ошибка. Попробуйте ещё раз.", "⚠️ Something went wrong. Please try again."),
]

_IDX = {"ru": 1, "en": 2}
_MAP: Dict[str, Tuple[str, str]] = {p[0]: (p[1], p[2]) for p in PHRASES}
_RE = re.compile("|".join(re.escape(k) for k in sorted(_MAP, key=len, reverse=True)))


def translate(text: str, lang: str) -> str:
    if lang not in _IDX or not text:
        return text
    i = _IDX[lang] - 1
    return _RE.sub(lambda m: _MAP[m.group(0)][i], text)


def translate_markup(kb, lang: str):
    """Tugmalar matnini (inline va reply) tarjima qiladi; asl obyektni o'zgartirmaydi."""
    if lang not in _IDX or not isinstance(kb, dict):
        return kb
    out = copy.deepcopy(kb)
    for key in ("inline_keyboard", "keyboard"):
        for row in out.get(key, []) or []:
            for b in row:
                if isinstance(b, dict) and isinstance(b.get("text"), str):
                    b["text"] = translate(b["text"], lang)
    if isinstance(out.get("input_field_placeholder"), str):
        out["input_field_placeholder"] = translate(out["input_field_placeholder"], lang)
    return out


def button_aliases() -> Dict[str, str]:
    """{tarjima qilingan tugma matni: asl o'zbekcha matn} — pastki menyu bosilganda to'g'ri ishlov beruvchi topilishi uchun."""
    out = {}
    for uz, ru, en in PHRASES:
        for tr in (ru, en):
            if tr and tr != uz:
                out[tr] = uz
    return out
