"""🌐 Sayt — bot ichida ochiladigan Telegram Mini App.

Bo'limlar: 🎬 Kinolar, 🧸 Multfilmlar, 🎵 Musiqalar. Foydalanuvchi saytda tanlagan narsani
bot o'zi chatga yuboradi (majburiy obuna va Premium qoidalari saqlanadi).

Faqat Python'ning standart kutubxonasi bilan ishlaydi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from . import genres, keyboards
from .core import App, Ctx, router, start_payload
from .database import CATEGORIES
from .telegram import Forbidden, TelegramError
from .utils import normalize, truncate

log = logging.getLogger("webapp")

WEB_DIR = Path(__file__).resolve().parent / "web"
PAGE_SIZE = 30
INIT_DATA_MAX_AGE = 7 * 86400  # sayt shu muddatgacha qayta ochilmasa ham ishlayveradi


# ═════════════════════════ Telegram initData tekshiruvi ═════════════════════════

def check_init_data(init_data: str, token: str, max_age: int = INIT_DATA_MAX_AGE) -> Optional[dict]:
    """Telegram imzolagan initData ni tekshiradi. To'g'ri bo'lsa foydalanuvchini qaytaradi."""
    if not init_data:
        return None
    try:
        pairs = urllib.parse.parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    data = dict(pairs)
    received = data.pop("hash", "")
    if not received:
        return None
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    try:
        if time.time() - int(data.get("auth_date", "0")) > max_age:
            return None
        user = json.loads(data.get("user") or "null")
    except ValueError:
        return None
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        return None
    return user


# ═════════════════════════ API ═════════════════════════

GUEST = {"id": 0, "first_name": ""}  # ilova / brauzer: premium huquqisiz mehmon

def _poster_key(poster_id: Optional[str]) -> Optional[str]:
    return hashlib.sha1(poster_id.encode()).hexdigest()[:12] if poster_id else None


def _user_flags(app: App, uid: int):
    is_admin = app.is_admin(uid)
    vip = is_admin or app.is_premium(uid)
    return is_admin, vip


_YEAR_ONLY = re.compile(r"(19[2-9]\d|20[0-4]\d)")


def smart_query(query: str):
    """Qidiruv so'rovini tushunadi: faqat janr/davlat/yil so'zlaridan iborat bo'lsa («komediya 2019», «hind»)
    filtr sifatida, aks holda oddiy matn sifatida. Qaytaradi: (matn tokenlari, filtrlar)."""
    toks = normalize(query).split()
    meta, others = {}, []
    for t in toks:
        if _YEAR_ONLY.fullmatch(t):
            meta["year"] = int(t)
            continue
        g = genres.detect(t) if len(t) >= 4 else []
        if g:
            meta.setdefault("genre", g[0])
            continue
        c = genres.detect_country(t) if len(t) >= 4 else ""
        if c:
            meta["country"] = c
            continue
        others.append(t)
    return (toks, {}) if others else ([], meta)


def api_catalog(app: App, user: dict, qs: dict) -> dict:
    cat = qs.get("cat", "movie")
    if cat not in CATEGORIES and cat != "video":
        cat = "movie"
    sort = qs.get("sort") if qs.get("sort") in ("top", "rating") else "new"
    try:
        offset = max(0, int(qs.get("offset", "0")))
    except ValueError:
        offset = 0
    query = (qs.get("q") or "").strip()[:100]
    genre = qs.get("genre") if qs.get("genre") in genres.GENRES else None
    country = qs.get("country") if qs.get("country") in genres.COUNTRIES else None
    lang = qs.get("lang") if qs.get("lang") in genres.LANGS else None
    year = int(qs["year"]) if (qs.get("year") or "").isdigit() and len(qs["year"]) == 4 else None
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")

    link = (qs.get("k") or "").strip()  # kanal postidagi havola: ?k=15 (kino) yoki ?k=m3 (musiqa)
    if re.fullmatch(r"m?\d{1,9}", link):
        code = -int(link[1:]) if link.startswith("m") else int(link)
        movie = app.db.get_movie_by_code(code)
        rows = app.db.catalog(movie["category"], movie_id=movie["id"], limit=1) if movie else []
        more = False
    elif re.fullmatch(r"#?\d{1,9}", query):
        # raqam: kino kodi (va 4 xonali bo'lsa — chiqqan yil ham)
        movie = app.db.get_movie_by_code(int(query.lstrip("#")))
        wide = qs.get("all") == "1"  # qidiruv sahifasi har bir tur bo'yicha alohida so'raydi
        rows = []
        if movie and offset == 0 and (not wide or movie["category"] == cat):
            rows = app.db.catalog(movie["category"], movie_id=movie["id"], limit=1)
        more = False
        if wide and _YEAR_ONLY.fullmatch(query):
            extra = app.db.catalog(cat, sort, None, PAGE_SIZE + 1, offset, year=int(query))
            have = {r["id"] for r in rows}
            more = len(extra) > PAGE_SIZE
            rows = rows + [r for r in extra[:PAGE_SIZE] if r["id"] not in have]
    else:
        tokens, meta = smart_query(query)
        rows = []
        if meta:  # «komediya», «2019», «hind» — janr/yil/davlat bo'yicha
            rows = app.db.catalog(cat, sort, None, PAGE_SIZE + 1, offset, genre=genre or meta.get("genre"),
                                  country=country or meta.get("country"), year=year or meta.get("year"), lang=lang)
        if not rows:
            tokens = tokens or normalize(query).split()
            rows = app.db.catalog(cat, sort, tokens, PAGE_SIZE + 1, offset, genre=genre, country=country, year=year,
                                  lang=lang)
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

    items = [_item(r, premium_on, vip) for r in rows]
    out = {"ok": True, "items": items, "more": more, "counts": app.db.count_by_category()}
    if offset == 0 and not query and cat != "music" and not link:
        out["genres"] = [{"key": k, "label": genres.label(k), "n": n} for k, n in app.db.genre_counts(cat).items()]
        f = app.db.facets(cat)
        out["filters"] = {
            "country": [{"key": k, "label": genres.country_label(k), "n": f["country"][k]}
                        for k in genres.COUNTRIES if k in f["country"]],
            "year": [{"key": str(y), "label": str(y), "n": n} for y, n in sorted(f["year"].items(), reverse=True)],
            "lang": [{"key": k, "label": genres.lang_label(k), "n": f["lang"][k]} for k in genres.LANGS if k in f["lang"]],
        }
    return out


