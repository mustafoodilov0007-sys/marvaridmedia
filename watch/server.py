"""Marvarid Watch — kinoni to'g'ridan-to'g'ri saytda ko'rsatadigan alohida sayt.

Ishga tushirish:  python server.py
Hamma sozlamalar muhit o'zgaruvchilarida (README.md ga qarang).
"""

from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

import api  # noqa: E402
from catalog import Syncer  # noqa: E402
from config import Config  # noqa: E402
from db import DB, now  # noqa: E402
from s3 import S3, S3Error  # noqa: E402
from storage import LocalStorage, S3Storage, safe_ext  # noqa: E402

log = logging.getLogger("watch")

MAX_VIDEO = 80 * 1024 ** 3          # bitta fayl uchun yuqori chegara
COOKIE = "wa"
COOKIE_TTL = 14 * 86400


class RateLimiter:
    """Oddiy «chelak»: kalit bo'yicha daqiqada `per_min` ta."""

    def __init__(self, per_min: int):
        self.rate, self.cap = per_min / 60.0, float(per_min)
        self.b: dict = {}
        self.lock = threading.Lock()
        self.gc = time.time()

    def allow(self, key: str) -> bool:
        t = time.time()
        with self.lock:
            if t - self.gc > 300:
                self.b = {k: v for k, v in self.b.items() if t - v[1] < 120}
                self.gc = t
            tokens, last = self.b.get(key, (self.cap, t))
            tokens = min(self.cap, tokens + (t - last) * self.rate)
            if tokens < 1:
                self.b[key] = (tokens, t)
                return False
            self.b[key] = (tokens - 1, t)
            return True


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = DB(cfg.db_path)
        if cfg.storage == "s3":
            self.storage = S3Storage(S3(cfg.s3_endpoint, cfg.s3_bucket, cfg.s3_access, cfg.s3_secret, cfg.s3_region),
                                     cfg.public_video_base)
        else:
            self.storage = LocalStorage(cfg.data_dir / "videos", cfg.secret)
        self.syncer = Syncer(self.db, cfg.source_url)
        self.stopping = threading.Event()
        self.public_rl = RateLimiter(900)   # mobil operatorlarda ko'p odam bitta IP dan kiradi
        self.admin_rl = RateLimiter(240)
        self.login_rl = RateLimiter(6)
        self.view_seen: dict = {}
        (cfg.data_dir / "posters").mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_uploads()

    # ───── admin sessiyasi ─────
    def make_cookie(self) -> str:
        exp = str(int(time.time()) + COOKIE_TTL)
        return exp + "." + hmac.new(self.cfg.secret.encode(), exp.encode(), hashlib.sha256).hexdigest()[:40]

    def check_cookie(self, value: str) -> bool:
        exp, _, sig = (value or "").partition(".")
        if not (exp.isdigit() and int(exp) > time.time() and sig):
            return False
        good = hmac.new(self.cfg.secret.encode(), exp.encode(), hashlib.sha256).hexdigest()[:40]
        return hmac.compare_digest(sig, good)

    # ───── yuklash tozalash ─────
    def _cleanup_stale_uploads(self) -> None:
        for v in self.db.q("SELECT * FROM videos WHERE status='uploading' AND created_at < ?", (now() - 2 * 86400,)):
            try:
                self.storage.abort(v["key"], v["upload_id"])
            except Exception:  # noqa: BLE001
                pass
            self.db.x("DELETE FROM videos WHERE id=?", (v["id"],))

    def title_videos(self, title_id: int):
        return self.db.q("SELECT * FROM videos WHERE title_id=? AND status='ready' ORDER BY part_no", (title_id,))


