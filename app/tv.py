"""📺 Marvarid TV — kutubxonadagi kinolardan kunlik «efir» jadvali.

Haqiqiy translyatsiya emas: har kun uchun bitta jadval tuziladi (kinolar ketma-ket), «hozir efirda» esa soatdan hisoblanadi.
Jadval kuniga bir marta tuziladi va bazada saqlanadi — shuning uchun kun davomida kinolar qo'shilsa ham «hozir efirda» o'zgarmaydi,
va hamma foydalanuvchi bir xil jadvalni ko'radi.
"""

from __future__ import annotations

import json
import logging
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .utils import TZ, now

log = logging.getLogger("tv")

BREAK = 180                       # kinolar orasidagi tanaffus (soniya)
DEFAULT_DUR = 100 * 60            # davomiyligi noma'lum kino uchun
MIN_DUR, MAX_DUR = 20 * 60, 4 * 3600
KEEP_DAYS = 3

# kunning bo'laklari: (boshlanish soati, kalit, nomi, yoqadigan janrlar)
BLOCKS = [
    (0, "night", "Tungi seans", ("horror", "thriller", "ghost", "zombie", "crime", "criminal", "vampire")),
    (6, "morning", "Ertalabki seans", ("animation", "family", "comedy", "adventure", "magic", "superhero")),
    (12, "day", "Kunduzgi seans", ("comedy", "adventure", "action", "fantasy", "family", "sport")),
    (18, "evening", "Kechki premyera", ("drama", "action", "thriller", "romance", "romantic", "biography", "history")),
    (23, "night", "Tungi seans", ("horror", "thriller", "ghost", "zombie", "crime", "criminal", "vampire")),
]

_lock = threading.Lock()
_mem: Dict[str, list] = {}


def block_of(ts: int) -> dict:
    hour = datetime.fromtimestamp(ts, TZ).hour
    cur = BLOCKS[0]
    for b in BLOCKS:
        if hour >= b[0]:
            cur = b
    return {"key": cur[1], "title": cur[2], "genres": cur[3]}


def day_start(ts: int) -> int:
    d = datetime.fromtimestamp(ts, TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(d.timestamp())


def _key(start: int) -> str:
    return "tv_" + datetime.fromtimestamp(start, TZ).strftime("%Y%m%d")


def _dur(seconds) -> int:
    s = int(seconds or 0)
    return s if MIN_DUR <= s <= MAX_DUR else DEFAULT_DUR


def pool(app) -> List[dict]:
    """Efirga chiqishi mumkin bo'lgan kinolar (kino va multfilm; serial va musiqa emas)."""
    rows = app.db.q("SELECT id, category, genres, duration, created_at, year, poster_id FROM movies"
                    " WHERE category IN ('movie','cartoon') ORDER BY id")
    return [{"id": r["id"], "cat": r["category"], "genres": [g for g in (r["genres"] or "").split(",") if g],
             "dur": _dur(r["duration"]), "added": r["created_at"] or 0, "poster": bool(r["poster_id"])} for r in rows]


def _score(m: dict, blk: dict, rng: random.Random, newest: set) -> float:
    s = rng.random()
    s += 1.5 * sum(1 for g in m["genres"] if g in blk["genres"])
    if blk["key"] == "morning":
        s += 2.5 if m["cat"] == "cartoon" else 0
    elif m["cat"] == "cartoon":
        s -= 1.0                      # kechqurun va tunda multfilm kamroq
    if blk["key"] == "evening" and m["id"] in newest:
        s += 2.0                      # kechki premyera — yangi qo'shilganlar
    if m["poster"]:
        s += 0.4                      # posterli kino chiroyliroq ko'rinadi
    return s


def build(items: List[dict], start: int, prev_id: int = 0) -> List[list]:
    """[start, start+24 soat) uchun jadval: [[kino id, boshlanish, tugash], ...]. Bir xil kino ketma-ket kelmaydi."""
    if not items:
        return []
    end = start + 86400
    rng = random.Random(start)
    newest = {m["id"] for m in sorted(items, key=lambda x: -x["added"])[:max(3, len(items) // 6)]}
    left = list(items)
    out: List[list] = []
    t, last = start, prev_id
    while t < end:
        if not left:
            left = list(items)
        blk = block_of(t)
        room = end - t
        cands = [m for m in left if m["id"] != last] or [m for m in items if m["id"] != last] or list(items)
        fit = [m for m in cands if m["dur"] <= room] or [m for m in items if m["id"] != last and m["dur"] <= room]
        if not fit:                                    # kun oxirida hech bir kino sig'maydi — qolgan vaqt «efir tanaffusi» (ertaga 00:00 da davom)
            break
        fit.sort(key=lambda m: -_score(m, blk, rng, newest))
        pick = fit[0]
        left = [m for m in left if m["id"] != pick["id"]]
        e = min(end, t + pick["dur"])
        out.append([pick["id"], t, e])
        last = pick["id"]
        t = e + BREAK
    return out


def schedule(app, start: int) -> List[list]:
    """Berilgan kunning jadvali (kun boshlanishi — Toshkent 00:00). Bir marta tuziladi va saqlanadi."""
    key = _key(start)
    with _lock:
        sched = _mem.get(key)
        if sched is None:
            raw = app.setting(key)
            try:
                sched = json.loads(raw) if raw else None
            except ValueError:
                sched = None
            if not sched:
                sched = None
            if sched is not None:                      # o'chirilgan kino bo'lsa — jadval qayta tuziladi
                ids = {s[0] for s in sched}
                have = {r[0] for r in app.db.q(f"SELECT id FROM movies WHERE id IN ({','.join('?' * len(ids))})", list(ids))} if ids else set()
                if ids - have:
                    sched = None
            if sched is None:
                sched = build(pool(app), start)
                if not sched:                          # kutubxona bo'sh — bo'sh jadvalni eslab qolmaymiz (kino qo'shilishi bilan efir boshlanadi)
                    return []
                app.set_setting(key, json.dumps(sched, separators=(",", ":")))
                _cleanup(app, start)
            _mem[key] = sched
        return sched


def _cleanup(app, start: int) -> None:
    keep = {_key(start + d * 86400) for d in range(-KEEP_DAYS, 3)}
    for k in [k for k in list(_mem) if k not in keep]:
        _mem.pop(k, None)
    try:
        for r in app.db.q("SELECT key FROM settings WHERE key LIKE 'tv\\_%' ESCAPE '\\'"):
            if r[0] not in keep and len(r[0]) == 11:
                app.db.x("DELETE FROM settings WHERE key=?", (r[0],))
    except Exception:  # noqa: BLE001 — tozalash muvaffaqiyatsiz bo'lsa ham efir ishlayveradi
        log.exception("TV jadvalini tozalashda xatolik")


def window(app, ts: Optional[int] = None) -> List[list]:
    """Hozirgi vaqt atrofidagi slotlar: bugungi kun (to'liq) + ertangi kunning boshi."""
    ts = ts or now()
    d0 = day_start(ts)
    today = schedule(app, d0)
    tomorrow = schedule(app, d0 + 86400)[:6]
    return today + tomorrow


def current(slots: List[list], ts: int) -> int:
    """ts vaqtida efirdagi slot indeksi (tanaffusda — navbatdagi), topilmasa -1."""
    for i, s in enumerate(slots):
        if s[1] <= ts < s[2]:
            return i
    for i, s in enumerate(slots):
        if s[1] > ts:
            return i
    return -1
