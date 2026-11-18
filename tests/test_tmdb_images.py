"""🖼 TMDB rasmlari: eski kinolarga qat'iy moslash, server orqali berish (poster va keng rasm), noto'g'ri yo'llar rad etiladi."""
import io
import tempfile
import unittest
from pathlib import Path

from app import tmdb, webapp


class FakeTm:
    def __init__(self, results, images=None):
        self.results, self.images, self.calls = results, images or {"backdrops": []}, []

    def _tmdb(self, path, **params):
        self.calls.append(path)
        if path == "/search/multi":
            return {"results": self.results.get(params.get("language"), [])}
        return self.images


def hit(id_, title, year, overview, orig=None):
    return {"id": id_, "media_type": "movie", "title": title, "original_title": orig or title, "release_date": f"{year}-05-01",
            "overview": overview, "poster_path": f"/poster{id_}abc.jpg", "backdrop_path": f"/back{id_}abc.jpg"}


RU = ("Самому миролюбивому в мире быку, с детства предпочитавшему сидеть под деревом и нюхать цветы, а не бегать вокруг, "
      "выпал нелепый жребий судьбы его как самый большой самый быстрый самый дикий экземпляр по ошибке выбрали для участия в бое быков")


class MatchTests(unittest.TestCase):
    def test_matches_by_description_even_when_title_differs(self):
        tm = FakeTm({"ru-RU": [hit(1, "Фердинанд", 2017, RU, "Ferdinand")], "en-US": []},
                    {"backdrops": [{"file_path": "/textless1.jpg", "vote_average": 5}, {"file_path": "/other11.jpg", "vote_average": 1}]})
        r = tmdb.match_images(tm, "Ferdinand mult", 2017, RU)
        self.assertEqual((r["id"], r["how"], r["backdrop"], r["tposter"]), (1, "tavsif", "/textless1.jpg", "/poster1abc.jpg"))

    def test_exact_title_and_year(self):
        tm = FakeTm({"en-US": [hit(2, "Epic", 2013, "Some text")], "ru-RU": []})
        r = tmdb.match_images(tm, "Epic", 2013, "")
        self.assertEqual((r["id"], r["how"]), (2, "nom+yil"))
        self.assertEqual(r["backdrop"], "/back2abc.jpg")        # rasmlar so'rovi bo'sh bo'lsa — qidiruvdagi keng rasm

    def test_wrong_year_or_unrelated_is_skipped(self):
        tm = FakeTm({"en-US": [hit(3, "Epic", 1999, "Other story entirely different words here nothing alike at all really")], "ru-RU": []})
        self.assertIsNone(tmdb.match_images(tm, "Epic", 2013, "Boshqa tavsif butunlay"))
        self.assertIsNone(tmdb.match_images(FakeTm({}), "", 2013, ""))

    def test_similarity_needs_enough_words(self):
        self.assertEqual(tmdb.overview_similarity("qisqa matn", "qisqa matn"), 0.0)
        self.assertGreater(tmdb.overview_similarity(RU, RU), 0.99)


class ServeTests(unittest.TestCase):
    def test_tposter_key_changes_poster_key_and_bad_path_ignored(self):
        from tests.harness import make_app, add_movie
        app = make_app(admins="1")
        mid = add_movie(app, 5, "Kino")
        base = webapp._item(app.db.q("SELECT m.*, 0 AS likes, 0 AS dislikes, 0 AS parts FROM movies m WHERE m.id=?", (mid,))[0], False, False)
        app.db.update_movie(mid, tposter="/okposter1.jpg", backdrop="/okbackdr1.jpg")
        it = webapp._item(app.db.q("SELECT m.*, 0 AS likes, 0 AS dislikes, 0 AS parts FROM movies m WHERE m.id=?", (mid,))[0], False, False)
        self.assertNotEqual(it["poster"], base["poster"])
        self.assertEqual(it["bd"], "/okbackdr1.jpg")
        app.db.update_movie(mid, tposter="https://evil.example/x.jpg", backdrop="../../etc/passwd")
        it = webapp._item(app.db.q("SELECT m.*, 0 AS likes, 0 AS dislikes, 0 AS parts FROM movies m WHERE m.id=?", (mid,))[0], False, False)
        self.assertEqual(it["bd"], "")
        self.assertEqual(it["poster"], base["poster"])

    def test_backdrop_and_tmdb_poster_are_served_and_fall_back(self):
        from tests.harness import make_app, add_movie
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow yo'q")
        buf = io.BytesIO(); Image.new("RGB", (1280, 720), (200, 40, 40)).save(buf, "JPEG"); big = buf.getvalue()
        buf = io.BytesIO(); Image.new("RGB", (1000, 1500), (40, 40, 200)).save(buf, "JPEG"); tall = buf.getvalue()
        app = make_app(admins="1")
        mid = add_movie(app, 6, "Kino")
        app.db.update_movie(mid, tposter="/okposter1.jpg", backdrop="/okbackdr1.jpg")
        orig = webapp._download_tmdb
        webapp._tposter_fail.clear()
        try:
            webapp._download_tmdb = lambda url: big if "w1280" in url else tall
            with tempfile.TemporaryDirectory() as d:
                d = Path(d)
                b = webapp.backdrop_bytes(app, mid, d, 780)
                self.assertEqual(Image.open(io.BytesIO(b)).width, 780)
                p = webapp.poster_bytes(app, mid, d, 540)
                self.assertEqual(Image.open(io.BytesIO(p)).width, 540)
                webapp._download_tmdb = lambda url: None      # TMDB ishlamasa: backdrop yo'q (404), poster esa Telegram'ga qaytadi
                webapp._tposter_fail.clear()
                app.db.update_movie(mid, backdrop="/otherbd22.jpg", tposter="")
                self.assertIsNone(webapp.backdrop_bytes(app, mid, d, 780))
        finally:
            webapp._download_tmdb = orig


if __name__ == "__main__":
    unittest.main()
