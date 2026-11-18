"""💬 Izohlar: tekshiruv (spam, havola, takror), ro'yxat va amallar. Saytdagi kino oynasida va adminlar uchun botda ishlatiladi."""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional

log = logging.getLogger("comments")

MIN_LEN, MAX_LEN = 2, 600
GAP_SECONDS = 20            # ketma-ket ikki izoh orasidagi eng kam vaqt
PER_HOUR = 12               # soatiga eng ko'pi bilan
HIDE_AT = 3                 # shuncha shikoyatda izoh avtomatik yashiriladi
PAGE = 10

_LINK = re.compile(r"(https?://|www\.|t\.me/|telegram\.me/|@[A-Za-z0-9_]{4,}|\b[\w-]+\.(?:com|ru|uz|org|net|me|io|ly|xyz|info|site|top|click|link|tk)\b)", re.I)
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f‪-‮⁦-⁩]")   # boshqaruv va yo'nalish almashtiruvchi belgilar
_REPEAT = re.compile(r"(.)\1{9,}")                                                 # «aaaaaaaaaaa»

REASONS = {
    "auth": "Izoh qoldirish uchun saytni Telegram bot orqali oching.",
    "short": "Izoh juda qisqa.", "long": f"Izoh {MAX_LEN} belgidan oshmasin.",
    "links": "Izohda havola yoki @user bo'lmasin.", "flood": "Biroz kuting — izohlar orasida 20 soniya bo'lsin.",
    "hour": "Bir soatda juda ko'p izoh. Keyinroq yozing.", "dup": "Bu izoh allaqachon yozilgan.",
    "spam": "Izoh spam deb topildi.", "banned": "Siz izoh qoldirishdan cheklangansiz.", "not_found": "Kino topilmadi.",
}


def clean(text: str) -> str:
    text = _CTRL.sub("", str(text or "").replace("\r", ""))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def check(app, user: dict, movie_id: int, body: str, is_admin: bool) -> Optional[str]:
    """Sabab kodi (xato bo'lsa) yoki None (hammasi joyida)."""
    uid = user.get("id") or 0
    if not uid:
        return "auth"
    if app.db.is_contact_banned(uid):
        return "banned"
    if len(body) < MIN_LEN:
        return "short"
    if len(body) > MAX_LEN:
        return "long"
    if not is_admin:
        if _LINK.search(body):
            return "links"
        if _REPEAT.search(body):
            return "spam"
        load = app.db.user_comment_load(uid)
        import time
        if time.time() - (load["last"] or 0) < GAP_SECONDS:
            return "flood"
        if load["hour"] >= PER_HOUR:
            return "hour"
    if app.db.has_same_comment(uid, movie_id, body):
        return "dup"
    return None


def _badge(app, row) -> str:
    uid = row["user_id"]
    if app.is_admin(uid):
        return "admin"
    import time
    return "premium" if (row["premium_until"] or 0) > time.time() else ""


def item(app, row, viewer: int) -> Dict:
    return {"id": row["id"], "name": (row["first_name"] or "Foydalanuvchi")[:24], "body": row["body"], "ts": row["created_at"],
            "likes": row["likes"], "liked": bool(row["liked"]), "mine": bool(viewer) and row["user_id"] == viewer,
            "badge": _badge(app, row), "uid": row["user_id"] if app.is_admin(viewer) else 0}


def listing(app, movie_id: int, viewer: int, sort: str, offset: int) -> Dict:
    db = app.db
    rows = db.top_comments(movie_id, viewer, "top" if sort == "top" else "new", PAGE + 1, offset)
    more = len(rows) > PAGE
    rows = rows[:PAGE]
    replies: Dict[int, list] = {}
    for r in db.comment_replies([r["id"] for r in rows], viewer):
        replies.setdefault(r["parent_id"], []).append(item(app, r, viewer))
    out = []
    for r in rows:
        it = item(app, r, viewer)
        it["replies"] = replies.get(r["id"], [])
        out.append(it)
    return {"items": out, "more": more, "total": db.count_comments(movie_id)}
