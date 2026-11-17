"""Poster sifati: bot kichik rasmni ogohlantiradi; server aniqroq o'lchamlarni beradi."""
import io
import unittest

from app.handlers import admin_movies as am


class FakeBot:
    def __init__(self, sent_photo=None):
        self.msgs, self.sent_photo = [], sent_photo or [{"file_id": "F", "width": 500, "height": 700}]

    def safe(self, method, params=None, **kw):
        if method == "sendMessage":
            self.msgs.append(params["text"])

    def call(self, method, params=None, **kw):
        if method == "getFile":
            return {"file_path": "x.jpg"}
        if method == "sendPhoto":
            return {"photo": self.sent_photo, "message_id": 9}
        return {}

    def download_file(self, path):
        return b"img"


class FakeCtx:
    def __init__(self, message, bot, music=False):
        self.message, self.bot, self.chat_id = message, bot, 1
        self._music = music


class PosterQualityTests(unittest.TestCase):
    def setUp(self):
        self._orig = am._is_music
        am._is_music = lambda ctx: getattr(ctx, "_music", False)

    def tearDown(self):
        am._is_music = self._orig

    def test_low_res_photo_warns_but_is_accepted(self):
        bot = FakeBot()
        ctx = FakeCtx({"photo": [{"file_id": "a", "width": 90, "height": 120}, {"file_id": "b", "width": 480, "height": 720}]}, bot)
        self.assertEqual(am.poster_from(ctx), "b")                       # poster qabul qilinadi
        self.assertEqual(len(bot.msgs), 1)
        self.assertIn("480×720", bot.msgs[0])

    def test_good_photo_has_no_warning(self):
        bot = FakeBot()
        ctx = FakeCtx({"photo": [{"file_id": "b", "width": 853, "height": 1280}]}, bot)
        self.assertEqual(am.poster_from(ctx), "b")
        self.assertEqual(bot.msgs, [])

    def test_document_image_checked_after_resend(self):
        bot = FakeBot([{"file_id": "F", "width": 500, "height": 700}])
        ctx = FakeCtx({"document": {"file_id": "d", "mime_type": "image/jpeg", "file_size": 1000, "file_name": "p.jpg"}}, bot)
        self.assertEqual(am.poster_from(ctx), "F")
        self.assertIn("500×700", bot.msgs[0])

    def test_square_music_cover_is_fine(self):
        bot = FakeBot()
        ctx = FakeCtx({"photo": [{"file_id": "c", "width": 640, "height": 640}]}, bot, music=True)
        self.assertEqual(am.poster_from(ctx), "c")
        self.assertEqual(bot.msgs, [])                                    # kvadrat muqova — me'yorda

    def test_new_widths_and_sharper_resize(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow o'rnatilmagan")
        from app import webapp
        im = Image.new("RGB", (853, 1280), (120, 60, 40))
        b = io.BytesIO(); im.save(b, "JPEG", quality=90)
        for w in (360, 540, 720):
            out = Image.open(io.BytesIO(webapp._thumb(b.getvalue(), w)))
            self.assertEqual(out.width, w)                                # kerakli kenglikka kichrayadi
        out = Image.open(io.BytesIO(webapp._thumb(b.getvalue(), 1080)))
        self.assertEqual(out.width, 853)                                  # asl rasmdan katta qilinmaydi (xiralashtirmaydi)


if __name__ == "__main__":
    unittest.main()
