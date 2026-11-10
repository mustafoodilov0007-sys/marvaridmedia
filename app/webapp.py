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
import html
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from . import genres, keyboards, seo
from .core import App, Ctx, router, start_payload
from .database import CATEGORIES
from .telegram import Forbidden, TelegramError
from datetime import datetime
from .utils import TZ, normalize, truncate

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
    user["_sp"] = str(data.get("start_param") or "")[:64]   # (imzolangan) ishga tushirish parametri: qayerdan ochilgani
    return user


# ═════════════════════════ API ═════════════════════════

GUEST = {"id": 0, "first_name": ""}  # ilova / brauzer: premium huquqisiz mehmon


def _upsert(app: App, user: dict) -> None:
    """Telegram foydalanuvchisini «users» jadvaliga yozadi. Google akkauntlar (manfiy ID) u yerga kirmaydi."""
    if (user.get("id") or 0) > 0:
        app.db.upsert_user(user)


def _session_user(app: App, token: str) -> Optional[dict]:
    """X-Session sarlavhasidagi kirish sessiyasidan foydalanuvchi (Telegram yoki Google akkaunt)."""
    uid = app.db.session_user(token)
    if uid is None:
        return None
    if uid > 0:
        row = app.db.get_user(uid)
        return {"id": uid, "first_name": (row["first_name"] if row else "") or "", "username": (row["username"] if row else "") or "", "_web": True}
    acc = app.db.get_web_account(uid)
    if not acc:
        return None
    return {"id": uid, "first_name": acc["name"] or "Foydalanuvchi", "_web": True, "_photo": acc["photo"]}


def _google_verify(app: App, credential: str) -> Optional[dict]:
    """Google ID-token ni Google'ning o'zida tekshiradi (imzo, muddat). To'g'ri bo'lsa — foydalanuvchi ma'lumoti."""
    cid = app.config.google_client_id
    if not cid or not credential or len(credential) > 4096:
        return None
    try:
        url = "https://oauth2.googleapis.com/tokeninfo?" + urllib.parse.urlencode({"id_token": credential})
        with urllib.request.urlopen(url, timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception:       # noqa: BLE001 — tarmoq/format xatosi: kirish rad etiladi
        return None
    if d.get("aud") != cid or d.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return None
    if str(d.get("email_verified")).lower() != "true" or int(d.get("exp") or 0) < time.time():
        return None
    return d


def api_auth(app: App, path: str, body: dict) -> dict:
    """🔐 Saytga kirish: Telegram (bot orqali tasdiqlash) yoki Google."""
    db = app.db
    if path == "/pub/auth/tg/start":
        tok = db.create_login_token()
        return {"ok": True, "token": tok, "link": f"https://t.me/{app.bot_username}?start=wl_{tok}"}
    if path == "/pub/auth/tg/poll":
        tok = str(body.get("token") or "")[:60]
        row = db.get_login_token(tok) if tok else None
        if not row:
            return {"ok": False, "reason": "expired"}
        if row["status"] != "done":
            return {"ok": True, "status": "pending"}
        db.drop_login_token(tok)
        return {"ok": True, "status": "done", "session": db.create_session(row["user_id"]), "name": row["name"]}
    if path == "/pub/auth/google":
        info = _google_verify(app, str(body.get("credential") or ""))
        if not info:
            return {"ok": False, "reason": "google"}
        uid = db.upsert_web_account("google", str(info.get("sub")), info.get("email") or "", info.get("name") or info.get("given_name") or "Foydalanuvchi",
                                    info.get("picture") or "")
        return {"ok": True, "session": db.create_session(uid), "name": info.get("name") or ""}
    return {"ok": False, "reason": "not_found"}

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
    fuzzy = False
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
        if not rows and offset == 0 and len(query) >= 3 and not (genre or country or year or lang):
            # 🔎 xato yozilgan nom (botdagi kabi): eng o'xshash kinolar
            from .handlers.user import search_ids
            ids, approx = search_ids(app, normalize(query), scope="music" if cat == "music" else "video")
            for mid in (ids if approx else [])[:12]:
                rows += list(app.db.catalog(cat, movie_id=mid, limit=1))
            fuzzy = bool(rows)

    items = [_item(r, premium_on, vip) for r in rows]
    out = {"ok": True, "items": items, "more": more, "counts": app.db.count_by_category()}
    if fuzzy:
        out["fuzzy"] = True
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


# ═════════════════════════ 💬 Izohlar ═════════════════════════

def _comment_movie(app: App, mid) -> Optional[dict]:
    try:
        m = app.db.get_movie(int(mid))
    except (TypeError, ValueError):
        return None
    return m if m and m["category"] != "music" else None


def api_comments(app: App, user: dict, qs: dict) -> dict:
    from . import comments
    m = _comment_movie(app, qs.get("id"))
    if not m:
        return {"ok": False, "reason": "not_found"}
    try:
        offset = max(0, int(qs.get("offset", "0")))
    except ValueError:
        offset = 0
    uid = user.get("id") or 0
    out = comments.listing(app, m["id"], uid, qs.get("sort", "new"), offset)
    out.update({"ok": True, "can_post": bool(uid) and not app.db.is_contact_banned(uid), "admin": app.is_admin(uid) if uid else False,
                "max": comments.MAX_LEN})
    return out


_reply_notified: dict = {}


def _notify_reply(app: App, par, user: dict, movie, text: str) -> None:
    """Izohga javob yozilganda izoh egasiga (Telegram akkaunt bo'lsa) botdan xabar boradi. Soatiga ko'pi bilan 5 ta."""
    try:
        target = int(par["user_id"])
    except (TypeError, ValueError, KeyError):
        return
    if target <= 0 or target == user["id"]:
        return
    u = app.db.get_user(target)
    if not u or u["is_blocked"]:
        return
    hour = int(time.time() // 3600)
    key = (target, hour)
    if _reply_notified.get(key, 0) >= 5:
        return
    _reply_notified[key] = _reply_notified.get(key, 0) + 1
    for k in [k for k in _reply_notified if k[1] != hour]:
        _reply_notified.pop(k, None)
    name = html.escape((user.get("first_name") or "Foydalanuvchi")[:40])
    snippet = html.escape(text[:160] + ("…" if len(text) > 160 else ""))
    msg = (f"💬 <b>{name}</b> izohingizga javob yozdi\n🎬 {html.escape(movie['title'][:80])}\n\n«{snippet}»")
    base = (app.config.webapp_url or "").rstrip("/")
    markup = None
    if base and movie["code"] > 0:
        markup = {"inline_keyboard": [[{"text": "💬 Javobni ko'rish", "url": f"{base}/kino/{movie['code']}"}]]}

    def work() -> None:
        try:
            app.bot.send_message(target, msg, markup)
        except Forbidden:
            app.db.set_blocked(target, True)
        except TelegramError as exc:
            log.debug("Javob xabari yetmadi (%s): %s", target, exc)

    threading.Thread(target=work, name="reply-notify", daemon=True).start()


def api_comment_post(app: App, user: dict, body: dict) -> dict:
    from . import comments
    m = _comment_movie(app, body.get("id"))
    if not m:
        return {"ok": False, "reason": "not_found"}
    text = comments.clean(body.get("body"))
    uid = user["id"]
    _upsert(app, user)
    parent = 0
    if body.get("parent"):
        try:
            par = app.db.get_comment(int(body["parent"]))
        except (TypeError, ValueError):
            par = None
        if not par or par["movie_id"] != m["id"] or par["status"] != "ok":
            return {"ok": False, "reason": "not_found"}
        parent = par["parent_id"] or par["id"]          # javob faqat bir pog'ona: javobga javob — asosiy izoh ostida
    reason = comments.check(app, user, m["id"], text, app.is_admin(uid))
    if reason:
        return {"ok": False, "reason": reason, "msg": comments.REASONS.get(reason, "")}
    cid = app.db.add_comment(m["id"], uid, text, parent)
    if body.get("parent"):
        _notify_reply(app, par, user, m, text)
    row = app.db.q1(app.db._COMMENT_SQL + " WHERE c.id=?", (uid, cid))
    it = comments.item(app, row, uid)
    it["replies"] = []
    return {"ok": True, "item": it, "total": app.db.count_comments(m["id"])}


def api_comment_like(app: App, user: dict, body: dict) -> dict:
    try:
        res = app.db.toggle_comment_like(int(body.get("cid")), user["id"])
    except (TypeError, ValueError):
        res = None
    if res is None:
        return {"ok": False, "reason": "not_found"}
    return {"ok": True, "liked": res[0], "likes": res[1]}


def api_comment_report(app: App, user: dict, body: dict) -> dict:
    from . import comments
    try:
        cid = int(body.get("cid"))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "not_found"}
    row = app.db.get_comment(cid)
    n = app.db.report_comment(cid, user["id"], comments.HIDE_AT)
    if n is None:
        return {"ok": False, "reason": "not_found"}
    if row and n == comments.HIDE_AT:       # yashirildi — bosh adminlarga xabar
        from .handlers.audit import notify_hidden_comment
        notify_hidden_comment(app, cid)
    return {"ok": True, "hidden": n >= comments.HIDE_AT}


def api_comment_delete(app: App, user: dict, body: dict) -> dict:
    try:
        cid = int(body.get("cid"))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "not_found"}
    row = app.db.get_comment(cid)
    if not row:
        return {"ok": False, "reason": "not_found"}
    admin = app.is_admin(user["id"])
    if row["user_id"] != user["id"] and not admin:
        return {"ok": False, "reason": "forbidden"}
    app.db.delete_comment(cid)
    if admin and row["user_id"] != user["id"]:
        from .handlers.audit import audit
        audit(app, user["id"], "comment_del", f"{row['body'][:80]} (user {row['user_id']})")
    return {"ok": True}


