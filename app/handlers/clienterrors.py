"""🛠 /xatolar — saytda foydalanuvchilarda chiqqan so'nggi JavaScript xatolari (kamida bir marta xabar berilganlar)."""

from __future__ import annotations

import html

from ..core import Ctx, router


@router.command("xatolar", owner=True)
def cmd_errors(ctx: Ctx) -> None:
    from .. import webapp
    rows = sorted(webapp._CLIENT_ERRS.values(), key=lambda r: -r[0])[:10]
    if not rows:
        ctx.send("✅ Bot ishga tushganidan beri saytda xatolik qayd etilmagan.")
        return
    lines = ["🛠 <b>Saytdagi xatolar</b> (eng ko'p takrorlanganlari)", ""]
    for cnt, _first, _last, msg, dev in rows:
        lines.append(f"• <b>{cnt}×</b> <code>{html.escape(msg[:90])}</code>\n   📱 {html.escape(dev)}")
    lines += ["", "Ro'yxat bot qayta ishga tushganda tozalanadi."]
    ctx.send("\n".join(lines))
