"""Ishga tushganda: boshlang'ich ma'lumotlar, buyruqlar menyusi, bot tavsifi va tekshiruvlar."""

from __future__ import annotations

import logging
import urllib.parse

from ..core import App, router
from ..telegram import TelegramError
from ..utils import channel_ref, esc
from .admin_panel import ADMIN_COMMANDS

log = logging.getLogger("bootstrap")

USER_COMMANDS = [
    {"command": "start", "description": "🏠 Bosh menyu"},
    {"command": "top", "description": "🔥 Top kinolar"},
    {"command": "new", "description": "🆕 Yangi kinolar"},
    {"command": "premium", "description": "💎 Premium obuna"},
    {"command": "donat", "description": "💝 Loyihani qo'llab-quvvatlash"},
    {"command": "help", "description": "ℹ️ Yordam"},
    {"command": "paysupport", "description": "🛟 To'lov bo'yicha yordam"},
    {"command": "terms", "description": "📜 Foydalanish shartlari"},
]

DEFAULT_PLANS = ((30, 10000, 50), (90, 25000, 120), (180, 45000, 220), (365, 80000, 400))


@router.on_startup
def seed_data(app: App) -> None:
    db = app.db
    settings = db.get_settings()
    if settings.get("_seeded_channels") != "1":
        for raw in app.config.channels:
            ref = channel_ref(raw)
            if ref is None:
                if raw.startswith("http"):
                    host = (urllib.parse.urlsplit(raw).hostname or "Havola").replace("www.", "")
                    db.add_channel(None, host, raw, "link")
                else:
                    log.warning(".env dagi kanal tushunilmadi: %s", raw)
                continue
            chat_id, title = ref, ref
            url = raw if raw.startswith("http") else (f"https://t.me/{ref[1:]}" if ref.startswith("@") else "")
            try:
                chat = app.bot.get_chat(ref)
                chat_id = str(chat["id"])
                title = chat.get("title") or title
                if not url and chat.get("username"):
                    url = f"https://t.me/{chat['username']}"
            except TelegramError as exc:
                log.warning("Kanal ma'lumotini olib bo'lmadi (%s): %s", ref, exc.description)
            if not url:
                log.warning("Kanal %s uchun havola yo'q — admin paneldan qo'shing", ref)
                continue
            if not db.channel_exists(chat_id):
                db.add_channel(chat_id, title, url, "public")
                log.info("Majburiy kanal qo'shildi: %s", title)
        app.set_setting("_seeded_channels", "1")
    if settings.get("_seeded_plans") != "1":
        if db.count_plans_all() == 0:
            for days, price, stars in DEFAULT_PLANS:
                db.add_plan(days, price, stars)
        app.set_setting("_seeded_plans", "1")


@router.on_startup
def setup_commands(app: App) -> None:
    commands = list(USER_COMMANDS)
    if app.config.webapp_url:
        commands.insert(1, {"command": "sayt", "description": "🌐 Sayt: kinolar, multfilmlar, musiqalar"})
    app.bot.safe("setMyCommands", {"commands": commands})
    for uid in app.admin_ids():
        app.bot.safe("setMyCommands", {"commands": ADMIN_COMMANDS, "scope": {"type": "chat", "chat_id": uid}})


@router.on_startup
def setup_description(app: App) -> None:
    brand = app.brand
    current = app.bot.safe("getMyDescription") or {}
    if not current.get("description"):
        app.bot.safe("setMyDescription", {"description": (
            f"🎬 {brand} — eng sara tarjima kinolar va multfilmlar boti!\n\n"
            "🔢 Kino kodini yoki 🔎 nomini yuboring — kino darhol keladi.\n"
            "🔥 Top, 🆕 yangi kinolar va 💎 Premium imkoniyatlar sizni kutmoqda!\n\n"
            "👇 Boshlash uchun «Start» tugmasini bosing")[:512]})
    current = app.bot.safe("getMyShortDescription") or {}
    if not current.get("short_description"):
        app.bot.safe("setMyShortDescription", {
            "short_description": f"🎬 {brand} — tarjima kinolar va multfilmlar. Kino kodini yuboring!"[:120]})


@router.on_startup
def railway_check(app: App) -> None:
    """Railway'da volume ulanmagan bo'lsa — har yangilanishda baza o'chib ketadi. Adminlarni ogohlantiramiz."""
    cfg = app.config
    log.info("Baza fayli: %s", cfg.db_path)
    if not cfg.on_railway or cfg.volume_path:
        return
    text = ("⚠️ <b>Diqqat! Railway'da Volume ulanmagan.</b>\n\n"
            "Hozir kinolar va foydalanuvchilar vaqtinchalik diskda saqlanmoqda — bot qayta joylansa "
            "(yangilanish, qayta ishga tushish) <b>hammasi o'chib ketadi</b>.\n\n"
            "Railway → loyiha → bo'sh joyda o'ng tugma → <b>Volume</b> → shu servisni tanlang → "
            "Mount path: <code>/app/data</code> → so'ng <b>Deploy</b>.")
    log.warning("Railway'da Volume ulanmagan — baza qayta joylashda o'chib ketadi!")
    for uid in cfg.owners:
        app.bot.safe("sendMessage", {"chat_id": uid, "text": text, "parse_mode": "HTML"})


@router.on_startup
def diagnostics(app: App) -> None:
    problems = []
    for ch in app.db.list_channels():
        if ch["kind"] == "link" or not ch["chat_id"]:
            continue
        try:
            member = app.bot.get_chat_member(ch["chat_id"], app.me.get("id"))
            ok = member.get("status") in ("administrator", "creator")
        except TelegramError:
            ok = False
        if not ok:
            problems.append(ch)
    log.info("Bazada: %s foydalanuvchi, %s kino, %s ta majburiy kanal",
             app.db.count_users(), app.db.count_movies(), len(app.db.list_channels()))
    if not problems:
        return
    names = "\n".join(f"• {esc(ch['title'])} — {esc(ch['url'])}" for ch in problems)
    text = ("⚠️ <b>Diqqat!</b> Bot quyidagi kanal(lar)da admin emas:\n\n"
            f"{names}\n\n"
            "Majburiy obuna ishlashi uchun botni kanalga <b>admin</b> qilib qo'shing:\n"
            f"Kanal → Administratorlar → Admin qo'shish → @{esc(app.bot_username)}")
    log.warning("Bot %s ta kanalda admin emas — majburiy obuna u yerda tekshirilmaydi", len(problems))
    for uid in app.config.owners:
        app.bot.safe("sendMessage", {"chat_id": uid, "text": text, "parse_mode": "HTML",
                                     "link_preview_options": {"is_disabled": True}})