def api_collection(app: App, user: dict, qs: dict) -> dict:
    col = app.db.get_collection(int(qs["id"])) if (qs.get("id") or "").isdigit() else None
    if not col:
        return {"ok": False, "reason": "not_found"}
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    return {"ok": True, "title": col["title"],
            "items": [_item(r, premium_on, vip) for r in app.db.collection_movies(col["id"])]}


def api_rating(app: App, user: dict, qs: dict) -> dict:
    if not (qs.get("id") or "").isdigit():
        return {"ok": False, "reason": "not_found"}
    return dict(app.db.rating(int(qs["id"]), user["id"]), ok=True)


def api_rate(app: App, user: dict, body: dict) -> dict:
    """👍 / 👎 — faqat Telegram ichida (foydalanuvchi aniq bo'lishi kerak)."""
    try:
        movie_id, value = int(body.get("id")), int(body.get("v"))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "bad"}
    if value not in (1, -1) or not app.db.get_movie(movie_id):
        return {"ok": False, "reason": "not_found"}
    app.db.upsert_user(user)
    app.db.rate(user["id"], movie_id, value)
    return dict(app.db.rating(movie_id, user["id"]), ok=True)


def api_collections(app: App, user: dict) -> dict:
    return {"ok": True, "items": [{"id": c["id"], "title": c["title"], "n": c["n"]}
                                  for c in app.db.list_collections() if c["n"]]}


def api_history_clear(app: App, user: dict) -> dict:
    """Foydalanuvchining «Davom ettiring» tarixini o'chiradi (faqat o'zining)."""
    return {"ok": True, "n": app.db.clear_history(user["id"]) if user["id"] else 0}


def api_random(app: App, user: dict) -> dict:
    """🎲 Tasodifiy kino (kino, serial yoki multfilm)."""
    movie = app.db.random_movie()
    if not movie:
        return {"ok": False, "reason": "empty"}
    _, vip = _user_flags(app, user["id"])
    rows = app.db.catalog_rows([movie["id"]])
    return {"ok": True, "item": _item(rows[0], app.setting_bool("premium_enabled"), vip)} if rows else {"ok": False}


def api_popular(app: App, user: dict) -> dict:
    """🔥 Ommabop qidiruvlar (kamida 2 xil odam qidirgan so'rovlar)."""
    rows = app.db.popular_queries(int(time.time()) - 60 * 86400, 10)
    return {"ok": True, "queries": [r["query"] for r in rows]}


_searched_at: dict = {}


def api_searched(app: App, user: dict, body: dict) -> dict:
    """Sayt qidiruvini (so'rov va natijalar soni) «eng ko'p qidirilgan» statistikasiga yozadi."""
    q = str(body.get("q") or "").strip()[:100]
    norm = normalize(q)
    if len(norm) < 3:
        return {"ok": True}
    try:
        n = max(0, int(body.get("n") or 0))
    except (TypeError, ValueError):
        n = 0
    key = (user["id"], norm)
    now_t = time.time()
    if now_t - _searched_at.get(key, 0) < 60:
        return {"ok": True}
    if len(_searched_at) > 5000:
        _searched_at.clear()
    _searched_at[key] = now_t
    app.db.log_search(user["id"], q, norm, n)
    return {"ok": True}


def api_similar(app: App, user: dict, qs: dict) -> dict:
    try:
        movie_id = int(qs.get("id", "0"))
    except ValueError:
        return {"ok": False, "reason": "not_found"}
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    return {"ok": True, "items": [_item(r, premium_on, vip) for r in app.db.similar(movie_id, 12)]}


