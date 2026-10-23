"""Foydalanuvchi bo'limi: start, qidiruv, raqamli ro'yxatlar va kinolarni yuborish."""

from __future__ import annotations

import logging
import math
import re
import urllib.parse
from typing import List, Optional

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb, nav_row, number_rows, user_menu
from ..subscription import all_joined, channel_statuses, gate_view, needs_gate
from ..telegram import BadRequest
from ..texts import B, HELP_TEXT, cat_icon
from ..utils import (esc, fmt_compact, fmt_num, fmt_short_date, fuzzy_match, normalize, now, render,
                     truncate, visible_len)

log = logging.getLogger("user")

PER_PAGE = 10        # ro'yxatda bir sahifadagi kinolar soni
MAX_RESULTS = 100    # qidiruvdagi eng ko'p natija
LIST_LIMIT = 50      # Top / Yangi ro'yxatlari uzunligi
CODE_RE = re.compile(r"#?\s*(\d{1,9})")

_reported_parts = set()


# ═════════════════════════ start / yordam ═════════════════════════

def send_welcome(ctx: Ctx) -> None:
    app = ctx.app
    text = render(app.setting("start_text"), name=esc(ctx.user.get("first_name") or "do'stim"),
                  brand=esc(app.brand), bot=app.bot_username)
    ctx.send(text, user_menu(ctx.is_admin, app.setting_bool("premium_enabled")))


@router.command("start")
def cmd_start(ctx: Ctx) -> None:
    payload = ctx.args.strip()
    code = CODE_RE.fullmatch(payload) if payload else None
    user = ctx.db.get_user(ctx.user_id)
    is_new = user is None or now() - user["joined_at"] < 15
    if not code or is_new:
        send_welcome(ctx)
    if code:
        handle_query(ctx, payload)


@router.command("help", gate=False)
def cmd_help(ctx: Ctx) -> None:
    ctx.send(HELP_TEXT)


@router.command("id", gate=False)
def cmd_id(ctx: Ctx) -> None:
    ctx.send(f"🆔 Sizning ID raqamingiz: <code>{ctx.user_id}</code>")


@router.callback("chk")
def cb_check(ctx: Ctx) -> None:
    app = ctx.app
    statuses = channel_statuses(app, ctx.user_id, force=True) if needs_gate(ctx) else []
    if all_joined(statuses):
        ctx.answer("✅ Obuna tasdiqlandi! Xush kelibsiz!")
        ctx.delete_cb_message()
        send_welcome(ctx)
        pending = app.pop_pending(ctx.user_id)
        if pending:
            handle_query(ctx, pending)
        return
    ctx.answer("❌ Siz hali barcha kanallarga obuna bo'lmadingiz!\n\n"
               "Qizil tugmalar orqali obuna bo'lib, qayta tekshiring.", alert=True)
    text, kb = gate_view(app, statuses, ctx.user)
    ctx.edit(text, kb)


@router.on("my_chat_member")
def on_my_chat_member(ctx: Ctx) -> None:
    upd = ctx.member_update
    if upd.get("chat", {}).get("type") != "private":
        return
    status = upd.get("new_chat_member", {}).get("status")
    ctx.db.set_blocked(upd["chat"]["id"], status in ("kicked", "left"))


# ═════════════════════════ menyu tugmalari ═════════════════════════

@router.button(B.SEARCH)
def btn_search(ctx: Ctx) -> None:
    ctx.send("🔎 <b>Kino qidirish</b>\n\n"
             "Kino <b>nomini</b> yoki <b>kodini</b> yozib yuboring 👇\n\n"
             "💡 Masalan: <code>Avatar</code> yoki <code>15</code>")


@router.button(B.SITE)
@router.command("sayt", "site")
def btn_site(ctx: Ctx) -> None:
    url = ctx.app.config.webapp_url
    if not url:
        ctx.send("🌐 Sayt hozircha ishga tushirilmagan. Tez orada!")
        return
    c = ctx.db.count_by_category()
    ctx.send(f"🌐 <b>{esc(ctx.app.brand)} sayti</b>\n\n"
             f"🎬 Kinolar: <b>{fmt_num(c['movie'])}</b>\n"
             f"🧸 Multfilmlar: <b>{fmt_num(c['cartoon'])}</b>\n"
             f"🎵 Musiqalar: <b>{fmt_num(c['music'])}</b>\n\n"
             "Hammasi bir joyda — tanlang, bot darhol yuboradi 👇",
             ikb([{"text": "🌐 Saytni ochish", "web_app": {"url": url}, "style": SUCCESS}]))


