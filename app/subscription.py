"""Majburiy obuna: tekshirish, rangli obuna oynasi va zayavkalar."""

from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

from .core import App, Ctx, router
from .keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from .telegram import TelegramError
from .utils import esc, render

log = logging.getLogger("subscription")

CACHE_TTL = 300  # obuna tasdiqlangan foydalanuvchini 5 daqiqa qayta tekshirmaymiz
MEMBER_STATUSES = ("creator", "administrator", "member")


def _is_member(app: App, ch, user_id: int) -> bool:
    if ch["kind"] == "request" and app.db.has_join_request(user_id, ch["chat_id"]):
        return True
    try:
        member = app.bot.get_chat_member(ch["chat_id"], user_id)
    except TelegramError as exc:
        if exc.has("user not found", "participant_id_invalid", "user_id_invalid"):
            return False
        # Bot kanalda admin bo'lmasa foydalanuvchilarni bloklab qo'ymaymiz
        log.warning("Obunani tekshirib bo'lmadi (%s): %s", ch["chat_id"], exc.description)
        return True
    status = member.get("status")
    if status in MEMBER_STATUSES:
        return True
    if status == "restricted":
        return bool(member.get("is_member"))
    return False


def channel_statuses(app: App, user_id: int, force: bool = False) -> List[Tuple[object, Optional[bool]]]:
    """[(kanal, True/False/None)] — None: tekshirib bo'lmaydigan havola (Instagram va h.k.)."""
    result = []
    for ch in app.db.list_channels():
        if ch["kind"] == "link" or not ch["chat_id"]:
            result.append((ch, None))
            continue
        key = (user_id, ch["id"])
        if not force and app.sub_cache.get(key, 0) > time.time():
            result.append((ch, True))
            continue
        ok = _is_member(app, ch, user_id)
        if ok:
            app.sub_cache[key] = time.time() + CACHE_TTL
        else:
            app.sub_cache.pop(key, None)
        result.append((ch, ok))
    return result


def all_joined(statuses) -> bool:
    return all(ok is not False for _, ok in statuses)


def needs_gate(ctx: Ctx) -> bool:
    if ctx.is_admin:
        return False
    app = ctx.app
    if app.setting_bool("premium_skip_sub") and ctx.is_premium:
        return False
    return True


def gate_view(app: App, statuses, user: dict):
    rows = []
    for ch, ok in statuses:
        if ok is True:
            rows.append([btn("✅ Obuna bo'lingan", url=ch["url"], style=SUCCESS)])
        else:
            rows.append([btn("➕ Obuna bo'lish", url=ch["url"], style=DANGER)])
    rows.append([btn("🔄 Tekshirish", "chk", style=PRIMARY)])
    text = render(app.setting("sub_text"), name=esc(user.get("first_name") or ""), brand=esc(app.brand),
                  bot=app.bot_username)
    return text, ikb(*rows)


def show_gate(ctx: Ctx, statuses) -> None:
    text, kb = gate_view(ctx.app, statuses, ctx.user)
    ctx.send(text, kb)


def check_gate(ctx: Ctx) -> bool:
    """Router uchun: obuna bo'lmagan bo'lsa obuna oynasini ko'rsatadi va False qaytaradi."""
    if not needs_gate(ctx):
        return True
    statuses = channel_statuses(ctx.app, ctx.user_id)
    if all_joined(statuses):
        return True
    if ctx.callback is not None:
        ctx.answer("📢 Avval kanallarga obuna bo'ling!", alert=True)
    elif ctx.message is not None:
        text = ctx.text.strip()
        if text.startswith("/start"):
            payload = text[6:].strip()
            if payload:
                ctx.app.set_pending(ctx.user_id, payload)
        elif text and not text.startswith("/") and ctx.app.router.find_button(text) is None:
            ctx.app.set_pending(ctx.user_id, text)
    show_gate(ctx, statuses)
    return False


router.gate_check = check_gate


@router.on("join_request")
def on_join_request(ctx: Ctx) -> None:
    """Zayavkali kanalga so'rov yuborgan foydalanuvchini obunachi deb hisoblaymiz."""
    req = ctx.join_request
    chat_id = str(req["chat"]["id"])
    for ch in ctx.db.list_channels():
        if ch["kind"] == "request" and str(ch["chat_id"]) == chat_id:
            ctx.db.add_join_request(ctx.user_id, chat_id)
            target = req.get("user_chat_id") or ctx.user_id
            ctx.bot.safe("sendMessage", {
                "chat_id": target, "parse_mode": "HTML",
                "text": "✅ <b>So'rovingiz qabul qilindi!</b>\n\nEndi botga qaytib «🔄 Tekshirish» tugmasini bosing.",
            })
            break
