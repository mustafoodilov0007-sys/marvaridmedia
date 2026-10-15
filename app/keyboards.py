"""Rangli (premium) tugmalar va klaviaturalar.

Telegram tugma ranglari (style):
    primary — ko'k, success — yashil, danger — qizil.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from .texts import B

PRIMARY = "primary"   # ko'k
SUCCESS = "success"   # yashil
DANGER = "danger"     # qizil


def btn(text: str, data: Optional[str] = None, *, url: Optional[str] = None,
        style: Optional[str] = PRIMARY, copy: Optional[str] = None) -> dict:
    b = {"text": text}
    if data is not None:
        b["callback_data"] = data
    elif url is not None:
        b["url"] = url
    elif copy is not None:
        b["copy_text"] = {"text": copy[:256]}
    if style:
        b["style"] = style
    return b


def ikb(*rows) -> dict:
    return {"inline_keyboard": [list(r) for r in rows if r]}


def rbtn(text: str, style: Optional[str] = PRIMARY) -> dict:
    b = {"text": text}
    if style:
        b["style"] = style
    return b


def rkb(rows: Sequence[Sequence[dict]], placeholder: Optional[str] = None) -> dict:
    # is_persistent qo'yilmaydi: telefonda «orqaga» tugmasi menyuni yopa olsin,
    # qayta ochish — yozish maydonidagi ⌨️ belgisi orqali
    kb = {"keyboard": [list(r) for r in rows if r], "resize_keyboard": True}
    if placeholder:
        kb["input_field_placeholder"] = placeholder[:64]
    return kb


def cancel_kb(text: str = "❌ Bekor qilish") -> dict:
    return ikb([btn(text, "cancel", style=DANGER)])


def number_rows(items: Sequence[Tuple[int, str]], per_row: int = 5, style: str = PRIMARY) -> List[List[dict]]:
    rows: List[List[dict]] = []
    for i in range(0, len(items), per_row):
        rows.append([btn(str(num), data, style=style) for num, data in items[i:i + per_row]])
    return rows


def nav_row(prefix: str, page: int, pages: int) -> List[dict]:
    prev_page = (page - 1) % pages
    next_page = (page + 1) % pages
    return [
        btn("⬅️", f"{prefix}:{prev_page}", style=SUCCESS),
        btn(f"{page + 1}/{pages}", "noop", style=PRIMARY),
        btn("➡️", f"{prefix}:{next_page}", style=SUCCESS),
    ]


def user_menu(is_admin: bool, premium_on: bool) -> dict:
    rows = [
        [rbtn(B.SEARCH, PRIMARY)],
        [rbtn(B.TOP, DANGER), rbtn(B.NEW, SUCCESS)],
        [rbtn(B.RANDOM, PRIMARY), rbtn(B.PREMIUM, SUCCESS)] if premium_on else [rbtn(B.RANDOM, PRIMARY)],
        [rbtn(B.DONATE, DANGER), rbtn(B.CONTACT, PRIMARY)],
    ]
    if is_admin:
        rows.append([rbtn(B.ADMIN, DANGER)])
    return rkb(rows, "🔎 Kino kodi yoki nomini yozing...")


def admin_menu() -> dict:
    return rkb([
        [rbtn(B.ADD_MOVIE, SUCCESS), rbtn(B.DEL_MOVIE, DANGER)],
        [rbtn(B.STATS, PRIMARY), rbtn(B.CHANNELS, SUCCESS)],
        [rbtn(B.BROADCAST, DANGER), rbtn(B.ADMINS, PRIMARY)],
        [rbtn(B.PREMIUMS, SUCCESS), rbtn(B.TEXTS, DANGER)],
        [rbtn(B.HOME, PRIMARY)],
    ], "👨‍💻 Admin panel")
