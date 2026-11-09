"""🔐 Saytga kirish: Telegram (bot tasdiqlashi bilan) va Google, sessiyalar, ruxsatlar."""

import unittest
from unittest import mock

from tests.harness import WebServer, add_movie, cleanup, make_app, message, press


class AuthCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = make_app(admins="1")
        cls.mid = add_movie(cls.app, 10, "Avatar")
        cls.web = WebServer(cls.app)
        from app.core import process_update
        cls.upd = staticmethod(lambda u: process_update(cls.app, u))

    @classmethod
    def tearDownClass(cls):
        cls.web.close()
        cleanup(cls.app)

    def api(self, method, path, session="", data=None):
        import json
        import urllib.request
        h = {"Content-Type": "application/json"}
        if session:
            h["X-Session"] = session
        req = urllib.request.Request(self.web.base + path, data=json.dumps(data or {}).encode() if method == "POST" else None,
                                     headers=h, method=method)
        import urllib.error
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode() or "{}")

    def telegram_login(self, uid=7, name="Ali"):
        _, st = self.api("POST", "/pub/auth/tg/start")
        tok = st["token"]
        self.assertIn(f"start=wl_{tok}", st["link"])
        self.upd(message(uid, f"/start wl_{tok}", name))                 # havola ochildi → bot tasdiq so'raydi
        self.assertIn("Saytga kirish", " ".join(self.app.bot.texts(uid)))
        _, pending = self.api("POST", "/pub/auth/tg/poll", data={"token": tok})
        self.assertEqual(pending["status"], "pending")                   # tasdiqlanmaguncha — kirmaydi
        self.upd(press(uid, f"wl:ok:{tok}"))
        _, done = self.api("POST", "/pub/auth/tg/poll", data={"token": tok})
        return tok, done


class TelegramLogin(AuthCase):
    def test_full_flow_and_session_works_for_api(self):
        tok, done = self.telegram_login()
        self.assertEqual(done["status"], "done")
        sess = done["session"]
        st, me = self.api("GET", "/api/me", sess)
        self.assertTrue(me["ok"] and me["web"] and me["tg"])
        self.assertEqual(me["name"], "Ali")
        # izoh yozish
        st, r = self.api("POST", "/api/comment", sess, {"id": self.mid, "body": "Zo'r kino ekan!"})
        self.assertTrue(r["ok"])
        # token bir martalik
        _, again = self.api("POST", "/pub/auth/tg/poll", data={"token": tok})
        self.assertFalse(again["ok"])

    def test_bad_session_rejected_and_logout(self):
        st, me = self.api("GET", "/api/me", "yolg'on-sessiya")
        self.assertEqual(st, 401)
        _, done = self.telegram_login(uid=8, name="Vali")
        sess = done["session"]
        self.assertEqual(self.api("GET", "/api/me", sess)[0], 200)
        self.api("POST", "/api/auth/logout", sess)
        self.assertEqual(self.api("GET", "/api/me", sess)[0], 401)

    def test_decline_and_expired_link(self):
        _, st = self.api("POST", "/pub/auth/tg/start")
        tok = st["token"]
        self.upd(message(9, f"/start wl_{tok}"))
        self.upd(press(9, f"wl:no:{tok}"))
        self.assertFalse(self.api("POST", "/pub/auth/tg/poll", data={"token": tok})[1]["ok"])
        self.upd(message(9, "/start wl_nomalum"))
        self.assertIn("eskirgan", self.app.bot.texts(9)[-1])

    def test_login_link_bypasses_subscription_gate(self):
        self.app.db.add_channel("-100500", "Kanal", "https://t.me/kanal", "public")
        self.app.bot.member_status = "left"
        try:
            _, st = self.api("POST", "/pub/auth/tg/start")
            self.upd(message(11, f"/start wl_{st['token']}"))
            self.assertIn("Saytga kirish", self.app.bot.texts(11)[-1])
        finally:
            self.app.bot.member_status = "member"


class GoogleLogin(AuthCase):
    def test_google_requires_configuration_and_valid_token(self):
        self.app.config.google_client_id = ""
        self.assertFalse(self.api("POST", "/pub/auth/google", data={"credential": "x"})[1]["ok"])
        self.app.config.google_client_id = "cid.apps.googleusercontent.com"
        good = {"aud": "cid.apps.googleusercontent.com", "iss": "https://accounts.google.com", "email_verified": "true",
                "exp": "9999999999", "sub": "123", "email": "a@gmail.com", "name": "Gulnora", "picture": "https://x/p.jpg"}
        with mock.patch("app.webapp._google_verify", return_value=good):
            st, r = self.api("POST", "/pub/auth/google", data={"credential": "jwt"})
        self.assertTrue(r["ok"])
        sess = r["session"]
        _, me = self.api("GET", "/api/me", sess)
        self.assertTrue(me["web"] and not me["tg"])
        self.assertEqual(me["name"], "Gulnora")
        # Google akkaunt izoh yoza oladi, ismi chiqadi; botga yuborish (watch) esa mumkin emas
        _, c = self.api("POST", "/api/comment", sess, {"id": self.mid, "body": "Google orqali yozdim"})
        self.assertTrue(c["ok"] and c["item"]["name"] == "Gulnora")
        _, w = self.api("POST", "/api/watch", sess, {"id": self.mid})
        self.assertEqual(w["reason"], "no_telegram")
        # akkaunt «users» jadvaliga tushmaydi (xabar yuborish/statistika buzilmaydi)
        self.assertEqual(self.app.db.val("SELECT COUNT(*) FROM users WHERE user_id<0"), 0)

    def test_google_verify_rejects_wrong_audience(self):
        from app import webapp

        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return b'{"aud":"boshqa","iss":"accounts.google.com","email_verified":"true","exp":"9999999999","sub":"1"}'
        self.app.config.google_client_id = "cid"
        with mock.patch("urllib.request.urlopen", return_value=R()):
            self.assertIsNone(webapp._google_verify(self.app, "jwt"))

    def test_me_exposes_google_client_id_for_guests(self):
        self.app.config.google_client_id = "cid"
        _, me = self.api("GET", "/pub/me")
        self.assertEqual(me["google"], "cid")


class Ads(AuthCase):
    def test_yandex_verification_file(self):
        import urllib.request
        with urllib.request.urlopen(self.web.base + "/yandex_ad2be0e9bc24166d.html", timeout=15) as r:
            self.assertEqual(r.status, 200)
            self.assertIn("Verification: ad2be0e9bc24166d", r.read().decode())

    def test_yandex_code_in_head_and_csp(self):
        import urllib.request
        self.app.config.yandex_ads_id = "20369723"
        with urllib.request.urlopen(self.web.base + "/", timeout=15) as r:
            html = r.read().decode()
            csp = r.headers["Content-Security-Policy"]
        self.assertIn('data-page-id="20369723" src="https://yandex.ru/ads/system/ap-loader.js"', html)
        self.assertLess(html.index("ap-loader.js"), html.index("</head>"))
        self.assertIn("https://yandex.ru", csp)
        self.app.config.yandex_ads_id = ""
        with urllib.request.urlopen(self.web.base + "/", timeout=15) as r:
            self.assertNotIn("ap-loader.js", r.read().decode())


if __name__ == "__main__":
    unittest.main()
