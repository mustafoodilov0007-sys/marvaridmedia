"""🌐 Bot tili: ruscha/inglizcha matn, tugmalar, pastki menyu bosilganda to'g'ri ishlov."""

import unittest

from tests.harness import add_movie, cleanup, make_app, message, press


class BotLang(unittest.TestCase):
    def setUp(self):
        self.app = make_app(admins="1")
        from app.core import process_update
        self.run_update = process_update

    def tearDown(self):
        cleanup(self.app)

    def msg(self, uid, t):
        self.run_update(self.app, message(uid, t))

    def press(self, uid, d):
        self.run_update(self.app, press(uid, d))

    def last(self, chat):
        t = self.app.bot.texts(chat)
        return t[-1] if t else ""

    def test_translate_basics(self):
        from app import i18n_bot as t
        self.assertEqual(t.translate("🔎 Kino qidirish", "ru"), "🔎 Поиск фильма")
        self.assertEqual(t.translate("🔎 Kino qidirish", "en"), "🔎 Search movies")
        self.assertEqual(t.translate("🔎 Kino qidirish", ""), "🔎 Kino qidirish")
        kb = {"keyboard": [[{"text": "🎲 Tasodifiy kino"}]]}
        out = t.translate_markup(kb, "ru")
        self.assertEqual(out["keyboard"][0][0]["text"], "🎲 Случайный фильм")
        self.assertEqual(kb["keyboard"][0][0]["text"], "🎲 Tasodifiy kino")        # asl o'zgarmadi

    def test_choose_language_and_menu_works(self):
        add_movie(self.app, 15, "Avatar")
        self.msg(7, "/start")
        self.assertIn("xush kelibsiz", self.last(7))
        self.msg(7, "/til")
        self.press(7, "lg:ru")
        self.assertEqual(self.app.db.get_lang(7), "ru")
        self.assertIn("Здравствуйте", " ".join(self.app.bot.texts(7)))           # salom ruscha
        # ruscha tugma matni bosilganda — asl ishlov beruvchi ishlaydi (tasodifiy kino)
        before = len(self.app.bot.sent)
        self.msg(7, "🎲 Случайный фильм")
        self.assertGreater(len(self.app.bot.sent), before)
        self.press(7, "lg:en")
        self.assertIn("Hello", " ".join(self.app.bot.texts(7)))
        self.press(7, "lg:uz")
        self.assertEqual(self.app.db.get_lang(7), "")
        self.msg(7, "/start")
        self.assertIn("xush kelibsiz", self.last(7))


if __name__ == "__main__":
    unittest.main()
