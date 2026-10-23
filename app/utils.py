"""Yordamchi funksiyalar: formatlash, matnni normallashtirish, HTML."""

from __future__ import annotations

import difflib
import html
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

TZ = timezone(timedelta(hours=5))  # Toshkent vaqti (UTC+5)


# ───────────────────────── vaqt ─────────────────────────

def now() -> int:
    return int(time.time())


def fmt_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y")


def fmt_short_date(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m")


def fmt_datetime(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y %H:%M")


def day_start(ts: Optional[int] = None) -> int:
    d = datetime.fromtimestamp(ts if ts is not None else now(), TZ)
    return int(d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())


def fmt_duration(seconds: float) -> str:
    sec = int(seconds)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h} soat")
    if m:
        parts.append(f"{m} daq")
    if s or not parts:
        parts.append(f"{s} son")
    return " ".join(parts)


# ───────────────────────── raqamlar ─────────────────────────

def fmt_num(n) -> str:
    return f"{int(n or 0):,}".replace(",", " ")


def fmt_compact(n) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 10_000:
        return f"{n // 1000}K"
    if n >= 1_000:
        return f"{n / 1000:.1f}K".replace(".0K", "K")
    return str(n)


def fmt_card(digits: str) -> str:
    d = re.sub(r"\D", "", digits or "")
    return " ".join(d[i:i + 4] for i in range(0, len(d), 4))


def plan_name(days: int) -> str:
    days = int(days)
    if days % 365 == 0:
        return f"{days // 365} yil"
    if days % 30 == 0:
        return f"{days // 30} oy"
    if days % 7 == 0:
        return f"{days // 7} hafta"
    return f"{days} kun"


def progress_bar(done: int, total: int, width: int = 10) -> str:
    if total <= 0:
        return "▱" * width
    filled = min(width, int(round(width * done / total)))
    return "▰" * filled + "▱" * (width - filled)


# ───────────────────────── matn / HTML ─────────────────────────

def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=False)


def esc_attr(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


_TAG_RE = re.compile(r"<[^>]+>")


def visible_len(html_text: str) -> int:
    """Telegram hisoblaydigan uzunlik (teglar olib tashlangan, UTF-16 birliklarda)."""
    plain = html.unescape(_TAG_RE.sub("", html_text or ""))
    return len(plain.encode("utf-16-le")) // 2


def render(template: str, **values) -> str:
    """{name} kabi o'zgaruvchilarni almashtiradi (format() ishlatilmaydi — xavfsiz)."""
    out = template or ""
    for key, value in values.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def user_link(user_id: int, name: str) -> str:
    return f'<a href="tg://user?id={int(user_id)}">{esc(name or "Foydalanuvchi")}</a>'


def full_name(user: dict) -> str:
    name = " ".join(x for x in (user.get("first_name"), user.get("last_name")) if x)
    return name or "Foydalanuvchi"


# ── Telegram entities → HTML (admin yozgan formatlashni saqlash uchun) ──

def entities_to_html(text: str, entities: Optional[Sequence[dict]]) -> str:
    if not text:
        return ""
    if not entities:
        return esc(text)
    raw = text.encode("utf-16-le")
    ents = sorted(entities, key=lambda e: (e["offset"], -e["length"]))
    return "".join(_unparse(raw, ents, 0, len(raw)))


def _dec(raw: bytes) -> str:
    return raw.decode("utf-16-le", errors="ignore")


def _unparse(raw: bytes, ents: List[dict], start: int, end: int) -> List[str]:
    out: List[str] = []
    pos = start
    i = 0
    while i < len(ents):
        e = ents[i]
        e_start = e["offset"] * 2
        e_end = min(e_start + e["length"] * 2, end)
        if e_start < pos:
            i += 1
            continue
        if e_start >= end:
            break
        if e_start > pos:
            out.append(esc(_dec(raw[pos:e_start])))
        j = i + 1
        children = []
        while j < len(ents) and ents[j]["offset"] * 2 < e_end:
            children.append(ents[j])
            j += 1
        if e["type"] in ("code", "pre"):
            inner = esc(_dec(raw[e_start:e_end]))
        else:
            inner = "".join(_unparse(raw, children, e_start, e_end))
        out.append(_wrap(e, inner))
        pos = e_end
        i = j
    if pos < end:
        out.append(esc(_dec(raw[pos:end])))
    return out


def _wrap(e: dict, inner: str) -> str:
    t = e.get("type")
    simple = {
        "bold": "b", "italic": "i", "underline": "u", "strikethrough": "s",
        "spoiler": "tg-spoiler", "code": "code", "blockquote": "blockquote",
    }
    if t in simple:
        tag = simple[t]
        return f"<{tag}>{inner}</{tag}>"
    if t == "pre":
        lang = e.get("language")
        if lang:
            return f'<pre><code class="language-{esc_attr(lang)}">{inner}</code></pre>'
        return f"<pre>{inner}</pre>"
    if t == "expandable_blockquote":
        return f"<blockquote expandable>{inner}</blockquote>"
    if t == "text_link":
        return f'<a href="{esc_attr(e.get("url", ""))}">{inner}</a>'
    if t == "text_mention" and e.get("user"):
        return f'<a href="tg://user?id={int(e["user"]["id"])}">{inner}</a>'
    if t == "custom_emoji" and e.get("custom_emoji_id"):
        return f'<tg-emoji emoji-id="{esc_attr(e["custom_emoji_id"])}">{inner}</tg-emoji>'
    return inner


def message_html(msg: dict) -> str:
    """Xabar matni yoki izohini formatlash bilan HTML ko'rinishda qaytaradi."""
    if msg.get("text") is not None:
        return entities_to_html(msg.get("text", ""), msg.get("entities"))
    return entities_to_html(msg.get("caption", ""), msg.get("caption_entities"))


# ───────────────────────── qidiruv uchun normallashtirish ─────────────────────────

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h", "і": "i", "ї": "i", "є": "e",
    "ґ": "g",
}
_APOSTROPHES = "'`´‘’ʻʼ′ʹ"
_NON_WORD = re.compile(r"[\W_]+", re.UNICODE)


