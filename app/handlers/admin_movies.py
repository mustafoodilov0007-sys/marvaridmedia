"""Admin: 🎬 Kino qo'shish (seriallar bilan), 🗑️ o'chirish/tahrirlash va 📢 kanalga e'lon."""

from __future__ import annotations

import logging
import re
import time

from .. import genres
from ..core import NEXT, Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb, number_rows
from ..telegram import InputFile, TelegramError
from ..texts import B, CATEGORIES, cat_icon, cat_name
from ..utils import (entities_to_html, esc, extract_media, fmt_date, fmt_num, message_html, normalize, post_link,
                     premium_html, truncate)
from .contact import notify_requesters
from .user import build_list, fmt_item, part_label, search_ids

log = logging.getLogger("admin.movies")

CODE_RE = re.compile(r"#?(\d{1,9})")


def _cap_html(msg) -> str:
    """Fayl izohi formatlash bilan (premium emoji, qalin...) — HTML ko'rinishda."""
    cap = (msg or {}).get("caption") or ""
    return entities_to_html(cap, msg.get("caption_entities")) if cap else ""


def _stale(ctx: Ctx) -> None:
    ctx.answer("⚠️ Bu tugma eskirgan. Qaytadan boshlang.", alert=True)


# ═════════════════════════ 🎬 Kino qo'shish ═════════════════════════

def _cat(ctx: Ctx) -> str:
    c = ctx.sdata.get("cat")
    return c if c in CATEGORIES else "movie"


def _noun(ctx: Ctx) -> str:
    """«kino» / «multfilm» / «musiqa» — joriy turga mos so'z."""
    return cat_name(_cat(ctx)).lower()


def _is_music(ctx: Ctx) -> bool:
    return _cat(ctx) == "music"


def ask_file(ctx: Ctx) -> None:
    """«🎬 Kino qo'shish» bosilganda — avval fayl so'raladi, turi keyin tanlanadi."""
    ctx.set_state("am:file")
    ctx.send("➕ <b>Kino yoki multfilm qo'shish</b>\n\n"
             "📤 <b>Video</b> yoki <b>fayl</b> yuboring (kanaldan forward qilsangiz ham bo'ladi).\n"
             "So'ng bot turini so'raydi: 🎬 Kino yoki 🧸 Multfilm.\n\n"
             f"🎵 Musiqa uchun — admin paneldagi «{B.ADD_MUSIC}» tugmasi.",
             ikb([btn("⚡️ Ommaviy qo'shish (forward)", "am:bulk", style=PRIMARY)],
                 [btn("❌ Bekor qilish", "cancel", style=DANGER)]))


@router.state("am:file", admin=True)
def st_file(ctx: Ctx) -> None:
    if music_from_message(ctx.message):
        begin_music(ctx)  # audio yuborilsa — musiqa bo'limiga o'tamiz
        return
    media = extract_media(ctx.message)
    if not media:
        ctx.send("❗️ Iltimos, kino <b>videosini</b> yoki <b>fayl</b> yuboring.", cancel_kb())
        return
    ask_category(ctx, prefill=media)


def category_rows(prefix: str) -> list:
    return [[btn("🎬 Kino", f"{prefix}:movie", style=SUCCESS), btn("📺 Serial", f"{prefix}:serial", style=PRIMARY),
             btn("🧸 Multfilm", f"{prefix}:cartoon", style=SUCCESS)],
            [btn("❌ Bekor qilish", "cancel", style=DANGER)]]


def ask_category(ctx: Ctx, prefill=None) -> None:
    """Fayl qabul qilingach — turini tanlash: kino yoki multfilm (musiqa — alohida bo'lim)."""
    data = {}
    if prefill:
        data = {"file_id": prefill[0], "file_type": prefill[1], "caption": prefill[2],
                "caption_html": _cap_html(ctx.message)}
    ctx.set_state("am:cat", **data)
    if prefill:
        head = "📹 <b>Fayl qabul qilindi!</b>"
    else:
        head = "➕ <b>Yangi qo'shish</b>"
    ctx.send(f"{head}\n\nBu nima? Turini tanlang 👇", ikb(*category_rows("am:cat")))


def start_add(ctx: Ctx, prefill=None, category: str = "movie") -> None:
    code = ctx.db.next_code()
    data = {"cat": category if category in CATEGORIES else "movie"}
    if prefill:
        data.update({"file_id": prefill[0], "file_type": prefill[1], "caption": prefill[2],
                     "caption_html": ctx.sdata.get("caption_html", "")})
    ctx.set_state("am:code", **data)
    icon, name = cat_icon(data["cat"]), cat_name(data["cat"])
    noun = name.lower()
    if prefill:
        head = "🎵 <b>Audio qabul qilindi!</b>" if prefill[1] == "audio" else "📹 <b>Video qabul qilindi!</b>"
        head += f"  •  {icon} {name}"
    else:
        head = f"{icon} <b>Yangi {noun} qo'shish</b>"
    if data["cat"] == "music":
        # musiqalar kodsiz — kod so'ralmaydi
        if prefill:
            ctx.goto("am:title", code=None)
            ask_title(ctx, None)
        else:
            ctx.goto("am:video", code=None)
            ctx.send(f"{head}\n\n📤 Musiqani yuboring (audio yoki fayl).\n"
                     f"💡 Ko'p musiqani birdaniga qo'shish uchun admin paneldagi «{B.ADD_MUSIC}» tugmasi qulay.",
                     cancel_kb())
        return
    rows = [[btn(f"🆕 Avtomatik kod: {code}", "am:auto", style=SUCCESS)]]
    if not prefill:
        rows.append([btn("⚡️ Ommaviy qo'shish (forward)", "am:bulk", style=PRIMARY)])
    rows.append([btn("❌ Bekor qilish", "cancel", style=DANGER)])
    ctx.send(f"{head}\n\n"
             f"1️⃣ {name} uchun <b>kod</b> yuboring (faqat raqam).\n\n"
             f"💡 Bo'sh kod: <code>{code}</code> — pastdagi tugma bilan avtomatik tanlang.\n"
             f"ℹ️ Band kod yuborsangiz, o'sha {noun}ga yangi qism qo'shiladi."
             + ("" if prefill else f"\n⚡️ Ko'p {noun}ni birdaniga ko'chirish uchun — «Ommaviy qo'shish»."),
             ikb(*rows))


@router.button(B.ADD_MOVIE, admin=True)
def btn_add_movie(ctx: Ctx) -> None:
    ask_file(ctx)


def admin_media_shortcut(ctx: Ctx) -> bool:
    """Admin hech qanday bo'limsiz fayl yuborsa: audio — musiqaga, video — kino/multfilm qo'shishga."""
    if music_from_message(ctx.message):
        begin_music(ctx)
        return True
    media = extract_media(ctx.message)
    if not media:
        return False
    ask_category(ctx, prefill=media)
    return True


router.special["admin_media"] = admin_media_shortcut


def choose_code(ctx: Ctx, code: int) -> None:
    if code <= 0:
        ctx.send("❗️ Kod musbat son bo'lishi kerak.", cancel_kb())
        return
    movie = ctx.db.get_movie_by_code(code)
    if movie:
        n = ctx.db.count_parts(movie["id"])
        ctx.send(f"⚠️ <b>{code}</b> kodi band: {cat_icon(movie['category'])} <b>{esc(movie['title'])}</b>"
                 f" ({n} qism).\n\n"
                 "Unga yangi qism qo'shamizmi yoki boshqa kod tanlaysizmi?",
                 ikb([btn(f"➕ {n + 1}-qism sifatida qo'shish", f"am:addpart:{movie['id']}", style=SUCCESS)],
                     [btn("🔢 Boshqa kod kiritish", "am:new", style=PRIMARY)],
                     [btn("❌ Bekor qilish", "cancel", style=DANGER)]))
        return
    if ctx.sdata.get("file_id"):
        ctx.goto("am:title", code=code)
        ask_title(ctx, code)
        return
    ctx.goto("am:video", code=code)
    if _is_music(ctx):
        ctx.send(f"✅ Kod: <b>{code}</b>\n\n"
                 "2️⃣ Endi <b>musiqani</b> yuboring 🎵\n"
                 "Audio, fayl yoki klip (video) ko'rinishida yuborishingiz, kanaldan forward qilishingiz mumkin.",
                 cancel_kb())
        return
    ctx.send(f"✅ Kod: <b>{code}</b>\n\n"
             f"2️⃣ Endi {_noun(ctx)} <b>videosini</b> yuboring 📹\n"
             "Video yoki fayl ko'rinishida yuborishingiz, kanaldan forward qilishingiz mumkin.", cancel_kb())


def ask_title(ctx: Ctx, code: int) -> None:
    if _is_music(ctx):
        example = "Shahzoda — Yoningdaman"
    elif _cat(ctx) == "cartoon":
        example = "Shrek 2 (2004)"
    elif _cat(ctx) == "serial":
        example = "Katta sichqon"
    else:
        example = "Avatar: Suv yo'li (2022)"
    ready = f"✅ Kod: <b>{code}</b>, fayl tayyor." if code else "✅ Fayl tayyor."
    ctx.send(f"{ready}\n\n"
             f"3️⃣ {cat_name(_cat(ctx))} <b>nomini</b> yuboring:\n💡 Masalan: <code>{esc(example)}</code>",
             cancel_kb())


@router.state("am:code", admin=True)
def st_code(ctx: Ctx) -> None:
    m = CODE_RE.fullmatch(ctx.text.strip())
    if not m:
        ctx.send("❗️ Kod faqat raqamlardan iborat bo'lishi kerak (masalan: <code>25</code>).", cancel_kb())
        return
    choose_code(ctx, int(m.group(1)))


@router.state("am:video", admin=True)
def st_video(ctx: Ctx) -> None:
    media = extract_media(ctx.message, audio=_is_music(ctx))
    if not media:
        if _is_music(ctx):
            ctx.send("❗️ Iltimos, musiqani <b>audio</b> yoki <b>fayl</b> ko'rinishida yuboring.", cancel_kb())
        else:
            ctx.send(f"❗️ Iltimos, {_noun(ctx)}ni <b>video</b> yoki <b>fayl</b> ko'rinishida yuboring.",
                     cancel_kb())
        return
    ctx.goto("am:title", file_id=media[0], file_type=media[1], caption=media[2], caption_html=_cap_html(ctx.message))
    ask_title(ctx, ctx.sdata["code"])


