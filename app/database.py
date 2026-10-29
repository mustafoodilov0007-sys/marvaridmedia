"""SQLite ma'lumotlar bazasi (thread-safe)."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import genres
from .utils import escape_like, normalize, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY,
    first_name       TEXT,
    username         TEXT,
    joined_at        INTEGER NOT NULL,
    last_active      INTEGER NOT NULL,
    is_blocked       INTEGER NOT NULL DEFAULT 0,
    premium_until    INTEGER NOT NULL DEFAULT 0,
    premium_notified INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_users_joined  ON users(joined_at);
CREATE INDEX IF NOT EXISTS idx_users_active  ON users(last_active);
CREATE INDEX IF NOT EXISTS idx_users_premium ON users(premium_until);

CREATE TABLE IF NOT EXISTS movies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        INTEGER NOT NULL UNIQUE,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    poster_id   TEXT,
    is_premium  INTEGER NOT NULL DEFAULT 0,
    norm_title  TEXT    NOT NULL DEFAULT '',
    norm_desc   TEXT    NOT NULL DEFAULT '',
    views       INTEGER NOT NULL DEFAULT 0,
    added_by    INTEGER,
    created_at  INTEGER NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'movie',
    desc_html   TEXT    NOT NULL DEFAULT '',
    genres      TEXT    NOT NULL DEFAULT '',
    year        INTEGER NOT NULL DEFAULT 0,
    country     TEXT    NOT NULL DEFAULT '',
    lang        TEXT    NOT NULL DEFAULT '',
    quality     TEXT    NOT NULL DEFAULT '',
    group_link  TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_movies_views   ON movies(views);
CREATE INDEX IF NOT EXISTS idx_movies_created ON movies(created_at);

CREATE TABLE IF NOT EXISTS parts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id   INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    part_no    INTEGER NOT NULL,
    title      TEXT    NOT NULL DEFAULT '',
    file_id    TEXT    NOT NULL,
    file_type  TEXT    NOT NULL,
    views      INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    UNIQUE (movie_id, part_no)
);

CREATE TABLE IF NOT EXISTS shorts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id   INTEGER NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    file_id    TEXT    NOT NULL,
    kind       TEXT    NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_shorts_movie ON shorts(movie_id);

CREATE TABLE IF NOT EXISTS requests (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    query      TEXT    NOT NULL,
    norm       TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    done_at    INTEGER NOT NULL DEFAULT 0,
    movie_id   INTEGER
);
CREATE INDEX IF NOT EXISTS idx_requests_open ON requests(done_at, created_at);

CREATE TABLE IF NOT EXISTS history (
    user_id     INTEGER NOT NULL,
    movie_id    INTEGER NOT NULL,
    at          INTEGER NOT NULL,
    PRIMARY KEY (user_id, movie_id)
);
CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, at);

CREATE TABLE IF NOT EXISTS ratings (
    user_id     INTEGER NOT NULL,
    movie_id    INTEGER NOT NULL,
    value       INTEGER NOT NULL,          -- 1 = 👍, -1 = 👎
    at          INTEGER NOT NULL,
    PRIMARY KEY (user_id, movie_id)
);
CREATE INDEX IF NOT EXISTS idx_ratings_movie ON ratings(movie_id, value);

CREATE TABLE IF NOT EXISTS collections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    pos         INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS collection_items (
    collection_id INTEGER NOT NULL,
    movie_id      INTEGER NOT NULL,
    pos           INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (collection_id, movie_id)
);

CREATE TABLE IF NOT EXISTS channels (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id  TEXT,
    title    TEXT NOT NULL,
    url      TEXT NOT NULL,
    kind     TEXT NOT NULL DEFAULT 'public',
    added_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS join_requests (
    user_id    INTEGER NOT NULL,
    chat_id    TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, chat_id)
);

CREATE TABLE IF NOT EXISTS admins (
    user_id  INTEGER PRIMARY KEY,
    added_by INTEGER,
    added_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS searches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    query      TEXT    NOT NULL,
    norm       TEXT    NOT NULL,
    results    INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_searches_created ON searches(created_at);

CREATE TABLE IF NOT EXISTS plans (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    days      INTEGER NOT NULL,
    price     INTEGER NOT NULL DEFAULT 0,
    stars     INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    method       TEXT    NOT NULL,
    plan_id      INTEGER,
    days         INTEGER NOT NULL DEFAULT 0,
    amount       INTEGER NOT NULL DEFAULT 0,
    currency     TEXT    NOT NULL DEFAULT 'UZS',
    status       TEXT    NOT NULL,
    receipt_id   TEXT,
    receipt_type TEXT,
    note         TEXT    NOT NULL DEFAULT '',
    charge_id    TEXT,
    reviewed_by  INTEGER,
    reviewed_at  INTEGER,
    created_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_user   ON payments(user_id, status);
CREATE INDEX IF NOT EXISTS idx_payments_charge ON payments(charge_id);

CREATE TABLE IF NOT EXISTS payment_msgs (
    payment_id INTEGER NOT NULL,
    admin_id   INTEGER NOT NULL,
    message_id INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payment_msgs ON payment_msgs(payment_id);
"""

CATEGORIES = ("movie", "serial", "cartoon", "music")

