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


class AddFlow(AdminCase):
    def video(self, caption="", w=1920, h=1080, name=""):
        m = message(1, "")
        m["message"].pop("text")
        m["message"]["video"] = {"file_id": "V1", "duration": 60, "width": w, "height": h, "file_name": name}
        if caption:
            m["message"]["caption"] = caption
        self.run_update(self.app, m)

    def buttons(self, uid=1):
        for n, a, k in reversed(self.app.bot.sent):
            kb = (k.get("reply_markup") if k else None) or next((x for x in a[2:] if isinstance(x, dict) and "inline_keyboard" in x), None)
            if isinstance(kb, dict) and "inline_keyboard" in kb:
                return [b.get("callback_data") for r in kb["inline_keyboard"] for b in r if b.get("callback_data")]
        return []

    def test_code_choice_from_caption_and_quality_autodetect(self):
        self.video("Avatar 2 1080p o'zbek tilida\nKod: 77")
        self.press(1, "am:cat:movie")
        txt = self.last(1)
        self.assertIn("Fayl izohida kod topildi: <b>77</b>", txt)
        btns = self.buttons()
        self.assertIn("am:capcode", btns)
        self.assertIn("am:auto", btns)
        self.assertIn("am:typecode", btns)
        self.press(1, "am:capcode")
        self.msg(1, "Avatar 2")
        self.assertIn("am:back", self.buttons())                      # har bir bosqichda «Orqaga» bor

    def test_quality_from_video_dimensions(self):
        from app import genres
        self.assertEqual(genres.detect_quality("", 1080), ["1080"])
        self.assertEqual(genres.detect_quality("film 720p va 1080p"), ["720", "1080"])
        self.assertEqual(genres.detect_quality("4K UHD"), ["4k"])
        self.assertIn("4k", genres.QUALITIES)
        self.assertIn("360", genres.QUALITIES)

    def test_back_returns_to_previous_step_and_keeps_data(self):
        self.video("kino 480p")
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Test kino")
        self.assertIn("janrini", self.last(1))
        self.press(1, "am:back")                                     # janrdan — nomga qaytadi
        self.assertIn("nomini", self.last(1))
        self.msg(1, "Yangi nom")
        self.press(1, "am:gok")
        self.press(1, "am:c:-")
        self.press(1, "am:back")                                     # yildan — davlatga
        self.assertIn("Davlatini", self.last(1))

    def test_full_flow_saves_site_link_and_skip(self):
        self.video("Matritsa 720p")
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Matritsa")
        for cb in ("am:gok", "am:c:-", "am:y:0", "am:l:-", "am:skip"):
            self.press(1, cb)
        self.assertIn("Saytdagi link", self.last(1))
        self.msg(1, "https://uzmovi.tv/kino/55")
        self.assertIn("poster", self.last(1).lower())
        self.press(1, "am:skip")                                     # poster o'tkazildi → tasdiq
        self.assertIn("Sayt linki", self.last(1))
        self.press(1, "am:save:0")
        m = self.app.db.get_movie_by_code(1)
        self.assertEqual(m["watch_url"], "https://uzmovi.tv/kino/55")
        self.assertEqual(m["quality"], ",720,")

    def sends(self):
        return sum(1 for n, a, k in self.app.bot.sent if n == "send_message" and a and a[0] == 1)

    def test_one_card_edited_in_place_and_catalogs_large(self):
        from app import genres
        self.assertEqual(len(genres.PICKER), 27)
        self.assertGreaterEqual(len(genres.COUNTRIES), 55)
        self.assertGreaterEqual(len(genres.LANGS), 12)
        self.video("Kino 1080p")
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Kartali kino")
        before = self.sends()
        for cb in ("am:gok", "am:c:-", "am:y:2020", "am:l:uz"):
            self.press(1, cb)
        self.assertEqual(self.sends(), before)                       # bosqichlar yangi xabar yubormaydi — bitta karta tahrirlanadi
        self.assertIn("Kartali kino", self.last(1))                  # tepada yig'ma ma'lumot
        self.assertIn("izoh", self.last(1))                          # sifat aniqlangan — qayta so'ralmadi, to'g'ri izohga o'tdi

    def test_marvel_dc_genres_fill_collections(self):
        from app import genres
        db = self.app.db
        mid = db.add_movie(5, "Temir odam", "", None, False, 1, "F", "video", "movie", genre_keys=["marvel", "action"])
        did = db.add_movie(6, "Betmen", "", None, False, 1, "F", "video", "movie", genre_keys=["dc"])
        titles = {c["title"]: c["n"] for c in db.list_collections()}
        self.assertEqual(titles["Marvel to'plami"], 1)
        self.assertEqual(titles["DC kolleksiyasi"], 1)
        db.update_movie(mid, genres=genres.dump(["action"]))                 # janr olindi — kolleksiyadan chiqdi
        self.assertEqual({c["title"]: c["n"] for c in db.list_collections()}["Marvel to'plami"], 0)
        self.assertEqual(genres.detect("Marvel: Final", ""), ["marvel"])
        self.assertIsNotNone(did)

    def test_year_range_typed(self):
        from app import genres
        self.assertEqual(genres.parse_years("2012-2015"), (2012, 2015))
        self.assertEqual(genres.parse_years("1994 – 99"), (1994, 1999))
        self.assertEqual(genres.parse_years("2015"), (2015, 0))
        self.assertEqual(genres.parse_years("2015-2012"), None)
        self.assertEqual(genres.year_text(2012, 2015), "2012–2015")
        self.video("Serial 720p")
        self.press(1, "am:cat:serial")
        self.press(1, "am:auto")
        self.msg(1, "Oraliqli serial")
        self.press(1, "am:gok")
        self.press(1, "am:c:-")
        self.msg(1, "2012-2015")
        self.assertIn("2012–2015", self.last(1))
        self.press(1, "am:l:-")
        for cb in ("am:skip", "am:lskip", "am:wskip", "am:skip", "am:save:0"):
            self.press(1, cb)
        m = self.app.db.get_movie_by_code(1)
        self.assertEqual((m["year"], m["year_end"]), (2012, 2015))
        from app import webapp
        item = webapp._item(self.app.db.catalog("serial", "new", None, 5)[0], False, True)
        self.assertEqual((item["year"], item["year_end"]), (2012, 2015))
        self.assertEqual(len(self.app.db.catalog("serial", "new", None, 5, year=2014)), 1)   # oraliq ichidagi yil bo'yicha ham topiladi

    def test_card_goes_below_poster(self):
        self.video("Kino 1080p")
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Posterli")
        for cb in ("am:gok", "am:c:-", "am:y:0", "am:l:-", "am:skip", "am:wskip"):
            self.press(1, cb)
        n = self.sends()
        m = message(1, "")
        m["message"].pop("text")
        m["message"]["photo"] = [{"file_id": "P1"}]
        self.run_update(self.app, m)
        self.assertEqual(self.sends(), n + 1)                        # tasdiq kartasi poster ostida yangi xabar bo'ldi
        self.assertIn("Hammasi tayyor", self.last(1))

    def test_quality_asked_once_only_when_not_detected(self):
        self.video("", w=0, h=0)
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Noma'lum sifat")
        for cb in ("am:gok", "am:c:-", "am:y:0", "am:l:-"):
            self.press(1, cb)
        self.assertIn("sifatini", self.last(1))                      # aniqlanmadi — bir marta so'raladi
        self.press(1, "am:q:720")
        self.press(1, "am:qok")
        self.assertIn("izoh", self.last(1))
        for cb in ("am:skip", "am:wskip", "am:skip"):
            self.press(1, cb)
        self.assertIn("am:eq", self.buttons())                       # tasdiqda o'zgartirish tugmasi bor
        self.press(1, "am:eq")
        self.press(1, "am:q:1080")
        self.press(1, "am:qok")
        self.assertIn("am:save:0", self.buttons())                   # tasdiqqa qaytdi
        self.press(1, "am:save:0")
        self.assertEqual(self.app.db.get_movie_by_code(1)["quality"], ",720,1080,")

    def test_country_pages(self):
        self.video("Kino 720p")
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Sahifali")
        self.press(1, "am:gok")
        self.assertIn("am:cp:1", self.buttons())
        self.press(1, "am:cp:2")
        self.assertIn("am:c:ng", self.buttons())
        self.press(1, "am:c:ng")
        self.press(1, "am:y:0")
        self.press(1, "am:l:tr")
        for cb in ("am:skip", "am:wskip", "am:skip", "am:save:0"):
            self.press(1, cb)
        m = self.app.db.get_movie_by_code(1)
        self.assertEqual((m["country"], m["lang"]), ("ng", "tr"))

    def test_site_link_optional(self):
        self.video("")
        self.press(1, "am:cat:movie")
        self.press(1, "am:auto")
        self.msg(1, "Kinochalar")
        for cb in ("am:gok", "am:c:-", "am:y:0", "am:l:-", "am:skip", "am:wskip", "am:skip"):
            self.press(1, cb)
        self.press(1, "am:save:0")
        self.assertEqual(self.app.db.get_movie_by_code(1)["watch_url"], "")
