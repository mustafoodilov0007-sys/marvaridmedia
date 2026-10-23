"""Admin: 🎬 Kino qo'shish (seriallar bilan), 🗑️ o'chirish/tahrirlash va 📢 kanalga e'lon."""

from __future__ import annotations

import logging
import re
import time

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb, number_rows
from ..telegram import TelegramError
from ..texts import B, CATEGORIES, cat_icon, cat_name
from ..utils import esc, extract_media, fmt_date, fmt_num, normalize, post_link, truncate, visible_len
from .user import build_list, fmt_item, part_label, search_ids

log = logging.getLogger("admin.movies")

CODE_RE = re.compile(r"#?(\d{1,9})")


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
    ctx.send("➕ <b>Yangi qo'shish</b>\n\n"
             "📤 Faylni yuboring: <b>video</b>, <b>audio</b> yoki <b>fayl</b>.\n"
             "Kanaldan forward qilsangiz ham bo'ladi.\n\n"
             "So'ng bot turini so'raydi: 🎬 Kino, 🧸 Multfilm yoki 🎵 Musiqa.",
             ikb([btn("⚡️ Ommaviy qo'shish (forward)", "am:bulk", style=PRIMARY)],
                 [btn("❌ Bekor qilish", "cancel", style=DANGER)]))


@router.state("am:file", admin=True)
def st_file(ctx: Ctx) -> None:
    media = extract_media(ctx.message, audio=True)
    if not media:
        ctx.send("❗️ Iltimos, <b>video</b>, <b>audio</b> yoki <b>fayl</b> yuboring.", cancel_kb())
        return
    ask_category(ctx, prefill=media)


def category_rows(prefix: str) -> list:
    return [[btn("🎬 Kino", f"{prefix}:movie", style=SUCCESS), btn("🧸 Multfilm", f"{prefix}:cartoon", style=PRIMARY),
             btn("🎵 Musiqa", f"{prefix}:music", style=DANGER)],
            [btn("❌ Bekor qilish", "cancel", style=DANGER)]]


def ask_category(ctx: Ctx, prefill=None) -> None:
    """Fayl qabul qilingach — turini tanlash: kino, multfilm yoki musiqa."""
    data = {}
    if prefill:
        data = {"file_id": prefill[0], "file_type": prefill[1], "caption": prefill[2]}
    ctx.set_state("am:cat", **data)
    if prefill and prefill[1] == "audio":
        head = "🎵 <b>Audio qabul qilindi!</b>"
    elif prefill:
        head = "📹 <b>Fayl qabul qilindi!</b>"
    else:
        head = "➕ <b>Yangi qo'shish</b>"
    ctx.send(f"{head}\n\nBu nima? Turini tanlang 👇", ikb(*category_rows("am:cat")))


