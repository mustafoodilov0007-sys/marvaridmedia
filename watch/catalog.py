"""Katalogni hozirgi saytdan (bot bazasi) olib turish: nom, poster, janr, yil va h.k. Videolar alohida yuklanadi."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, Optional

from db import DB
from textutil import normalize

log = logging.getLogger("catalog")

CATS = ("movie", "serial", "cartoon")
_UA = {"User-Agent": "MarvaridWatchSync/1.0"}


def _get_json(url: str, timeout: float = 25) -> dict:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_all(source: str, get: Callable[[str], dict] = _get_json, pause: float = 0.3):
    """Hamma kino/serial/multfilmlar ro'yxatini sahifalab oladi (generator)."""
    for cat in CATS:
        offset, pages = 0, 0
        while pages < 400:
            d = get(f"{source}/pub/catalog?cat={cat}&sort=new&offset={offset}")
            if not d.get("ok"):
                raise RuntimeError(f"manba javobi noto'g'ri: {d.get('reason')}")
            for it in d.get("items", []):
                yield it
            pages += 1
            if not d.get("more") or not d.get("items"):
                break
            offset += len(d["items"])
            time.sleep(pause)


def to_row(it: dict) -> Optional[dict]:
    if not it.get("id") or not it.get("title"):
        return None
    return {
        "src_id": int(it["id"]), "code": int(it.get("code") or 0), "title": it["title"], "norm": normalize(it["title"]),
        "description": it.get("desc") or "", "category": it.get("cat") if it.get("cat") in CATS else "movie",
        "year": int(it.get("year") or 0), "genres": it.get("genres") or [], "country": it.get("country") or "",
        "lang": it.get("lang") or "", "quality": it.get("quality") or "", "duration": int(it.get("duration") or 0),
        "age": int(it.get("age") or 0), "imdb": it.get("imdb") or "", "poster_v": it.get("poster") or "",
        "added": int(it.get("added") or 0) or None,
    }


class Syncer:
    def __init__(self, db: DB, source: str):
        self.db, self.source = db, source
        self.lock = threading.Lock()
        self.state: Dict = {"running": False, "done": 0, "error": "", "finished": int(db.get_kv("sync_at", "0") or 0)}

    def start(self) -> bool:
        if not self.source:
            self.state["error"] = "SOURCE_URL berilmagan"
            return False
        with self.lock:
            if self.state["running"]:
                return False
            self.state.update(running=True, done=0, error="")
        threading.Thread(target=self._run, name="catalog-sync", daemon=True).start()
        return True

    def _run(self, get: Callable[[str], dict] = _get_json) -> None:
        try:
            n = 0
            for it in fetch_all(self.source, get):
                row = to_row(it)
                if row:
                    self.db.upsert_title(row)
                    n += 1
                    self.state["done"] = n
            self.db.set_kv("sync_at", str(int(time.time())))
            self.state["finished"] = int(time.time())
            log.info("Katalog yangilandi: %s ta", n)
        except Exception as exc:  # noqa: BLE001
            log.exception("Katalogni yangilashda xatolik")
            self.state["error"] = str(exc)[:200]
        finally:
            self.state["running"] = False

    def loop(self, stopping: threading.Event, every: int = 6 * 3600) -> None:
        """Fon vazifasi: har 6 soatda katalogni yangilaydi."""
        if stopping.wait(20):
            return
        while not stopping.is_set():
            last = int(self.db.get_kv("sync_at", "0") or 0)
            if time.time() - last >= every:
                self.start()
            if stopping.wait(1800):
                return
