"""Admin panel: xavfsizlik, jurnal, chiqindi qutisi, qismlar, kod, e'lon, xabar yuborish, murojaatlar."""

import time
import unittest

from tests.harness import add_movie, cleanup, make_app, message, press


class AdminCase(unittest.TestCase):
    admins = "1"        # 1 — bosh admin (.env); 2 — oddiy admin (bazadan qo'shilgan)

    def setUp(self):
        self.app = make_app(admins=self.admins)
        from app.core import process_update
        self.run_update = process_update
        self.app.db.add_admin(2, 1)
        self.app.invalidate_admins()
        self.app.bot.emoji_map = {}
        for u in (1, 2, 7):
            self.msg(u, "/start")

    def tearDown(self):
        cleanup(self.app)

    def msg(self, uid, text):
        self.run_update(self.app, message(uid, text))

    def press(self, uid, data):
        self.run_update(self.app, press(uid, data))

    def last(self, chat):
        t = self.app.bot.texts(chat)
        return t[-1] if t else ""

    def all(self, chat):
        return " ".join(self.app.bot.texts(chat))


class CaptionParsing(unittest.TestCase):
    def test_hashtags_are_not_codes(self):
        from app.handlers.admin_movies import parse_caption
        self.assertIsNone(parse_caption("Avatar 2\n#2024 #kino")[0])      # yil
        self.assertIsNone(parse_caption("Avatar 2 #1080")[0])             # sifat
        self.assertEqual(parse_caption("Avatar\n#45")[0], 45)             # haqiqiy kod
        self.assertEqual(parse_caption("Kod: 55\nAvatar")[0], 55)
        self.assertIsNone(parse_caption("Kod: 99999999")[0])              # juda katta
        code, title, _ = parse_caption("#kino #film\nTitanik 1997")
        self.assertEqual(title, "Titanik 1997")                           # xeshteg qatori nom emas


class Premium(AdminCase):
    def test_unknown_id_rejected_and_no_ghost_user(self):
        n = self.app.db.count_users()
        self.press(1, "pa:give")
        self.msg(1, "999999999 30")
        self.assertIn("botda yo'q", self.last(1))
        self.assertEqual(self.app.db.count_users(), n)
        self.assertEqual(self.app.db.count_premium(), 0)

    def test_regular_admin_limited_and_owner_notified(self):
        self.press(2, "pa:give")
        self.msg(2, "7 1000")
        self.assertIn("faqat bosh adminlar", self.last(2))
        self.assertEqual(self.app.db.count_premium(), 0)
        self.press(2, "pa:give")
        self.msg(2, "7 30")
        self.assertEqual(self.app.db.count_premium(), 1)
        self.assertIn("Premium berdi", self.all(1))                       # bosh adminga xabar bordi
        self.assertEqual(self.app.db.recent_actions(1)[0]["action"], "premium_give")

    def test_plan_delete_needs_confirmation(self):
        self.app.db.add_plan(30, 10000, 50)
        pid = self.app.db.list_plans()[0]["id"]
        self.press(1, f"pa:pdel:{pid}")
        self.assertEqual(len(self.app.db.list_plans()), 1)
        self.press(1, f"pa:pdelok:{pid}")
        self.assertEqual(len(self.app.db.list_plans()), 0)


class Stats(AdminCase):
    def test_provider_revenue_in_stats(self):
        self.app.db.create_payment(7, "premium", "provider", "approved", days=30, amount=25000, currency="UZS")
        self.msg(1, "📊 Statistika")
        text = self.last(1)
        self.assertIn("Click/Payme", text)
        self.assertIn("25 000", text.replace(" ", " "))


class Trash(AdminCase):
    def test_delete_goes_to_trash_and_restores(self):
        mid = add_movie(self.app, 60, "Transformerlar")
        self.app.db.add_part(mid, "F2", "video")
        self.press(1, f"dm:delok:{mid}")
        self.assertIsNone(self.app.db.get_movie(mid))
        tid = self.app.db.list_trash()[0]["id"]
        self.press(1, f"tl:trr:{tid}")
        m = self.app.db.get_movie_by_code(60)
        self.assertIsNotNone(m)
        self.assertEqual(self.app.db.count_parts(m["id"]), 2)
        self.assertEqual(self.app.db.list_trash(), [])

    def test_restore_when_code_taken_gets_new_code(self):
        mid = add_movie(self.app, 60, "Eski")
        self.app.db.trash_movie(mid, 1)
        add_movie(self.app, 60, "Yangi")
        new_id = self.app.db.restore_trash(self.app.db.list_trash()[0]["id"])
        self.assertNotEqual(self.app.db.get_movie(new_id)["code"], 60)


