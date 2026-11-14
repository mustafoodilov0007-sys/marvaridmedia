"""🌐 TMDB dan kino ma'lumotini to'ldirish (bot ichida): asl nomi → variantlar → ko'rib chiqish → qo'llash."""

from __future__ import annotations

import logging

from .. import genres, tmdb
from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..utils import esc, fmt_num, truncate

log = logging.getLogger("admin.tmdb")


def not_configured(ctx: Ctx) -> None:
    ctx.send("🌐 <b>TMDB ulanmagan.</b>\n\n1. https://www.themoviedb.org da bepul akkaunt oching\n"
             "2. Settings → API → kalitni oling\n3. Railway → Variables → <code>TMDB_API_KEY</code> ga kiriting\n"
             "<i>IMDb reytingi ham kerak bo'lsa, https://www.omdbapi.com dan bepul kalit olib <code>OMDB_API_KEY</code> ga qo'ying.</i>")


def start(ctx: Ctx, movie) -> None:
    """«🌐 TMDB dan to'ldirish» bosilganda: asl nomini so'raymiz."""
    if not tmdb.get(ctx.app).configured:
        ctx.answer()
        not_configured(ctx)
        return
    ctx.answer()
    ctx.set_state("tm:q", ttl=1800, mid=movie["id"])
    ctx.send(f"🌐 <b>{esc(movie['title'])}</b>\n\nKinoning <b>asl (inglizcha) nomini</b> yozing — masalan: <code>Avengers Endgame</code>\n"
             "Chiqqan yilini ham qo'shsangiz aniqroq: <code>Avengers Endgame 2019</code>", cancel_kb())


@router.state("tm:q", admin=True)
def st_query(ctx: Ctx) -> None:
    mid = ctx.sdata.get("mid")
    movie = ctx.db.get_movie(mid or 0)
    text = ctx.text.strip()
    if not movie or not text or text.startswith("/"):
        ctx.send("❗️ Kino nomini matn ko'rinishida yozing.", cancel_kb())
        return
    import re
    m = re.search(r"\b(19[2-9]\d|20[0-4]\d)\b\s*$", text)
    year = int(m.group(1)) if m else None
    query = text[:m.start()].strip() if m else text
    try:
        items = tmdb.get(ctx.app).search(query, year)
    except tmdb.TmdbError as exc:
        ctx.clear_state()
        ctx.send(f"❌ {esc(str(exc))}")
        return
    ctx.clear_state()
    if not items:
        ctx.send(f"😔 «{esc(query)}» bo'yicha topilmadi. Boshqa yozilishini sinab ko'ring.",
                 ikb([btn("🔁 Qayta qidirish", f"dm:tm:{mid}", style=PRIMARY)], [btn("⬅️ Orqaga", f"dm:open:{mid}", style=DANGER)]))
        return
    rows = [[btn(f"{'📺' if x['kind'] == 'tv' else '🎬'} {truncate(x['title'], 28)} ({x['year'] or '—'})", f"tm:p:{mid}:{x['kind']}:{x['id']}",
                 style=PRIMARY)] for x in items[:6]]
    rows.append([btn("🔁 Boshqa nom", f"dm:tm:{mid}", style=SUCCESS), btn("⬅️ Orqaga", f"dm:open:{mid}", style=DANGER)])
    ctx.send(f"🔎 <b>«{esc(query)}»</b> uchun variantlar — to'g'risini tanlang:", ikb(*rows))


def preview(movie, d: dict) -> str:
    names = ", ".join(genres.name(k) for k in d["genres"]) or "—"
    return (f"🌐 <b>{esc(d['title'])}</b> ({esc(d['original'])})\n\n"
            f"📅 Yil: <b>{d['year'] or '—'}</b>\n🎭 Janr: <b>{esc(names)}</b>\n"
            f"🌍 Davlat: <b>{genres.country_label(d['country']) or '—'}</b>\n⏱ Davomiylik: <b>{d['duration_min'] or '—'}</b> daq\n"
            f"🔞 Yosh: <b>{str(d['age']) + '+' if d['age'] else '—'}</b>\n⭐ IMDb: <b>{d['imdb'] or '—'}</b>\n\n"
            f"🎭 Aktyorlar: <b>{len((d.get('extra') or {}).get('cast', []))}</b> · 🖼 Kadrlar: <b>{len((d.get('extra') or {}).get('stills', []))}</b> · "
            f"🎞 Treyler: <b>{'bor' if d.get('trailer') else '—'}</b>\n\n"
            f"📝 {esc(truncate(d['overview'], 300)) or '—'}\n\n"
            f"<i>«{esc(truncate(movie['title'], 40))}» ga shu ma'lumotlar yoziladi (bo'sh topilganlari o'zgartirilmaydi).</i>")


@router.callback("tm", admin=True)
def cb_tmdb(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    if action == "x":
        ctx.answer()
        ctx.delete_cb_message()
        return
    try:
        mid, kind, tid = int(parts[2]), parts[3], int(parts[4])
    except (IndexError, ValueError):
        ctx.answer()
        return
    movie = ctx.db.get_movie(mid)
    if not movie:
        ctx.answer("😔 Kino topilmadi", alert=True)
        return
    try:
        d = tmdb.get(ctx.app).details(kind, tid)
    except tmdb.TmdbError as exc:
        ctx.answer(str(exc)[:150], alert=True)
        return
    if action == "p":
        ctx.answer()
        ctx.edit(preview(movie, d), ikb([btn("✅ Qo'llash", f"tm:a:{mid}:{kind}:{tid}", style=SUCCESS)],
                                        [btn("✅ Izoh bilan (almashtirib)", f"tm:ad:{mid}:{kind}:{tid}", style=PRIMARY)],
                                        [btn("⬅️ Boshqa variant", f"dm:tm:{mid}", style=DANGER)]))
    elif action in ("a", "ad"):
        changed = tmdb.apply_fields(ctx.db, mid, d, with_description=(action == "ad"))
        ctx.answer("✅ Saqlandi")
        ctx.edit(f"✅ <b>{esc(movie['title'])}</b>: {', '.join(changed) if changed else 'yangi ma’lumot topilmadi'} yozildi.",
                 ikb([btn("📋 Kino sahifasi", f"dm:open:{mid}", style=PRIMARY)]))
