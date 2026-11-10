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
    "adventure": ("🗺", "Sarguzasht",   ("sarguzasht", "priklyuchen", "adventure")),
    "comedy":    ("😂", "Komediya",     ("komediya", "komedi", "comedy", "kulgili", "yumor")),
    "drama":     ("🎭", "Drama",        ("drama", "dramatik")),
    "romance":   ("❤️", "Melodrama",    ("melodrama",)),
    "romantic":  ("💕", "Romantika",    ("romantika", "romantik", "romance", "muhabbat")),
    "fantasy":   ("🚀", "Fantastika",   ("fantastika", "fantastik", "scifi", "kosmik")),
    "magic":     ("🧙", "Fentezi",      ("fentezi", "fantasy", "sehrli")),
    "horror":    ("😱", "Qo'rqinchli",  ("qorqinchli", "horror", "uzhas", "ujas", "dahshatli", "vahimali")),
    "thriller":  ("🔪", "Triller",      ("triller", "thriller", "sirli")),
    "crime":     ("🕵️", "Detektiv",     ("detektiv",)),
    "criminal":  ("🔫", "Kriminal",     ("kriminal", "jinoyat", "crime")),
    "history":   ("🏛", "Tarixiy",      ("tarixiy", "istorich")),
    "biography": ("📖", "Biografik",    ("biografik", "biografiya", "biography")),
    "docu":      ("🎞", "Hujjatli",     ("hujjatli", "dokumental", "documentary")),
    "family":    ("👨‍👩‍👧", "Oilaviy",   ("oilaviy", "family", "semeyn")),
    "animation": ("🎨", "Animatsiya",   ("animatsiya", "animatsion", "animation")),
    "musical":   ("🎶", "Musiqiy",      ("musiqiy", "myuzikl", "musical")),
    "sport":     ("⚽", "Sport",        ("sport", "sportiv")),
    "war":       ("⚔️", "Harbiy",       ("harbiy", "urush", "voennyy", "vojna")),
    "zombie":    ("🧟", "Zombilar",     ("zombi", "zombilar", "zombie")),
    "superhero": ("🦸", "Super qahramonlar", ("superqahramon", "superqahramonlar", "superhero", "supergeroy")),
    "mafia":     ("🎩", "Mafia",        ("mafia", "mafiya", "gangster")),
    "ghost":     ("👻", "Ruhlar",       ("ruhlar", "ruh", "arvoh", "arvohlar")),
    "vampire":   ("🧛", "Vampirlar",    ("vampir", "vampirlar", "vampire")),
    "marvel":    ("🕷", "Marvel",       ("marvel", "marvell")),
    "dc":        ("🦇", "DC",           ("dc",)),
    # eski kinolar va TMDB uchun saqlanadi (tanlash ro'yxatida chiqmaydi)
    "anime":     ("🌸", "Anime",        ("anime",)),
    "indian":    ("🇮🇳", "Hind",         ("hind", "hindiston", "indiysk", "bollivud")),
    "turkish":   ("🇹🇷", "Turk",         ("turk", "turkiya", "turkcha", "turetsk")),
    "korean":    ("🇰🇷", "Koreys",       ("koreys", "koreya", "dorama", "korean")),
}

# admin kino qo'shayotganda ko'radigan janrlar tartibi
PICKER = [k for k in GENRES if k not in ("anime", "indian", "turkish", "korean")]

# qisqa kalit so'zlar faqat to'liq so'z bo'lsa mos keladi («turk» ≠ «turkum», «hind» ≠ «hindu...» emas)
# janr → avtomatik kolleksiya nomi (kino shu janrni olsa, kolleksiyaga o'zi qo'shiladi)
AUTO_COLLECTIONS = {"marvel": "Marvel to'plami", "dc": "DC kolleksiyasi"}
_EXACT = {"dc", "marvel", "hind", "turk", "anime", "drama", "sirli", "yumor", "urush", "ruh", "sport"}
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
    for key in PICKER:
        keys = GENRES[key][2]
        for kw in keys:
            if any((w == kw) if kw in _EXACT else w.startswith(kw) for w in words):
                found.append(key)
                break
    return found[:4]


