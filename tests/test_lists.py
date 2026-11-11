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


class ShareSetting(unittest.TestCase):
    def setUp(self):
        self.app = make_app()

    def tearDown(self):
        cleanup(self.app)

    def test_default_allows_sharing_and_admin_toggles(self):
        from app.core import process_update
        from tests.harness import message, press
        self.app.load_settings()                                              # ishga tushish
        process_update(self.app, message(1, "/start"))
        self.assertFalse(self.app.setting_bool("protect_content"))            # obunachilar ulasha oladi
        process_update(self.app, press(1, "st:tog:protect_content"))          # admin himoyani yoqadi
        self.assertTrue(self.app.setting_bool("protect_content"))
        self.app.load_settings()                                              # qayta yuklash (restart) tanlovni buzmaydi
        self.assertTrue(self.app.setting_bool("protect_content"))
        process_update(self.app, press(1, "st:tog:protect_content"))
        self.assertFalse(self.app.setting_bool("protect_content"))


class Growth(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.db = self.app.db

    def tearDown(self):
        cleanup(self.app)

    def test_popular_lists_only_public_and_big_enough(self):
        ids = [add_movie(self.app, i, f"K{i}") for i in range(1, 5)]
        pub = self.db.create_user_list(5, "Ommaviy")
        priv = self.db.create_user_list(5, "Yopiq")
        small = self.db.create_user_list(5, "Kichik")
        for m in ids[:3]:
            self.db.user_list_add(pub, m)
            self.db.user_list_add(priv, m)
        self.db.user_list_add(small, ids[0])
        for lid in (pub, priv, small):
            self.db.set_list_public(lid, True) if lid != priv else None
        self.assertEqual([r["title"] for r in self.db.popular_lists()], ["Ommaviy"])
        web = WebServer(self.app)
        try:
            tok = self.db.get_user_list(pub)["token"]
            web.json(f"/api/list?t={tok}", uid=6)                       # begona ko'rdi -> ko'rishlar +1
            web.json(f"/api/list?t={tok}", uid=5)                       # egasi — hisoblanmaydi
            self.assertEqual(self.db.get_user_list(pub)["views"], 1)
            home = web.json("/api/home", uid=6)[1]
            self.assertEqual([x["title"] for x in home["lists"]], ["Ommaviy"])
            self.assertTrue(web.post("/api/list", {"act": "public", "id": pub, "on": False}, uid=5)[1]["ok"])
            self.assertEqual(web.json("/api/home", uid=6)[1]["lists"], [])
            self.assertEqual(web.post("/api/list", {"act": "public", "id": pub, "on": True}, uid=6)[1].get("reason"), "forbidden")
            self.assertTrue(web.post("/api/list", {"act": "delete", "id": pub}, uid=1)[1]["ok"])      # admin o'chira oladi
        finally:
            web.close()

    def test_deep_health(self):
        web = WebServer(self.app)
        try:
            st, body, _ = web.get("/healthz/deep")
            self.assertEqual((st, body), (200, b"ok"))
            self.app.last_poll = 0                                       # bot Telegram bilan aloqani yo'qotdi
            st, body, _ = web.get("/healthz/deep")
            self.assertEqual(st, 503)
            self.assertIn(b"bot_poll", body)
        finally:
            web.close()

    def test_referral_milestone(self):
        from app.core import process_update
        from tests.harness import message
        process_update(self.app, message(100, "/start"))
        for i in range(3):
            process_update(self.app, message(200 + i, f"/start r100"))
        self.assertEqual(self.db.referral_count(100), 3)
        # 3 × (+1) + 3-do'st bosqichi (+3) = 6 kun
        left = (self.db.premium_until(100) - int(__import__("time").time())) / 86400
        self.assertGreater(left, 5.5)
        from app.handlers.user import ref_next
        self.assertEqual(ref_next(3), (10, 10))
        self.assertIsNone(ref_next(50))

    def test_me_has_invite_info(self):
        web = WebServer(self.app)
        try:
            ref = web.json("/api/me", uid=5)[1]["ref"]
            self.assertTrue(ref["link"].endswith("?start=r5"))
            self.assertEqual((ref["n"], ref["next"], ref["bonus"]), (0, 3, 3))
        finally:
            web.close()