def api_comment_ban(app: App, user: dict, body: dict) -> dict:
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    row = None
    try:
        row = app.db.get_comment(int(body.get("cid")))
    except (TypeError, ValueError):
        pass
    if not row or app.is_admin(row["user_id"]):
        return {"ok": False, "reason": "not_found"}
    banned = not app.db.is_contact_banned(row["user_id"])
    app.db.set_contact_banned(row["user_id"], banned)
    from .handlers.audit import audit
    audit(app, user["id"], "ban", f"{row['user_id']}: izoh — {'cheklandi' if banned else 'cheklash olindi'}")
    return {"ok": True, "banned": banned}


def _genre_collections(app: App, top: int = 6, min_n: int = 3) -> list:
    """Avtomatik kolleksiyalar: kinosi eng ko'p janrlar — o'sha janr nomi bilan (Marvel/DC alohida kolleksiyaga ega)."""
    counts = [(k, n) for k, n in app.db.genre_counts("video").items() if n >= min_n and k not in genres.AUTO_COLLECTIONS]
    counts.sort(key=lambda kn: -kn[1])
    out = []
    for k, n in counts[:top]:
        rows = app.db.catalog("video", "top", None, 8, genre=k)
        out.append({"id": "g_" + k, "title": genres.name(k), "n": n,
                    "covers": [{"id": r["id"], "poster": _poster_key(r["poster_id"])} for r in rows if r["poster_id"]][:4]})
    return out


def api_collection(app: App, user: dict, qs: dict) -> dict:
    gid = qs.get("id") or ""
    if gid.startswith("g_") and gid[2:] in genres.GENRES:
        _, vip = _user_flags(app, user["id"])
        premium_on = app.setting_bool("premium_enabled")
        rows = app.db.catalog("video", "top", None, 200, genre=gid[2:])
        return {"ok": True, "title": genres.name(gid[2:]), "items": [_item(r, premium_on, vip) for r in rows]}
    col = app.db.get_collection(int(qs["id"])) if (qs.get("id") or "").isdigit() else None
    if not col:
        return {"ok": False, "reason": "not_found"}
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    return {"ok": True, "title": col["title"],
            "items": [_item(r, premium_on, vip) for r in app.db.collection_movies(col["id"])]}


def api_mystats(app: App, user: dict) -> dict:
    """«Sizning yilingiz» kartasi: faqat kirgan foydalanuvchi uchun, joriy yil (Toshkent vaqti) bo'yicha."""
    uid = user["id"]
    if not uid or uid < 0:
        return {"ok": False, "reason": "auth"}
    now_t = datetime.now(TZ)
    since = int(datetime(now_t.year, 1, 1, tzinfo=TZ).timestamp())
    st = app.db.user_stats(uid, since)
    st["genres"] = [{"key": k, "label": genres.label(k)} for k in st["genres"]]
    return dict(st, ok=True, year=now_t.year)


def api_myratings(app: App, user: dict) -> dict:
    """⭐ Baholarim: foydalanuvchi 👍/👎 bergan kinolar (oxirgisi birinchi)."""
    if not user.get("id"):
        return {"ok": True, "items": []}
    rows = app.db.q("SELECT movie_id, value FROM ratings WHERE user_id=? ORDER BY at DESC LIMIT 60", (user["id"],))
    mine = {r["movie_id"]: r["value"] for r in rows}
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    items = []
    for r in app.db.catalog_rows(list(mine)):
        it = _item(r, premium_on, vip)
        it["mine"] = mine[r["id"]]
        items.append(it)
    return {"ok": True, "items": items}


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
    _upsert(app, user)
    app.db.rate(user["id"], movie_id, value)
    return dict(app.db.rating(movie_id, user["id"]), ok=True)


class _Server(ThreadingHTTPServer):
    request_queue_size = 256          # standart 5 — birdaniga ko'p odam kirsa ulanishlar rad etilardi