_CATALOG_ROW = """
SELECT m.id, m.code, m.title, m.description, m.is_premium, m.views, m.created_at, m.category, m.poster_id,
       m.genres, m.year, m.country, m.lang, m.quality,
       (SELECT COUNT(*) FROM ratings r WHERE r.movie_id = m.id AND r.value = 1) AS likes,
       (SELECT COUNT(*) FROM ratings r WHERE r.movie_id = m.id AND r.value = -1) AS dislikes,
       (SELECT s.id FROM shorts s WHERE s.movie_id = m.id AND s.kind = 'video' ORDER BY s.id LIMIT 1) AS trailer,
       (SELECT COUNT(*) FROM parts p WHERE p.movie_id = m.id) AS parts
FROM movies m"""

_MOVIE_ROW = """
SELECT m.id, m.code, m.title, m.is_premium, m.views, m.created_at, m.category,
       (SELECT COUNT(*) FROM parts p WHERE p.movie_id = m.id) AS parts
FROM movies m
"""


class Database:
    def __init__(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None, timeout=30)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript(SCHEMA)
            self._migrate()

    def _migrate(self) -> None:
        """Eski bazaga yangi ustunlarni qo'shadi (ma'lumotlar saqlanib qoladi)."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(movies)").fetchall()}
        if "category" not in cols:
            # eski kinolarning hammasi «kino» turida qoladi
            self.conn.execute("ALTER TABLE movies ADD COLUMN category TEXT NOT NULL DEFAULT 'movie'")
        if "desc_html" not in cols:
            # izohning formatlangan nusxasi (premium emoji, qalin/kursiv) — kino yuborilganda shu ishlatiladi
            self.conn.execute("ALTER TABLE movies ADD COLUMN desc_html TEXT NOT NULL DEFAULT ''")
        if "genres" not in cols:
            # 🎭 janr va 📅 yil — eski kinolar uchun nom va izohdan avtomatik aniqlanadi
            self.conn.execute("ALTER TABLE movies ADD COLUMN genres TEXT NOT NULL DEFAULT ''")
            self.conn.execute("ALTER TABLE movies ADD COLUMN year INTEGER NOT NULL DEFAULT 0")
            for r in self.conn.execute("SELECT id, title, description, category FROM movies").fetchall():
                g = "" if r[3] == "music" else genres.dump(genres.detect(r[1], r[2]))
                self.conn.execute("UPDATE movies SET genres=?, year=? WHERE id=?",
                                  (g, genres.detect_year(r[1], r[2]), r[0]))
        if "country" not in cols:
            # 🌍 davlat va 🗣 til — eski kinolar uchun izohdan avtomatik aniqlanadi
            self.conn.execute("ALTER TABLE movies ADD COLUMN country TEXT NOT NULL DEFAULT ''")
            self.conn.execute("ALTER TABLE movies ADD COLUMN lang TEXT NOT NULL DEFAULT ''")
            for r in self.conn.execute("SELECT id, description FROM movies WHERE category<>'music'").fetchall():
                self.conn.execute("UPDATE movies SET country=?, lang=? WHERE id=?",
                                  (genres.detect_country(r[1]), genres.detect_lang(r[1]), r[0]))
        if "group_link" not in cols:  # 📺 serialning qolgan qismlari joylangan guruh havolasi
            self.conn.execute("ALTER TABLE movies ADD COLUMN group_link TEXT NOT NULL DEFAULT ''")
        if "quality" not in cols:
            self.conn.execute("ALTER TABLE movies ADD COLUMN quality TEXT NOT NULL DEFAULT ''")  # 🎞 «,720,1080,»
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_movies_category ON movies(category, created_at)")
        # musiqalar kodsiz: avval kod bilan qo'shilganlari ichki (manfiy) raqamga o'tkaziladi
        rows = self.conn.execute("SELECT id FROM movies WHERE category='music' AND code>0 ORDER BY id").fetchall()
        if rows:
            low = self.conn.execute("SELECT MIN(code) FROM movies WHERE code<0").fetchone()[0] or 0
            for r in rows:
                low -= 1
                self.conn.execute("UPDATE movies SET code=? WHERE id=?", (low, r[0]))

    # ───────── yordamchilar ─────────

    def q(self, sql: str, params: Iterable = ()) -> List[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchall()

    def q1(self, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(params)).fetchone()

    def val(self, sql: str, params: Iterable = (), default=0):
        row = self.q1(sql, params)
        return default if row is None or row[0] is None else row[0]

    def x(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, tuple(params))

    @contextmanager
    def tx(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
            except BaseException:
                self.conn.execute("ROLLBACK")
                raise
            else:
                self.conn.execute("COMMIT")

    def backup_to(self, target: Path) -> None:
        with self.lock:
            dst = sqlite3.connect(str(target))
            try:
                self.conn.backup(dst)
            finally:
                dst.close()

    def restore_from(self, source: Path) -> None:
        """Boshqa bazani (zaxira nusxani) joriy bazaning o'rniga yozadi."""
        src = sqlite3.connect(str(source))
        try:
            with self.lock:
                src.backup(self.conn)
                self.conn.execute("PRAGMA foreign_keys=ON")
                self.conn.executescript(SCHEMA)
                self._migrate()
        finally:
            src.close()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    # ───────── foydalanuvchilar ─────────

    def upsert_user(self, user: dict) -> bool:
        uid = user["id"]
        t = now()
        with self.lock:
            exists = self.conn.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone()
            if exists:
                self.conn.execute(
                    "UPDATE users SET first_name=?, username=?, last_active=?, is_blocked=0 WHERE user_id=?",
                    (user.get("first_name"), user.get("username"), t, uid))
                return False
            self.conn.execute(
                "INSERT INTO users(user_id, first_name, username, joined_at, last_active) VALUES (?,?,?,?,?)",
                (uid, user.get("first_name"), user.get("username"), t, t))
            return True

    def get_user(self, uid: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM users WHERE user_id=?", (uid,))

    def set_blocked(self, uid: int, blocked: bool) -> None:
        self.x("UPDATE users SET is_blocked=? WHERE user_id=?", (1 if blocked else 0, uid))

    def count_users(self) -> int:
        return self.val("SELECT COUNT(*) FROM users")

    def count_blocked(self) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=1")

    def count_joined_since(self, ts: int) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE joined_at>=?", (ts,))

    def count_active_since(self, ts: int) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE last_active>=?", (ts,))

    def count_audience(self, audience: str = "all") -> int:
        t = now()
        if audience == "premium":
            return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0 AND premium_until>?", (t,))
        if audience == "free":
            return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0 AND premium_until<=?", (t,))
        return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0")

    def user_ids(self, audience: str = "all") -> List[int]:
        t = now()
        if audience == "premium":
            rows = self.q("SELECT user_id FROM users WHERE is_blocked=0 AND premium_until>? ORDER BY user_id", (t,))
        elif audience == "free":
            rows = self.q("SELECT user_id FROM users WHERE is_blocked=0 AND premium_until<=? ORDER BY user_id", (t,))
        else:
            rows = self.q("SELECT user_id FROM users WHERE is_blocked=0 ORDER BY user_id")
        return [r[0] for r in rows]

    # ───────── premium ─────────

    def premium_until(self, uid: int) -> int:
        return self.val("SELECT premium_until FROM users WHERE user_id=?", (uid,))

    def grant_premium(self, uid: int, days: int) -> int:
        t = now()
        with self.tx() as c:
            row = c.execute("SELECT premium_until FROM users WHERE user_id=?", (uid,)).fetchone()
            until = max(t, row["premium_until"] if row else 0) + int(days) * 86400
            notified = 1 if until - t <= 2 * 86400 else 0
            if row:
                c.execute("UPDATE users SET premium_until=?, premium_notified=? WHERE user_id=?",
                          (until, notified, uid))
            else:
                c.execute("INSERT INTO users(user_id, joined_at, last_active, premium_until, premium_notified)"
                          " VALUES (?,?,?,?,?)", (uid, t, t, until, notified))
            return until

    def subtract_premium(self, uid: int, days: int) -> int:
        t = now()
        with self.tx() as c:
            row = c.execute("SELECT premium_until FROM users WHERE user_id=?", (uid,)).fetchone()
            if not row:
                return 0
            until = row["premium_until"] - int(days) * 86400
            if until <= t:
                until = 0
            c.execute("UPDATE users SET premium_until=? WHERE user_id=?", (until, uid))
            return until

    def revoke_premium(self, uid: int) -> bool:
        return self.x("UPDATE users SET premium_until=0, premium_notified=0 WHERE user_id=? AND premium_until>?",
                      (uid, now())).rowcount > 0

    def count_premium(self) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE premium_until>?", (now(),))

    def list_premium(self, limit: int, offset: int = 0) -> List[sqlite3.Row]:
        return self.q("SELECT user_id, first_name, username, premium_until FROM users WHERE premium_until>?"
                      " ORDER BY premium_until LIMIT ? OFFSET ?", (now(), limit, offset))

    def premium_due_reminders(self) -> List[sqlite3.Row]:
        t = now()
        return self.q("SELECT user_id, premium_until FROM users WHERE premium_notified=0 AND is_blocked=0"
                      " AND premium_until>? AND premium_until<=?", (t, t + 86400))

    def premium_expired_unnotified(self) -> List[sqlite3.Row]:
        return self.q("SELECT user_id, premium_until FROM users WHERE premium_notified<2 AND is_blocked=0"
                      " AND premium_until>0 AND premium_until<=?", (now(),))

    def set_premium_notified(self, uid: int, value: int) -> None:
        self.x("UPDATE users SET premium_notified=? WHERE user_id=?", (value, uid))

    # ───────── kinolar ─────────

    def next_code(self) -> int:
        """Kino/multfilm uchun keyingi kod (musiqalar kodlari manfiy — ularga ta'sir qilmaydi)."""
        return int(self.val("SELECT MAX(code) FROM movies WHERE code>0")) + 1

    def next_music_code(self) -> int:
        """Musiqalar kodsiz: ichki raqami manfiy (-1, -2, ...) — kino kodlari bilan aralashmaydi."""
        return int(self.val("SELECT MIN(code) FROM movies WHERE code<0")) - 1

    def get_movie(self, movie_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM movies WHERE id=?", (movie_id,))

    def get_movie_by_code(self, code: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM movies WHERE code=?", (code,))

    def add_movie(self, code: int, title: str, description: str, poster_id: Optional[str],
                  is_premium: bool, added_by: int, file_id: str, file_type: str,
                  category: str = "movie", desc_html: str = "", genre_keys=None, year: Optional[int] = None,
                  country: Optional[str] = None, lang: Optional[str] = None, quality: str = "",
                  group_link: str = "") -> int:
        t = now()
        if category not in CATEGORIES:
            category = "movie"
        if genre_keys is None:
            genre_keys = [] if category == "music" else genres.detect(title, description)
        if year is None:
            year = genres.detect_year(title, description)
        if country is None:
            country = "" if category == "music" else genres.detect_country(description)
        if lang is None:
            lang = "" if category == "music" else genres.detect_lang(description)
        with self.tx() as c:
            if category == "music":
                code = (c.execute("SELECT MIN(code) FROM movies WHERE code<0").fetchone()[0] or 0) - 1
            cur = c.execute(
                "INSERT INTO movies(code, title, description, poster_id, is_premium, norm_title, norm_desc,"
                " added_by, created_at, category, desc_html, genres, year, country, lang, quality, group_link)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, title, description or "", poster_id, 1 if is_premium else 0, normalize(title),
                 normalize(description or ""), added_by, t, category, desc_html or "",
                 genres.dump(genre_keys), year or 0, country or "", lang or "", quality or "", group_link or ""))
            movie_id = cur.lastrowid
            c.execute("INSERT INTO parts(movie_id, part_no, file_id, file_type, created_at) VALUES (?,?,?,?,?)",
                      (movie_id, 1, file_id, file_type, t))
            return movie_id

    def update_movie(self, movie_id: int, **fields) -> None:
        if "title" in fields:
            fields["norm_title"] = normalize(fields["title"])
        if "description" in fields:
            fields["description"] = fields["description"] or ""
            fields["norm_desc"] = normalize(fields["description"])
        if "is_premium" in fields:
            fields["is_premium"] = 1 if fields["is_premium"] else 0
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        self.x(f"UPDATE movies SET {cols} WHERE id=?", list(fields.values()) + [movie_id])

    def delete_movie(self, movie_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM ratings WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM collection_items WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM history WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM shorts WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM parts WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM movies WHERE id=?", (movie_id,))

    def add_part(self, movie_id: int, file_id: str, file_type: str) -> int:
        with self.tx() as c:
            no = (c.execute("SELECT MAX(part_no) FROM parts WHERE movie_id=?", (movie_id,)).fetchone()[0] or 0) + 1
            c.execute("INSERT INTO parts(movie_id, part_no, file_id, file_type, created_at) VALUES (?,?,?,?,?)",
                      (movie_id, no, file_id, file_type, now()))
            return no

    def get_parts(self, movie_id: int) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM parts WHERE movie_id=? ORDER BY part_no", (movie_id,))

    def count_parts(self, movie_id: int) -> int:
        return self.val("SELECT COUNT(*) FROM parts WHERE movie_id=?", (movie_id,))

    def get_part(self, part_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM parts WHERE id=?", (part_id,))

    def get_part_by_no(self, movie_id: int, part_no: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM parts WHERE movie_id=? AND part_no=?", (movie_id, part_no))

    def delete_part(self, part_id: int) -> Optional[int]:
        """Qismni o'chiradi va qolganlarini qayta raqamlaydi. Qolgan qismlar sonini qaytaradi."""
        with self.tx() as c:
            p = c.execute("SELECT movie_id FROM parts WHERE id=?", (part_id,)).fetchone()
            if not p:
                return None
            c.execute("DELETE FROM parts WHERE id=?", (part_id,))
            rows = c.execute("SELECT id FROM parts WHERE movie_id=? ORDER BY part_no", (p["movie_id"],)).fetchall()
            for i, r in enumerate(rows, 1):
                c.execute("UPDATE parts SET part_no=? WHERE id=?", (i, r["id"]))
            if not rows:
                c.execute("DELETE FROM shorts WHERE movie_id=?", (p["movie_id"],))
                c.execute("DELETE FROM movies WHERE id=?", (p["movie_id"],))
            return len(rows)

    def inc_views(self, movie_id: int, part_id: int) -> None:
        with self.tx() as c:
            c.execute("UPDATE movies SET views=views+1 WHERE id=?", (movie_id,))
            c.execute("UPDATE parts SET views=views+1 WHERE id=?", (part_id,))

    def movie_rows(self, ids: List[int]) -> List[sqlite3.Row]:
        if not ids:
            return []
        ph = ",".join("?" * len(ids))
        rows = self.q(_MOVIE_ROW + f" WHERE m.id IN ({ph})", ids)
        by_id = {r["id"]: r for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    @staticmethod
    def _scope_sql(scope: Optional[str]) -> str:
        """scope: None — hammasi, 'video' — kino va multfilmlar, 'music' — faqat musiqa."""
        if scope == "video":
            return " AND category<>'music'"
        if scope == "music":
            return " AND category='music'"
        return ""

    def search_candidates(self, tokens: List[str], limit: int = 400, scope: Optional[str] = None) -> List[sqlite3.Row]:
        if not tokens:
            return []
        where = " AND ".join(["(norm_title || ' ' || norm_desc) LIKE ? ESCAPE '\\'"] * len(tokens))
        params = [f"%{escape_like(t)}%" for t in tokens] + [limit]
        return self.q(f"SELECT id, norm_title, views FROM movies WHERE {where}{self._scope_sql(scope)} LIMIT ?",
                      params)

    def find_title(self, norm_title: str, category: str) -> Optional[sqlite3.Row]:
        return self.q1("SELECT id, code, title FROM movies WHERE norm_title=? AND category=? LIMIT 1",
                       (norm_title, category))

    def all_titles(self, scope: Optional[str] = None) -> List[sqlite3.Row]:
        return self.q("SELECT id, norm_title FROM movies WHERE 1=1" + self._scope_sql(scope))

    # Top / Yangi / Tasodifiy — faqat kino va multfilmlar (musiqa alohida bo'limda)
    def top_movies(self, limit: int, include_premium: bool = True) -> List[sqlite3.Row]:
        return self.q(_MOVIE_ROW + " WHERE (? OR m.is_premium=0) AND m.category<>'music'"
                      " ORDER BY m.views DESC, m.id DESC LIMIT ?", (1 if include_premium else 0, limit))

    def new_movies(self, limit: int, include_premium: bool = True) -> List[sqlite3.Row]:
        return self.q(_MOVIE_ROW + " WHERE (? OR m.is_premium=0) AND m.category<>'music'"
                      " ORDER BY m.created_at DESC, m.id DESC LIMIT ?", (1 if include_premium else 0, limit))

    def random_movie(self, include_premium: bool = True) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM movies WHERE (? OR is_premium=0) AND category<>'music'"
                       " ORDER BY RANDOM() LIMIT 1", (1 if include_premium else 0,))

    def count_movies(self) -> int:
        return self.val("SELECT COUNT(*) FROM movies")

    def count_by_category(self) -> Dict[str, int]:
        out = {c: 0 for c in CATEGORIES}
        for r in self.q("SELECT category, COUNT(*) AS n FROM movies GROUP BY category"):
            out[r["category"] if r["category"] in out else "movie"] += r["n"]
        return out

    # ───────── 🎬 kino so'rovlari ─────────

    def add_request(self, uid: int, query: str) -> int:
        return self.x("INSERT INTO requests(user_id, query, norm, created_at) VALUES (?,?,?,?)",
                      (uid, query[:300], normalize(query)[:300], now())).lastrowid

    def open_requests(self, since: int) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM requests WHERE done_at=0 AND created_at>=? ORDER BY id", (since,))

    def close_request(self, request_id: int, movie_id: int) -> None:
        self.x("UPDATE requests SET done_at=?, movie_id=? WHERE id=?", (now(), movie_id, request_id))

    def count_open_requests(self, since: int) -> int:
        return self.val("SELECT COUNT(*) FROM requests WHERE done_at=0 AND created_at>=?", (since,))

    # ───────── shorts (qisqa video / rasm) ─────────

    def add_short(self, movie_id: int, file_id: str, kind: str) -> int:
        return self.x("INSERT INTO shorts(movie_id, file_id, kind, created_at) VALUES (?,?,?,?)",
                      (movie_id, file_id, kind, now())).lastrowid

    def get_short(self, short_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM shorts WHERE id=?", (short_id,))

    def count_shorts(self, movie_id: Optional[int] = None) -> int:
        if movie_id is None:
            return self.val("SELECT COUNT(*) FROM shorts")
        return self.val("SELECT COUNT(*) FROM shorts WHERE movie_id=?", (movie_id,))

    def movie_shorts(self, movie_id: int) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM shorts WHERE movie_id=? ORDER BY id", (movie_id,))

    def delete_shorts(self, movie_id: int) -> List[int]:
        ids = [r[0] for r in self.q("SELECT id FROM shorts WHERE movie_id=?", (movie_id,))]
        self.x("DELETE FROM shorts WHERE movie_id=?", (movie_id,))
        return ids

    def shorts_feed(self, limit: int = 10, offset: int = 0) -> List[sqlite3.Row]:
        return self.q(
            "SELECT s.id AS short_id, s.kind AS short_kind, m.id, m.code, m.title, m.description, m.is_premium,"
            " m.views, m.created_at, m.category, m.poster_id, m.genres, m.year, m.country, m.lang, m.quality,"
            " (SELECT COUNT(*) FROM parts p WHERE p.movie_id = m.id) AS parts"
            " FROM shorts s JOIN movies m ON m.id = s.movie_id ORDER BY s.id DESC LIMIT ? OFFSET ?",
            (limit, offset))

    # ───────── sayt (Mini App) katalogi ─────────

    def catalog(self, category: str, sort: str = "new", tokens: Optional[List[str]] = None,
                limit: int = 30, offset: int = 0, movie_id: Optional[int] = None,
                genre: Optional[str] = None, country: Optional[str] = None, year: Optional[int] = None,
                lang: Optional[str] = None) -> List[sqlite3.Row]:
        if category in (None, "video"):  # kino + serial + multfilm (musiqasiz)
            where, params = ["m.category<>'music'"], []
        else:
            where, params = ["m.category=?"], [category]
        if genre:
            where.append("m.genres LIKE ?")
            params.append(f"%,{genre},%")
        if country:
            where.append("m.country=?")
            params.append(country)
        if year:
            where.append("m.year=?")
            params.append(year)
        if lang:
            where.append("m.lang=?")
            params.append(lang)
        if movie_id is not None:
            where.append("m.id=?")
            params.append(movie_id)
        for t in tokens or []:
            where.append("(m.norm_title || ' ' || m.norm_desc) LIKE ? ESCAPE '\\'")
            params.append(f"%{escape_like(t)}%")
        order = {"top": "m.views DESC, m.id DESC",
                 "rating": "(likes + 1.0) / (likes + dislikes + 2.0) DESC, likes DESC, m.views DESC, m.id DESC"
                 }.get(sort, "m.created_at DESC, m.id DESC")
        sql = (_CATALOG_ROW + f" WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?")
        return self.q(sql, params + [limit, offset])

    def catalog_rows(self, ids: List[int]) -> List[sqlite3.Row]:
        if not ids:
            return []
        rows = self.q(_CATALOG_ROW + f" WHERE m.id IN ({','.join('?' * len(ids))})", ids)
        by_id = {r["id"]: r for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def genre_counts(self, category: str) -> Dict[str, int]:
        """Har bir janrda nechta kino bor (faqat bo'sh bo'lmaganlari)."""
        out: Dict[str, int] = {}
        where, params = (("category<>'music'", ()) if category == "video" else ("category=?", (category,)))
        for r in self.q(f"SELECT genres FROM movies WHERE {where} AND genres<>''", params):
            for k in genres.parse(r[0]):
                out[k] = out.get(k, 0) + 1
        return {k: out[k] for k in genres.GENRES if k in out}

    def facets(self, category: str) -> Dict[str, Dict]:
        """Saytdagi filtrlar uchun: qaysi davlat, yil va tilda nechta kino bor."""
        out: Dict[str, Dict] = {}
        where, params = (("category<>'music'", ()) if category == "video" else ("category=?", (category,)))
        for col in ("country", "year", "lang"):
            rows = self.q(f"SELECT {col} AS v, COUNT(*) AS n FROM movies WHERE {where} AND {col}<>'' AND {col}<>0"
                          f" GROUP BY {col}", params)
            out[col] = {r["v"]: r["n"] for r in rows}
        return out

    def similar(self, movie_id: int, limit: int = 12) -> List[sqlite3.Row]:
        """O'xshash kinolar: shu turdagi, umumiy janri ko'p bo'lganlari oldin, keyin eng ko'p ko'rilganlar."""
        movie = self.get_movie(movie_id)
        if not movie or movie["category"] == "music":
            return []
        mine = set(genres.parse(movie["genres"]))
        rows = self.q(_CATALOG_ROW + " WHERE m.category=? AND m.id<>? ORDER BY m.views DESC, m.id DESC LIMIT 300",
                      (movie["category"], movie_id))
        def score(r):
            common = len(mine & set(genres.parse(r["genres"])))
            near = 1 if movie["year"] and r["year"] and abs(movie["year"] - r["year"]) <= 3 else 0
            return common * 10 + near
        ranked = sorted(enumerate(rows), key=lambda x: (-score(x[1]), x[0]))
        return [r for _, r in ranked[:limit]]

    # ───────── 👍 / 👎 tomoshabin bahosi ─────────

    def rate(self, uid: int, movie_id: int, value: int) -> int:
        """Baho qo'yadi; xuddi shu bahoni qayta bossa — bekor qiladi. Yangi holatni qaytaradi (1, -1 yoki 0)."""
        with self.tx() as c:
            row = c.execute("SELECT value FROM ratings WHERE user_id=? AND movie_id=?", (uid, movie_id)).fetchone()
            if row and row[0] == value:
                c.execute("DELETE FROM ratings WHERE user_id=? AND movie_id=?", (uid, movie_id))
                return 0
            c.execute("INSERT INTO ratings(user_id, movie_id, value, at) VALUES (?,?,?,?)"
                      " ON CONFLICT(user_id, movie_id) DO UPDATE SET value=excluded.value, at=excluded.at",
                      (uid, movie_id, value, now()))
            return value

    def rating(self, movie_id: int, uid: int = 0) -> Dict[str, int]:
        likes = self.val("SELECT COUNT(*) FROM ratings WHERE movie_id=? AND value=1", (movie_id,))
        dislikes = self.val("SELECT COUNT(*) FROM ratings WHERE movie_id=? AND value=-1", (movie_id,))
        mine = self.val("SELECT value FROM ratings WHERE movie_id=? AND user_id=?", (movie_id, uid)) if uid else 0
        return {"likes": likes, "dislikes": dislikes, "mine": mine or 0}

    def audience_choice(self, limit: int = 15, min_votes: int = 3) -> List[sqlite3.Row]:
        """👑 Tomoshabinlar tanlovi: eng ko'p 👍 olgan kino va multfilmlar (ovozlar soni hisobga olinadi)."""
        return self.q("SELECT * FROM (" + _CATALOG_ROW + " WHERE m.category<>'music') t"
                      " WHERE likes + dislikes >= ?"
                      " ORDER BY (likes + 1.0) / (likes + dislikes + 2.0) DESC, likes DESC LIMIT ?", (min_votes, limit))

    # ───────── 📚 to'plamlar ─────────

    def list_collections(self) -> List[sqlite3.Row]:
        return self.q("SELECT c.*, (SELECT COUNT(*) FROM collection_items i WHERE i.collection_id=c.id) AS n"
                      " FROM collections c ORDER BY c.pos, c.id")

    def get_collection(self, cid: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM collections WHERE id=?", (cid,))

    def add_collection(self, title: str) -> int:
        pos = self.val("SELECT COALESCE(MAX(pos), 0) + 1 FROM collections")
        return self.x("INSERT INTO collections(title, pos, created_at) VALUES (?,?,?)", (title, pos, now())).lastrowid

    def rename_collection(self, cid: int, title: str) -> None:
        self.x("UPDATE collections SET title=? WHERE id=?", (title, cid))

    def delete_collection(self, cid: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM collection_items WHERE collection_id=?", (cid,))
            c.execute("DELETE FROM collections WHERE id=?", (cid,))

    def move_collection(self, cid: int, up: bool) -> None:
        rows = [r["id"] for r in self.list_collections()]
        if cid not in rows:
            return
        i = rows.index(cid)
        j = i - 1 if up else i + 1
        if 0 <= j < len(rows):
            rows[i], rows[j] = rows[j], rows[i]
            with self.tx() as c:
                for pos, x in enumerate(rows):
                    c.execute("UPDATE collections SET pos=? WHERE id=?", (pos, x))

    def add_to_collection(self, cid: int, movie_id: int) -> bool:
        pos = self.val("SELECT COALESCE(MAX(pos), 0) + 1 FROM collection_items WHERE collection_id=?", (cid,))
        cur = self.x("INSERT OR IGNORE INTO collection_items(collection_id, movie_id, pos) VALUES (?,?,?)",
                     (cid, movie_id, pos))
        return cur.rowcount > 0

    def remove_from_collection(self, cid: int, movie_id: int) -> None:
        self.x("DELETE FROM collection_items WHERE collection_id=? AND movie_id=?", (cid, movie_id))

    def collection_movies(self, cid: int, limit: int = 200) -> List[sqlite3.Row]:
        return self.q(_CATALOG_ROW.replace("FROM movies m", "FROM collection_items ci JOIN movies m ON m.id = ci.movie_id")
                      + " WHERE ci.collection_id=? ORDER BY ci.pos, ci.movie_id LIMIT ?", (cid, limit))

    # ───────── 🕘 ko'rilganlar tarixi ─────────

    def touch_history(self, uid: int, movie_id: int) -> None:
        self.x("INSERT INTO history(user_id, movie_id, at) VALUES (?,?,?)"
               " ON CONFLICT(user_id, movie_id) DO UPDATE SET at=excluded.at", (uid, movie_id, now()))

    def history(self, uid: int, limit: int = 15) -> List[sqlite3.Row]:
        return self.q(_CATALOG_ROW.replace("FROM movies m", "FROM history h JOIN movies m ON m.id = h.movie_id")
                      + " WHERE h.user_id=? AND m.category<>'music' ORDER BY h.at DESC LIMIT ?", (uid, limit))

    def clear_history(self, uid: int) -> int:
        return self.x("DELETE FROM history WHERE user_id=?", (uid,)).rowcount

    def prune_history(self, keep: int = 60) -> None:
        self.x("DELETE FROM history WHERE rowid IN (SELECT rowid FROM (SELECT rowid, ROW_NUMBER() OVER"
               " (PARTITION BY user_id ORDER BY at DESC) AS n FROM history) WHERE n>?)", (keep,))

    def count_premium_movies(self) -> int:
        return self.val("SELECT COUNT(*) FROM movies WHERE is_premium=1")

    def count_serials(self) -> int:
        return self.val("SELECT COUNT(*) FROM (SELECT movie_id FROM parts GROUP BY movie_id HAVING COUNT(*)>1)")

    def count_parts_total(self) -> int:
        return self.val("SELECT COUNT(*) FROM parts")

    def total_views(self) -> int:
        return self.val("SELECT SUM(views) FROM movies")

    # ───────── kanallar ─────────

    def list_channels(self) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM channels ORDER BY id")

    def get_channel(self, channel_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM channels WHERE id=?", (channel_id,))

    def add_channel(self, chat_id: Optional[str], title: str, url: str, kind: str) -> int:
        return self.x("INSERT INTO channels(chat_id, title, url, kind, added_at) VALUES (?,?,?,?,?)",
                      (chat_id, title, url, kind, now())).lastrowid

    def channel_exists(self, chat_id: str) -> bool:
        return self.q1("SELECT 1 FROM channels WHERE chat_id=?", (chat_id,)) is not None

    def delete_channel(self, channel_id: int) -> None:
        self.x("DELETE FROM channels WHERE id=?", (channel_id,))

    def add_join_request(self, uid: int, chat_id: str) -> None:
        self.x("INSERT OR IGNORE INTO join_requests(user_id, chat_id, created_at) VALUES (?,?,?)",
               (uid, str(chat_id), now()))

    def has_join_request(self, uid: int, chat_id: str) -> bool:
        return self.q1("SELECT 1 FROM join_requests WHERE user_id=? AND chat_id=?", (uid, str(chat_id))) is not None

    # ───────── adminlar ─────────

    def list_admins(self) -> List[sqlite3.Row]:
        return self.q("SELECT a.user_id, a.added_at, u.first_name, u.username FROM admins a"
                      " LEFT JOIN users u ON u.user_id=a.user_id ORDER BY a.added_at")

    def admin_ids(self) -> List[int]:
        return [r[0] for r in self.q("SELECT user_id FROM admins")]

    def add_admin(self, uid: int, added_by: int) -> bool:
        return self.x("INSERT OR IGNORE INTO admins(user_id, added_by, added_at) VALUES (?,?,?)",
                      (uid, added_by, now())).rowcount > 0

    def remove_admin(self, uid: int) -> bool:
        return self.x("DELETE FROM admins WHERE user_id=?", (uid,)).rowcount > 0

    # ───────── sozlamalar ─────────

    def get_settings(self) -> Dict[str, str]:
        return {r["key"]: r["value"] for r in self.q("SELECT key, value FROM settings")}

    def set_setting(self, key: str, value: str) -> None:
        self.x("INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)", (key, str(value)))

    def delete_setting(self, key: str) -> None:
        self.x("DELETE FROM settings WHERE key=?", (key,))

    # ───────── qidiruvlar ─────────

    def log_search(self, uid: int, query: str, norm: str, results: int) -> int:
        return self.x("INSERT INTO searches(user_id, query, norm, results, created_at) VALUES (?,?,?,?,?)",
                      (uid, query[:200], norm[:200], results, now())).lastrowid

    def get_search(self, search_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM searches WHERE id=?", (search_id,))

    def count_searches_since(self, ts: int) -> int:
        return self.val("SELECT COUNT(*) FROM searches WHERE created_at>=?", (ts,))

    def top_failed_queries(self, since: int, limit: int = 5) -> List[sqlite3.Row]:
        return self.q("SELECT norm, MIN(query) AS query, COUNT(*) AS n FROM searches"
                      " WHERE results=0 AND created_at>=? AND norm<>'' GROUP BY norm ORDER BY n DESC LIMIT ?",
                      (since, limit))

    def popular_queries(self, since: int, limit: int = 12, min_count: int = 2) -> List[sqlite3.Row]:
        """Eng ko'p qidirilgan (va natija topilgan) so'rovlar — kamida `min_count` marta, shaxsiy so'rov chiqmasin."""
        return self.q("SELECT norm, MIN(query) AS query, COUNT(*) AS n FROM searches WHERE results>0 AND created_at>=?"
                      " AND norm<>'' AND LENGTH(norm)>=3 GROUP BY norm HAVING COUNT(DISTINCT COALESCE(user_id, 0))>=?"
                      " ORDER BY n DESC LIMIT ?", (since, min_count, limit))

    def recommend(self, uid: int, limit: int = 15) -> List[sqlite3.Row]:
        """🎯 Siz uchun: foydalanuvchining ko'rgan va 👍 bergan kinolari janrlariga o'xshash, hali ko'rmaganlari."""
        if not uid:
            return []
        liked = self.q("SELECT m.id, m.genres FROM history h JOIN movies m ON m.id = h.movie_id WHERE h.user_id=?"
                       " UNION ALL SELECT m.id, m.genres FROM ratings r JOIN movies m ON m.id = r.movie_id"
                       " WHERE r.user_id=? AND r.value=1", (uid, uid))
        freq: Dict[str, int] = {}
        seen = set()
        for r in liked:
            seen.add(r["id"])
            for g in genres.parse(r["genres"]):
                freq[g] = freq.get(g, 0) + 1
        if not freq:
            return []
        rows = self.q(_CATALOG_ROW + " WHERE m.category<>'music' ORDER BY m.views DESC, m.id DESC LIMIT 400")
        scored = []
        for i, r in enumerate(rows):
            if r["id"] in seen:
                continue
            sc = sum(freq.get(g, 0) for g in genres.parse(r["genres"]))
            if sc:
                scored.append((-sc, i, r))
        scored.sort(key=lambda x: (x[0], x[1]))
        return [r for _, _, r in scored[:limit]]

    def prune_searches(self, before: int) -> None:
        self.x("DELETE FROM searches WHERE created_at<?", (before,))

    # ───────── tariflar ─────────

    def list_plans(self, active_only: bool = True) -> List[sqlite3.Row]:
        sql = "SELECT * FROM plans" + (" WHERE is_active=1" if active_only else "") + " ORDER BY days, id"
        return self.q(sql)

    def get_plan(self, plan_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM plans WHERE id=?", (plan_id,))

    def add_plan(self, days: int, price: int, stars: int) -> int:
        return self.x("INSERT INTO plans(days, price, stars) VALUES (?,?,?)", (days, price, stars)).lastrowid

    def deactivate_plan(self, plan_id: int) -> None:
        self.x("UPDATE plans SET is_active=0 WHERE id=?", (plan_id,))

    def count_plans_all(self) -> int:
        return self.val("SELECT COUNT(*) FROM plans")

    # ───────── to'lovlar ─────────

    def create_payment(self, user_id: int, kind: str, method: str, status: str, plan_id=None, days: int = 0,
                       amount: int = 0, currency: str = "UZS", receipt_id=None, receipt_type=None,
                       note: str = "", charge_id=None) -> int:
        t = now()
        reviewed = t if status != "pending" else None
        return self.x(
            "INSERT INTO payments(user_id, kind, method, plan_id, days, amount, currency, status, receipt_id,"
            " receipt_type, note, charge_id, reviewed_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, kind, method, plan_id, days, amount, currency, status, receipt_id, receipt_type,
             note or "", charge_id, reviewed, t)).lastrowid

    def get_payment(self, payment_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM payments WHERE id=?", (payment_id,))

    def payment_by_charge(self, charge_id: str) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM payments WHERE charge_id=?", (charge_id,))

    def set_payment_status(self, payment_id: int, status: str, reviewer: Optional[int],
                           expected: str = "pending") -> bool:
        return self.x("UPDATE payments SET status=?, reviewed_by=?, reviewed_at=? WHERE id=? AND status=?",
                      (status, reviewer, now(), payment_id, expected)).rowcount > 0

    def count_pending_user(self, uid: int) -> int:
        return self.val("SELECT COUNT(*) FROM payments WHERE user_id=? AND status='pending'", (uid,))

    def count_pending(self) -> int:
        return self.val("SELECT COUNT(*) FROM payments WHERE status='pending'")

    def payment_totals(self) -> Dict[str, Dict[str, int]]:
        """{'premium:card': {'n': .., 'total': ..}, 'premium:stars': .., 'donate:card': .., ...}"""
        rows = self.q("SELECT kind, method, COUNT(*) AS n, COALESCE(SUM(amount),0) AS total FROM payments"
                      " WHERE status='approved' GROUP BY kind, method")
        out: Dict[str, Dict[str, int]] = {}
        for r in rows:
            out[f"{r['kind']}:{r['method']}"] = {"n": r["n"], "total": r["total"]}
        return out

    def add_payment_msg(self, payment_id: int, admin_id: int, message_id: int) -> None:
        self.x("INSERT INTO payment_msgs(payment_id, admin_id, message_id) VALUES (?,?,?)",
               (payment_id, admin_id, message_id))

    def get_payment_msgs(self, payment_id: int) -> List[sqlite3.Row]:
        return self.q("SELECT admin_id, message_id FROM payment_msgs WHERE payment_id=?", (payment_id,))
