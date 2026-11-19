"""📈 /tahlil — asosiy ko'rsatkichlar qisqacha (to'liq grafiklar saytdagi «Statistika → Tahlil» da)."""

from __future__ import annotations

from datetime import datetime

from .. import analytics
from ..core import Ctx, router
from ..keyboards import PRIMARY, btn, ikb
from ..utils import TZ, fmt_num


def _p(v) -> str:
    return "—" if v is None else f"{v:g}%"


def summary(ctx: Ctx) -> str:
    d = analytics.build(ctx.db)
    a, r = d["active"], d["retention"]
    lines = ["📈 <b>Tahlil</b> (Toshkent vaqti)", "",
             f"👥 Faol: bugun <b>{fmt_num(a['dau'])}</b> • hafta <b>{fmt_num(a['wau'])}</b> • oy <b>{fmt_num(a['mau'])}</b>"
             f" (jami {fmt_num(a['total'])}, yopishtirish {_p(a['stickiness'])})",
             f"🔁 Qaytish (30 kunlik): 1 kunda <b>{_p(r['d1'])}</b> • 7 kunda <b>{_p(r['d7'])}</b> • 30 kunda <b>{_p(r['d30'])}</b>", ""]
    lines.append(f"🧭 <b>Qayerdan kelishdi</b> (30 kun, {fmt_num(d['new_total'])} ta):")
    for s in d["sources"][:6]:
        lines.append(f"   • {s['label']}: <b>{fmt_num(s['n'])}</b> ({_p(s['pct'])})")
    lines += ["", "🪜 <b>Voronka</b> (30 kunda qo'shilganlar):"]
    for f in d["funnel"]:
        lines.append(f"   • {f['label']}: <b>{fmt_num(f['n'])}</b> ({_p(f['pct'])})")
    mo = d["revenue"][-1]
    lines += ["", f"💰 <b>Shu oy</b>: Premium {fmt_num(mo['premium_uzs'])} so'm • donat {fmt_num(mo['donate_uzs'])} so'm • ⭐ {fmt_num(mo['stars'])} • {mo['n']} ta to'lov"]
    if d["site_sources"]:
        lines += ["", "🌐 <b>Sayt tashriflari</b> (14 kun): " + ", ".join(f"{s['label']} {fmt_num(s['n'])}" for s in d["site_sources"][:4])]
    lines += ["", f"🕐 {datetime.now(TZ).strftime('%d.%m.%Y %H:%M')}"]
    return "\n".join(lines)


def _kb(ctx: Ctx):
    rows = [[btn("🔄 Yangilash", "an2:r", style=PRIMARY)]]
    url = ctx.app.config.webapp_url
    if url:
        rows.insert(0, [{"text": "📊 To'liq tahlil (grafiklar)", "web_app": {"url": url.rstrip("/") + "/?v=stats&tab=analytics"}}])
    return ikb(*rows)


@router.command("tahlil", "analytics", admin=True)
def cmd_analytics(ctx: Ctx) -> None:
    ctx.send(summary(ctx), _kb(ctx))


@router.callback("an2", admin=True)
def cb_analytics(ctx: Ctx) -> None:
    ctx.answer("🔄")
    try:
        ctx.edit(summary(ctx), _kb(ctx))
    except Exception:  # noqa: BLE001 — matn o'zgarmasa Telegram xato beradi
        pass
