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

    def test_genre_collections_named_by_top_genre(self):
        from app import webapp
        db = self.app.db
        for i in range(4):
            db.add_movie(20 + i, f"Jang {i}", "", None, False, 1, "F", "video", "movie", genre_keys=["action"])
        db.add_movie(30, "Bitta", "", None, False, 1, "F", "video", "movie", genre_keys=["comedy"])
        cols = webapp.api_collections(self.app, {"id": 0})["items"]
        g = [c for c in cols if c["id"] == "g_action"]
        self.assertEqual(g[0]["title"], "Jangari")
        self.assertEqual(g[0]["n"], 4)
        self.assertFalse([c for c in cols if c["id"] == "g_comedy"])      # 3 tadan kam — chiqmaydi
        r = webapp.api_collection(self.app, {"id": 0}, {"id": "g_action"})
        self.assertEqual((r["title"], len(r["items"])), ("Jangari", 4))

    def test_start_welcome_stats_and_media(self):
        add_movie(self.app, 5, "Avatar")
        self.msg(1, "/start")
        self.assertIn("kino olamiga xush kelibsiz", self.last(1))
        self.assertLess(len(self.last(1)), 200)                            # qisqa va yoqimli
        self.msg(1, "/startmedia")                                         # admin GIF/rasm qo'yadi
        m = message(1, "")
        m["message"].pop("text")
        m["message"]["animation"] = {"file_id": "ANIM1"}
        self.run_update(self.app, m)
        self.assertEqual(self.app.setting("start_media"), "animation:ANIM1")
        sent = [(n, a) for n, a, k in self.app.bot.sent if n == "call" or n == "sendAnimation"]
        calls = [a[0] for n, a, k in self.app.bot.sent if n == "sendAnimation"]
        self.assertTrue(calls and calls[-1]["animation"] == "ANIM1" and "kino olamiga" in calls[-1]["caption"])
        self.assertIn("reply_markup", calls[-1])                           # pastki menyu media bilan birga
        self.msg(1, "/startmedia")
        self.press(1, "sm:off")
        self.assertEqual(self.app.setting("start_media"), "")

    def test_animation_command_needs_posters(self):
        self.msg(1, "/animatsiya")
        self.assertTrue("4 ta posterli" in self.last(1) or "o'rnatilmagan" in self.last(1))

    def test_follow_genres_notify_and_weekly(self):
        from app.handlers import follow
        db = self.app.db
        db.upsert_user({"id": 77, "first_name": "Sardor", "username": "sardor"})
        self.msg(77, "/kuzatish")
        self.assertIn("Yangi kinolardan xabardor", self.last(77))
        self.press(77, "fw:g:action")
        self.press(77, "fw:w")
        self.assertEqual(db.user_follows(77), {"action", "weekly"})
        mid = db.add_movie(40, "Jangari kino", "", "POSTER1", False, 1, "F", "video", "movie", genre_keys=["action"])
        follow._sent_today.clear()
        import threading
        follow.notify_followers(self.app, mid)
        for t in threading.enumerate():
            if t.name == "follow-notify":
                t.join(5)
        got = [a[0] for n, a, k in self.app.bot.sent if n == "sendPhoto" and a and isinstance(a[0], dict) and a[0].get("chat_id") == 77 and a[0].get("photo") == "POSTER1"]
        self.assertTrue(got and "Jangari kino" in got[0]["caption"])
        self.assertTrue(follow.send_weekly(self.app, 77))                  # haftalik tavsiya yuboriladi
        self.assertIn("Bu hafta siz uchun", self.last(77))
        self.press(77, "fw:woff")
        self.assertEqual(db.user_follows(77), {"action"})

    def test_backup_is_gzipped_local_copies_and_restorable(self):
        import gzip
        import os
        import tempfile
        from pathlib import Path
        from app.handlers import admin_panel
        db = self.app.db
        add_movie(self.app, 61, "Zaxira kino")
        tmp = Path(tempfile.mkdtemp()) / "b.db"
        db.backup_to(tmp)
        data = gzip.compress(tmp.read_bytes())
        self.assertLess(len(data), tmp.stat().st_size)                       # siqilgan
        out = Path(tempfile.mkdtemp()) / "x.db"
        out.write_bytes(gzip.decompress(data))
        self.assertGreaterEqual(admin_panel.inspect_db(out)[0], 1)           # ochilgach baza o'qiladi
        for i in range(9):
            admin_panel._keep_local(db, data + bytes([i]), keep=7)
        folder = db.path.parent / "backups"
        self.assertLessEqual(len(list(folder.glob("auto_*.db.gz"))), 7)      # eski nusxalar o'chiriladi
        self.msg(1, "/status")
        self.assertIn("zaxira", self.last(1).lower())

    def test_error_alert_to_owners_is_rate_limited(self):
        from app import core
        core._last_alert[0] = 0
        n0 = len([1 for n, a, k in self.app.bot.sent if n == "sendMessage"])
        try:
            raise ValueError("sinov <xato>")
        except ValueError:
            core._alert_owners(self.app, {"message": {"from": {"id": 1}}})
            core._alert_owners(self.app, {"message": {"from": {"id": 1}}})      # ikkinchisi — 15 daqiqa ichida, yuborilmaydi
        sent = [a[0] for n, a, k in self.app.bot.sent if n == "sendMessage" and a and isinstance(a[0], dict) and "kutilmagan xatolik" in str(a[0].get("text"))]
        self.assertEqual(len(sent), 1)
        self.assertIn("&lt;xato&gt;", sent[0]["text"])

    def test_missing_data_tool(self):
        db = self.app.db
        db.add_movie(80, "Bo'sh kino", "", None, False, 1, "F", "video", "movie", genre_keys=[], year=0, country="", lang="")
        db.add_movie(81, "To'liq kino", "Tavsif bor", "P", False, 1, "F", "video", "movie", genre_keys=["drama"], year=2020, country="us", lang="uz")
        c = db.missing_counts()
        self.assertGreaterEqual(c["poster"], 1)
        self.assertGreaterEqual(c["genre"], 1)
        self.msg(1, "🧰 Vositalar") if False else None
        from app.handlers import audit
        class C:  # kichik soxta ctx
            pass
        ctx = C(); ctx.db = db
        text, kb = audit.missing_view(ctx)
        self.assertIn("Posteri yo'q", text)
        text2, kb2 = audit.missing_list_view(ctx, "poster", 0)
        self.assertIn("Bo'sh kino", str(kb2))
        self.assertNotIn("To'liq kino", str(kb2))

    def test_phonetic_search_and_webp_and_reply_notice(self):
        from app.utils import normalize, phonetic
        from app.handlers.user import search_ids
        mid = add_movie(self.app, 90, "Titanik")
        ids, approx = search_ids(self.app, normalize("Титаник 2"), scope="video") if False else search_ids(self.app, normalize("Titanic"), scope="video")
        self.assertIn(mid, ids)                                              # Titanic ≈ Titanik
        ids2, _ = search_ids(self.app, normalize("Титаник"), scope="video")
        self.assertIn(mid, ids2)                                             # кирилл ≈ lotin
        self.assertEqual(phonetic(normalize("Джокер")), phonetic(normalize("Joker")))
        # javob bildirishnomasi: izoh egasiga bot xabar yuboradi
        from app import webapp
        self.app.db.upsert_user({"id": 51, "first_name": "Ali"})
        self.app.db.upsert_user({"id": 52, "first_name": "Vali"})
        top = webapp.api_comment_post(self.app, {"id": 51, "first_name": "Ali"}, {"id": mid, "body": "Zo'r kino ekan!"})["item"]
        self.app.db.x("UPDATE comments SET created_at=created_at-3600")
        webapp.api_comment_post(self.app, {"id": 52, "first_name": "Vali"}, {"id": mid, "body": "Rostdan ham zo'r", "parent": top["id"]})
        import threading
        for th in threading.enumerate():
            if th.name == "reply-notify":
                th.join(5)
        self.assertIn("izohingizga javob yozdi", " ".join(self.app.bot.texts(51)))

    def test_premium_trial_given_once_to_new_users(self):
        from app.handlers import trial
        db = self.app.db
        self.app.set_setting("trial_days", "3")
        self.app.set_setting("trial_since", "1")
        self.msg(201, "/start")                                              # yangi foydalanuvchi — sovg'a
        self.assertIn("bepul Premium", " ".join(self.app.bot.texts(201)))
        until = db.premium_until(201)
        self.assertGreater(until, 0)
        self.msg(201, "/start")                                              # ikkinchi marta — berilmaydi
        self.assertEqual(db.premium_until(201), until)
        self.app.set_setting("trial_days", "0")
        self.msg(202, "/start")
        self.assertEqual(db.premium_until(202), 0)                           # o'chiq — berilmaydi
        self.app.set_setting("trial_days", "3")
        db.x("UPDATE users SET joined_at=0 WHERE user_id=202")               # eski foydalanuvchi ham sinovni oladi (hali olmagan bo'lsa)
        self.msg(202, "/start")
        self.assertGreater(db.premium_until(202), 0)
        self.msg(1, "/sinov")
        self.assertIn("sinov muddati", self.last(1).lower())
        self.press(1, "tr:set:30")
        self.assertEqual(trial.trial_days(self.app), 30)                       # «1 oy»
        self.press(1, "tr:custom")
        self.msg(1, "14")
        self.assertEqual(trial.trial_days(self.app), 14)                       # admin o'zi yozgan muddat
        self.press(1, "tr:set:1")
        self.assertEqual(trial.trial_days(self.app), 1)

    def test_marvarid_tv_is_premium_only_with_free_trial_day(self):
        from app import tv, webapp
        tv._mem.clear()
        app, db = self.app, self.app.db
        app.set_setting("premium_enabled", "1")
        app.set_setting("trial_days", "1")
        for i in range(1, 8):
            m = add_movie(app, 970 + i, f"TV kino {i}")
            db.x("UPDATE movies SET duration=? WHERE id=?", ((90 + i * 7) * 60, m))
        db.upsert_user({"id": 401, "first_name": "T"})
        d = webapp.api_tv(app, {"id": 401})
        self.assertTrue(d["locked"])                                       # Premium'siz — yopiq
        self.assertEqual(d["trial_days"], 1)                               # lekin 1 kunlik sinov taklif qilinadi
        self.assertNotIn("slots", d)
        self.assertEqual(webapp.api_tv_trial(app, {"id": 0})["reason"], "login")
        r = webapp.api_tv_trial(app, {"id": 401})
        self.assertTrue(r["ok"] and r["days"] == 1)
        self.assertEqual(webapp.api_tv_trial(app, {"id": 401})["reason"], "used")   # faqat bir marta
        d = webapp.api_tv(app, {"id": 401})
        self.assertNotIn("locked", d)
        self.assertTrue(d["slots"] and d["cur"] >= 0)
        # jadval: ketma-ket, ustma-ust tushmaydi, bir xil kino ketma-ket kelmaydi, kun to'liq yopiladi
        t0 = tv.day_start(d["now"])
        sched = tv.schedule(app, t0)
        self.assertEqual(sched[0][1], t0)
        self.assertLessEqual(sched[-1][2], t0 + 86400)                     # kun oxirida tanaffus bo'lishi mumkin, lekin keyingi kunga o'tmaydi
        for a, b in zip(sched, sched[1:]):
            self.assertLessEqual(a[2], b[1])
            self.assertNotEqual(a[0], b[0])
        self.assertEqual(tv.schedule(app, t0), sched)                      # kun davomida o'zgarmaydi (saqlanadi)
        tv._mem.clear()
        self.assertEqual(tv.schedule(app, t0), sched)                      # qayta ishga tushgandan keyin ham bir xil
        # Premium o'chirilgan tizimda TV hammaga ochiq
        app.set_setting("premium_enabled", "0")
        db.upsert_user({"id": 402, "first_name": "U"})
        self.assertNotIn("locked", webapp.api_tv(app, {"id": 402}))

    def test_tv_live_channels_admin_and_api(self):
        from app import tv, webapp
        tv._mem.clear()
        app, db = self.app, self.app.db
        app.set_setting("premium_enabled", "0")
        add_movie(app, 995, "Efir kino")
        self.assertEqual(tv.parse_channel_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")[0], "youtube")
        self.assertIn("embed/dQw4w9WgXcQ", tv.parse_channel_url("https://youtu.be/dQw4w9WgXcQ")[1])
        self.assertIn("live_stream?channel=UCabcdefghijklmnopqrstuv", tv.parse_channel_url("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv")[1])
        self.assertEqual(tv.parse_channel_url("https://kanal.uz/live"), ("link", ""))      # tashqi havola
        self.assertIsNone(tv.parse_channel_url("javascript:alert(1)"))                      # xavfli sxema rad etiladi
        self.assertIsNone(tv.parse_channel_url("http://kanal.uz"))                          # faqat https
        self.msg(1, "/kanallar")
        self.assertIn("Hozircha kanal yo'q", self.last(1))
        self.press(1, "tvc:add")
        self.msg(1, "Milliy TV | https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertIn("qo'shildi", " ".join(self.app.bot.texts(1)))
        self.press(1, "tvc:add")
        self.msg(1, "noto'g'ri format")                                                    # yaroqsiz — qo'shilmaydi
        self.assertEqual(len(db.tv_channels()), 1)
        d = webapp.api_tv(app, {"id": 1})
        self.assertEqual([c["name"] for c in d["channels"]], ["Milliy TV"])
        self.assertEqual(d["channels"][0]["kind"], "youtube")
        self.press(1, f"tvc:del:{db.tv_channels()[0]['id']}")
        self.assertEqual(webapp.api_tv(app, {"id": 1})["channels"], [])

    def test_weekly_top5_post_and_toggle(self):
        from app.handlers import weekly
        app, db = self.app, self.app.db
        app.set_setting("post_channel", "-100777")
        for i in range(6):
            mid = add_movie(app, 800 + i, f"Haftalik kino {i}")
            for _ in range(6 - i):
                db.inc_views(mid, db.get_parts(mid)[0]["id"])
        self.msg(1, "/haftatop")
        self.assertIn("Haftaning TOP-5", self.last(1))
        self.press(1, "wk:tog")
        self.assertTrue(app.setting_bool("weekly_on"))
        self.press(1, "wk:now")
        posts = [a for nme, a, k in app.bot.sent if nme in ("send_photo", "send_message") and a and a[0] == "-100777"]
        self.assertTrue(posts)
        txt = str(posts[-1])
        self.assertIn("Haftalik kino 0", txt)
        self.assertNotIn("Haftalik kino 5", txt)                                     # faqat 5 ta
        self.press(1, "wk:test")
        self.assertTrue([1 for nme, a, k in app.bot.sent if nme in ("send_photo", "send_message") and a and a[0] == 1 and "TOP-5" in str(a)])

    def test_searcher_of_missing_movie_is_notified_when_added(self):
        app, db = self.app, self.app.db
        db.upsert_user({"id": 601, "first_name": "Q"})
        db.log_search(601, "Yashirin Qahramon", "yashirin qahramon", 0)          # topilmagan qidiruv (so'rov yubormagan)
        add_movie(app, 810, "Boshqa kino")
        self.assertNotIn("Qidirgan kinongiz", " ".join(app.bot.texts(601)))
        mid = add_movie(app, 811, "Yashirin Qahramon")
        from app.handlers.contact import notify_requesters
        notify_requesters(app, mid)
        self.assertIn("Qidirgan kinongiz qo'shildi", " ".join(app.bot.texts(601)))
        n = len(app.bot.texts(601))
        notify_requesters(app, mid)                                                  # ikkinchi marta yuborilmaydi
        self.assertEqual(len(app.bot.texts(601)), n)

    def test_premium_emoji_pairs_with_equals(self):
        from app.handlers.admin_emoji import parse_pairs
        t = "🥲=⭐ 😂＝⭐\n👨‍👩‍👧 = ⭐ ❤️=⭐ ⭐"
        ents, idx = [], 0
        for cid in "12345":
            idx = t.index("⭐", idx)
            ents.append({"type": "custom_emoji", "custom_emoji_id": cid, "offset": len(t[:idx].encode("utf-16-le")) // 2, "length": 1})
            idx += 1
        got = parse_pairs(t, ents)
        self.assertEqual(got["🥲"], "1")
        self.assertEqual(got["😂"], "2")
        self.assertEqual(got["👨‍👩‍👧"], "3")
        self.assertEqual(got["❤"], "4")
        self.assertEqual(got["⭐"], "5")                       # «=» yo'q — premium emojining o'z ko'rinishi (eski usul)

    def test_saved_sync_site_and_bot(self):
        from app import webapp
        app, db = self.app, self.app.db
        a, b2 = add_movie(app, 701, "Sevimli A"), add_movie(app, 702, "Sevimli B")
        db.upsert_user({"id": 801, "first_name": "S"})
        self.assertEqual(webapp.api_saved(app, {"id": 0})["reason"], "login")
        self.assertTrue(webapp.api_saved_set(app, {"id": 801}, {"id": a, "on": True})["on"])
        self.assertEqual(webapp.api_saved_set(app, {"id": 801}, {"ids": [b2, a, 99999]})["added"], 1)   # mavjud bo'lmagan kino o'tkazib yuboriladi
        self.assertEqual({x["id"] for x in webapp.api_saved(app, {"id": 801})["items"]}, {a, b2})
        self.assertFalse(webapp.api_saved_set(app, {"id": 801}, {"id": a, "on": False})["on"])
        self.assertEqual([x["id"] for x in webapp.api_saved(app, {"id": 801})["items"]], [b2])
        # botda: «🔖 Saqlash» tugmasi va /saqlangan ro'yxati — saytdagi bilan bir xil
        self.press(801, f"svt:{a}")
        self.assertTrue(db.is_saved(801, a))
        self.msg(801, "/saqlangan")
        out = self.last(801)
        self.assertIn("Sevimli A", out); self.assertIn("Sevimli B", out)
        self.press(801, f"svt:{a}")
        self.assertFalse(db.is_saved(801, a))

    def test_share_card_image_and_og_tag(self):
        from app import sharecard, seo, webapp
        if not sharecard.available():
            self.skipTest("Pillow yo'q")
        import io as _io
        from PIL import Image
        img = Image.new("RGB", (400, 600), (180, 40, 40)); buf = _io.BytesIO(); img.save(buf, "JPEG")
        data = sharecard.render(buf.getvalue(), "Sinov kinosi: juda uzun nom bilan ikki qatorga tushadi", "Kino · 2024 · AQSH", "Jangari · Drama", "8.1", 123)
        im = Image.open(_io.BytesIO(data))
        self.assertEqual(im.size, (1200, 630))
        self.assertEqual(sharecard.render(None, "Postersiz", "Kino", "", "", 0)[:2], b"\xff\xd8")   # postersiz ham ishlaydi
        mid = add_movie(self.app, 777, "OG kino")
        page = seo.movie_page(self.app, "https://site.test", 777, webapp._poster_key)
        self.assertIn(f"/og/{mid}.jpg", str(page))

    def test_site_resume_serial_part(self):
        from app import webapp
        app, db = self.app, self.app.db
        mid = add_movie(app, 720, "Uzun serial", cat="serial")
        for no in (2, 3):
            db.add_part(mid, f"FP{no}", "video")
        db.upsert_user({"id": 901, "first_name": "R"})
        self.assertIsNone(webapp.api_resume(app, {"id": 901}, {"id": str(mid)})["part"])      # hali ko'rmagan
        p2 = db.get_part_by_no(mid, 2)
        db.touch_history(901, mid, p2["id"])
        r = webapp.api_resume(app, {"id": 901}, {"id": str(mid)})
        self.assertEqual((r["last"], r["part"]["no"], r["total"], r["again"]), (2, 3, 3, False))   # 2-qism ko'rilgan → 3-qismdan davom
        res = webapp.api_watch(app, {"id": 901, "first_name": "R"}, {"id": mid, "part": r["part"]["id"]})
        self.assertTrue(res["ok"])
        sent = [a for nme, a, k in app.bot.sent if nme == "send_video" and a and a[0] == 901]
        self.assertTrue(sent and sent[-1][1] == "FP3")                                              # aynan 3-qism yuborildi

    def test_saved_reminder_flow(self):
        from app.handlers import remind
        app, db = self.app, self.app.db
        a, b2 = add_movie(app, 731, "Eslatma A"), add_movie(app, 732, "Eslatma B")
        db.upsert_user({"id": 911, "first_name": "E"})
        db.set_saved(911, a, True); db.set_saved(911, b2, True)
        self.assertEqual(remind.run_once(app), 0)                         # eslatma yoqilmagan — hech kimga yuborilmaydi
        self.press(911, "svr:1")                                          # botdan yoqish
        self.assertTrue(remind.enabled(db, 911))
        self.assertEqual(remind.run_once(app), 1)
        self.assertIn("Saqlagan kinongiz kutmoqda", " ".join(app.bot.texts(911)) + " ".join(
            str(a_[2]) for n_, a_, k_ in app.bot.sent if n_ == "send_photo" and a_ and a_[0] == 911))
        self.assertEqual(remind.run_once(app), 0)                         # 3 kun ichida takror yuborilmaydi
        db.x("UPDATE remind_log SET last_at=0 WHERE user_id=911")
        db.touch_history(911, a)                                          # A ko'rildi → faqat B qoldi
        self.assertEqual(db.unwatched_saved(911)["id"], b2)
        db.x("UPDATE remind_log SET last_at=0 WHERE user_id=911")
        db.touch_history(911, b2)                                         # hammasi ko'rilgan — eslatma yo'q
        self.assertEqual(remind.run_once(app), 0)
        from app import webapp
        self.assertTrue(webapp.api_saved(app, {"id": 911})["remind"])
        self.assertFalse(webapp.api_saved_set(app, {"id": 911}, {"remind": False})["remind"])
        self.assertFalse(remind.enabled(db, 911))
        self.assertEqual(webapp.api_saved_set(app, {"id": -5}, {"remind": True})["reason"], "no_telegram")

    def test_for_you_with_reasons_and_cold_start(self):
        from app import webapp
        app, db = self.app, self.app.db
        ids = []
        for i, g in enumerate((",drama,", ",drama,thriller,", ",comedy,", ",drama,", ",action,")):
            mid = add_movie(app, 740 + i, f"Tavsiya {i}")
            db.x("UPDATE movies SET genres=? WHERE id=?", (g, mid)); ids.append(mid)
        db.upsert_user({"id": 921, "first_name": "F"})
        cold = webapp.api_foryou(app, {"id": 921})
        self.assertFalse(cold["personal"])                                # tarix yo'q — ommabop kinolar
        self.assertTrue(cold["items"] and cold["items"][0]["why"] == "Hozir ommabop")
        db.touch_history(921, ids[0])                                     # drama ko'rdi
        db.set_saved(921, ids[3], True)                                   # yana drama saqladi
        r = webapp.api_foryou(app, {"id": 921})
        self.assertTrue(r["personal"])
        titles = [x["title"] for x in r["items"]]
        self.assertIn("Tavsiya 1", titles)                                # drama+triller — o'xshash, hali ko'rilmagan
        self.assertNotIn("Tavsiya 0", titles); self.assertNotIn("Tavsiya 3", titles)   # ko'rgan va saqlaganlari qaytarilmaydi
        self.assertIn("Drama", [x["why"] for x in r["items"]][0])
        self.assertEqual(webapp.api_foryou(app, {"id": 0})["guest"], True)

    def test_client_error_report_dedup_and_noise(self):
        from app import webapp
        app = self.app
        webapp._CLIENT_ERRS.clear(); webapp._err_notify[:] = [0.0, 0]
        owners = list(app.config.owners)
        app.bot.sent.clear()
        ua = "Mozilla/5.0 (Linux; Android 13) Chrome/120.0 Mobile Safari/537.36"
        body = {"m": "TypeError: x is undefined", "s": "https://site/assets/app.js", "l": 42, "v": "home", "ver": "abc123"}
        webapp.api_client_error(app, body, ua)
        webapp.api_client_error(app, body, ua)                            # bir xil xato — ikkinchi xabar yuborilmaydi
        msgs = [a for n, a, k in app.bot.sent if n == "sendMessage"]
        self.assertEqual(len(msgs), len(owners))
        self.assertIn("Saytda xatolik", str(msgs[0]))
        self.assertIn("Android", str(msgs[0]))
        webapp.api_client_error(app, {"m": "ResizeObserver loop limit exceeded", "s": "x", "l": 1}, ua)   # shovqin — e'tiborga olinmaydi
        webapp.api_client_error(app, {"m": "Failed to fetch", "s": "x", "l": 2}, ua)
        self.assertEqual(len([a for n, a, k in app.bot.sent if n == "sendMessage"]), len(owners))
        self.assertEqual(webapp._CLIENT_ERRS[next(iter(webapp._CLIENT_ERRS))][0], 2)
        self.msg(1, "/xatolar")
        self.assertIn("TypeError", self.last(1))

    def test_new_part_badge_for_followed_series(self):
        from app import webapp
        import time as _t
        app, db = self.app, self.app.db
        mid = add_movie(app, 750, "Yangilanuvchi serial", cat="serial")
        p1 = db.get_parts(mid)[0]
        db.upsert_user({"id": 931, "first_name": "N"})
        db.touch_history(931, mid, p1["id"])                               # 1-qismni ko'rdi
        self.assertEqual(db.fresh_parts(931), [])                         # hali yangi qism yo'q
        db.add_part(mid, "NEW2", "video"); db.add_part(mid, "NEW3", "video")
        db.x("UPDATE parts SET created_at=created_at+100 WHERE file_id IN ('NEW2','NEW3')")      # ko'rganidan KEYIN qo'shilgan
        fr = db.fresh_parts(931)
        self.assertEqual([(r["id"], r["newparts"]) for r in fr], [(mid, 2)])
        home = webapp.api_home(app, {"id": 931})
        self.assertEqual([(x["id"], x["newparts"]) for x in home["fresh"]], [(mid, 2)])
        pts = db.get_parts(mid)
        db.touch_history(931, mid, pts[-1]["id"])
        db.x("UPDATE history SET at=at+1000 WHERE user_id=931")           # yangi qismni ko'rdi — belgi o'chadi
        self.assertEqual(db.fresh_parts(931), [])

    def test_search_suggest_trending_and_seo_graph(self):
        from app import webapp, seo
        app, db = self.app, self.app.db
        a = add_movie(app, 760, "Titanik tez qidiruv")
        db.upsert_user({"id": 941, "first_name": "Q"})
        r = webapp.api_suggest(app, {"id": 941}, {"q": "titan"})
        self.assertTrue(any(x["id"] == a for x in r["items"]))
        self.assertEqual(webapp.api_suggest(app, {"id": 941}, {"q": "t"})["items"], [])    # 1 belgi — kutamiz
        self.assertEqual(webapp.api_suggest(app, {"id": 941}, {"q": "760"})["items"][0]["id"], a)   # kod bo'yicha
        t = webapp.api_suggest(app, {"id": 941}, {})
        self.assertIn("trending", t); self.assertIn("recent", t)
        # SEO: reyting (kamida 3 ovoz), non (breadcrumb), «tomosha qilish», sitemap rasmlari
        for u in (950, 951, 952):
            db.upsert_user({"id": u, "first_name": "V"}); db.rate(u, a, 1)
        page = seo.movie_page(app, "https://site.test", 760, webapp._poster_key)
        g = page["jsonld"]["@graph"]
        movie = g[0]
        self.assertEqual(movie["aggregateRating"]["ratingCount"], 3)
        self.assertEqual(movie["aggregateRating"]["ratingValue"], 5.0)
        self.assertEqual(g[1]["@type"], "BreadcrumbList")
        self.assertEqual(movie["potentialAction"]["@type"], "WatchAction")
        self.assertIn("max-image-preview:large", page["og"])
        seo._cache.clear()                                                # sitemap keshi boshqa testlarga aralashmasin
        xml = seo.sitemap(app, "https://site.test")
        seo._cache.clear()
        self.assertIn("image:image", xml); self.assertIn("<changefreq>", xml)
        home = seo.home_jsonld(app, "https://site.test")
        self.assertEqual(home["@graph"][0]["potentialAction"]["@type"], "SearchAction")

    def test_marvarid_tv_empty_and_deleted_movie(self):
        from app import tv, webapp
        tv._mem.clear()
        app, db = self.app, self.app.db
        app.set_setting("premium_enabled", "0")
        self.assertTrue(webapp.api_tv(app, {"id": 1}).get("empty"))        # kino yo'q — xato emas, bo'sh holat
        ids = [add_movie(app, 990 + i, f"Efir {i}") for i in range(3)]
        d = webapp.api_tv(app, {"id": 1})
        first = d["slots"][0]["it"]["id"]
        db.x("DELETE FROM movies WHERE id=?", (first,))                   # jadvaldagi kino o'chirildi — jadval o'zi qayta tuziladi
        tv._mem.clear()
        d2 = webapp.api_tv(app, {"id": 1})
        self.assertTrue(d2["slots"] and all(s["it"]["id"] != first for s in d2["slots"]))

    def test_request_votes(self):
        db = self.app.db
        db.upsert_user({"id": 301, "first_name": "A"})
        db.upsert_user({"id": 302, "first_name": "B"})
        db.add_request(301, "Gladiator 2")
        self.msg(302, "/sorovlar")
        self.assertIn("Gladiator 2", self.last(302))
        from app.handlers import contact
        text, kb = contact._vote_view(type("C", (), {"db": db, "user_id": 302})())
        cb = kb["inline_keyboard"][0][0]["callback_data"]
        self.press(302, cb)
        self.assertTrue(db.user_requested(302, "gladiator 2"))
        self.assertEqual(db.top_requests(5)[0]["n"], 2)                        # ovoz hisoblandi
        self.press(302, cb)                                                    # ikkinchi marta — qo'shilmaydi
        self.assertEqual(db.top_requests(5)[0]["n"], 2)

    def test_stars_subscription_flow(self):
        db = self.app.db
        db.upsert_user({"id": 401, "first_name": "Obuna"})
        db.add_plan(30, 10000, 50)
        plan = db.q1("SELECT * FROM plans WHERE days=30 AND is_active=1")
        self.assertIsNotNone(plan)
        self.app.bot.create_invoice_link = lambda *a, **k: "https://t.me/$sub123"
        self.press(401, f"pr:plan:{plan['id']}")
        self.assertIn(f"pr:sub:{plan['id']}", str(self.app.bot.sent[-1]))                  # obuna tugmasi bor
        self.press(401, f"pr:sub:{plan['id']}")
        self.assertIn("https://t.me/$sub123", str(self.app.bot.sent[-1]))                   # to'lov havolasi tugmada
        import copy
        def pay(charge, first, recurring=True):
            upd = message(401, "")
            upd["message"].pop("text")
            upd["message"]["successful_payment"] = {"currency": "XTR", "total_amount": plan["stars"], "invoice_payload": f"premsub:{plan['id']}:401",
                                                    "telegram_payment_charge_id": charge, "is_recurring": recurring, "is_first_recurring": first,
                                                    "subscription_expiration_date": 9999999999}
            self.run_update(self.app, upd)
        pay("C1", True)
        until1 = db.premium_until(401)
        self.assertGreater(until1, 0)
        pay("C2", False)                                                                    # keyingi oy — avtomatik yangilanish
        self.assertGreater(db.premium_until(401), until1)
        self.assertIn("avtomatik yangilandi", " ".join(self.app.bot.texts(401)))

    def test_contest_cancel_restart_and_reannounce(self):
        from app.handlers import contest
        self.app.set_setting("post_channel", "-100777")
        self.msg(1, "/musobaqa")
        self.press(1, "cn:tog")                                                    # boshlandi (xato sozlamalar bilan)
        self.assertTrue(contest.enabled(self.app))
        self.assertEqual(self.app.setting("contest_ann"), "-100777:7")             # e'lon xabari eslab qolindi
        self.press(1, "cn:cx")                                                     # bekor qilish — avval tasdiq so'raydi
        self.assertTrue(contest.enabled(self.app))
        self.assertIn("bekor qilasizmi", self.last(1))
        self.press(1, "cn:cxy")
        self.assertFalse(contest.enabled(self.app))
        dels = [a for nme, a, k in self.app.bot.sent if nme == "deleteMessage"]
        self.assertTrue(dels)                                                      # kanaldagi e'lon o'chirildi
        self.press(1, "cn:l:5")
        self.press(1, "cn:tog")                                                    # to'g'ri sozlamalar bilan qayta boshlash
        n_ann = len([1 for nme, a, k in self.app.bot.sent if nme == "send_message" and a and a[0] == "-100777"])
        self.press(1, "cn:ann")                                                    # qayta e'lon: eskisini o'chirib, yangisini yuboradi
        n_ann2 = len([1 for nme, a, k in self.app.bot.sent if nme == "send_message" and a and a[0] == "-100777"])
        self.assertEqual(n_ann2, n_ann + 1)
        self.press(1, "cn:rs")                                                     # eskisini bekor qilib, yangidan boshlash
        self.assertTrue(contest.enabled(self.app))
        start, end = contest.active_period(self.app)
        self.assertEqual(end - start, 5 * 86400)

    def _make_referrals(self, start, spec, base=600):
        db = self.app.db
        n = base
        for inviter, cnt in spec:
            db.upsert_user({"id": inviter, "first_name": f"U{inviter}"})
            for _ in range(cnt):
                n += 1
                db.upsert_user({"id": n, "first_name": "d"})
                db.x("UPDATE users SET ref_by=?, joined_at=? WHERE user_id=?", (inviter, start + 100, n))

    def test_bekorqilish_command(self):
        from app.handlers import contest
        self.app.set_setting("post_channel", "-100777")
        self.press(1, "cn:tog")
        self.assertTrue(contest.enabled(self.app))
        self.msg(1, "/bekorqilish")
        self.assertFalse(contest.enabled(self.app))
        self.assertIn("bekor qilindi", self.last(1))
        self.msg(1, "/bekorqilish")
        self.assertIn("Faol musobaqa yo'q", self.last(1))

    def test_contest_with_custom_days_prizes_announce_and_auto_finish(self):
        from app.handlers import contest
        db = self.app.db
        contest.save_prizes(self.app, [{"t": "p", "v": 30}, {"t": "m", "v": "50 000 so'm"}, {"t": "p", "v": 7}])
        self.app.set_setting("post_channel", "-100777")
        self.msg(1, "/musobaqa")
        self.press(1, "cn:l:3")                                                    # muddat — 3 kun
        self.assertEqual(contest.contest_len(self.app), 3)
        self.press(1, "cn:lc")
        self.msg(1, "2")                                                           # o'zi yozgan muddat — 2 kun
        self.assertEqual(contest.contest_len(self.app), 2)
        self.press(1, "cn:tog")                                                    # boshlash → kanalga e'lon
        ann = [a for nme, a, k in self.app.bot.sent if nme == "send_message" and a and a[0] == "-100777"]
        self.assertTrue(ann and "boshlandi" in str(ann[-1]) and "2 kun" in str(ann[-1]) and "50 000 so'm" in str(ann[-1]))
        start, end = contest.active_period(self.app)
        self.assertEqual(end - start, 2 * 86400)
        # vaqtni 2 kun oldinga suramiz: musobaqa «2 kun oldin boshlangan va hozir tugagan» bo'ladi
        shift = 2 * 86400 + 10
        self.app.set_setting("contest_start", str(start - shift))
        self.app.set_setting("contest_end", str(end - shift))
        start, end = start - shift, end - shift
        self._make_referrals(start, ((501, 5), (502, 4), (503, 3), (504, 2)))      # 504 — 3 tadan kam
        self.app.set_setting("contest_end", str(contest.now() + 3600))             # hali tugamagan — jadval ko'rinadi
        self.msg(501, "/reyting")
        self.assertIn("← siz", self.last(501))
        self.assertIn("Tugashiga", self.last(501))
        self.app.set_setting("contest_end", str(end))                              # muddat o'tdi — avtomatik yakunlanadi
        self.app.set_setting("contest_approve", "0")                               # bu testda tasdiqsiz mukofotlanadi
        won = contest.finish_contest(self.app, award=True)
        self.assertEqual([(o, u) for o, u, _, _ in won], [(1, 501), (2, 502), (3, 503)])
        self.assertFalse(contest.enabled(self.app))
        self.assertGreater(db.premium_until(501), 0)
        self.assertEqual(db.premium_until(502), 0)                                 # pul mukofoti
        self.assertGreater(db.premium_until(503), 0)
        self.assertEqual(db.premium_until(504), 0)
        post = [a for nme, a, k in self.app.bot.sent if nme == "send_message" and a and a[0] == "-100777" and "g'oliblari" in str(a)]
        self.assertTrue(post)                                                      # g'oliblar e'loni
        self.assertIn("PUL TO'LANADI", " ".join(self.app.bot.texts(1)))
        # /tekshir: tugagan musobaqa natijasi
        self.msg(504, "/tekshir")
        out = self.last(504)
        self.assertIn("g'olibda 5 ta, sizda 2 ta", out)
        self.msg(501, "/tekshir")
        self.assertIn("Tabriklaymiz, siz g'olibsiz", self.last(501))
        self.press(1, "cn:add")
        self.assertEqual(len(contest.prizes(self.app)), 4)                         # g'oliblar sonini admin belgilaydi

    def test_contest_winners_manual_approval(self):
        from app.handlers import contest
        db = self.app.db
        contest.save_prizes(self.app, [{"t": "p", "v": 30}, {"t": "p", "v": 7}])
        self.press(1, "cn:tog")
        start, end = contest.active_period(self.app)
        shift = 31 * 86400
        start, end = start - shift, end - shift
        self.app.set_setting("contest_start", str(start))
        self.app.set_setting("contest_end", str(end))
        self._make_referrals(start, ((501, 5), (502, 4), (503, 3)))
        self.assertEqual(contest.finish_contest(self.app, award=True), [])         # tasdiqsiz mukofot berilmaydi
        self.assertEqual(db.premium_until(501), 0)
        self.assertIn("tasdiqlang", " ".join(self.app.bot.texts(1)))
        self.press(1, "cn:px:501")                                                 # 501 shubhali — chiqariladi
        self.press(1, "cn:pok")
        self.assertEqual(db.premium_until(501), 0)                                 # chiqarilgan
        self.assertGreater(db.premium_until(502), 0)                               # 502 — 1-o'rin
        self.assertGreater(db.premium_until(503), 0)                               # zaxiradagi 503 — 2-o'rin
        self.assertEqual(contest._pending(self.app), None)

    def test_shortscheck_finds_and_removes_broken(self):
        from app.handlers import shortscheck
        from app.telegram import TelegramError
        mid = add_movie(self.app, 960, "Shortsli kino")
        good, bad = self.app.db.add_short(mid, "GOOD", "video"), self.app.db.add_short(mid, "BAD", "video")
        real = self.app.bot.call

        def fake(method, params=None, **k):
            if method == "getFile" and params["file_id"] == "BAD":
                raise TelegramError("getFile", 400, "Bad Request: file is too big")
            return {"file_path": "x", "file_size": 1000}
        self.app.bot.call = fake
        self.assertEqual([i for i, _, _ in shortscheck.check_shorts(self.app)], [bad])
        self.msg(1, "/shortstekshir")
        self.assertIn("1 ta shorts yuklanmaydi", " ".join(self.app.bot.texts(1)))
        self.press(1, "sc:del")
        self.assertEqual([r["id"] for r in self.app.db.movie_shorts(mid)], [good])
        self.app.bot.call = real

    def test_old_railway_host_redirects_to_custom_domain(self):
        from app import webapp
        self.app.config.webapp_url = "https://marvarid.uz"
        mv = lambda host, path: webapp._moved_to(self.app, host, path)
        self.assertEqual(mv("marvaridmedia-production.up.railway.app", "/kino/5"), "https://marvarid.uz")
        self.assertEqual(mv("marvaridmedia-production.up.railway.app", "/api/me"), "")      # API ga tegmaydi
        self.assertEqual(mv("marvaridmedia-production.up.railway.app", "/healthz"), "")
        self.assertEqual(mv("marvarid.uz", "/kino/5"), "")                                  # allaqachon yangi domen
        self.assertEqual(mv("127.0.0.1:8770", "/"), "")

    def test_trailer_link_bot_and_site(self):
        from app import webapp
        mid = add_movie(self.app, 950, "Treylerli kino")
        self.msg(1, "/start")
        self.press(1, f"dm:tu:{mid}")
        self.msg(1, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertEqual(self.app.db.get_movie(mid)["trailer_url"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        row = self.app.db.catalog("video", "new", None, 5, movie_id=mid)[0]
        self.assertEqual(webapp._item(row, False, True)["turl"], "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.msg(5, "950")                                                         # botda foydalanuvchiga «🎞 Treyler» tugmasi
        self.assertIn("Treyler", str(self.app.bot.sent[-1]))
        r = webapp.api_admin_save(self.app, {"id": 1, "first_name": "A"}, {"id": mid, "trailer_url": "not-a-link"})
        self.assertEqual(r.get("reason"), "turl")

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