class Parts(AdminCase):
    def test_reorder_rename_and_code_change(self):
        mid = add_movie(self.app, 60, "Serial X")
        self.app.db.add_part(mid, "F2", "video")
        first = self.app.db.get_parts(mid)[0]
        self.press(1, f"dm:pdn:{first['id']}")
        self.assertEqual([p["file_id"] for p in self.app.db.get_parts(mid)], ["F2", "F60"])
        self.press(1, f"dm:pn:{first['id']}")
        self.msg(1, "Boshlanish")
        self.assertEqual(self.app.db.get_part(first["id"])["title"], "Boshlanish")
        other = add_movie(self.app, 61, "Boshqa")
        self.press(1, f"dm:cd:{mid}")
        self.msg(1, "61")                                               # band
        self.assertEqual(self.app.db.get_movie(mid)["code"], 60)
        self.assertIn("band", self.last(1))
        self.msg(1, "88")
        self.assertEqual(self.app.db.get_movie(mid)["code"], 88)
        self.assertIsNotNone(other)

    def test_duplicate_title_warning(self):
        add_movie(self.app, 60, "Avatar")
        self.press(1, "am:cat:movie")
        self.msg(1, "70")
        m = message(1, "")
        m["message"].pop("text")
        m["message"]["video"] = {"file_id": "V", "duration": 5}
        self.run_update(self.app, m)
        self.msg(1, "Avatar")
        self.assertIn("allaqachon bor", self.last(1))
        self.msg(1, "Avatar")                                           # ikkinchi marta — qabul
        self.assertIn("janr", self.last(1))


class Announce(AdminCase):
    def test_second_announce_asks_confirmation(self):
        self.app.set_setting("post_channel", "-100500")
        mid = add_movie(self.app, 60, "Avatar")
        self.press(1, f"an:{mid}")
        self.assertEqual(len(self.app.db.get_announces(mid)), 1)
        posts = sum(1 for n, *_ in self.app.bot.sent if n in ("send_photo", "send_message") and _[0][0] == "-100500")
        self.press(1, f"an:{mid}")
        self.assertIn("allaqachon kanalga", self.last(1))
        posts2 = sum(1 for n, *_ in self.app.bot.sent if n in ("send_photo", "send_message") and _[0][0] == "-100500")
        self.assertEqual(posts, posts2)
        self.press(1, f"an:f:{mid}")
        self.assertEqual(len(self.app.db.get_announces(mid)), 2)


class Broadcast(AdminCase):
    def test_interrupted_broadcast_resumes_without_repeats(self):
        db = self.app.db
        bid = db.create_broadcast(1, 1, "copy", "all", 1, 55, [])
        ids = db.user_ids("all")
        db.update_broadcast(bid, total=len(ids), done=1, ok=1, last_uid=ids[0], status="interrupted")
        self.press(1, f"bc:resume:{bid}")
        for _ in range(50):
            if db.get_broadcast(bid)["status"] == "done":
                break
            time.sleep(0.1)
        row = db.get_broadcast(bid)
        self.assertEqual(row["status"], "done")
        sent_to = [a[0] for n, a, k in self.app.bot.sent if n == "copy_message"]
        self.assertNotIn(ids[0], sent_to)                               # birinchisiga qayta yuborilmadi
        self.assertEqual(len(sent_to), len(ids) - 1)

    def test_active_audience_counts_recent_only(self):
        db = self.app.db
        db.x("UPDATE users SET last_active=? WHERE user_id=7", (int(time.time()) - 90 * 86400,))
        self.assertEqual(db.count_audience("active"), db.count_audience("all") - 1)


class Tickets(AdminCase):
    def test_reply_marks_done_and_blocks_duplicates(self):
        self.msg(7, "/murojaat")
        self.msg(7, "Salom, savolim bor")
        t = self.app.db.q1("SELECT * FROM tickets ORDER BY id DESC LIMIT 1")
        self.assertEqual(t["status"], "open")
        self.assertEqual(len(self.app.db.ticket_msgs(t["id"])), 2)       # ikkala adminga
        self.press(1, f"rep:7:{t['id']}")
        self.msg(1, "Javob")
        self.assertEqual(self.app.db.get_ticket(t["id"])["status"], "done")
        before = len(self.app.bot.sent)
        self.press(2, f"rep:7:{t['id']}")                                # ikkinchi admin: allaqachon javob berilgan
        self.assertFalse(any(n == "send_message" for n, *_ in self.app.bot.sent[before:]))

    def test_banned_user_cannot_contact(self):
        self.app.db.set_contact_banned(7, True)
        self.msg(7, "/murojaat")
        self.assertIn("cheklangan", self.last(7))

    def test_requests_view_groups_by_title(self):
        for u in (7, 8, 9):
            self.app.db.upsert_user({"id": u, "first_name": "x"})
            self.app.db.add_request(u, "Avatar 3")
        self.press(1, "tl:rq")
        self.assertIn("3 kishi", self.last(1))


class Channels(AdminCase):
    def test_admin_check_is_cached(self):
        from app.handlers import admin_channels as ch
        self.app.db.add_channel("-100500", "Kanal", "https://t.me/kanal", "public")
        ch._ADMIN_CACHE.clear()
        calls = []
        orig = self.app.bot.get_chat_member
        self.app.bot.get_chat_member = lambda *a: (calls.append(a), orig(*a))[1]
        self.msg(1, "/admin")
        self.msg(1, "/admin")
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