def api_collections(app: App, user: dict) -> dict:
    out = []
    for c in app.db.list_collections():
        if not c["n"]:
            continue
        covers = [{"id": r["id"], "poster": _poster_key(r["poster_id"])} for r in app.db.collection_movies(c["id"], 8) if r["poster_id"]][:4]
        out.append({"id": c["id"], "title": c["title"], "n": c["n"], "covers": covers})
    return {"ok": True, "items": out + _genre_collections(app, top=12)}


def api_tv(app: App, user: dict) -> dict:
    """📺 Marvarid TV: bugungi jadval (+ ertangi kunning boshi), hozir efirdagi kino server vaqti bo'yicha."""
    from . import tv
    from .handlers import trial
    ts = int(time.time())
    _, vip = _user_flags(app, user["id"])
    if app.setting_bool("premium_enabled") and not vip:      # 📺 TV faqat Premium egalari uchun (sinov — 1 kun hammaga)
        days = trial.trial_days(app)
        can = bool(days) and user["id"] > 0 and app.db.can_claim_trial(user["id"])
        return {"ok": True, "locked": True, "now": ts, "trial_days": days if can else 0, "guest": user["id"] <= 0}
    slots = tv.window(app, ts)
    if not slots:
        return {"ok": True, "empty": True, "now": ts}
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")
    ids = list(dict.fromkeys(sl[0] for sl in slots))
    items = {r["id"]: _item(r, premium_on, vip) for r in app.db.catalog_rows(ids)}
    out = [{"s": sl[1], "e": sl[2], "b": tv.block_of(sl[1])["title"], "it": items[sl[0]]} for sl in slots if sl[0] in items]
    if not out:
        return {"ok": True, "empty": True, "now": ts}
    return {"ok": True, "now": ts, "slots": out, "cur": tv.current([[0, o["s"], o["e"]] for o in out], ts)}


def api_tv_trial(app: App, user: dict) -> dict:
    """🎁 TV uchun bepul sinov Premium'ni (bir marta) oladi — hali olmagan har bir foydalanuvchi."""
    from .handlers import trial
    days = trial.trial_days(app)
    if user["id"] <= 0:
        return {"ok": False, "reason": "login"}
    if not days or not app.setting_bool("premium_enabled"):
        return {"ok": False, "reason": "off"}
    if not app.db.claim_trial(user["id"]):
        return {"ok": False, "reason": "used"}
    app.db.grant_premium(user["id"], days)
    return {"ok": True, "days": days}


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
        "year_end": r["year_end"] if "year_end" in keys and r["year_end"] and year and r["year_end"] > year else None,
        "trailer": r["trailer"] if "trailer" in keys else None,
        "added": r["created_at"] if "created_at" in keys else 0,
        "genres": [{"key": k, "label": genres.label(k)} for k in genres.parse(r["genres"] if "genres" in keys else "")],
        "country": genres.country_label(r["country"]) if "country" in keys else "",
        "lang": genres.lang_label(r["lang"]) if "lang" in keys else "",
        "quality": genres.quality_text(r["quality"]) if "quality" in keys else "",
        "duration": r["duration"] if "duration" in keys else 0,
        "age": r["age"] if "age" in keys and r["age"] else None,
        "imdb": r["imdb"] if "imdb" in keys and r["imdb"] else None,
        "likes": r["likes"] if "likes" in keys else 0,
        "dislikes": r["dislikes"] if "dislikes" in keys else 0,
        "parts": r["parts"],
        "views": r["views"],
        "premium": bool(r["is_premium"]),
        "locked": bool(r["is_premium"]) and premium_on and not vip,
        "poster": _poster_key(r["poster_id"]),
        "glink": (r["group_link"] if "group_link" in keys else "") if r["category"] in ("serial", "cartoon") else "",
        "wurl": (r["watch_url"] if "watch_url" in keys else "") or "",
        "turl": (r["trailer_url"] if "trailer_url" in keys else "") or "",
    }


def api_home(app: App, user: dict) -> dict:
    """Bosh sahifa. Mehmonlar uchun 15 soniya keshlanadi (ko'p odam birdaniga kirganda baza bo'shashmaydi)."""
    if user["id"]:
        return _api_home(app, user)
    cache = app.__dict__.setdefault("_home_cache", {})
    hit = cache.get("guest")
    if hit and time.time() - hit[0] < 15:
        return hit[1]
    data = _api_home(app, user)
    cache["guest"] = (time.time(), data)
    return data


def _api_home(app: App, user: dict) -> dict:
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
    if history:   # serialda qaysi qismda to'xtagani — «Davom ettiring» kartasida «3-qism» belgisi
        resume = db.resume_parts(user["id"], [x["id"] for x in history])
        for x in history:
            if resume.get(x["id"]):
                x["resume"] = resume[x["id"]]
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
    collections = [{"id": c["id"], "title": c["title"], "n": c["n"],
                    "covers": [{"id": r["id"], "poster": _poster_key(r["poster_id"])} for r in db.collection_movies(c["id"], 8) if r["poster_id"]][:4]}
                   for c in db.list_collections() if c["n"]][:12] + _genre_collections(app)
    return {
        "ok": True,
        "history": history,
        "foryou": foryou,
        "searched": searched,
        "extra": extra,
        "choice": pack(db.audience_choice(15)),
        "collections": collections,
        "weekly": pack(db.weekly_top(10)),
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
    if user["id"] > 0 and not user.get("_web"):   # tahlil: Telegram foydalanuvchisi saytni ochdi (kuniga bir marta), manba — start_param
        sp = user.get("_sp", "")
        try:
            app.db.site_visit(user["id"], "kanal" if sp.startswith("k") else ("menyu" if not sp else "boshqa"))
        except Exception:  # noqa: BLE001 — tahlil hech qachon asosiy ishni to'smasligi kerak
            pass
    return {
        "ok": True,
        "brand": app.brand,
        "bot": app.bot_username,
        "name": user.get("first_name") or "",
        "web": bool(user.get("_web")),          # brauzerda hisob bilan kirgan
        "tg": user["id"] > 0,                   # Telegram hisobi (botga yuborish mumkin)
        "photo": user.get("_photo") or "",
        "google": app.config.google_client_id,  # bo'sh bo'lsa — «Google orqali kirish» yashirin
        "premium": vip,
        "premium_on": app.setting_bool("premium_enabled"),
        "premium_until": app.db.premium_until(user["id"]) if user["id"] else 0,
        "miniapp": app.miniapp_link(),
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
            "category": m["category"], "genres": genres.parse(m["genres"]), "year": m["year"] or 0, "year_end": m["year_end"] or 0,
            "country": m["country"], "lang": m["lang"], "quality": genres.quality_parse(m["quality"]),
            "premium": bool(m["is_premium"]), "group_link": m["group_link"] or "", "watch_url": m["watch_url"] or "", "trailer_url": m["trailer_url"] or "",
            "duration_min": round((m["duration"] or 0) / 60), "age": m["age"] or 0, "imdb": m["imdb"] or "",
        },
        "meta": {
            "ages": [6, 12, 16, 18],
            "genres": [{"key": k, "label": genres.label(k)} for k in genres.GENRES],
            "countries": [{"key": k, "label": genres.country_label(k)} for k in genres.COUNTRIES],
            "langs": [{"key": k, "label": genres.lang_label(k)} for k in genres.LANGS],
            "qualities": [{"key": k, "label": v} for k, v in genres.QUALITIES.items()],
        },
    }


