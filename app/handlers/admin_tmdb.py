"""🌐 TMDB dan kino ma'lumotini to'ldirish (bot ichida): asl nomi → variantlar → ko'rib chiqish → qo'llash."""

from __future__ import annotations

import logging
import time

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


# ───── 🖼 /rasmlar: eski kinolarga keng rasm va aniq (TMDB) poster topish ─────
IMG_BATCH = 20          # bir buyruqda nechta kino (bot uzoq qotib qolmasligi uchun)
LOWRES_W = 800          # Telegram posteri shundan tor bo'lsa — TMDB posteri ham qo'yiladi


def _tg_poster_width(ctx: Ctx, movie) -> int:
    """Hozirgi (Telegram) poster kengligi, px. Poster yo'q yoki o'qilmasa — 0."""
    from pathlib import Path
    from .. import webapp
    if not movie["poster_id"] or webapp._PIL is None:
        return 0
    try:
        import io
        data = webapp.poster_bytes(ctx.app, movie["id"], Path(ctx.app.config.db_path).parent / "posters", 0)
        return webapp._PIL.open(io.BytesIO(data)).width if data else 0
    except Exception:       # noqa: BLE001
        return 0


@router.command("rasmlar", "rasmlar_yangila", admin=True)
def cmd_images(ctx: Ctx) -> None:
    """Keng rasmi (yoki aniq posteri) yo'q kinolar uchun TMDB dan mos rasm topadi.
    Faqat rasmga tegadi (nom, tavsif, yil o'zgarmaydi). Mos kelganiga ishonch bo'lmasa — o'tkazib yuboradi."""
    tm = tmdb.get(ctx.app)
    if not tm.configured:
        not_configured(ctx)
        return
    if ctx.args.strip().lower() in ("boshidan", "reset"):
        ctx.app.set_setting("tmdbimg_cursor", "0")
        ctx.send("🔄 Boshidan boshlaymiz. Yana /rasmlar yozing.")
        return
    cursor = int(ctx.app.setting("tmdbimg_cursor") or 0)
    rows = ctx.db.movies_for_images(cursor, IMG_BATCH)
    if not rows:
        ctx.send("✅ <b>Hammasi ko'rib chiqildi.</b> Qolgan kinolar uchun «TMDB dan to'ldirish» tugmasini ishlating "
                 "(nomi mos kelmagan kinolarni o'zim topolmayman).\n\nBoshidan: <code>/rasmlar boshidan</code>")
        return
    ctx.send(f"⏳ {len(rows)} ta kino tekshirilmoqda…")
    done, skipped, errors = [], [], 0
    for m in rows:
        cursor = m["id"]
        try:
            hit = tmdb.match_images(tm, m["title"], m["year"] or 0, m["description"] or "")
        except tmdb.TmdbError:
            errors += 1
            if errors >= 3:
                break
            continue
        if not hit:
            skipped.append(m["title"])
            continue
        f = {}
        if hit["backdrop"] and not m["backdrop"]:
            f["backdrop"] = hit["backdrop"]
        if hit["tposter"] and not m["tposter"] and _tg_poster_width(ctx, m) < LOWRES_W:
            f["tposter"] = hit["tposter"]
        if f:
            ctx.db.update_movie(m["id"], **f)
            done.append(f"{truncate(m['title'], 26)} ({'rasm+poster' if len(f) == 2 else ('rasm' if 'backdrop' in f else 'poster')}, {hit['how']})")
        else:
            skipped.append(m["title"])
        time.sleep(0.25)
    ctx.app.set_setting("tmdbimg_cursor", str(cursor))
    ctx.db.__dict__.pop("_memo", None)
    ctx.app.__dict__.pop("_home_cache", None)
    text = f"🖼 <b>Natija:</b> topildi {len(done)}, o'tkazildi {len(skipped)}" + (f", xato {errors}" if errors else "") + "\n"
    if done:
        text += "\n✅ " + "\n✅ ".join(esc(x) for x in done[:15])
    if skipped:
        text += "\n\n➖ Ishonchli topilmadi: " + esc(", ".join(truncate(x, 22) for x in skipped[:12])) + ("…" if len(skipped) > 12 else "")
    if errors >= 3:
        text += "\n\n⚠️ TMDB javob bermayapti — keyinroq qayta urinib ko'ring."
    elif len(rows) == IMG_BATCH:
        text += "\n\n▶️ Davom etish uchun yana <code>/rasmlar</code> yozing."
    ctx.send(text)
