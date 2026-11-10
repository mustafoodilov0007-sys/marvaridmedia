"""SQLite ma'lumotlar bazasi (thread-safe)."""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from . import genres
from .utils import duration_of, escape_like, normalize, now

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

CREATE TABLE IF NOT EXISTS promos (
    code       TEXT PRIMARY KEY,
    days       INTEGER NOT NULL,
    created_by INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    used_by    INTEGER NOT NULL DEFAULT 0,
    used_at    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_promos_days ON promos(used_by, days);

CREATE TABLE IF NOT EXISTS view_days (   -- kunlik ko'rishlar (haftalik TOP uchun)
    movie_id INTEGER NOT NULL,
    day      INTEGER NOT NULL,
    n        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (movie_id, day)
);
CREATE INDEX IF NOT EXISTS idx_view_days_day ON view_days(day);

CREATE TABLE IF NOT EXISTS hits (        -- sayt tashriflari (mehmonlar): kun × manba
    day INTEGER NOT NULL,
    src TEXT    NOT NULL,
    n   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, src)
);

CREATE TABLE IF NOT EXISTS site_visits ( -- sayt tashriflari (Telegram foydalanuvchilari): kuniga bir marta
    day     INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    src     TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (day, user_id)
);
CREATE INDEX IF NOT EXISTS idx_site_visits_day ON site_visits(day);

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

CREATE TABLE IF NOT EXISTS admin_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       INTEGER NOT NULL,
    admin_id INTEGER NOT NULL,
    action   TEXT    NOT NULL,
    detail   TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_admin_log_ts ON admin_log(ts);

