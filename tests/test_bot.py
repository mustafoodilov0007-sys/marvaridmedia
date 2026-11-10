"""Botning asosiy oqimlari: qidiruv, so'rov, promokod, referal, obuna, admin huquqlari, kun kinosi, xato xabarlari."""

import logging
import time
import unittest

from tests.harness import add_movie, cleanup, make_app, message, press


class BotCase(unittest.TestCase):
    channels = ""

    def setUp(self):
        self.app = make_app(channels=self.channels)
        from app.core import process_update
        self.run_update = process_update

    def tearDown(self):
        cleanup(self.app)

    def msg(self, uid, text):
        self.run_update(self.app, message(uid, text))

    def press(self, uid, data):
        self.run_update(self.app, press(uid, data))

    def last(self, chat=None):
        t = self.app.bot.texts(chat)
        return t[-1] if t else ""


class Basics(BotCase):
    def test_start_and_search(self):
        add_movie(self.app, 15, "Avatar")
        self.msg(5, "/start")
        self.assertIn("xush kelibsiz", " ".join(self.app.bot.texts(5)))
        self.msg(5, "Avatar")
        self.assertIn("Avatar", " ".join(self.app.bot.texts(5)))
        self.msg(5, "15")        # kod bilan: kino yuboriladi
        self.assertTrue(any(n == "send_video" for n, _, _ in self.app.bot.sent))

    def test_not_found_offers_request_button(self):
        self.msg(5, "/start")
        self.msg(5, "mavjud emas kino")
        self.assertIn("hozircha bazamizda yo'q", self.last(5))

    def test_request_not_sent_to_admin_if_movie_exists(self):
        add_movie(self.app, 7, "Avatar Suv yo'li")
        self.msg(1, "/start")
        self.msg(8, "/start")
        self.msg(8, "/sorov")
        self.msg(8, "Avatar 2025, o'zbek tilida kino")
        admin_msgs = [t for t in self.app.bot.texts(1) if "so'rovi" in t]
        self.assertEqual(admin_msgs, [])
        self.assertIn("bazamizda bor", self.last(8))
        self.msg(8, "/sorov")
        self.msg(8, "Umuman yo'q film 3")
        self.assertTrue([t for t in self.app.bot.texts(1) if "so'rovi" in t])

    def test_admin_commands_hidden_from_users(self):
        self.msg(5, "/start")
        before = len(self.app.bot.sent)
        for cmd in ("/admin", "/status", "/kunkino", "/saytpost", "/miniapp x"):
            self.msg(5, cmd)
        texts = " ".join(self.app.bot.texts(5))
        self.assertNotIn("Bot holati", texts)
        self.assertNotIn("Kun kinosi", texts)
        self.assertGreaterEqual(len(self.app.bot.sent), before)


class Promo(BotCase):
    def test_promo_lifecycle(self):
        self.msg(1, "/start")
        self.press(1, "pc:new:3:1")
        import re
        code = re.search(r"MM-[A-Z0-9]{6}", " ".join(self.app.bot.texts(1))).group(0)
        self.msg(2, "/start")
        self.msg(2, "/promo " + code)
        self.assertIn("Promokod qabul qilindi", self.last(2))
        self.assertGreater(self.app.db.premium_until(2), time.time() + 2.9 * 86400)
        self.msg(3, "/start")
        self.msg(3, "/promo " + code)             # ikkinchi marta ishlamaydi
        self.assertIn("topilmadi", self.last(3))
        self.assertEqual(self.app.db.premium_until(3), 0)

    def test_wrong_attempts_limited(self):
        self.msg(4, "/start")
        for _ in range(6):
            self.msg(4, "/promo XXXXXX")
        self.assertIn("Juda ko'p xato", self.last(4))


class Referral(BotCase):
    def test_both_get_bonus_once(self):
        self.msg(10, "/start")
        self.msg(20, "/start r10")
        self.msg(20, "/start r10")
        self.msg(10, "/start r10")
        self.assertEqual(self.app.db.referral_count(10), 1)
        self.assertGreater(self.app.db.premium_until(10), time.time())
        self.assertGreater(self.app.db.premium_until(20), time.time())


class GatedReferral(BotCase):
    channels = "https://t.me/kanal"

    def test_referral_survives_subscription_gate(self):
        self.app.db.add_channel(-100500, "Kanal", "https://t.me/kanal", "public")   # (ishga tushish vaqtidagi urug'lash o'rniga)
        self.app.bot.member_status = "member"
        self.msg(10, "/start")
        self.app.bot.member_status = "left"
        self.msg(20, "/start r10")
        self.assertEqual(self.app.db.referral_count(10), 0)
        self.app.bot.member_status = "member"
        self.press(20, "chk")
        self.assertEqual(self.app.db.referral_count(10), 1)
        self.assertEqual(self.app.db.val("SELECT COUNT(*) FROM searches WHERE norm='r10'"), 0)


class Inline(BotCase):
    def test_inline_results(self):
        add_movie(self.app, 1, "Qora Yulduz")
        self.run_update(self.app, {"update_id": 1, "inline_query": {"id": "q", "from": {"id": 5, "first_name": "A"}, "query": "qora", "offset": ""}})
        calls = [p for n, a, k in self.app.bot.sent if n == "answerInlineQuery" for p in a]
        self.assertTrue(calls and calls[0]["results"][0]["title"] == "Qora Yulduz")


class Daily(BotCase):
    def test_no_repeats_and_no_premium(self):
        from app.handlers import daily
        self.app.set_setting("post_channel", "@kanal")
        for i in range(1, 9):
            add_movie(self.app, i, f"Kino {i}", premium=(i == 3))
        picked = [daily.post_daily(self.app)[0]["title"] for _ in range(6)]
        self.assertEqual(len(set(picked)), 6)
        self.assertNotIn("Kino 3", picked)


class Alerts(BotCase):
    def test_owner_gets_deduplicated_alert(self):
        from app.handlers import ops
        ops.install_alerts(self.app)
        log = logging.getLogger("test_alert")
        try:
            log.error("Sinov xatosi %s", 1)
            log.error("Sinov xatosi %s", 1)
            time.sleep(0.3)
        finally:
            root = logging.getLogger()
            for h in list(root.handlers):
                if isinstance(h, ops.OwnerAlerts):
                    root.removeHandler(h)
        sent = [p for n, a, k in self.app.bot.sent if n == "sendMessage" for p in a]
        self.assertEqual(len(sent), 1)
        self.assertIn("Bot xatosi", sent[0]["text"])


if __name__ == "__main__":
    unittest.main()


class AdminSequels(BotCase):
    def test_next_sequel_gets_next_code(self):
        mid = add_movie(self.app, 60, "Transformerlar 1")
        self.msg(1, "/start")
        self.press(1, f"am:next:{mid}")
        txt = " ".join(self.app.bot.texts(1))
        self.assertIn("Kod: <b>61</b>", txt)

    def test_multserial_choice_sets_flag(self):
        self.msg(1, "/start")
        self.press(1, "am:cat:multserial")
        txt = " ".join(self.app.bot.texts(1))
        self.assertIn("Multserial", txt)