_YEAR_RE = re.compile(r"\b(19[2-9]\d|20[0-4]\d)\b")


def _item(r, premium_on: bool, vip: bool) -> dict:
    desc = r["description"] or ""
    keys = r.keys()
    year = r["year"] if "year" in keys and r["year"] else None
    if not year:
        m = _YEAR_RE.search(r["title"] + " " + desc)
        year = int(m.group(1)) if m else None
    return {
        "id": r["id"],
        "code": r["code"],
        "cat": r["category"],
        "title": r["title"],
        "desc": truncate(desc, 400),
        "year": year,
        "trailer": r["trailer"] if "trailer" in keys else None,
        "added": r["created_at"] if "created_at" in keys else 0,
        "genres": [{"key": k, "label": genres.label(k)} for k in genres.parse(r["genres"] if "genres" in keys else "")],
        "country": genres.country_label(r["country"]) if "country" in keys else "",
        "lang": genres.lang_label(r["lang"]) if "lang" in keys else "",
        "quality": genres.quality_text(r["quality"]) if "quality" in keys else "",
        "likes": r["likes"] if "likes" in keys else 0,
        "dislikes": r["dislikes"] if "dislikes" in keys else 0,
        "parts": r["parts"],
        "views": r["views"],
        "premium": bool(r["is_premium"]),
        "locked": bool(r["is_premium"]) and premium_on and not vip,
        "poster": _poster_key(r["poster_id"]),
    }


def api_home(app: App, user: dict) -> dict:
    """Bosh sahifa: almashib turadigan yangi kinolar (hero) va bo'limlar."""
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    db = app.db

    def pack(rows):
        return [_item(r, premium_on, vip) for r in rows]

    newest = []
    for cat in ("movie", "serial", "cartoon"):
        newest += list(db.catalog(cat, "new", None, 12))
    newest.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
    with_poster = [r for r in newest if r["poster_id"]]
    hero = (with_poster + [r for r in newest if not r["poster_id"]])[:6]
    history = pack(db.history(user["id"], 15)) if user["id"] else []
    foryou = pack(db.recommend(user["id"], 15)) if user["id"] else []
    from .handlers.user import search_ids  # aylanma importdan qochish uchun
    searched = []
    seen_ids = set()
    for q in db.popular_queries(int(time.time()) - 60 * 86400, 20):
        ids, _ = search_ids(app, q["norm"], scope="video", fuzzy_ok=False)
        for i in ids[:1]:
            if i not in seen_ids:
                seen_ids.add(i)
                searched.append(i)
    searched = pack(db.catalog_rows(searched[:15]))
    extra = []
    uz = db.catalog("video", "top", None, 15, lang="uz")
    if len(uz) >= 3:
        extra.append({"key": "uz", "title": "O'zbek tilida", "cat": "video", "f": {"lang": "uz"}, "items": pack(uz)})
    for key in ("action", "comedy", "fantasy"):
        rows_g = db.catalog("video", "top", None, 15, genre=key)
        if len(rows_g) >= 3:
            extra.append({"key": "g_" + key, "title": genres.name(key), "cat": "video", "f": {"genre": key},
                          "items": pack(rows_g)})
    collections = [{"id": c["id"], "title": c["title"], "items": pack(db.collection_movies(c["id"], 15))}
                   for c in db.list_collections() if c["n"]]
    return {
        "ok": True,
        "history": history,
        "foryou": foryou,
        "searched": searched,
        "extra": extra,
        "choice": pack(db.audience_choice(15)),
        "collections": collections,
        "hero": pack(hero),
        "rails": [
            {"key": "new", "title": "Yangi qo'shilganlar", "cat": "video", "sort": "new",
             "items": pack(db.catalog("video", "new", None, 15))},
            {"key": "top", "title": "Eng ko'p ko'rilgan", "cat": "video", "sort": "top",
             "items": pack(db.catalog("video", "top", None, 15))},
            {"key": "serial", "title": "Seriallar", "cat": "serial", "sort": "new",
             "items": pack(db.catalog("serial", "new", None, 15))},
            {"key": "cartoon", "title": "Multfilmlar", "cat": "cartoon", "sort": "new",
             "items": pack(db.catalog("cartoon", "new", None, 15))},
            {"key": "music", "title": "Musiqalar", "cat": "music", "sort": "new",
             "items": pack(db.catalog("music", "new", None, 15))},
        ],
        "counts": dict(db.count_by_category(), shorts=db.count_shorts()),
        "genres": [{"key": k, "label": genres.label(k), "n": n} for k, n in db.genre_counts("video").items()],
        "shorts": [dict(_item(r, premium_on, vip), short={"id": r["short_id"], "kind": r["short_kind"]})
                   for r in db.shorts_feed(SHORTS_PAGE, 0)],
    }


def _channel_url(app: App) -> Optional[str]:
    ref = app.setting("post_channel") or ""
    if ref.startswith("@"):
        return "https://t.me/" + ref[1:]
    for ch in app.db.list_channels():
        if (ch["url"] or "").startswith("https://t.me/"):
            return ch["url"]
    return None


