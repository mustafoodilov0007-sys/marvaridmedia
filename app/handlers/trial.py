"""🎁 Premium sinov muddati: yangi foydalanuvchi birinchi /start da bir marta bepul Premium oladi. Admin: /sinov."""

from __future__ import annotations

import logging

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..utils import now

log = logging.getLogger("trial")

DEFAULT_DAYS = 1          # standart: 1 kun hammaga bepul Premium (Marvarid TV uchun); egasi /sinov orqali o‘zgartiradi yoki o‘chiradi


def trial_days(app) -> int:
    raw = app.setting("trial_days")
    if raw == "":
        return DEFAULT_DAYS
    try:
        return max(0, min(90, int(raw)))
    except ValueError:
        return 0


def _since(app) -> int:
    """Funksiya yoqilgan vaqt — undan oldin qo'shilgan foydalanuvchilar sinovga ega emas."""
    raw = app.setting("trial_since")
    if raw.isdigit():
        return int(raw)
    t = now()
    app.set_setting("trial_since", str(t))
    return t


def maybe_gift(ctx: Ctx) -> bool:
    """/start paytida chaqiriladi. Sovg'a berilsa True."""
    app = ctx.app
    days = trial_days(app)
    if days <= 0 or not app.setting_bool("premium_enabled") or ctx.is_admin:
        return False
    if not ctx.db.take_trial(ctx.user_id, 0):          # hali olmagan har bir foydalanuvchi (eski ham, yangi ham)
        return False
    ctx.db.grant_premium(ctx.user_id, days)
    ctx.send(f"🎁 <b>Sovg'a!</b> Sizga <b>{days} kunlik bepul Premium</b> berildi.\n\n"
             "💎 Majburiy obunasiz, maxsus kinolar bilan tomosha qiling. Yoqsa, /premium orqali uzaytirasiz.")
    log.info("Sinov Premium berildi: %s (%s kun)", ctx.user_id, days)
    return True


LABELS = {0: "O'chirish", 1: "1 kun", 3: "3 kun", 30: "1 oy"}


def _view(app):
    d = trial_days(app)
    shown = "o‘chiq" if d == 0 else (f"{d} kun" + (" (1 oy)" if d == 30 else ""))
    text = ("🎁 <b>Premium sinov muddati</b>\n\n"
            f"Hozir: <b>{shown}</b>\n\n"
            "Hali olmagan har bir foydalanuvchi /start da (yoki saytda «Marvarid TV» ni ochganda) bir marta shuncha vaqt bepul Premium oladi. "
            "Muddatni o'zingiz tanlaysiz.\n\n"
            "⚠️ Sinov davomida foydalanuvchi majburiy kanallarga obuna bo'lmasdan foydalanadi (Premium shunday ishlaydi).")
    rows = [[btn(("✅ " if d == n else "") + LABELS[n], f"tr:set:{n}", style=SUCCESS if d == n else PRIMARY) for n in (0, 1, 3, 30)],
            [btn("✏️ Boshqa muddat (kun)", "tr:custom", style=PRIMARY)]]
    return text, ikb(*rows)


@router.command("sinov", owner=True)
def cmd_trial(ctx: Ctx) -> None:
    ctx.send(*_view(ctx.app))


@router.callback("tr", owner=True)
def cb_trial(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    if len(parts) > 2 and parts[1] == "set" and parts[2].isdigit():
        n = int(parts[2])
        ctx.app.set_setting("trial_days", str(n))
        if n:
            _since(ctx.app)
        ctx.answer("✅ Saqlandi")
        ctx.edit(*_view(ctx.app))
    elif len(parts) > 1 and parts[1] == "custom":
        ctx.answer()
        ctx.set_state("tr:in")
        ctx.send("✏️ Sinov muddatini <b>kun</b> bilan yuboring (1 dan 90 gacha), masalan <code>14</code>.",
                 ikb([btn("❌ Bekor qilish", "cancel", style=DANGER)]))
    else:
        ctx.answer()


@router.state("tr:in", admin=True)
def st_trial_days(ctx: Ctx) -> None:
    if not ctx.is_owner:
        ctx.clear_state()
        return
    text = ctx.text.strip()
    if not text.isdigit() or not 1 <= int(text) <= 90:
        ctx.send("❗️ 1 dan 90 gacha kun sonini yuboring.")
        return
    ctx.app.set_setting("trial_days", text)
    _since(ctx.app)
    ctx.clear_state()
    ctx.send("✅ Saqlandi.")
    ctx.send(*_view(ctx.app))
