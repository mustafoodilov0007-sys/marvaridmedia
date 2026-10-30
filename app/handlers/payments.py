"""Donat va Premium: karta (chek orqali), Telegram Stars, tasdiqlash va muddat nazorati."""

from __future__ import annotations

import logging
import math

from ..core import NEXT, App, Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb, user_menu
from ..telegram import Forbidden, TelegramError
from ..texts import B, PAYSUPPORT_TEXT, TERMS_TEXT
from ..utils import (esc, fmt_card, fmt_datetime, fmt_num, now, plan_name, render, truncate,
                     user_link)

log = logging.getLogger("payments")

STAR_AMOUNTS = (10, 50, 100, 250, 500)
RECEIPT_TTL = 1800  # chek kutish holati 30 daqiqa amal qiladi


# ═════════════════════════ yordamchilar ═════════════════════════

def card_info(app: App):
    digits = app.setting("card_number")
    return digits, fmt_card(digits), esc(app.setting("card_holder") or "—")


def methods(app: App):
    return app.setting_bool("premium_card"), app.setting_bool("premium_stars")


def plan_label(app: App, plan) -> str:
    card_on, stars_on = methods(app)
    prices = []
    if card_on and plan["price"] > 0:
        prices.append(f"{fmt_num(plan['price'])} so'm")
    if stars_on and plan["stars"] > 0:
        prices.append(f"{plan['stars']} ⭐")
    name = plan_name(plan["days"])
    return f"💎 {name} — {' • '.join(prices)}" if prices else f"💎 {name}"


def premium_status_line(app: App, uid: int) -> str:
    until = app.db.premium_until(uid)
    t = now()
    if until > t:
        days_left = math.ceil((until - t) / 86400)
        return (f"✅ <b>Sizda Premium faol!</b>\n📅 Amal qiladi: <b>{fmt_datetime(until)}</b> gacha\n"
                f"⏳ Qolgan: <b>{days_left} kun</b>\n\n♻️ Muddatni uzaytirish uchun tarif tanlang 👇")
    return "🆓 Hozircha sizda oddiy obuna.\n\n👇 Premium tarifini tanlang:"


# ═════════════════════════ 💝 Donat ═════════════════════════

def donate_view(app: App):
    digits, card, holder = card_info(app)
    text = render(app.setting("donate_text"), card=card, holder=holder, brand=esc(app.brand),
                  bot=app.bot_username)
    rows = []
    if digits:
        rows.append([btn("📋 Karta raqamini nusxalash", copy=digits, style=SUCCESS)])
    rows.append([btn("🧾 Chek yuborish", "dn:receipt", style=PRIMARY)])
    if app.setting_bool("donate_stars"):
        rows.append([btn("⭐ Telegram Stars bilan", "dn:stars", style=DANGER)])
    if app.setting_bool("premium_enabled"):
        rows.append([btn("💎 Premium olish", "pr:menu", style=SUCCESS)])
    return text, ikb(*rows)


@router.button(B.DONATE, gate=False)
@router.command("donat", "donate", gate=False)
def btn_donate(ctx: Ctx) -> None:
    text, kb = donate_view(ctx.app)
    ctx.send(text, kb)


