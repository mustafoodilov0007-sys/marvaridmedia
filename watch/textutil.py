"""Qidiruv uchun matnni tekislash (kirill/lotin, tutuq belgilari)."""

from __future__ import annotations

import re

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}
_APOS = "'`´‘’ʻʼ′ʹ"
_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)


def normalize(text: str) -> str:
    s = (text or "").casefold()
    s = "".join(_CYR.get(ch, ch) for ch in s)
    for a in _APOS:
        s = s.replace(a, "")
    return " ".join(_NON_WORD.sub(" ", s).split())


def like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