@router.state("am:title", admin=True)
def st_title(ctx: Ctx) -> None:
    title = ctx.text.strip()
    if extract_media(ctx.message, audio=True):
        ctx.send(f"ℹ️ Avval {_noun(ctx)} <b>nomini</b> matn ko'rinishida yuboring.\n"
                 "Qo'shimcha qismlarni kino saqlangandan so'ng «➕ Keyingi qismni qo'shish» orqali yuborasiz.")
        return
    if not title or title.startswith("/"):
        ctx.send(f"❗️ {cat_name(_cat(ctx))} nomini matn ko'rinishida yuboring.", cancel_kb())
        return
    if len(title) > 150:
        ctx.send("❗️ Nom juda uzun — 150 belgigacha qisqartiring.", cancel_kb())
        return
    ctx.goto("am:title", title=title)
    if _is_music(ctx):
        ask_desc(ctx)
    else:
        begin_meta(ctx)


def ask_desc(ctx: Ctx) -> None:
    ctx.goto("am:desc")
    rows = []
    if ctx.sdata.get("caption"):
        rows.append([btn("📄 Fayl izohidan olish", "am:usecap", style=PRIMARY)])
    rows.append([btn("⏭ O'tkazib yuborish", "am:skip", style=SUCCESS)])
    rows.append([btn("❌ Bekor qilish", "cancel", style=DANGER)])
    if _is_music(ctx):
        ctx.send(f"4️⃣ Musiqa haqida <b>qisqacha ma'lumot</b> yuboring:\n💡 Masalan: ijrochi, albom, yil.\n\n"
                 "Yoki bu bosqichni o'tkazib yuboring 👇", ikb(*rows))
        return
    ctx.send(f"9️⃣ Endi {_noun(ctx)} haqida <b>izoh</b> yozing ✍️\n"
             "💡 Masalan: syujeti, IMDb reytingi. Izoh botda kino bilan chiqadi, kanal postiga qo'yilmaydi.\n"
             "Premium emoji, <b>qalin</b>, <i>kursiv</i> yozuvlar saqlanadi.\n\nYoki o'tkazib yuboring 👇", ikb(*rows))


@router.state("am:desc", admin=True)
def st_desc(ctx: Ctx) -> None:
    if has_image(ctx.message):  # poster izoh bilan birga (yoki izohsiz) yuborildi
        poster = poster_from(ctx)
        if not poster:
            poster_error(ctx)
            return
        cap = (ctx.message.get("caption") or "").strip()[:800]
        html = message_html(ctx.message).strip() if cap and len(ctx.message.get("caption") or "") <= 800 else ""
        ctx.goto("am:desc", poster_pre=poster)
        ctx.send("🖼 Poster qabul qilindi!" + (" 📝 Rasm izohi ma'lumot sifatida olindi." if cap else ""))
        after_desc(ctx, cap, html)
        return
    desc = ctx.text.strip()
    if not desc:
        ctx.send("❗️ Ma'lumotni matn ko'rinishida yuboring yoki «⏭ O'tkazib yuborish» ni bosing.")
        return
    if len(desc) > 800:
        ctx.send("❗️ Ma'lumot juda uzun — 800 belgigacha qisqartiring.")
        return
    after_desc(ctx, desc, message_html(ctx.message).strip())


# ───── 🎭 janr va 📅 yil ─────

def genre_rows(selected, toggle_prefix: str, done_cb: str, done_text: str = "✅ Tayyor — davom etish") -> list:
    rows, row = [], []
    for k in genres.GENRES:
        on = k in selected
        row.append(btn(("✅ " if on else "") + genres.label(k), f"{toggle_prefix}{k}", style=SUCCESS if on else None))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn(done_text, done_cb, style=PRIMARY)])
    return rows


def genre_prompt(title: str, selected) -> str:
    chosen = " • ".join(genres.label(k) for k in genres.GENRES if k in selected) or "—"
    return (f"4️⃣ <b>{esc(title)}</b> — <b>janrini</b> tanlang 🎭 (4 tagacha)\n\n"
            f"Tanlangan: {chosen}\n\n"
            "💡 Tanlab bo'lgach «✅ Tayyor» ni bosing.")


def begin_meta(ctx: Ctx) -> None:
    """Kino/multfilm: janr → davlat → yil → til → izoh. Fayl izohidan oldindan aniqlab qo'yiladi."""
    d = ctx.sdata
    title, cap = d.get("title") or "", d.get("caption") or ""
    found = genres.detect(title, cap)
    ctx.goto("am:genre", genres=found, year=genres.detect_year(title, cap),
             country=genres.detect_country(cap), lang=genres.detect_lang(cap))
    ctx.send(genre_prompt(title, found), {"inline_keyboard": genre_rows(found, "am:g:", "am:gok")})


def country_rows(selected: str, prefix: str, extra=None) -> list:
    rows, row = [], []
    for k in genres.COUNTRIES:
        on = k == selected
        row.append(btn(("✅ " if on else "") + genres.country_label(k), f"{prefix}{k}", style=SUCCESS if on else None))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows + (extra or [])


YEAR_BUTTONS = list(range(2026, 1999, -1))  # 2026 … 2000


def year_rows(selected: int, prefix: str, extra=None) -> list:
    rows, row = [], []
    for y in YEAR_BUTTONS:
        on = y == selected
        row.append(btn(("✅" if on else "") + str(y), f"{prefix}{y}", style=SUCCESS if on else None))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows + (extra or [])


def lang_rows(selected: str, prefix: str, extra=None) -> list:
    rows = [[btn(("✅ " if k == selected else "") + genres.lang_label(k), f"{prefix}{k}",
                 style=SUCCESS if k == selected else PRIMARY)] for k in genres.LANGS]
    return rows + (extra or [])


def _skip_row(cb: str) -> list:
    return [[btn("⏭ O'tkazib yuborish", cb, style=DANGER)]]


def ask_country(ctx: Ctx) -> None:
    ctx.goto("am:country")
    sel = ctx.sdata.get("country") or ""
    hint = f"\n💡 Fayl izohidan topildi: <b>{genres.country_label(sel)}</b> — to'g'ri bo'lsa shuni bosing." if sel else ""
    ctx.send(f"5️⃣ <b>Davlatini</b> tanlang 🌍{hint}",
             {"inline_keyboard": country_rows(sel, "am:c:", _skip_row("am:c:-"))})


def ask_year(ctx: Ctx) -> None:
    ctx.goto("am:year")
    sel = int(ctx.sdata.get("year") or 0)
    hint = f"\n💡 Topilgan yil: <b>{sel}</b>" if sel else ""
    ctx.send(f"6️⃣ <b>Chiqqan yilini</b> tanlang 📅{hint}\n\n"
             "Ro'yxatda yo'q bo'lsa — yilni yozib yuboring (masalan <code>1997</code>).",
             {"inline_keyboard": year_rows(sel, "am:y:", _skip_row("am:y:0"))})


def ask_lang(ctx: Ctx) -> None:
    ctx.goto("am:lang")
    sel = ctx.sdata.get("lang") or ""
    ctx.send("7️⃣ <b>Tilini</b> tanlang 🗣", {"inline_keyboard": lang_rows(sel, "am:l:", _skip_row("am:l:-"))})


def quality_rows(selected, prefix: str, done_cb: str, done_text: str = "✅ Tayyor — davom etish") -> list:
    row = [btn(("✅ " if k in selected else "") + v, f"{prefix}{k}", style=SUCCESS if k in selected else None)
           for k, v in genres.QUALITIES.items()]
    return [row, [btn(done_text, done_cb, style=PRIMARY)]]


def quality_prompt(selected) -> str:
    chosen = genres.quality_text(genres.quality_dump(selected)) or "—"
    return (f"8️⃣ <b>Video sifatini</b> tanlang 🎞 (bir nechtasini tanlash mumkin)\n\n"
            f"Tanlangan: <b>{chosen}</b>\n\n💡 Tanlab bo'lgach «✅ Tayyor» ni bosing.")


def ask_quality(ctx: Ctx) -> None:
    ctx.goto("am:quality")
    sel = ctx.sdata.get("quality") or []
    ctx.send(quality_prompt(sel), {"inline_keyboard": quality_rows(sel, "am:q:", "am:qok")})


LINK_RE = re.compile(r"(?:https?://)?(?:t\.me|telegram\.me)/\S+|https?://\S+", re.I)


def clean_link(text: str) -> str:
    m = LINK_RE.search(text or "")
    if not m:
        return ""
    url = m.group(0).rstrip(").,")
    return url if url.lower().startswith("http") else "https://" + url


def after_desc(ctx: Ctx, desc: str, desc_html: str = "") -> None:
    ctx.goto("am:desc", desc=desc, desc_html=desc_html)
    if _cat(ctx) == "serial":
        ctx.goto("am:link")
        ctx.send("🔗 <b>Qolgan qismlar linki</b>\n\n"
                 "Serialning qolgan qismlari joylangan Telegram guruh yoki post havolasini yuboring.\n"
                 "💡 Masalan: <code>https://t.me/MarvaridMediaderial/1170</code>\n\n"
                 "Bot serialni yuborganda «qolgan qismlari bu yerda 👇» deb shu linkni qo'shadi.\n"
                 "📢 Kanal e'loniga bu link <b>qo'yilmaydi</b>.",
                 ikb([btn("⏭ O'tkazib yuborish", "am:lskip", style=DANGER)]))
        return
    to_poster(ctx)


def to_poster(ctx: Ctx) -> None:
    d = ctx.sdata
    if d.get("poster_pre"):
        ctx.goto("am:poster")
        show_confirm(ctx, d["poster_pre"])
    else:
        ask_poster(ctx, d.get("desc") or "", d.get("desc_html") or "")


@router.state("am:link", admin=True)
def st_link(ctx: Ctx) -> None:
    if has_image(ctx.message):
        poster = poster_from(ctx)
        if not poster:
            poster_error(ctx)
            return
        ctx.goto("am:link", poster_pre=poster)
        ctx.send("🖼 Poster saqlandi! Endi linkni yuboring yoki «⏭ O'tkazib yuborish» ni bosing.")
        return
    link = clean_link(ctx.text)
    if not link or len(link) > 300:
        ctx.send("❗️ Havolani yuboring (masalan <code>https://t.me/guruh/123</code>) "
                 "yoki «⏭ O'tkazib yuborish» ni bosing.", ikb([btn("⏭ O'tkazib yuborish", "am:lskip", style=DANGER)]))
        return
    ctx.goto("am:link", group_link=link)
    ctx.send(f"🔗 Link saqlandi ✅\n{esc(link)}", preview=False)
    to_poster(ctx)


