"""Baza: eski bazani yangilash, haftalik TOP, bir vaqtda ko'p oqim."""

import sqlite3
import threading
import time
import unittest

from tests.harness import add_movie, cleanup, make_app


class Db(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def tearDown(self):
        cleanup(self.app)

    def test_weekly_top_never_empty_and_prefers_real_views(self):
        for i in range(1, 13):
            add_movie(self.app, i, f"Kino {i}")
        db = self.app.db
        self.assertEqual(len(db.weekly_top(10)), 10)                 # ko'rishlar yo'q — baribir to'ladi
        pid = db.get_parts(5)[0]["id"]
        for _ in range(4):
            db.inc_views(5, pid)
        self.assertEqual(db.weekly_top(10)[0]["title"], "Kino 5")    # haqiqiy ko'rishlar oldinda

    def test_old_database_is_migrated(self):
        from app.database import Database
        path = self.app.db.path
        self.app.db.conn.close()
        c = sqlite3.connect(str(path))
        for stmt in ("DROP INDEX IF EXISTS idx_users_ref", "ALTER TABLE users DROP COLUMN ref_by",
                     "ALTER TABLE movies DROP COLUMN duration", "ALTER TABLE movies DROP COLUMN age",
                     "ALTER TABLE movies DROP COLUMN imdb", "ALTER TABLE parts DROP COLUMN duration"):
            try:
                c.execute(stmt)
            except sqlite3.OperationalError:
                self.skipTest("SQLite DROP COLUMN qo'llanmaydi")
        c.commit()
        c.close()
        db = Database(path)
        cols = {r[1] for r in db.conn.execute("PRAGMA table_info(movies)")}
        self.assertTrue({"duration", "age", "imdb"} <= cols)
        self.assertIn("ref_by", {r[1] for r in db.conn.execute("PRAGMA table_info(users)")})

    def test_concurrent_writes_and_reads(self):
        for i in range(1, 11):
            add_movie(self.app, i, f"Kino {i}")
        db, errs = self.app.db, []

        def worker(k):
            try:
                for n in range(40):
                    m = (n + k) % 10 + 1
                    db.inc_views(m, db.get_parts(m)[0]["id"])
                    db.rate(1000 + k, m, 1 if n % 2 else -1)
                    db.weekly_top(10)
                    db.joined_per_day(14)
                    db.catalog("video", "new")
            except Exception as exc:  # noqa: BLE001
                errs.append(repr(exc))

        ts = [threading.Thread(target=worker, args=(k,)) for k in range(12)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(errs, [])
        self.assertEqual(db.val("SELECT SUM(views) FROM movies"), 12 * 40)
        self.assertEqual(db.val("SELECT SUM(n) FROM view_days"), 12 * 40)


if __name__ == "__main__":
    unittest.main()
