"""SQLite ma'lumotlar bazasi (thread-safe)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS titles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    src_id      INTEGER UNIQUE,           -- hozirgi saytdagi (bot bazasidagi) id
    code        INTEGER NOT NULL DEFAULT 0,
    title       TEXT    NOT NULL,
    norm        TEXT    NOT NULL DEFAULT '',
    description TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT 'movie',
    year        INTEGER NOT NULL DEFAULT 0,
    genres      TEXT    NOT NULL DEFAULT '[]',   -- [{"key","label"}]
    country     TEXT    NOT NULL DEFAULT '',
    lang        TEXT    NOT NULL DEFAULT '',
    quality     TEXT    NOT NULL DEFAULT '',
    duration    INTEGER NOT NULL DEFAULT 0,
    age         INTEGER NOT NULL DEFAULT 0,
    imdb        TEXT    NOT NULL DEFAULT '',
    poster_v    TEXT    NOT NULL DEFAULT '',
    published   INTEGER NOT NULL DEFAULT 1,
    views       INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_titles_cat ON titles(category, created_at);
CREATE INDEX IF NOT EXISTS idx_titles_code ON titles(code);

CREATE TABLE IF NOT EXISTS videos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title_id   INTEGER NOT NULL,
    part_no    INTEGER NOT NULL DEFAULT 1,
    key        TEXT    NOT NULL,
    ctype      TEXT    NOT NULL DEFAULT 'video/mp4',
    size       INTEGER NOT NULL DEFAULT 0,
    duration   INTEGER NOT NULL DEFAULT 0,
    upload_id  TEXT    NOT NULL DEFAULT '',
    status     TEXT    NOT NULL DEFAULT 'uploading',   -- uploading | ready
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_videos_title ON videos(title_id, part_no);

CREATE TABLE IF NOT EXISTS view_days (
    title_id INTEGER NOT NULL,
    day      INTEGER NOT NULL,
    n        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (title_id, day)
);
CREATE INDEX IF NOT EXISTS idx_view_days_day ON view_days(day);

CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
"""


def now() -> int:
    return int(time.time())


def today() -> int:
    return (now() + 18000) // 86400   # Toshkent vaqti bo'yicha kun raqami


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.executescript(SCHEMA)

    def q(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchall()

    def q1(self, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchone()

    def val(self, sql: str, params: Iterable = (), default=0):
        r = self.q1(sql, params)
        return default if r is None or r[0] is None else r[0]

    def x(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, tuple(params))

    @contextmanager
    def tx(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.execute("COMMIT")
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise

    # ───── kv ─────
    def get_kv(self, k: str, default: str = "") -> str:
        r = self.q1("SELECT v FROM kv WHERE k=?", (k,))
        return r["v"] if r else default

    def set_kv(self, k: str, v: str) -> None:
        self.x("INSERT INTO kv(k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ───── kinolar ─────
    def upsert_title(self, d: dict) -> int:
        t = now()
        genres = json.dumps(d.get("genres") or [], ensure_ascii=False)
        with self.tx() as c:
            row = c.execute("SELECT id FROM titles WHERE src_id=?", (d["src_id"],)).fetchone()
            vals = (d["code"], d["title"], d["norm"], d.get("description", ""), d["category"], d.get("year", 0), genres,
                    d.get("country", ""), d.get("lang", ""), d.get("quality", ""), d.get("duration", 0), d.get("age", 0),
                    d.get("imdb", ""), d.get("poster_v", ""), t)
            if row:
                c.execute("UPDATE titles SET code=?, title=?, norm=?, description=?, category=?, year=?, genres=?, country=?,"
                          " lang=?, quality=?, duration=?, age=?, imdb=?, poster_v=?, updated_at=? WHERE id=?", vals + (row["id"],))
                return row["id"]
            cur = c.execute("INSERT INTO titles(code, title, norm, description, category, year, genres, country, lang,"
                            " quality, duration, age, imdb, poster_v, updated_at, created_at, src_id)"
                            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals + (d.get("added") or t, d["src_id"]))
            return cur.lastrowid

    def add_view(self, title_id: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE titles SET views=views+1 WHERE id=?", (title_id,))
            c.execute("INSERT INTO view_days(title_id, day, n) VALUES (?,?,1)"
                      " ON CONFLICT(title_id, day) DO UPDATE SET n=n+1", (title_id, today()))

    def prune_views(self, keep_days: int = 60) -> None:
        self.x("DELETE FROM view_days WHERE day < ?", (today() - keep_days,))