@router.state("am:genre", "am:country", "am:year", "am:lang", "am:quality", admin=True)
def st_meta(ctx: Ctx) -> None:
    if has_image(ctx.message):  # poster oldinroq yuborildi — saqlab qo'yamiz, bosqichlar davom etadi
        poster = poster_from(ctx)
        if not poster:
            poster_error(ctx)
            return
        ctx.goto(ctx.state, poster_pre=poster)
        ctx.send("🖼 Poster saqlandi! Yuqoridagi tugmalar bilan davom eting 👆")
        return
    text = ctx.text.strip()
    if ctx.state == "am:year" and re.fullmatch(r"\d{4}", text):
        if not genres.YEAR_MIN <= int(text) <= genres.YEAR_MAX:
            ctx.send(f"❗️ Yil {genres.YEAR_MIN}–{genres.YEAR_MAX} oralig'ida bo'lsin.")
            return
        ctx.goto("am:year", year=int(text))
        ctx.send(f"📅 Yil: <b>{text}</b> ✅")
        ask_lang(ctx)
        return
    hint = {"am:genre": "janrlarni tanlab «✅ Tayyor» ni bosing", "am:country": "davlatni tanlang",
            "am:year": "yilni tanlang yoki yozib yuboring (masalan <code>2017</code>)", "am:lang": "tilni tanlang",
            "am:quality": "sifatni tanlab «✅ Tayyor» ni bosing"}
    ctx.send(f"👆 Yuqoridagi tugmalardan {hint.get(ctx.state, 'tanlang')}.")


POSTER_LIMIT = 10 * 1024 * 1024  # sendPhoto shundan katta rasmni qabul qilmaydi


def has_image(msg: dict) -> bool:
    doc = msg.get("document") or {}
    return bool(msg.get("photo")) or (doc.get("mime_type") or "").startswith("image/")


def poster_from(ctx: Ctx):
    """Xabardagi rasmni poster file_id siga aylantiradi.

    Oddiy rasm — to'g'ridan-to'g'ri. «Fayl» (siqilmagan) qilib yuborilgan rasm esa yuklab olinib,
    rasm sifatida qayta yuboriladi (aks holda uni poster qilib bo'lmaydi). Bo'lmasa — None.
    """
    msg = ctx.message
    if msg.get("photo"):
        return msg["photo"][-1]["file_id"]
    doc = msg.get("document") or {}
    if not (doc.get("mime_type") or "").startswith("image/") or (doc.get("file_size") or 0) > POSTER_LIMIT:
        return None
    try:
        info = ctx.bot.call("getFile", {"file_id": doc["file_id"]})
        data = ctx.bot.download_file(info["file_path"])
        sent = ctx.bot.call("sendPhoto", {"chat_id": ctx.chat_id, "disable_notification": True},
                            files={"photo": InputFile(doc.get("file_name") or "poster.jpg", data, doc["mime_type"])})
        file_id = sent["photo"][-1]["file_id"]
        ctx.bot.safe("deleteMessage", {"chat_id": ctx.chat_id, "message_id": sent["message_id"]})
        return file_id
    except (TelegramError, KeyError, IndexError, TypeError) as exc:
        log.warning("Fayl-rasmni posterga aylantirib bo'lmadi: %s", exc)
        return None


def poster_error(ctx: Ctx, extra: str = "") -> None:
    doc = ctx.message.get("document") or {}
    if (doc.get("mime_type") or "").startswith("image/") and (doc.get("file_size") or 0) > POSTER_LIMIT:
        ctx.send("❗️ Rasm juda katta (10 MB dan ortiq). Uni oddiy <b>rasm</b> (siqilgan) qilib yuboring." + extra)
    else:
        ctx.send("❗️ Poster uchun <b>rasm</b> yuboring." + extra)


def ask_poster(ctx: Ctx, desc: str, desc_html: str = "") -> None:
    ctx.goto("am:poster", desc=desc, desc_html=desc_html)
    what = "muqovasini" if _is_music(ctx) else "posterini"
    step = "5️⃣" if _is_music(ctx) else "🔟"
    ctx.send(f"{step} {cat_name(_cat(ctx))} <b>{what}</b> (rasm) yuboring 🖼\n"
             "Rasm saytda, kanal e'lonida va qismlar ro'yxatida chiroyli ko'rinadi.\n\nYoki o'tkazib yuboring 👇",
             ikb([btn("⏭ O'tkazib yuborish", "am:skip", style=SUCCESS)], [btn("❌ Bekor qilish", "cancel", style=DANGER)]))


@router.state("am:poster", admin=True)
def st_poster(ctx: Ctx) -> None:
    poster = poster_from(ctx)
    if not poster:
        poster_error(ctx, " Yoki «⏭ O'tkazib yuborish» ni bosing.")
        return
    show_confirm(ctx, poster)


def show_confirm(ctx: Ctx, poster) -> None:
    ctx.goto("am:confirm", poster=poster)
    d = ctx.sdata
    file_txt = {"video": "video", "audio": "audio"}.get(d["file_type"], "hujjat (fayl)")
    poster_txt = "bor ✅" if poster else "yo'q"
    cat = _cat(ctx)
    text = ("✅ <b>Hammasi tayyor! Tekshirib chiqing:</b>\n\n"
            f"🏷 Turi: <b>{cat_icon(cat)} {cat_name(cat)}</b>\n"
            + (f"🔢 Kod: <code>{d['code']}</code>\n" if d.get("code") else "") +
            f"{cat_icon(cat)} Nomi: <b>{esc(d['title'])}</b>\n"
            f"📝 Ma'lumot: {esc(truncate(d.get('desc') or '—', 300))}\n"
            + ("" if cat == "music" else
               f"🎭 Janr: {genres.line(genres.dump(d.get('genres') or [])) or '—'}\n"
               f"🌍 Davlat: {genres.country_label(d.get('country')) or '—'}\n"
               f"📅 Yil: {d.get('year') or '—'}\n"
               f"🗣 Til: {genres.lang_label(d.get('lang')) or '—'}\n"
               f"🎞 Sifat: {genres.quality_text(genres.quality_dump(d.get('quality') or [])) or '—'}\n") +
            (f"🔗 Qismlar linki: {esc(d.get('group_link') or '—')}\n" if cat == "serial" else "") +
            f"📹 Fayl: {file_txt}\n"
            f"🖼 Poster: {poster_txt}\n\n"
            "Qanday saqlaymiz? 👇")
    rows = [[btn("✅ Saqlash", "am:save:0", style=SUCCESS)]]
    if ctx.app.setting_bool("premium_enabled"):
        rows.append([btn("💎 Premium sifatida saqlash", "am:save:1", style=PRIMARY)])
    rows.append([btn("❌ Bekor qilish", "cancel", style=DANGER)])
    ctx.send(text, ikb(*rows))


@router.state("am:confirm", admin=True)
def st_confirm(ctx: Ctx) -> None:
    ctx.send("👆 Yuqoridagi tugmalardan birini tanlang: «✅ Saqlash» yoki «❌ Bekor qilish».")


def save_movie(ctx: Ctx, premium: bool) -> None:
    d = ctx.sdata
    db = ctx.db
    if d.get("code") and db.get_movie_by_code(d["code"]):
        ctx.answer("⚠️ Bu kod band bo'lib qoldi! Boshqa kod tanlang.", alert=True)
        start_add(ctx, prefill=(d["file_id"], d["file_type"], d.get("caption", "")), category=_cat(ctx))
        return
    cat = _cat(ctx)
    movie_id = db.add_movie(d["code"], d["title"], d.get("desc") or "", d.get("poster"), premium,
                            ctx.user_id, d["file_id"], d["file_type"], cat, d.get("desc_html") or "",
                            genre_keys=d.get("genres"), year=d.get("year"),
                            country=d.get("country"), lang=d.get("lang"),
                            quality=genres.quality_dump(d.get("quality") or []),
                            group_link=d.get("group_link") or "" if cat == "serial" else "")
    ctx.clear_state()
    ctx.answer("✅ Saqlandi!")
    code = db.get_movie(movie_id)["code"]
    notified = notify_requesters(ctx.app, movie_id)
    ctx.edit(f"🎉 <b>{cat_name(cat)} muvaffaqiyatli saqlandi!</b>\n\n"
             f"{cat_icon(cat)} <b>{esc(d['title'])}</b>\n"
             + (f"🔢 Kod: <code>{code}</code>\n" if code > 0 else "") +
             f"{'💎 Turi: Premium' if premium else '🆓 Turi: Oddiy'}\n"
             f"🔗 Havola: {esc(ctx.app.deep_link(code))}"
             + (f"\n\n📨 Bu kinoni so'ragan <b>{notified}</b> kishiga avtomatik xabar yuborildi!" if notified else ""),
             ikb([btn("📢 Kanalga e'lon qilish", f"an:{movie_id}", style=SUCCESS)],
                 [btn("➕ Keyingi qismni qo'shish", f"am:addpart:{movie_id}", style=PRIMARY)],
                 [btn("🎞 Shorts qo'shish (saytda)", f"dm:shadd:{movie_id}", style=PRIMARY)],
                 [btn("➕ Yana qo'shish", "am:new", style=SUCCESS)]))


def throttled_status(ctx: Ctx, state: str, text: str, kb, interval: float) -> None:
    """Holat xabarini ko'pi bilan `interval` soniyada bir marta yangilaydi (eskisini o'chirib).
    Ko'plab forward qilinganda Telegram cheklovlariga tushmaslik uchun."""
    t = time.time()
    if t - float(ctx.sdata.get("last") or 0) < interval:
        return
    old = ctx.sdata.get("status")
    sent = ctx.send(text, kb)
    if old:
        ctx.bot.safe("deleteMessage", {"chat_id": ctx.chat_id, "message_id": old})
    ctx.goto(state, ttl=6 * 3600, status=sent["message_id"], last=t)


def parts_done_kb(movie_id: int) -> dict:
    return ikb([btn("🏁 Tugatish", "am:done", style=SUCCESS),
                btn("📢 E'lon qilish", f"an:{movie_id}", style=PRIMARY)])


def start_parts(ctx: Ctx, movie) -> None:
    data = ctx.sdata if ctx.state == "am:code" else {}
    prefill, prefill_type = data.get("file_id"), data.get("file_type") or "video"
    ctx.set_state("am:part", ttl=6 * 3600, movie_id=movie["id"], saved=[], last=0.0)
    saved_line = ""
    if prefill:
        no = ctx.db.add_part(movie["id"], prefill, prefill_type)
        ctx.goto("am:part", ttl=6 * 3600, saved=[no])
        saved_line = f"✅ <b>{no}-qism</b> saqlandi!\n\n"
    n = ctx.db.count_parts(movie["id"])
    sent = ctx.send(f"🎞 <b>{esc(movie['title'])}</b> — qism qo'shish\n\n{saved_line}"
                    f"Hozir: <b>{n}</b> qism. Keyingi qismlarni ketma-ket yuboring (bir nechtasini birdaniga "
                    f"forward qilsangiz ham bo'ladi) — har biri avtomatik <b>{n + 1}-qism</b>, "
                    f"<b>{n + 2}-qism</b>... bo'lib saqlanadi.\n\n"
                    "Tugatgach «🏁 Tugatish» tugmasini bosing.", parts_done_kb(movie["id"]))
    ctx.goto("am:part", ttl=6 * 3600, status=sent["message_id"])


