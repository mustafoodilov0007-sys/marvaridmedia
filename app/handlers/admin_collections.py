"""Admin: 📚 To'plamlar — qo'lda tuzilgan kino to'plamlari («Marvel olami», «Yangi yil kinolari» ...).

To'plamlar saytning bosh sahifasida alohida qator bo'lib, botda esa «📚 To'plamlar» bo'limida chiqadi.
"""

from __future__ import annotations

import re

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb, number_rows
from ..texts import B, cat_icon
from ..utils import esc, normalize, truncate
from .user import search_ids

CODES_RE = re.compile(r"#?\d{1,9}(?:[\s,;]+#?\d{1,9})*")
EXAMPLES = "🦸 Marvel olami, 🎄 Yangi yil kinolari, 🇮🇳 Hind klassikasi, 😂 Oilaviy komediyalar"


def list_view(ctx: Ctx):
    cols = ctx.db.list_collections()
    lines = ["📚 <b>To'plamlar</b>", ""]
    if cols:
        lines.append("Saytning bosh sahifasida va botda shu tartibda chiqadi:")
        for i, c in enumerate(cols, 1):
            lines.append(f"<b>{i}.</b> {esc(c['title'])} — {c['n']} ta")
    else:
        lines.append("Hozircha to'plam yo'q.\n\n💡 Masalan: " + EXAMPLES)
    rows = [[btn(f"{c['title'][:40]} ({c['n']})", f"co:open:{c['id']}", style=PRIMARY)] for c in cols]
    rows.append([btn("➕ Yangi to'plam", "co:new:0", style=SUCCESS)])
    rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


def open_view(ctx: Ctx, cid: int):
    col = ctx.db.get_collection(cid)
    if not col:
        return list_view(ctx)
    movies = ctx.db.collection_movies(cid, 50)
    lines = [f"📚 <b>{esc(col['title'])}</b> — {len(movies)} ta", ""]
    for i, m in enumerate(movies, 1):
        code = f" <code>{m['code']}</code>" if m["code"] > 0 else ""
        lines.append(f"<b>{i}.</b> {cat_icon(m['category'])} {esc(truncate(m['title'], 50))}{code}")
    if not movies:
        lines.append("Bo'sh. «➕ Kino qo'shish» ni bosing.")
    rows = [[btn("➕ Kino qo'shish", f"co:add:{cid}", style=SUCCESS)]]
    if movies:
        rows.append([btn("➖ Kinoni olib tashlash", f"co:rm:{cid}", style=DANGER)])
    rows.append([btn("⬆️ Yuqoriga", f"co:up:{cid}", style=PRIMARY), btn("⬇️ Pastga", f"co:down:{cid}", style=PRIMARY)])
    rows.append([btn("✏️ Nomini o'zgartirish", f"co:ren:{cid}", style=PRIMARY),
                 btn("🗑 O'chirish", f"co:del:{cid}", style=DANGER)])
    rows.append([btn("⬅️ To'plamlar", "co:list:0", style=SUCCESS)])
    return "\n".join(lines), ikb(*rows)


@router.button(B.COLLECTIONS, admin=True)
def btn_collections(ctx: Ctx) -> None:
    ctx.clear_state()
    ctx.send(*list_view(ctx))