def normalize(text: str) -> str:
    """Kirill/lotin, katta/kichik harf va tutuq belgilaridan qat'i nazar solishtirish uchun."""
    s = (text or "").casefold()
    s = "".join(_CYR.get(ch, ch) for ch in s)
    for a in _APOSTROPHES:
        s = s.replace(a, "")
    s = _NON_WORD.sub(" ", s)
    return " ".join(s.split())


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def fuzzy_match(query: str, candidates: Iterable[Tuple[int, str]],
                limit: int = 30, threshold: float = 0.7) -> List[int]:
    """Imlo xatolari bilan yozilgan so'rovlar uchun o'xshash nomlarni topadi."""
    q = query.strip()
    if len(q) < 3:
        return []
    k = len(q.split())
    scored = []
    for item_id, title in candidates:
        if not title:
            continue
        words = title.split()
        windows = {title, title[: len(q) + 2]}
        for i in range(max(1, len(words) - k + 1)):
            windows.add(" ".join(words[i:i + k]))
        best = 0.0
        for w in windows:
            sm = difflib.SequenceMatcher(None, q, w)
            if sm.real_quick_ratio() < threshold or sm.quick_ratio() < threshold:
                continue
            best = max(best, sm.ratio())
        if best >= threshold:
            scored.append((best, item_id))
    scored.sort(key=lambda x: -x[0])
    return [i for _, i in scored[:limit]]


def extract_media(msg: Optional[dict], audio: bool = False) -> Optional[Tuple[str, str, str]]:
    """Xabardan faylni oladi: (file_id, 'video'|'document'|'audio', izoh).
    audio=True bo'lsa musiqa (audio) fayllari ham qabul qilinadi."""
    if not msg:
        return None
    if msg.get("video"):
        return msg["video"]["file_id"], "video", msg.get("caption") or ""
    if audio and msg.get("audio"):
        a = msg["audio"]
        caption = msg.get("caption") or " - ".join(x for x in (a.get("performer"), a.get("title")) if x)
        return a["file_id"], "audio", caption
    if msg.get("document"):
        return msg["document"]["file_id"], "document", msg.get("caption") or ""
    return None


