"""🎭 Janrlar: ro'yxat, izohdan avtomatik aniqlash va saqlash formati.

Bazada janrlar «,action,comedy,» ko'rinishida saqlanadi — LIKE '%,action,%' bilan tez qidiriladi.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from .utils import normalize

# kalit → (belgi, nomi, izohdagi kalit so'zlar — normalize() qilingan ko'rinishda, so'z boshi bo'yicha)
GENRES = {
    "action":    ("💥", "Jangari",      ("jangari", "boyevik", "boevik", "ekshn", "action", "jangovar")),
    "comedy":    ("😂", "Komediya",     ("komediya", "komedi", "comedy", "kulgili", "yumor")),
    "drama":     ("🎭", "Drama",        ("drama", "dramatik")),
    "thriller":  ("🔪", "Triller",      ("triller", "thriller", "sirli")),
    "horror":    ("👻", "Qo'rqinchli",  ("qorqinchli", "horror", "uzhas", "ujas", "dahshatli", "vahimali")),
    "fantasy":   ("🚀", "Fantastika",   ("fantastika", "fantastik", "fantasy", "fentezi")),
    "adventure": ("🗺", "Sarguzasht",   ("sarguzasht", "priklyuchen", "adventure")),
    "romance":   ("❤️", "Melodrama",    ("melodrama", "romantik", "romance", "muhabbat")),
    "crime":     ("🕵️", "Detektiv",     ("detektiv", "kriminal", "jinoyat", "crime")),
    "history":   ("🏛", "Tarixiy",      ("tarixiy", "harbiy", "urush", "voennyy", "istorich", "biografik")),
    "family":    ("👨‍👩‍👧", "Oilaviy",   ("oilaviy", "family", "semeyn")),
    "anime":     ("🌸", "Anime",        ("anime",)),
    "indian":    ("🇮🇳", "Hind",         ("hind", "hindiston", "indiysk", "bollivud")),
    "turkish":   ("🇹🇷", "Turk",         ("turk", "turkiya", "turkcha", "turetsk")),
    "korean":    ("🇰🇷", "Koreys",       ("koreys", "koreya", "dorama", "korean")),
}

# qisqa kalit so'zlar faqat to'liq so'z bo'lsa mos keladi («turk» ≠ «turkum», «hind» ≠ «hindu...» emas)
_EXACT = {"hind", "turk", "anime", "drama", "sirli", "yumor", "urush"}
_YEAR_RE = re.compile(r"\b(19[2-9]\d|20[0-4]\d)\b")


def label(key: str) -> str:
    g = GENRES.get(key)
    return f"{g[0]} {g[1]}" if g else ""


def name(key: str) -> str:
    g = GENRES.get(key)
    return g[1] if g else ""


def parse(stored: Optional[str]) -> List[str]:
    return [k for k in (stored or "").split(",") if k in GENRES]


def dump(keys: Iterable[str]) -> str:
    keys = [k for k in GENRES if k in set(keys)]  # tartib doim bir xil
    return ("," + ",".join(keys) + ",") if keys else ""


def detect(*texts: str) -> List[str]:
    """Nom va izohdan janrlarni topadi (masalan «Janr: komediya, jangari» → comedy, action)."""
    words = normalize(" ".join(t or "" for t in texts)).split()
    found = []
    for key, (_, _, keys) in GENRES.items():
        for kw in keys:
            if any((w == kw) if kw in _EXACT else w.startswith(kw) for w in words):
                found.append(key)
                break
    return found[:4]


def detect_year(*texts: str) -> int:
    m = _YEAR_RE.search(" ".join(t or "" for t in texts))
    return int(m.group(1)) if m else 0


def line(stored: Optional[str]) -> str:
    """«💥 Jangari • 😂 Komediya» — xabarlarda ko'rsatish uchun."""
    return " • ".join(label(k) for k in parse(stored))


# ───────── 🌍 davlat va 🗣 til ─────────

# kalit → (bayroq, nomi, izohdagi kalit so'zlar — so'z boshi bo'yicha)
COUNTRIES = {
    "us": ("🇺🇸", "AQSH",            ("aqsh", "amerika", "usa", "ssha")),
    "gb": ("🇬🇧", "Buyuk Britaniya", ("britaniya", "angliya", "england")),
    "fr": ("🇫🇷", "Fransiya",        ("fransiya", "frantsiya", "fransuz")),
    "de": ("🇩🇪", "Germaniya",       ("germaniya", "nemis")),
    "it": ("🇮🇹", "Italiya",         ("italiya",)),
    "es": ("🇪🇸", "Ispaniya",        ("ispaniya",)),
    "ru": ("🇷🇺", "Rossiya",         ("rossiya",)),
    "tr": ("🇹🇷", "Turkiya",         ("turkiya",)),
    "in": ("🇮🇳", "Hindiston",       ("hindiston",)),
    "kr": ("🇰🇷", "Janubiy Koreya",  ("koreya",)),
    "jp": ("🇯🇵", "Yaponiya",        ("yaponiya",)),
    "cn": ("🇨🇳", "Xitoy",           ("xitoy",)),
    "uz": ("🇺🇿", "O'zbekiston",     ("ozbekiston",)),
    "kz": ("🇰🇿", "Qozog'iston",     ("qozogiston",)),
    "ca": ("🇨🇦", "Kanada",          ("kanada",)),
    "au": ("🇦🇺", "Avstraliya",      ("avstraliya",)),
    "ir": ("🇮🇷", "Eron",            ("eron",)),
    "ua": ("🇺🇦", "Ukraina",         ("ukraina",)),
    "br": ("🇧🇷", "Braziliya",       ("braziliya",)),
    "mx": ("🇲🇽", "Meksika",         ("meksika",)),
}

LANGS = {
    "uz": ("🇺🇿", "O'zbek tilida",  ("ozbek tilida", "ozbekcha", "uzbek")),
    "ru": ("🇷🇺", "Rus tilida",     ("rus tilida", "ruscha", "russkiy")),
    "en": ("🇬🇧", "Ingliz tilida",  ("ingliz tilida", "inglizcha", "english")),
}

YEAR_MIN, YEAR_MAX = 1920, 2049


def country_label(key: str) -> str:
    c = COUNTRIES.get(key or "")
    return f"{c[0]} {c[1]}" if c else ""


def lang_label(key: str) -> str:
    lg = LANGS.get(key or "")
    return f"{lg[0]} {lg[1]}" if lg else ""


def detect_country(*texts: str) -> str:
    words = normalize(" ".join(t or "" for t in texts)).split()
    for key, (_, _, keys) in COUNTRIES.items():
        if any(w.startswith(kw) for kw in keys for w in words):
            return key
    return ""


def detect_lang(*texts: str) -> str:
    text = " " + normalize(" ".join(t or "" for t in texts)) + " "
    for key, (_, _, keys) in LANGS.items():
        if any(f" {kw}" in text for kw in keys):
            return key
    return ""


def info_lines(movie) -> list:
    """Kino ma'lumotlari: davlat, yil, janr, til — xabar va e'lonlarda bir xil ko'rinishda."""
    keys = movie.keys()
    lines = []
    if "country" in keys and movie["country"] in COUNTRIES:
        lines.append(f"🌍 Davlati: {country_label(movie['country'])}")
    if movie["year"]:
        lines.append(f"📅 Yili: {movie['year']}")
    g = ", ".join(name(k) for k in parse(movie["genres"]))
    if g:
        lines.append(f"🎭 Janri: {g}")
    if "lang" in keys and movie["lang"] in LANGS:
        lines.append(f"🗣 Tili: {LANGS[movie['lang']][1]}")
    return lines
