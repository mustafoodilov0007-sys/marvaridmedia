"""🔐 Saytga Telegram orqali kirish: sayt bir martalik havola beradi, foydalanuvchi botda «Ha, men» ni bosadi."""

from __future__ import annotations

from ..core import Ctx, router
from ..keyboards import DANGER, SUCCESS, btn, ikb
from ..utils import esc


def ask_confirm(ctx: Ctx, token: str) -> None:
    row = ctx.db.get_login_token(token) if token else None
    if not row or row["status"] != "pending":
        ctx.send("⏳ <b>Kirish havolasi eskirgan.</b>\n\nSaytga qaytib, «Telegram orqali kirish» tugmasini qaytadan bosing.")
        return
    ctx.send("🔐 <b>Saytga kirish</b>\n\n"
             f"<b>{esc(ctx.app.brand)}</b> saytiga <b>{esc(ctx.user.get('first_name') or 'sizning')}</b> hisobingiz bilan kirilmoqda.\n\n"
             "Bu siz bo'lsangiz — «✅ Ha, men» ni bosing.\n"
             "⚠️ Agar siz so'ramagan bo'lsangiz, <b>bosmang</b> — «❌ Yo'q» ni tanlang.",
             ikb([btn("✅ Ha, men", f"wl:ok:{token}", style=SUCCESS)], [btn("❌ Yo'q", f"wl:no:{token}", style=DANGER)]))


@router.callback("wl", gate=False)
def cb_weblogin(ctx: Ctx) -> None:
    parts = ctx.data.split(":", 2)
    if len(parts) < 3:
        return
    action, token = parts[1], parts[2]
    if action == "ok":
        if ctx.db.bind_login_token(token, ctx.user_id, ctx.user.get("first_name") or "Foydalanuvchi"):
            ctx.answer("✅ Tasdiqlandi")
            ctx.edit("✅ <b>Tasdiqlandi!</b>\n\nBrauzerga (saytga) qayting — kirish avtomatik bajariladi.")
        else:
            ctx.answer("⏳ Havola eskirgan. Saytda qaytadan urinib ko'ring.", alert=True)
    else:
        ctx.db.drop_login_token(token)
        ctx.answer("Bekor qilindi")
        ctx.edit("❌ Kirish bekor qilindi.")