# ───────────────────────── kanal havolalari ─────────────────────────

_TG_LINK = re.compile(r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/([A-Za-z][A-Za-z0-9_]{3,})/?")


def channel_ref(text: str) -> Optional[str]:
    """«https://t.me/kanal», «@kanal» yoki «-100123» → API uchun chat havolasi."""
    t = (text or "").strip()
    m = _TG_LINK.fullmatch(t)
    if m:
        return "@" + m.group(1)
    if re.fullmatch(r"@[A-Za-z][A-Za-z0-9_]{3,}", t):
        return t
    if re.fullmatch(r"-?\d{5,}", t):
        return t
    return None


def is_private_invite(text: str) -> bool:
    return bool(re.match(r"(?:https?://)?(?:t\.me|telegram\.me)/(?:\+|joinchat/)", (text or "").strip()))


def post_link(chat: dict, message_id: int) -> Optional[str]:
    if chat.get("username"):
        return f"https://t.me/{chat['username']}/{message_id}"
    cid = str(chat.get("id", ""))
    if cid.startswith("-100"):
        return f"https://t.me/c/{cid[4:]}/{message_id}"
    return None


# ───────────────────────── tugmalar matnini o'qish ─────────────────────────

_EMOJI_MARK = re.compile("\ue000(\\d+)\ue002(.*?)\ue001", re.S)


def _utf16_index(text: str, offset: int) -> int:
    """UTF-16 (Telegram) offsetini Python satr indeksiga o'giradi."""
    units = 0
    for i, ch in enumerate(text):
        if units >= offset:
            return i
        units += 2 if ord(ch) > 0xFFFF else 1
    return len(text)


def mark_custom_emoji(text: str, entities: Optional[Sequence[dict]]) -> str:
    """Premium (custom) emojilarni matnda belgilab qo'yadi — tugma ikonkasi qilish uchun."""
    ems = [e for e in (entities or []) if e.get("type") == "custom_emoji" and e.get("custom_emoji_id")]
    if not ems:
        return text or ""
    out = text
    for e in sorted(ems, key=lambda e: e["offset"], reverse=True):
        a = _utf16_index(out, e["offset"])
        b = _utf16_index(out, e["offset"] + e["length"])
        out = out[:a] + "\ue000" + str(e["custom_emoji_id"]) + "\ue002" + out[a:b] + "\ue001" + out[b:]
    return out


def count_custom_emoji(msg: Optional[dict]) -> int:
    ents = (msg or {}).get("entities") or (msg or {}).get("caption_entities") or []
    return sum(1 for e in ents if e.get("type") == "custom_emoji")


def parse_url_buttons(text: str, entities: Optional[Sequence[dict]] = None) -> Tuple[Optional[List[List[dict]]], str]:
    """«Matn - https://havola» qatorlaridan URL-tugmalar yasaydi. «|» — bir qatorda bir nechta.
    Tugma matnidagi premium emoji tugma ikonkasiga aylanadi (icon_custom_emoji_id)."""
    rows: List[List[dict]] = []
    text = mark_custom_emoji(text, entities)
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        row = []
        for chunk in line.split("|"):
            chunk = chunk.strip()
            m = re.match(r"^(.+?)\s+[-–—]\s+(\S+)$", chunk)
            if not m:
                return None, chunk
            label, url = m.group(1).strip(), m.group(2).strip()
            url = _EMOJI_MARK.sub(lambda x: x.group(2), url)
            icon = None
            found = _EMOJI_MARK.search(label)
            if found:
                icon = found.group(1)
                plain = _EMOJI_MARK.sub("", label).strip()
                label = plain or _EMOJI_MARK.sub(lambda x: x.group(2), label).strip()
            if url.startswith("@"):
                url = "https://t.me/" + url[1:]
            if not re.match(r"^(https?://|tg://)", url):
                url = "https://" + url
            button = {"text": label[:64], "url": url, "style": "success"}
            if icon:
                button["icon_custom_emoji_id"] = icon
            row.append(button)
        if row:
            rows.append(row[:8])
    if not rows:
        return None, text
    return rows[:10], ""
