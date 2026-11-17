"""🎞 /shortstekshir — Shorts fayllarini Telegram'dan tekshiradi: qaysi biri saytda yuklanmaydi va nega. Buzuqlarini o'chirish mumkin."""

from __future__ import annotations

import logging

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, btn, ikb
from ..telegram import TelegramError
from ..utils import esc, truncate

log = logging.getLogger("shortscheck")

LIMIT = 20 * 1024 * 1024
MAX_CHECK = 200


def check_shorts(app) -> list:
    """[(short_id, kino nomi, sabab)] — faqat muammoli shortslar. Faylni yuklamaydi, faqat getFile so'raydi."""
    bad = []
    rows = app.db.q("SELECT s.id, s.file_id, s.kind, m.title FROM shorts s JOIN movies m ON m.id=s.movie_id ORDER BY s.id DESC LIMIT ?",
                    (MAX_CHECK,))
    for r in rows:
        try:
            info = app.bot.call("getFile", {"file_id": r["file_id"]})
        except TelegramError as exc:
            desc = (exc.description or str(exc)).lower()
            why = "20 MB dan katta" if "too big" in desc else "file_id yaroqsiz (boshqa botniki yoki o'chgan)"
            bad.append((r["id"], r["title"], why))
            continue
        size = (info or {}).get("file_size") or 0
        if size > LIMIT:
            bad.append((r["id"], r["title"], f"{size // 1048576} MB — 20 MB dan katta"))
    return bad


def _drop_files(app, ids) -> None:
    folder = app.db.path.parent / "shorts"
    for sid in ids:
        for f in folder.glob(f"{int(sid)}.*"):
            try:
                f.unlink()
            except OSError:
                pass


@router.command("shortstekshir", owner=True)
def cmd_check(ctx: Ctx) -> None:
    app = ctx.app
    total = app.db.count_shorts()
    if not total:
        ctx.send("🎞 Hali shorts yo'q.")
        return
    ctx.send("🔎 Shorts fayllari tekshirilmoqda…")
    bad = check_shorts(app)
    if not bad:
        ctx.send(f"✅ Hammasi joyida: {min(total, MAX_CHECK)} ta shorts Telegram'dan olinadi.\n"
                 "Saytda baribir yuklanmasa — qurilma/brauzerni yozib yuboring.")
        return
    lines = [f"⚠️ <b>{len(bad)} ta shorts yuklanmaydi</b> (jami {total}):", ""]
    lines += [f"• №{i} — {esc(truncate(t, 30))}: {esc(why)}" for i, t, why in bad[:25]]
    lines += ["", "Ular saytda «Video yuklanmadi» bo'lib turibdi. O'chirsangiz, kinoning o'zi qoladi — shortsni qayta qo'shasiz (20 MB dan kichik)."]
    ctx.send("\n".join(lines), ikb([btn(f"🗑 {len(bad)} ta buzuqni o'chirish", "sc:del", style=DANGER)]))


@router.callback("sc", owner=True)
def cb_check(ctx: Ctx) -> None:
    if ctx.data != "sc:del":
        ctx.answer()
        return
    bad = check_shorts(ctx.app)                       # qayta tekshiramiz: o'sha vaqtgacha tuzalgan bo'lishi mumkin
    ids = [i for i, _, _ in bad]
    for i in ids:
        ctx.db.x("DELETE FROM shorts WHERE id=?", (i,))
    _drop_files(ctx.app, ids)
    ctx.answer(f"🗑 {len(ids)} ta o'chirildi", alert=True)
    ctx.edit(f"✅ {len(ids)} ta buzuq shorts o'chirildi.")