def api_admin_tmdb(app: App, user: dict, qs: dict) -> dict:
    """🌐 TMDB: qidiruv (?q=nomi&year=) yoki to'liq ma'lumot (?kind=movie&id=123). Faqat admin."""
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    from . import tmdb
    t = tmdb.get(app)
    if not t.configured:
        return {"ok": False, "reason": "not_configured"}
    try:
        if qs.get("id"):
            return {"ok": True, "data": t.details(qs.get("kind", ""), int(qs["id"]))}
        year = int(qs["year"]) if (qs.get("year") or "").isdigit() else None
        return {"ok": True, "items": t.search(qs.get("q", ""), year)}
    except (tmdb.TmdbError, ValueError, KeyError) as exc:
        return {"ok": False, "reason": "tmdb", "message": str(exc)[:150]}


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
            raw = str(body["year"] or "").strip()
            if raw in ("", "0"):
                f["year"], f["year_end"] = 0, 0
            else:
                yy = genres.parse_years(raw)
                if not yy:
                    return {"ok": False, "reason": "year"}
                f["year"], f["year_end"] = yy
        if "duration_min" in body:
            try:
                dm = int(float(body["duration_min"] or 0))
            except (TypeError, ValueError):
                return {"ok": False, "reason": "duration"}
            if not 0 <= dm <= 1500:
                return {"ok": False, "reason": "duration"}
            f["duration"] = dm * 60
        if "age" in body:
            try:
                age = int(body["age"] or 0)
            except (TypeError, ValueError):
                return {"ok": False, "reason": "age"}
            f["age"] = age if age in (0, 6, 12, 16, 18) else 0
        if "imdb" in body:
            raw = str(body["imdb"]).strip().replace(",", ".")
            if raw:
                try:
                    val = float(raw)
                except ValueError:
                    return {"ok": False, "reason": "imdb"}
                if not 0 < val <= 10:
                    return {"ok": False, "reason": "imdb"}
                raw = f"{val:.1f}"
            f["imdb"] = raw
        if "watch_url" in body:
            wu = str(body["watch_url"]).strip()[:400]
            if wu and not re.match(r"https?://", wu):
                return {"ok": False, "reason": "wlink"}
            f["watch_url"] = wu
        if "trailer_url" in body:
            tu = str(body["trailer_url"]).strip()[:400]
            if tu and not re.match(r"https?://", tu):
                return {"ok": False, "reason": "turl"}
            f["trailer_url"] = tu
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
    m = app.db.get_movie(mid)
    app.db.trash_movie(mid, user["id"])      # 30 kun chiqindi qutisida saqlanadi
    app.db.drop_announces(mid)
    from .handlers.audit import audit
    audit(app, user["id"], "movie_del", f"{m['title']} (kod {m['code']}) — saytdan")
    app.db.__dict__.pop("_memo", None)
    log.info("Admin %s sayt orqali #%s kinoni o'chirdi", user["id"], mid)
    return {"ok": True}


def api_support(app: App, user: dict) -> dict:
    """💝 «Bizni qo'llab-quvvatlang»: karta raqami (botdagi bilan bir xil) va Stars borligi."""
    from .handlers.payments import card_info
    digits, card, holder = card_info(app)
    return {"ok": True, "digits": digits, "card": card, "holder": re.sub(r"<[^>]+>|&\w+;", "", holder or "").strip(),
            "stars": app.setting_bool("donate_stars"), "bot": app.bot_username}


def api_admin_analytics(app: App, user: dict) -> dict:
    """📈 Tahlil: manbalar, faollik, saqlanib qolish, voronka, daromad (faqat admin)."""
    if not _admin_only(app, user):
        return {"ok": False, "reason": "forbidden"}
    from . import analytics
    return analytics.build(app.db)


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
    if uid < 0:      # Google akkaunt: Telegram chati yo'q — mijoz botga havola ochadi
        return {"ok": False, "reason": "no_telegram"}
    update = {"message": {"message_id": 0, "date": int(time.time()), "from": user,
                          "chat": {"id": uid, "type": "private"}, "text": start_payload(movie["code"])}}
    ctx = Ctx(app, update)
    _upsert(app, user)
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
    if user["id"] < 0:
        return {"ok": False, "reason": "no_telegram"}
    update = {"message": {"message_id": 0, "date": int(time.time()), "from": user,
                          "chat": {"id": user["id"], "type": "private"}, "text": query}}
    ctx = Ctx(app, update)
    _upsert(app, user)
    try:
        send_request(ctx, query)
    except Forbidden:
        return {"ok": False, "reason": "blocked"}
    except TelegramError as exc:
        log.warning("Saytdan so'rovda xatolik: %s", exc)
        return {"ok": False, "reason": "error"}
    return {"ok": True}


try:                                # Pillow bo'lsa — kichik nusxalar (tez yuklanadi); bo'lmasa — asl rasm
    from PIL import Image as _PIL
except Exception:                   # noqa: BLE001
    _PIL = None
_poster_fail: dict = {}             # yuklanmagan posterni 60 soniya qayta so'ramaymiz (Telegramga yuklama tushmasin)


def _webp_ok() -> bool:
    try:
        from PIL import features
        return bool(_PIL is not None and features.check("webp"))
    except Exception:  # noqa: BLE001
        return False


def _thumb(data: bytes, width: int, webp: bool = False) -> bytes:
    import io
    try:
        im = _PIL.open(io.BytesIO(data))
        if im.width <= width and not webp:
            return data
        im = im.convert("RGB")
        if im.width > width:
            im.thumbnail((width, width * 2))
        out = io.BytesIO()
        if webp:                      # WebP: JPEG ga qaraganda ~30% kichik — sahifa tezroq ochiladi
            im.save(out, "WEBP", quality=78, method=4)
        else:
            im.save(out, "JPEG", quality=80, optimize=True, progressive=True)
        return out.getvalue()
    except Exception:               # noqa: BLE001 — buzuq rasm: asl nusxa qaytadi
        return data