def api_me(app: App, user: dict) -> dict:
    is_admin, vip = _user_flags(app, user["id"])
    return {
        "ok": True,
        "brand": app.brand,
        "bot": app.bot_username,
        "name": user.get("first_name") or "",
        "premium": vip,
        "premium_on": app.setting_bool("premium_enabled"),
        "admin": bool(is_admin and user["id"]),
        "counts": dict(app.db.count_by_category(), shorts=app.db.count_shorts()),
        "channel": _channel_url(app),
    }


# ───── ✏️ saytdagi admin: kinoni tahrirlash / o'chirish ─────

def _admin_only(app: App, user: dict) -> bool:
    return bool(user.get("id")) and app.is_admin(user["id"])


def api_admin_movie(app: App, user: dict, qs: dict) -> dict:
    """Tahrirlash oynasi uchun kinoning to'liq ma'lumoti va tanlov ro'yxatlari."""
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    try:
        m = app.db.get_movie(int(qs.get("id")))
    except (TypeError, ValueError):
        m = None
    if not m:
        return {"ok": False, "reason": "not_found"}
    return {
        "ok": True,
        "movie": {
            "id": m["id"], "code": m["code"], "title": m["title"], "description": m["description"] or "",
            "category": m["category"], "genres": genres.parse(m["genres"]), "year": m["year"] or 0,
            "country": m["country"], "lang": m["lang"], "quality": genres.quality_parse(m["quality"]),
            "premium": bool(m["is_premium"]), "group_link": m["group_link"] or "",
        },
        "meta": {
            "genres": [{"key": k, "label": genres.label(k)} for k in genres.GENRES],
            "countries": [{"key": k, "label": genres.country_label(k)} for k in genres.COUNTRIES],
            "langs": [{"key": k, "label": genres.lang_label(k)} for k in genres.LANGS],
            "qualities": [{"key": k, "label": v} for k, v in genres.QUALITIES.items()],
        },
    }


def api_admin_save(app: App, user: dict, body: dict) -> dict:
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    db = app.db
    try:
        m = db.get_movie(int(body.get("id")))
    except (TypeError, ValueError):
        m = None
    if not m:
        return {"ok": False, "reason": "not_found"}
    f: dict = {}
    if "title" in body:
        title = str(body["title"]).strip()[:200]
        if not title:
            return {"ok": False, "reason": "title"}
        f["title"] = title
    if "description" in body:
        desc = str(body["description"]).strip()[:3000]
        f["description"] = desc
        if desc != (m["description"] or ""):
            f["desc_html"] = ""  # eski formatlangan nusxa endi to'g'ri kelmaydi
    if "category" in body and m["category"] != "music" and body["category"] in ("movie", "serial", "cartoon"):
        f["category"] = body["category"]
    if m["category"] != "music":
        if "genres" in body and isinstance(body["genres"], list):
            f["genres"] = genres.dump([str(x) for x in body["genres"]])
        if "quality" in body and isinstance(body["quality"], list):
            f["quality"] = genres.quality_dump([str(x) for x in body["quality"]])
        if "country" in body and (body["country"] in genres.COUNTRIES or body["country"] == ""):
            f["country"] = body["country"]
        if "lang" in body and (body["lang"] in genres.LANGS or body["lang"] == ""):
            f["lang"] = body["lang"]
        if "year" in body:
            try:
                y = int(body["year"] or 0)
            except (TypeError, ValueError):
                return {"ok": False, "reason": "year"}
            if y and not 1900 <= y <= 2100:
                return {"ok": False, "reason": "year"}
            f["year"] = y
        if "group_link" in body:
            link = str(body["group_link"]).strip()[:300]
            if link and not re.match(r"https?://", link):
                return {"ok": False, "reason": "link"}
            f["group_link"] = link
    if "premium" in body:
        f["is_premium"] = bool(body["premium"])
    db.update_movie(m["id"], **f)
    db.__dict__.pop("_memo", None)  # filtr sanoqlari keshini yangilaymiz
    log.info("Admin %s sayt orqali #%s kinoni tahrirladi: %s", user["id"], m["id"], ", ".join(f))
    return {"ok": True}


def api_admin_delete(app: App, user: dict, body: dict) -> dict:
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    try:
        mid = int(body.get("id"))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "not_found"}
    if not app.db.get_movie(mid):
        return {"ok": False, "reason": "not_found"}
    app.db.delete_movie(mid)
    app.db.__dict__.pop("_memo", None)
    log.info("Admin %s sayt orqali #%s kinoni o'chirdi", user["id"], mid)
    return {"ok": True}


def api_support(app: App, user: dict) -> dict:
    """💝 «Bizni qo'llab-quvvatlang»: karta raqami (botdagi bilan bir xil) va Stars borligi."""
    from .handlers.payments import card_info
    digits, card, holder = card_info(app)
    return {"ok": True, "digits": digits, "card": card, "holder": re.sub(r"<[^>]+>|&\w+;", "", holder or "").strip(),
            "stars": app.setting_bool("donate_stars"), "bot": app.bot_username}


