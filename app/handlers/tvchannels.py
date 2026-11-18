"""📺 /kanallar — Marvarid TV dagi «Jonli kanallar» ro'yxatini admin boshqaradi.
Kanal: nom + rasmiy efir havolasi. YouTube jonli efiri (video yoki /channel/UC… havolasi) saytda o'ynaydi; boshqa havola — «Kanal saytida ko'rish»."""

from __future__ import annotations

from .. import tv
from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..utils import esc, truncate

KINDS = {"youtube": "▶️ saytda o'ynaydi", "link": "🔗 tashqi havola"}


def _view(app):
    chans = tv.channels(app)
    lines = ["📺 <b>Jonli kanallar</b> (Marvarid TV bo'limida)", ""]
    if chans:
        for c in chans:
            lines.append(f"• <b>{esc(c['name'])}</b> — {KINDS[c['kind']]}")
    else:
        lines.append("Hozircha kanal yo'q — faqat Marvarid TV ko'rinadi.")
    lines += ["", "Kanal qo'shish: «➕ Qo'shish» ni bosing va <code>Nomi | https://havola</code> yuboring.",
              "✅ Saytda o'ynaydi: YouTube jonli efir havolasi (<code>youtube.com/watch?v=…</code>, <code>youtu.be/…</code>) yoki "
              "<code>youtube.com/channel/UC…</code>.",
              "🔗 Boshqa har qanday <code>https://</code> havola — «Kanal saytida ko'rish» tugmasi bo'ladi.",
              "", "⚠️ Faqat kanalning <b>rasmiy</b> efir havolasini qo'shing."]
    rows = [[btn("➕ Qo'shish", "tvc:add", style=SUCCESS)]]
    for c in chans:
        rows.append([btn(f"🗑 {truncate(c['name'], 28)}", f"tvc:del:{c['id']}", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


@router.command("kanallar", "tvkanal", owner=True)
def cmd_channels(ctx: Ctx) -> None:
    ctx.send(*_view(ctx.app))


@router.callback("tvc", owner=True)
def cb_channels(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    act = parts[1] if len(parts) > 1 else ""
    if act == "add":
        ctx.answer()
        ctx.set_state("tvc:add", ttl=1800)
        ctx.send("✏️ <code>Nomi | https://havola</code> ko'rinishida yuboring.\nMasalan: <code>Milliy TV | https://www.youtube.com/watch?v=XXXXXXXXXXX</code>",
                 ikb([btn("❌ Bekor qilish", "cancel", style=DANGER)]))
        return
    if act == "del" and len(parts) > 2 and parts[2].isdigit():
        ctx.answer("🗑 O'chirildi" if ctx.db.del_tv_channel(int(parts[2])) else "Topilmadi")
    else:
        ctx.answer()
    ctx.edit(*_view(ctx.app))


@router.state("tvc:add", admin=True)
def st_add(ctx: Ctx) -> None:
    if not ctx.is_owner:
        ctx.clear_state()
        return
    name, sep, url = (ctx.text or "").partition("|")
    name, url = name.strip()[:40], url.strip()
    parsed = tv.parse_channel_url(url) if sep and name else None
    if not parsed:
        ctx.send("❗️ Format: <code>Nomi | https://havola</code> (havola <code>https://</code> bilan boshlansin).")
        return
    ctx.db.add_tv_channel(name, url)
    ctx.clear_state()
    ctx.send(f"✅ «{esc(name)}» qo'shildi — {KINDS[parsed[0]]}.")
    ctx.send(*_view(ctx.app))
