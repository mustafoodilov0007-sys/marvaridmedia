"""Ochiq API — hozirgi saytning (app/web/index.html) kutayotgan javob shakllari bilan bir xil."""

from __future__ import annotations

import json
import random
import sqlite3
from typing import Dict, List, Optional

from db import DB, now, today
from textutil import like, normalize

PAGE = 24
WATCHABLE = ("t.published=1 AND EXISTS (SELECT 1 FROM videos v WHERE v.title_id=t.id AND v.status='ready')")
BASE = ("SELECT t.*,"
        " (SELECT COUNT(*) FROM videos v WHERE v.title_id=t.id AND v.status='ready') AS parts,"
        " (SELECT MAX(v.created_at) FROM videos v WHERE v.title_id=t.id AND v.status='ready') AS vadded,"
        " (SELECT v.duration FROM videos v WHERE v.title_id=t.id AND v.status='ready' ORDER BY v.part_no LIMIT 1) AS vdur"
        " FROM titles t")
ORDERS = {"new": "COALESCE(vadded, t.created_at) DESC, t.id DESC", "top": "t.views DESC, t.id DESC"}


def _trunc(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def item(r: sqlite3.Row) -> dict:
    try:
        genres = json.loads(r["genres"] or "[]")
    except ValueError:
        genres = []
    return {
        "id": r["id"], "code": r["code"], "cat": r["category"], "title": r["title"],
        "desc": _trunc(r["description"], 400), "year": r["year"] or None, "trailer": None,
        "added": r["vadded"] or r["created_at"], "genres": genres, "country": r["country"], "lang": r["lang"],
        "quality": r["quality"], "duration": r["vdur"] or r["duration"] or 0, "age": r["age"] or None,
        "imdb": r["imdb"] or None, "likes": 0, "dislikes": 0, "parts": r["parts"], "views": r["views"],
        "premium": False, "locked": False, "poster": r["poster_v"] or None,
    }


def pack(rows) -> List[dict]:
    return [item(r) for r in rows]


def counts(db: DB) -> Dict[str, int]:
    out = {"movie": 0, "serial": 0, "cartoon": 0, "music": 0, "shorts": 0}
    for r in db.q(f"SELECT t.category AS c, COUNT(*) AS n FROM titles t WHERE {WATCHABLE} GROUP BY t.category"):
        out[r["c"]] = r["n"]
    return out


def _list(db: DB, where: str, params: list, order: str, limit: int, offset: int = 0) -> List[sqlite3.Row]:
    return db.q(f"{BASE} WHERE {WATCHABLE} {('AND ' + where) if where else ''} ORDER BY {order} LIMIT ? OFFSET ?",
                params + [limit, offset])


def _cat_where(cat: str):
    if cat in ("movie", "serial", "cartoon"):
        return "t.category=?", [cat]
    return "", []


def genre_counts(db: DB, cat: str = "video") -> List[dict]:
    w, p = _cat_where(cat)
    labels: Dict[str, str] = {}
    cnt: Dict[str, int] = {}
    for r in db.q(f"SELECT t.genres FROM titles t WHERE {WATCHABLE} {('AND ' + w) if w else ''}", p):
        try:
            for g in json.loads(r["genres"] or "[]"):
                cnt[g["key"]] = cnt.get(g["key"], 0) + 1
                labels[g["key"]] = g["label"]
        except (ValueError, KeyError, TypeError):
            pass
    return [{"key": k, "label": labels[k], "n": n} for k, n in sorted(cnt.items(), key=lambda kv: -kv[1])]


def weekly_top(db: DB, limit: int = 10) -> List[sqlite3.Row]:
    since = today() - 6
    ids = [r[0] for r in db.q(
        f"SELECT d.title_id FROM view_days d JOIN titles t ON t.id=d.title_id WHERE {WATCHABLE} AND d.day>=?"
        " GROUP BY d.title_id ORDER BY SUM(d.n) DESC, d.title_id DESC LIMIT ?", (since, limit))]
    rows = {r["id"]: r for r in db.q(f"{BASE} WHERE {WATCHABLE} AND t.id IN ({','.join('?' * len(ids)) or '-1'})", ids)}
    out = [rows[i] for i in ids if i in rows]
    if len(out) < limit:       # ma'lumot yetmasa: yangi qo'shilgan mashhurlar, keyin umumiy TOP
        have = {r["id"] for r in out}
        t = now()
        for where, params in (("COALESCE(vadded, t.created_at) >= ?", [t - 30 * 86400]), ("", [])):
            for r in _list(db, where, params, ORDERS["top"], limit + len(have)):
                if r["id"] not in have and len(out) < limit:
                    out.append(r)
                    have.add(r["id"])
    return out


def home(db: DB) -> dict:
    newest = list(_list(db, "", [], ORDERS["new"], 30))
    with_poster = [r for r in newest if r["poster_v"]]
    hero = (with_poster + [r for r in newest if not r["poster_v"]])[:6]
    return {
        "ok": True, "history": [], "foryou": [], "searched": [], "extra": [], "choice": [], "collections": [],
        "weekly": pack(weekly_top(db, 10)), "hero": pack(hero), "shorts": [],
        "rails": [
            {"key": "new", "title": "Yangi qo'shilganlar", "cat": "video", "sort": "new", "items": pack(newest[:15])},
            {"key": "top", "title": "Eng ko'p ko'rilgan", "cat": "video", "sort": "top",
             "items": pack(_list(db, "", [], ORDERS["top"], 15))},
            {"key": "serial", "title": "Seriallar", "cat": "serial", "sort": "new",
             "items": pack(_list(db, "t.category='serial'", [], ORDERS["new"], 15))},
            {"key": "cartoon", "title": "Multfilmlar", "cat": "cartoon", "sort": "new",
             "items": pack(_list(db, "t.category='cartoon'", [], ORDERS["new"], 15))},
            {"key": "music", "title": "Musiqa", "cat": "music", "sort": "new", "items": []},
        ],
        "genres": genre_counts(db), "counts": counts(db),
    }


def catalog(db: DB, qs: dict) -> dict:
    cat = qs.get("cat", "video")
    if cat not in ("movie", "serial", "cartoon"):
        cat = "video"
    sort = "top" if qs.get("sort") in ("top", "rating") else "new"
    try:
        offset = max(0, int(qs.get("offset", "0")))
    except ValueError:
        offset = 0
    query = (qs.get("q") or "").strip()[:100]
    where, params = [], []
    w, p = _cat_where(cat)
    if w:
        where.append(w)
        params += p
    link = (qs.get("k") or "").strip()
    if link.isdigit():                       # kanaldagi havola: ?k=<kod>
        where.append("t.code=?")
        params.append(int(link))
        rows = _list(db, " AND ".join(where), params, ORDERS["new"], 1)
        return {"ok": True, "items": pack(rows), "more": False, "counts": counts(db)}
    if qs.get("genre"):
        where.append("t.genres LIKE ? ESCAPE '\\'")
        params.append('%"key": "' + like(qs["genre"]) + '"%')
    for key, col in (("country", "t.country"), ("lang", "t.lang")):
        if qs.get(key):
            where.append(f"{col}=?")
            params.append(qs[key])
    if (qs.get("year") or "").isdigit() and len(qs["year"]) == 4:
        where.append("t.year=?")
        params.append(int(qs["year"]))
    if query:
        if query.lstrip("#").isdigit():
            n = int(query.lstrip("#"))
            if 1900 <= n <= 2100 and qs.get("all") == "1":
                where.append("t.year=?")
            else:
                where.append("t.code=?")
            params.append(n)
        else:
            for tok in normalize(query).split():
                where.append("t.norm LIKE ? ESCAPE '\\'")
                params.append(f"%{like(tok)}%")
    rows = _list(db, " AND ".join(where), params, ORDERS[sort], PAGE + 1, offset)
    out = {"ok": True, "items": pack(rows[:PAGE]), "more": len(rows) > PAGE, "counts": counts(db)}
    if offset == 0 and not query:
        out["genres"] = genre_counts(db, cat)
        w2, p2 = _cat_where(cat)
        base = f"SELECT {{c}} AS v, COUNT(*) AS n FROM titles t WHERE {WATCHABLE} {('AND ' + w2) if w2 else ''} AND {{c}}<>'' AND {{c}}<>0 GROUP BY {{c}}"
        f = {c: db.q(base.format(c=c), p2) for c in ("t.country", "t.year", "t.lang")}
        out["filters"] = {
            "country": [{"key": r["v"], "label": r["v"], "n": r["n"]} for r in sorted(f["t.country"], key=lambda r: -r["n"])],
            "year": [{"key": str(r["v"]), "label": str(r["v"]), "n": r["n"]} for r in sorted(f["t.year"], key=lambda r: -r["v"])],
            "lang": [{"key": r["v"], "label": r["v"], "n": r["n"]} for r in sorted(f["t.lang"], key=lambda r: -r["n"])],
        }
    return out


def similar(db: DB, qs: dict) -> dict:
    try:
        tid = int(qs.get("id", "0"))
    except ValueError:
        return {"ok": False, "reason": "not_found"}
    me = db.q1("SELECT category, genres FROM titles WHERE id=?", (tid,))
    if not me:
        return {"ok": True, "items": []}
    try:
        mine = {g["key"] for g in json.loads(me["genres"] or "[]")}
    except ValueError:
        mine = set()
    rows = [r for r in _list(db, "t.category=? AND t.id<>?", [me["category"], tid], ORDERS["top"], 200)]

    def score(r):
        try:
            return len(mine & {g["key"] for g in json.loads(r["genres"] or "[]")})
        except ValueError:
            return 0
    rows.sort(key=lambda r: -score(r))
    return {"ok": True, "items": pack(rows[:12])}


def random_item(db: DB) -> dict:
    rows = _list(db, "", [], ORDERS["new"], 300)
    return {"ok": True, "item": item(random.choice(rows))} if rows else {"ok": False, "reason": "empty"}


def me(cfg, db: DB) -> dict:
    return {"ok": True, "brand": cfg.brand, "bot": cfg.bot_username, "name": "", "premium": False, "premium_on": False,
            "premium_until": 0, "admin": False, "miniapp": None, "counts": counts(db), "channel": None}
