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

from . import keyboards
from .core import App, Ctx, router
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
    _, vip = _user_flags(app, user["id"])
    premium_on = app.setting_bool("premium_enabled")

    if re.fullmatch(r"#?\d{1,9}", query):
        movie = app.db.get_movie_by_code(int(query.lstrip("#")))
        rows = []
        if movie and offset == 0:
            rows = app.db.catalog(movie["category"], movie_id=movie["id"], limit=1)
        more = False
    else:
        tokens = normalize(query).split()
        rows = app.db.catalog(cat, sort, tokens, PAGE_SIZE + 1, offset)
        more = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]

    items = [{
        "id": r["id"],
        "code": r["code"],
        "cat": r["category"],
        "title": r["title"],
        "desc": truncate(r["description"] or "", 400),
        "parts": r["parts"],
        "views": r["views"],
        "premium": bool(r["is_premium"]),
        "locked": bool(r["is_premium"]) and premium_on and not vip,
        "poster": _poster_key(r["poster_id"]),
    } for r in rows]
    return {"ok": True, "items": items, "more": more, "counts": app.db.count_by_category()}


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
                          "chat": {"id": uid, "type": "private"}, "text": str(movie["code"])}}
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


# ═════════════════════════ HTTP server ═════════════════════════

def make_handler(app: App):
    cache_dir = Path(app.config.db_path).parent / "posters"

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
                if path.startswith("/api/"):
                    user = self._user()
                    if not user:
                        return self._json({"ok": False, "reason": "auth"}, 401)
                    if path == "/api/me":
                        return self._json(api_me(app, user))
                    if path == "/api/catalog":
                        return self._json(api_catalog(app, user, qs))
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
                user = self._user()
                if not user:
                    return self._json({"ok": False, "reason": "auth"}, 401)
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except ValueError:
                    body = {}
                if path == "/api/watch" and isinstance(body, dict):
                    return self._json(api_watch(app, user, body))
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
        log.info("🌐 Sayt ishga tushdi: %s (port %s)", cfg.webapp_url, cfg.web_port)
    else:
        log.warning("🌐 Sayt %s-portda ishlayapti, lekin manzili noma'lum — .env ga WEBAPP_URL=https://... "
                    "yozing (Railway'da: Settings → Networking → Generate Domain)", cfg.web_port)
