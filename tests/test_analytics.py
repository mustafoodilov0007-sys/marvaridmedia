"""Tahlil hisob-kitoblari: manbalar, faollik, saqlanib qolish (retention), voronka, daromad."""

import time
import unittest

from tests.harness import WebServer, add_movie, cleanup, make_app, message

DAY = 86400


class Analytics(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.db = self.app.db
        self.t = int(time.time())

    def tearDown(self):
        cleanup(self.app)

    def user(self, uid, joined, active, src):
        self.db.x("INSERT INTO users(user_id, first_name, joined_at, last_active, src) VALUES (?,?,?,?,?)", (uid, "u", joined, active, src))

    def test_numbers(self):
        t = self.t
        j = t - 20 * DAY
        for i in range(6):
            self.user(100 + i, j, j + (3 * DAY if i < 3 else 3600), "channel")      # 3 tasi qaytgan (1 kundan keyin)
        for i in range(4):
            self.user(200 + i, j, j + (10 * DAY if i < 2 else 3600), "referral")    # 2 tasi 7+ kundan keyin ham
        for i in range(5):
            self.user(300 + i, t - 7200, t - 100, "direct")                          # yangi: hali baholab bo'lmaydi
        mid = add_movie(self.app, 1, "Kino")
        for uid in (100, 101, 200, 300):
            self.db.touch_history(uid, mid)
        self.db.create_payment(100, "premium", "card", "approved", days=30, amount=10000)
        self.db.create_payment(101, "premium", "promo", "approved", days=3, amount=0)   # promokod — daromad emas

        from app import analytics
        d = analytics.build(self.db, t)
        src = {s["src"]: s["n"] for s in d["sources"]}
        self.assertEqual(src, {"channel": 6, "referral": 4, "direct": 5})
        self.assertEqual(d["new_total"], 15)
        self.assertEqual(d["retention"]["d1"], 50.0)         # 10 ta eskidan 5 tasi qaytgan (3 + 2)
        self.assertEqual(d["retention"]["d7"], 20.0)         # 2 / 10
        f = {x["label"]: x["n"] for x in d["funnel"]}
        self.assertEqual(f["Qo'shildi"], 15)
        self.assertEqual(f["Kamida 1 kino ko'rdi"], 4)
        self.assertEqual(f["Premium sotib oldi"], 1)       # faqat haqiqiy to'lov
        self.assertEqual(d["revenue"][-1]["premium_uzs"], 10000)
        self.assertEqual(len(d["new_daily"]), 30)
        self.assertEqual(d["active"]["dau"], 5)

    def test_source_detection_on_first_message(self):
        from app.core import process_update, source_of
        for text, want in (("/start", "direct"), ("Avatar", "direct"), ("/start 15", "link"), ("/start 15c", "channel"),
                           ("/start m3c", "channel"), ("/start r10", "referral"), ("/start sorov", "site"), ("/start zzz", "other")):
            self.assertEqual(source_of(text), want, text)
        process_update(self.app, message(41, "/start 7c"))
        process_update(self.app, message(42, "/start r41"))
        self.assertEqual(self.db.get_user(41)["src"], "channel")
        self.assertEqual(self.db.get_user(42)["src"], "referral")
        process_update(self.app, message(41, "/start"))                  # keyingi /start manbani o'zgartirmaydi
        self.assertEqual(self.db.get_user(41)["src"], "channel")

    def test_channel_link_opens_movie_not_search(self):
        from app.core import process_update
        add_movie(self.app, 15, "Avatar")
        process_update(self.app, message(50, "/start 15c"))
        self.assertTrue(any(n == "send_video" for n, _, _ in self.app.bot.sent))
        self.assertIsNone(self.db.q1("SELECT 1 FROM searches WHERE norm='15c'"))

    def test_api_admin_only_and_hits(self):
        web = WebServer(self.app)
        try:
            self.assertEqual(web.json("/api/admin/analytics", uid=5)[1].get("reason"), "forbidden")
            self.assertEqual(web.post("/pub/hit", {"src": "PWA<script>"})[0], 200)       # tozalanadi
            self.assertEqual(web.json("/api/me", uid=1)[0], 200)                         # admin saytni ochdi -> tashrif yoziladi
            st, d = web.json("/api/admin/analytics", uid=1)
            self.assertTrue(d["ok"])
            labels = {s["src"] for s in d["site_sources"]}
            self.assertIn("pwascript", labels)
            self.assertIn("menyu", labels)
        finally:
            web.close()


if __name__ == "__main__":
    unittest.main()
