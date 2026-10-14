"""✍️ Murojaat: foydalanuvchi adminlarga yozadi, admin javob qaytaradi."""

from __future__ import annotations

import logging
import time

from ..core import Ctx, router
from ..keyboards import PRIMARY, btn, cancel_kb, ikb
from ..telegram import Forbidden, TelegramError
from ..texts import B
from ..utils import esc, message_html, user_link, visible_len

log = logging.getLogger("contact")

CONTACT_TTL = 600        # murojaat yozish holati 10 daqiqa amal qiladi
_last_contact = {}       # spamdan himoya: foydalanuvchi -> oxirgi murojaat vaqti


def start_contact(ctx: Ctx) -> None:
    ctx.set_state("contact", ttl=CONTACT_TTL)
    ctx.send("✍️ <b>Murojaat</b>\n\n"
             "Adminlarga xabaringizni yozing: kino so'rovi, taklif yoki muammo.\n"
             "Matn, rasm, video yoki ovozli xabar yuborishingiz mumkin 👇", cancel_kb())


@router.button(B.CONTACT, gate=False)
@router.command("murojaat", "contact", gate=False)
def btn_contact(ctx: Ctx) -> None:
    start_contact(ctx)


@router.callback("ct")
def cb_contact(ctx: Ctx) -> None:
    ctx.answer()
    start_contact(ctx)


@router.state("contact")
def st_contact(ctx: Ctx) -> None:
    app = ctx.app
    msg = ctx.message
    last = _last_contact.get(ctx.user_id, 0)
    if time.time() - last < 20:
        ctx.send("⏳ Iltimos, keyingi murojaatni biroz kutib yuboring.")
        return
    _last_contact[ctx.user_id] = time.time()
    ctx.clear_state()

    uname = f" (@{esc(ctx.user['username'])})" if ctx.user.get("username") else ""
    header = (f"📨 <b>Yangi murojaat</b>\n\n👤 {user_link(ctx.user_id, ctx.user.get('first_name'))}{uname}\n"
              f"🆔 <code>{ctx.user_id}</code>")
    kb = ikb([btn("✍️ Javob berish", f"rep:{ctx.user_id}", style=PRIMARY)])
    body = message_html(msg) if msg.get("text") else ""
    delivered = 0
    for admin_id in app.admin_ids():
        try:
            if body and visible_len(body) < 3500:
                ctx.bot.send_message(admin_id, f"{header}\n\n💬 {body}", kb)
            else:
                ctx.bot.send_message(admin_id, header)
                ctx.bot.copy_message(admin_id, ctx.chat_id, msg["message_id"], reply_markup=kb)
            delivered += 1
        except TelegramError as exc:
            log.warning("Murojaat adminga yetmadi (%s): %s", admin_id, exc.description)
    if delivered:
        ctx.send("✅ <b>Xabaringiz adminlarga yuborildi!</b>\n\nTez orada javob beramiz. Rahmat! 😊")
    else:
        ctx.send("⚠️ Xabarni yuborib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")


@router.callback("rep", admin=True)
def cb_reply(ctx: Ctx) -> None:
    try:
        uid = int(ctx.data.split(":")[1])
    except (IndexError, ValueError):
        return
    ctx.answer()
    u = ctx.db.get_user(uid)
    name = esc(u["first_name"]) if u and u["first_name"] else str(uid)
    ctx.set_state("reply", uid=uid)
    ctx.send(f"✍️ <b>{name}</b> ga javobingizni yozing (matn, rasm, video...):", cancel_kb())


@router.state("reply", admin=True)
def st_reply(ctx: Ctx) -> None:
    uid = ctx.sdata.get("uid")
    ctx.clear_state()
    msg = ctx.message
    try:
        body = message_html(msg) if msg.get("text") else ""
        if body and visible_len(body) < 3800:
            ctx.bot.send_message(uid, f"📩 <b>Admin javobi:</b>\n\n{body}")
        else:
            ctx.bot.send_message(uid, "📩 <b>Admin javobi:</b>")
            ctx.bot.copy_message(uid, ctx.chat_id, msg["message_id"])
    except Forbidden:
        ctx.db.set_blocked(uid, True)
        ctx.send("❌ Foydalanuvchi botni bloklagan — javob yetkazilmadi.")
        return
    except TelegramError as exc:
        ctx.send(f"❌ Javob yuborilmadi: {esc(exc.description)}")
        return
    ctx.send("✅ Javobingiz foydalanuvchiga yuborildi!")
