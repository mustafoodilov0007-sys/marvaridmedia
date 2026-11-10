"""✍️ Murojaat: foydalanuvchi adminlarga yozadi, admin javob qaytaradi."""

from __future__ import annotations

import logging
import time
import zlib

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..telegram import Forbidden, TelegramError
from ..texts import B
from ..utils import esc, message_html, user_link, visible_len

log = logging.getLogger("contact")

CONTACT_TTL = 600        # murojaat yozish holati 10 daqiqa amal qiladi
_last_contact = {}       # spamdan himoya: foydalanuvchi -> oxirgi murojaat vaqti


def ticket_kb(uid: int, tid: int, banned: bool = False) -> dict:
    return ikb([btn("✍️ Javob berish", f"rep:{uid}:{tid}", style=PRIMARY),
                btn("✅ Cheklashni olish" if banned else "🚫 Cheklash", f"bn:{uid}:{tid}", style=DANGER)])


def _banned_reply(ctx: Ctx) -> bool:
    if ctx.db.is_contact_banned(ctx.user_id):
        ctx.clear_state()
        ctx.send("⛔️ Hozircha murojaat yuborish imkoni cheklangan.")
        return True
    return False


def start_contact(ctx: Ctx) -> None:
    if _banned_reply(ctx):
        return
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
    if len(_last_contact) > 5000:
        _last_contact.clear()
    _last_contact[ctx.user_id] = time.time()
    ctx.clear_state()
    if _banned_reply(ctx):
        return
    tid = ctx.db.create_ticket("msg", ctx.user_id)

    uname = f" (@{esc(ctx.user['username'])})" if ctx.user.get("username") else ""
    header = (f"📨 <b>Yangi murojaat</b>\n\n👤 {user_link(ctx.user_id, ctx.user.get('first_name'))}{uname}\n"
              f"🆔 <code>{ctx.user_id}</code>")
    kb = ticket_kb(ctx.user_id, tid)
    body = message_html(msg) if msg.get("text") else ""
    delivered = 0
    for admin_id in app.admin_ids():
        try:
            if body and visible_len(body) < 3500:
                sent = ctx.bot.send_message(admin_id, f"{header}\n\n💬 {body}", kb)
            else:
                ctx.bot.send_message(admin_id, header)
                sent = ctx.bot.copy_message(admin_id, ctx.chat_id, msg["message_id"], reply_markup=kb)
            ctx.db.add_ticket_msg(tid, admin_id, sent["message_id"])
            delivered += 1
        except TelegramError as exc:
            log.warning("Murojaat adminga yetmadi (%s): %s", admin_id, exc.description)
    if delivered:
        ctx.send("✅ <b>Xabaringiz adminlarga yuborildi!</b>\n\nTez orada javob beramiz. Rahmat! 😊")
    else:
        ctx.send("⚠️ Xabarni yuborib bo'lmadi. Birozdan so'ng qayta urinib ko'ring.")


def _handled_kb(name: str) -> dict:
    return ikb([btn(f"✅ Javob berildi — {name[:30]}", "nop")])


@router.callback("nop")
def cb_nop(ctx: Ctx) -> None:
    ctx.answer()