_RANGE_RE = re.compile(r"^\s*(\d{4})\s*[-–—−/]\s*(\d{2}|\d{4})\s*$")


def parse_years(text: str):
    """«2015» → (2015, 0); «2012-2015» / «1994 – 99» → (2012, 2015). Yaroqsiz — None."""
    t = (text or "").strip()
    if re.fullmatch(r"\d{4}", t):
        y = int(t)
        return (y, 0) if YEAR_MIN <= y <= YEAR_MAX else None
    m = _RANGE_RE.match(t)
    if not m:
        return None
    a, b = int(m.group(1)), m.group(2)
    e = int(b) if len(b) == 4 else (a // 100) * 100 + int(b)
    if not (YEAR_MIN <= a <= YEAR_MAX and YEAR_MIN <= e <= YEAR_MAX) or e < a:
        return None
    return (a, e) if e != a else (a, 0)


def year_text(year, year_end=0) -> str:
    """2012, 2015 → «2012–2015»; faqat yil bo'lsa — «2012»."""
    y, e = int(year or 0), int(year_end or 0)
    if not y:
        return ""
    return f"{y}–{e}" if e and e > y else str(y)


def detect_year(*texts: str) -> int:
    m = _YEAR_RE.search(" ".join(t or "" for t in texts))
    return int(m.group(1)) if m else 0


def line(stored: Optional[str]) -> str:
    """«💥 Jangari • 😂 Komediya» — xabarlarda ko'rsatish uchun."""
    return " • ".join(label(k) for k in parse(stored))


# ───────── 🌍 davlat va 🗣 til ─────────

# kalit → (bayroq, nomi, izohdagi kalit so'zlar — so'z boshi bo'yicha)
def _flag(cc: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())


# (kalit — ISO kod, nomi, izohdagi kalit so'zlar). Mashhurlari oldinda.
_COUNTRY_LIST = [
    ("us", "AQSH", ("aqsh", "amerika", "usa", "ssha")), ("uz", "O'zbekiston", ("ozbekiston",)),
    ("kz", "Qozog'iston", ("qozogiston",)), ("kg", "Qirg'iziston", ("qirgiziston", "qirgizstan")),
    ("gb", "Buyuk Britaniya", ("britaniya", "angliya", "england")), ("fr", "Fransiya", ("fransiya", "frantsiya", "fransuz")),
    ("de", "Germaniya", ("germaniya", "nemis")), ("it", "Italiya", ("italiya",)), ("es", "Ispaniya", ("ispaniya",)),
    ("ru", "Rossiya", ("rossiya",)), ("tr", "Turkiya", ("turkiya",)), ("in", "Hindiston", ("hindiston",)),
    ("kr", "Janubiy Koreya", ("koreya",)), ("jp", "Yaponiya", ("yaponiya",)), ("cn", "Xitoy", ("xitoy",)),
    ("ca", "Kanada", ("kanada",)), ("au", "Avstraliya", ("avstraliya",)), ("ir", "Eron", ("eron",)),
    ("ua", "Ukraina", ("ukraina",)), ("br", "Braziliya", ("braziliya",)), ("mx", "Meksika", ("meksika",)),
    ("tj", "Tojikiston", ("tojikiston",)), ("tm", "Turkmaniston", ("turkmaniston",)), ("az", "Ozarbayjon", ("ozarbayjon", "ozerbayjon")),
    ("am", "Armaniston", ("armaniston",)), ("ge", "Gruziya", ("gruziya",)), ("by", "Belarus", ("belarus", "belorussiya")),
    ("pl", "Polsha", ("polsha",)), ("se", "Shvetsiya", ("shvetsiya",)), ("dk", "Daniya", ("daniya",)),
    ("no", "Norvegiya", ("norvegiya",)), ("fi", "Finlandiya", ("finlandiya",)), ("nl", "Niderlandiya", ("niderlandiya", "gollandiya")),
    ("be", "Belgiya", ("belgiya",)), ("ch", "Shveytsariya", ("shveytsariya",)), ("at", "Avstriya", ("avstriya",)),
    ("pt", "Portugaliya", ("portugaliya",)), ("gr", "Gretsiya", ("gretsiya",)), ("ie", "Irlandiya", ("irlandiya",)),
    ("cz", "Chexiya", ("chexiya",)), ("ro", "Ruminiya", ("ruminiya",)), ("hu", "Vengriya", ("vengriya",)),
    ("bg", "Bolgariya", ("bolgariya",)), ("rs", "Serbiya", ("serbiya",)), ("hr", "Xorvatiya", ("xorvatiya",)),
    ("il", "Isroil", ("isroil",)), ("eg", "Misr", ("misr",)), ("sa", "Saudiya Arabistoni", ("saudiya",)),
    ("ae", "BAA", ("baa", "emirliklar")), ("pk", "Pokiston", ("pokiston",)), ("th", "Tailand", ("tailand",)),
    ("id", "Indoneziya", ("indoneziya",)), ("ph", "Filippin", ("filippin",)), ("vn", "Vetnam", ("vetnam",)),
    ("my", "Malayziya", ("malayziya",)), ("hk", "Gonkong", ("gonkong",)), ("tw", "Tayvan", ("tayvan",)),
    ("nz", "Yangi Zelandiya", ("zelandiya",)), ("ar", "Argentina", ("argentina",)), ("co", "Kolumbiya", ("kolumbiya",)),
    ("cl", "Chili", ("chili",)), ("pe", "Peru", ("peru",)), ("za", "Janubiy Afrika", ("afrika",)), ("ng", "Nigeriya", ("nigeriya",)),
]
COUNTRIES = {k: (_flag(k), n, kw) for k, n, kw in _COUNTRY_LIST}

# kalit → (bayroq, nomi, izohdagi kalit so'zlar)
LANGS = {
    "uz": ("🇺🇿", "O'zbek tilida",  ("ozbek tilida", "ozbekcha", "uzbek")),
    "ru": ("🇷🇺", "Rus tilida",     ("rus tilida", "ruscha", "russkiy")),
    "en": ("🇬🇧", "Ingliz tilida",  ("ingliz tilida", "inglizcha", "english")),
    "tr": ("🇹🇷", "Turk tilida",    ("turk tilida", "turkcha tilida")),
    "ko": ("🇰🇷", "Koreys tilida",  ("koreys tilida", "koreyscha")),
    "hi": ("🇮🇳", "Hind tilida",    ("hind tilida", "hindcha")),
    "kk": ("🇰🇿", "Qozoq tilida",   ("qozoq tilida", "qozoqcha")),
    "tg": ("🇹🇯", "Tojik tilida",   ("tojik tilida", "tojikcha")),
    "es": ("🇪🇸", "Ispan tilida",   ("ispan tilida", "ispancha")),
    "fr": ("🇫🇷", "Fransuz tilida", ("fransuz tilida", "fransuzcha")),
    "de": ("🇩🇪", "Nemis tilida",   ("nemis tilida", "nemischa")),
    "ja": ("🇯🇵", "Yapon tilida",   ("yapon tilida", "yaponcha")),
    "zh": ("🇨🇳", "Xitoy tilida",   ("xitoy tilida", "xitoycha")),
    "ar": ("🇸🇦", "Arab tilida",    ("arab tilida", "arabcha")),
    "orig": ("🎬", "Original (subtitr)", ("subtitr", "subtitrli", "original")),
}

YEAR_MIN, YEAR_MAX = 1920, 2049

# 🎞 video sifati (bir nechtasi tanlanadi) — kalit → yozuv; tartib: pastdan yuqoriga
QUALITIES = {"360": "360p", "480": "480p", "720": "720p", "1080": "1080p", "2k": "2K", "4k": "4K"}

_Q_RE = re.compile(r"(?<![\d.])(?:(360|480|720|1080|1440|2160)\s*[pр]\b|(2k|4k|uhd)(?![a-z0-9]))", re.I)


def detect_quality(text: str = "", height: int = 0) -> list:
    """Fayl izohi/nomidan (360p, 720p, 1080p, 2K, 4K ...) yoki video balandligidan sifatni aniqlaydi (kalitlar ro'yxati)."""
    found = []
    for m in _Q_RE.finditer(text or ""):
        k = (m.group(1) or m.group(2) or "").lower()
        k = {"1440": "2k", "2160": "4k", "uhd": "4k"}.get(k, k)
        if k in QUALITIES and k not in found:
            found.append(k)
    if not found and height:
        h = int(height)
        found = ["4k" if h >= 2000 else "2k" if h >= 1300 else "1080" if h >= 1000 else "720" if h >= 700 else "480" if h >= 440 else "360"]
    return [k for k in QUALITIES if k in found]


def quality_text(stored: Optional[str]) -> str:
    """«,720,1080,» → «1080p va 720p» (yuqori sifat oldin)."""
    keys = [k for k in reversed(list(QUALITIES)) if f",{k}," in (stored or "")]
    names = [QUALITIES[k] for k in keys]
    if len(names) > 1:
        return ", ".join(names[:-1]) + " va " + names[-1]
    return names[0] if names else ""


def quality_dump(keys) -> str:
    keys = [k for k in QUALITIES if k in set(keys)]
    return ("," + ",".join(keys) + ",") if keys else ""


def quality_parse(stored: Optional[str]) -> list:
    return [k for k in QUALITIES if f",{k}," in (stored or "")]


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


def card_lines(movie, parts: int = 0) -> list:
    """Bot va kanal uchun ixcham, chiroyli ma'lumot: 2 qator (davlat · janrlar / til · sifat · qismlar)."""
    keys = movie.keys()
    a, b = [], []
    if "country" in keys and movie["country"] in COUNTRIES:
        a.append(country_label(movie["country"]))
    g = " · ".join(name(k) for k in parse(movie["genres"])[:3])
    if g:
        a.append("🎭 " + g)
    if "lang" in keys and movie["lang"] in LANGS:
        b.append("🗣 " + LANGS[movie["lang"]][1])
    q = quality_text(movie["quality"]) if "quality" in keys else ""
    if q:
        b.append("🎞 " + q.replace(", ", " · ").replace(" va ", " · "))
    if parts > 1:
        b.append(f"📺 {parts} qism")
    return [x for x in ("  ·  ".join(a), "  ·  ".join(b)) if x]


def title_year(movie) -> str:
    """« <i>(2015)</i>» — nomning yonida kichik yil (bo'lmasa bo'sh)."""
    keys = movie.keys()
    y = year_text(movie["year"], movie["year_end"] if "year_end" in keys else 0) if movie["year"] else ""
    return f"  <i>({y})</i>" if y else ""


def info_lines(movie) -> list:
    """Kino ma'lumotlari: davlat, yil, janr, til — xabar va e'lonlarda bir xil ko'rinishda."""
    keys = movie.keys()
    lines = []
    if "country" in keys and movie["country"] in COUNTRIES:
        lines.append(f"🌍 Davlati: {country_label(movie['country'])}")
    if movie["year"]:
        lines.append(f"📅 Yili: {year_text(movie['year'], movie['year_end'] if 'year_end' in keys else 0)}")
    g = ", ".join(name(k) for k in parse(movie["genres"]))
    if g:
        lines.append(f"🎭 Janri: {g}")
    if "lang" in keys and movie["lang"] in LANGS:
        lines.append(f"🗣 Tili: {LANGS[movie['lang']][1]}")
    q = quality_text(movie["quality"]) if "quality" in keys else ""
    if q:
        lines.append(f"🎞 Sifati: {q}")
    return lines
