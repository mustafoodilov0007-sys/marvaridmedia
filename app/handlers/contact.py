"""✍️ Murojaat: foydalanuvchi adminlarga yozadi, admin javob qaytaradi."""

from __future__ import annotations

import logging
import time

from ..core import Ctx, router
from ..keyboards import PRIMARY, SUCCESS, btn, cancel_kb, ikb
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


# ═════════════════════════ 🎬 Kino so'rash ═════════════════════════

_last_request = {}       # foydalanuvchi -> (oxirgi so'ralgan kino, vaqt)

REQUEST_PROMPT = (
    "🎬 <b>Kino so'rash</b>\n\n"
    "Qaysi kinoni izlayapsiz? Nomini yozing 👇\n\n"
    "💡 Yili, tili yoki aktyorini ham qo'shsangiz, tezroq topamiz.\n"
    "<i>Masalan: «Avatar 3, 2025, o'zbek tilida»</i>"
)


def send_request(ctx: Ctx, query: str) -> bool:
    """So'ralgan kinoni barcha adminlarga yuboradi."""
    app = ctx.app
    query = (query or "").strip()[:300]
    if not query:
        return False
    prev_q, prev_t = _last_request.get(ctx.user_id, ("", 0.0))
    if prev_q.casefold() == query.casefold() and time.time() - prev_t < 3600:
        ctx.send(f"✅ «{esc(query)}» so'rovingiz allaqachon adminlarga yuborilgan. Tez orada qo'shamiz! 🙌")
        return True
    if time.time() - prev_t < 5:
        ctx.set_state("req", ttl=CONTACT_TTL)
        ctx.send("⏳ Biroz shoshildingiz 🙂 Bir necha soniyadan so'ng kino nomini qayta yuboring.", cancel_kb())
        return True
    _last_request[ctx.user_id] = (query, time.time())
    uname = f" (@{esc(ctx.user['username'])})" if ctx.user.get("username") else ""
    text = (f"🎬 <b>Yangi kino so'rovi</b>\n\n"
            f"🔎 <b>«{esc(query)}»</b>\n\n"
            f"👤 {user_link(ctx.user_id, ctx.user.get('first_name'))}{uname}\n🆔 <code>{ctx.user_id}</code>\n\n"
            "💡 Qo'shgach, foydalanuvchiga javob yozib kodini yuboring.")
    kb = ikb([btn("✍️ Javob berish", f"rep:{ctx.user_id}", style=PRIMARY)])
    delivered = 0
    for admin_id in app.admin_ids():
        try:
            ctx.bot.send_message(admin_id, text, kb)
            delivered += 1
        except TelegramError as exc:
            log.warning("Kino so'rovi adminga yetmadi (%s): %s", admin_id, exc.description)
    if delivered:
        ctx.send(f"✅ <b>So'rovingiz qabul qilindi!</b>\n\n🎬 «{esc(query)}»\n\n"
                 "Adminlarimiz kinoni topib, tez orada qo'shishadi va sizga xabar berishadi. 🙌\n"
                 "Shu orada boshqa kinolarni ham ko'rib chiqing 🍿")
    else:
        ctx.send("⚠️ So'rovni yuborib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")
    return True


@router.command("sorov", "sorash", "sorovnoma", gate=False)
def cmd_request(ctx: Ctx) -> None:
    if ctx.args.strip():  # «/sorov Avatar 3» — darhol yuboriladi
        send_request(ctx, ctx.args)
        return
    ctx.set_state("req", ttl=CONTACT_TTL)
    ctx.send(REQUEST_PROMPT, cancel_kb())


@router.state("req")
def st_request(ctx: Ctx) -> None:
    if not ctx.text.strip() or ctx.text.startswith("/"):
        ctx.send("❗️ Kino nomini matn ko'rinishida yozing.", cancel_kb())
        return
    ctx.clear_state()
    send_request(ctx, ctx.text)


@router.callback("rq")
def cb_request(ctx: Ctx) -> None:
    """Qidiruvda topilmagan kinoni bir bosishda so'rash: rq:<qidiruv id>."""
    try:
        row = ctx.db.get_search(int(ctx.data.split(":")[1]))
    except (IndexError, ValueError):
        row = None
    if not row or row["user_id"] != ctx.user_id:
        ctx.answer()
        ctx.set_state("req", ttl=CONTACT_TTL)
        ctx.send(REQUEST_PROMPT, cancel_kb())
        return
    ctx.answer("📨 Yuborilmoqda...")
    ctx.bot.safe("editMessageReplyMarkup", {"chat_id": ctx.chat_id, "message_id": ctx.cb_message.get("message_id")})
    send_request(ctx, row["query"])