def make_handler(app: App):
    cfg, db, storage = app.cfg, app.db, app.storage

    class Handler(BaseHTTPRequestHandler):
        server_version = "MarvaridWatch/1.0"
        protocol_version = "HTTP/1.1"
        timeout = 120

        def log_message(self, fmt, *args):
            log.debug("%s - %s", self.address_string(), fmt % args)

        # ───── yordamchilar ─────
        def _ip(self) -> str:
            xff = self.headers.get("X-Forwarded-For", "")
            return xff.split(",")[-1].strip() or self.client_address[0]

        def _send(self, status: int, body: bytes, ctype: str, cache: str = "no-store", extra: Optional[dict] = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            if len(body) > 800 and ctype.startswith(("text/html", "application/json", "text/css", "text/javascript")):
                self.send_header("Vary", "Accept-Encoding")
                if "gzip" in self.headers.get("Accept-Encoding", ""):
                    body = gzip.compress(body, 5)
                    self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, obj, status: int = 200, extra: Optional[dict] = None):
            self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", extra=extra)

        def _body(self, limit: int = 1_000_000) -> bytes:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            if n > limit:
                self.close_connection = True      # tanani o'qimadik — ulanishni yopamiz (keyingi so'rov buzilmasin)
                raise ValueError("so'rov juda katta")
            return self.rfile.read(n) if n else b""

        def _json_body(self) -> dict:
            try:
                d = json.loads((self._raw or b"").decode("utf-8") or "{}")
            except ValueError:
                return {}
            return d if isinstance(d, dict) else {}

        def _admin(self) -> bool:
            jar = self.headers.get("Cookie", "")
            m = re.search(r"(?:^|;\s*)" + COOKIE + r"=([^;]+)", jar)
            return bool(cfg.admin_password and m and app.check_cookie(m.group(1)))

        def _send_file(self, path: Path, ctype: str):
            """Faylni Range (bo'lib-bo'lib) yuboradi — video oldinga-orqaga o'tkazilishi uchun shart."""
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
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
            self.send_header("Cache-Control", "public, max-age=86400")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            if self.command == "HEAD":
                return
            with open(path, "rb") as f:
                f.seek(start)
                left = length
                while left > 0:
                    chunk = f.read(min(262144, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        # ───── GET ─────
        def do_GET(self):
            url = urllib.parse.urlsplit(self.path)
            path = url.path
            qs = dict(urllib.parse.parse_qsl(url.query))
            try:
                if path in ("/", "/index.html"):
                    return self._send(200, (cfg.web_dir / "index.html").read_bytes(), "text/html; charset=utf-8", "no-cache")
                if path in ("/admin", "/admin/"):
                    return self._send(200, (cfg.web_dir / "admin.html").read_bytes(), "text/html; charset=utf-8", "no-cache")
                if path == "/healthz":
                    return self._send(200, b"ok", "text/plain")
                if path == "/favicon.ico":
                    return self._send(204, b"", "image/x-icon")
                m = re.fullmatch(r"/api/poster/(\d+)", path)
                if m:
                    return self._poster(int(m.group(1)))
                m = re.fullmatch(r"/media/(\d+)", path)
                if m:
                    return self._media(int(m.group(1)), qs)
                if path.startswith("/pub/"):
                    if not app.public_rl.allow(self._ip()):
                        return self._json({"ok": False, "reason": "rate"}, 429)
                    return self._public_get(path[5:], qs)
                if path.startswith("/admin/api/"):
                    if not self._admin():
                        return self._json({"ok": False, "reason": "auth"}, 401)
                    if not app.admin_rl.allow(self._ip()):
                        return self._json({"ok": False, "reason": "rate"}, 429)
                    return self._admin_get(path[len("/admin/api/"):], qs)
                return self._send(404, b"Not found", "text/plain")
            except (BrokenPipeError, ConnectionResetError):
                pass
            except OverflowError:
                self._json({"ok": False, "reason": "not_found"}, 404)
            except Exception:  # noqa: BLE001
                log.exception("GET xatolik: %s", path)
                try:
                    self._json({"ok": False, "reason": "error"}, 500)
                except Exception:  # noqa: BLE001
                    pass

        do_HEAD = do_GET

        def _public_get(self, name: str, qs: dict):
            if name == "me":
                return self._json(api.me(cfg, db))
            if name == "home":
                return self._json(api.home(db))
            if name == "catalog":
                return self._json(api.catalog(db, qs))
            if name == "similar":
                return self._json(api.similar(db, qs))
            if name == "random":
                return self._json(api.random_item(db))
            if name == "popular":
                return self._json({"ok": True, "queries": []})
            if name in ("collections",):
                return self._json({"ok": True, "items": []})
            if name == "shorts":
                return self._json({"ok": True, "items": [], "more": False})
            if name == "playinfo":
                return self._playinfo(qs)
            return self._json({"ok": False, "reason": "not_found"}, 404)

        def _playinfo(self, qs: dict):
            try:
                tid = int(qs.get("id", "0"))
            except ValueError:
                return self._json({"ok": False, "reason": "not_found"}, 404)
            t = db.q1("SELECT * FROM titles WHERE id=? AND published=1", (tid,))
            vids = app.title_videos(tid) if t else []
            if not vids:
                return self._json({"ok": False, "reason": "not_found"}, 404)
            return self._json({"ok": True, "id": tid, "title": t["title"], "parts": [
                {"no": v["part_no"], "url": storage.play_url(v["id"], v["key"]), "duration": v["duration"],
                 "size": v["size"], "type": v["ctype"]} for v in vids]})

        def _poster(self, tid: int):
            t = db.q1("SELECT src_id, poster_v FROM titles WHERE id=?", (tid,))
            if not t or not t["poster_v"] or not cfg.source_url:
                return self._send(404, b"", "text/plain")
            cache = cfg.data_dir / "posters" / f"{tid}_{re.sub(r'[^A-Za-z0-9]', '', t['poster_v'])}.jpg"
            if not cache.exists():
                try:
                    req = urllib.request.Request(f"{cfg.source_url}/api/poster/{t['src_id']}?v={urllib.parse.quote(t['poster_v'])}",
                                                 headers={"User-Agent": "MarvaridWatch/1.0"})
                    with urllib.request.urlopen(req, timeout=20) as r:
                        data = r.read(8_000_000)
                    cache.write_bytes(data)
                except Exception:  # noqa: BLE001
                    return self._send(404, b"", "text/plain")
            return self._send(200, cache.read_bytes(), "image/jpeg", "public, max-age=604800, immutable")

        def _media(self, vid: int, qs: dict):
            if storage.mode != "local":
                return self._send(404, b"", "text/plain")
            if not storage.check(vid, qs.get("e", ""), qs.get("s", "")):
                return self._send(403, b"", "text/plain")
            v = db.q1("SELECT * FROM videos WHERE id=? AND status='ready'", (vid,))
            if not v:
                return self._send(404, b"", "text/plain")
            p = storage.path(v["key"])
            if not p.exists():
                return self._send(404, b"", "text/plain")
            return self._send_file(p, v["ctype"] or "video/mp4")

        # ───── POST ─────
        _raw: bytes = b""

        def do_POST(self):
            path = urllib.parse.urlsplit(self.path).path
            qs = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
            try:
                # so'rov tanasini DOIM o'qiymiz (aks holda keep-alive ulanishda keyingi so'rov buziladi);
                # faqat video bo'lagi (upload/chunk) o'zi, katta hajmda o'qiydi
                self._raw = b"" if path.endswith("/upload/chunk") else self._body()
                if path == "/admin/login":
                    return self._login()
                if path == "/admin/logout":
                    return self._json({"ok": True}, extra={"Set-Cookie": f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"})
                if path == "/pub/played":
                    if not app.public_rl.allow(self._ip()):
                        return self._json({"ok": False, "reason": "rate"}, 429)
                    return self._played(self._json_body())
                if path.startswith("/admin/api/"):
                    if not self._admin():
                        return self._json({"ok": False, "reason": "auth"}, 401)
                    if not app.admin_rl.allow(self._ip()):
                        return self._json({"ok": False, "reason": "rate"}, 429)
                    return self._admin_post(path[len("/admin/api/"):], qs)
                if path.startswith("/pub/"):
                    return self._json({"ok": True})     # qidiruv jurnali va boshqalar — kerak emas
                return self._json({"ok": False, "reason": "not_found"}, 404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except ValueError as exc:
                self._json({"ok": False, "reason": "bad", "message": str(exc)}, 400)
            except S3Error as exc:
                log.warning("Ombor xatosi: %s", exc)
                self._json({"ok": False, "reason": "storage", "message": str(exc)[:200]}, 502)
            except Exception:  # noqa: BLE001
                log.exception("POST xatolik: %s", path)
                try:
                    self._json({"ok": False, "reason": "error"}, 500)
                except Exception:  # noqa: BLE001
                    pass

        def _login(self):
            if not app.login_rl.allow(self._ip()):
                return self._json({"ok": False, "reason": "rate"}, 429)
            pw = str(self._json_body().get("password") or "")
            if cfg.admin_password and hmac.compare_digest(pw.encode(), cfg.admin_password.encode()):
                secure = "; Secure" if (self.headers.get("X-Forwarded-Proto") == "https" or cfg.base_url.startswith("https")) else ""
                return self._json({"ok": True}, extra={
                    "Set-Cookie": f"{COOKIE}={app.make_cookie()}; Path=/; Max-Age={COOKIE_TTL}; HttpOnly; SameSite=Lax{secure}"})
            time.sleep(0.6)
            return self._json({"ok": False, "reason": "password"}, 401)

        def _played(self, body: dict):
            try:
                tid = int(body.get("id"))
            except (TypeError, ValueError):
                return self._json({"ok": False})
            key = (self._ip(), tid)
            t = time.time()
            if t - app.view_seen.get(key, 0) > 1800:          # bitta odam 30 daqiqada bir marta hisoblanadi
                if len(app.view_seen) > 20000:
                    app.view_seen.clear()
                app.view_seen[key] = t
                if db.q1("SELECT 1 FROM titles WHERE id=?", (tid,)):
                    db.add_view(tid)
            return self._json({"ok": True})

        # ───── admin ─────
        def _admin_get(self, name: str, qs: dict):
            if name == "titles":
                return self._json(self._titles(qs))
            if name == "sync":
                return self._json({"ok": True, **app.syncer.state})
            if name == "stats":
                return self._json(self._stats())
            return self._json({"ok": False, "reason": "not_found"}, 404)

        def _titles(self, qs: dict) -> dict:
            where, params = [], []
            q = (qs.get("q") or "").strip()
            if q:
                if q.lstrip("#").isdigit():
                    where.append("t.code=?")
                    params.append(int(q.lstrip("#")))
                else:
                    from textutil import like, normalize
                    for tok in normalize(q).split():
                        where.append("t.norm LIKE ? ESCAPE '\\'")
                        params.append(f"%{like(tok)}%")
            has = qs.get("has", "all")
            ex = "EXISTS (SELECT 1 FROM videos v WHERE v.title_id=t.id AND v.status='ready')"
            if has == "yes":
                where.append(ex)
            elif has == "no":
                where.append("NOT " + ex)
            if qs.get("cat") in ("movie", "serial", "cartoon"):
                where.append("t.category=?")
                params.append(qs["cat"])
            try:
                offset = max(0, int(qs.get("offset", "0")))
            except ValueError:
                offset = 0
            w = ("WHERE " + " AND ".join(where)) if where else ""
            total = db.val(f"SELECT COUNT(*) FROM titles t {w}", params)
            rows = db.q(f"SELECT t.* FROM titles t {w} ORDER BY t.code DESC, t.id DESC LIMIT 40 OFFSET ?", params + [offset])
            items = []
            for t in rows:
                vids = db.q("SELECT id, part_no, size, duration, status FROM videos WHERE title_id=? ORDER BY part_no", (t["id"],))
                items.append({"id": t["id"], "code": t["code"], "title": t["title"], "cat": t["category"], "year": t["year"],
                              "poster": t["poster_v"] or None, "published": bool(t["published"]), "views": t["views"],
                              "videos": [dict(v) for v in vids]})
            return {"ok": True, "items": items, "total": total, "more": offset + 40 < total,
                    "sync": app.syncer.state, "storage": storage.mode, "source": bool(cfg.source_url),
                    "titles_total": db.val("SELECT COUNT(*) FROM titles")}

        def _stats(self) -> dict:
            return {"ok": True,
                    "titles": db.val("SELECT COUNT(*) FROM titles"),
                    "watchable": db.val(f"SELECT COUNT(*) FROM titles t WHERE {api.WATCHABLE}"),
                    "videos": db.val("SELECT COUNT(*) FROM videos WHERE status='ready'"),
                    "bytes": db.val("SELECT SUM(size) FROM videos WHERE status='ready'"),
                    "views": db.val("SELECT SUM(views) FROM titles"),
                    "views7": db.val("SELECT SUM(n) FROM view_days WHERE day >= ?", (api.today() - 6,)),
                    "top": [{"title": r["title"], "views": r["views"]} for r in
                            db.q("SELECT title, views FROM titles WHERE views>0 ORDER BY views DESC LIMIT 10")],
                    "storage": storage.mode, "problems": cfg.problems()}

        def _admin_post(self, name: str, qs: dict):
            if name == "sync":
                started = app.syncer.start()
                return self._json({"ok": started, **app.syncer.state})
            if name == "upload/chunk":                    # faqat mahalliy ombor: bo'lak to'g'ridan-to'g'ri serverga keladi
                return self._upload_chunk(qs)
            body = self._json_body()
            if name == "upload/start":
                return self._upload_start(body)
            if name == "upload/sign":
                return self._upload_sign(body)
            if name == "upload/complete":
                return self._upload_complete(body)
            if name == "upload/abort":
                v = db.q1("SELECT * FROM videos WHERE id=? AND status='uploading'", (int(body.get("video_id") or 0),))
                if v:
                    storage.abort(v["key"], v["upload_id"])
                    db.x("DELETE FROM videos WHERE id=?", (v["id"],))
                return self._json({"ok": True})
            if name == "video/delete":
                v = db.q1("SELECT * FROM videos WHERE id=?", (int(body.get("video_id") or 0),))
                if not v:
                    return self._json({"ok": False, "reason": "not_found"}, 404)
                storage.delete(v["key"])
                db.x("DELETE FROM videos WHERE id=?", (v["id"],))
                return self._json({"ok": True})
            if name == "title/publish":
                db.x("UPDATE titles SET published=? WHERE id=?", (1 if body.get("published") else 0, int(body.get("title_id") or 0)))
                return self._json({"ok": True})
            return self._json({"ok": False, "reason": "not_found"}, 404)

        def _upload_start(self, b: dict):
            tid = int(b.get("title_id") or 0)
            size = int(b.get("size") or 0)
            if not db.q1("SELECT 1 FROM titles WHERE id=?", (tid,)):
                return self._json({"ok": False, "reason": "not_found"}, 404)
            if not 0 < size <= MAX_VIDEO:
                raise ValueError("fayl hajmi noto'g'ri")
            ctype = str(b.get("ctype") or "video/mp4")[:60]
            if not (ctype.startswith("video/") or ctype == "application/octet-stream"):
                raise ValueError("faqat video fayl yuklang")
            part_no = int(b.get("part_no") or 0) or (db.val("SELECT MAX(part_no) FROM videos WHERE title_id=?", (tid,)) + 1)
            if db.q1("SELECT 1 FROM videos WHERE title_id=? AND part_no=? AND status='ready'", (tid, part_no)):
                raise ValueError(f"{part_no}-qism allaqachon yuklangan (avval uni o'chiring)")
            key = f"videos/{tid}/{part_no:02d}-{secrets.token_hex(4)}.{safe_ext(str(b.get('filename') or ''), ctype)}"
            part_size = cfg.part_size
            while size / part_size > 9000:
                part_size *= 2
            upload_id = storage.start(key, ctype if ctype != "application/octet-stream" else "video/mp4")
            vid = db.x("INSERT INTO videos(title_id, part_no, key, ctype, size, upload_id, status, created_at)"
                       " VALUES (?,?,?,?,?,?,?,?)", (tid, part_no, key, ctype, size, upload_id, "uploading", now())).lastrowid
            return self._json({"ok": True, "video_id": vid, "part_no": part_no, "part_size": part_size,
                               "parts": -(-size // part_size), "mode": storage.mode})

        def _upload_sign(self, b: dict):
            v = db.q1("SELECT * FROM videos WHERE id=? AND status='uploading'", (int(b.get("video_id") or 0),))
            if not v or storage.mode != "s3":
                return self._json({"ok": False, "reason": "not_found"}, 404)
            ns = [int(n) for n in (b.get("ns") or [])][:20]
            return self._json({"ok": True, "urls": {str(n): storage.part_url(v["key"], v["upload_id"], n) for n in ns if 1 <= n <= 10000}})

        def _upload_chunk(self, qs: dict):
            v = db.q1("SELECT * FROM videos WHERE id=? AND status='uploading'", (int(qs.get("video_id") or 0),))
            if not v or storage.mode != "local":
                return self._json({"ok": False, "reason": "not_found"}, 404)
            n = int(qs.get("n") or 0)
            size = int(qs.get("part_size") or cfg.part_size)
            data = self._body(limit=size + 8 * 1024 * 1024)
            storage.write_chunk(v["key"], n, size, data)
            return self._json({"ok": True})

        def _upload_complete(self, b: dict):
            v = db.q1("SELECT * FROM videos WHERE id=? AND status='uploading'", (int(b.get("video_id") or 0),))
            if not v:
                return self._json({"ok": False, "reason": "not_found"}, 404)
            parts = [(int(p["n"]), str(p["etag"])) for p in (b.get("parts") or [])]
            storage.complete(v["key"], v["upload_id"], parts, v["size"])
            dur = max(0, min(int(float(b.get("duration") or 0)), 86400))
            db.x("UPDATE videos SET status='ready', duration=? WHERE id=?", (dur, v["id"]))
            return self._json({"ok": True})

    return Handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Config()
    for p in cfg.problems():
        log.warning("⚠️ %s", p)
    app = App(cfg)
    server = ThreadingHTTPServer(("0.0.0.0", cfg.port), make_handler(app))
    server.daemon_threads = True
    threading.Thread(target=app.syncer.loop, args=(app.stopping,), name="sync-loop", daemon=True).start()
    log.info("🎬 %s ishga tushdi: port %s, ombor: %s", cfg.brand, cfg.port, app.storage.mode)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stopping.set()


if __name__ == "__main__":
    main()
