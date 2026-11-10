"""Sinovlar uchun umumiy asboblar: soxta Telegram, vaqtinchalik baza, imzolangan initData."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

TOKEN = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
ROOT = Path(__file__).resolve().parent.parent


class FakeBot:
    """Telegram o'rniga: yuborilgan hamma narsani yodda saqlaydi."""
    emoji_fail = 0

    def __init__(self):
        self.sent = []
        self.member_status = "member"

    def __getattr__(self, name):
        def call(*a, **k):
            self.sent.append((name, a, k))
            chat = a[0] if a else k.get("chat_id")
            return {"message_id": 7, "chat": {"id": chat, "type": "private", "username": "kanal"}}
        return call

    def get_me(self):
        return {"id": 9, "username": "test_bot"}

    def get_chat(self, c):
        return {"id": -100500, "title": "Kanal", "username": "kanal", "type": "channel"}

    def get_chat_member(self, c, u):
        return {"status": self.member_status}

    def safe(self, method, params=None, **k):
        self.sent.append((method, (params,), {}))
        return {"ok": 1}

    def call(self, method, params=None, **k):
        self.sent.append((method, (params,), {}))
        return True

    def texts(self, chat=None):
        out = []
        for name, a, k in self.sent:
            if name in ("sendPhoto", "editMessageMedia") and a and isinstance(a[0], dict):       # bot.call orqali rasmli xabar
                prm = a[0]
                if chat is None or prm.get("chat_id") == chat:
                    out.append(str(prm.get("caption") or (prm.get("media") or {}).get("caption") or ""))
                continue
            if name in ("send_message", "send_photo", "send_video", "send_document", "edit_message_text"):
                if chat is None or (a and a[0] == chat):
                    idx = 2 if name == "edit_message_text" else 1     # (edit: chat_id, message_id, matn)
                    out.append(str(a[idx]) if len(a) > idx else str(k.get("text", "")))
        return out


def make_app(channels: str = "", webapp_url: str = "https://site.test", admins: str = "1"):
    """Yangi bo'sh baza bilan App yaratadi (har bir test uchun alohida)."""
    tmp = tempfile.mkdtemp(prefix="mmtest_")
    os.environ.update(BOT_TOKEN=TOKEN, ADMINS=admins, DB_PATH=os.path.join(tmp, "bot.db"), CHANNELS=channels,
                      PORT="", WEBAPP_URL=webapp_url, CARD_NUMBER="8600123412341234")
    import sys
    sys.path.insert(0, str(ROOT))
    from app.config import Config
    import app.handlers  # noqa: F401  — hamma buyruq va tugmalarni ro'yxatdan o'tkazadi
    from app.core import App
    app = App(Config())
    app.bot = FakeBot()
    app.me = {"id": 9, "username": "test_bot"}
    app._tmp = tmp
    return app


def cleanup(app):
    try:
        app.db.conn.close()
    except Exception:  # noqa: BLE001
        pass
    shutil.rmtree(app._tmp, ignore_errors=True)


def message(uid: int, text: str, name: str = "Ali") -> dict:
    return {"update_id": 1, "message": {"message_id": 1, "date": 0, "text": text, "from": {"id": uid, "first_name": name},
                                        "chat": {"id": uid, "type": "private"}}}


def press(uid: int, data: str) -> dict:
    return {"update_id": 1, "callback_query": {"id": "c", "from": {"id": uid, "first_name": "Ali"}, "data": data,
                                                "message": {"message_id": 5, "chat": {"id": uid, "type": "private"}, "text": "x"}}}


def add_movie(app, code: int, title: str, **kw) -> int:
    kw.setdefault("poster", "P")
    mid = app.db.add_movie(code, title, kw.get("desc", "Izoh"), kw["poster"], kw.get("premium", False), 1, f"F{code}",
                           kw.get("ftype", "video"), kw.get("cat", "movie"))
    return mid


def init_data(uid: int, name: str = "Ali") -> str:
    d = {"auth_date": str(int(time.time())), "user": json.dumps({"id": uid, "first_name": name})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    d["hash"] = hmac.new(hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest(), check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(d)


class WebServer:
    """Sayt serverini vaqtinchalik portda ishga tushiradi."""

    def __init__(self, app):
        from app.webapp import make_handler
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def get(self, path: str, uid: int = 0, headers: dict = None):
        h = dict(headers or {})
        if uid:
            h["X-Init-Data"] = init_data(uid)
        req = urllib.request.Request(self.base + path, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read(), dict(e.headers)

    def json(self, path: str, uid: int = 0, headers: dict = None):
        st, body, _ = self.get(path, uid, headers)
        return st, json.loads(body.decode("utf-8"))

    def post(self, path: str, data: dict, uid: int = 0):
        h = {"Content-Type": "application/json"}
        if uid:
            h["X-Init-Data"] = init_data(uid)
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")

    def close(self):
        self.srv.shutdown()