def api_admin_stats(app: App, user: dict) -> dict:
    """📊 Admin uchun statistika: foydalanuvchilar, kunlik yangilar, eng ko'p ko'rilganlar, topilmagan qidiruvlar."""
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    from .utils import day_start
    db = app.db
    t = int(time.time())
    today = day_start()
    since30 = t - 30 * 86400
    top = db.q("SELECT id, title, category, views FROM movies WHERE views>0 ORDER BY views DESC, id DESC LIMIT 10")
    failed = db.top_failed_queries(since30, 10)
    return {
        "ok": True,
        "users": {
            "total": db.count_users(), "today": db.count_joined_since(today),
            "week": db.count_joined_since(today - 6 * 86400), "month": db.count_joined_since(today - 29 * 86400),
            "active24": db.count_active_since(t - 86400), "premium": db.count_premium(),
            "blocked": db.count_blocked(),
        },
        "daily": [{"ts": ts, "n": n} for ts, n in db.joined_per_day(14)],
        "counts": dict(db.count_by_category(), shorts=db.count_shorts()),
        "views_total": db.val("SELECT COALESCE(SUM(views),0) FROM movies"),
        "top": [{"id": r["id"], "title": r["title"], "cat": r["category"], "views": r["views"]} for r in top],
        "failed": [{"q": r["query"], "n": r["n"]} for r in failed],
        "searches30": db.count_searches_since(since30),
        "requests_open": db.val("SELECT COUNT(*) FROM requests WHERE done_at=0"),
    }


def api_watch(app: App, user: dict, body: dict) -> dict:
    """Saytda tanlangan kinoni/musiqani bot foydalanuvchiga chatda yuboradi."""
    from .handlers.user import open_movie, premium_locked  # aylanma importdan qochish uchun

    try:
        movie = app.db.get_movie(int(body.get("id")))
    except (TypeError, ValueError):
        movie = None
    if not movie:
        return {"ok": False, "reason": "not_found"}
    uid = user["id"]
    update = {"message": {"message_id": 0, "date": int(time.time()), "from": user,
                          "chat": {"id": uid, "type": "private"}, "text": start_payload(movie["code"])}}
    ctx = Ctx(app, update)
    app.db.upsert_user(user)
    if not ctx.is_admin and app.flooding(uid):
        return {"ok": False, "reason": "flood"}
    try:
        if app.router.gate_check and not app.router.gate_check(ctx):
            return {"ok": False, "reason": "sub"}  # obuna oynasi chatga yuborildi
        locked = premium_locked(ctx, movie)
        open_movie(ctx, movie)
    except Forbidden:
        return {"ok": False, "reason": "blocked"}
    except TelegramError as exc:
        log.warning("Saytdan yuborishda xatolik: %s", exc)
        return {"ok": False, "reason": "error"}
    return {"ok": not locked, "reason": "premium" if locked else None}


def api_request(app: App, user: dict, body: dict) -> dict:
    """Saytda topilmagan kinoni so'rash (Telegram ichida): adminlarga yuboriladi, foydalanuvchiga chatda javob."""
    from .handlers.contact import send_request
    query = str(body.get("q") or "").strip()[:200]
    if len(query) < 2:
        return {"ok": False, "reason": "short"}
    update = {"message": {"message_id": 0, "date": int(time.time()), "from": user,
                          "chat": {"id": user["id"], "type": "private"}, "text": query}}
    ctx = Ctx(app, update)
    app.db.upsert_user(user)
    try:
        send_request(ctx, query)
    except Forbidden:
        return {"ok": False, "reason": "blocked"}
    except TelegramError as exc:
        log.warning("Saytdan so'rovda xatolik: %s", exc)
        return {"ok": False, "reason": "error"}
    return {"ok": True}


def poster_bytes(app: App, movie_id: int, cache_dir: Path) -> Optional[bytes]:
    movie = app.db.get_movie(movie_id)
    if not movie or not movie["poster_id"]:
        return None
    path = cache_dir / f"{movie_id}_{_poster_key(movie['poster_id'])}.jpg"
    if path.exists():
        return path.read_bytes()
    try:
        info = app.bot.call("getFile", {"file_id": movie["poster_id"]})
        data = app.bot.download_file(info["file_path"])
    except (TelegramError, KeyError) as exc:
        log.debug("Poster yuklanmadi (%s): %s", movie_id, exc)
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    for old in cache_dir.glob(f"{movie_id}_*.jpg"):
        try:
            old.unlink()
        except OSError:
            pass
    tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return data


# ═════════════════════════ 🎞 Shorts ═════════════════════════

SHORTS_PAGE = 8
_short_locks: dict = {}
_short_locks_guard = threading.Lock()


def api_shorts(app: App, user: dict, qs: dict) -> dict:
    try:
        offset = max(0, int(qs.get("offset", "0")))
    except ValueError:
        offset = 0
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    rows = app.db.shorts_feed(SHORTS_PAGE + 1, offset)
    items = []
    for r in rows[:SHORTS_PAGE]:
        it = _item(r, premium_on, vip)
        it["short"] = {"id": r["short_id"], "kind": r["short_kind"]}
        items.append(it)
    return {"ok": True, "items": items, "more": len(rows) > SHORTS_PAGE}