def poster_bytes(app: App, movie_id: int, cache_dir: Path, width: int = 0, webp: bool = False) -> Optional[bytes]:
    movie = app.db.get_movie(movie_id)
    if not movie or not movie["poster_id"]:
        return None
    key = _poster_key(movie["poster_id"])
    path = cache_dir / f"{movie_id}_{key}.jpg"
    if width and _PIL is not None:
        small = cache_dir / f"{movie_id}_{key}_{width}.{'webp' if webp else 'jpg'}"
        if small.exists():
            return small.read_bytes()
        full = poster_bytes(app, movie_id, cache_dir, 0)
        if full is None:
            return None
        data = _thumb(full, width, webp)
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = small.with_suffix(f".{threading.get_ident()}.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, small)
        return data
    if path.exists():
        return path.read_bytes()
    if time.time() - _poster_fail.get(movie_id, 0) < 60:
        return None
    try:
        info = app.bot.call("getFile", {"file_id": movie["poster_id"]})
        data = app.bot.download_file(info["file_path"])
    except (TelegramError, KeyError) as exc:
        log.debug("Poster yuklanmadi (%s): %s", movie_id, exc)
        _poster_fail[movie_id] = time.time()
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    for old in list(cache_dir.glob(f"{movie_id}_*.jpg")) + list(cache_dir.glob(f"{movie_id}_*.webp")):
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
            log.warning("Shorts yuklanmadi (%s, %s): %r — Telegram fayl bermadi (20 MB dan katta yoki file_id boshqa botniki)",
                        short_id, short["kind"], exc)
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
        _upsert(app, user)
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

_gz_cache: dict = {}


# 📦 Sayt fayllari bo'laklarga ajratilgan: css/*.css va js/app/*.js tartib bo'yicha birlashtirilib beriladi
# (bo'laklar bitta IIFE ichida — umumiy o'zgaruvchilar saqlanadi). Versiya (?v=) — mazmun xeshi: o'zgarsa brauzer yangisini oladi.
_ASSETS = {
    "app.css": ("css", "*.css", "text/css; charset=utf-8"),
    "app.js": ("js/app", "*.js", "text/javascript; charset=utf-8"),
    "i18n.js": ("js", "i18n.js", "text/javascript; charset=utf-8"),
}
_asset_cache: dict = {}


def web_asset(name: str):
    """(bayt, mazmun turi, versiya) yoki None. Fayllar o'zgarsa (mtime) avtomatik qayta yig'iladi."""
    spec = _ASSETS.get(name)
    if not spec:
        return None
    files = sorted((WEB_DIR / spec[0]).glob(spec[1]))
    key = tuple((f.name, f.stat().st_mtime_ns) for f in files)
    hit = _asset_cache.get(name)
    if hit and hit[0] == key:
        return hit[1]
    body = "\n".join(f.read_text(encoding="utf-8") for f in files).encode("utf-8")
    res = (body, spec[2], hashlib.sha1(body).hexdigest()[:10])
    _asset_cache[name] = (key, res)
    return res


def _gzip_cached(body: bytes) -> bytes:
    """Sayt sahifasi (katta va o'zgarmas) — bir marta siqiladi; JSON javoblar har safar tez siqiladi."""
    import gzip
    if len(body) > 50_000:
        key = hash(body)
        hit = _gz_cache.get(key)
        if hit is None:
            if len(_gz_cache) > 8:
                _gz_cache.clear()
            hit = _gz_cache[key] = gzip.compress(body, 6)
        return hit
    return gzip.compress(body, 4)


def _kids_item_ok(x: dict) -> bool:
    """👶 Bolalar rejimi: multfilmlar va yoshi 12+ gacha belgilangan kontent."""
    age = x.get("age") or 0
    if x.get("cat") == "cartoon":
        return age <= 12
    return 0 < age <= 12 and x.get("cat") != "music"


def _kids_filter(o):
    if isinstance(o, list):
        return [_kids_filter(x) for x in o
                if not (isinstance(x, dict) and "cat" in x and "title" in x and "id" in x and not _kids_item_ok(x))]
    if isinstance(o, dict):
        return {k: _kids_filter(v) for k, v in o.items()}
    return o


# ───── 🌐 PWA va boy havola ko'rinishi (Open Graph) ─────

# Telegram oynasi (web.telegram.org va ilovalar) ichida ochilishi uchun frame-ancestors ruxsat etilgan
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://telegram.org https://accounts.google.com; "
       "style-src 'self' 'unsafe-inline' https://accounts.google.com; frame-src https://accounts.google.com https://www.youtube-nocookie.com https://www.youtube.com; "
       "img-src 'self' data: blob: https://image.tmdb.org https://*.googleusercontent.com; font-src 'self'; media-src 'self' blob:; "
       "connect-src 'self' https://accounts.google.com; "
       "object-src 'none'; base-uri 'self'; form-action 'self'; "
       "frame-ancestors 'self' https://web.telegram.org https://*.telegram.org https://telegram.org")

# Yandex reklama (avto-joylashtirish) yoqilgan bo'lsa — faqat shu domenlarga ruxsat (reklama rasmlari/ramkalari boshqa manzillardan keladi)
_ADS = ("https://yandex.ru https://*.yandex.ru https://*.yandex.net https://*.yandex.com https://yastatic.net https://*.yastatic.net")


def csp_for(app) -> str:
    if not getattr(app.config, "yandex_ads_id", ""):
        return CSP
    return (CSP.replace("https://accounts.google.com;", f"https://accounts.google.com {_ADS};", 1)
               .replace("style-src 'self' 'unsafe-inline'", f"style-src 'self' 'unsafe-inline' {_ADS}", 1)
               .replace("frame-src https://accounts.google.com;", f"frame-src https://accounts.google.com {_ADS} https:;", 1)
               .replace("img-src 'self' data: blob:", "img-src 'self' data: blob: https:", 1)
               .replace("connect-src 'self' https://accounts.google.com;", f"connect-src 'self' https://accounts.google.com {_ADS};", 1))

YANDEX_VERIFY = ('<html>\n    <head>\n        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n    </head>\n'
                 '    <body>Verification: ad2be0e9bc24166d</body>\n</html>\n')

STATIC_FILES = {
    "/og.png": "image/png", "/icon-192.png": "image/png", "/icon-512.png": "image/png",
    "/icon-maskable-512.png": "image/png", "/apple-touch-icon.png": "image/png",
}

