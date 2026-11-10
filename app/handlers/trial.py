"""🎁 Premium sinov muddati: yangi foydalanuvchi birinchi /start da bir marta bepul Premium oladi. Admin: /sinov."""

from __future__ import annotations

import logging

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..utils import now

log = logging.getLogger("trial")

DEFAULT_DAYS = 0          # standart: o‘chiq — egasi /sinov orqali yoqadi (sinov paytida majburiy obuna o‘tkazib yuboriladi)


def trial_days(app) -> int:
    raw = app.setting("trial_days")
    if raw == "":
        return DEFAULT_DAYS
    try:
        return max(0, min(30, int(raw)))
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
    if not ctx.db.take_trial(ctx.user_id, _since(app)):
        return False
    ctx.db.grant_premium(ctx.user_id, days)
    ctx.send(f"🎁 <b>Sovg'a!</b> Sizga <b>{days} kunlik bepul Premium</b> berildi.\n\n"
             "💎 Majburiy obunasiz, maxsus kinolar bilan tomosha qiling. Yoqsa, /premium orqali uzaytirasiz.")
    log.info("Sinov Premium berildi: %s (%s kun)", ctx.user_id, days)
    return True


def _view(app):
    d = trial_days(app)
    text = ("🎁 <b>Premium sinov muddati</b>\n\n"
            f"Hozir: <b>{'o‘chiq' if d == 0 else f'{d} kun'}</b>\n\n"
            "Yangi foydalanuvchi birinchi /start da bir marta shuncha kun bepul Premium oladi "
            "(eski foydalanuvchilarga berilmaydi). Premium'ni sinab ko'rgan odam keyin to'lashi ehtimoli yuqori.\n\n"
            "⚠️ Sinov davomida foydalanuvchi majburiy kanallarga obuna bo'lmasdan foydalanadi (Premium shunday ishlaydi).")
    rows = [[btn(("✅ " if d == n else "") + (f"{n} kun" if n else "O'chirish"), f"tr:set:{n}", style=SUCCESS if d == n else PRIMARY)
             for n in (0, 1, 3, 7)]]
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
    else:
        ctx.answer()