@router.state("am:part", admin=True)
def st_part(ctx: Ctx) -> None:
    media = extract_media(ctx.message, audio=True)
    movie = ctx.db.get_movie(ctx.sdata.get("movie_id") or 0)
    if not movie:
        ctx.clear_state()
        ctx.send("⚠️ Kino topilmadi (o'chirilgan bo'lishi mumkin).")
        return
    if not media:
        ctx.send("❗️ Qismni <b>video</b> yoki <b>fayl</b> ko'rinishida yuboring yoki «🏁 Tugatish» ni bosing.",
                 parts_done_kb(movie["id"]))
        return
    no = ctx.db.add_part(movie["id"], media[0], media[1])
    saved = list(ctx.sdata.get("saved", [])) + [no]
    ctx.goto("am:part", ttl=6 * 3600, saved=saved)
    throttled_status(ctx, "am:part",
                     f"✅ <b>{no}-qism</b> saqlandi! ({esc(truncate(movie['title'], 40))})\n"
                     f"📦 Jami: <b>{no}</b> qism. Yana yuboring yoki «🏁 Tugatish» ni bosing.",
                     parts_done_kb(movie["id"]), 2.0)


# ═════════════════════════ ⚡️ Ommaviy qo'shish (forward) ═════════════════════════

CAPTION_CODE = re.compile(r"(?:\bkod(?:i)?\b|\bcode\b|\bкод(?:и)?\b|#)\s*[:№\-–]?\s*(\d{1,9})\b", re.I)
_CODE_WORDS = {"kino", "film", "multfilm", "serial", "anime", "kod", "kodi", "code", "raqami", "nomer", "id"}