@router.callback("dn")
def cb_donate(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"
    if action == "menu":
        ctx.answer()
        text, kb = donate_view(app)
        ctx.edit(text, kb)
    elif action == "receipt":
        ctx.answer()
        ctx.set_state("receipt", ttl=RECEIPT_TTL, kind="donate")
        ctx.send("🧾 <b>To'lov chekini yuboring</b>\n\n"
                 "📸 Chek rasmini (skrinshot) shu yerga yuboring. Izohga summani yozib qo'yishingiz mumkin.",
                 cancel_kb())
    elif action == "stars":
        if not app.setting_bool("donate_stars"):
            ctx.answer("⭐ Stars orqali donat vaqtincha o'chirilgan", alert=True)
            return
        ctx.answer()
        amounts = [btn(f"⭐ {a}", f"dn:s:{a}", style=SUCCESS) for a in STAR_AMOUNTS]
        ctx.edit("⭐ <b>Telegram Stars bilan qo'llab-quvvatlash</b>\n\nQancha Stars yubormoqchisiz? 👇",
                 ikb(amounts[:3], amounts[3:], [btn("⬅️ Orqaga", "dn:menu", style=DANGER)]))
    elif action == "s" and len(parts) > 2 and parts[2].isdigit():
        amount = int(parts[2])
        if amount not in STAR_AMOUNTS or not app.setting_bool("donate_stars"):
            ctx.answer("⚠️ Noto'g'ri summa", alert=True)
            return
        ctx.answer()
        try:
            ctx.bot.send_invoice(ctx.chat_id, "💝 Qo'llab-quvvatlash",
                                 f"{app.brand} loyihasiga {amount} ⭐ xayriya. Katta rahmat! 💖"[:255],
                                 f"don:{amount}", [{"label": "Xayriya", "amount": amount}])
        except TelegramError as exc:
            log.error("Invoice yuborilmadi: %s", exc)
            ctx.send("⚠️ To'lov oynasini ochib bo'lmadi. Keyinroq urinib ko'ring.")


# ═════════════════════════ 💎 Premium ═════════════════════════

def premium_view(ctx: Ctx):
    app = ctx.app
    head = render(app.setting("premium_text"), brand=esc(app.brand), bot=app.bot_username,
                  name=esc(ctx.user.get("first_name") or ""))
    text = head + "\n\n" + premium_status_line(app, ctx.user_id)
    card_on, stars_on = methods(app)
    plans = [p for p in app.db.list_plans() if (card_on and p["price"] > 0) or (stars_on and p["stars"] > 0)]
    if not plans:
        text += "\n\n⚠️ Hozircha sotuvda tariflar yo'q. Keyinroq qaytib keling."
    rows = [[btn(plan_label(app, p), f"pr:plan:{p['id']}", style=SUCCESS)] for p in plans]
    rows.append([btn("🎟 Promokod", "promo:ask", style=PRIMARY), btn("🤝 Do'st taklif qilish", "promo:inv", style=PRIMARY)])
    return text, ikb(*rows)


def send_premium_menu(ctx: Ctx, edit: bool = False) -> None:
    if not ctx.app.setting_bool("premium_enabled"):
        msg = "💎 Premium tizimi hozircha faol emas."
        if ctx.callback is not None:
            ctx.answer(msg, alert=True)
        else:
            ctx.send(msg)
        return
    text, kb = premium_view(ctx)
    if edit and "text" in ctx.cb_message:
        ctx.edit(text, kb)
    else:
        ctx.send(text, kb)


@router.button(B.PREMIUM, gate=False)
@router.command("premium", gate=False)
def btn_premium(ctx: Ctx) -> None:
    send_premium_menu(ctx)


@router.callback("pr")
def cb_premium(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"
    if not app.setting_bool("premium_enabled"):
        ctx.answer("💎 Premium tizimi hozircha faol emas.", alert=True)
        return
    if action == "menu":
        if ctx.state == "receipt":
            ctx.clear_state()
        ctx.answer()
        send_premium_menu(ctx, edit=True)
        return

    plan = app.db.get_plan(int(parts[2])) if len(parts) > 2 and parts[2].isdigit() else None
    if not plan or not plan["is_active"]:
        ctx.answer("⚠️ Bu tarif endi mavjud emas.", alert=True)
        send_premium_menu(ctx, edit=True)
        return
    card_on, stars_on = methods(app)
    name = plan_name(plan["days"])

    if action == "plan":
        if ctx.state == "receipt":
            ctx.clear_state()
        ctx.answer()
        lines = [f"💎 <b>Premium — {name}</b> ({plan['days']} kun)", ""]
        rows = []
        if card_on and plan["price"] > 0:
            lines.append(f"💳 Karta orqali: <b>{fmt_num(plan['price'])} so'm</b>")
            rows.append([btn(f"💳 Karta orqali — {fmt_num(plan['price'])} so'm", f"pr:card:{plan['id']}",
                             style=PRIMARY)])
        if stars_on and plan["stars"] > 0:
            lines.append(f"⭐ Telegram Stars: <b>{plan['stars']} ⭐</b> (darhol faollashadi)")
            rows.append([btn(f"⭐ Telegram Stars — {plan['stars']} ⭐", f"pr:stars:{plan['id']}",
                             style=SUCCESS)])
        lines += ["", "To'lov usulini tanlang 👇"]
        rows.append([btn("⬅️ Orqaga", "pr:menu", style=DANGER)])
        ctx.edit("\n".join(lines), ikb(*rows))

    elif action == "card":
        if not (card_on and plan["price"] > 0):
            ctx.answer("💳 Karta orqali to'lov vaqtincha o'chirilgan.", alert=True)
            return
        digits, card, holder = card_info(app)
        ctx.answer()
        ctx.set_state("receipt", ttl=RECEIPT_TTL, kind="premium", plan_id=plan["id"])
        ctx.edit(
            f"💳 <b>Karta orqali to'lov</b> — Premium {name}\n\n"
            f"1️⃣ Quyidagi kartaga <b>{fmt_num(plan['price'])} so'm</b> o'tkazing:\n"
            f"💳 <code>{card}</code>\n👤 {holder}\n\n"
            "2️⃣ To'lov chekini (skrinshot) <b>shu chatga yuboring</b> 📸\n\n"
            "⏱ Admin chekni tekshirgach, Premium avtomatik faollashadi.\n"
            "ℹ️ To'lov qilish orqali /terms shartlariga rozilik bildirasiz.",
            ikb([btn("📋 Karta raqamini nusxalash", copy=digits, style=SUCCESS)] if digits else None,
                [btn("⬅️ Orqaga", f"pr:plan:{plan['id']}", style=DANGER)]))

    elif action == "stars":
        if not (stars_on and plan["stars"] > 0):
            ctx.answer("⭐ Stars orqali to'lov vaqtincha o'chirilgan.", alert=True)
            return
        ctx.answer()
        try:
            ctx.bot.send_invoice(
                ctx.chat_id, f"💎 Premium — {name}"[:32],
                f"{app.brand} Premium: {plan['days']} kun. Majburiy obunasiz, reklamasiz va maxsus "
                f"kinolar bilan. To'lov qilish orqali /terms shartlariga rozilik bildirasiz."[:255],
                f"prem:{plan['id']}:{ctx.user_id}", [{"label": f"Premium {name}", "amount": plan["stars"]}])
        except TelegramError as exc:
            log.error("Invoice yuborilmadi: %s", exc)
            ctx.send("⚠️ To'lov oynasini ochib bo'lmadi. Keyinroq urinib ko'ring.")


# ═════════════════════════ 🧾 Chek qabul qilish ═════════════════════════

def review_caption(app: App, p) -> str:
    u = app.db.get_user(p["user_id"])
    name = (u["first_name"] if u and u["first_name"] else None) or "Foydalanuvchi"
    uname = f" (@{esc(u['username'])})" if u and u["username"] else ""
    if p["kind"] == "premium":
        head = f"💎 <b>Premium to'lov so'rovi</b> #{p['id']}"
    else:
        head = f"💝 <b>Yangi donat</b> #{p['id']}"
    lines = [head, "", f"👤 {user_link(p['user_id'], name)}{uname}", f"🆔 <code>{p['user_id']}</code>"]
    if p["kind"] == "premium":
        lines.append(f"📦 Tarif: <b>{plan_name(p['days'])}</b> ({p['days']} kun) — "
                     f"<b>{fmt_num(p['amount'])} so'm</b>")
    if p["note"]:
        lines.append(f"💬 Izoh: {esc(truncate(p['note'], 200))}")
    lines.append(f"🕐 {fmt_datetime(p['created_at'])}")
    return "\n".join(lines)


@router.state("receipt")
def st_receipt(ctx: Ctx):
    msg = ctx.message
    if msg.get("photo"):
        file_id, ftype = msg["photo"][-1]["file_id"], "photo"
    elif msg.get("document"):
        file_id, ftype = msg["document"]["file_id"], "document"
    elif msg.get("text"):
        return NEXT  # matn yozsa — oddiy qidiruvga o'tkazamiz
    else:
        ctx.send("📸 Iltimos, to'lov chekini <b>rasm</b> (skrinshot) ko'rinishida yuboring.", cancel_kb())
        return None

    app, db = ctx.app, ctx.db
    data = ctx.sdata
    kind = data.get("kind", "donate")
    ctx.clear_state()
    if db.count_pending_user(ctx.user_id) >= 3:
        ctx.send("⏳ Sizda tekshirilayotgan cheklar bor. Iltimos, adminlar javobini kuting.")
        return None
    plan = None
    if kind == "premium":
        plan = db.get_plan(int(data.get("plan_id") or 0))
        if not plan:
            ctx.send("⚠️ Tarif topilmadi. «💎 Premium» bo'limidan qaytadan tanlang.")
            return None
    pid = db.create_payment(
        ctx.user_id, kind, "card", "pending",
        plan_id=plan["id"] if plan else None, days=plan["days"] if plan else 0,
        amount=plan["price"] if plan else 0, currency="UZS",
        receipt_id=file_id, receipt_type=ftype, note=(msg.get("caption") or "")[:300])
    payment = db.get_payment(pid)
    caption = review_caption(app, payment)
    kb = ikb([btn("✅ Tasdiqlash", f"pay:ok:{pid}", style=SUCCESS),
              btn("❌ Rad etish", f"pay:no:{pid}", style=DANGER)])
    delivered = 0
    for admin_id in app.admin_ids():
        try:
            if ftype == "photo":
                m = ctx.bot.send_photo(admin_id, file_id, caption, kb)
            else:
                m = ctx.bot.send_document(admin_id, file_id, caption=caption, reply_markup=kb)
            db.add_payment_msg(pid, admin_id, m["message_id"])
            delivered += 1
        except TelegramError as exc:
            log.warning("Chek adminga yuborilmadi (%s): %s", admin_id, exc.description)
    if not delivered:
        log.error("Chek #%s hech bir adminga yetkazilmadi", pid)
    ctx.send("✅ <b>Chekingiz qabul qilindi!</b>\n\n"
             "⏱ Adminlarimiz tez orada tekshirib, natijasini shu yerga yuborishadi. Rahmat! 🙏")
    return None


@router.callback("pay", admin=True)
def cb_review(ctx: Ctx) -> None:
    app, db = ctx.app, ctx.db
    try:
        _, action, pid = ctx.data.split(":")
        pid = int(pid)
    except ValueError:
        return
    p = db.get_payment(pid)
    if not p:
        ctx.answer("⚠️ So'rov topilmadi", alert=True)
        return
    approve = action == "ok"
    if not db.set_payment_status(pid, "approved" if approve else "rejected", ctx.user_id):
        ctx.answer("ℹ️ Bu so'rov allaqachon ko'rib chiqilgan.", alert=True)
        return
    admin_name = esc(ctx.user.get("first_name") or "Admin")
    user_id = p["user_id"]
    if approve and p["kind"] == "premium":
        until = db.grant_premium(user_id, p["days"])
        status = f"✅ <b>Tasdiqlandi</b> — {admin_name}\n💎 Premium {fmt_datetime(until)} gacha"
        user_text = ("🎉 <b>Tabriklaymiz! To'lovingiz tasdiqlandi.</b>\n\n"
                     f"💎 Premium faollashtirildi — <b>{fmt_datetime(until)}</b> gacha.\n\n"
                     "Endi botdan cheklovsiz foydalanishingiz mumkin 🍿")
        user_kb = user_menu(app.is_admin(user_id), True)
    elif approve:
        status = f"✅ <b>Tasdiqlandi</b> — {admin_name}"
        user_text = ("💖 <b>Donatingiz qabul qilindi!</b>\n\n"
                     f"{esc(app.brand)} jamoasi nomidan katta rahmat! Sizning yordamingiz biz uchun juda qadrli 🙏")
        user_kb = None
    else:
        status = f"❌ <b>Rad etildi</b> — {admin_name}"
        user_text = ("❌ <b>To'lovingiz tasdiqlanmadi.</b>\n\n"
                     "Chek noto'g'ri yoki to'lov topilmadi. Savollar bo'lsa «✍️ Murojaat» orqali yozing.")
        user_kb = None
    try:
        ctx.bot.send_message(user_id, user_text, user_kb)
    except Forbidden:
        db.set_blocked(user_id, True)
    except TelegramError:
        pass
    caption = review_caption(app, db.get_payment(pid)) + "\n\n" + status
    for row in db.get_payment_msgs(pid):
        ctx.bot.safe("editMessageCaption", {"chat_id": row["admin_id"], "message_id": row["message_id"],
                                            "caption": caption, "parse_mode": "HTML"})
    ctx.answer("✅ Tasdiqlandi" if approve else "❌ Rad etildi")


# ═════════════════════════ ⭐ Telegram Stars ═════════════════════════

def _check_payload(app: App, payload: str, currency: str, amount: int, uid: int):
    if currency != "XTR":
        return False, "Noto'g'ri valyuta"
    parts = payload.split(":")
    if parts[0] == "prem" and len(parts) == 3:
        if not (app.setting_bool("premium_enabled") and app.setting_bool("premium_stars")):
            return False, "Premium sotuvi vaqtincha to'xtatilgan"
        plan = app.db.get_plan(int(parts[1])) if parts[1].isdigit() else None
        if not plan or not plan["is_active"] or plan["stars"] != amount:
            return False, "Tarif o'zgargan. Iltimos, qaytadan tanlang"
        if parts[2] != str(uid):
            return False, "Bu to'lov boshqa foydalanuvchi uchun"
        return True, None
    if parts[0] == "don" and len(parts) == 2 and parts[1].isdigit():
        return (int(parts[1]) == amount and amount > 0), "Noto'g'ri summa"
    return False, "Noma'lum to'lov"


@router.on("pre_checkout")
def on_pre_checkout(ctx: Ctx) -> None:
    q = ctx.pre_checkout
    ok, error = _check_payload(ctx.app, q.get("invoice_payload", ""), q.get("currency", ""),
                               int(q.get("total_amount", 0)), ctx.user_id)
    try:
        ctx.bot.answer_pre_checkout_query(q["id"], ok, None if ok else error)
    except TelegramError as exc:
        log.error("pre_checkout javobi yuborilmadi: %s", exc)


@router.on("payment")
def on_successful_payment(ctx: Ctx) -> None:
    app, db = ctx.app, ctx.db
    sp = ctx.message["successful_payment"]
    charge = sp.get("telegram_payment_charge_id")
    if charge and db.payment_by_charge(charge):
        return
    amount = int(sp.get("total_amount", 0))
    payload = sp.get("invoice_payload", "")
    parts = payload.split(":")
    who = f"{user_link(ctx.user_id, ctx.user.get('first_name'))} (<code>{ctx.user_id}</code>)"
    if parts[0] == "prem":
        plan = db.get_plan(int(parts[1])) if len(parts) > 1 and parts[1].isdigit() else None
        days = plan["days"] if plan else 30
        until = db.grant_premium(ctx.user_id, days)
        db.create_payment(ctx.user_id, "premium", "stars", "approved", plan_id=plan["id"] if plan else None,
                          days=days, amount=amount, currency="XTR", charge_id=charge)
        ctx.send("🎉 <b>To'lov qabul qilindi!</b>\n\n"
                 f"💎 Premium faollashtirildi — <b>{fmt_datetime(until)}</b> gacha.\n\n"
                 "Endi botdan cheklovsiz foydalanishingiz mumkin 🍿",
                 user_menu(ctx.is_admin, True))
        app.notify_admins(f"⭐ <b>Yangi Stars to'lov!</b>\n\n👤 {who}\n💎 Premium {plan_name(days)} — "
                          f"<b>{amount} ⭐</b>\n🧾 <code>{esc(charge)}</code>")
    else:
        db.create_payment(ctx.user_id, "donate", "stars", "approved", amount=amount, currency="XTR",
                          charge_id=charge)
        ctx.send(f"💖 <b>Katta rahmat!</b>\n\n{amount} ⭐ xayriyangiz qabul qilindi. "
                 f"{esc(app.brand)} jamoasi sizdan minnatdor! 🙏")
        app.notify_admins(f"⭐ <b>Yangi Stars donat!</b>\n\n👤 {who}\n💝 <b>{amount} ⭐</b>\n"
                          f"🧾 <code>{esc(charge)}</code>")


@router.command("terms", gate=False)
def cmd_terms(ctx: Ctx) -> None:
    ctx.send(TERMS_TEXT)


@router.command("paysupport", gate=False)
def cmd_paysupport(ctx: Ctx) -> None:
    ctx.send(PAYSUPPORT_TEXT, ikb([btn("✍️ Murojaat yozish", "ct:start", style=PRIMARY)]))


@router.command("refund", owner=True)
def cmd_refund(ctx: Ctx) -> None:
    """/refund <to'lov ID> — Stars to'lovini qaytarish (faqat bosh adminlar)."""
    charge = ctx.args.strip()
    if not charge:
        ctx.send("ℹ️ Foydalanish: <code>/refund TO'LOV_ID</code>\n\nTo'lov ID si Stars to'lov xabarida ko'rsatiladi.")
        return
    p = ctx.db.payment_by_charge(charge)
    if not p or p["method"] != "stars":
        ctx.send("❌ Bunday Stars to'lov topilmadi.")
        return
    if p["status"] == "refunded":
        ctx.send("ℹ️ Bu to'lov allaqachon qaytarilgan.")
        return
    try:
        ctx.bot.refund_star_payment(p["user_id"], charge)
    except TelegramError as exc:
        ctx.send(f"❌ Qaytarib bo'lmadi: {esc(exc.description)}")
        return
    ctx.db.set_payment_status(p["id"], "refunded", ctx.user_id, expected=p["status"])
    if p["kind"] == "premium" and p["days"]:
        ctx.db.subtract_premium(p["user_id"], p["days"])
    ctx.bot.safe("sendMessage", {"chat_id": p["user_id"], "parse_mode": "HTML",
                                 "text": f"↩️ <b>To'lovingiz qaytarildi:</b> {p['amount']} ⭐"})
    ctx.send(f"✅ {p['amount']} ⭐ foydalanuvchiga qaytarildi.")


# ═════════════════════════ ⏳ Premium muddati nazorati ═════════════════════════

def check_premiums(app: App) -> None:
    renew = ikb([btn("💎 Premiumni uzaytirish", "pr:menu", style=SUCCESS)])
    for u in app.db.premium_due_reminders():
        try:
            app.bot.send_message(u["user_id"], "⏳ <b>Premium muddatingiz tugashiga oz qoldi!</b>\n\n"
                                 f"📅 Tugash vaqti: <b>{fmt_datetime(u['premium_until'])}</b>\n\n"
                                 "Imtiyozlardan uzluksiz foydalanish uchun obunani uzaytiring 👇", renew)
        except Forbidden:
            app.db.set_blocked(u["user_id"], True)
        except TelegramError:
            pass
        app.db.set_premium_notified(u["user_id"], 1)
    for u in app.db.premium_expired_unnotified():
        try:
            app.bot.send_message(u["user_id"], "⌛️ <b>Premium muddatingiz tugadi.</b>\n\n"
                                 "Siz yana oddiy rejimdasiz. Premium imtiyozlarini qaytarish uchun obunani "
                                 "yangilang 👇", ikb([btn("💎 Premiumni yangilash", "pr:menu", style=SUCCESS)]))
        except Forbidden:
            app.db.set_blocked(u["user_id"], True)
        except TelegramError:
            pass
        app.db.set_premium_notified(u["user_id"], 2)


@router.task
def premium_watcher(app: App) -> None:
    if app.stopping.wait(20):
        return
    last_prune = 0.0
    while True:
        if app.setting_bool("premium_enabled"):
            check_premiums(app)
        t = now()
        if t - last_prune > 86400:
            app.db.prune_searches(t - 90 * 86400)
            last_prune = t
        if app.stopping.wait(600):
            return
