"""🗂 Serial mavsumlari: baza qoidalari, adminda qism qo'shish, foydalanuvchi ko'rinishi, mavsum posteri."""
import json
import unittest

from tests.harness import add_movie, cleanup, make_app, message
from tests.test_admin import AdminCase


def S(db, mid):
    """[(mavsum, qism, part_no), …] — tartib bo'yicha."""
    return [(p["season"], p["ep_no"], p["part_no"]) for p in db.get_parts(mid)]


class SeasonDb(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.db = self.app.db
        self.mid = add_movie(self.app, 800, "Seriya", cat="serial")

    def tearDown(self):
        cleanup(self.app)

    def test_existing_behaviour_is_unchanged_for_one_season(self):
        self.assertEqual(self.db.add_part(self.mid, "F2", "video"), 2)
        self.assertEqual(self.db.add_part(self.mid, "F3", "video"), 3)
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (1, 3, 3)])          # ep_no == part_no
        self.assertEqual(self.db.count_seasons(self.mid), 1)

    def test_new_season_restarts_numbering_from_one(self):
        self.db.add_part(self.mid, "F2", "video")
        pid = self.db.add_part_id(self.mid, "G1", "video", 2)                               # 2-mavsum 1-qism
        self.db.add_part(self.mid, "G2", "video")                                           # keyingisi — oxirgi mavsumga
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (2, 1, 3), (2, 2, 4)])
        self.assertEqual(self.db.get_part(pid)["part_no"], 3)
        self.assertEqual(self.db.season_counts(self.mid), [(1, 2), (2, 2)])
        # mavjud mavsumdan keyingi-keyingisiga sakrab bo'lmaydi: 9 → faqat keyingi (3-mavsum)
        self.db.add_part_id(self.mid, "H1", "video", 9)
        self.assertEqual(self.db.season_counts(self.mid)[-1], (3, 1))

    def test_adding_into_middle_season_keeps_history(self):
        self.db.add_part(self.mid, "F2", "video")
        self.db.add_part_id(self.mid, "G1", "video", 2)
        g1 = self.db.get_part_by_no(self.mid, 3)
        self.db.upsert_user({"id": 50, "first_name": "T"})
        self.db.touch_history(50, self.mid, g1["id"])                                        # 2-mavsum 1-qismni ko'rgan
        self.db.add_part_id(self.mid, "F3", "video", 1)                                      # 1-mavsumga yangi qism
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (1, 3, 3), (2, 1, 4)])
        self.assertEqual(self.db.last_part(50, self.mid)["id"], g1["id"])                    # tarix part_id bo'yicha — buzilmadi
        self.assertEqual(self.db.last_part(50, self.mid)["part_no"], 4)                      # umumiy o'rni surildi

    def test_delete_renumbers_and_closes_empty_season(self):
        for f in ("F2", "F3"):
            self.db.add_part(self.mid, f, "video")
        only = self.db.add_part_id(self.mid, "G1", "video", 2)
        self.db.add_part_id(self.mid, "H1", "video", 3)
        self.db.set_season_poster(self.mid, 3, "P3")
        self.db.delete_part(only)                                                            # 2-mavsum butunlay bo'shadi
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (1, 3, 3), (2, 1, 4)])  # 3-mavsum → 2-mavsum
        self.assertEqual(self.db.season_poster(self.mid, 2), "P3")                           # poster ham ergashdi
        self.assertEqual(self.db.season_poster(self.mid, 3), "")
        mid2 = self.db.get_part_by_no(self.mid, 2)
        self.db.delete_part(mid2["id"])                                                      # o'rtadan o'chirish
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (2, 1, 3)])

    def test_move_part_stays_inside_season(self):
        self.db.add_part(self.mid, "F2", "video")
        self.db.add_part_id(self.mid, "G1", "video", 2)
        p2 = self.db.get_part_by_no(self.mid, 2)
        self.assertFalse(self.db.move_part(p2["id"], up=False))                              # mavsum chegarasidan o'tmaydi
        self.assertTrue(self.db.move_part(p2["id"], up=True))                                # 1-mavsum ichida yuqoriga
        self.assertEqual([p["file_id"] for p in self.db.get_parts(self.mid)], ["F2", "F800", "G1"])
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (2, 1, 3)])

    def test_regroup_validates_and_splits(self):
        for i in range(2, 9):
            self.db.add_part(self.mid, f"F{i}", "video")                                     # jami 8
        self.assertFalse(self.db.regroup(self.mid, [3, 3]))                                  # yig'indi 6 ≠ 8
        self.assertFalse(self.db.regroup(self.mid, [8, 0]))
        self.assertTrue(self.db.regroup(self.mid, [3, 3, 2]))
        self.assertEqual(self.db.season_counts(self.mid), [(1, 3), (2, 3), (3, 2)])
        self.assertEqual([p["ep_no"] for p in self.db.get_parts(self.mid)], [1, 2, 3, 1, 2, 3, 1, 2])
        self.assertEqual([p["part_no"] for p in self.db.get_parts(self.mid)], list(range(1, 9)))   # umumiy tartib o'zgarmadi
        self.db.set_season_poster(self.mid, 3, "P3")
        self.assertTrue(self.db.regroup(self.mid, [4, 4]))
        self.assertEqual(self.db.season_posters(self.mid), {})                               # bo'lmay qolgan mavsum posteri olib tashlandi

    def test_season_poster_set_clear_fallback(self):
        self.db.add_part_id(self.mid, "G1", "video", 2)
        self.assertEqual(self.db.season_poster(self.mid, 2), "")                             # yo'q → umumiy poster ishlatiladi
        self.db.set_season_poster(self.mid, 2, "SP2")
        self.db.set_season_poster(self.mid, 2, "SP2b")
        self.assertEqual(self.db.season_posters(self.mid), {2: "SP2b"})
        self.db.set_season_poster(self.mid, 2, "")
        self.assertEqual(self.db.season_posters(self.mid), {})

    def test_trash_restore_keeps_seasons_and_fixes_old_format(self):
        self.db.add_part(self.mid, "F2", "video")
        self.db.add_part_id(self.mid, "G1", "video", 2)
        tid = self.db.trash_movie(self.mid, 1)
        new = self.db.restore_trash(tid)
        self.assertEqual(S(self.db, new), [(1, 1, 1), (1, 2, 2), (2, 1, 3)])
        tid = self.db.trash_movie(new, 1)                                                    # eski (mavsumsiz) quti yozuvi
        row = self.db.get_trash(tid)
        parts = json.loads(row["parts"])
        for p in parts:
            p.pop("season", None); p.pop("ep_no", None)
        self.db.x("UPDATE trash SET parts=? WHERE id=?", (json.dumps(parts), tid))
        old = self.db.restore_trash(tid)
        self.assertEqual(S(self.db, old), [(1, 1, 1), (1, 2, 2), (1, 3, 3)])                 # hammasi 1-mavsum, raqamlar to'g'ri

    def test_migration_adds_columns_and_keeps_numbers(self):
        self.db.add_part(self.mid, "F2", "video")
        self.db.conn.execute("ALTER TABLE parts DROP COLUMN season")
        self.db.conn.execute("ALTER TABLE parts DROP COLUMN ep_no")
        self.db._migrate()                                                                   # eski baza ochilgandagidek
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2)])

    def test_site_fields(self):
        from app import webapp
        self.db.add_part(self.mid, "F2", "video")
        self.db.add_part_id(self.mid, "G1", "video", 2)
        item = webapp._item(self.db.catalog("serial", "new", None, 5)[0], False, True)
        self.assertEqual((item["parts"], item["seasons"]), (3, 2))
        self.db.upsert_user({"id": 60, "first_name": "R"})
        self.db.touch_history(60, self.mid, self.db.get_part_by_no(self.mid, 2)["id"])
        self.assertEqual(self.db.resume_parts(60, [self.mid]), {self.mid: "1-mavsum 2-qism"})
        r = webapp.api_resume(self.app, {"id": 60}, {"id": str(self.mid)})
        self.assertEqual(r["part"]["label"], "2-mavsum 1-qism")                              # keyingisi — yangi mavsum


