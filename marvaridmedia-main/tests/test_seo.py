"""SEO: sitemap, robots, kino va ro'yxat sahifalari, kanonik havola, JSON-LD, <noscript>, 404."""

import json
import re
import unittest

from tests.harness import WebServer, add_movie, cleanup, make_app


class Seo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app()
        db = cls.app.db
        cls.m1 = add_movie(cls.app, 101, "Avatar: Suv yo'li", desc="Pandora dengizida jang")
        db.x("UPDATE movies SET year=2022, genres=',action,fantasy,', duration=11700, age=12 WHERE id=?", (cls.m1,))
        add_movie(cls.app, 102, "Muzlik davri", cat="cartoon")
        cls.song = add_movie(cls.app, 0, "Qo'shiq", cat="music", ftype="audio")
        cls.web = WebServer(cls.app)

    @classmethod
    def tearDownClass(cls):
        cls.web.close()
        cleanup(cls.app)

    def page(self, path):
        st, body, h = self.web.get(path)
        return st, body.decode()

    def test_robots_and_sitemap(self):
        st, txt = self.page("/robots.txt")
        self.assertIn("Sitemap: ", txt)
        self.assertIn("Disallow: /api/", txt)
        st, xml = self.page("/sitemap.xml")
        self.assertEqual(st, 200)
        self.assertIn("/kino/101-avatar-suv-yoli", xml)
        self.assertIn("/kino/102-muzlik-davri", xml)
        self.assertIn("/janr/action", xml)
        self.assertNotIn("qoshiq", xml)                      # musiqa sitemapga kirmaydi

    def test_movie_page(self):
        st, page = self.page("/kino/101-avatar-suv-yoli")
        self.assertEqual(st, 200)
        self.assertIn("<title>Avatar: Suv yo&#x27;li (2022)", page)
        self.assertIn('rel="canonical" href="https://site.test/kino/101-avatar-suv-yoli"', page)
        self.assertIn("<noscript><article><h1>Avatar", page)
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))["@graph"][0]
        self.assertEqual((ld["@type"], ld["datePublished"], ld["duration"], ld["contentRating"]), ("Movie", "2022", "PT3H15M", "12+"))
        self.assertEqual(ld["genre"], ["Jangari", "Fantastika"])
        # slug noto'g'ri bo'lsa ham kod bo'yicha ochiladi
        self.assertEqual(self.page("/kino/101")[0], 200)

    def test_missing_and_music_are_404_but_still_serve_site(self):
        for path in ("/kino/99999", "/kino/0", "/janr/nomalum"):
            st, page = self.page(path)
            self.assertEqual(st, 404, path)
            self.assertIn('id="view"', page)                  # foydalanuvchi baribir saytni ko'radi

    def test_list_and_genre_pages(self):
        st, page = self.page("/kinolar")
        self.assertEqual(st, 200)
        self.assertIn("/kino/101-avatar-suv-yoli", page)
        self.assertNotIn("/kino/102", page)                   # multfilm kinolar ro'yxatida emas
        st, page = self.page("/janr/action")
        self.assertIn("Jangari kinolar", page)
        self.assertIn("ItemList", page)

    def test_legacy_k_link_gets_canonical(self):
        st, page = self.page("/?k=101")
        self.assertIn('rel="canonical" href="https://site.test/kino/101-avatar-suv-yoli"', page)
        self.assertIn('property="og:image"', page)

    def test_home_not_polluted(self):
        st, page = self.page("/")
        self.assertNotIn("<noscript><article>", page)
        self.assertIn('"@type": "WebSite"', page)                   # bosh sahifa: sayt + qidiruv kutisi (kino sahifasi ma'lumoti emas)
        self.assertNotIn('"@type": "Movie"', page)


if __name__ == "__main__":
    unittest.main()
