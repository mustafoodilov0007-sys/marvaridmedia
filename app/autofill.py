"""🤖 Eski kinolarni avto to'ldirish: nom va izohdan janr, yil, davlat va tilni aniqlaydi (faqat BO'SH maydonlarni to'ldiradi)."""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Tuple

from . import genres

log = logging.getLogger("autofill")

FIELDS = ("genres", "year", "country", "lang")
LABELS = {"genres": "🎭 janr", "year": "📅 yil", "country": "🌍 davlat", "lang": "🗣 til"}
UNDO_KEY = "autofill_undo"
MAX_UNDO = 3000


def plan(db) -> List[Tuple[int, str, Dict]]:
    """[(id, nom, {maydon: yangi qiymat})] — hech narsa yozmaydi."""
    out = []
    rows = db.q("SELECT id, title, description, genres, year, country, lang FROM movies WHERE category<>'music'"
                " AND (genres='' OR year=0 OR country='' OR lang='')")
    for r in rows:
        title, desc = r["title"] or "", r["description"] or ""
        upd: Dict = {}
        if not r["genres"]:
            g = genres.detect(title, desc)
            if g:
                upd["genres"] = genres.dump(g)
        if not r["year"]:
            y = genres.detect_year(title, desc)
            if y:
                upd["year"] = y
        if not r["country"]:
            c = genres.detect_country(desc)               # nomdan emas: nomdagi «Hind», «Turk» so'zlari adashtirmasin
            if c:
                upd["country"] = c
        if not r["lang"]:
            lg = genres.detect_lang(desc)
            if lg:
                upd["lang"] = lg
        if upd:
            out.append((r["id"], title, upd))
    return out


def summary(items) -> Dict[str, int]:
    cnt = {k: 0 for k in FIELDS}
    for _, _, upd in items:
        for k in upd:
            cnt[k] += 1
    return cnt


def apply(app, items) -> int:
    """Rejani qo'llaydi va oldingi (bo'sh) qiymatlarni «qaytarish» uchun saqlaydi."""
    undo = []
    for mid, _title, upd in items:
        old = {k: ("" if k != "year" else 0) for k in upd}
        undo.append([mid, old])
        app.db.update_movie(mid, **upd)
    app.set_setting(UNDO_KEY, json.dumps(undo[:MAX_UNDO], ensure_ascii=False))
    return len(items)


def undo(app) -> int:
    try:
        data = json.loads(app.setting(UNDO_KEY) or "[]")
    except ValueError:
        return 0
    n = 0
    for mid, old in data:
        if app.db.get_movie(mid):
            app.db.update_movie(mid, **old)
            n += 1
    app.set_setting(UNDO_KEY, "[]")
    return n