SERVICE_WORKER = r"""// Marvarid Media — xizmat ishchisi: sahifa tezroq ochiladi, internet uzilsa ham ilova qobig'i chiqadi
const V = "mm-v3", IMG = "mm-img-v1";
self.addEventListener("install", (e) => { self.skipWaiting(); e.waitUntil(caches.open(V).then((c) => c.add("/"))); });
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== V && k !== IMG).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
async function trim(name, max) { const c = await caches.open(name), ks = await c.keys(); for (let i = 0; i < ks.length - max; i++) await c.delete(ks[i]); }
self.addEventListener("fetch", (e) => {
  const r = e.request, u = new URL(r.url);
  if (r.method !== "GET" || u.origin !== location.origin) return;
  if (r.mode === "navigate") {           // sahifa: avval tarmoq, bo'lmasa saqlangan nusxa
    e.respondWith(fetch(r).then((res) => { if (res.ok && !u.search) { const cp = res.clone(); caches.open(V).then((c) => c.put("/", cp)); } return res; })
      .catch(() => caches.match("/")));
    return;
  }
  if (/^\/(api\/poster\/|icon-|og\.png|apple-touch|fonts\/|assets\/)/.test(u.pathname)) {   // posterlar va ikonkalar: avval saqlangan
    e.respondWith(caches.open(IMG).then((c) => c.match(r).then((hit) => hit || fetch(r).then((res) => { if (res.ok) { c.put(r, res.clone()); trim(IMG, 250); } return res; }))));
  }
});
"""


def _moved_to(app: App, host: str, path: str) -> str:
    """Sayt o'z domenida (WEBAPP_URL) bo'lsa, eski *.railway.app manzilidagi sahifa so'rovlarini shu yerga o'tkazadi.
    API, media va healthz ga tegmaydi (eski ilovalar va Railway tekshiruvi buzilmasin). Bo'sh qator — o'tkazish shart emas."""
    base = (app.config.webapp_url or "").rstrip("/")
    if not base or path == "/healthz" or path.startswith(("/api/", "/pub/", "/media/")):
        return ""
    host = host.split(":")[0].lower()
    want = urllib.parse.urlsplit(base).hostname or ""
    if not want or host == want or not host.endswith(".railway.app"):
        return ""
    return base


def _site_base(handler, app: App) -> str:
    if app.config.webapp_url:
        return app.config.webapp_url.rstrip("/")
    proto = handler.headers.get("X-Forwarded-Proto") or "http"
    return f"{proto}://{handler.headers.get('Host', 'localhost')}"


