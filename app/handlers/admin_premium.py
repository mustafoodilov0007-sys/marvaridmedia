"""Admin: 💎 Premiumlar — tariflar, premium berish/olish, ro'yxat va sozlamalar."""

from __future__ import annotations

import logging
import math
import re

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb, nav_row
from ..telegram import TelegramError
from ..texts import B
from ..utils import esc, fmt_date, fmt_datetime, fmt_num, plan_name

log = logging.getLogger("admin.premium")

TOGGLES = ("premium_enabled", "premium_skip_sub", "premium_card", "premium_stars", "donate_stars")
PER_PAGE = 20


def _on(ctx: Ctx, key: str) -> str:
    return "✅" if ctx.app.setting_bool(key) else "❌"


def _toggle(ctx: Ctx, label: str, key: str) -> dict:
    """Yoqilgan — yashil, o'chirilgan — qizil."""
    on = ctx.app.setting_bool(key)
    return btn(f"{label}: {'✅' if on else '❌'}", f"pa:tog:{key}", style=SUCCESS if on else DANGER)


def premium_admin_view(ctx: Ctx):
    db = ctx.db
    totals = db.payment_totals()
    card = totals.get("premium:card", {"n": 0, "total": 0})
    stars = totals.get("premium:stars", {"n": 0, "total": 0})
    skip = ctx.app.setting_bool("premium_skip_sub")
    text = ("💎 <b>Premium boshqaruvi</b>\n\n"
            f"👥 Faol premiumlar: <b>{fmt_num(db.count_premium())}</b>\n"
            f"⏳ Tekshirilmagan cheklar: <b>{fmt_num(db.count_pending())}</b>\n"
            f"💳 Karta orqali tushum: <b>{fmt_num(card['total'])} so'm</b> ({card['n']} ta)\n"
            f"⭐ Stars orqali tushum: <b>{fmt_num(stars['total'])} ⭐</b> ({stars['n']} ta)\n\n"
            f"⚙️ Premium tizimi: {_on(ctx, 'premium_enabled')}\n"
            f"💳 Karta orqali sotuv: {_on(ctx, 'premium_card')}\n"
            f"⭐ Stars orqali sotuv: {_on(ctx, 'premium_stars')}\n"
            f"🚪 Premiumlarga majburiy obuna: {'❌ talab qilinmaydi' if skip else '✅ talab qilinadi'}\n"
            f"💝 Stars orqali donat: {_on(ctx, 'donate_stars')}")
    rows = [
        [btn("📋 Tariflar", "pa:plans", style=PRIMARY), btn("👥 Premiumlar", "pa:list:0", style=PRIMARY)],
        [btn("🎁 Premium berish", "pa:give", style=SUCCESS), btn("🚫 Premiumni olish", "pa:take", style=DANGER)],
        [_toggle(ctx, "⚙️ Tizim", "premium_enabled"), _toggle(ctx, "🚪 Obunasiz kirish", "premium_skip_sub")],
        [_toggle(ctx, "💳 Karta", "premium_card"), _toggle(ctx, "⭐ Stars", "premium_stars")],
        [_toggle(ctx, "💝 Stars donat", "donate_stars")],
    ]
    return text, ikb(*rows)