class SeasonBot(AdminCase):
    def setUp(self):
        super().setUp()
        self.db = self.app.db
        self.mid = add_movie(self.app, 801, "Mavsumli", cat="serial")
        self.db.add_part(self.mid, "E2", "video")

    def buttons(self, uid=1):
        for n, a, k in reversed(self.app.bot.sent):
            kb = (k.get("reply_markup") if k else None) or next((x for x in a[2:] if isinstance(x, dict) and "inline_keyboard" in x), None)
            if isinstance(kb, dict) and "inline_keyboard" in kb:
                return [b.get("callback_data") for r in kb["inline_keyboard"] for b in r if b.get("callback_data")]
        return []

    def shown(self, chat):
        """Oxirgi ko'rsatilgan matn (rasm izohi ham)."""
        for n, a, k in reversed(self.app.bot.sent):
            if not a or a[0] != chat:
                continue
            if n in ("send_message", "edit_message_text") or n == "send_photo":
                idx = 2 if n in ("send_photo", "edit_message_text") else 1
                return str(a[idx]) if len(a) > idx else str(k.get("text", ""))
        return ""

    def part_video(self):
        m = message(1, "")
        m["message"].pop("text")
        m["message"]["video"] = {"file_id": "PV", "duration": 60, "width": 1920, "height": 1080, "file_name": "p.mp4"}
        self.run_update(self.app, m)

    def kb_texts(self, name="send_video"):
        for n, a, k in reversed(self.app.bot.sent):
            if n == name and len(a) > 3 and isinstance(a[3], dict):
                return [b["text"] for r in a[3]["inline_keyboard"] for b in r]
        return []

    def test_admin_adds_episodes_to_chosen_and_new_season(self):
        self.press(1, f"am:addpart:{self.mid}")
        self.assertIn("Qaysi mavsumga", self.last(1))
        self.assertIn(f"am:sea:{self.mid}:1", self.buttons())
        self.assertIn(f"am:sea:{self.mid}:2", self.buttons())                                # «➕ 2-mavsum (yangi)»
        self.press(1, f"am:sea:{self.mid}:1")
        self.part_video()
        self.assertEqual(S(self.db, self.mid), [(1, 1, 1), (1, 2, 2), (1, 3, 3)])            # bir mavsumda — eskicha
        self.press(1, f"am:ns:{self.mid}")
        self.assertIn("2-mavsum</b> boshlandi", self.last(1))
        self.part_video()
        self.part_video()
        self.assertEqual(S(self.db, self.mid)[3:], [(2, 1, 4), (2, 2, 5)])                   # 2-mavsum 1-qism, 2-qism
        self.press(1, "am:done")
        self.assertIn("2</b> mavsum", self.last(1))

    def test_new_season_cannot_start_twice_empty(self):
        self.press(1, f"am:addpart:{self.mid}")
        self.press(1, f"am:sea:{self.mid}:1")
        self.press(1, f"am:ns:{self.mid}")
        self.press(1, f"am:ns:{self.mid}")                                                   # qism yuborilmay yana bosildi
        self.part_video()
        self.assertEqual(self.db.season_counts(self.mid), [(1, 2), (2, 1)])                  # bo'sh mavsum paydo bo'lmadi

    def test_user_sees_seasons_then_episodes_with_season_poster(self):
        self.db.add_part_id(self.mid, "G1", "video", 2)
        self.db.add_part_id(self.mid, "G2", "video", 2)
        self.db.set_season_poster(self.mid, 2, "SP2")
        self.press(7, f"mv:{self.mid}")
        self.assertIn("Mavsumni tanlang", self.shown(7))
        b = self.buttons(7)
        self.assertIn(f"ps:{self.mid}:1:0", b)
        self.assertIn(f"ps:{self.mid}:2:0", b)
        n_before = len(self.app.bot.sent)
        self.press(7, f"ps:{self.mid}:2:0")                                                  # o'z posteri bor mavsum → rasm bilan
        photos = [x for x in self.app.bot.sent[n_before:] if x[0] == "send_photo"]
        self.assertTrue(photos and photos[-1][1][1] == "SP2")
        self.assertIn("2-mavsum", self.shown(7))
        g1 = self.db.get_season_parts(self.mid, 2)[0]
        self.assertIn(f"pt:{g1['id']}", self.buttons(7))
        n_before = len(self.app.bot.sent)
        self.press(7, f"ps:{self.mid}:1:0")                                                  # posteri yo'q mavsum → umumiy poster qoladi
        self.assertFalse([x for x in self.app.bot.sent[n_before:] if x[0] == "send_photo"])
        self.assertIn("1-mavsum", self.shown(7))

    def test_episode_navigation_crosses_season_with_full_label(self):
        self.db.add_part_id(self.mid, "G1", "video", 2)
        last1 = self.db.get_part_by_no(self.mid, 2)
        self.press(7, f"pt:{last1['id']}")
        texts = self.kb_texts()
        self.assertIn("2-mavsum 1-qism ➡️", texts)                                            # keyingisi — boshqa mavsum
        self.assertTrue(any("📋" in t for t in texts))
        sent_video = [x for x in self.app.bot.sent if x[0] == "send_video"][-1]
        self.assertIn("1-mavsum 2-qism", sent_video[1][2])                                    # izohda to'liq nom
        self.assertIn("/ 2", sent_video[1][2])                                                # mavsumdagi qismlar soni

    def test_admin_season_poster_and_regroup(self):
        for i in range(3, 7):
            self.db.add_part(self.mid, f"E{i}", "video")                                      # jami 6
        self.press(1, f"dm:open:{self.mid}")
        self.assertIn(f"dm:seas:{self.mid}", self.buttons())
        self.press(1, f"dm:rg:{self.mid}")
        self.msg(1, "2 2")                                                                    # yig'indi 4 ≠ 6
        self.assertIn("Tushunmadim", self.last(1))
        self.msg(1, "har 4")                                                                  # [4, 2]
        self.assertEqual(self.db.season_counts(self.mid), [(1, 4), (2, 2)])
        self.press(1, f"dm:sp:{self.mid}:2")
        m = message(1, "")
        m["message"].pop("text")
        m["message"]["photo"] = [{"file_id": "S", "width": 90, "height": 120}, {"file_id": "SP2", "width": 800, "height": 1200}]
        self.run_update(self.app, m)
        self.assertEqual(self.db.season_poster(self.mid, 2), "SP2")
        self.press(1, f"dm:spx:{self.mid}:2")
        self.assertEqual(self.db.season_poster(self.mid, 2), "")                              # olib tashlandi — umumiy poster
        self.press(1, f"dm:parts:{self.mid}")
        self.assertIn(f"dm:psea:{self.mid}:2", self.buttons())                                # ko'p mavsum: avval mavsum tanlanadi
        self.press(1, f"dm:psea:{self.mid}:2")
        p = self.db.get_season_parts(self.mid, 2)[0]
        self.assertIn(f"dm:pm:{p['id']}", self.buttons())

    def test_parse_regroup(self):
        from app.handlers.admin_movies import parse_regroup
        self.assertEqual(parse_regroup("12 12 8", 32), [12, 12, 8])
        self.assertEqual(parse_regroup("12,12,8", 32), [12, 12, 8])
        self.assertEqual(parse_regroup("har 12", 30), [12, 12, 6])
        self.assertEqual(parse_regroup("Har 10", 20), [10, 10])
        self.assertIsNone(parse_regroup("12 12", 30))
        self.assertIsNone(parse_regroup("har 0", 10))
        self.assertIsNone(parse_regroup("salom", 10))


if __name__ == "__main__":
    unittest.main()
