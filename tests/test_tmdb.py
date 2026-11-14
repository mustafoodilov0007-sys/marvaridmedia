"""TMDB/OMDb: qidiruv, janr/davlat/yosh/IMDb moslash, kinoga qo'llash, admin API (soxta TMDB server bilan)."""

import json
import os
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.harness import WebServer, add_movie, cleanup, make_app

MOVIE = {"id": 299534, "title": "Avengers: Endgame", "original_title": "Avengers: Endgame", "release_date": "2019-04-24",
         "overview": "Мстители собираются", "genres": [{"id": 12}, {"id": 878}, {"id": 28}], "runtime": 181, "original_language": "en",
         "production_countries": [{"iso_3166_1": "US"}], "poster_path": "/p.jpg",
         "external_ids": {"imdb_id": "tt4154796"}, "budget": 356000000, "revenue": 2797800564,
         "credits": {"cast": [{"name": "Robert Downey Jr.", "character": "Tony Stark", "profile_path": "/rdj123.jpg"},
                              {"name": "Bez Rasm", "character": "", "profile_path": None},
                              {"name": "Xavfli", "character": "X", "profile_path": "https://evil.example/a.jpg"},
                              {"name": "  ", "character": "bo'sh ism", "profile_path": "/x12345.jpg"}]},
         "images": {"backdrops": [{"file_path": "/withtext1.jpg", "iso_639_1": "en", "vote_average": 9},
                                  {"file_path": "/notext12.jpg", "iso_639_1": None, "vote_average": 5},
                                  {"file_path": "http://evil.example/b.jpg", "iso_639_1": None, "vote_average": 10}]},
         "videos": {"results": [{"site": "Vimeo", "type": "Trailer", "key": "vimeo1234"},
                                {"site": "YouTube", "type": "Teaser", "key": "teaser12345", "official": True},
                                {"site": "YouTube", "type": "Trailer", "key": "enOld123456", "iso_639_1": "en", "official": True, "published_at": "2019-01-01"},
                                {"site": "YouTube", "type": "Trailer", "key": "ruTrailer12", "iso_639_1": "ru", "official": True, "published_at": "2019-02-01"}]},
         "release_dates": {"results": [{"iso_3166_1": "DE", "release_dates": [{"certification": "12"}]},
                                       {"iso_3166_1": "US", "release_dates": [{"certification": ""}, {"certification": "PG-13"}]}]}}
TV = {"id": 1396, "name": "Breaking Bad", "first_air_date": "2008-01-20", "overview": "", "genres": [{"id": 18}, {"id": 80}],
      "episode_run_time": [47], "original_language": "en", "origin_country": ["US"], "external_ids": {"imdb_id": "tt0903747"},
      "content_ratings": {"results": [{"iso_3166_1": "US", "rating": "TV-MA"}]}}
