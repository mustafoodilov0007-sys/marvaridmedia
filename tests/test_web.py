"""Sayt serveri: sahifalar, PWA, boy havola, ochiq va admin API, bolalar rejimi, chegaralar, chidamlilik."""

import json
import unittest

from tests.harness import WebServer, add_movie, cleanup, make_app


class WebCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(admins="1")
        db = cls.app.db
        cls.m1 = add_movie(cls.app, 101, "Avatar Suv yo'li")
        cls.m2 = add_movie(cls.app, 102, "Shrek 2", cat="cartoon")
        cls.m3 = add_movie(cls.app, 103, "Qasoskorlar", premium=True)
        db.x("UPDATE movies SET age=16, year=2019, genres=',action,' WHERE id=?", (cls.m3,))
        db.x("UPDATE movies SET age=6 WHERE id=?", (cls.m2,))
        db.rate(5, cls.m1, 1)
        for _ in range(3):
            db.inc_views(cls.m1, db.get_parts(cls.m1)[0]["id"])
        cls.web = WebServer(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.web.close()
        cleanup(cls.app)


class Pages(WebCase):
    def test_index_has_open_graph_and_pwa_links(self):
        st, body, h = self.web.get("/")
        page = body.decode()
        self.assertEqual(st, 200)
        self.assertIn('property="og:image"', page)
        self.assertIn('rel="manifest"', page)

    def test_collection_pages_for_search_engines(self):
        db = self.app.db
        cid = db.add_collection("Marvel to'plami")
        db.add_to_collection(cid, self.m1)
        db.add_to_collection(cid, self.m3)
        st, body, _ = self.web.get(f"/kolleksiya/{cid}-marvel-toplami")
        page = body.decode()
        self.assertEqual(st, 200)
        self.assertIn("Marvel to&#x27;plami — kinolar o&#x27;zbek tilida", page)
        self.assertIn('"@type": "ItemList"', page)
        self.assertIn('rel="canonical"', page)
        self.assertIn("Avatar Suv yo&#x27;li", page)                                  # <noscript> ro'yxatida
        st2, body2, _ = self.web.get("/kolleksiyalar")
        self.assertEqual(st2, 200)
        self.assertIn(f"/kolleksiya/{cid}-marvel-toplami", body2.decode())
        self.assertEqual(self.web.get("/kolleksiya/99999")[0], 404)
        from app import seo
        seo._cache.clear()                                                          # sitemap 1 soat keshlanadi
        sm = self.web.get("/sitemap.xml")[1].decode()
        self.assertIn(f"/kolleksiya/{cid}-marvel-toplami", sm)

    def test_movie_link_preview(self):
        st, body, _ = self.web.get("/?k=101")
        page = body.decode()
        self.assertIn("Avatar Suv yo&#x27;li", page)          # nom kartochkada
        self.assertTrue(f"/og/{self.m1}.jpg?v=" in page or f"/api/poster/{self.m1}?v=" in page)   # ulashish kartochkasi (Pillow bo'lmasa — poster)

    def test_manifest_service_worker_and_icons(self):
        st, body, _ = self.web.get("/manifest.webmanifest")
        m = json.loads(body)
        self.assertEqual((st, m["display"]), (200, "standalone"))
        self.assertTrue(any(i["purpose"] == "maskable" for i in m["icons"]))
        st, body, h = self.web.get("/sw.js")
        self.assertEqual(st, 200)
        self.assertIn("javascript", h["Content-Type"])
        for f in ("/icon-192.png", "/icon-512.png", "/og.png", "/apple-touch-icon.png"):
            self.assertEqual(self.web.get(f)[0], 200, f)

    def test_gzip(self):
        st, body, h = self.web.get("/", headers={"Accept-Encoding": "gzip"})
        self.assertEqual(h.get("Content-Encoding"), "gzip")


class PublicApi(WebCase):
    def test_home_has_weekly_and_rails(self):
        st, d = self.web.json("/pub/home")
        self.assertTrue(d["ok"])
        self.assertGreaterEqual(len(d["weekly"]), 1)
        self.assertEqual(d["weekly"][0]["title"], "Avatar Suv yo'li")     # haftada eng ko'p ko'rilgan
        self.assertTrue(any(r["key"] == "top" for r in d["rails"]))

    def test_catalog_search_and_filters(self):
        _, d = self.web.json("/pub/catalog?cat=video&q=avatar")
        self.assertEqual([i["title"] for i in d["items"]], ["Avatar Suv yo'li"])
        _, d = self.web.json("/pub/catalog?cat=cartoon")
        self.assertEqual([i["title"] for i in d["items"]], ["Shrek 2"])

    def test_kids_mode_filters_server_side(self):
        _, d = self.web.json("/pub/catalog?cat=video", headers={"X-Kids": "1"})
        self.assertEqual([i["title"] for i in d["items"]], ["Shrek 2"])    # faqat multfilm (6+)
        _, d = self.web.json("/pub/home", headers={"X-Kids": "1"})
        self.assertTrue(all(i["cat"] == "cartoon" for r in d["rails"] for i in r["items"]))

    def test_premium_locked_for_guests(self):
        _, d = self.web.json("/pub/catalog?cat=video&q=qasoskorlar")
        self.assertTrue(d["items"][0]["premium"])


class AdminApi(WebCase):
    def test_admin_endpoints_closed_to_others(self):
        for path in (f"/api/admin/movie?id={self.m1}", "/api/admin/stats"):
            self.assertEqual(self.web.json(path, uid=5)[1].get("reason"), "forbidden", path)
            self.assertEqual(self.web.json("/pub" + path[4:])[1].get("reason"), "forbidden", path)
        self.assertEqual(self.web.post("/api/admin/save", {"id": self.m1, "title": "Hack"}, uid=5)[1].get("reason"), "forbidden")
        self.assertEqual(self.web.post("/api/admin/delete", {"id": self.m1}, uid=5)[1].get("reason"), "forbidden")

    def test_admin_can_edit_and_validate(self):
        st, d = self.web.json(f"/api/admin/movie?id={self.m2}", uid=1)
        self.assertTrue(d["ok"])
        r = self.web.post("/api/admin/save", {"id": self.m2, "year": "abc"}, uid=1)[1]
        self.assertEqual(r["reason"], "year")
        r = self.web.post("/api/admin/save", {"id": self.m2, "imdb": "11"}, uid=1)[1]
        self.assertEqual(r["reason"], "imdb")
        r = self.web.post("/api/admin/save", {"id": self.m2, "imdb": "7,9", "duration_min": 95, "age": 12}, uid=1)[1]
        self.assertTrue(r["ok"])
        row = self.app.db.get_movie(self.m2)
        self.assertEqual((row["imdb"], row["duration"], row["age"]), ("7.9", 95 * 60, 12))
        self.app.db.update_movie(self.m2, age=6)

    def test_stats_for_admin(self):
        _, d = self.web.json("/api/admin/stats", uid=1)
        self.assertTrue(d["ok"])
        self.assertEqual(len(d["daily"]), 14)


class Robustness(WebCase):
    def test_weird_inputs_never_crash(self):
        weird = ["", "0", "-1", "99999999999999999999", "%00", "' OR 1=1--", "<script>", "../../etc/passwd", "a" * 3000, "💥"]
        import urllib.parse
        for w in weird:
            q = urllib.parse.quote(w, safe="")
            for path in (f"/pub/catalog?cat={q}&q={q}&offset={q}&year={q}", f"/pub/similar?id={q}", f"/api/poster/{q}",
                         f"/media/short/{q}", f"/pub/collection?id={q}"):
                st, _, _ = self.web.get(path)
                self.assertLess(st, 500, path[:60])
        st, _, _ = self.web.get("/api/admin/stats")
        self.assertEqual(st, 401)                                  # imzosiz — rad etiladi

    def test_rate_limit_is_per_user_not_per_ip(self):
        # bir foydalanuvchi chegaradan o'tsa, boshqasi (bir xil IP dan) to'silmaydi
        codes = [self.web.get("/api/me", uid=77)[0] for _ in range(330)]
        self.assertIn(429, codes)
        self.assertEqual(self.web.get("/api/me", uid=78)[0], 200)


if __name__ == "__main__":
    unittest.main()