def _manifest(app: App) -> bytes:
    brand = app.brand
    return json.dumps({
        "name": brand, "short_name": brand[:12], "description": f"{brand} — eng sara kinolar, seriallar va multfilmlar",
        "start_url": "/?utm=pwa", "scope": "/", "display": "standalone", "orientation": "portrait",
        "background_color": "#0b0a0d", "theme_color": "#0b0a0d", "lang": "uz", "categories": ["entertainment", "video"],
        "icons": [
            {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Qidiruv", "url": "/?v=search&utm=pwa", "icons": [{"src": "/icon-192.png", "sizes": "192x192"}]},
            {"name": "Seriallar", "url": "/?v=serial&utm=pwa", "icons": [{"src": "/icon-192.png", "sizes": "192x192"}]},
            {"name": "Saqlanganlar", "url": "/?v=saved&utm=pwa", "icons": [{"src": "/icon-192.png", "sizes": "192x192"}]},
        ],
    }, ensure_ascii=False).encode("utf-8")


def _og_block(app: App, base: str, k: str = "") -> str:
    """Havola ulashilganda (Telegram, WhatsApp...) chiqadigan kartochka: umumiy yoki aniq kino uchun."""
    import html as _html
    brand = app.brand
    title = f"{brand} — kinolar, seriallar, multfilmlar"
    desc = "Eng sara kinolar, seriallar va multfilmlar bir joyda. Qidiring, saqlang, tomosha qiling."
    image, url = f"{base}/og.png", base + "/"
    if re.fullmatch(r"m?\d{1,9}", k or ""):
        movie = app.db.get_movie_by_code(-int(k[1:]) if k.startswith("m") else int(k))
        if movie:
            bits = [CATEGORY_NAMES.get(movie["category"], "Kino")]
            if movie["year"]:
                bits.append(str(movie["year"]))
            g = ", ".join(genres.name(x) for x in genres.parse(movie["genres"])[:3])
            if g:
                bits.append(g)
            title = f"{movie['title']} — {brand}"
            desc = " • ".join(bits) + ((" — " + truncate(movie["description"] or "", 140)) if movie["description"] else "")
            if movie["poster_id"]:
                image = f"{base}/api/poster/{movie['id']}?v={_poster_key(movie['poster_id'])}"
            url = f"{base}/?k={k}"
    e = _html.escape
    return (f'<meta name="description" content="{e(desc, True)}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="{e(brand, True)}">\n'
            f'<meta property="og:title" content="{e(title, True)}">\n<meta property="og:description" content="{e(desc, True)}">\n'
            f'<meta property="og:url" content="{e(url, True)}">\n<meta property="og:image" content="{e(image, True)}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="{e(title, True)}">\n'
            f'<meta name="twitter:description" content="{e(desc, True)}">\n<meta name="twitter:image" content="{e(image, True)}">')


CATEGORY_NAMES = {"movie": "Kino", "serial": "Serial", "cartoon": "Multfilm", "music": "Musiqa"}


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

    # Telegram foydalanuvchisi (initData bilan tasdiqlangan) — o'z ID si bo'yicha; mehmon/noma'lum — IP bo'yicha.
    # IP chegarasi kattaroq: mobil operatorlarda yuzlab odam bitta IP dan kiradi.
    _hit_seen: dict = {}
    api_user, api_ip = RateLimiter(300), RateLimiter(900)
    write_user, write_ip = RateLimiter(60), RateLimiter(240)

    class Handler(BaseHTTPRequestHandler):
        server_version = "MarvaridWeb/1.0"
        timeout = 60  # sekin/osilib qolgan ulanishlar oqimni band qilib turmasin

        def _ip(self) -> str:
            # Railway proksisi haqiqiy IP ni X-Forwarded-For ning OXIRIGA qo'shadi (boshidagisini soxtalashtirish mumkin)
            xff = self.headers.get("X-Forwarded-For", "")
            return xff.split(",")[-1].strip() or self.client_address[0]

        def _limited(self, by_user: "RateLimiter", by_ip: "RateLimiter", user: Optional[dict] = None) -> bool:
            uid = (user or {}).get("id")
            if uid:
                ok = by_user.allow(f"u{uid}")
            else:
                ok = by_ip.allow(self._ip())
            if ok:
                return False
            self._json({"ok": False, "reason": "rate"}, 429)
            return True
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # oddiy so'rovlarni logga yozmaymiz
            log.debug("%s - %s", self.address_string(), fmt % args)

        # ───── javoblar ─────
        def _send(self, status: int, body: bytes, ctype: str, cache: str = "no-store", extra: Optional[dict] = None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            if len(body) > 800 and ctype.startswith(("text/html", "application/json", "text/javascript", "application/xml", "text/css")):
                self.send_header("Vary", "Accept-Encoding")
                if "gzip" in self.headers.get("Accept-Encoding", ""):
                    body = _gzip_cached(body)  # 4 baravar kichik: tezroq ochiladi, trafik tejaladi
                    self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
            if ctype.startswith("text/html"):
                self.send_header("Content-Security-Policy", csp_for(app))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        _kids = False

        def _index(self, qs: dict, page: Optional[dict], status: int = 200) -> None:
            """Asosiy sahifa (SPA); SEO ma'lumotlari bilan boyitiladi (kino/ro'yxat sahifalari, ?k= havolalari)."""
            html_text = (WEB_DIR / "index.html").read_text(encoding="utf-8")
            for tok, name in (("__CSS__", "app.css"), ("__I18N__", "i18n.js"), ("__JS__", "app.js")):
                html_text = html_text.replace(tok, web_asset(name)[2])
            base = _site_base(self, app)
            if page is None and re.fullmatch(r"\d{1,9}", qs.get("k", "")):       # eski ko'rinishdagi havola: ?k=15
                page = seo.movie_page(app, base, int(qs["k"]), _poster_key)
            if page is not None:
                html_text = seo.apply(html_text, page)
            else:
                html_text = re.sub(r"<!--OG-->.*?<!--/OG-->", lambda m: "<!--OG-->\n" + _og_block(app, base, qs.get("k", "")) + "\n<!--/OG-->",
                                   html_text, count=1, flags=re.S)
            ads = getattr(app.config, "yandex_ads_id", "")
            if ads:       # Yandex reklama kodi — </head> dan oldin (Yandex ko'rsatmasi), moderator shu kodni sahifada ko'radi
                snippet = (f"<!-- Yandex Autoplacement {ads} -->\n"
                           '<script src="https://yandex.ru/ads/system/context.js" async></script>\n'
                           f'<script data-page-id="{ads}" src="https://yandex.ru/ads/system/ap-loader.js" async></script>\n')
                html_text = html_text.replace("</head>", snippet + "</head>", 1)
            body = html_text.encode("utf-8")
            etag = '"' + hashlib.sha1(body).hexdigest()[:20] + '"'
            if status == 200 and self.headers.get("If-None-Match") == etag:      # o'zgarmagan — qayta yuklanmaydi
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return
            self._send(status, body, "text/html; charset=utf-8", "no-cache", {"ETag": etag})

        def _json(self, obj: dict, status: int = 200) -> None:
            if self._kids and isinstance(obj, dict):
                obj = _kids_filter(obj)
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
            u = check_init_data(self.headers.get("X-Init-Data", ""), app.config.token)
            if u:
                return u
            sess = self.headers.get("X-Session", "")
            return _session_user(app, sess) if sess else None

        # ───── GET ─────
        def do_GET(self):
            self._kids = False   # ulanish qayta ishlatiladi — avvalgi so'rov holati qolmasin
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            qs = dict(urllib.parse.parse_qsl(url.query))
            try:
                moved = _moved_to(app, self.headers.get("Host", ""), path)
                if moved:   # eski railway.app manzili → yangi domen (SEO uchun doimiy yo'naltirish)
                    self.send_response(301)
                    self.send_header("Location", moved + self.path)
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if path in ("/", "/index.html"):
                    return self._index(qs, None)
                if path == "/yandex_ad2be0e9bc24166d.html":       # Yandex Reklama tarmog'i: sayt egaligini tasdiqlash fayli
                    return self._send(200, YANDEX_VERIFY.encode(), "text/html; charset=utf-8", "public, max-age=3600")
                m = re.fullmatch(r"/assets/([a-z0-9.-]+)", path)
                if m and m.group(1) in _ASSETS:
                    body, ctype, _v = web_asset(m.group(1))
                    return self._send(200, body, ctype, "public, max-age=31536000, immutable")
                if path in ("/shartlar", "/maxfiylik"):
                    from . import legal
                    html_page = legal.page("terms" if path == "/shartlar" else "privacy", app.brand, app.bot_username, _site_base(self, app))
                    return self._send(200, html_page.encode("utf-8"), "text/html; charset=utf-8", "public, max-age=3600")
                if path == "/robots.txt":
                    return self._send(200, seo.robots(_site_base(self, app)).encode(), "text/plain; charset=utf-8", "public, max-age=3600")
                if path == "/sitemap.xml":
                    return self._send(200, seo.sitemap(app, _site_base(self, app)).encode(), "application/xml; charset=utf-8", "public, max-age=3600")
                m = re.fullmatch(r"/kino/(\d{1,9})(?:-[a-z0-9-]*)?", path)
                if m:
                    page = seo.movie_page(app, _site_base(self, app), int(m.group(1)), _poster_key)
                    return self._index(qs, page, 200 if page else 404)
                m = re.fullmatch(r"/kolleksiya/(\d{1,9})(?:-[a-z0-9-]*)?", path)
                if m or path == "/kolleksiyalar":
                    base = _site_base(self, app)
                    page = seo.collection_page(app, base, int(m.group(1))) if m else seo.collections_index_page(app, base)
                    return self._index(qs, page, 200 if page else 404)
                m = re.fullmatch(r"/janr/([a-z]{3,20})", path)
                if m or path in seo.LIST_PAGES:
                    base = _site_base(self, app)
                    page = (seo.list_page(app, base, genre=m.group(1)) if m else seo.list_page(app, base, cat=seo.LIST_PAGES[path][0]))
                    return self._index(qs, page, 200 if page else 404)
                if path == "/manifest.webmanifest":
                    return self._send(200, _manifest(app), "application/manifest+json; charset=utf-8", "public, max-age=3600")
                if path == "/sw.js":
                    return self._send(200, SERVICE_WORKER.encode("utf-8"), "text/javascript; charset=utf-8", "no-cache",
                                      {"Service-Worker-Allowed": "/"})
                m = re.fullmatch(r"/fonts/([a-z0-9-]+\.woff2)", path)
                if m and (WEB_DIR / "fonts" / m.group(1)).is_file():
                    return self._send(200, (WEB_DIR / "fonts" / m.group(1)).read_bytes(), "font/woff2",
                                      "public, max-age=31536000, immutable")
                if path in STATIC_FILES:
                    return self._send(200, (WEB_DIR / path.lstrip("/")).read_bytes(), STATIC_FILES[path], "public, max-age=604800")
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                m = re.fullmatch(r"/api/poster/(\d+)", path)
                if m:
                    if self._limited(api_user, api_ip):
                        return
                    width = int(qs["w"]) if qs.get("w") in ("360", "720") else 0
                    webp = bool(width) and "image/webp" in self.headers.get("Accept", "") and _webp_ok()
                    data = poster_bytes(app, int(m.group(1)), cache_dir, width, webp)
                    if data is None:
                        return self._send(404, b"", "text/plain")
                    return self._send(200, data, "image/webp" if webp else "image/jpeg", "public, max-age=604800, immutable",
                                      {"Vary": "Accept"})
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
                if path.startswith("/pub/"):
                    # 📱 Ilova va oddiy brauzer uchun: Telegram'siz, faqat katalog (mehmon sifatida)
                    path = "/api/" + path[5:]
                    user = GUEST
                elif path.startswith("/api/"):
                    user = self._user()
                    if not user:
                        if self._limited(api_user, api_ip):
                            return
                        return self._json({"ok": False, "reason": "auth"}, 401)
                if path.startswith("/api/"):
                    if self._limited(api_user, api_ip, user):
                        return
                    self._kids = self.headers.get("X-Kids") == "1"
                    if self._kids and path == "/api/shorts":
                        return self._json({"ok": True, "items": [], "more": False})
                    if path == "/api/me":
                        return self._json(api_me(app, user))
                    if path == "/api/home":
                        return self._json(api_home(app, user))
                    if path == "/api/catalog":
                        return self._json(api_catalog(app, user, qs))
                    if path == "/api/shorts":
                        return self._json(api_shorts(app, user, qs))
                    if path == "/api/comments":
                        return self._json(api_comments(app, user, qs))
                    if path == "/api/similar":
                        return self._json(api_similar(app, user, qs))
                    if path == "/api/collections":
                        return self._json(api_collections(app, user))
                    if path == "/api/tv":
                        d = api_tv(app, user)
                        if self._kids and d.get("slots"):      # bolalar rejimi: faqat mos kinolar efirda
                            d["slots"] = [x for x in d["slots"] if _kids_item_ok(x["it"])]
                            d["cur"] = -1 if not d["slots"] else next((i for i, x in enumerate(d["slots"]) if x["e"] > d["now"]), 0)
                        return self._json(d)
                    if path == "/api/random":
                        return self._json(api_random(app, user))
                    if path == "/api/popular":
                        return self._json(api_popular(app, user))
                    if path == "/api/collection":
                        return self._json(api_collection(app, user, qs))
                    if path == "/api/myratings":
                        return self._json(api_myratings(app, user))
                    if path == "/api/mystats":
                        return self._json(api_mystats(app, user))
                    if path == "/api/support":
                        return self._json(api_support(app, user))
                    if path == "/api/admin/stats":
                        return self._json(api_admin_stats(app, user))
                    if path == "/api/admin/tmdb":
                        return self._json(api_admin_tmdb(app, user, qs))
                    if path == "/api/admin/analytics":
                        return self._json(api_admin_analytics(app, user))
                    if path == "/api/admin/movie":
                        return self._json(api_admin_movie(app, user, qs))
                    if path == "/api/rating":
                        return self._json(api_rating(app, user, qs))
                return self._send(404, b"Not found", "text/plain")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except OverflowError:  # juda katta raqam yuborilgan
                self._json({"ok": False, "reason": "not_found"}, 404)
            except Exception:
                log.exception("Sayt so'rovida xatolik: %s", path)
                try:
                    self._json({"ok": False, "reason": "error"}, 500)
                except Exception:
                    pass

        do_HEAD = do_GET

        # ───── POST ─────
        def do_POST(self):
            self._kids = False
            path = urllib.parse.urlsplit(self.path).path
            try:
                length = min(int(self.headers.get("Content-Length") or 0), 20_000)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except ValueError:
                    body = {}
                if not isinstance(body, dict):
                    body = {}
                if path in ("/pub/auth/tg/start", "/pub/auth/tg/poll", "/pub/auth/google"):
                    if self._limited(write_user, write_ip):
                        return
                    return self._json(api_auth(app, path, body))
                if path in ("/pub/play", "/pub/searched", "/pub/hit"):  # 📱 ilova / brauzer — mehmon sifatida
                    if self._limited(write_user, write_ip):
                        return
                    if path == "/pub/play":
                        return self._json(api_play(app, GUEST, body, guest=True))
                    if path == "/pub/hit":        # tahlil: mehmon sayt ochdi (manba bo'yicha sanaladi, shaxsiy ma'lumotsiz)
                        src = re.sub(r"[^a-z0-9_-]", "", str(body.get("src") or "direct").lower())[:20] or "direct"
                        ip = self._ip()
                        t = time.time()
                        if t - _hit_seen.get(ip, 0) > 600:        # bir IP dan 10 daqiqada bir marta (statistika buzilmasin)
                            if len(_hit_seen) > 20000:
                                _hit_seen.clear()
                            _hit_seen[ip] = t
                            app.db.hit(src)
                        return self._json({"ok": True})
                    return self._json(api_searched(app, GUEST, body))
                user = self._user()
                if not user:
                    if self._limited(write_user, write_ip):
                        return
                    return self._json({"ok": False, "reason": "auth"}, 401)
                if self._limited(write_user, write_ip, user):
                    return
                if path == "/api/auth/logout":
                    sess = self.headers.get("X-Session", "")
                    if sess:
                        app.db.delete_session(sess)
                    return self._json({"ok": True})
                if path == "/api/play":
                    return self._json(api_play(app, user, body, guest=(user["id"] < 0)))
                if path == "/api/watch":
                    return self._json(api_watch(app, user, body))
                if path == "/api/request":
                    return self._json(api_request(app, user, body))
                if path == "/api/tv/trial":
                    return self._json(api_tv_trial(app, user))
                if path == "/api/history/clear":
                    return self._json(api_history_clear(app, user))
                if path == "/api/searched":
                    return self._json(api_searched(app, user, body))
                if path == "/api/rate":
                    return self._json(api_rate(app, user, body))
                if path == "/api/comment":
                    return self._json(api_comment_post(app, user, body))
                if path == "/api/comment/like":
                    return self._json(api_comment_like(app, user, body))
                if path == "/api/comment/report":
                    return self._json(api_comment_report(app, user, body))
                if path == "/api/comment/delete":
                    return self._json(api_comment_delete(app, user, body))
                if path == "/api/comment/ban":
                    return self._json(api_comment_ban(app, user, body))
                if path == "/api/admin/save":
                    return self._json(api_admin_save(app, user, body))
                if path == "/api/admin/delete":
                    return self._json(api_admin_delete(app, user, body))
                return self._json({"ok": False, "reason": "not_found"}, 404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except OverflowError:  # juda katta raqam yuborilgan
                self._json({"ok": False, "reason": "not_found"}, 404)
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
        server = _Server(("0.0.0.0", cfg.web_port), make_handler(app))
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
            "type": "web_app", "text": "🌐 Saytni ochish", "web_app": {"url": cfg.webapp_url}}})
        log.info("🌐 Sayt ishga tushdi: %s (port %s)", cfg.webapp_url, cfg.web_port)
    else:
        log.warning("🌐 Sayt %s-portda ishlayapti, lekin manzili noma'lum — .env ga WEBAPP_URL=https://... "
                    "yozing (Railway'da: Settings → Networking → Generate Domain)", cfg.web_port)