def parse_caption(caption: str):
    """Kanal postidagi izohdan (kod, nom, ma'lumot) ni ajratib oladi."""
    text = caption or ""
    m = CAPTION_CODE.search(text)
    code = int(m.group(1)) if m else None
    title, rest = "", []
    for line in (ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        has_code = bool(CAPTION_CODE.search(line))
        clean = CAPTION_CODE.sub("", line).strip()
        if has_code and not (set(normalize(clean).split()) - _CODE_WORDS):
            continue  # «🔢 Kino kodi: 45» kabi qator
        clean = re.sub(r"^[\W_]+", "", clean)
        clean = re.sub(r"^(?:kino\s+)?(?:nomi|name|название)\s*[:\-–—]\s*", "", clean, flags=re.I).strip()
        if not title:
            if re.search(r"[^\W\d_]", clean):
                title = clean[:150]
            continue
        if "t.me/" in line or "http" in line or re.search(r"@\w{4,}", line):
            continue  # kanal reklamalari ma'lumotga kirmaydi
        rest.append(line)
    return code, title, "\n".join(rest)[:800]


def start_bulk(ctx: Ctx) -> None:
    cat = _cat(ctx)
    files = "musiqalarni (audiolarni)" if cat == "music" else f"{cat_name(cat).lower()}larni (videolarni)"
    sent = ctx.send(f"⚡️ <b>Ommaviy qo'shish</b>  •  {cat_icon(cat)} {cat_name(cat)}\n\n"
                    f"Kanal yoki guruhdan {files} birdaniga <b>forward</b> qiling — har biri "
                    "avtomatik saqlanadi:\n\n"
                    "• <b>Kod</b> izohdan olinadi (<code>Kod: 45</code>, <code>#45</code>); topilmasa — "
                    "keyingi bo'sh kod beriladi.\n"
                    "• <b>Nomi</b> — izohning birinchi qatori.\n"
                    "• Izohdagi kod band bo'lsa — o'sha kodga <b>yangi qism</b> bo'lib qo'shiladi.\n\n"
                    "Tugatgach «🏁 Tugatish» ni bosing.",
                    ikb([btn("🏁 Tugatish", "am:bulkdone", style=SUCCESS)]))
    ctx.set_state("am:bulk", ttl=6 * 3600, saved=[], status=None, intro=sent["message_id"], last=0.0, cat=cat)


@router.state("am:bulk", admin=True)
def st_bulk(ctx: Ctx) -> None:
    media = extract_media(ctx.message, audio=_is_music(ctx))
    done_kb = ikb([btn("🏁 Tugatish", "am:bulkdone", style=SUCCESS)])
    if not media:
        ctx.send("❗️ Ommaviy rejimda faqat video yoki fayl yuboring. Tugatish uchun «🏁 Tugatish».", done_kb)
        return
    db = ctx.db
    file_id, file_type, caption = media
    code, title, desc = parse_caption(caption)
    if _is_music(ctx):
        code = None  # musiqalar kodsiz
        if file_type == "audio" and not title:
            title = (caption or "").strip().split("\n")[0][:150]
    existing = db.get_movie_by_code(code) if code else None
    if existing:
        no = db.add_part(existing["id"], file_id, file_type)
        line = f"🎞 <code>{existing['code']}</code> — {esc(truncate(existing['title'], 40))} ({no}-qism)"
    else:
        code = code or db.next_code()
        cat = _cat(ctx)
        title = title or f"{cat_name(cat)} {code}"
        notify_requesters(ctx.app, db.add_movie(code, title, desc, None, False, ctx.user_id, file_id, file_type, cat))
        line = (f"{cat_icon(cat)} {esc(truncate(title, 40))}" if cat == "music" else
                f"{cat_icon(cat)} <code>{code}</code> — {esc(truncate(title, 40))}")
    saved = list(ctx.sdata.get("saved", [])) + [line]
    ctx.goto("am:bulk", ttl=6 * 3600, saved=saved)
    throttled_status(ctx, "am:bulk",
                     f"⚡️ <b>Ommaviy qo'shish</b> — saqlandi: <b>{len(saved)}</b> ta\n\n"
                     + "\n".join(saved[-5:]) + "\n\nDavom eting yoki «🏁 Tugatish» ni bosing.",
                     done_kb, 3.0)


def finish_bulk(ctx: Ctx) -> None:
    saved = ctx.sdata.get("saved", []) if ctx.state == "am:bulk" else []
    ctx.clear_state()
    ctx.answer("🏁 Tayyor!")
    if not saved:
        ctx.edit("🏁 Ommaviy qo'shish yakunlandi — hech narsa qo'shilmadi.")
        return
    shown = saved[-40:]
    more = f"\n… va yana {len(saved) - len(shown)} ta" if len(saved) > len(shown) else ""
    ctx.edit(f"🏁 <b>Ommaviy qo'shish yakunlandi!</b>\n\nJami saqlandi: <b>{len(saved)}</b> ta\n\n"
             + "\n".join(shown) + more
             + "\n\nℹ️ Nom yoki ma'lumotni «🗑️ Kino o'chirish» bo'limida kod orqali tahrirlashingiz mumkin.")


@router.callback("am", admin=True)
def cb_add_movie(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    state = ctx.state
    if action == "bulk":
        ctx.answer()
        if state == "am:code":
            start_bulk(ctx)
        else:
            ctx.set_state("am:bulkcat")
            ctx.send("⚡️ <b>Ommaviy qo'shish</b>\n\nNimalarni forward qilasiz? Turini tanlang 👇",
                     ikb(*category_rows("am:bulkcat")))
        return
    if action == "bulkcat":
        cat = parts[2] if len(parts) > 2 and parts[2] in CATEGORIES else "movie"
        ctx.answer(f"{cat_icon(cat)} {cat_name(cat)}")
        ctx.set_state("am:bulkcat", cat=cat)
        start_bulk(ctx)
        return
    if action == "bulkdone":
        finish_bulk(ctx)
        return
    if action in ("cat", "bulkcat") and len(parts) > 2 and parts[2] == "music":
        ctx.answer()
        btn_add_music(ctx)  # eski xabarlardagi «🎵 Musiqa» tugmasi — musiqa alohida bo'limda
        return
    if action == "cat":
        cat = parts[2] if len(parts) > 2 and parts[2] in CATEGORIES else "movie"
        ctx.answer(f"{cat_icon(cat)} {cat_name(cat)}")
        prefill = None
        if state == "am:cat" and ctx.sdata.get("file_id"):
            d = ctx.sdata
            prefill = (d["file_id"], d["file_type"], d.get("caption", ""))
        start_add(ctx, prefill, cat)
    elif action == "new":
        ctx.answer()
        prefill = None
        if state == "am:code" and ctx.sdata.get("file_id"):
            d = ctx.sdata
            prefill = (d["file_id"], d["file_type"], d.get("caption", ""))
        if state == "am:code" or prefill:
            start_add(ctx, prefill, _cat(ctx))
        else:
            ask_file(ctx)
    elif action == "auto":
        if state != "am:code":
            _stale(ctx)
            return
        ctx.answer()
        choose_code(ctx, ctx.db.next_code())
    elif action == "addpart" and len(parts) > 2 and parts[2].isdigit():
        movie = ctx.db.get_movie(int(parts[2]))
        if not movie:
            ctx.answer("😔 Kino topilmadi", alert=True)
            return
        ctx.answer()
        start_parts(ctx, movie)
    elif action == "usecap":
        if state != "am:desc":
            _stale(ctx)
            return
        ctx.answer()
        cap = ctx.sdata.get("caption") or ""
        cap_html = ctx.sdata.get("caption_html") or ""
        after_desc(ctx, cap[:800], cap_html if len(cap) <= 800 else "")
    elif action == "skip":
        if state == "am:desc":
            ctx.answer()
            after_desc(ctx, "")
        elif state == "am:poster":
            ctx.answer()
            show_confirm(ctx, None)
        else:
            _stale(ctx)
    elif action == "g" and len(parts) > 2 and parts[2] in genres.GENRES:
        if state != "am:genre":
            _stale(ctx)
            return
        sel = list(ctx.sdata.get("genres") or [])
        key = parts[2]
        if key in sel:
            sel.remove(key)
        elif len(sel) >= 4:
            ctx.answer("Ko'pi bilan 4 ta janr tanlash mumkin", alert=True)
            return
        else:
            sel.append(key)
        ctx.goto("am:genre", genres=sel)
        ctx.answer(genres.label(key))
        d = ctx.sdata
        ctx.edit(genre_prompt(d.get("title") or "", sel), {"inline_keyboard": genre_rows(sel, "am:g:", "am:gok")})
    elif action == "gok":
        if state != "am:genre":
            _stale(ctx)
            return
        ctx.answer()
        ctx.edit(f"🎭 Janr: <b>{genres.line(genres.dump(ctx.sdata.get('genres') or [])) or '—'}</b> ✅")
        ask_country(ctx)
    elif action == "c" and len(parts) > 2:
        if state != "am:country":
            _stale(ctx)
            return
        key = parts[2] if parts[2] in genres.COUNTRIES else ""
        ctx.goto("am:country", country=key)
        ctx.answer()
        ctx.edit(f"🌍 Davlat: <b>{genres.country_label(key) or '—'}</b> ✅")
        ask_year(ctx)
    elif action == "y" and len(parts) > 2 and parts[2].isdigit():
        if state != "am:year":
            _stale(ctx)
            return
        year = int(parts[2])
        ctx.goto("am:year", year=year)
        ctx.answer()
        ctx.edit(f"📅 Yil: <b>{year or '—'}</b> ✅")
        ask_lang(ctx)
    elif action == "l" and len(parts) > 2:
        if state != "am:lang":
            _stale(ctx)
            return
        key = parts[2] if parts[2] in genres.LANGS else ""
        ctx.goto("am:lang", lang=key)
        ctx.answer()
        ctx.edit(f"🗣 Til: <b>{genres.lang_label(key) or '—'}</b> ✅")
        ask_quality(ctx)
    elif action == "q" and len(parts) > 2 and parts[2] in genres.QUALITIES:
        if state != "am:quality":
            _stale(ctx)
            return
        sel = list(ctx.sdata.get("quality") or [])
        sel.remove(parts[2]) if parts[2] in sel else sel.append(parts[2])
        ctx.goto("am:quality", quality=sel)
        ctx.answer(genres.QUALITIES[parts[2]])
        ctx.edit(quality_prompt(sel), {"inline_keyboard": quality_rows(sel, "am:q:", "am:qok")})
    elif action == "qok":
        if state != "am:quality":
            _stale(ctx)
            return
        ctx.answer()
        ctx.edit(f"🎞 Sifat: <b>{genres.quality_text(genres.quality_dump(ctx.sdata.get('quality') or [])) or '—'}</b> ✅")
        ask_desc(ctx)
    elif action == "lskip":
        if state != "am:link":
            _stale(ctx)
            return
        ctx.answer()
        ctx.goto("am:link", group_link="")
        to_poster(ctx)
    elif action == "save":
        if state != "am:confirm":
            _stale(ctx)
            return
        save_movie(ctx, premium=len(parts) > 2 and parts[2] == "1")
    elif action == "done":
        data = ctx.sdata if state == "am:part" else {}
        movie = ctx.db.get_movie(data["movie_id"]) if data.get("movie_id") else None
        added = len(data.get("saved", []))
        ctx.clear_state()
        ctx.answer("🏁 Tayyor!")
        if movie:
            n = ctx.db.count_parts(movie["id"])
            code_txt = f"🔢 Kod: <code>{movie['code']}</code>\n" if movie["code"] > 0 else ""
            ctx.send(f"🏁 <b>Tayyor!</b>\n\n🎬 {esc(movie['title'])}\n{code_txt}"
                     f"➕ Bu safar qo'shildi: <b>{added}</b> qism\n🎞 Jami: <b>{n}</b> qism",
                     ikb([btn("📢 Kanalga e'lon qilish", f"an:{movie['id']}", style=SUCCESS)]))
        else:
            ctx.send("🏁 <b>Tayyor!</b>")


# ═════════════════════════ 📢 Kanalga e'lon ═════════════════════════

def announce_text(app, movie, parts: int) -> str:
    """Kanal posti: sarlavha → ma'lumot qatorlari → reaksiya taklifi. Syujet kanalga qo'yilmaydi (u botda va saytda);
    havolalar — pastdagi tugmalarda."""
    cat = movie["category"]
    music = cat == "music"
    head = f"{cat_icon(cat)} <b>{esc(movie['title'])}</b>"
    rows = [] if music else genres.info_lines(movie)
    if parts > 1:
        rows.append(f"📺 Qismlar: {parts} ta")
    if movie["code"] > 0:
        rows.append(f"🔢 Kodi: <code>{movie['code']}</code>")
    if movie["is_premium"]:
        rows.append("💎 Premium")
    tail = "❤️ Yoqsa, reaksiya qoldiring!"
    blocks = [head]
    if rows:
        blocks.append("\n".join(rows))
    blocks.append(tail)
    return "\n\n".join(blocks)


def announce_kb(app, movie) -> dict:
    music = movie["category"] == "music"
    verb = "tinglash" if music else "tomosha qilish"
    rows = [[btn(f"🤖 Botda {verb}", url=app.deep_link(movie["code"]), style=PRIMARY)]]
    site_url = app.site_link(movie["code"])
    if site_url:
        rows.append([btn(f"🌐 Saytda {verb}", url=site_url, style=PRIMARY)])
    return ikb(*rows)


@router.callback("an", admin=True)
def cb_announce(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    preview = len(parts) > 2 and parts[1] == "pv"  # «premium ko'rinishini menga yuborish»
    try:
        movie = ctx.db.get_movie(int(parts[2] if preview else parts[1]))
    except (IndexError, ValueError):
        return
    if not movie:
        ctx.answer("😔 Kino topilmadi", alert=True)
        return
    if preview:
        send_premium_preview(ctx, movie)
        return
    channel = app.setting("post_channel")
    if not channel:
        ctx.answer("❗️ E'lon kanali sozlanmagan. ⚙️ Matnlar → 📣 E'lon kanali", alert=True)
        return
    text = announce_text(app, movie, ctx.db.count_parts(movie["id"]))
    kb = announce_kb(app, movie)
    try:
        sent = None
        if movie["poster_id"]:
            try:
                sent = ctx.bot.send_photo(channel, movie["poster_id"], text, kb)
            except TelegramError as exc:
                if not exc.has("file", "photo", "identifier", "wrong type"):
                    raise
                log.info("Poster yuborilmadi, e'lon rasmsiz chiqadi: %s", exc)
        if sent is None:
            sent = ctx.bot.send_message(channel, text, kb)
    except TelegramError as exc:
        log.warning("E'lon yuborilmadi: %s", exc)
        ctx.answer("❌ Kanalga yuborib bo'lmadi! Bot kanalda admin va post yozish huquqiga ega ekanini "
                   "tekshiring.", alert=True)
        return
    ctx.answer("✅ Kanalga e'lon qilindi!")
    link = post_link(sent.get("chat") or {}, sent.get("message_id"))
    rows = [[btn("👁 Postni ko'rish", url=link, style=PRIMARY)]] if link else []
    note = ""
    if "tg-emoji" in premium_html(text, app.bot.emoji_map) and not _has_custom_emoji(sent):
        # Telegram kanalda botning premium emojisini oddiy emojiga aylantirdi
        note = ("\n\n⚠️ <b>Kanal postida premium emoji ko'rinmadi</b> — Telegram kanallarda botlarga buni "
                "cheklaydi. Premium ko'rinishdagi postni o'zingiz kanalga ko'chirishingiz mumkin 👇")
        rows.append([btn("💎 Premium ko'rinishini menga yuborish", f"an:pv:{movie['id']}", style=SUCCESS)])
    ctx.send("📢 <b>E'lon kanalga joylandi!</b>" + note, ikb(*rows) if rows else None)


def _has_custom_emoji(message: dict) -> bool:
    ents = (message or {}).get("caption_entities") or (message or {}).get("entities") or []
    return any(e.get("type") == "custom_emoji" for e in ents)


def send_premium_preview(ctx: Ctx, movie) -> None:
    """E'lon postini adminning o'ziga yuboradi (shaxsiy chatda premium emoji ishlaydi).
    Admin uni «Jo'natuvchi nomini yashirish» bilan kanalga uzatadi — premium emoji saqlanib qoladi."""
    app = ctx.app
    text = announce_text(app, movie, ctx.db.count_parts(movie["id"]))
    ctx.answer()
    try:
        sent = None
        if movie["poster_id"]:
            try:
                sent = ctx.bot.send_photo(ctx.chat_id, movie["poster_id"], text, announce_kb(app, movie))
            except TelegramError as exc:
                if not exc.has("file", "photo", "identifier", "wrong type"):
                    raise
        if sent is None:
            sent = ctx.bot.send_message(ctx.chat_id, text, announce_kb(app, movie))
    except TelegramError as exc:
        ctx.send(f"❌ Yuborib bo'lmadi: <i>{esc(str(exc))}</i>")
        return
    if _has_custom_emoji(sent):
        ctx.send("👆 <b>Shu postni kanalga ko'chiring:</b>\n"
                 "1. Postni bosib turing → <b>Forward</b> (Uzatish)\n"
                 "2. Kanalingizni tanlang\n"
                 "3. <b>«Hide sender name»</b> (Jo'natuvchi nomini yashirish) ni yoqing\n\n"
                 "💡 Kanaldagi eski (oddiy emojili) postni o'chirib qo'ying.")
    else:
        ctx.send("❌ Shaxsiy chatda ham premium emoji chiqmadi — bot egasi akkauntida <b>Telegram Premium</b> "
                 "yo'q yoki obuna tugagan. /almashtir → «🧪 Sinab ko'rish» orqali tekshiring.")


# ═════════════════════════ 🗑️ Kino o'chirish / tahrirlash ═════════════════════════

@router.button(B.DEL_MOVIE, admin=True)
def btn_del_movie(ctx: Ctx) -> None:
    ctx.set_state("dm:find")
    ctx.send("🗑️ <b>Kino o'chirish / tahrirlash</b>\n\n"
             "Kino <b>kodini</b> yoki <b>nomini</b> yuboring 👇", cancel_kb())


def manage_view(ctx: Ctx, movie):
    n = ctx.db.count_parts(movie["id"])
    mid = movie["id"]
    premium_txt = "Ha" if movie["is_premium"] else "Yo'q"
    poster_txt = "bor" if movie["poster_id"] else "yo'q"
    cat = movie["category"]
    text = (f"{cat_icon(cat)} <b>{esc(movie['title'])}</b>\n\n"
            f"🏷 Turi: <b>{cat_name(cat)}</b>\n"
            + (f"🔢 Kod: <code>{movie['code']}</code>\n" if movie["code"] > 0 else "") +
            f"🎞 Qismlar: <b>{n}</b>\n"
            + ("" if cat == "music" else
               f"🎭 Janr: <b>{genres.line(movie['genres']) or '—'}</b>\n"
               f"🌍 Davlat: <b>{genres.country_label(movie['country']) or '—'}</b>\n"
               f"📅 Yil: <b>{movie['year'] or '—'}</b>\n"
               f"🗣 Til: <b>{genres.lang_label(movie['lang']) or '—'}</b>\n"
               f"🎞 Sifat: <b>{genres.quality_text(movie['quality']) or '—'}</b>\n") +
            (f"🔗 Qismlar linki: {esc(movie['group_link'] or '—')}\n" if cat == "serial" else "") +
            f"👁 Ko'rishlar: <b>{fmt_num(movie['views'])}</b>\n"
            f"💎 Premium: <b>{premium_txt}</b>\n"
            f"🖼 Poster: <b>{poster_txt}</b>\n"
            f"📅 Qo'shilgan: {fmt_date(movie['created_at'])}")
    if movie["description"]:
        text += f"\n\n📝 {esc(truncate(movie['description'], 500))}"
    rows = [[btn("🗑 Butunlay o'chirish", f"dm:del:{mid}", style=DANGER)]]
    if n > 1:
        rows.append([btn("🎞 Qismni o'chirish", f"dm:parts:{mid}", style=DANGER)])
    rows.append([btn("✏️ Nomi", f"dm:et:{mid}", style=PRIMARY), btn("📝 Ma'lumoti", f"dm:ed:{mid}", style=PRIMARY),
                 btn("🖼 Poster", f"dm:ep:{mid}", style=PRIMARY)])
    if cat != "music":
        rows.append([btn("🏷 Janr • Davlat • Yil • Til • Sifat", f"dm:meta:{mid}", style=SUCCESS)])
    if cat == "serial":
        rows.append([btn("🔗 Qolgan qismlar linki", f"dm:el:{mid}", style=PRIMARY)])
    rows.append([btn(f"🏷 Turini o'zgartirish ({cat_icon(cat)} {cat_name(cat)})", f"dm:cat:{mid}",
                     style=SUCCESS)])
    if ctx.app.setting_bool("premium_enabled") or movie["is_premium"]:
        rows.append([btn("🆓 Oddiy qilish" if movie["is_premium"] else "💎 Premium qilish",
                         f"dm:prem:{mid}", style=PRIMARY)])
    n_shorts = ctx.db.count_shorts(mid)
    rows.append([btn(f"🎞 Shorts ({n_shorts})" if n_shorts else "🎞 Shorts qo'shish", f"dm:sh:{mid}", style=SUCCESS)])
    rows.append([btn("➕ Qism qo'shish", f"am:addpart:{mid}", style=SUCCESS),
                 btn("📢 E'lon qilish", f"an:{mid}", style=PRIMARY)])
    rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return text, ikb(*rows)


def meta_menu(ctx: Ctx, movie) -> None:
    mid = movie["id"]
    text = (f"🏷 <b>{esc(movie['title'])}</b> — ma'lumotlari\n\n"
            f"🎭 Janr: <b>{genres.line(movie['genres']) or '—'}</b>\n"
            f"🌍 Davlat: <b>{genres.country_label(movie['country']) or '—'}</b>\n"
            f"📅 Yil: <b>{movie['year'] or '—'}</b>\n"
            f"🗣 Til: <b>{genres.lang_label(movie['lang']) or '—'}</b>\n"
            f"🎞 Sifat: <b>{genres.quality_text(movie['quality']) or '—'}</b>\n\n"
            "👇 Nimani o'zgartiramiz?")
    ctx.edit(text, ikb([btn("🎭 Janr", f"dm:gen:{mid}", style=PRIMARY), btn("🌍 Davlat", f"dm:ctr:{mid}", style=PRIMARY)],
                       [btn("📅 Yil", f"dm:yr:{mid}", style=PRIMARY), btn("🗣 Til", f"dm:lg:{mid}", style=PRIMARY)],
                       [btn("🎞 Sifat", f"dm:ql:{mid}", style=PRIMARY)],
                       [btn("⬅️ Orqaga", f"dm:open:{mid}", style=DANGER)]))


def send_manage(ctx: Ctx, movie, edit: bool = False) -> None:
    text, kb = manage_view(ctx, movie)
    if edit:
        ctx.edit(text, kb)
    else:
        ctx.send(text, kb)


@router.state("dm:find", admin=True)
def st_find(ctx: Ctx) -> None:
    query = ctx.text.strip()
    if not query:
        ctx.send("❗️ Kino kodini yoki nomini matn ko'rinishida yuboring.", cancel_kb())
        return
    m = CODE_RE.fullmatch(query)
    if m:
        movie = ctx.db.get_movie_by_code(int(m.group(1)))
        if not movie:
            ctx.send(f"❌ <b>{esc(query)}</b> kodli kino topilmadi. Boshqa kod yoki nom yuboring.", cancel_kb())
            return
        ctx.clear_state()
        send_manage(ctx, movie)
        return
    ids, _ = search_ids(ctx.app, normalize(query))
    if not ids:
        ctx.send("❌ Hech narsa topilmadi. Boshqa nom yoki kod yuboring.", cancel_kb())
        return
    ctx.clear_state()
    rows = ctx.db.movie_rows(ids[:20])
    header = f"🔎 <b>«{esc(truncate(query, 40))}»</b> bo'yicha natijalar:"
    if len(ids) > 20:
        header += "\n<i>(birinchi 20 tasi ko'rsatildi)</i>"
    text, kb = build_list(header, rows, 0, 0, 1, None, fmt_item, item_cb="dm:open",
                          hint="👇 Boshqariladigan kino raqamini tanlang:")
    ctx.send(text, kb)


def _movie_from(ctx: Ctx, value: str):
    movie = ctx.db.get_movie(int(value)) if value.isdigit() else None
    if not movie:
        ctx.answer("😔 Kino topilmadi (o'chirilgan bo'lishi mumkin).", alert=True)
    return movie


@router.callback("dm", admin=True)
def cb_manage(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    if len(parts) < 3:
        return
    action, value = parts[1], parts[2]
    db = ctx.db

    if action in ("pdel", "pdelok"):
        part = db.get_part(int(value)) if value.isdigit() else None
        movie = db.get_movie(part["movie_id"]) if part else None
        if not part or not movie:
            ctx.answer("😔 Qism topilmadi", alert=True)
            return
        if action == "pdel":
            ctx.answer()
            ctx.edit(f"⚠️ <b>{esc(movie['title'])}</b> — <b>{esc(part_label(part))}</b> o'chirilsinmi?\n\n"
                     "Qolgan qismlar avtomatik qayta raqamlanadi.",
                     ikb([btn("✅ Ha, o'chirilsin", f"dm:pdelok:{part['id']}", style=DANGER)],
                         [btn("⬅️ Orqaga", f"dm:parts:{movie['id']}", style=PRIMARY)]))
            return
        if db.count_parts(movie["id"]) <= 1:  # oxirgi qism — kino ham o'chadi
            _drop_short_files(ctx, db.delete_shorts(movie["id"]))
        left = db.delete_part(part["id"])
        ctx.answer("🗑 Qism o'chirildi")
        movie = db.get_movie(movie["id"])
        if movie:
            send_manage(ctx, movie, edit=True)
        else:
            ctx.edit("🗑 Oxirgi qism o'chirildi — kino bazadan olib tashlandi.")
        log.info("Qism o'chirildi (qoldi: %s)", left)
        return

    movie = _movie_from(ctx, value)
    if not movie:
        return
    mid = movie["id"]
    if action == "open":
        if ctx.state == "dm:short":
            added = int(ctx.sdata.get("added") or 0)
            ctx.clear_state()
            ctx.answer(f"🏁 Tayyor! {added} ta shorts qo'shildi" if added else "🏁 Tayyor")
        else:
            ctx.answer()
        send_manage(ctx, movie, edit=True)
    elif action == "del":
        ctx.answer()
        n = db.count_parts(mid)
        ctx.edit(f"⚠️ <b>{esc(movie['title'])}</b> ({n} qism) butunlay o'chirilsinmi?\n\n"
                 "❗️ Bu amalni ortga qaytarib bo'lmaydi!",
                 ikb([btn("✅ Ha, o'chirilsin", f"dm:delok:{mid}", style=DANGER)],
                     [btn("⬅️ Yo'q, orqaga", f"dm:open:{mid}", style=PRIMARY)]))
    elif action == "delok":
        _drop_short_files(ctx, db.delete_shorts(mid))
        db.delete_movie(mid)
        ctx.answer("🗑 O'chirildi")
        ctx.edit(f"🗑 <b>{esc(movie['title'])}</b> o'chirildi.")
    elif action == "parts":
        ctx.answer()
        plist = db.get_parts(mid)
        lines = [f"🎞 <b>{esc(movie['title'])}</b> — qaysi qismni o'chiramiz?", ""]
        for p in plist[:50]:
            lines.append(f"<b>{p['part_no']}.</b> {esc(part_label(p))}")
        rows = number_rows([(p["part_no"], f"dm:pdel:{p['id']}") for p in plist[:50]], style=DANGER)
        rows.append([btn("⬅️ Orqaga", f"dm:open:{mid}", style=DANGER)])
        ctx.edit("\n".join(lines), {"inline_keyboard": rows})
    elif action == "sh":
        ctx.answer()
        n = db.count_shorts(mid)
        rows = [[btn("➕ Shorts qo'shish", f"dm:shadd:{mid}", style=SUCCESS)]]
        if n:
            rows.append([btn(f"🗑 Shortslarni o'chirish ({n})", f"dm:shdel:{mid}", style=DANGER)])
        rows.append([btn("⬅️ Orqaga", f"dm:open:{mid}", style=PRIMARY)])
        ctx.edit(f"🎞 <b>Shorts</b> — {esc(movie['title'])}\n\n"
                 f"Hozir: <b>{n}</b> ta.\n\n"
                 "Shorts saytdagi «Shorts» bo'limida chiqadi: foydalanuvchi qisqa videoni (treyler) yoki "
                 "rasmni ko'radi va «▶ To'liq ko'rish» bosib kinoni oladi.", ikb(*rows))
    elif action == "shadd":
        ctx.answer()
        ctx.set_state("dm:short", ttl=6 * 3600, movie_id=mid, added=0)
        ctx.send(f"🎞 <b>{esc(movie['title'])}</b> — shorts qo'shish\n\n"
                 "Qisqa <b>video</b> (treyler, parcha) yoki <b>rasm</b> (poster, kadr) yuboring.\n"
                 "Bir nechtasini ketma-ket yuborsangiz ham bo'ladi.\n\n"
                 "⚠️ Video <b>20 MB</b> dan kichik bo'lsin (1 daqiqagacha bo'lgani yaxshi) — "
                 "kattasini Telegram saytga bera olmaydi.", shorts_done_kb(mid))
    elif action == "shdel":
        ids = db.delete_shorts(mid)
        _drop_short_files(ctx, ids)
        ctx.answer(f"🗑 {len(ids)} ta shorts o'chirildi")
        send_manage(ctx, db.get_movie(mid), edit=True)
    elif action == "cat":
        ctx.answer()
        cur = movie["category"]
        cats = [btn(("✅ " if c == cur else "") + f"{cat_icon(c)} {cat_name(c)}", f"dm:to{c}:{mid}",
                    style=SUCCESS if c == cur else PRIMARY) for c in CATEGORIES]
        rows = [cats[:2], cats[2:], [btn("⬅️ Orqaga", f"dm:open:{mid}", style=DANGER)]]
        warn = ("\n\n⚠️ Musiqaga o'tkazilsa, <b>kodi olib tashlanadi</b> (musiqalar kodsiz)."
                if cur != "music" and movie["code"] > 0 else "")
        ctx.edit(f"🏷 <b>{esc(movie['title'])}</b> — turini tanlang:{warn}", ikb(*rows))
    elif action.startswith("to") and action[2:] in CATEGORIES:
        new = action[2:]
        fields = {"category": new}
        if new == "music" and movie["code"] > 0:
            fields["code"] = db.next_music_code()
        elif new != "music" and movie["code"] < 0:
            fields["code"] = db.next_code()
        if new != movie["category"]:
            db.update_movie(mid, **fields)
        ctx.answer(f"🏷 Turi: {cat_icon(new)} {cat_name(new)}")
        send_manage(ctx, db.get_movie(mid), edit=True)
    elif action == "ql" or (action[:2] == "qt" and action[2:] in genres.QUALITIES):
        sel = genres.quality_parse(movie["quality"])
        if action != "ql":
            key = action[2:]
            sel.remove(key) if key in sel else sel.append(key)
            db.update_movie(mid, quality=genres.quality_dump(sel))
            ctx.answer(genres.QUALITIES[key])
        else:
            ctx.answer()
        rows = quality_rows(sel, "dm:qt", f"dm:meta:{mid}", "✅ Tayyor")
        for b in rows[0]:
            b["callback_data"] += f":{mid}"
        ctx.edit(f"🎞 <b>{esc(movie['title'])}</b> — video sifatini belgilang:\n\n"
                 f"Tanlangan: <b>{genres.quality_text(genres.quality_dump(sel)) or '—'}</b>", {"inline_keyboard": rows})
    elif action == "meta":
        ctx.answer()
        meta_menu(ctx, movie)
    elif action in ("ctr", "yr", "lg"):
        ctx.answer()
        back = [[btn("⬅️ Orqaga", f"dm:meta:{mid}", style=DANGER)]]
        if action == "ctr":
            rows = country_rows(movie["country"], "dm:cs", [[btn("🚫 Olib tashlash", "dm:cs-", style=DANGER)]] + back)
            title = "🌍 <b>Davlatini</b> tanlang:"
        elif action == "yr":
            rows = year_rows(movie["year"], "dm:ys", [[btn("✍️ Boshqa yil yozish", f"dm:ey:{mid}", style=PRIMARY),
                                                      btn("🚫 Olib tashlash", "dm:ys0", style=DANGER)]] + back)
            title = "📅 <b>Chiqqan yilini</b> tanlang:"
        else:
            rows = lang_rows(movie["lang"], "dm:ls", [[btn("🚫 Olib tashlash", "dm:ls-", style=DANGER)]] + back)
            title = "🗣 <b>Tilini</b> tanlang:"
        for r in rows:
            for b in r:
                if b.get("callback_data", "")[:5] in ("dm:cs", "dm:ys", "dm:ls"):
                    b["callback_data"] += f":{mid}"
        ctx.edit(f"🎬 <b>{esc(movie['title'])}</b>\n\n{title}", {"inline_keyboard": rows})
    elif (action[:2] == "cs" and (action[2:] in genres.COUNTRIES or action[2:] == "-")) \
            or (action[:2] == "ys" and action[2:].isdigit()) \
            or (action[:2] == "ls" and (action[2:] in genres.LANGS or action[2:] == "-")):
        val = action[2:]
        field = {"cs": "country", "ys": "year", "ls": "lang"}[action[:2]]
        db.update_movie(mid, **{field: int(val) if field == "year" else ("" if val == "-" else val)})
        ctx.answer("✅ Saqlandi")
        meta_menu(ctx, db.get_movie(mid))
    elif action == "gen" or (action.startswith("gx") and action[2:] in genres.GENRES):
        sel = genres.parse(movie["genres"])
        if action != "gen":
            key = action[2:]
            if key in sel:
                sel.remove(key)
            elif len(sel) >= 4:
                ctx.answer("Ko'pi bilan 4 ta janr tanlash mumkin", alert=True)
                return
            else:
                sel.append(key)
            db.update_movie(mid, genres=genres.dump(sel))
            ctx.answer(genres.label(key))
        else:
            ctx.answer()
        rows = genre_rows(sel, "dm:gx", f"dm:meta:{mid}", "✅ Tayyor")
        for r in rows:
            for b in r:
                if b["callback_data"].startswith("dm:gx"):
                    b["callback_data"] += f":{mid}"
        chosen = " • ".join(genres.label(k) for k in genres.GENRES if k in sel) or "—"
        ctx.edit(f"🎭 <b>{esc(movie['title'])}</b> — janrlarini belgilang (4 tagacha):\n\nTanlangan: {chosen}",
                 {"inline_keyboard": rows})
    elif action == "ey":
        ctx.answer()
        ctx.set_state("dm:year", movie_id=mid)
        ctx.send(f"📅 <b>{esc(movie['title'])}</b>\n\nChiqqan <b>yilini</b> yuboring (masalan <code>2024</code>).\n"
                 "Olib tashlash uchun <code>-</code> yuboring.", cancel_kb())
    elif action == "prem":
        db.update_movie(mid, is_premium=not movie["is_premium"])
        ctx.answer("💎 Premium qilindi" if not movie["is_premium"] else "🆓 Oddiy qilindi")
        send_manage(ctx, db.get_movie(mid), edit=True)
    elif action == "el":
        ctx.answer()
        ctx.set_state("dm:link", movie_id=mid)
        cur = movie["group_link"] or "—"
        ctx.send(f"📺 <b>{esc(movie['title'])}</b>\n\nHozirgi link: {esc(cur)}\n\n"
                 "Yangi <b>linkni</b> yuboring (olib tashlash uchun <code>-</code>):", cancel_kb(), preview=False)
    elif action in ("et", "ed", "ep"):
        ctx.answer()
        state = {"et": "dm:title", "ed": "dm:desc", "ep": "dm:poster"}[action]
        prompt = {
            "et": "✏️ Yangi <b>nomni</b> yuboring:",
            "ed": "📝 Yangi <b>ma'lumotni</b> yuboring.\nO'chirib tashlash uchun <code>-</code> yuboring.",
            "ep": "🖼 Yangi <b>poster</b> (rasm) yuboring.\nPosterni olib tashlash uchun <code>-</code> yuboring.",
        }[action]
        ctx.set_state(state, movie_id=mid)
        ctx.send(f"🎬 <b>{esc(movie['title'])}</b>\n\n{prompt}", cancel_kb())


SHORT_LIMIT = 20 * 1024 * 1024  # Telegram bot API shundan katta faylni yuklab berolmaydi


def shorts_done_kb(movie_id: int) -> dict:
    return ikb([btn("🏁 Tugatish", f"dm:open:{movie_id}", style=SUCCESS)])


def _drop_short_files(ctx: Ctx, ids) -> None:
    folder = ctx.db.path.parent / "shorts"
    for sid in ids:
        for f in folder.glob(f"{int(sid)}.*"):
            try:
                f.unlink()
            except OSError:
                pass


def extract_short(msg: dict):
    """Xabardan shorts uchun media: (file_id, 'video'|'photo', hajmi)."""
    if msg.get("photo"):
        p = msg["photo"][-1]
        return p["file_id"], "photo", p.get("file_size") or 0
    for key in ("video", "animation"):
        if msg.get(key):
            v = msg[key]
            return v["file_id"], "video", v.get("file_size") or 0
    doc = msg.get("document") or {}
    mime = doc.get("mime_type") or ""
    if mime.startswith("video/"):
        return doc["file_id"], "video", doc.get("file_size") or 0
    if mime.startswith("image/"):
        return doc["file_id"], "photo", doc.get("file_size") or 0
    return None


@router.state("dm:short", admin=True)
def st_short(ctx: Ctx) -> None:
    movie = ctx.db.get_movie(ctx.sdata.get("movie_id") or 0)
    if not movie:
        ctx.clear_state()
        ctx.send("😔 Kino topilmadi (o'chirilgan bo'lishi mumkin).")
        return
    media = extract_short(ctx.message)
    if not media:
        ctx.send("❗️ Qisqa <b>video</b> yoki <b>rasm</b> yuboring. Tugatish uchun «🏁 Tugatish».",
                 shorts_done_kb(movie["id"]))
        return
    file_id, kind, size = media
    if size > SHORT_LIMIT:
        ctx.send(f"❌ Video juda katta ({size // (1024 * 1024)} MB). <b>20 MB</b> dan kichik video yuboring — "
                 "masalan, kinodan 30–60 soniyalik parcha.", shorts_done_kb(movie["id"]))
        return
    ctx.db.add_short(movie["id"], file_id, kind)
    added = int(ctx.sdata.get("added") or 0) + 1
    ctx.goto("dm:short", ttl=6 * 3600, added=added)
    what = "🎬 Video" if kind == "video" else "🖼 Rasm"
    ctx.send(f"✅ {what} shortsga qo'shildi! ({esc(truncate(movie['title'], 40))})\n"
             f"Bu safar: <b>{added}</b> ta, jami: <b>{ctx.db.count_shorts(movie['id'])}</b> ta.\n\n"
             "Yana yuboring yoki «🏁 Tugatish» ni bosing.", shorts_done_kb(movie["id"]))


def _edit_target(ctx: Ctx):
    movie = ctx.db.get_movie(ctx.sdata.get("movie_id") or 0)
    if not movie:
        ctx.clear_state()
        # tahrirlanayotgan kino o'chirilgan — yuborilgan fayl yo'qolmasin, yangi qo'shishga o'tadi
        if not admin_media_shortcut(ctx):
            ctx.send("😔 Kino topilmadi (o'chirilgan bo'lishi mumkin).")
    return movie


@router.state("dm:title", admin=True)
def st_edit_title(ctx: Ctx) -> None:
    movie = _edit_target(ctx)
    if not movie:
        return
    title = ctx.text.strip()
    if not title or len(title) > 150:
        ctx.send("❗️ Nom 1–150 belgidan iborat matn bo'lishi kerak.", cancel_kb())
        return
    ctx.db.update_movie(movie["id"], title=title)
    ctx.clear_state()
    notified = notify_requesters(ctx.app, movie["id"])
    ctx.send("✅ Nom yangilandi!" + (f"\n📨 So'ragan {notified} kishiga xabar yuborildi." if notified else ""))
    send_manage(ctx, ctx.db.get_movie(movie["id"]))


@router.state("dm:desc", admin=True)
def st_edit_desc(ctx: Ctx) -> None:
    movie = _edit_target(ctx)
    if not movie:
        return
    desc = ctx.text.strip()
    if not desc or len(desc) > 800:
        ctx.send("❗️ Ma'lumot 1–800 belgidan iborat matn bo'lishi kerak (o'chirish uchun <code>-</code>).",
                 cancel_kb())
        return
    if desc == "-":
        ctx.db.update_movie(movie["id"], description="", desc_html="")
    else:
        extra = {}
        if movie["category"] != "music" and not movie["genres"]:
            extra["genres"] = genres.dump(genres.detect(movie["title"], desc))
        if not movie["year"]:
            extra["year"] = genres.detect_year(movie["title"], desc)
        ctx.db.update_movie(movie["id"], description=desc, desc_html=message_html(ctx.message).strip(), **extra)
    ctx.clear_state()
    ctx.send("✅ Ma'lumot yangilandi!")
    send_manage(ctx, ctx.db.get_movie(movie["id"]))


@router.state("dm:link", admin=True)
def st_edit_link(ctx: Ctx) -> None:
    movie = _edit_target(ctx)
    if not movie:
        return
    text = ctx.text.strip()
    link = "" if text == "-" else clean_link(text)
    if text != "-" and (not link or len(link) > 300):
        ctx.send("❗️ Havolani yuboring (masalan <code>https://t.me/guruh/123</code>) yoki <code>-</code>.", cancel_kb())
        return
    ctx.db.update_movie(movie["id"], group_link=link)
    ctx.clear_state()
    ctx.send("✅ Link yangilandi!" if link else "🗑 Link olib tashlandi.")
    send_manage(ctx, ctx.db.get_movie(movie["id"]))


@router.state("dm:year", admin=True)
def st_edit_year(ctx: Ctx) -> None:
    movie = _edit_target(ctx)
    if not movie:
        return
    text = ctx.text.strip()
    if text == "-":
        year = 0
    elif re.fullmatch(r"(19[2-9]\d|20[0-4]\d)", text):
        year = int(text)
    else:
        ctx.send("❗️ Yilni 4 xonali son bilan yuboring (masalan <code>2024</code>) yoki <code>-</code>.", cancel_kb())
        return
    ctx.db.update_movie(movie["id"], year=year)
    ctx.clear_state()
    ctx.send("✅ Yil yangilandi!")
    send_manage(ctx, ctx.db.get_movie(movie["id"]))


@router.state("dm:poster", admin=True)
def st_edit_poster(ctx: Ctx) -> None:
    movie = _edit_target(ctx)
    if not movie:
        return
    if has_image(ctx.message):
        poster = poster_from(ctx)
        if not poster:
            poster_error(ctx, " Yoki posterni olib tashlash uchun <code>-</code> yuboring.")
            return
        ctx.db.update_movie(movie["id"], poster_id=poster)
    elif ctx.text.strip() == "-":
        ctx.db.update_movie(movie["id"], poster_id=None)
    else:
        ctx.send("❗️ Rasm yuboring yoki posterni olib tashlash uchun <code>-</code> yuboring.", cancel_kb())
        return
    ctx.clear_state()
    ctx.send("✅ Poster yangilandi!")
    send_manage(ctx, ctx.db.get_movie(movie["id"]))


# ═════════════════════════ 🎵 Musiqa qo'shish (birdaniga ko'p fayl) ═════════════════════════

_JUNK = re.compile(r"[\[(][^\])]*(?:\.[a-z]{2,4}|www|http|t\.me|@)[^\])]*[\])]", re.I)
_TRACK_NO = re.compile(r"^\s*(?:0\d|\d{1,3}\s*[.)\-–])\s*")  # «01 », «3.», «12)» — «50 Cent» emas
_AUDIO_EXT = (".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac", ".wma", ".amr")


def clean_file_name(name: str) -> str:
    """«01_Shahzoda_-_Yoningdaman_(uzhits.net).mp3» → «Shahzoda - Yoningdaman»."""
    base = re.sub(r"\.[A-Za-z0-9]{2,5}$", "", name or "")
    base = _JUNK.sub(" ", base)
    base = re.sub(r"(?:https?://|www\.)\S+|\b\S+\.(?:uz|ru|com|net|org|me)\b|@\w+", " ", base, flags=re.I)
    base = base.replace("_", " ")
    base = _TRACK_NO.sub("", base)
    base = re.sub(r"\s*[-–—]\s*", " - ", base)
    return re.sub(r"\s{2,}", " ", base).strip(" -.")


def music_from_message(msg: dict):
    """Xabardan musiqa: (file_id, file_type, nomi, ma'lumot, muqova_id) yoki None."""
    a = msg.get("audio")
    doc = msg.get("document") or {}
    if a:
        performer, title = (a.get("performer") or "").strip(), (a.get("title") or "").strip()
        if performer and title:
            name = f"{performer} - {title}"
        else:
            name = title or performer or clean_file_name(a.get("file_name") or "")
        thumb = (a.get("thumbnail") or a.get("thumb") or {}).get("file_id")
        desc = f"Ijrochi: {performer}" if performer else ""
        return a["file_id"], "audio", name, desc, thumb
    if doc and ((doc.get("mime_type") or "").startswith("audio/")
                or (doc.get("file_name") or "").lower().endswith(_AUDIO_EXT)):
        return doc["file_id"], "document", clean_file_name(doc.get("file_name") or ""), "", None
    if msg.get("voice"):
        return msg["voice"]["file_id"], "audio", "", "", None
    return None


def music_done_kb() -> dict:
    return ikb([btn("🏁 Tugatish", "mu:done", style=SUCCESS)])


def begin_music(ctx: Ctx) -> None:
    """Audio kelganda musiqa rejimini yoqib, shu faylni ham saqlaydi (keyingilari ham qabul qilinadi)."""
    ctx.set_state("mu:bulk", ttl=6 * 3600, saved=[], skipped=[], status=None, last=0.0)
    st_music_bulk(ctx)


@router.button(B.ADD_MUSIC, admin=True)
def btn_add_music(ctx: Ctx) -> None:
    sent = ctx.send("🎵 <b>Musiqa qo'shish</b>\n\n"
                    "Musiqalarni yuboring — <b>bir nechtasini birdaniga</b> (10, 20, 50 ta...) tashlashingiz yoki "
                    "kanaldan forward qilishingiz mumkin. Har biri avtomatik saqlanadi:\n\n"
                    "• <b>Nomi</b> — fayldagi ijrochi va qo'shiq nomi (bo'lmasa — fayl nomi)\n"
                    "• <b>Kod</b> berilmaydi — musiqalar nomi bo'yicha topiladi\n"
                    "• <b>Muqova</b> — qo'shiq ichida rasm bo'lsa, saytda chiqadi\n"
                    "• Bazada bor qo'shiq qayta qo'shilmaydi\n\n"
                    "Tugatgach «🏁 Tugatish» ni bosing.", music_done_kb())
    ctx.set_state("mu:bulk", ttl=6 * 3600, saved=[], skipped=[], status=None, intro=sent["message_id"], last=0.0)


@router.state("mu:bulk", admin=True)
def st_music_bulk(ctx: Ctx) -> None:
    db = ctx.db
    found = music_from_message(ctx.message)
    if not found and ctx.text:
        return NEXT  # matn yozilsa — musiqa rejimi tugaydi, matn odatdagidek ishlanadi (qidiruv va h.k.)
    if not found:
        ctx.send("❗️ Musiqa <b>fayl</b> ko'rinishida yuboring (audio yoki mp3 fayl). "
                 "Tugatish uchun «🏁 Tugatish».", music_done_kb())
        return
    file_id, file_type, name, desc, thumb = found
    if not name:
        name = (ctx.message.get("caption") or "").strip().split("\n")[0][:150]
    name = (name or f"Nomsiz musiqa {db.count_by_category()['music'] + 1}")[:150]
    saved = list(ctx.sdata.get("saved", []))
    skipped = list(ctx.sdata.get("skipped", []))
    dup = db.find_title(normalize(name), "music")
    if dup:
        skipped.append(f"♻️ {esc(truncate(name, 45))} — bazada bor")
    else:
        notify_requesters(ctx.app, db.add_movie(0, name, desc, thumb, False, ctx.user_id, file_id, file_type, "music"))
        saved.append(f"🎵 {esc(truncate(name, 45))}")
    ctx.goto("mu:bulk", ttl=6 * 3600, saved=saved, skipped=skipped)
    lines = (saved + skipped)[-6:]
    extra = f"  •  ♻️ takror: <b>{len(skipped)}</b>" if skipped else ""
    throttled_status(ctx, "mu:bulk",
                     f"🎵 <b>Musiqa qo'shish</b> — saqlandi: <b>{len(saved)}</b> ta{extra}\n\n"
                     + "\n".join(lines) + "\n\nDavom eting yoki «🏁 Tugatish» ni bosing.",
                     music_done_kb(), 2.5)


@router.callback("mu", admin=True)
def cb_music(ctx: Ctx) -> None:
    if ctx.data != "mu:done":
        return
    data = ctx.sdata if ctx.state == "mu:bulk" else {}
    saved, skipped = data.get("saved", []), data.get("skipped", [])
    ctx.clear_state()
    ctx.answer("🏁 Tayyor!")
    if not saved and not skipped:
        ctx.send("🏁 Musiqa qo'shish yakunlandi — hech narsa qo'shilmadi.")
        return
    shown = saved[-40:]
    more = f"\n… va yana {len(saved) - len(shown)} ta" if len(saved) > len(shown) else ""
    text = (f"🏁 <b>Musiqa qo'shish yakunlandi!</b>\n\n✅ Saqlandi: <b>{len(saved)}</b> ta\n"
            + (f"♻️ Bazada bor edi: <b>{len(skipped)}</b> ta\n" if skipped else "")
            + ("\n" + "\n".join(shown) + more if shown else "")
            + "\n\nℹ️ Nomini o'zgartirish: «🗑️ Kino o'chirish» → qo'shiq nomini yozing → «✏️ Nomi».")
    ctx.send(text[:4000])