ANIME = {"id": 5, "title": "Spirited Away", "release_date": "2001-07-20", "genres": [{"id": 16}, {"id": 14}], "runtime": 125,
         "original_language": "ja", "production_countries": [{"iso_3166_1": "JP"}], "external_ids": {}}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urllib.parse.urlsplit(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/3/search/multi":
            body = {"results": [{"id": 299534, "media_type": "movie", "title": "Avengers: Endgame", "original_title": "Avengers: Endgame",
                                 "release_date": "2019-04-24", "popularity": 90, "poster_path": "/p.jpg", "overview": "x"},
                                {"id": 7, "media_type": "person", "name": "Someone"},
                                {"id": 1396, "media_type": "tv", "name": "Breaking Bad", "first_air_date": "2008-01-20", "popularity": 50}]}
        elif u.path == "/3/movie/299534":
            body = dict(MOVIE, overview=MOVIE["overview"] if q.get("language") == "ru-RU" else "Heroes assemble")
        elif u.path == "/3/tv/1396":
            body = dict(TV, overview="" if q.get("language") == "ru-RU" else "A chemistry teacher")
        elif u.path == "/3/movie/5":
            body = ANIME
        elif u.path == "/omdb/":
            body = {"imdbRating": "8.4" if q.get("i") == "tt4154796" else "N/A"}
        else:
            self.send_response(404); self.end_headers(); return
        if u.path.startswith("/3/") and q.get("api_key") != "KEY" and not self.headers.get("Authorization"):
            self.send_response(401); self.end_headers(); return
        data = json.dumps(body).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


class TmdbCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        os.environ.update(TMDB_API_KEY="KEY", TMDB_BASE=base + "/3", OMDB_API_KEY="OK", OMDB_BASE=base + "/omdb/", TMDB_LANG="ru-RU")
        cls.app = make_app()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cleanup(cls.app)
        for k in ("TMDB_API_KEY", "TMDB_BASE", "OMDB_API_KEY", "OMDB_BASE", "TMDB_LANG"):
            os.environ.pop(k, None)

    def t(self):
        from app import tmdb
        return tmdb.get(self.app)

    def test_search_filters_and_ranks(self):
        r = self.t().search("avengers endgame", 2019)
        self.assertEqual([x["kind"] for x in r], ["movie", "tv"])          # «person» tashlab ketildi
        self.assertEqual(r[0]["year"], 2019)

    def test_movie_details_mapping(self):
        d = self.t().details("movie", 299534)
        self.assertEqual((d["year"], d["duration_min"], d["age"], d["country"], d["imdb"]), (2019, 181, 12, "us", "8.4"))
        self.assertEqual(sorted(d["genres"]), ["action", "adventure", "fantasy"])    # Sci-Fi -> fantasy
        self.assertEqual(d["category"], "movie")
        self.assertTrue(d["overview"].startswith("Мстители"))

    def test_tv_details_and_english_fallback(self):
        d = self.t().details("tv", 1396)
        self.assertEqual((d["category"], d["duration_min"], d["age"], d["year"]), ("serial", 47, 18, 2008))
        self.assertEqual(sorted(d["genres"]), ["criminal", "drama"])
        self.assertEqual(d["overview"], "A chemistry teacher")                      # ruscha yo'q — inglizcha
        self.assertEqual(d["imdb"], "")                                              # OMDb «N/A»

    def test_anime(self):
        d = self.t().details("movie", 5)
        self.assertIn("anime", d["genres"])
        self.assertEqual(d["country"], "jp")

    def test_apply_does_not_clobber_description(self):
        from app import tmdb
        mid = add_movie(self.app, 1, "Qasoskorlar: Final", desc="Mening izohim")
        data = self.t().details("movie", 299534)
        ch = tmdb.apply_fields(self.app.db, mid, data)
        m = self.app.db.get_movie(mid)
        self.assertNotIn("izoh", ch)
        self.assertEqual((m["year"], m["duration"], m["age"], m["imdb"], m["country"]), (2019, 181 * 60, 12, "8.4", "us"))
        self.assertEqual(m["description"], "Mening izohim")
        tmdb.apply_fields(self.app.db, mid, data, with_description=True)
        self.assertTrue(self.app.db.get_movie(mid)["description"].startswith("Мстители"))
        empty = add_movie(self.app, 2, "Bo'sh izohli", desc="")
        self.assertIn("izoh", tmdb.apply_fields(self.app.db, empty, data))            # bo'sh bo'lsa o'zi to'ldiriladi

    def test_admin_api(self):
        web = WebServer(self.app)
        try:
            self.assertEqual(web.json("/api/admin/tmdb?q=x", uid=5)[1]["reason"], "forbidden")
            st, d = web.json("/api/admin/tmdb?q=avengers&year=2019", uid=1)
            self.assertTrue(d["ok"] and d["items"][0]["id"] == 299534)
            st, d = web.json("/api/admin/tmdb?kind=movie&id=299534", uid=1)
            self.assertEqual(d["data"]["imdb"], "8.4")
            st, d = web.json("/api/admin/tmdb?kind=movie&id=424242", uid=1)       # TMDB 404
            self.assertEqual(d["reason"], "tmdb")
        finally:
            web.close()

    def test_extra_cast_stills_budget_trailer(self):
        d = self.t().details("movie", 299534)
        ex = d["extra"]
        self.assertEqual([c["n"] for c in ex["cast"]], ["Robert Downey Jr.", "Bez Rasm", "Xavfli"])      # bo'sh ism tashlandi
        self.assertEqual(ex["cast"][0], {"n": "Robert Downey Jr.", "r": "Tony Stark", "p": "/rdj123.jpg"})
        self.assertEqual(ex["cast"][1]["p"], "")                                                          # rasmsiz — bo'sh
        self.assertEqual(ex["cast"][2]["p"], "")                                                          # begona manzil o'tmaydi
        self.assertEqual(ex["stills"], ["/notext12.jpg", "/withtext1.jpg"])                               # matnsiz oldinda, begona manzil yo'q
        self.assertEqual((ex["budget"], ex["revenue"]), (356000000, 2797800564))
        self.assertEqual(d["trailer"], "https://www.youtube.com/watch?v=ruTrailer12")                    # YouTube + Trailer + ruscha afzal
        tv = self.t().details("tv", 1396)
        self.assertEqual(tv["extra"], {})                                                                 # ma'lumot yo'q — bo'sh
        self.assertEqual(tv["trailer"], "")

    def test_apply_saves_extra_and_keeps_manual_trailer(self):
        import json
        from app import tmdb
        data = self.t().details("movie", 299534)
        a = add_movie(self.app, 31, "Bir", desc="")
        ch = tmdb.apply_fields(self.app.db, a, data)
        self.assertIn("aktyorlar/kadrlar", ch)
        self.assertIn("treyler", ch)
        m = self.app.db.get_movie(a)
        self.assertEqual(json.loads(m["extra"])["cast"][0]["n"], "Robert Downey Jr.")
        self.assertEqual(m["trailer_url"], "https://www.youtube.com/watch?v=ruTrailer12")
        b = add_movie(self.app, 32, "Ikki", desc="")
        self.app.db.update_movie(b, trailer_url="https://youtu.be/manual12345")
        self.assertNotIn("treyler", tmdb.apply_fields(self.app.db, b, data))
        self.assertEqual(self.app.db.get_movie(b)["trailer_url"], "https://youtu.be/manual12345")

    def test_extra_api_public_and_sanitized(self):
        mid = add_movie(self.app, 33, "Uch", desc="")
        web = WebServer(self.app)
        try:
            self.assertEqual(web.json(f"/pub/extra?id={mid}")[1], {"ok": True, "cast": [], "stills": [], "budget": 0, "revenue": 0})
            # admin saqlash: TMDB tanlovi yuboriladi — aktyor/kadr serverda TMDB dan olinadi
            st, r = web.post("/api/admin/save", {"id": mid, "tmdb": {"kind": "movie", "id": 299534}}, uid=1)
            self.assertTrue(r["ok"], r)
            st, d = web.json(f"/pub/extra?id={mid}")                      # mehmon ham ko'ra oladi
            self.assertEqual(d["cast"][0]["n"], "Robert Downey Jr.")
            self.assertEqual(d["stills"], ["/notext12.jpg", "/withtext1.jpg"])
            self.assertEqual(d["revenue"], 2797800564)
            # bazadagi ma'lumotga begona manzil tushib qolgan bo'lsa ham javobga chiqmaydi
            self.app.db.update_movie(mid, extra=json.dumps({"cast": [{"n": "Z", "r": "r", "p": "https://evil.example/p.jpg"}],
                                                            "stills": ["https://evil.example/s.jpg", "/ok12345.jpg"], "budget": "x"}))
            st, d = web.json(f"/pub/extra?id={mid}")
            self.assertEqual((d["cast"][0]["p"], d["stills"], d["budget"]), ("", ["/ok12345.jpg"], 0))
            self.assertEqual(web.json("/pub/extra?id=999999")[1]["reason"], "not_found")
            self.assertEqual(web.json("/pub/extra?id=abc")[1]["reason"], "not_found")
        finally:
            web.close()

    def test_save_with_tmdb_pick_requires_admin(self):
        mid = add_movie(self.app, 34, "To'rt", desc="")
        web = WebServer(self.app)
        try:
            st, r = web.post("/api/admin/save", {"id": mid, "tmdb": {"kind": "movie", "id": 299534}}, uid=5)
            self.assertEqual(r["reason"], "forbidden")
            st, d = web.json(f"/pub/extra?id={mid}")
            self.assertEqual(d["cast"], [])
            st, r = web.post("/api/admin/save", {"id": mid, "tmdb": {"kind": "movie", "id": 424242}}, uid=1)     # TMDB 404
            self.assertTrue(r["ok"] and r.get("warn") == "tmdb")                                                    # qolgan saqlanadi, ogohlantirish
        finally:
            web.close()

    def _buttons(self):
        out = []
        for name, a, k in self.app.bot.sent:
            for x in list(a) + list(k.values()):
                if isinstance(x, dict) and "inline_keyboard" in x:
                    out += [b.get("callback_data", "") for row in x["inline_keyboard"] for b in row]
        return out

    def test_bot_flow(self):
        from app.core import process_update
        from tests.harness import message, press
        mid = add_movie(self.app, 9, "Qasoskorlar: Yakun", desc="")
        self.app.bot.sent.clear()
        process_update(self.app, message(1, "/start"))
        process_update(self.app, press(1, f"dm:tm:{mid}"))
        self.assertIn("asl (inglizcha) nomini", " ".join(self.app.bot.texts(1)))
        process_update(self.app, message(1, "Avengers Endgame 2019"))
        pick = [b for b in self._buttons() if b.startswith(f"tm:p:{mid}:movie:299534")]
        self.assertTrue(pick, "variantlar chiqmadi")
        process_update(self.app, press(1, pick[-1]))
        self.assertIn("Avengers: Endgame", " ".join(self.app.bot.texts(1)))
        process_update(self.app, press(1, f"tm:a:{mid}:movie:299534"))
        m = self.app.db.get_movie(mid)
        self.assertEqual((m["year"], m["duration"], m["imdb"], m["age"]), (2019, 181 * 60, "8.4", 12))
        self.assertTrue(m["description"].startswith("Мстители"))        # izoh bo'sh edi — to'ldirildi
        # oddiy foydalanuvchi bu tugmani bosolmaydi
        before = self.app.db.get_movie(mid)["imdb"]
        process_update(self.app, press(5, f"tm:a:{mid}:movie:5"))
        self.assertEqual(self.app.db.get_movie(mid)["imdb"], before)

    def test_not_configured(self):
        saved = self.app.config.tmdb_key
        self.app.config.tmdb_key = ""
        web = WebServer(self.app)
        try:
            self.assertEqual(web.json("/api/admin/tmdb?q=x", uid=1)[1]["reason"], "not_configured")
        finally:
            self.app.config.tmdb_key = saved
            web.close()


if __name__ == "__main__":
    unittest.main()
