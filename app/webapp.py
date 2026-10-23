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


def api_catalog(app: App, user: dict, qs: dict) -> dict:
    cat = qs.get("cat", "movie")
    if cat not in CATEGORIES:
        cat = "movie"
    sort = "top" if qs.get("sort") == "top" else "new"
    try:
        offset = max(0, int(qs.get("offset", "0")))
    except ValueError:
        offset = 0
    query = (qs.get("q") or "").strip()[:100]
    genre = qs.get("genre") if qs.get("genre") in genres.GENRES else None
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")

    link = (qs.get("k") or "").strip()  # kanal postidagi havola: ?k=15 (kino) yoki ?k=m3 (musiqa)
    if re.fullmatch(r"m?\d{1,9}", link):
        code = -int(link[1:]) if link.startswith("m") else int(link)
        movie = app.db.get_movie_by_code(code)
        rows = app.db.catalog(movie["category"], movie_id=movie["id"], limit=1) if movie else []
        more = False
    elif re.fullmatch(r"#?\d{1,9}", query):
        movie = app.db.get_movie_by_code(int(query.lstrip("#")))
        rows = []
        if movie and offset == 0:
            rows = app.db.catalog(movie["category"], movie_id=movie["id"], limit=1)
        more = False
    else:
        tokens = normalize(query).split()
        rows = app.db.catalog(cat, sort, tokens, PAGE_SIZE + 1, offset, genre=genre)
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

    items = [_item(r, premium_on, vip) for r in rows]
    out = {"ok": True, "items": items, "more": more, "counts": app.db.count_by_category()}
    if offset == 0 and not query and cat != "music":
        out["genres"] = [{"key": k, "label": genres.label(k), "n": n} for k, n in app.db.genre_counts(cat).items()]
    return out


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
        "genres": [{"key": k, "label": genres.label(k)} for k in genres.parse(r["genres"] if "genres" in keys else "")],
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
    for cat in ("movie", "cartoon"):
        newest += list(db.catalog(cat, "new", None, 12))
    newest.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)
    with_poster = [r for r in newest if r["poster_id"]]
    hero = (with_poster + [r for r in newest if not r["poster_id"]])[:6]
    history = pack(db.history(user["id"], 15)) if user["id"] else []
    return {
        "ok": True,
        "history": history,
        "hero": pack(hero),
        "rails": [
            {"key": "movie_new", "title": "Yangi kinolar", "cat": "movie", "sort": "new",
             "items": pack(db.catalog("movie", "new", None, 15))},
            {"key": "movie_top", "title": "Eng ko'p ko'rilgan", "cat": "movie", "sort": "top",
             "items": pack(db.catalog("movie", "top", None, 15))},
            {"key": "cartoon", "title": "Multfilmlar", "cat": "cartoon", "sort": "new",
             "items": pack(db.catalog("cartoon", "new", None, 15))},
            {"key": "music", "title": "Musiqalar", "cat": "music", "sort": "new",
             "items": pack(db.catalog("music", "new", None, 15))},
        ],
        "counts": db.count_by_category(),
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
        "counts": app.db.count_by_category(),
        "channel": _channel_url(app),
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

def make_handler(app: App):
    cache_dir = Path(app.config.db_path).parent / "posters"
    shorts_dir = Path(app.config.db_path).parent / "shorts"
    audio_dir = Path(app.config.db_path).parent / "audio"

    class Handler(BaseHTTPRequestHandler):
        server_version = "MarvaridWeb/1.0"
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
                length = min(int(self.headers.get("Content-Length") or 0), 10_000)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except ValueError:
                    body = {}
                if not isinstance(body, dict):
                    body = {}
                if path == "/pub/play":  # 📱 ilova / brauzer — mehmon sifatida tinglash
                    return self._json(api_play(app, GUEST, body, guest=True))
                user = self._user()
                if not user:
                    return self._json({"ok": False, "reason": "auth"}, 401)
                if path == "/api/play":
                    return self._json(api_play(app, user, body, guest=False))
                if path == "/api/watch":
                    return self._json(api_watch(app, user, body))
                if path == "/api/request":
                    return self._json(api_request(app, user, body))
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