def short_file(app: App, short_id: int, folder: Path) -> Optional[Path]:
    """Shorts faylini Telegram'dan bir marta yuklab, diskda saqlaydi."""
    short = app.db.get_short(short_id)
    if not short:
        return None
    path = folder / (f"{short_id}.mp4" if short["kind"] == "video" else f"{short_id}.jpg")
    if path.exists():
        return path
    with _short_locks_guard:
        lock = _short_locks.setdefault(short_id, threading.Lock())
    with lock:  # bir vaqtda kelgan so'rovlar faylni ikki marta yuklamasin
        if path.exists():
            return path
        try:
            info = app.bot.call("getFile", {"file_id": short["file_id"]})
            data = app.bot.download_file(info["file_path"])
        except (TelegramError, KeyError) as exc:
            log.warning("Shorts yuklanmadi (%s): %s", short_id, exc)
            return None
        folder.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    return path


# ═════════════════════════ 🎵 Saytda musiqa tinglash ═════════════════════════

AUDIO_LIMIT = 20 * 1024 * 1024        # Telegram bot API shundan katta faylni bermaydi
AUDIO_CACHE_MAX = 2 * 1024 ** 3       # diskdagi musiqa keshi (2 GB) — oshsa eskilari o'chadi
AUDIO_TYPES = {".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".aac": "audio/aac",
               ".ogg": "audio/ogg", ".oga": "audio/ogg", ".opus": "audio/ogg", ".wav": "audio/wav",
               ".flac": "audio/flac"}
_audio_meta: dict = {}                # part_id -> (fayl yo'li Telegram'da, hajmi)


def _audio_sig(app: App, movie_id: int, exp: int) -> str:
    return hmac.new(app.config.token.encode(), f"audio:{movie_id}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def _audio_part(app: App, movie_id: int):
    movie = app.db.get_movie(movie_id)
    if not movie or movie["category"] != "music":
        return None, None
    parts = app.db.get_parts(movie_id)
    return movie, (parts[0] if parts else None)


def api_play(app: App, user: dict, body: dict, guest: bool) -> dict:
    """Musiqani saytda tinglash uchun vaqtinchalik imzolangan havola beradi."""
    try:
        movie, part = _audio_part(app, int(body.get("id")))
    except (TypeError, ValueError):
        movie, part = None, None
    if not movie or not part:
        return {"ok": False, "reason": "not_found"}
    _, vip = _user_flags(app, user["id"])
    if movie["is_premium"] and app.setting_bool("premium_enabled") and not vip:
        return {"ok": False, "reason": "premium"}
    if not guest:
        # Telegram ichida: majburiy obuna botdagidek ishlaydi (obuna oynasi chatga yuboriladi)
        update = {"message": {"message_id": 0, "date": int(time.time()), "from": user,
                              "chat": {"id": user["id"], "type": "private"}, "text": start_payload(movie["code"])}}
        ctx = Ctx(app, update)
        app.db.upsert_user(user)
        try:
            if app.router.gate_check and not app.router.gate_check(ctx):
                return {"ok": False, "reason": "sub"}
        except TelegramError:
            pass
    meta = _audio_meta.get(part["id"])
    if meta is None:
        try:
            info = app.bot.call("getFile", {"file_id": part["file_id"]})
        except TelegramError as exc:
            if exc.has("too big"):
                return {"ok": False, "reason": "big"}
            log.warning("Musiqa fayli olinmadi (%s): %s", movie_id_str(movie), exc)
            return {"ok": False, "reason": "error"}
        size = int(info.get("file_size") or 0)
        if size > AUDIO_LIMIT:
            return {"ok": False, "reason": "big"}
        meta = (info.get("file_path") or "", size)
        _audio_meta[part["id"]] = meta
    exp = int(time.time()) + 6 * 3600
    app.db.inc_views(movie["id"], part["id"])
    return {"ok": True, "url": f"/media/audio/{movie['id']}?e={exp}&s={_audio_sig(app, movie['id'], exp)}"}


def movie_id_str(movie) -> str:
    return f"{movie['id']}:{movie['title']}"


def audio_file(app: App, movie_id: int, folder: Path) -> Optional[Path]:
    movie, part = _audio_part(app, movie_id)
    if not part:
        return None
    for f in folder.glob(f"{part['id']}.*"):
        if f.suffix in AUDIO_TYPES:
            try:
                os.utime(f)  # oxirgi ishlatilgan vaqt — kesh tozalashda kerak
            except OSError:
                pass
            return f
    with _short_locks_guard:
        lock = _short_locks.setdefault(("a", part["id"]), threading.Lock())
    with lock:
        for f in folder.glob(f"{part['id']}.*"):
            if f.suffix in AUDIO_TYPES:
                return f
        try:
            info = app.bot.call("getFile", {"file_id": part["file_id"]})
            data = app.bot.download_file(info["file_path"], limit=AUDIO_LIMIT)
        except (TelegramError, KeyError) as exc:
            log.warning("Musiqa yuklanmadi (%s): %s", movie_id, exc)
            return None
        ext = os.path.splitext(info.get("file_path") or "")[1].lower()
        if ext not in AUDIO_TYPES:
            ext = ".mp3"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{part['id']}{ext}"
        tmp = path.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)
    _trim_cache(folder)
    return path