@router.button(B.TOP)
@router.command("top")
def btn_top(ctx: Ctx) -> None:
    text, kb = list_page(ctx, "tp", 0)
    ctx.send(text, kb)


@router.button(B.NEW)
@router.command("new")
def btn_new(ctx: Ctx) -> None:
    text, kb = list_page(ctx, "np", 0)
    ctx.send(text, kb)


@router.button(B.RANDOM)
@router.command("random")
def btn_random(ctx: Ctx) -> None:
    send_random(ctx)


@router.callback("rnd", gate=True)
def cb_random(ctx: Ctx) -> None:
    ctx.answer("🎲")
    send_random(ctx)


def send_random(ctx: Ctx) -> None:
    include_premium = ctx.vip or not ctx.app.setting_bool("premium_enabled")
    movie = ctx.db.random_movie(include_premium)
    if not movie:
        ctx.send("📭 Hozircha bazada kinolar yo'q.")
        return
    open_movie(ctx, movie, extra_rows=[[btn("🎲 Yana bittasi", "rnd", style=PRIMARY)]])


# ═════════════════════════ kod / nom bo'yicha qidiruv ═════════════════════════

@router.default()
def on_any_message(ctx: Ctx) -> None:
    if ctx.text:
        handle_query(ctx, ctx.text)
        return
    hook = ctx.app.router.special.get("admin_media")
    if ctx.is_admin and hook and hook(ctx):
        return
    ctx.send("🔢 Kino <b>kodini</b> yoki 🔎 <b>nomini</b> yozib yuboring.")


def handle_query(ctx: Ctx, raw: str) -> None:
    app, db = ctx.app, ctx.db
    text = (raw or "").strip()
    m = CODE_RE.fullmatch(text)
    if m:
        code = int(m.group(1))
        movie = db.get_movie_by_code(code)
        db.log_search(ctx.user_id, text, str(code), 1 if movie else 0)
        if movie:
            open_movie(ctx, movie)
        else:
            ctx.send(f"😔 <b>{code}</b> kodli kino topilmadi.\n\n"
                     "🔎 Kodni tekshirib qayta yuboring yoki kino nomini yozib qidiring.", not_found_kb())
        return

    text = text[:100]
    norm = normalize(text)
    if len(norm.replace(" ", "")) < 2:
        ctx.send("🔎 Qidirish uchun kamida <b>2 ta harf</b> yozing.")
        return
    ids, fuzzy = search_ids(app, norm)
    sid = db.log_search(ctx.user_id, text, norm, 0 if fuzzy else len(ids))
    if not ids:
        ctx.send(f"😔 <b>«{esc(truncate(text, 50))}»</b> bo'yicha hech narsa topilmadi.\n\n"
                 "💡 <b>Maslahatlar:</b>\n"
                 "• Nomini boshqacharoq yozib ko'ring\n"
                 "• Kino kodini yuboring (masalan: <code>15</code>)\n"
                 "• Kerakli kinoni «✍️ Kino so'rash» orqali so'rang", not_found_kb())
        return
    app.cache_search(sid, (text, ids, fuzzy))
    page_text, kb = search_view(app, sid, text, ids, fuzzy, 0)
    ctx.send(page_text, kb)


def not_found_kb() -> dict:
    return ikb([btn("🔥 Top kinolar", "tp:0", style=SUCCESS), btn("🆕 Yangi kinolar", "np:0", style=PRIMARY)],
               [btn("✍️ Kino so'rash", "ct:start", style=DANGER)])


def search_ids(app, norm: str):
    """(id lar ro'yxati, taxminiy_natijami) qaytaradi."""
    tokens = norm.split()
    rows = app.db.search_candidates(tokens)
    if rows:
        scored = []
        for r in rows:
            title = r["norm_title"]
            if title == norm:
                score = 0
            elif title.startswith(norm):
                score = 1
            elif all(re.search(r"\b" + re.escape(t), title) for t in tokens):
                score = 2
            elif all(t in title for t in tokens):
                score = 3
            else:
                score = 4  # faqat ma'lumot (tavsif) ichida topildi
            scored.append((score, -r["views"], -r["id"], r["id"]))
        scored.sort()
        return [x[3] for x in scored[:MAX_RESULTS]], False
    titles = [(r["id"], r["norm_title"]) for r in app.db.all_titles()]
    return fuzzy_match(norm, titles, limit=30), True