def start_add(ctx: Ctx, prefill=None, category: str = "movie") -> None:
    code = ctx.db.next_code()
    data = {"cat": category if category in CATEGORIES else "movie"}
    if prefill:
        data.update({"file_id": prefill[0], "file_type": prefill[1], "caption": prefill[2]})
    ctx.set_state("am:code", **data)
    icon, name = cat_icon(data["cat"]), cat_name(data["cat"])
    noun = name.lower()
    if prefill:
        head = "🎵 <b>Audio qabul qilindi!</b>" if prefill[1] == "audio" else "📹 <b>Video qabul qilindi!</b>"
        head += f"  •  {icon} {name}"
    else:
        head = f"{icon} <b>Yangi {noun} qo'shish</b>"
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
    """Admin hech qanday bo'limsiz video/audio yuborsa — darhol qo'shishni taklif qilamiz."""
    media = extract_media(ctx.message, audio=True)
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
    else:
        example = "Avatar: Suv yo'li (2022)"
    ctx.send(f"✅ Kod: <b>{code}</b>, fayl tayyor.\n\n"
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
    ctx.goto("am:title", file_id=media[0], file_type=media[1], caption=media[2])
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
    ctx.goto("am:desc", title=title)
    rows = []
    if ctx.sdata.get("caption"):
        rows.append([btn("📄 Fayl izohidan olish", "am:usecap", style=PRIMARY)])
    rows.append([btn("⏭ O'tkazib yuborish", "am:skip", style=SUCCESS)])
    rows.append([btn("❌ Bekor qilish", "cancel", style=DANGER)])
    hint = "ijrochi, albom, yil, janr" if _is_music(ctx) else "janr, yil, davlat, til, sifat"
    ctx.send(f"4️⃣ {cat_name(_cat(ctx))} haqida <b>qisqacha ma'lumot</b> yuboring:\n"
             f"💡 Masalan: {hint}.\n\nYoki bu bosqichni o'tkazib yuboring 👇", ikb(*rows))


@router.state("am:desc", admin=True)
def st_desc(ctx: Ctx) -> None:
    desc = ctx.text.strip()
    if not desc:
        ctx.send("❗️ Ma'lumotni matn ko'rinishida yuboring yoki «⏭ O'tkazib yuborish» ni bosing.")
        return
    if len(desc) > 800:
        ctx.send("❗️ Ma'lumot juda uzun — 800 belgigacha qisqartiring.")
        return
    ask_poster(ctx, desc)


def ask_poster(ctx: Ctx, desc: str) -> None:
    ctx.goto("am:poster", desc=desc)
    what = "muqovasini" if _is_music(ctx) else "posterini"
    ctx.send(f"5️⃣ {cat_name(_cat(ctx))} <b>{what}</b> (rasm) yuboring 🖼\n"
             "Rasm saytda, kanal e'lonida va qismlar ro'yxatida chiroyli ko'rinadi.\n\nYoki o'tkazib yuboring 👇",
             ikb([btn("⏭ O'tkazib yuborish", "am:skip", style=SUCCESS)], [btn("❌ Bekor qilish", "cancel", style=DANGER)]))


@router.state("am:poster", admin=True)
def st_poster(ctx: Ctx) -> None:
    photos = ctx.message.get("photo")
    if not photos:
        ctx.send("❗️ Poster uchun <b>rasm</b> yuboring yoki «⏭ O'tkazib yuborish» ni bosing.")
        return
    show_confirm(ctx, photos[-1]["file_id"])


def show_confirm(ctx: Ctx, poster) -> None:
    ctx.goto("am:confirm", poster=poster)
    d = ctx.sdata
    file_txt = {"video": "video", "audio": "audio"}.get(d["file_type"], "hujjat (fayl)")
    poster_txt = "bor ✅" if poster else "yo'q"
    cat = _cat(ctx)
    text = ("✅ <b>Hammasi tayyor! Tekshirib chiqing:</b>\n\n"
            f"🏷 Turi: <b>{cat_icon(cat)} {cat_name(cat)}</b>\n"
            f"🔢 Kod: <code>{d['code']}</code>\n"
            f"{cat_icon(cat)} Nomi: <b>{esc(d['title'])}</b>\n"
            f"📝 Ma'lumot: {esc(truncate(d.get('desc') or '—', 300))}\n"
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
    if db.get_movie_by_code(d["code"]):
        ctx.answer("⚠️ Bu kod band bo'lib qoldi! Boshqa kod tanlang.", alert=True)
        start_add(ctx, prefill=(d["file_id"], d["file_type"], d.get("caption", "")), category=_cat(ctx))
        return
    cat = _cat(ctx)
    movie_id = db.add_movie(d["code"], d["title"], d.get("desc") or "", d.get("poster"), premium,
                            ctx.user_id, d["file_id"], d["file_type"], cat)
    ctx.clear_state()
    ctx.answer("✅ Saqlandi!")
    ctx.edit(f"🎉 <b>{cat_name(cat)} muvaffaqiyatli saqlandi!</b>\n\n"
             f"{cat_icon(cat)} <b>{esc(d['title'])}</b>\n"
             f"🔢 Kod: <code>{d['code']}</code>\n"
             f"{'💎 Turi: Premium' if premium else '🆓 Turi: Oddiy'}\n"
             f"🔗 Havola: {esc(ctx.app.deep_link(d['code']))}",
             ikb([btn("📢 Kanalga e'lon qilish", f"an:{movie_id}", style=SUCCESS)],
                 [btn("➕ Keyingi qismni qo'shish", f"am:addpart:{movie_id}", style=PRIMARY)],
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
    existing = db.get_movie_by_code(code) if code else None
    if existing:
        no = db.add_part(existing["id"], file_id, file_type)
        line = f"🎞 <code>{existing['code']}</code> — {esc(truncate(existing['title'], 40))} ({no}-qism)"
    else:
        code = code or db.next_code()
        cat = _cat(ctx)
        title = title or f"{cat_name(cat)} {code}"
        db.add_movie(code, title, desc, None, False, ctx.user_id, file_id, file_type, cat)
        line = f"{cat_icon(cat)} <code>{code}</code> — {esc(truncate(title, 40))}"
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
        ask_poster(ctx, (ctx.sdata.get("caption") or "")[:800])
    elif action == "skip":
        if state == "am:desc":
            ctx.answer()
            ask_poster(ctx, "")
        elif state == "am:poster":
            ctx.answer()
            show_confirm(ctx, None)
        else:
            _stale(ctx)
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
            ctx.send(f"🏁 <b>Tayyor!</b>\n\n🎬 {esc(movie['title'])}\n🔢 Kod: <code>{movie['code']}</code>\n"
                     f"➕ Bu safar qo'shildi: <b>{added}</b> qism\n🎞 Jami: <b>{n}</b> qism",
                     ikb([btn("📢 Kanalga e'lon qilish", f"an:{movie['id']}", style=SUCCESS)]))
        else:
            ctx.send("🏁 <b>Tayyor!</b>")


# ═════════════════════════ 📢 Kanalga e'lon ═════════════════════════

def announce_text(app, movie, parts: int) -> str:
    cat = movie["category"]
    head = f"{cat_icon(cat)} <b>{esc(movie['title'])}</b>"
    if parts > 1:
        head += f"\n📺 <b>{parts} qism</b>"
    meta = f"🔢 {cat_name(cat)} kodi: <code>{movie['code']}</code>"
    if movie["is_premium"]:
        meta += "\n💎 Premium"
    action = "Tinglash" if cat == "music" else "Tomosha qilish"
    tail = f"🤖 @{esc(app.bot_username)}\n👇 {action} uchun pastdagi tugmani bosing"
    budget = 1000 - visible_len(head) - visible_len(meta) - visible_len(tail) - 12
    blocks = [head]
    desc = (movie["description"] or "").strip()
    if desc and budget > 30:
        blocks.append("📝 " + esc(truncate(desc, min(budget, 700))))
    blocks += [meta, tail]
    return "\n\n".join(blocks)


@router.callback("an", admin=True)
def cb_announce(ctx: Ctx) -> None:
    app = ctx.app
    try:
        movie = ctx.db.get_movie(int(ctx.data.split(":")[1]))
    except (IndexError, ValueError):
        return
    if not movie:
        ctx.answer("😔 Kino topilmadi", alert=True)
        return
    channel = app.setting("post_channel")
    if not channel:
        ctx.answer("❗️ E'lon kanali sozlanmagan. ⚙️ Matnlar → 📣 E'lon kanali", alert=True)
        return
    text = announce_text(app, movie, ctx.db.count_parts(movie["id"]))
    label = "🎵 Tinglash" if movie["category"] == "music" else "🎬 Tomosha qilish"
    kb = ikb([btn(label, url=app.deep_link(movie["code"]), style=SUCCESS)])
    try:
        if movie["poster_id"]:
            sent = ctx.bot.send_photo(channel, movie["poster_id"], text, kb)
        else:
            sent = ctx.bot.send_message(channel, text, kb)
    except TelegramError as exc:
        log.warning("E'lon yuborilmadi: %s", exc)
        ctx.answer("❌ Kanalga yuborib bo'lmadi! Bot kanalda admin va post yozish huquqiga ega ekanini "
                   "tekshiring.", alert=True)
        return
    ctx.answer("✅ Kanalga e'lon qilindi!")
    link = post_link(sent.get("chat") or {}, sent.get("message_id"))
    ctx.send("📢 <b>E'lon kanalga joylandi!</b>",
             ikb([btn("👁 Postni ko'rish", url=link, style=PRIMARY)]) if link else None)


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
            f"🔢 Kod: <code>{movie['code']}</code>\n"
            f"🎞 Qismlar: <b>{n}</b>\n"
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
    rows.append([btn(f"🏷 Turini o'zgartirish ({cat_icon(cat)} {cat_name(cat)})", f"dm:cat:{mid}",
                     style=SUCCESS)])
    if ctx.app.setting_bool("premium_enabled") or movie["is_premium"]:
        rows.append([btn("🆓 Oddiy qilish" if movie["is_premium"] else "💎 Premium qilish",
                         f"dm:prem:{mid}", style=PRIMARY)])
    rows.append([btn("➕ Qism qo'shish", f"am:addpart:{mid}", style=SUCCESS),
                 btn("📢 E'lon qilish", f"an:{mid}", style=PRIMARY)])
    rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return text, ikb(*rows)


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
        db.delete_movie(mid)
        ctx.answer("🗑 O'chirildi")
        ctx.edit(f"🗑 <b>{esc(movie['title'])}</b> (kod {movie['code']}) o'chirildi.")
    elif action == "parts":
        ctx.answer()
        plist = db.get_parts(mid)
        lines = [f"🎞 <b>{esc(movie['title'])}</b> — qaysi qismni o'chiramiz?", ""]
        for p in plist[:50]:
            lines.append(f"<b>{p['part_no']}.</b> {esc(part_label(p))}")
        rows = number_rows([(p["part_no"], f"dm:pdel:{p['id']}") for p in plist[:50]], style=DANGER)
        rows.append([btn("⬅️ Orqaga", f"dm:open:{mid}", style=DANGER)])
        ctx.edit("\n".join(lines), {"inline_keyboard": rows})
    elif action == "cat":
        order = list(CATEGORIES)
        cur = movie["category"] if movie["category"] in order else "movie"
        new = order[(order.index(cur) + 1) % len(order)]
        db.update_movie(mid, category=new)
        ctx.answer(f"🏷 Turi: {cat_icon(new)} {cat_name(new)}")
        send_manage(ctx, db.get_movie(mid), edit=True)
    elif action == "prem":
        db.update_movie(mid, is_premium=not movie["is_premium"])
        ctx.answer("💎 Premium kino qilindi" if not movie["is_premium"] else "🆓 Oddiy kino qilindi")
        send_manage(ctx, db.get_movie(mid), edit=True)
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


def _edit_target(ctx: Ctx):
    movie = ctx.db.get_movie(ctx.sdata.get("movie_id") or 0)
    if not movie:
        ctx.clear_state()
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
    ctx.send("✅ Nom yangilandi!")
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
    ctx.db.update_movie(movie["id"], description="" if desc == "-" else desc)
    ctx.clear_state()
    ctx.send("✅ Ma'lumot yangilandi!")
    send_manage(ctx, ctx.db.get_movie(movie["id"]))


@router.state("dm:poster", admin=True)
def st_edit_poster(ctx: Ctx) -> None:
    movie = _edit_target(ctx)
    if not movie:
        return
    photos = ctx.message.get("photo")
    if photos:
        ctx.db.update_movie(movie["id"], poster_id=photos[-1]["file_id"])
    elif ctx.text.strip() == "-":
        ctx.db.update_movie(movie["id"], poster_id=None)
    else:
        ctx.send("❗️ Rasm yuboring yoki posterni olib tashlash uchun <code>-</code> yuboring.", cancel_kb())
        return
    ctx.clear_state()
    ctx.send("✅ Poster yangilandi!")
    send_manage(ctx, ctx.db.get_movie(movie["id"]))