def _trim_cache(folder: Path) -> None:
    try:
        files = [f for f in folder.iterdir() if f.suffix in AUDIO_TYPES]
        total = sum(f.stat().st_size for f in files)
        if total <= AUDIO_CACHE_MAX:
            return
        for f in sorted(files, key=lambda f: f.stat().st_mtime):
            total -= f.stat().st_size
            f.unlink()
            if total <= AUDIO_CACHE_MAX * 0.8:
                break
    except OSError:
        pass


# ═════════════════════════ HTTP server ═════════════════════════

class RateLimiter:
    """Oddiy "chelak" (token bucket): bitta IP daqiqada ko'pi bilan `per_min` ta so'rov yubora oladi."""

    def __init__(self, per_min: int):
        self.rate = per_min / 60.0
        self.cap = float(per_min)
        self.buckets: dict = {}
        self.lock = threading.Lock()
        self.last_gc = time.time()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            if now - self.last_gc > 300:  # eski yozuvlarni tozalaymiz (xotira to'lmasin)
                self.buckets = {k: v for k, v in self.buckets.items() if now - v[1] < 120}
                self.last_gc = now
            tokens, t = self.buckets.get(key, (self.cap, now))
            tokens = min(self.cap, tokens + (now - t) * self.rate)
            if tokens < 1:
                self.buckets[key] = (tokens, now)
                return False
            self.buckets[key] = (tokens - 1, now)
            return True