def fmt_item(r, extra: Optional[str] = None) -> str:
    title = esc(truncate(r["title"], 60))
    category = r["category"] if "category" in r.keys() else "movie"
    if category != "movie":
        title = cat_icon(category) + " " + title
    if r["is_premium"]:
        title = "💎 " + title
    bits = []
    if r["parts"] > 1:
        bits.append(f"📺 {r['parts']} qism")
    if extra:
        bits.append(extra)
    return title + (f"  <i>{' • '.join(bits)}</i>" if bits else "")


def build_list(header: str, rows, start_no: int, page: int, pages: int, page_prefix: Optional[str],
               item_fmt, item_cb: str = "mv", hint: str = "👇 Kerakli kino raqamini tanlang:"):
    """Raqamlangan ro'yxat: matnda 1. 2. 3. …, pastda raqamli tugmalar."""
    lines = [header, ""]
    nums = []
    for i, r in enumerate(rows, start_no + 1):
        lines.append(f"<b>{i}.</b> {item_fmt(r)}")
        nums.append((i, f"{item_cb}:{r['id']}"))
    lines.append("")
    if pages > 1:
        lines.append(f"📄 Sahifa: <b>{page + 1}/{pages}</b>")
    lines.append(hint)
    kb_rows = number_rows(nums)
    if pages > 1 and page_prefix:
        kb_rows.append(nav_row(page_prefix, page, pages))
    kb_rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return "\n".join(lines), {"inline_keyboard": kb_rows}


def search_view(app, sid: int, query: str, ids: List[int], fuzzy: bool, page: int):
    total = len(ids)
    pages = max(1, math.ceil(total / PER_PAGE))
    page %= pages
    rows = app.db.movie_rows(ids[page * PER_PAGE:(page + 1) * PER_PAGE])
    q = esc(truncate(query, 40))
    if fuzzy:
        header = (f"🤔 <b>«{q}»</b> bo'yicha aniq natija topilmadi.\n"
                  "💡 Balki shulardan birini nazarda tutgandirsiz:")
    else:
        header = f"🔎 <b>«{q}»</b> bo'yicha <b>{total}</b> ta natija:"
    return build_list(header, rows, page * PER_PAGE, page, pages, f"sp:{sid}", fmt_item)


@router.callback("sp", gate=True)
def cb_search_page(ctx: Ctx) -> None:
    try:
        _, sid, page = ctx.data.split(":")
        sid, page = int(sid), int(page)
    except ValueError:
        return
    cached = ctx.app.cached_search(sid)
    if not cached:
        row = ctx.db.get_search(sid)
        if not row:
            ctx.answer("⌛️ Qidiruv eskirgan. Kino nomini qaytadan yozing.", alert=True)
            return
        ids, fuzzy = search_ids(ctx.app, row["norm"])
        cached = (row["query"], ids, fuzzy)
        ctx.app.cache_search(sid, cached)
    query, ids, fuzzy = cached
    if not ids:
        ctx.answer("😔 Natija qolmadi", alert=True)
        return
    text, kb = search_view(ctx.app, sid, query, ids, fuzzy, page)
    ctx.answer()
    edit_or_send(ctx, text, kb)


def edit_or_send(ctx: Ctx, text: str, kb) -> None:
    """Matnli xabar bo'lsa tahrirlaydi, aks holda (video, rasm) yangisini yuboradi."""
    if "text" in ctx.cb_message:
        ctx.edit(text, kb)
    else:
        ctx.send(text, kb)


# ═════════════════════════ Top / Yangi ═════════════════════════

def list_page(ctx: Ctx, kind: str, page: int):
    db = ctx.db
    rows = db.top_movies(LIST_LIMIT) if kind == "tp" else db.new_movies(LIST_LIMIT)
    if not rows:
        return "📭 Hozircha bazada kinolar yo'q. Tez orada qo'shiladi!", None
    pages = max(1, math.ceil(len(rows) / PER_PAGE))
    page %= pages
    chunk = rows[page * PER_PAGE:(page + 1) * PER_PAGE]
    if kind == "tp":
        header = "🔥 <b>Eng ko'p ko'rilgan kinolar</b>"

        def fmt(r):
            return fmt_item(r, f"👁 {fmt_compact(r['views'])}")
    else:
        header = "🆕 <b>Yangi qo'shilgan kinolar</b>"

        def fmt(r):
            return fmt_item(r, f"🗓 {fmt_short_date(r['created_at'])}")
    return build_list(header, chunk, page * PER_PAGE, page, pages, kind, fmt)


