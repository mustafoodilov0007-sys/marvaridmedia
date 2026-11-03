"""📈 Tahlil: foydalanuvchilar qayerdan kelmoqda, qaytib turishmi (retention), voronka, daromad, sayt tashriflari.

Hammasi Toshkent vaqti (UTC+5) bo'yicha. Shaxsiy ma'lumot ishlatilmaydi — faqat yig'ma sonlar.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Dict, List, Optional

from .utils import TZ

DAY = 86400
OFF = 18000   # UTC+5

SRC_LABELS = {
    "channel": "Kanal posti", "link": "Kino havolasi (ulashilgan)", "referral": "Do'st taklifi",
    "site": "Saytdan (so'rov/Premium)", "direct": "To'g'ridan-to'g'ri (bot qidiruvi)", "other": "Boshqa", "": "Eski (noma'lum)",
    # sayt manbalari
    "kanal": "Kanal → Mini App", "menyu": "Bot menyusi → Mini App", "boshqa": "Boshqa",
    "pwa": "O'rnatilgan ilova", "havola": "Ulashilgan havola", "telegram": "Telegram brauzeri",
    "qidiruv": "Qidiruv tizimi", "apk": "Android ilova",
}


def label(src: str) -> str:
    return SRC_LABELS.get(src, src)


def _day(ts: float) -> int:
    return int((ts + OFF) // DAY)


def _pct(a: int, b: int) -> Optional[float]:
    return round(a * 100.0 / b, 1) if b else None


def build(db, t: Optional[int] = None) -> Dict:
    t = int(t or time.time())
    today = _day(t)
    today_start = today * DAY - OFF
    since30 = today_start - 29 * DAY

    # ───── yangi foydalanuvchilar (30 kun) manba bo'yicha ─────
    rows = db.q("SELECT (joined_at + ?) / ? AS d, src, COUNT(*) AS n FROM users WHERE joined_at >= ? GROUP BY d, src",
                (OFF, DAY, since30))
    by_day: Dict[int, Dict[str, int]] = {}
    totals: Dict[str, int] = {}
    for r in rows:
        by_day.setdefault(r["d"], {})[r["src"]] = r["n"]
        totals[r["src"]] = totals.get(r["src"], 0) + r["n"]
    new_daily = [{"day": (d * DAY) - OFF, "n": sum(by_day.get(d, {}).values()), "by": by_day.get(d, {})}
                 for d in range(today - 29, today + 1)]
    grand = sum(totals.values())
    sources = [{"src": k, "label": label(k), "n": n, "pct": _pct(n, grand)} for k, n in sorted(totals.items(), key=lambda kv: -kv[1])]

    # ───── faollik ─────
    active = {
        "dau": db.val("SELECT COUNT(*) FROM users WHERE last_active >= ?", (today_start,)),
        "wau": db.val("SELECT COUNT(*) FROM users WHERE last_active >= ?", (today_start - 6 * DAY,)),
        "mau": db.val("SELECT COUNT(*) FROM users WHERE last_active >= ?", (today_start - 29 * DAY,)),
        "total": db.val("SELECT COUNT(*) FROM users"),
        "blocked": db.val("SELECT COUNT(*) FROM users WHERE is_blocked=1"),
    }
    active["stickiness"] = _pct(active["dau"], active["mau"])

    # ───── saqlanib qolish (retention): kohortalar haftalik ─────
    def ret(lo: int, hi: int, n_days: int):
        """[lo, hi) oralig'ida qo'shilganlar; ularning necha foizi qo'shilganidan keyin kamida n_days kun o'tib ham faol bo'lgan.
        Kohortaning eng yangi a'zosi hali n_days kun yashamagan bo'lsa — None."""
        size = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND joined_at < ?", (lo, hi))
        if not size or hi - 1 + n_days * DAY > t:
            return size, None
        back = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND joined_at < ? AND last_active >= joined_at + ?",
                      (lo, hi, n_days * DAY))
        return size, _pct(back, size)

    cohorts: List[Dict] = []
    for w in range(7, -1, -1):
        hi = today_start + DAY - w * 7 * DAY
        lo = hi - 7 * DAY
        size, d1 = ret(lo, hi, 1)
        d7 = ret(lo, hi, 7)[1]
        d30 = ret(lo, hi, 30)[1]
        cohorts.append({"from": lo, "to": hi - DAY, "n": size, "d1": d1, "d7": d7, "d30": d30})
    cohorts = [c for c in cohorts if c["n"]]

    def overall(n_days: int):
        elig = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND joined_at <= ?", (since30, t - n_days * DAY))
        back = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND joined_at <= ? AND last_active >= joined_at + ?",
                      (since30, t - n_days * DAY, n_days * DAY))
        return _pct(back, elig)

    # ───── voronka (30 kunda qo'shilganlar) ─────
    joined = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (since30,))
    watched = db.val("SELECT COUNT(*) FROM users u WHERE joined_at >= ? AND EXISTS (SELECT 1 FROM history h WHERE h.user_id=u.user_id)", (since30,))
    returned = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND last_active >= joined_at + ?", (since30, DAY))
    paid = db.val("SELECT COUNT(*) FROM users u WHERE joined_at >= ? AND EXISTS (SELECT 1 FROM payments p WHERE p.user_id=u.user_id"
                  " AND p.kind='premium' AND p.status='approved' AND p.amount>0)", (since30,))
    funnel = [{"label": "Qo'shildi", "n": joined, "pct": 100.0 if joined else None},
              {"label": "Kamida 1 kino ko'rdi", "n": watched, "pct": _pct(watched, joined)},
              {"label": "Keyingi kunlarda qaytdi", "n": returned, "pct": _pct(returned, joined)},
              {"label": "Premium sotib oldi", "n": paid, "pct": _pct(paid, joined)}]

    # ───── daromad (oxirgi 6 oy) ─────
    months = []
    dt = datetime.fromtimestamp(t, TZ)
    y, m = dt.year, dt.month
    for _ in range(6):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    rev = {k: {"month": k, "premium_uzs": 0, "donate_uzs": 0, "stars": 0, "n": 0} for k in months}
    for r in db.q("SELECT strftime('%Y-%m', created_at + ?, 'unixepoch') AS mo, kind, method, COUNT(*) AS n, COALESCE(SUM(amount),0) AS s"
                  " FROM payments WHERE status='approved' AND amount>0 AND method IN ('card','stars','provider') GROUP BY mo, kind, method", (OFF,)):
        e = rev.get(r["mo"])
        if not e:
            continue
        e["n"] += r["n"]
        if r["method"] == "stars":
            e["stars"] += r["s"]
        elif r["kind"] == "premium":
            e["premium_uzs"] += r["s"]
        else:
            e["donate_uzs"] += r["s"]

    # ───── ko'rishlar va sayt (14 kun) ─────
    d14 = today - 13
    plays = {r["day"]: r["n"] for r in db.q("SELECT day, SUM(n) AS n FROM view_days WHERE day >= ? GROUP BY day", (d14,))}
    visits = {r["day"]: r["n"] for r in db.q("SELECT day, COUNT(*) AS n FROM site_visits WHERE day >= ? GROUP BY day", (d14,))}
    hits = {r["day"]: r["n"] for r in db.q("SELECT day, SUM(n) AS n FROM hits WHERE day >= ? GROUP BY day", (d14,))}
    site_src: Dict[str, int] = {}
    for r in db.q("SELECT src, COUNT(*) AS n FROM site_visits WHERE day >= ? GROUP BY src", (d14,)):
        site_src[r["src"]] = site_src.get(r["src"], 0) + r["n"]
    for r in db.q("SELECT src, SUM(n) AS n FROM hits WHERE day >= ? GROUP BY src", (d14,)):
        site_src[r["src"]] = site_src.get(r["src"], 0) + r["n"]
    daily14 = [{"day": d * DAY - OFF, "plays": plays.get(d, 0), "tg": visits.get(d, 0), "web": hits.get(d, 0)} for d in range(d14, today + 1)]
    site_sources = [{"src": k, "label": label(k), "n": n} for k, n in sorted(site_src.items(), key=lambda kv: -kv[1])]

    return {"ok": True, "generated": t, "new_daily": new_daily, "new_total": grand, "sources": sources, "active": active,
            "retention": {"cohorts": cohorts, "d1": overall(1), "d7": overall(7), "d30": overall(30)},
            "funnel": funnel, "revenue": list(rev.values()), "daily14": daily14, "site_sources": site_sources}