CREATE TABLE IF NOT EXISTS trash (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    deleted_at INTEGER NOT NULL,
    deleted_by INTEGER NOT NULL,
    code       INTEGER NOT NULL DEFAULT 0,
    title      TEXT    NOT NULL DEFAULT '',
    movie      TEXT    NOT NULL,
    parts      TEXT    NOT NULL DEFAULT '[]',
    shorts     TEXT    NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS announces (
    movie_id   INTEGER NOT NULL,
    chat_id    TEXT    NOT NULL,
    message_id INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_announces_movie ON announces(movie_id);

CREATE TABLE IF NOT EXISTS broadcasts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  INTEGER NOT NULL,
    finished_at INTEGER NOT NULL DEFAULT 0,
    admin_id    INTEGER NOT NULL,
    admin_chat  INTEGER NOT NULL DEFAULT 0,
    mode        TEXT    NOT NULL,
    audience    TEXT    NOT NULL,
    src_chat    INTEGER NOT NULL,
    src_msg     INTEGER NOT NULL,
    buttons     TEXT    NOT NULL DEFAULT '[]',
    total       INTEGER NOT NULL DEFAULT 0,
    done        INTEGER NOT NULL DEFAULT 0,
    ok          INTEGER NOT NULL DEFAULT 0,
    blocked     INTEGER NOT NULL DEFAULT 0,
    failed      INTEGER NOT NULL DEFAULT 0,
    last_uid    INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS follows (
    user_id INTEGER NOT NULL,
    topic   TEXT    NOT NULL,
    at      INTEGER NOT NULL,
    PRIMARY KEY (user_id, topic)
);
CREATE INDEX IF NOT EXISTS idx_follows_topic ON follows(topic);

CREATE TABLE IF NOT EXISTS comments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id   INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    parent_id  INTEGER NOT NULL DEFAULT 0,
    body       TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'ok',
    likes      INTEGER NOT NULL DEFAULT 0,
    reports    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_comments_movie ON comments(movie_id, parent_id, status, id);
CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id, created_at);
CREATE TABLE IF NOT EXISTS comment_likes (
    comment_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    PRIMARY KEY (comment_id, user_id)
);
CREATE TABLE IF NOT EXISTS comment_reports (
    comment_id INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    PRIMARY KEY (comment_id, user_id)
);

CREATE TABLE IF NOT EXISTS web_accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT    NOT NULL,
    subject    TEXT    NOT NULL,
    email      TEXT    NOT NULL DEFAULT '',
    name       TEXT    NOT NULL DEFAULT '',
    photo      TEXT    NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL,
    UNIQUE (provider, subject)
);
CREATE TABLE IF NOT EXISTS web_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    last_seen  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_web_sessions_user ON web_sessions(user_id);
CREATE TABLE IF NOT EXISTS login_tokens (
    token      TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    user_id    INTEGER NOT NULL DEFAULT 0,
    name       TEXT    NOT NULL DEFAULT '',
    status     TEXT    NOT NULL DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT    NOT NULL,
    user_id    INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    status     TEXT    NOT NULL DEFAULT 'open',
    handled_by INTEGER NOT NULL DEFAULT 0,
    handled_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ticket_msgs (
    ticket_id  INTEGER NOT NULL,
    admin_id   INTEGER NOT NULL,
    message_id INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticket_msgs ON ticket_msgs(ticket_id);
"""

CATEGORIES = ("movie", "serial", "cartoon", "music")

_CATALOG_ROW = """
SELECT m.id, m.code, m.title, m.description, m.is_premium, m.views, m.created_at, m.category, m.poster_id,
       m.genres, m.year, m.year_end, m.country, m.lang, m.quality, m.duration, m.age, m.imdb, m.group_link, m.watch_url,
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
        if "year_end" not in cols:  # 📅 serial yillar oralig'i (2012–2015): year — boshlanishi, year_end — tugashi
            self.conn.execute("ALTER TABLE movies ADD COLUMN year_end INTEGER NOT NULL DEFAULT 0")
        if "watch_url" not in cols:  # 🌐 kino joylangan boshqa saytning linki (ixtiyoriy) — saytda «Saytda ko'rish» tugmasi
            self.conn.execute("ALTER TABLE movies ADD COLUMN watch_url TEXT NOT NULL DEFAULT ''")
        if "group_link" not in cols:  # 📺 serialning qolgan qismlari joylangan guruh havolasi
            self.conn.execute("ALTER TABLE movies ADD COLUMN group_link TEXT NOT NULL DEFAULT ''")
        if "quality" not in cols:
            self.conn.execute("ALTER TABLE movies ADD COLUMN quality TEXT NOT NULL DEFAULT ''")  # 🎞 «,720,1080,»
        if "duration" not in cols:   # ⏱ davomiyligi (soniya), 🔞 yosh cheklovi, ⭐ IMDb reyting
            self.conn.execute("ALTER TABLE movies ADD COLUMN duration INTEGER NOT NULL DEFAULT 0")
            self.conn.execute("ALTER TABLE movies ADD COLUMN age INTEGER NOT NULL DEFAULT 0")
            self.conn.execute("ALTER TABLE movies ADD COLUMN imdb TEXT NOT NULL DEFAULT ''")
        pcols = {r[1] for r in self.conn.execute("PRAGMA table_info(parts)").fetchall()}
        if "duration" not in pcols:
            self.conn.execute("ALTER TABLE parts ADD COLUMN duration INTEGER NOT NULL DEFAULT 0")
        ucols = {r[1] for r in self.conn.execute("PRAGMA table_info(users)").fetchall()}
        if "src" not in ucols:  # 📈 foydalanuvchi qayerdan kelgani (tahlil uchun)
            self.conn.execute("ALTER TABLE users ADD COLUMN src TEXT NOT NULL DEFAULT ''")
        if "ref_by" not in ucols:  # 🤝 kim taklif qilgan (referal)
            self.conn.execute("ALTER TABLE users ADD COLUMN ref_by INTEGER NOT NULL DEFAULT 0")
        if "contact_banned" not in ucols:  # 🚫 admin murojaat/so'rov yuborishini cheklagan
            self.conn.execute("ALTER TABLE users ADD COLUMN contact_banned INTEGER NOT NULL DEFAULT 0")
        if "tour_done" not in ucols:  # 🧭 tanishtiruv ko'rsatilganmi
            self.conn.execute("ALTER TABLE users ADD COLUMN tour_done INTEGER NOT NULL DEFAULT 0")
        if "lang" not in ucols:  # 🌐 bot tili: '' (o'zbek) | ru | en
            self.conn.execute("ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT ''")
        if "trial_used" not in ucols:  # 🎁 bepul Premium sinov muddati berilganmi (bir marta)
            self.conn.execute("ALTER TABLE users ADD COLUMN trial_used INTEGER NOT NULL DEFAULT 0")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_ref ON users(ref_by)")
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

    def upsert_user(self, user: dict, src: str = "") -> bool:
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
                "INSERT INTO users(user_id, first_name, username, joined_at, last_active, src) VALUES (?,?,?,?,?,?)",
                (uid, user.get("first_name"), user.get("username"), t, t, src))
            return True

    def hit(self, src: str) -> None:
        self.x("INSERT INTO hits(day, src, n) VALUES (?,?,1) ON CONFLICT(day, src) DO UPDATE SET n=n+1",
               ((now() + 18000) // 86400, src))

    def site_visit(self, uid: int, src: str) -> None:
        self.x("INSERT OR IGNORE INTO site_visits(day, user_id, src) VALUES (?,?,?)", ((now() + 18000) // 86400, uid, src))

    def set_referrer(self, uid: int, ref: int) -> bool:
        """Yangi foydalanuvchini taklif qilgan odamga bog'laydi (faqat bir marta, o'zini emas). Muvaffaqiyatli bo'lsa True."""
        if uid == ref:
            return False
        with self.tx() as c:
            if not c.execute("SELECT 1 FROM users WHERE user_id=?", (ref,)).fetchone():
                return False
            return c.execute("UPDATE users SET ref_by=? WHERE user_id=? AND ref_by=0", (ref, uid)).rowcount > 0

    # ───────── 🎟 promokodlar ─────────

    PROMO_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # chalkash oson harflarsiz (0/O, 1/I)

    def create_promos(self, days: int, count: int, admin_id: int) -> List[str]:
        import secrets
        out: List[str] = []
        with self.tx() as c:
            while len(out) < count:
                code = "MM-" + "".join(secrets.choice(self.PROMO_ALPHABET) for _ in range(6))
                if c.execute("SELECT 1 FROM promos WHERE code=?", (code,)).fetchone():
                    continue
                c.execute("INSERT INTO promos(code, days, created_by, created_at) VALUES (?,?,?,?)",
                          (code, days, admin_id, now()))
                out.append(code)
        return out

    def redeem_promo(self, code: str, uid: int) -> int:
        """Promokodni ishlatadi. Muvaffaqiyatli bo'lsa kunlar sonini, aks holda 0 qaytaradi (yo'q yoki ishlatilgan)."""
        code = (code or "").strip().upper().replace(" ", "")
        with self.tx() as c:
            row = c.execute("SELECT days FROM promos WHERE code=? AND used_by=0", (code,)).fetchone()
            if not row:
                return 0
            c.execute("UPDATE promos SET used_by=?, used_at=? WHERE code=? AND used_by=0", (uid, now(), code))
            return row["days"]

    def promo_stats(self) -> Dict[int, Dict[str, int]]:
        out: Dict[int, Dict[str, int]] = {}
        for r in self.q("SELECT days, SUM(used_by=0) AS free, SUM(used_by<>0) AS used FROM promos GROUP BY days"):
            out[r["days"]] = {"free": r["free"] or 0, "used": r["used"] or 0}
        return out

    def free_promos(self, days: int, limit: int = 30) -> List[sqlite3.Row]:
        return self.q("SELECT code FROM promos WHERE used_by=0 AND days=? ORDER BY created_at DESC LIMIT ?",
                      (days, limit))

    def user_stats(self, uid: int, since: int) -> dict:
        """«Sizning yilingiz»: shu yilda ko'rilgan kinolar, sevimli janrlar, soat, yoqtirganlari, izohlari, taklif qilgan do'stlari."""
        rows = self.q("SELECT m.genres, m.duration FROM history h JOIN movies m ON m.id=h.movie_id"
                      " WHERE h.user_id=? AND h.at>=?", (uid, since))
        freq: Dict[str, int] = {}
        secs = 0
        for r in rows:
            secs += r["duration"] or 0
            for g in genres.parse(r["genres"]):
                freq[g] = freq.get(g, 0) + 1
        top = [k for k, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:3]]
        return {"watched": len(rows), "hours": round(secs / 3600, 1), "genres": top,
                "likes": self.val("SELECT COUNT(*) FROM ratings WHERE user_id=? AND value=1", (uid,)),
                "comments": self.val("SELECT COUNT(*) FROM comments WHERE user_id=? AND status='ok'", (uid,)),
                "referrals": self.referral_count(uid)}

    def top_referrers(self, since: int, until: int, limit: int = 10) -> List[sqlite3.Row]:
        """Oylik musobaqa: [since, until) oralig'ida eng ko'p do'st taklif qilganlar (bir xil sonda — avval boshlaganlar)."""
        return self.q("SELECT r.ref_by AS uid, COUNT(*) AS n, MIN(r.joined_at) AS first_at, u.first_name, u.username FROM users r"
                      " JOIN users u ON u.user_id = r.ref_by WHERE r.ref_by>0 AND r.joined_at>=? AND r.joined_at<?"
                      " GROUP BY r.ref_by ORDER BY n DESC, first_at ASC LIMIT ?", (since, until, limit))

    def referral_count_between(self, uid: int, since: int, until: int) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE ref_by=? AND joined_at>=? AND joined_at<?", (uid, since, until))

    def referral_count(self, uid: int) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE ref_by=?", (uid,))

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

    def joined_per_day(self, days: int) -> List[tuple]:
        """Oxirgi `days` kun uchun [(kun_boshi_ts, yangi_foydalanuvchilar)] — Toshkent vaqti bilan, bo'sh kunlar 0."""
        from .utils import day_start
        today = day_start()
        start = today - (days - 1) * 86400
        counts = {r[0]: r[1] for r in self.q(
            "SELECT (joined_at + 18000) / 86400 AS d, COUNT(*) FROM users WHERE joined_at>=? GROUP BY d", (start,))}
        return [(start + i * 86400, counts.get((start + i * 86400 + 18000) // 86400, 0)) for i in range(days)]

    def count_active_since(self, ts: int) -> int:
        return self.val("SELECT COUNT(*) FROM users WHERE last_active>=?", (ts,))

    def count_audience(self, audience: str = "all") -> int:
        t = now()
        if audience == "premium":
            return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0 AND premium_until>?", (t,))
        if audience == "free":
            return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0 AND premium_until<=?", (t,))
        if audience == "active":
            return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0 AND last_active>=?", (t - 30 * 86400,))
        return self.val("SELECT COUNT(*) FROM users WHERE is_blocked=0")

    def user_ids(self, audience: str = "all") -> List[int]:
        t = now()
        if audience == "premium":
            rows = self.q("SELECT user_id FROM users WHERE is_blocked=0 AND premium_until>? ORDER BY user_id", (t,))
        elif audience == "free":
            rows = self.q("SELECT user_id FROM users WHERE is_blocked=0 AND premium_until<=? ORDER BY user_id", (t,))
        elif audience == "active":
            rows = self.q("SELECT user_id FROM users WHERE is_blocked=0 AND last_active>=? ORDER BY user_id",
                          (t - 30 * 86400,))
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

    def take_tour(self, uid: int) -> bool:
        """Tanishtiruv hali ko'rsatilmagan bo'lsa belgilaydi va True qaytaradi (bir marta)."""
        return self.x("UPDATE users SET tour_done=1 WHERE user_id=? AND tour_done=0", (uid,)).rowcount > 0

    def get_lang(self, uid: int) -> str:
        return self.val("SELECT lang FROM users WHERE user_id=?", (uid,)) or ""

    def set_lang(self, uid: int, lang: str) -> None:
        self.x("UPDATE users SET lang=? WHERE user_id=?", (lang if lang in ("ru", "en") else "", uid))

    def take_trial(self, uid: int, since: int) -> bool:
        """Yangi foydalanuvchiga sinov muddati berilmagan bo'lsa belgilaydi (True). `since` — funksiya yoqilgan vaqt: undan oldin
        qo'shilgan eski foydalanuvchilarga berilmaydi. Premium'i bor yoki oldin olgan odamga ham berilmaydi."""
        t = now()
        with self.tx() as c:
            row = c.execute("SELECT joined_at, trial_used, premium_until FROM users WHERE user_id=?", (uid,)).fetchone()
            if not row or row["trial_used"] or row["joined_at"] < since or row["premium_until"] > t:
                return False
            c.execute("UPDATE users SET trial_used=1 WHERE user_id=?", (uid,))
            return True

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
                  group_link: str = "", watch_url: str = "", year_end: int = 0) -> int:
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
                " added_by, created_at, category, desc_html, genres, year, country, lang, quality, group_link, watch_url, year_end)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (code, title, description or "", poster_id, 1 if is_premium else 0, normalize(title),
                 normalize(description or ""), added_by, t, category, desc_html or "",
                 genres.dump(genre_keys), year or 0, country or "", lang or "", quality or "", group_link or "", watch_url or "", year_end or 0))
            movie_id = cur.lastrowid
            dur = duration_of(file_id)
            c.execute("INSERT INTO parts(movie_id, part_no, file_id, file_type, created_at, duration) VALUES (?,?,?,?,?,?)",
                      (movie_id, 1, file_id, file_type, t, dur))
            if dur and category != "music":
                c.execute("UPDATE movies SET duration=? WHERE id=?", (dur, movie_id))
        if category != "music" and any(k in genres.AUTO_COLLECTIONS for k in genre_keys or []):
            self.sync_genre_collections(movie_id)
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
        if "genres" in fields:
            self.sync_genre_collections(movie_id)

    def delete_movie(self, movie_id: int) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM ratings WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM collection_items WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM history WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM shorts WHERE movie_id=?", (movie_id,))
            c.execute("DELETE FROM parts WHERE movie_id=?", (movie_id,))
            self._drop_comments(c, movie_id)
            c.execute("DELETE FROM movies WHERE id=?", (movie_id,))

    def add_part(self, movie_id: int, file_id: str, file_type: str) -> int:
        with self.tx() as c:
            no = (c.execute("SELECT MAX(part_no) FROM parts WHERE movie_id=?", (movie_id,)).fetchone()[0] or 0) + 1
            c.execute("INSERT INTO parts(movie_id, part_no, file_id, file_type, created_at, duration) VALUES (?,?,?,?,?,?)",
                      (movie_id, no, file_id, file_type, now(), duration_of(file_id)))
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
            c.execute("INSERT INTO view_days(movie_id, day, n) VALUES (?,?,1)"
                      " ON CONFLICT(movie_id, day) DO UPDATE SET n=n+1", (movie_id, (now() + 18000) // 86400))

    def prune_views(self, keep_days: int = 60) -> None:
        self.x("DELETE FROM view_days WHERE day < ?", ((now() + 18000) // 86400 - keep_days,))

    def weekly_top(self, limit: int = 10, days: int = 7) -> List[sqlite3.Row]:
        """🔥 Haftaning TOP'i: avval shu haftada eng ko'p ko'rilganlar; yetmasa — oxirgi oyda qo'shilgan mashhurlari,
        keyin umumiy TOP bilan to'ldiriladi (qator hech qachon bo'sh qolmasin; ma'lumot to'plangach o'zi haqiqiy bo'ladi)."""
        t = now()
        since = (t + 18000) // 86400 - (days - 1)
        ids = [r[0] for r in self.q(
            "SELECT v.movie_id FROM view_days v JOIN movies m ON m.id = v.movie_id"
            " WHERE v.day >= ? AND m.category<>'music' GROUP BY v.movie_id ORDER BY SUM(v.n) DESC, v.movie_id DESC LIMIT ?",
            (since, limit))]
        for where, params in (("created_at >= ?", (t - 30 * 86400,)), ("1=1", ())):
            if len(ids) >= limit:
                break
            skip = ",".join("?" * len(ids)) or "-1"
            more = self.q(f"SELECT id FROM movies WHERE category<>'music' AND {where} AND id NOT IN ({skip})"
                          " ORDER BY views DESC, id DESC LIMIT ?", (*params, *ids, limit - len(ids)))
            ids += [r[0] for r in more]
        return self.catalog_rows(ids)

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

    def user_requested(self, uid: int, norm: str) -> bool:
        return bool(self.val("SELECT COUNT(*) FROM requests WHERE user_id=? AND norm=? AND done_at=0", (uid, norm[:300])))

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
            where.append("(m.year=? OR (m.year_end>0 AND ? BETWEEN m.year AND m.year_end))")
            params.extend([year, year])
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
        if sort == "rating":
            sql = (_CATALOG_ROW + f" WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?")
            return self.q(sql, params + [limit, offset])
        # avval faqat id larni tanlaymiz (tez), keyin faqat shu sahifadagilar uchun og'ir ustunlarni hisoblaymiz
        sql = (_CATALOG_ROW + f" WHERE m.id IN (SELECT m.id FROM movies m WHERE {' AND '.join(where)}"
               f" ORDER BY {order} LIMIT ? OFFSET ?) ORDER BY {order}")
        return self.q(sql, params + [limit, offset])

    def catalog_rows(self, ids: List[int]) -> List[sqlite3.Row]:
        if not ids:
            return []
        rows = self.q(_CATALOG_ROW + f" WHERE m.id IN ({','.join('?' * len(ids))})", ids)
        by_id = {r["id"]: r for r in rows}
        return [by_id[i] for i in ids if i in by_id]

    def _cached(self, key, fn, ttl: float = 30.0):
        cache = self.__dict__.setdefault("_memo", {})
        hit = cache.get(key)
        now = time.time()
        if hit and now - hit[0] < ttl:
            return hit[1]
        val = fn()
        cache[key] = (now, val)
        return val

    def genre_counts(self, category: str) -> Dict[str, int]:
        return self._cached(("g", category), lambda: self._genre_counts(category))

    def facets(self, category: str) -> Dict[str, Dict]:
        return self._cached(("f", category), lambda: self._facets(category))

    def _genre_counts(self, category: str) -> Dict[str, int]:
        """Har bir janrda nechta kino bor (faqat bo'sh bo'lmaganlari)."""
        out: Dict[str, int] = {}
        where, params = (("category<>'music'", ()) if category == "video" else ("category=?", (category,)))
        for r in self.q(f"SELECT genres FROM movies WHERE {where} AND genres<>''", params):
            for k in genres.parse(r[0]):
                out[k] = out.get(k, 0) + 1
        return {k: out[k] for k in genres.GENRES if k in out}

    def _facets(self, category: str) -> Dict[str, Dict]:
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

    def sync_genre_collections(self, movie_id: int) -> None:
        """Marvel/DC janri belgilangan kino «Marvel to'plami» / «DC kolleksiyasi»ga o'zi qo'shiladi (janr olinsa — chiqariladi)."""
        m = self.get_movie(movie_id)
        if not m:
            return
        have = set(genres.parse(m["genres"]))
        for key, title in genres.AUTO_COLLECTIONS.items():
            row = self.q1("SELECT id FROM collections WHERE title=?", (title,))
            if key in have:
                cid = row["id"] if row else self.add_collection(title)
                self.add_to_collection(cid, movie_id)
            elif row:
                self.remove_from_collection(row["id"], movie_id)

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

    # ───────── 🧾 admin harakatlari jurnali ─────────

    def log_action(self, admin_id: int, action: str, detail: str = "") -> None:
        self.x("INSERT INTO admin_log(ts, admin_id, action, detail) VALUES (?,?,?,?)",
               (now(), admin_id, action[:40], detail[:300]))

    def recent_actions(self, limit: int = 30) -> List[sqlite3.Row]:
        return self.q("SELECT l.*, u.first_name FROM admin_log l LEFT JOIN users u ON u.user_id=l.admin_id"
                      " ORDER BY l.id DESC LIMIT ?", (limit,))

    def prune_admin_log(self, before: int) -> None:
        self.x("DELETE FROM admin_log WHERE ts<?", (before,))

    # ───────── 🗑 chiqindi qutisi (o'chirilgan kinolar 30 kun saqlanadi) ─────────

    def trash_movie(self, movie_id: int, admin_id: int) -> Optional[int]:
        """Kinoni (qismlari va shorts bilan) chiqindi qutisiga ko'chirib, bazadan o'chiradi. Quti yozuvi ID sini qaytaradi."""
        import json
        with self.tx() as c:
            m = c.execute("SELECT * FROM movies WHERE id=?", (movie_id,)).fetchone()
            if not m:
                return None
            parts = [dict(r) for r in c.execute("SELECT * FROM parts WHERE movie_id=? ORDER BY part_no", (movie_id,))]
            shorts = [dict(r) for r in c.execute("SELECT * FROM shorts WHERE movie_id=?", (movie_id,))]
            tid = c.execute("INSERT INTO trash(deleted_at, deleted_by, code, title, movie, parts, shorts) VALUES (?,?,?,?,?,?,?)",
                            (now(), admin_id, m["code"], m["title"], json.dumps(dict(m), ensure_ascii=False),
                             json.dumps(parts, ensure_ascii=False), json.dumps(shorts, ensure_ascii=False))).lastrowid
            for tbl in ("ratings", "collection_items", "history", "shorts", "parts"):
                c.execute(f"DELETE FROM {tbl} WHERE movie_id=?", (movie_id,))
            self._drop_comments(c, movie_id)
            c.execute("DELETE FROM movies WHERE id=?", (movie_id,))
            return tid

    def list_trash(self, limit: int = 15) -> List[sqlite3.Row]:
        return self.q("SELECT id, deleted_at, deleted_by, code, title FROM trash ORDER BY id DESC LIMIT ?", (limit,))

    def get_trash(self, tid: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM trash WHERE id=?", (tid,))

    def restore_trash(self, tid: int) -> Optional[int]:
        """Qutidagi kinoni qaytaradi. Kodi band bo'lsa — keyingi bo'sh kod beriladi. Kino ID sini qaytaradi."""
        import json
        with self.tx() as c:
            row = c.execute("SELECT * FROM trash WHERE id=?", (tid,)).fetchone()
            if not row:
                return None
            m = json.loads(row["movie"])
            if m["code"] > 0 and c.execute("SELECT 1 FROM movies WHERE code=?", (m["code"],)).fetchone():
                m["code"] = (c.execute("SELECT MAX(code) FROM movies WHERE code>0").fetchone()[0] or 0) + 1
            if c.execute("SELECT 1 FROM movies WHERE id=?", (m["id"],)).fetchone():
                m.pop("id")
            cols = list(m.keys())
            c.execute(f"INSERT INTO movies({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", [m[k] for k in cols])
            mid = m.get("id") or c.execute("SELECT last_insert_rowid()").fetchone()[0]
            for tbl, items in (("parts", json.loads(row["parts"])), ("shorts", json.loads(row["shorts"]))):
                for it in items:
                    it["movie_id"] = mid
                    it.pop("id", None)
                    k = list(it.keys())
                    c.execute(f"INSERT INTO {tbl}({','.join(k)}) VALUES ({','.join('?' * len(k))})", [it[x] for x in k])
            c.execute("DELETE FROM trash WHERE id=?", (tid,))
            return mid

    def prune_trash(self, before: int) -> None:
        self.x("DELETE FROM trash WHERE deleted_at<?", (before,))

    # ───────── 📢 kanalga e'lon qilinganlar ─────────

    def add_announce(self, movie_id: int, chat_id, message_id: int) -> None:
        self.x("INSERT INTO announces(movie_id, chat_id, message_id, created_at) VALUES (?,?,?,?)",
               (movie_id, str(chat_id), message_id, now()))

    def get_announces(self, movie_id: int) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM announces WHERE movie_id=? ORDER BY created_at DESC", (movie_id,))

    def drop_announces(self, movie_id: int) -> None:
        self.x("DELETE FROM announces WHERE movie_id=?", (movie_id,))

    # ───────── 🎞 qismlar: tartib va nom ─────────

    def move_part(self, part_id: int, up: bool) -> bool:
        with self.tx() as c:
            p = c.execute("SELECT movie_id, part_no FROM parts WHERE id=?", (part_id,)).fetchone()
            if not p:
                return False
            other = c.execute("SELECT id, part_no FROM parts WHERE movie_id=? AND part_no=?",
                              (p["movie_id"], p["part_no"] + (-1 if up else 1))).fetchone()
            if not other:
                return False
            c.execute("UPDATE parts SET part_no=-1 WHERE id=?", (part_id,))
            c.execute("UPDATE parts SET part_no=? WHERE id=?", (p["part_no"], other["id"]))
            c.execute("UPDATE parts SET part_no=? WHERE id=?", (other["part_no"], part_id))
            return True

    def set_part_title(self, part_id: int, title: str) -> None:
        self.x("UPDATE parts SET title=? WHERE id=?", (title[:100], part_id))

    def code_taken(self, code: int, except_id: int = 0) -> bool:
        return self.q1("SELECT 1 FROM movies WHERE code=? AND id<>?", (code, except_id)) is not None

    # ───────── ✉️ xabar yuborish tarixi (to'xtab qolsa — davom ettiriladi) ─────────

    def create_broadcast(self, admin_id: int, admin_chat: int, mode: str, audience: str, src_chat: int, src_msg: int,
                         buttons) -> int:
        import json
        return self.x("INSERT INTO broadcasts(created_at, admin_id, admin_chat, mode, audience, src_chat, src_msg, buttons)"
                      " VALUES (?,?,?,?,?,?,?,?)",
                      (now(), admin_id, admin_chat, mode, audience, src_chat, src_msg,
                       json.dumps(buttons, ensure_ascii=False))).lastrowid

    def update_broadcast(self, bid: int, **f) -> None:
        if f:
            self.x(f"UPDATE broadcasts SET {', '.join(k + '=?' for k in f)} WHERE id=?", [*f.values(), bid])

    def get_broadcast(self, bid: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM broadcasts WHERE id=?", (bid,))

    def interrupted_broadcast(self) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM broadcasts WHERE status='running' ORDER BY id DESC LIMIT 1")

    def recent_broadcasts(self, limit: int = 10) -> List[sqlite3.Row]:
        return self.q("SELECT * FROM broadcasts ORDER BY id DESC LIMIT ?", (limit,))

    def user_ids_after(self, audience: str, last_uid: int) -> List[int]:
        return [u for u in self.user_ids(audience) if u > last_uid]

    # ───────── 📥 so'rovlar va murojaatlar ───────

    def top_requests(self, limit: int = 15, since: int = 0) -> List[sqlite3.Row]:
        return self.q("SELECT norm, MIN(query) AS query, COUNT(DISTINCT user_id) AS n, MAX(created_at) AS last"
                      " FROM requests WHERE done_at=0 AND created_at>=? GROUP BY norm"
                      " ORDER BY n DESC, last DESC LIMIT ?", (since, limit))

    def dismiss_request_norm(self, norm: str) -> int:
        return self.x("UPDATE requests SET done_at=?, movie_id=0 WHERE done_at=0 AND norm=?", (now(), norm)).rowcount

    def create_ticket(self, kind: str, user_id: int) -> int:
        return self.x("INSERT INTO tickets(kind, user_id, created_at) VALUES (?,?,?)", (kind, user_id, now())).lastrowid

    def add_ticket_msg(self, ticket_id: int, admin_id: int, message_id: int) -> None:
        self.x("INSERT INTO ticket_msgs(ticket_id, admin_id, message_id) VALUES (?,?,?)", (ticket_id, admin_id, message_id))

    def ticket_msgs(self, ticket_id: int) -> List[sqlite3.Row]:
        return self.q("SELECT admin_id, message_id FROM ticket_msgs WHERE ticket_id=?", (ticket_id,))

    def get_ticket(self, ticket_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM tickets WHERE id=?", (ticket_id,))

    def close_ticket(self, ticket_id: int, admin_id: int) -> bool:
        return self.x("UPDATE tickets SET status='done', handled_by=?, handled_at=? WHERE id=? AND status='open'",
                      (admin_id, now(), ticket_id)).rowcount > 0

    def open_tickets(self) -> int:
        return self.val("SELECT COUNT(*) FROM tickets WHERE status='open' AND created_at>=?", (now() - 14 * 86400,))

    def set_contact_banned(self, uid: int, banned: bool) -> None:
        self.x("UPDATE users SET contact_banned=? WHERE user_id=?", (1 if banned else 0, uid))

    def is_contact_banned(self, uid: int) -> bool:
        return bool(self.val("SELECT contact_banned FROM users WHERE user_id=?", (uid,)))

    def user_exists(self, uid: int) -> bool:
        return self.q1("SELECT 1 FROM users WHERE user_id=?", (uid,)) is not None

    def revenue_since(self, since: int) -> Dict[str, int]:
        """So'nggi davr tushumi: so'm (karta + Click/Payme) va Stars."""
        rows = self.q("SELECT method, COALESCE(SUM(amount),0) AS s FROM payments WHERE status='approved' AND created_at>=?"
                      " AND amount>0 GROUP BY method", (since,))
        return {r["method"]: r["s"] for r in rows}

    # ───────── 💬 izohlar ─────────

    @staticmethod
    def _drop_comments(c, movie_id: int) -> None:
        ids = "SELECT id FROM comments WHERE movie_id=?"
        c.execute(f"DELETE FROM comment_likes WHERE comment_id IN ({ids})", (movie_id,))
        c.execute(f"DELETE FROM comment_reports WHERE comment_id IN ({ids})", (movie_id,))
        c.execute("DELETE FROM comments WHERE movie_id=?", (movie_id,))

    def add_comment(self, movie_id: int, user_id: int, body: str, parent_id: int = 0) -> int:
        return self.x("INSERT INTO comments(movie_id, user_id, parent_id, body, created_at) VALUES (?,?,?,?,?)",
                      (movie_id, user_id, parent_id, body, now())).lastrowid

    def get_comment(self, cid: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM comments WHERE id=?", (cid,))

    _COMMENT_SQL = ("SELECT c.id, c.movie_id, c.user_id, c.parent_id, c.body, c.created_at, c.likes,"
                    " COALESCE(u.first_name, w.name) AS first_name, u.premium_until,"
                    " EXISTS(SELECT 1 FROM comment_likes l WHERE l.comment_id=c.id AND l.user_id=?) AS liked"
                    " FROM comments c LEFT JOIN users u ON u.user_id=c.user_id LEFT JOIN web_accounts w ON c.user_id = -w.id")

    def top_comments(self, movie_id: int, viewer: int, sort: str, limit: int, offset: int) -> List[sqlite3.Row]:
        order = "c.likes DESC, c.id DESC" if sort == "top" else "c.id DESC"
        return self.q(f"{self._COMMENT_SQL} WHERE c.movie_id=? AND c.parent_id=0 AND c.status='ok' ORDER BY {order} LIMIT ? OFFSET ?",
                      (viewer, movie_id, limit, offset))

    def comment_replies(self, parent_ids: List[int], viewer: int) -> List[sqlite3.Row]:
        if not parent_ids:
            return []
        ph = ",".join("?" * len(parent_ids))
        return self.q(f"{self._COMMENT_SQL} WHERE c.parent_id IN ({ph}) AND c.status='ok' ORDER BY c.id", (viewer, *parent_ids))

    def count_comments(self, movie_id: int, top_only: bool = False) -> int:
        return self.val("SELECT COUNT(*) FROM comments WHERE movie_id=? AND status='ok'" + (" AND parent_id=0" if top_only else ""),
                        (movie_id,))

    def user_comment_load(self, user_id: int) -> Dict[str, int]:
        """Spamdan himoya: oxirgi izoh vaqti va so'nggi soatdagi izohlar soni."""
        t = now()
        return {"last": self.val("SELECT MAX(created_at) FROM comments WHERE user_id=?", (user_id,)),
                "hour": self.val("SELECT COUNT(*) FROM comments WHERE user_id=? AND created_at>=?", (user_id, t - 3600))}

    def has_same_comment(self, user_id: int, movie_id: int, body: str) -> bool:
        return self.q1("SELECT 1 FROM comments WHERE user_id=? AND movie_id=? AND body=? AND created_at>=?",
                       (user_id, movie_id, body, now() - 86400)) is not None

    def toggle_comment_like(self, cid: int, uid: int) -> Optional[tuple]:
        with self.tx() as c:
            if not c.execute("SELECT 1 FROM comments WHERE id=?", (cid,)).fetchone():
                return None
            if c.execute("SELECT 1 FROM comment_likes WHERE comment_id=? AND user_id=?", (cid, uid)).fetchone():
                c.execute("DELETE FROM comment_likes WHERE comment_id=? AND user_id=?", (cid, uid))
                liked = False
            else:
                c.execute("INSERT INTO comment_likes(comment_id, user_id) VALUES (?,?)", (cid, uid))
                liked = True
            n = c.execute("SELECT COUNT(*) FROM comment_likes WHERE comment_id=?", (cid,)).fetchone()[0]
            c.execute("UPDATE comments SET likes=? WHERE id=?", (n, cid))
            return liked, n

    def report_comment(self, cid: int, uid: int, hide_at: int = 3) -> Optional[int]:
        """Shikoyat qo'shadi (bir kishidan bir marta). Hide_at ta shikoyatda izoh yashiriladi. Shikoyatlar sonini qaytaradi."""
        with self.tx() as c:
            if not c.execute("SELECT 1 FROM comments WHERE id=?", (cid,)).fetchone():
                return None
            c.execute("INSERT OR IGNORE INTO comment_reports(comment_id, user_id) VALUES (?,?)", (cid, uid))
            n = c.execute("SELECT COUNT(*) FROM comment_reports WHERE comment_id=?", (cid,)).fetchone()[0]
            c.execute("UPDATE comments SET reports=?, status=CASE WHEN ?>=? THEN 'hidden' ELSE status END WHERE id=?",
                      (n, n, hide_at, cid))
            return n

    def delete_comment(self, cid: int) -> int:
        """Izohni va uning javoblarini o'chiradi. O'chirilganlar sonini qaytaradi."""
        with self.tx() as c:
            ids = [r[0] for r in c.execute("SELECT id FROM comments WHERE id=? OR parent_id=?", (cid, cid))]
            for tbl in ("comment_likes", "comment_reports"):
                c.execute(f"DELETE FROM {tbl} WHERE comment_id IN ({','.join('?' * len(ids))})", ids) if ids else None
            if ids:
                c.execute(f"DELETE FROM comments WHERE id IN ({','.join('?' * len(ids))})", ids)
            return len(ids)

    def restore_comment(self, cid: int) -> None:
        self.x("UPDATE comments SET status='ok' WHERE id=?", (cid,))

    def recent_comments(self, limit: int = 10, status: str = "ok") -> List[sqlite3.Row]:
        return self.q("SELECT c.id, c.movie_id, c.user_id, c.body, c.created_at, c.status, c.reports, u.first_name, m.title"
                      " FROM comments c LEFT JOIN users u ON u.user_id=c.user_id LEFT JOIN movies m ON m.id=c.movie_id"
                      " WHERE c.status=? ORDER BY c.id DESC LIMIT ?", (status, limit))

    # ───────── 🔐 saytga kirish (Telegram bot orqali / Google) ─────────

    def create_login_token(self) -> str:
        import secrets
        tok = secrets.token_urlsafe(18)
        self.x("DELETE FROM login_tokens WHERE created_at<?", (now() - 1800,))
        self.x("INSERT INTO login_tokens(token, created_at) VALUES (?,?)", (tok, now()))
        return tok

    def get_login_token(self, tok: str, max_age: int = 600) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM login_tokens WHERE token=? AND created_at>=?", (tok, now() - max_age))

    def bind_login_token(self, tok: str, user_id: int, name: str) -> bool:
        return self.x("UPDATE login_tokens SET user_id=?, name=?, status='done' WHERE token=? AND status='pending' AND created_at>=?",
                      (user_id, name[:60], tok, now() - 600)).rowcount > 0

    def drop_login_token(self, tok: str) -> None:
        self.x("DELETE FROM login_tokens WHERE token=?", (tok,))

    def create_session(self, user_id: int) -> str:
        import hashlib
        import secrets
        tok = secrets.token_urlsafe(32)
        t = now()
        self.x("INSERT INTO web_sessions(token_hash, user_id, created_at, last_seen) VALUES (?,?,?,?)",
               (hashlib.sha256(tok.encode()).hexdigest(), user_id, t, t))
        self.x("DELETE FROM web_sessions WHERE last_seen<?", (t - 90 * 86400,))
        return tok

    def session_user(self, tok: str) -> Optional[int]:
        import hashlib
        if not tok or len(tok) > 100:
            return None
        h = hashlib.sha256(tok.encode()).hexdigest()
        row = self.q1("SELECT user_id, last_seen FROM web_sessions WHERE token_hash=?", (h,))
        if not row or now() - row["last_seen"] > 90 * 86400:
            return None
        if now() - row["last_seen"] > 3600:
            self.x("UPDATE web_sessions SET last_seen=? WHERE token_hash=?", (now(), h))
        return row["user_id"]

    def delete_session(self, tok: str) -> None:
        import hashlib
        self.x("DELETE FROM web_sessions WHERE token_hash=?", (hashlib.sha256(tok.encode()).hexdigest(),))

    def upsert_web_account(self, provider: str, subject: str, email: str, name: str, photo: str) -> int:
        """Google (va boshqa) akkaunt uchun ichki manfiy ID qaytaradi (Telegram ID lari musbat — aralashmaydi)."""
        with self.tx() as c:
            row = c.execute("SELECT id FROM web_accounts WHERE provider=? AND subject=?", (provider, subject)).fetchone()
            if row:
                c.execute("UPDATE web_accounts SET email=?, name=?, photo=? WHERE id=?", (email[:120], name[:60], photo[:300], row["id"]))
                return -row["id"]
            cur = c.execute("INSERT INTO web_accounts(provider, subject, email, name, photo, created_at) VALUES (?,?,?,?,?,?)",
                            (provider, subject, email[:120], name[:60], photo[:300], now()))
            return -cur.lastrowid

    def get_web_account(self, user_id: int) -> Optional[sqlite3.Row]:
        return self.q1("SELECT * FROM web_accounts WHERE id=?", (-user_id,)) if user_id < 0 else None

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

    # ───────── 🧩 yetishmayotgan ma'lumotlar (admin uchun) ─────────

    MISSING = {
        "poster": ("🖼 Posteri yo'q", "(m.poster_id IS NULL OR m.poster_id='')"),
        "genre": ("🎭 Janri yo'q", "m.genres=''"),
        "year": ("📅 Yili yo'q", "m.year=0"),
        "country": ("🌍 Davlati yo'q", "m.country=''"),
        "desc": ("📝 Tavsifi yo'q", "TRIM(m.description)=''"),
    }

    def missing_counts(self) -> Dict[str, int]:
        return {k: self.val(f"SELECT COUNT(*) FROM movies m WHERE m.category<>'music' AND {cond}")
                for k, (_, cond) in self.MISSING.items()}

    def missing_list(self, kind: str, limit: int = 8, offset: int = 0) -> List[sqlite3.Row]:
        cond = self.MISSING[kind][1]
        return self.q(f"SELECT m.id, m.code, m.title, m.category FROM movies m WHERE m.category<>'music' AND {cond}"
                      " ORDER BY m.views DESC, m.id DESC LIMIT ? OFFSET ?", (limit, offset))

    # ───────── 🔔 kuzatish: janrlar va haftalik tavsiya ─────────

    def follow_toggle(self, uid: int, topic: str) -> bool:
        """Obunani yoqadi/o'chiradi. Yoqilgan bo'lsa True."""
        if self.val("SELECT COUNT(*) FROM follows WHERE user_id=? AND topic=?", (uid, topic)):
            self.x("DELETE FROM follows WHERE user_id=? AND topic=?", (uid, topic))
            return False
        self.x("INSERT OR IGNORE INTO follows(user_id, topic, at) VALUES (?,?,?)", (uid, topic, now()))
        return True

    def user_follows(self, uid: int) -> set:
        return {r[0] for r in self.q("SELECT topic FROM follows WHERE user_id=?", (uid,))}

    def followers_of(self, topics) -> List[int]:
        """Shu janrlardan birortasini kuzatayotgan (bloklamagan) foydalanuvchilar."""
        topics = [t for t in topics if t]
        if not topics:
            return []
        marks = ",".join("?" * len(topics))
        return [r[0] for r in self.q(
            f"SELECT DISTINCT f.user_id FROM follows f JOIN users u ON u.user_id=f.user_id"
            f" WHERE u.is_blocked=0 AND f.topic IN ({marks}) ORDER BY f.user_id", topics)]

    def weekly_subscribers(self) -> List[int]:
        return [r[0] for r in self.q(
            "SELECT f.user_id FROM follows f JOIN users u ON u.user_id=f.user_id WHERE u.is_blocked=0 AND f.topic='weekly' ORDER BY f.user_id")]

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