@router.callback("tp", "np", gate=True)
def cb_list_page(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    kind = parts[0]
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    text, kb = list_page(ctx, kind, page)
    ctx.answer()
    edit_or_send(ctx, text, kb)


# ═════════════════════════ kinoni ochish va yuborish ═════════════════════════

def premium_locked(ctx: Ctx, movie) -> bool:
    return bool(movie["is_premium"]) and ctx.app.setting_bool("premium_enabled") and not ctx.vip


def send_premium_lock(ctx: Ctx, movie) -> None:
    ctx.send("🔒 <b>Bu kino faqat Premium a'zolar uchun!</b>\n\n"
             f"🎬 <b>{esc(movie['title'])}</b>\n\n"
             "💎 Premium obuna bilan ushbu va boshqa maxsus kinolarni cheklovsiz tomosha qiling.",
             ikb([btn("💎 Premium olish", "pr:menu", style=SUCCESS)]))


def protect_for(ctx: Ctx) -> bool:
    return ctx.app.setting_bool("protect_content") and not ctx.vip


def part_label(part) -> str:
    return part["title"] or f"{part['part_no']}-qism"


def open_movie(ctx: Ctx, movie, extra_rows=None) -> None:
    if premium_locked(ctx, movie):
        send_premium_lock(ctx, movie)
        return
    parts = ctx.db.get_parts(movie["id"])
    if not parts:
        ctx.send("⚠️ Bu kinoning fayli topilmadi.")
        return
    if len(parts) == 1:
        send_part(ctx, movie, parts[0], 1, extra_rows)
    else:
        send_parts_list(ctx, movie, parts, 0, extra_rows)


def build_caption(app, movie, part, total: int) -> str:
    head = f"{cat_icon(movie['category'])} <b>{esc(movie['title'])}</b>"
    if total > 1:
        head += f"\n📺 <b>{esc(part_label(part))}</b>  <i>({total} qismdan)</i>"
    meta = f"🔢 Kod: <code>{movie['code']}</code>  •  👁 {fmt_num(movie['views'] + 1)}"
    if movie["is_premium"]:
        meta += "  •  💎 Premium"
    footer = render(app.setting("caption_footer"), brand=esc(app.brand), bot=app.bot_username).strip()
    blocks = [head]
    budget = 1000 - visible_len(head) - visible_len(meta) - visible_len(footer) - 12
    desc = (movie["description"] or "").strip()
    if desc and budget > 30:
        blocks.append("📝 " + esc(truncate(desc, budget - 3)))
    blocks.append(meta)
    if footer:
        blocks.append(footer)
    return "\n\n".join(blocks)


def part_kb(app, movie, part, total: int, extra_rows=None) -> dict:
    rows = []
    if total > 1:
        no = part["part_no"]
        nav = []
        prev_part = app.db.get_part_by_no(movie["id"], no - 1) if no > 1 else None
        next_part = app.db.get_part_by_no(movie["id"], no + 1) if no < total else None
        if prev_part:
            nav.append(btn(f"⬅️ {no - 1}-qism", f"pt:{prev_part['id']}", style=SUCCESS))
        nav.append(btn("📋 Qismlar", f"pl:{movie['id']}:{(no - 1) // PER_PAGE}", style=PRIMARY))
        if next_part:
            nav.append(btn(f"{no + 1}-qism ➡️", f"pt:{next_part['id']}", style=SUCCESS))
        rows.append(nav)
    share = "https://t.me/share/url?" + urllib.parse.urlencode({
        "url": app.deep_link(movie["code"]),
        "text": f"🎬 {movie['title']} — {app.brand} botida tomosha qiling!",
    })
    rows.append([btn("📤 Do'stlarga ulashish", url=share, style=PRIMARY)])
    if extra_rows:
        rows.extend(extra_rows)
    return {"inline_keyboard": rows}


def send_part(ctx: Ctx, movie, part, total: int, extra_rows=None) -> None:
    app = ctx.app
    caption = build_caption(app, movie, part, total)
    kb = part_kb(app, movie, part, total, extra_rows)
    protect = protect_for(ctx)
    try:
        if part["file_type"] == "video":
            ctx.bot.send_video(ctx.chat_id, part["file_id"], caption, kb, protect)
        elif part["file_type"] == "audio":
            ctx.bot.send_audio(ctx.chat_id, part["file_id"], caption, kb, protect)
        else:
            ctx.bot.send_document(ctx.chat_id, part["file_id"], caption=caption, reply_markup=kb,
                                  protect_content=protect)
    except BadRequest as exc:
        log.error("Kino yuborilmadi (kod %s, qism %s): %s", movie["code"], part["part_no"], exc)
        ctx.send("⚠️ Kechirasiz, bu kino faylini yuborib bo'lmadi. Adminlar xabardor qilindi.")
        if part["id"] not in _reported_parts:
            _reported_parts.add(part["id"])
            app.notify_admins(
                "⚠️ <b>Kino faylida muammo!</b>\n\n"
                f"🎬 {esc(movie['title'])}\n🔢 Kod: <code>{movie['code']}</code> • {part['part_no']}-qism\n"
                f"❗️ {esc(exc.description)}\n\nFaylni qayta yuklash tavsiya etiladi.")
        return
    ctx.db.inc_views(movie["id"], part["id"])


def parts_view(movie, parts, page: int, extra_rows=None):
    total = len(parts)
    pages = max(1, math.ceil(total / PER_PAGE))
    page %= pages
    chunk = parts[page * PER_PAGE:(page + 1) * PER_PAGE]
    lines = [f"📺 <b>{esc(truncate(movie['title'], 100))}</b>", f"🎞 Jami: <b>{total}</b> qism", ""]
    nums = []
    for p in chunk:
        lines.append(f"<b>{p['part_no']}.</b> {esc(truncate(part_label(p), 60))}")
        nums.append((p["part_no"], f"pt:{p['id']}"))
    lines.append("")
    if pages > 1:
        lines.append(f"📄 Sahifa: <b>{page + 1}/{pages}</b>")
    lines.append("👇 Kerakli qism raqamini tanlang:")
    rows = number_rows(nums)
    if pages > 1:
        rows.append(nav_row(f"pl:{movie['id']}", page, pages))
    if extra_rows:
        rows.extend(extra_rows)
    rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return "\n".join(lines), {"inline_keyboard": rows}


def send_parts_list(ctx: Ctx, movie, parts, page: int, extra_rows=None) -> None:
    text, kb = parts_view(movie, parts, page, extra_rows)
    if movie["poster_id"]:
        try:
            ctx.bot.send_photo(ctx.chat_id, movie["poster_id"], text, kb)
            return
        except BadRequest as exc:
            log.warning("Poster yuborilmadi (kod %s): %s", movie["code"], exc.description)
    ctx.send(text, kb)


@router.callback("mv", gate=True)
def cb_movie(ctx: Ctx) -> None:
    try:
        movie = ctx.db.get_movie(int(ctx.data.split(":")[1]))
    except (IndexError, ValueError):
        return
    if not movie:
        ctx.answer("😔 Bu kino o'chirilgan.", alert=True)
        return
    ctx.answer("🎬 Yuborilmoqda...")
    open_movie(ctx, movie)


@router.callback("pt", gate=True)
def cb_part(ctx: Ctx) -> None:
    try:
        part = ctx.db.get_part(int(ctx.data.split(":")[1]))
    except (IndexError, ValueError):
        return
    movie = ctx.db.get_movie(part["movie_id"]) if part else None
    if not part or not movie:
        ctx.answer("😔 Bu qism o'chirilgan.", alert=True)
        return
    if premium_locked(ctx, movie):
        ctx.answer()
        send_premium_lock(ctx, movie)
        return
    ctx.answer("🎬 Yuborilmoqda...")
    send_part(ctx, movie, part, ctx.db.count_parts(movie["id"]))


@router.callback("pl", gate=True)
def cb_parts_list(ctx: Ctx) -> None:
    try:
        _, mid, page = ctx.data.split(":")
        movie = ctx.db.get_movie(int(mid))
        page = int(page)
    except ValueError:
        return
    parts = ctx.db.get_parts(movie["id"]) if movie else []
    if not parts:
        ctx.answer("😔 Bu kino o'chirilgan.", alert=True)
        return
    if premium_locked(ctx, movie):
        ctx.answer()
        send_premium_lock(ctx, movie)
        return
    ctx.answer()
    msg = ctx.cb_message
    if msg.get("video") or msg.get("document") or msg.get("audio"):
        send_parts_list(ctx, movie, parts, page)
    else:
        text, kb = parts_view(movie, parts, page)
        ctx.edit(text, kb)
