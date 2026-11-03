"""Ochiq API va bazaning asosiy mantiqini tekshiradi."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
import db as D  # noqa: E402
from textutil import normalize  # noqa: E402


class Api(unittest.TestCase):
    def setUp(self):
        self.d = D.DB(Path(tempfile.mkdtemp()) / "t.db")
        self.tid = self.d.upsert_title({"src_id": 1, "code": 15, "title": "Avatar: Suv yo'li", "norm": normalize("Avatar: Suv yo'li"),
                                        "category": "movie", "year": 2022, "genres": [{"key": "action", "label": "Jangari"}]})

    def test_hidden_without_video(self):
        self.assertEqual(api.catalog(self.d, {"cat": "video"})["items"], [])

    def test_visible_with_video_and_search(self):
        self.d.x("INSERT INTO videos(title_id, part_no, key, status, created_at, duration) VALUES (?,?,?,?,?,?)",
                 (self.tid, 1, "k", "ready", D.now(), 8700))
        r = api.catalog(self.d, {"cat": "video"})
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["duration"], 8700)
        for q in ({"q": "avatar suv"}, {"q": "15"}, {"genre": "action"}, {"k": "15"}):
            self.assertEqual(len(api.catalog(self.d, q)["items"]), 1, q)
        self.assertEqual(len(api.catalog(self.d, {"genre": "drama"})["items"]), 0)

    def test_unpublished_hidden(self):
        self.d.x("INSERT INTO videos(title_id, part_no, key, status, created_at) VALUES (?,?,?,?,?)", (self.tid, 1, "k", "ready", D.now()))
        self.d.x("UPDATE titles SET published=0 WHERE id=?", (self.tid,))
        self.assertEqual(api.catalog(self.d, {})["items"], [])


if __name__ == "__main__":
    unittest.main()