@router.callback("rep", admin=True)
def cb_reply(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    try:
        uid = int(parts[1])
        tid = int(parts[2]) if len(parts) > 2 else 0
    except (IndexError, ValueError):
        return
    t = ctx.db.get_ticket(tid) if tid else None
    if t and t["status"] == "done" and t["handled_by"] != ctx.user_id:
        who = ctx.db.get_user(t["handled_by"])
        ctx.answer(f"ℹ️ Bu murojaatga {(who['first_name'] if who else '') or 'boshqa admin'} allaqachon javob bergan.",
                   alert=True)
        return
    ctx.answer()
    u = ctx.db.get_user(uid)
    name = esc(u["first_name"]) if u and u["first_name"] else str(uid)
    ctx.set_state("reply", uid=uid, tid=tid)
    ctx.send(f"✍️ <b>{name}</b> ga javobingizni yozing (matn, rasm, video...):", cancel_kb())


@router.callback("bn", admin=True)
def cb_ban(ctx: Ctx) -> None:
    from .audit import audit
    parts = ctx.data.split(":")
    try:
        uid, tid = int(parts[1]), int(parts[2])
    except (IndexError, ValueError):
        return
    banned = not ctx.db.is_contact_banned(uid)
    ctx.db.set_contact_banned(uid, banned)
    audit(ctx.app, ctx.user_id, "ban", f"{uid}: {'cheklandi' if banned else 'cheklash olindi'}")
    ctx.answer("🚫 Murojaat yuborishi cheklandi" if banned else "✅ Cheklash olindi", alert=True)
    t = ctx.db.get_ticket(tid)
    if t and t["status"] == "open":
        for row in ctx.db.ticket_msgs(tid):
            ctx.bot.safe("editMessageReplyMarkup", {"chat_id": row["admin_id"], "message_id": row["message_id"],
                                                    "reply_markup": ticket_kb(uid, tid, banned)})


@router.state("reply", admin=True)
def st_reply(ctx: Ctx) -> None:
    uid = ctx.sdata.get("uid")
    tid = ctx.sdata.get("tid") or 0
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
    if tid and ctx.db.close_ticket(tid, ctx.user_id):      # boshqa adminlarda «javob berildi» deb ko'rinsin
        name = ctx.user.get("first_name") or "Admin"
        for row in ctx.db.ticket_msgs(tid):
            ctx.bot.safe("editMessageReplyMarkup", {"chat_id": row["admin_id"], "message_id": row["message_id"],
                                                    "reply_markup": _handled_kb(name)})


# ═════════════════════════ 🎬 Kino so'rash ═════════════════════════

_last_request = {}       # foydalanuvchi -> (oxirgi so'ralgan kino, vaqt)

REQUEST_PROMPT = (
    "🎬 <b>Kino so'rash</b>\n\n"
    "Qaysi kinoni izlayapsiz? Nomini yozing 👇\n\n"
    "💡 Yili, tili yoki aktyorini ham qo'shsangiz, tezroq topamiz.\n"
    "<i>Masalan: «Avatar 3, 2025, o'zbek tilida»</i>"
)


def _already_in_bot(ctx: Ctx, query: str) -> bool:
    """So'ralgan kino bazada bo'lsa — adminni bezovta qilmay, foydalanuvchiga o'zini ko'rsatamiz."""
    from ..utils import normalize
    from .user import search_view
    app, db = ctx.app, ctx.db
    norm = normalize(query)
    need = _need_tokens(norm)
    if not need:
        return False
    ids = [r["id"] for r in db.search_candidates(need, scope=None)
           if all(t in r["norm_title"] for t in need)]
    if not ids:
        return False
    ids = ids[:50]
    sid = db.log_search(ctx.user_id, query, norm, len(ids))
    app.cache_search(sid, (query, ids, False))
    ctx.clear_state()
    text, kb = search_view(app, sid, query, ids, False, 0, 0)
    ctx.send("✅ <b>Bu kino bazamizda bor!</b> So'rov yuborish shart emas — tanlang 👇\n\n" + text, kb)
    return True


def send_request(ctx: Ctx, query: str) -> bool:
    """So'ralgan kinoni barcha adminlarga yuboradi."""
    app = ctx.app
    query = (query or "").strip()[:300]
    if not query:
        return False
    if _already_in_bot(ctx, query):
        return True
    prev_q, prev_t = _last_request.get(ctx.user_id, ("", 0.0))
    if prev_q.casefold() == query.casefold() and time.time() - prev_t < 3600:
        ctx.send(f"✅ «{esc(query)}» so'rovingiz allaqachon adminlarga yuborilgan. Tez orada qo'shamiz! 🙌")
        return True
    if time.time() - prev_t < 5:
        ctx.set_state("req", ttl=CONTACT_TTL)
        ctx.send("⏳ Biroz shoshildingiz 🙂 Bir necha soniyadan so'ng kino nomini qayta yuboring.", cancel_kb())
        return True
    if len(_last_request) > 5000:   # xotira cheksiz o'smasin
        _last_request.clear()
    _last_request[ctx.user_id] = (query, time.time())
    if ctx.db.is_contact_banned(ctx.user_id):
        ctx.send("⛔️ Hozircha so'rov yuborish imkoni cheklangan.")
        return True
    ctx.db.add_request(ctx.user_id, query)  # kino qo'shilganda avtomatik xabar berish uchun
    tid = ctx.db.create_ticket("req", ctx.user_id)
    uname = f" (@{esc(ctx.user['username'])})" if ctx.user.get("username") else ""
    text = (f"🎬 <b>Yangi kino so'rovi</b>\n\n"
            f"🔎 <b>«{esc(query)}»</b>\n\n"
            f"👤 {user_link(ctx.user_id, ctx.user.get('first_name'))}{uname}\n🆔 <code>{ctx.user_id}</code>\n\n"
            "💡 Qo'shgach, foydalanuvchiga javob yozib kodini yuboring.")
    kb = ticket_kb(ctx.user_id, tid)
    delivered = 0
    for admin_id in app.admin_ids():
        try:
            sent = ctx.bot.send_message(admin_id, text, kb)
            ctx.db.add_ticket_msg(tid, admin_id, sent["message_id"])
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


def _vote_view(ctx: Ctx):
    from ..utils import now
    rows = ctx.db.top_requests(8, now() - REQUEST_DAYS * 86400)
    lines = ["🗳 <b>Eng ko'p so'ralgan kinolar</b>", "",
             "«Menga ham kerak» tugmasini bossangiz, kino qo'shilishi bilan bot sizga xabar beradi. "
             "Ovoz ko'p kinolar birinchi qo'shiladi 🎬", ""]
    kb = []
    if not rows:
        lines.append("Hozircha ochiq so'rov yo'q 👍 O'zingiz so'rang: /sorov")
    for i, r in enumerate(rows, 1):
        mine = ctx.db.user_requested(ctx.user_id, r["norm"])
        lines.append(f"<b>{i}.</b> {esc(r['query'][:60])} — 👥 {r['n']}" + (" ✅" if mine else ""))
        if not mine:
            kb.append([btn(f"🙋 Menga ham kerak: {r['query'][:26]}", f"rv:{zlib.crc32(r['norm'].encode()):08x}", style=SUCCESS)])
    return "\n".join(lines), ikb(*kb) if kb else None


@router.command("sorovlar", "ovoz", gate=False)
def cmd_votes(ctx: Ctx) -> None:
    ctx.send(*_vote_view(ctx))


@router.callback("rv", gate=False)
def cb_vote(ctx: Ctx) -> None:
    from ..utils import now
    key = ctx.data.split(":", 1)[1] if ":" in ctx.data else ""
    if ctx.db.is_contact_banned(ctx.user_id):
        ctx.answer("⛔️ Hozircha so'rov yuborish cheklangan", alert=True)
        return
    for r in ctx.db.top_requests(20, now() - REQUEST_DAYS * 86400):
        if f"{zlib.crc32(r['norm'].encode()):08x}" == key:
            if not ctx.db.user_requested(ctx.user_id, r["norm"]):
                ctx.db.add_request(ctx.user_id, r["query"])
            ctx.answer("✅ Ovozingiz qo'shildi!")
            ctx.edit(*_vote_view(ctx))
            return
    ctx.answer("😔 Bu so'rov allaqachon yopilgan", alert=True)
    ctx.edit(*_vote_view(ctx))


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


# ═════════════════════════ 🎉 so'ralgan kino qo'shilganda xabar berish ═════════════════════════

REQUEST_DAYS = 60   # shuncha kun ichidagi so'rovlar kuzatiladi
_STOP = {"kino", "kinosi", "film", "filmi", "multfilm", "multfilmi", "multik", "serial", "seriali", "uzbek", "ozbek",
         "ozbekcha", "tilida", "tarjima", "tarjimasi", "hd", "full", "barcha", "qismlari", "qismi", "qism", "yangi",
         "the", "uz", "ru", "rus", "tilda", "va", "bilan"}


def _need_tokens(norm: str):
    """So'rovdagi muhim so'zlar (yillar va umumiy so'zlarsiz). Raqamlar (qism raqami) muhim."""
    out = []
    for t in norm.split():
        if t in _STOP or (len(t) == 4 and t.isdigit() and t[:2] in ("19", "20")):
            continue
        if len(t) < 2 and not t.isdigit():
            continue
        out.append(t)
    return out


def notify_requesters(app, movie_id: int) -> int:
    """Yangi qo'shilgan kino nomiga mos ochiq so'rovlar egalariga xabar yuboradi. Nechta yuborilganini qaytaradi."""
    from ..keyboards import SUCCESS
    from ..utils import now
    movie = app.db.get_movie(movie_id)
    if not movie:
        return 0
    title_tokens = set(movie["norm_title"].split())
    sent_to = set()
    for r in app.db.open_requests(now() - REQUEST_DAYS * 86400):
        need = _need_tokens(r["norm"])
        if not need or not set(need) <= title_tokens:
            continue
        app.db.close_request(r["id"], movie_id)
        if r["user_id"] in sent_to:
            continue
        sent_to.add(r["user_id"])
        code = f"\n🔢 Kod: <code>{movie['code']}</code>" if movie["code"] > 0 else ""
        try:
            app.bot.send_message(
                r["user_id"],
                f"🎉 <b>Siz so'ragan kino qo'shildi!</b>\n\n🔎 So'rovingiz: «{esc(r['query'])}»\n"
                f"🎬 <b>{esc(movie['title'])}</b>{code}\n\nHoziroq tomosha qiling 🍿",
                ikb([btn("▶️ Ko'rish", f"mv:{movie_id}", style=SUCCESS)]))
        except Forbidden:
            app.db.set_blocked(r["user_id"], True)
        except TelegramError as exc:
            log.warning("So'rov egasiga xabar yetmadi (%s): %s", r["user_id"], exc.description)
        time.sleep(0.05)
    # 🔔 /sorov bosmagan bo'lsa ham: kino topilmagan qidiruv egasiga ham xabar boradi (bir marta, har qidiruv uchun)
    for r in app.db.failed_searches(now() - REQUEST_DAYS * 86400):
        need = _need_tokens(r["norm"])
        if not need or not set(need) <= title_tokens:
            continue
        app.db.mark_searches_notified(r["user_id"], r["norm"])
        u = app.db.get_user(r["user_id"])
        if r["user_id"] in sent_to or not u or u["is_blocked"]:
            continue
        sent_to.add(r["user_id"])
        code = f"\n🔢 Kod: <code>{movie['code']}</code>" if movie["code"] > 0 else ""
        try:
            app.bot.send_message(
                r["user_id"],
                f"🔔 <b>Qidirgan kinongiz qo'shildi!</b>\n\n🔎 Siz qidirgan: «{esc(r['query'])}»\n"
                f"🎬 <b>{esc(movie['title'])}</b>{code}\n\nHoziroq tomosha qiling 🍿",
                ikb([btn("▶️ Ko'rish", f"mv:{movie_id}", style=SUCCESS)]))
        except Forbidden:
            app.db.set_blocked(r["user_id"], True)
        except TelegramError as exc:
            log.warning("Qidiruv egasiga xabar yetmadi (%s): %s", r["user_id"], exc.description)
        time.sleep(0.05)
    return len(sent_to)
