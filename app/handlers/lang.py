"""🌐 /til — bot tilini tanlash (o'zbek / ruscha / inglizcha)."""

from __future__ import annotations

from ..core import Ctx, router
from ..i18n_bot import LANGS
from ..keyboards import PRIMARY, SUCCESS, btn, ikb


def _kb(cur: str):
    cur = cur or "uz"
    return ikb(*[[btn(("✅ " if k == cur else "") + name, f"lg:{k}", style=SUCCESS if k == cur else PRIMARY)] for k, name in LANGS.items()])


@router.command("til", "lang", "language", gate=False)
def cmd_lang(ctx: Ctx) -> None:
    # sarlavha uch tilda ko'rsatiladi — foydalanuvchi o'z tilini topsin
    ctx.bot.send_message(ctx.chat_id, "🌐 <b>Til / Язык / Language</b>", reply_markup=_kb(ctx.lang))


@router.callback("lg", gate=False)
def cb_lang(ctx: Ctx) -> None:
    code = ctx.data.split(":", 1)[1] if ":" in ctx.data else "uz"
    if code not in LANGS:
        ctx.answer()
        return
    ctx.app.set_user_lang(ctx.user_id, "" if code == "uz" else code)
    ctx.answer("✅")
    from .user import send_welcome
    ctx.edit("✅ Til o'zgartirildi.")
    send_welcome(ctx)          # yangi tildagi menyu va salom
