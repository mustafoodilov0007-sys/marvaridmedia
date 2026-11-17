"""💬 Saytdagi izohlar: tekshiruvlar, javoblar, yoqtirish, shikoyat, moderatsiya."""

import time
import unittest

from tests.harness import add_movie, cleanup, make_app


class CommentsCase(unittest.TestCase):
    def setUp(self):
        from app import webapp
        self.w = webapp
        self.app = make_app(admins="1")
        self.mid = add_movie(self.app, 10, "Avatar")
        self.u = {"id": 5, "first_name": "Ali"}
        self.v = {"id": 6, "first_name": "Vali"}
        self.admin = {"id": 1, "first_name": "Boss"}

    def tearDown(self):
        cleanup(self.app)

    def post(self, user, body, **kw):
        # tezlik cheklovi sinovga xalaqit bermasin
        self.app.db.x("UPDATE comments SET created_at=created_at-3600 WHERE user_id=?", (user["id"],))
        return self.w.api_comment_post(self.app, user, {"id": self.mid, "body": body, **kw})

    def test_post_and_list(self):
        r = self.post(self.u, "  Ajoyib kino!  ")
        self.assertTrue(r["ok"])
        self.assertEqual(r["item"]["body"], "Ajoyib kino!")
        self.assertTrue(r["item"]["mine"])
        lst = self.w.api_comments(self.app, self.v, {"id": self.mid})
        self.assertEqual(lst["total"], 1)
        self.assertFalse(lst["items"][0]["mine"])
        self.assertTrue(lst["can_post"])

    def test_guest_cannot_post_but_can_read(self):
        guest = {"id": 0, "first_name": ""}
        self.post(self.u, "Salom hammaga")
        self.assertEqual(self.w.api_comments(self.app, guest, {"id": self.mid})["total"], 1)
        self.assertFalse(self.w.api_comments(self.app, guest, {"id": self.mid})["can_post"])
        r = self.w.api_comment_post(self.app, guest, {"id": self.mid, "body": "salom"})
        self.assertEqual(r["reason"], "auth")

    def test_validation(self):
        for text, reason in [("a", "short"), ("x" * 601, "long"), ("mana https://spam.uz", "links"),
                             ("yozing @spamkanal", "links"), ("kiring site.com", "links"), ("a" * 12, "spam")]:
            self.assertEqual(self.post(self.u, text)["reason"], reason, text)
        self.assertTrue(self.post(self.u, "Yaxshi film, tavsiya qilaman")["ok"])
        self.assertEqual(self.post(self.u, "Yaxshi film, tavsiya qilaman")["reason"], "dup")

    def test_flood_and_hourly_limit(self):
        self.assertTrue(self.w.api_comment_post(self.app, self.u, {"id": self.mid, "body": "birinchi izoh"})["ok"])
        r = self.w.api_comment_post(self.app, self.u, {"id": self.mid, "body": "ikkinchi izoh"})
        self.assertEqual(r["reason"], "flood")
        for i in range(12):
            self.app.db.add_comment(self.mid, 6, f"izoh {i}")
        self.app.db.x("UPDATE comments SET created_at=created_at-100 WHERE user_id=6")      # 20 soniyadan eski, soatdan yangi
        self.assertEqual(self.w.api_comment_post(self.app, self.v, {"id": self.mid, "body": "yana bitta"})["reason"], "hour")

    def test_admin_may_post_links(self):
        self.assertTrue(self.w.api_comment_post(self.app, self.admin, {"id": self.mid, "body": "Kanalimiz: t.me/marvarid"})["ok"])

    def test_replies_one_level_like_and_delete(self):
        top = self.post(self.u, "Birinchi izoh")["item"]
        rep = self.post(self.v, "Javob yozdim", parent=top["id"])["item"]
        rep2 = self.post(self.u, "Javobga javob", parent=rep["id"])["item"]       # asosiy izoh ostiga tushadi
        lst = self.w.api_comments(self.app, self.u, {"id": self.mid})
        self.assertEqual(len(lst["items"]), 1)
        self.assertEqual([r["body"] for r in lst["items"][0]["replies"]], ["Javob yozdim", "Javobga javob"])
        self.assertEqual(self.w.api_comment_like(self.app, self.v, {"cid": top["id"]})["likes"], 1)
        self.assertEqual(self.w.api_comment_like(self.app, self.v, {"cid": top["id"]})["likes"], 0)
        self.assertEqual(self.w.api_comment_delete(self.app, self.v, {"cid": top["id"]})["reason"], "forbidden")
        self.assertTrue(self.w.api_comment_delete(self.app, self.u, {"cid": top["id"]})["ok"])    # o'ziniki — bo'ladi
        self.assertEqual(self.app.db.count_comments(self.mid), 0)                                # javoblari ham ketdi
        self.assertIsNotNone(rep2)

    def test_reports_hide_and_admin_moderation(self):
        top = self.post(self.u, "Yomon izoh")["item"]
        for uid in (11, 12, 13):
            self.w.api_comment_report(self.app, {"id": uid, "first_name": "x"}, {"cid": top["id"]})
        self.assertEqual(self.w.api_comments(self.app, self.v, {"id": self.mid})["total"], 0)       # yashirildi
        self.assertIn("Izoh yashirildi", " ".join(self.app.bot.texts(1)))                            # bosh adminga xabar
        self.app.db.restore_comment(top["id"])
        self.assertEqual(self.w.api_comments(self.app, self.v, {"id": self.mid})["total"], 1)
        r = self.w.api_comment_ban(self.app, self.admin, {"cid": top["id"]})
        self.assertTrue(r["banned"])
        self.assertEqual(self.post(self.u, "yana yozaman")["reason"], "banned")
        self.assertEqual(self.w.api_comment_ban(self.app, self.v, {"cid": top["id"]})["reason"], "forbidden")
        self.assertTrue(self.w.api_comment_delete(self.app, self.admin, {"cid": top["id"]})["ok"])  # admin hammasini o'chiradi

    def test_comments_removed_with_movie_and_music_excluded(self):
        self.post(self.u, "Salom hammaga")
        self.app.db.trash_movie(self.mid, 1)
        self.assertEqual(self.app.db.count_comments(self.mid), 0)
        song = add_movie(self.app, 11, "Qo'shiq", ftype="audio", cat="music")
        self.assertEqual(self.w.api_comment_post(self.app, self.u, {"id": song, "body": "yaxshi qo'shiq"})["reason"], "not_found")

    def test_xss_text_is_plain(self):
        r = self.post(self.u, "<img src=x onerror=alert(1)>")
        self.assertTrue(r["ok"])
        self.assertEqual(r["item"]["body"], "<img src=x onerror=alert(1)>")   # saqlanadi; mijoz textContent bilan chiqaradi

    def test_sort_top(self):
        a = self.post(self.u, "Birinchi izoh")["item"]
        self.post(self.v, "Ikkinchi izoh")
        self.w.api_comment_like(self.app, self.v, {"cid": a["id"]})
        top = self.w.api_comments(self.app, self.u, {"id": self.mid, "sort": "top"})["items"]
        self.assertEqual(top[0]["body"], "Birinchi izoh")
        new = self.w.api_comments(self.app, self.u, {"id": self.mid, "sort": "new"})["items"]
        self.assertEqual(new[0]["body"], "Ikkinchi izoh")


if __name__ == "__main__":
    unittest.main()