def plans_view(ctx: Ctx):
    plans = ctx.db.list_plans()
    lines = ["📋 <b>Premium tariflari</b>", ""]
    rows = [[btn("➕ Tarif qo'shish", "pa:padd", style=SUCCESS)]]
    if not plans:
        lines.append("— hozircha tarif yo'q")
    for i, p in enumerate(plans, 1):
        lines.append(f"{i}. 💎 <b>{plan_name(p['days'])}</b> ({p['days']} kun) — "
                     f"💳 {fmt_num(p['price'])} so'm • ⭐ {p['stars']}")
        rows.append([btn(f"🗑 {i}. {plan_name(p['days'])} — o'chirish", f"pa:pdel:{p['id']}", style=DANGER)])
    lines += ["", "ℹ️ Narx 0 bo'lsa, o'sha usulda sotilmaydi."]
    rows.append([btn("⬅️ Orqaga", "pa:menu", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


def premium_list_view(ctx: Ctx, page: int):
    db = ctx.db
    total = db.count_premium()
    pages = max(1, math.ceil(total / PER_PAGE))
    page %= pages
    lines = [f"👥 <b>Faol premiumlar:</b> {fmt_num(total)} ta", ""]
    for i, u in enumerate(db.list_premium(PER_PAGE, page * PER_PAGE), page * PER_PAGE + 1):
        uname = f" @{esc(u['username'])}" if u["username"] else ""
        lines.append(f"{i}. {esc(u['first_name'] or '—')}{uname} — <code>{u['user_id']}</code>\n"
                     f"     📅 {fmt_date(u['premium_until'])} gacha")
    if not total:
        lines.append("— hozircha premium foydalanuvchilar yo'q")
    rows = []
    if pages > 1:
        rows.append(nav_row("pa:list", page, pages))
    rows.append([btn("⬅️ Orqaga", "pa:menu", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


@router.button(B.PREMIUMS, admin=True)
def btn_premiums(ctx: Ctx) -> None:
    text, kb = premium_admin_view(ctx)
    ctx.send(text, kb)


@router.callback("pa", admin=True)
def cb_premium_admin(ctx: Ctx) -> None:
    app, db = ctx.app, ctx.db
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"
    arg = parts[2] if len(parts) > 2 else ""
    if action == "menu":
        ctx.answer()
        text, kb = premium_admin_view(ctx)
        ctx.edit(text, kb)
    elif action == "tog" and arg in TOGGLES:
        app.set_setting(arg, "0" if app.setting_bool(arg) else "1")
        ctx.answer("✅ Saqlandi")
        text, kb = premium_admin_view(ctx)
        ctx.edit(text, kb)
    elif action == "plans":
        ctx.answer()
        text, kb = plans_view(ctx)
        ctx.edit(text, kb)
    elif action == "pdel" and arg.isdigit():
        db.deactivate_plan(int(arg))
        ctx.answer("🗑 Tarif o'chirildi")
        text, kb = plans_view(ctx)
        ctx.edit(text, kb)
    elif action == "padd":
        ctx.answer()
        ctx.set_state("pa:padd")
        ctx.send("➕ <b>Yangi tarif</b>\n\n"
                 "Uchta sonni probel bilan yuboring: <code>kun narx(so'm) stars</code>\n\n"
                 "💡 Masalan: <code>30 10000 50</code> — 1 oy, 10 000 so'm yoki 50 ⭐\n"
                 "Stars bilan sotmaslik uchun oxirgi sonni 0 qiling.", cancel_kb())
    elif action == "list":
        ctx.answer()
        text, kb = premium_list_view(ctx, int(arg) if arg.isdigit() else 0)
        ctx.edit(text, kb)
    elif action == "give":
        ctx.answer()
        ctx.set_state("pa:give")
        ctx.send("🎁 <b>Premium berish</b>\n\n"
                 "Foydalanuvchi ID raqami va kunlar sonini yuboring:\n"
                 "<code>123456789 30</code>", cancel_kb())
    elif action == "take":
        ctx.answer()
        ctx.set_state("pa:take")
        ctx.send("🚫 <b>Premiumni olish</b>\n\nFoydalanuvchi ID raqamini yuboring:", cancel_kb())


@router.state("pa:padd", admin=True)
def st_add_plan(ctx: Ctx) -> None:
    nums = re.findall(r"\d+", ctx.text.replace(" 000", "000"))
    if len(nums) != 3:
        ctx.send("❗️ Format: <code>kun narx stars</code>, masalan: <code>30 10000 50</code>", cancel_kb())
        return
    days, price, stars = (int(n) for n in nums)
    if not 1 <= days <= 3650 or (price == 0 and stars == 0) or stars > 10000:
        ctx.send("❗️ Kun 1–3650 oralig'ida, narx yoki stars 0 dan katta bo'lishi kerak (stars ≤ 10000).",
                 cancel_kb())
        return
    ctx.db.add_plan(days, price, stars)
    ctx.clear_state()
    ctx.send(f"✅ Tarif qo'shildi: 💎 <b>{plan_name(days)}</b> — {fmt_num(price)} so'm • {stars} ⭐")
    text, kb = plans_view(ctx)
    ctx.send(text, kb)


@router.state("pa:give", admin=True)
def st_give(ctx: Ctx) -> None:
    nums = re.findall(r"\d+", ctx.text)
    if len(nums) != 2 or not 1 <= int(nums[1]) <= 3650:
        ctx.send("❗️ Format: <code>ID kun</code>, masalan: <code>123456789 30</code>", cancel_kb())
        return
    uid, days = int(nums[0]), int(nums[1])
    until = ctx.db.grant_premium(uid, days)
    ctx.db.create_payment(uid, "premium", "gift", "approved", days=days, amount=0, currency="UZS",
                          note=f"Admin {ctx.user_id} sovg'asi")
    ctx.clear_state()
    try:
        ctx.bot.send_message(uid, f"🎁 <b>Sizga {days} kunlik Premium sovg'a qilindi!</b>\n\n"
                                  f"💎 Amal qiladi: <b>{fmt_datetime(until)}</b> gacha.\n"
                                  "Yoqimli tomosha! 🍿")
        note = ""
    except TelegramError:
        note = "\nℹ️ Foydalanuvchiga xabar yetkazilmadi (u botni ishga tushirmagan bo'lishi mumkin)."
    ctx.send(f"✅ <code>{uid}</code> ga {days} kunlik Premium berildi — {fmt_datetime(until)} gacha.{note}")


@router.state("pa:take", admin=True)
def st_take(ctx: Ctx) -> None:
    nums = re.findall(r"\d+", ctx.text)
    if len(nums) != 1:
        ctx.send("❗️ Faqat ID raqamni yuboring, masalan: <code>123456789</code>", cancel_kb())
        return
    uid = int(nums[0])
    ctx.clear_state()
    if ctx.db.revoke_premium(uid):
        ctx.send(f"✅ <code>{uid}</code> dan Premium olib tashlandi.")
    else:
        ctx.send("ℹ️ Bu foydalanuvchida faol Premium yo'q.")