@router.callback("co", admin=True)
def cb_collections(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    if len(parts) < 3 or not parts[2].lstrip("-").isdigit():
        ctx.answer()
        return
    action, cid = parts[1], int(parts[2])
    db = ctx.db
    if action == "list":
        ctx.answer()
        ctx.clear_state()
        ctx.edit(*list_view(ctx))
        return
    if action == "new":
        ctx.answer()
        ctx.set_state("co:title")
        ctx.send("📚 Yangi to'plam <b>nomini</b> yuboring:\n💡 Masalan: " + EXAMPLES, cancel_kb())
        return
    col = db.get_collection(cid)
    if not col:
        ctx.answer("😔 To'plam topilmadi", alert=True)
        return
    if action == "open":
        ctx.answer()
        ctx.clear_state()
        ctx.edit(*open_view(ctx, cid))
    elif action == "add":
        ctx.answer()
        ctx.set_state("co:add", ttl=6 * 3600, cid=cid)
        ctx.send(f"➕ <b>{esc(col['title'])}</b> ga kino qo'shamiz.\n\n"
                 "Kino <b>kodlarini</b> yuboring — bir nechtasini bo'sh joy bilan: <code>15 23 40</code>\n"
                 "yoki kino <b>nomini</b> yozing.\n\nTugatgach «✅ Tayyor» ni bosing.",
                 ikb([btn("✅ Tayyor", f"co:open:{cid}", style=SUCCESS)]))
    elif action == "pick" and len(parts) > 3 and parts[3].isdigit():
        movie = db.get_movie(int(parts[3]))
        if movie and db.add_to_collection(cid, movie["id"]):
            ctx.answer(f"✅ Qo'shildi: {movie['title'][:40]}")
        else:
            ctx.answer("Bu kino allaqachon to'plamda")
    elif action == "rm":
        ctx.answer()
        movies = db.collection_movies(cid, 50)
        lines = [f"➖ <b>{esc(col['title'])}</b> — qaysi kinoni olib tashlaymiz?", ""]
        for i, m in enumerate(movies, 1):
            lines.append(f"<b>{i}.</b> {esc(truncate(m['title'], 50))}")
        rows = number_rows([(i, f"co:rmi:{cid}:{m['id']}") for i, m in enumerate(movies, 1)], style=DANGER)
        rows.append([btn("⬅️ Orqaga", f"co:open:{cid}", style=PRIMARY)])
        ctx.edit("\n".join(lines), {"inline_keyboard": rows})
    elif action == "rmi" and len(parts) > 3 and parts[3].isdigit():
        db.remove_from_collection(cid, int(parts[3]))
        ctx.answer("➖ Olib tashlandi")
        ctx.edit(*open_view(ctx, cid))
    elif action in ("up", "down"):
        db.move_collection(cid, action == "up")
        ctx.answer("⬆️ Yuqoriga surildi" if action == "up" else "⬇️ Pastga surildi")
        ctx.edit(*open_view(ctx, cid))
    elif action == "ren":
        ctx.answer()
        ctx.set_state("co:ren", cid=cid)
        ctx.send(f"✏️ <b>{esc(col['title'])}</b> — yangi nomni yuboring:", cancel_kb())
    elif action == "del":
        ctx.answer()
        ctx.edit(f"⚠️ <b>{esc(col['title'])}</b> to'plami o'chirilsinmi?\n\nKinolarning o'zi o'chmaydi.",
                 ikb([btn("✅ Ha, o'chirilsin", f"co:delok:{cid}", style=DANGER)],
                     [btn("⬅️ Yo'q", f"co:open:{cid}", style=PRIMARY)]))
    elif action == "delok":
        db.delete_collection(cid)
        ctx.answer("🗑 O'chirildi")
        ctx.edit(*list_view(ctx))


def _title_ok(ctx: Ctx) -> str:
    title = ctx.text.strip()
    if not title or title.startswith("/") or len(title) > 60:
        ctx.send("❗️ Nom 1–60 belgidan iborat matn bo'lsin.", cancel_kb())
        return ""
    return title


@router.state("co:title", admin=True)
def st_title(ctx: Ctx) -> None:
    title = _title_ok(ctx)
    if not title:
        return
    cid = ctx.db.add_collection(title)
    ctx.clear_state()
    ctx.send(f"✅ <b>{esc(title)}</b> to'plami yaratildi!")
    ctx.send(*open_view(ctx, cid))


@router.state("co:ren", admin=True)
def st_rename(ctx: Ctx) -> None:
    title = _title_ok(ctx)
    if not title:
        return
    cid = ctx.sdata.get("cid") or 0
    ctx.db.rename_collection(cid, title)
    ctx.clear_state()
    ctx.send("✅ Nomi o'zgartirildi!")
    ctx.send(*open_view(ctx, cid))


@router.state("co:add", admin=True)
def st_add(ctx: Ctx) -> None:
    cid = ctx.sdata.get("cid") or 0
    col = ctx.db.get_collection(cid)
    text = ctx.text.strip()
    if not col:
        ctx.clear_state()
        ctx.send("😔 To'plam topilmadi.")
        return
    if not text:
        ctx.send("❗️ Kino kodini yoki nomini matn qilib yuboring.")
        return
    done_kb = ikb([btn("✅ Tayyor", f"co:open:{cid}", style=SUCCESS)])
    if CODES_RE.fullmatch(text):
        added, missing = [], []
        for code in re.findall(r"\d+", text):
            movie = ctx.db.get_movie_by_code(int(code))
            if not movie:
                missing.append(code)
            elif ctx.db.add_to_collection(cid, movie["id"]):
                added.append(movie["title"])
        lines = []
        if added:
            lines.append(f"✅ Qo'shildi ({len(added)}): " + ", ".join(esc(truncate(t, 30)) for t in added))
        if missing:
            lines.append("❌ Topilmagan kodlar: " + ", ".join(missing))
        if not lines:
            lines.append("ℹ️ Bu kinolar allaqachon to'plamda.")
        ctx.send("\n".join(lines) + "\n\nYana yuboring yoki «✅ Tayyor» ni bosing.", done_kb)
        return
    ids, _ = search_ids(ctx.app, normalize(text), scope="video")
    rows = ctx.db.movie_rows(ids[:10])
    if not rows:
        ctx.send("❌ Hech narsa topilmadi. Boshqa nom yoki kod yuboring.", done_kb)
        return
    kb = [[btn(f"{cat_icon(r['category'])} {truncate(r['title'], 45)}", f"co:pick:{cid}:{r['id']}", style=PRIMARY)]
          for r in rows]
    kb.append([btn("✅ Tayyor", f"co:open:{cid}", style=SUCCESS)])
    ctx.send("🔎 Qaysi birini qo'shamiz? (bir nechtasini bosish mumkin)", {"inline_keyboard": kb})
