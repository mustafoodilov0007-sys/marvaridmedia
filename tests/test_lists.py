"""Foydalanuvchi ro'yxatlari, «Tomoshabinlar ham ko'rdi», soatlar statistikasi, izoh kartochkasi."""

import unittest

from tests.harness import WebServer, add_movie, cleanup, make_app


class Lists(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.db = self.app.db

    def tearDown(self):
        cleanup(self.app)

    def test_list_flow(self):
        a = add_movie(self.app, 1, "Birinchi")
        b = add_movie(self.app, 2, "Ikkinchi")
        web = WebServer(self.app)
        try:
            self.assertEqual(web.post("/api/list", {"act": "create", "title": "X"})[1].get("reason"), "auth")
            st, r = web.post("/api/list", {"act": "create", "title": "  Bolalar  uchun ", "movie": a}, uid=5)
            self.assertTrue(r["ok"])
            lid, tok = r["id"], r["token"]
            self.assertTrue(web.post("/api/list", {"act": "add", "id": lid, "movie": b}, uid=5)[1]["ok"])
            self.assertEqual(web.post("/api/list", {"act": "add", "id": lid, "movie": 9999}, uid=5)[1].get("reason"), "not_found")
            # boshqa foydalanuvchi o'zgartira olmaydi, lekin ko'ra oladi
            self.assertEqual(web.post("/api/list", {"act": "delete", "id": lid}, uid=6)[1].get("reason"), "forbidden")
            d = web.json(f"/api/list?t={tok}", uid=6)[1]
            self.assertEqual((d["title"], len(d["items"]), d["mine"]), ("Bolalar uchun", 2, False))
            self.assertTrue(web.json(f"/api/list?t={tok}", uid=5)[1]["mine"])
            mine = web.json(f"/api/lists?movie={a}", uid=5)[1]["lists"]
            self.assertEqual([(x["n"], x["has"]) for x in mine], [(2, True)])
            web.post("/api/list", {"act": "remove", "id": lid, "movie": a}, uid=5)
            self.assertEqual(len(web.json(f"/api/list?t={tok}", uid=6)[1]["items"]), 1)
            web.post("/api/list", {"act": "delete", "id": lid}, uid=5)
            self.assertEqual(web.json(f"/api/list?t={tok}", uid=6)[1].get("reason"), "not_found")
        finally:
            web.close()

    def test_limit(self):
        for i in range(self.db.MAX_LISTS):
            self.assertIsNotNone(self.db.create_user_list(5, f"L{i}"))
        self.assertIsNone(self.db.create_user_list(5, "ortiqcha"))

    def test_also_watched(self):
        a, b, c = (add_movie(self.app, i, f"K{i}") for i in (1, 2, 3))
        for uid in (10, 11, 12):
            self.db.touch_history(uid, a)
        for uid in (10, 11):
            self.db.touch_history(uid, b)
        self.db.touch_history(12, c)
        ids = [r["id"] for r in self.db.also_watched(a)]
        self.assertEqual(ids, [b])                 # b ni 2 kishi ko'rgan, c ni faqat 1 kishi — chiqmaydi

    def test_hours_recorded(self):
        a = add_movie(self.app, 1, "Kino")
        self.db.inc_views(a, 0)
        from app import analytics
        d = analytics.build(self.db)
        self.assertEqual(sum(x["n"] for x in d["hours"]), 1)
        self.assertEqual(len(d["hours"]), 24)

    def test_comment_card(self):
        import tempfile
        from pathlib import Path
        from app.webapp import comment_card_bytes
        a = add_movie(self.app, 1, "Kino", poster="")
        cid = self.db.add_comment(a, 5, "Juda zo'r film!")
        data = comment_card_bytes(self.app, cid, Path(tempfile.mkdtemp()))
        if data is not None:                       # Pillow yoki shrift bo'lmasa — None
            self.assertEqual(data[:2], b"\xff\xd8")
        self.assertIsNone(comment_card_bytes(self.app, 9999, Path(tempfile.mkdtemp())))


if __name__ == "__main__":
    unittest.main()
