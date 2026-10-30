"""🎟 Promokodlar: admin hosil qiladi (1, 3, 5, 30 kun), foydalanuvchi kiritib Premium oladi."""

from __future__ import annotations

import logging
import time

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..utils import esc, fmt_datetime, plan_name

log = logging.getLogger("promo")

PROMO_DAYS = (1, 3, 5, 30)
MAX_FAILS = 5            # xato urinishlar chegarasi
FAIL_WINDOW = 600        # shu soniya ichida
_fails: dict = {}


def _too_many(uid: int) -> bool:
    t = time.time()
    arr = [x for x in _fails.get(uid, []) if t - x < FAIL_WINDOW]
    _fails[uid] = arr
    return len(arr) >= MAX_FAILS


def redeem(ctx: Ctx, code: str) -> None:
    """Promokodni tekshirib, Premium beradi."""
    if _too_many(ctx.user_id):
        ctx.send("⏳ Juda ko'p xato urinish. 10 daqiqadan so'ng qayta urinib ko'ring.")
        return
    days = ctx.db.redeem_promo(code, ctx.user_id)
    if not days:
        _fails.setdefault(ctx.user_id, []).append(time.time())
        ctx.send("❌ <b>Promokod topilmadi yoki ishlatilgan.</b>\n\nKodni tekshirib, qayta yuboring.",
                 ikb([btn("🎟 Qayta kiritish", "promo:ask", style=PRIMARY)]))
        return
    until = ctx.db.grant_premium(ctx.user_id, days)
    ctx.db.create_payment(ctx.user_id, "premium", "promo", "approved", days=days, amount=0, currency="UZS",
                          note=f"Promokod {code.strip().upper()}")
    ctx.clear_state()
    ctx.send(f"🎉 <b>Promokod qabul qilindi!</b>\n\n💎 Sizga <b>{plan_name(days)}</b> Premium berildi.\n"
             f"⏳ Amal qiladi: <b>{fmt_datetime(until)}</b> gacha.\n\nYoqimli tomosha! 🍿")


@router.command("promo", gate=False)
def cmd_promo(ctx: Ctx) -> None:
    if ctx.args.strip():
        redeem(ctx, ctx.args)
        return
    ctx.set_state("promo:in", ttl=600)
    ctx.send("🎟 <b>Promokod</b>\n\nPromokodni yuboring (masalan: <code>MM-AB12CD</code>):", cancel_kb())


@router.state("promo:in")
def st_promo(ctx: Ctx) -> None:
    redeem(ctx, ctx.text)


@router.callback("promo")
def cb_promo(ctx: Ctx) -> None:
    action = ctx.data.split(":")[1] if ":" in ctx.data else ""
    ctx.answer()
    if action == "ask":
        ctx.set_state("promo:in", ttl=600)
        ctx.send("🎟 <b>Promokod</b>\n\nPromokodni yuboring (masalan: <code>MM-AB12CD</code>):", cancel_kb())
    elif action == "inv":
        from .user import send_invite
        send_invite(ctx)


# ═════════════════════════ 👮 Admin ═════════════════════════

def promo_admin_view(ctx: Ctx):
    stats = ctx.db.promo_stats()
    lines = ["🎟 <b>Promokodlar</b>", "",
             "Muddatni tanlang — bot yangi promokod hosil qiladi. Har bir kod <b>bir marta</b> ishlaydi.", ""]
    for d in PROMO_DAYS:
        st = stats.get(d, {"free": 0, "used": 0})
        lines.append(f"• <b>{plan_name(d)}</b>: bo'sh {st['free']} • ishlatilgan {st['used']}")
    rows = [[btn(f"➕ {plan_name(d)}", f"pc:new:{d}:1", style=SUCCESS),
             btn("×5", f"pc:new:{d}:5", style=SUCCESS),
             btn("📋", f"pc:list:{d}", style=PRIMARY)] for d in PROMO_DAYS]
    rows.append([btn("⬅️ Orqaga", "pa:menu", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


@router.callback("pc", admin=True)
def cb_promo_admin(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"
    if action == "menu":
        ctx.answer()
        text, kb = promo_admin_view(ctx)
        ctx.edit(text, kb)
    elif action == "new" and len(parts) > 3 and parts[2].isdigit() and parts[3].isdigit():
        days, count = int(parts[2]), min(int(parts[3]), 20)
        if days not in PROMO_DAYS:
            ctx.answer("⚠️", alert=True)
            return
        codes = ctx.db.create_promos(days, count, ctx.user_id)
        ctx.answer("✅ Tayyor")
        ctx.send(f"🎟 <b>{plan_name(days)}</b> promokod{'lar' if count > 1 else ''}:\n\n"
                 + "\n".join(f"<code>{c}</code>" for c in codes)
                 + "\n\n👆 Bosib nusxalang. Foydalanuvchi botda <code>/promo KOD</code> yuboradi "
                   "yoki 💎 Premium bo'limidagi «🎟 Promokod» tugmasini bosadi.")
        text, kb = promo_admin_view(ctx)
        ctx.edit(text, kb)
    elif action == "list" and len(parts) > 2 and parts[2].isdigit():
        rows = ctx.db.free_promos(int(parts[2]))
        ctx.answer()
        if not rows:
            ctx.send("ℹ️ Bu muddat uchun bo'sh promokod yo'q.")
        else:
            ctx.send(f"📋 <b>Bo'sh promokodlar — {plan_name(int(parts[2]))}</b>\n\n"
                     + "\n".join(f"<code>{r['code']}</code>" for r in rows))