def make_handler(app: App):
    cache_dir = Path(app.config.db_path).parent / "posters"
    shorts_dir = Path(app.config.db_path).parent / "shorts"
    audio_dir = Path(app.config.db_path).parent / "audio"

    api_limit = RateLimiter(240)    # katalog o'qish: daqiqasiga 240 tagacha
    write_limit = RateLimiter(40)   # yozish (baho, qidiruv logi, so'rov): daqiqasiga 40 tagacha

    class Handler(BaseHTTPRequestHandler):
        server_version = "MarvaridWeb/1.0"

        def _ip(self) -> str:
            # Railway proksisi haqiqiy IP ni X-Forwarded-For ning OXIRIGA qo'shadi (boshidagisini soxtalashtirish mumkin)
            xff = self.headers.get("X-Forwarded-For", "")
            return xff.split(",")[-1].strip() or self.client_address[0]

        def _limited(self, limiter: "RateLimiter") -> bool:
            if limiter.allow(self._ip()):
                return False
            self._json({"ok": False, "reason": "rate"}, 429)
            return True
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # oddiy so'rovlarni logga yozmaymiz
            log.debug("%s - %s", self.address_string(), fmt % args)

        # ───── javoblar ─────
        def _send(self, status: int, body: bytes, ctype: str, cache: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj: dict, status: int = 200) -> None:
            self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _send_file(self, path: Path, ctype: str) -> None:
            """Faylni Range (bo'lib-bo'lib) so'rovlarini qo'llab yuboradi — video ijrosi uchun kerak."""
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range", "")
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
            if m and size:
                a, b = m.group(1), m.group(2)
                if a:
                    start = int(a)
                    end = min(int(b), size - 1) if b else size - 1
                elif b:
                    start = max(0, size - int(b))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
            length = end - start + 1
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "public, max-age=604800, immutable")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            with open(path, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(65536, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        def _user(self) -> Optional[dict]:
            return check_init_data(self.headers.get("X-Init-Data", ""), app.config.token)

        # ───── GET ─────
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            qs = dict(urllib.parse.parse_qsl(url.query))
            try:
                if path in ("/", "/index.html"):
                    body = (WEB_DIR / "index.html").read_bytes()
                    return self._send(200, body, "text/html; charset=utf-8", "no-cache")
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                m = re.fullmatch(r"/api/poster/(\d+)", path)
                if m:
                    data = poster_bytes(app, int(m.group(1)), cache_dir)
                    if data is None:
                        return self._send(404, b"", "text/plain")
                    return self._send(200, data, "image/jpeg", "public, max-age=604800, immutable")
                m = re.fullmatch(r"/media/short/(\d+)", path)
                if m:
                    f = short_file(app, int(m.group(1)), shorts_dir)
                    if f is None:
                        return self._send(404, b"", "text/plain")
                    return self._send_file(f, "video/mp4" if f.suffix == ".mp4" else "image/jpeg")
                m = re.fullmatch(r"/media/audio/(\d+)", path)
                if m:
                    mid, exp = int(m.group(1)), qs.get("e", "")
                    if not (exp.isdigit() and int(exp) > time.time()
                            and hmac.compare_digest(qs.get("s", ""), _audio_sig(app, mid, int(exp)))):
                        return self._send(403, b"", "text/plain")
                    f = audio_file(app, mid, audio_dir)
                    if f is None:
                        return self._send(404, b"", "text/plain")
                    return self._send_file(f, AUDIO_TYPES.get(f.suffix, "audio/mpeg"))
                if path.startswith(("/pub/", "/api/")) and self._limited(api_limit):
                    return
                if path.startswith("/pub/"):
                    # 📱 Ilova va oddiy brauzer uchun: Telegram'siz, faqat katalog (mehmon sifatida)
                    path = "/api/" + path[5:]
                    user = GUEST
                elif path.startswith("/api/"):
                    user = self._user()
                    if not user:
                        return self._json({"ok": False, "reason": "auth"}, 401)
                if path.startswith("/api/"):
                    if path == "/api/me":
                        return self._json(api_me(app, user))
                    if path == "/api/home":
                        return self._json(api_home(app, user))
                    if path == "/api/catalog":
                        return self._json(api_catalog(app, user, qs))
                    if path == "/api/shorts":
                        return self._json(api_shorts(app, user, qs))
                    if path == "/api/similar":
                        return self._json(api_similar(app, user, qs))
                    if path == "/api/collections":
                        return self._json(api_collections(app, user))
                    if path == "/api/random":
                        return self._json(api_random(app, user))
                    if path == "/api/popular":
                        return self._json(api_popular(app, user))
                    if path == "/api/collection":
                        return self._json(api_collection(app, user, qs))
                    if path == "/api/support":
                        return self._json(api_support(app, user))
                    if path == "/api/admin/stats":
                        return self._json(api_admin_stats(app, user))
                    if path == "/api/admin/movie":
                        return self._json(api_admin_movie(app, user, qs))
                    if path == "/api/rating":
                        return self._json(api_rating(app, user, qs))
                return self._send(404, b"Not found", "text/plain")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                log.exception("Sayt so'rovida xatolik: %s", path)
                try:
                    self._json({"ok": False, "reason": "error"}, 500)
                except Exception:
                    pass

        do_HEAD = do_GET

        # ───── POST ─────
        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            try:
                if self._limited(write_limit):
                    return
                length = min(int(self.headers.get("Content-Length") or 0), 20_000)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except ValueError:
                    body = {}
                if not isinstance(body, dict):
                    body = {}
                if path == "/pub/play":  # 📱 ilova / brauzer — mehmon sifatida tinglash
                    return self._json(api_play(app, GUEST, body, guest=True))
                if path == "/pub/searched":
                    return self._json(api_searched(app, GUEST, body))
                user = self._user()
                if not user:
                    return self._json({"ok": False, "reason": "auth"}, 401)
                if path == "/api/play":
                    return self._json(api_play(app, user, body, guest=False))
                if path == "/api/watch":
                    return self._json(api_watch(app, user, body))
                if path == "/api/request":
                    return self._json(api_request(app, user, body))
                if path == "/api/history/clear":
                    return self._json(api_history_clear(app, user))
                if path == "/api/searched":
                    return self._json(api_searched(app, user, body))
                if path == "/api/rate":
                    return self._json(api_rate(app, user, body))
                if path == "/api/admin/save":
                    return self._json(api_admin_save(app, user, body))
                if path == "/api/admin/delete":
                    return self._json(api_admin_delete(app, user, body))
                return self._json({"ok": False, "reason": "not_found"}, 404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                log.exception("Sayt so'rovida xatolik: %s", path)
                try:
                    self._json({"ok": False, "reason": "error"}, 500)
                except Exception:
                    pass

    return Handler


@router.on_startup
def start_web(app: App) -> None:
    cfg = app.config
    if not cfg.webapp_url:
        # sayt manzili yo'q — «Menu» tugmasi odatiy buyruqlar ro'yxatini ochsin
        app.bot.safe("setChatMenuButton", {"menu_button": {"type": "commands"}})
    if not cfg.web_port:
        log.info("🌐 Sayt o'chiq (WEBAPP_URL yoki PORT sozlanmagan)")
        return
    try:
        server = ThreadingHTTPServer(("0.0.0.0", cfg.web_port), make_handler(app))
    except OSError as exc:
        log.error("🌐 Saytni ishga tushirib bo'lmadi (port %s): %s", cfg.web_port, exc)
        return
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="webapp", daemon=True).start()
    app.web_server = server
    if cfg.webapp_url:
        keyboards.SITE_ON = True
        # chat pastidagi «Menu» tugmasi saytni ochadi
        app.bot.safe("setChatMenuButton", {"menu_button": {
            "type": "web_app", "text": app.brand[:30] or "Sayt", "web_app": {"url": cfg.webapp_url}}})
        log.info("🌐 Sayt ishga tushdi: %s (port %s)", cfg.webapp_url, cfg.web_port)
    else:
        log.warning("🌐 Sayt %s-portda ishlayapti, lekin manzili noma'lum — .env ga WEBAPP_URL=https://... "
                    "yozing (Railway'da: Settings → Networking → Generate Domain)", cfg.web_port)
