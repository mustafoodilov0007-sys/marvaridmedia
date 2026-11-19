"""🌐 TMDB (va ixtiyoriy OMDb) dan kino ma'lumotini topish: yil, janr, davlat, davomiylik, yosh cheklovi, IMDb reyting,
aktyorlar, kadrlar, byudjet/kassa va YouTube treyleri.

Kinolar o'zbekcha nom bilan saqlanadi, shuning uchun qidiruv asl (inglizcha) nom bilan qilinadi va admin to'g'ri variantni tanlaydi —
ma'lumot hech qachon o'zi, so'rovsiz o'zgarmaydi.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

log = logging.getLogger("tmdb")

TMDB_BASE = "https://api.themoviedb.org/3"
OMDB_BASE = "https://www.omdbapi.com/"
OMDB_TIMEOUT = 4        # IMDb bali ixtiyoriy — sekin bo'lsa butun to'ldirishni 12 soniyaga kutdirmaymiz
IMG = "https://image.tmdb.org/t/p/"

# TMDB janr identifikatorlari → bizning janr kalitlari
GENRE_MAP = {
    28: "action", 10759: "action",
    10752: "war", 37: "action", 16: "animation",
    12: "adventure",
    35: "comedy",
    18: "drama", 10766: "drama",
    53: "thriller", 9648: "crime",
    27: "horror",
    14: "magic", 878: "fantasy", 10765: "fantasy",
    99: "docu", 10402: "musical", 10770: "drama",
    10749: "romance",
    80: "criminal",
    36: "history", 10768: "history",
    10751: "family", 10762: "family",
}
def _country_map():
    from . import genres as _G
    return {k.upper(): k for k in _G.COUNTRIES}


COUNTRY_MAP = _country_map()
AGE_MAP = {"G": 0, "PG": 6, "PG-13": 12, "R": 16, "NC-17": 18,
           "TV-Y": 0, "TV-Y7": 6, "TV-G": 0, "TV-PG": 6, "TV-14": 16, "TV-MA": 18}


class TmdbError(Exception):
    code = 0        # HTTP kodi (bo'lsa): 401/403 — kalit noto'g'ri yoki faollashtirilmagan


_IMG_PATH = re.compile(r"^/[A-Za-z0-9_-]{5,60}\.(?:jpg|jpeg|png|webp)$")
_YT_KEY = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
MAX_CAST, MAX_STILLS = 40, 16


def img_path(p) -> str:
    """TMDB rasm yo'li («/abc.jpg») faqat shu ko'rinishda qabul qilinadi — boshqa manzil saqlanmaydi."""
    p = p if isinstance(p, str) else ""
    return p if _IMG_PATH.match(p) else ""


def build_extra(d: dict, kind: str) -> dict:
    """Aktyorlar (rasm + rol), kadrlar, byudjet va kassa. Bo'sh bo'lsa — {}."""
    cast = []
    for c in ((d.get("credits") or {}).get("cast") or [])[:MAX_CAST]:
        name = (c.get("name") or "").strip()
        if name:
            cast.append({"n": name[:80], "r": (c.get("character") or "").strip()[:80], "p": img_path(c.get("profile_path"))})
    backs = [b for b in ((d.get("images") or {}).get("backdrops") or []) if img_path(b.get("file_path"))]
    # matnsiz (til belgilanmagan) kadrlar oldinga, keyin eng yuqori baholilari
    backs.sort(key=lambda b: (b.get("iso_639_1") is not None, -(b.get("vote_average") or 0)))
    stills = [b["file_path"] for b in backs[:MAX_STILLS]]
    out: dict = {}
    if cast:
        out["cast"] = cast
    if stills:
        out["stills"] = stills
    if kind == "movie":
        for k in ("budget", "revenue"):
            v = int(d.get(k) or 0)
            if v > 0:
                out[k] = v
    return out


def pick_trailer(d: dict) -> str:
    """Eng yaxshi YouTube treyleri (rasmiy, ruscha/inglizcha, yangiroq) — to'liq havola yoki ''."""
    vids = [v for v in ((d.get("videos") or {}).get("results") or [])
            if v.get("site") == "YouTube" and v.get("type") == "Trailer" and _YT_KEY.match(v.get("key") or "")]
    if not vids:
        return ""
    vids.sort(key=lambda v: v.get("published_at") or "", reverse=True)
    vids.sort(key=lambda v: ({"uz": 0, "ru": 1, "en": 2}.get(v.get("iso_639_1"), 3), not v.get("official")))
    return "https://www.youtube.com/watch?v=" + vids[0]["key"]


class Tmdb:
    def __init__(self, key: str, lang: str = "uz-UZ,en-US", omdb_key: str = "", base: str = TMDB_BASE, omdb_base: str = OMDB_BASE):
        # 🇺🇿 TMDB_LANG — vergul bilan til zanjiri: «uz-UZ,en-US». Birinchisi asosiy, qolganlari — izoh topilmasa zaxira.
        self.langs = [x.strip() for x in (lang or "").split(",") if x.strip()] or ["uz-UZ"]
        if "en-US" not in self.langs:
            self.langs.append("en-US")        # oxirgi zaxira doim inglizcha
        self.key, self.lang, self.omdb_key = key.strip(), self.langs[0], omdb_key.strip()
        self.base, self.omdb_base = base.rstrip("/"), omdb_base
        self._cache: Dict[str, tuple] = {}

    @property
    def configured(self) -> bool:
        return bool(self.key)

    # ───── tarmoq ─────
    def _fetch(self, url: str, headers: Optional[dict] = None, ttl: int = 600, timeout: int = 12) -> dict:
        hit = self._cache.get(url)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "MarvaridMedia/1.0", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err = TmdbError("API kalit noto'g'ri" if e.code in (401, 403) else f"TMDB xatosi ({e.code})")
            err.code = e.code
            raise err from None
        except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
            raise TmdbError(f"TMDB bilan aloqa yo'q: {e}") from None
        if len(self._cache) > 300:
            self._cache.clear()
        self._cache[url] = (time.time(), data)
        return data

    def _tmdb(self, path: str, **params) -> dict:
        headers = {}
        if self.key.startswith("eyJ"):      # v4 "Read Access Token"
            headers["Authorization"] = "Bearer " + self.key
        else:
            params["api_key"] = self.key
        return self._fetch(f"{self.base}{path}?{urllib.parse.urlencode(params)}", headers)

    # ───── qidiruv ─────
    def search(self, query: str, year: Optional[int] = None) -> List[dict]:
        q = (query or "").strip()
        if not q:
            return []
        d = self._tmdb("/search/multi", query=q, language="en-US", include_adult="false")
        out = []
        for r in d.get("results", []):
            kind = r.get("media_type")
            if kind not in ("movie", "tv"):
                continue
            date = r.get("release_date") or r.get("first_air_date") or ""
            y = int(date[:4]) if date[:4].isdigit() else 0
            out.append({"id": r["id"], "kind": kind, "title": r.get("title") or r.get("name") or "", "original": r.get("original_title") or r.get("original_name") or "",
                        "year": y, "poster": (IMG + "w154" + r["poster_path"]) if r.get("poster_path") else "",
                        "overview": (r.get("overview") or "")[:160], "popularity": r.get("popularity", 0)})
        if year:    # yil ko'rsatilgan bo'lsa — mos kelganlar oldinga
            out.sort(key=lambda x: (abs(x["year"] - year) if x["year"] else 99, -x["popularity"]))
        return out[:8]

    # ───── to'liq ma'lumot ─────
    def details(self, kind: str, tid: int) -> dict:
        if kind not in ("movie", "tv"):
            raise TmdbError("noto'g'ri tur")
        extra = ("external_ids,release_dates" if kind == "movie" else "external_ids,content_ratings") + ",credits,images,videos"
        d = self._tmdb(f"/{kind}/{int(tid)}", language=self.lang, append_to_response=extra,
                       include_image_language="en,null", include_video_language="uz,ru,en,null")
        overview = d.get("overview") or ""
        for alt in self.langs[1:]:       # o'zbekcha izoh yo'q — zanjirdagi keyingi til (standart: inglizcha)
            if overview:
                break
            try:
                overview = self._tmdb(f"/{kind}/{int(tid)}", language=alt).get("overview") or ""
            except TmdbError:
                continue
        date = d.get("release_date") or d.get("first_air_date") or ""
        gids = [g["id"] for g in d.get("genres", [])]
        countries = [c.get("iso_3166_1") for c in d.get("production_countries", [])] or d.get("origin_country") or []
        country = next((COUNTRY_MAP[c] for c in countries if c in COUNTRY_MAP), "")
        genres_out: List[str] = []
        for gid in gids:
            k = GENRE_MAP.get(gid)
            if k and k not in genres_out:
                genres_out.append(k)
        lang = d.get("original_language") or ""
        if 16 in gids and lang == "ja":
            genres_out.append("anime")
        if countries and countries[0] == "IN" or lang in ("hi", "ta", "te"):
            genres_out.append("indian")
        elif "TR" in countries or lang == "tr":
            genres_out.append("turkish")
        elif "KR" in countries or lang == "ko":
            genres_out.append("korean")
        runtime = d.get("runtime") or next(iter(d.get("episode_run_time") or []), 0) or (d.get("last_episode_to_air") or {}).get("runtime") or 0
        category = "serial" if kind == "tv" else ("cartoon" if 16 in gids and lang != "ja" else "movie")
        imdb_id = (d.get("external_ids") or {}).get("imdb_id") or d.get("imdb_id") or ""
        imdb, imdb_note = self.imdb_lookup(imdb_id)
        return {"tmdb_id": d["id"], "kind": kind, "title": d.get("title") or d.get("name") or "",
                "original": d.get("original_title") or d.get("original_name") or "", "year": int(date[:4]) if date[:4].isdigit() else 0,
                "genres": genres_out, "country": country, "duration_min": int(runtime or 0), "age": self._age(d, kind),
                "imdb": imdb, "imdb_note": imdb_note, "imdb_id": imdb_id, "overview": overview.strip(), "category": category,
                "poster": (IMG + "w342" + d["poster_path"]) if d.get("poster_path") else "",
                "poster_path": img_path(d.get("poster_path")),
                "extra": build_extra(d, kind), "trailer": pick_trailer(d)}

    @staticmethod
    def _age(d: dict, kind: str) -> int:
        try:
            if kind == "movie":
                res = (d.get("release_dates") or {}).get("results", [])
                for region in sorted(res, key=lambda r: r.get("iso_3166_1") != "US"):
                    for rel in region.get("release_dates", []):
                        c = (rel.get("certification") or "").strip()
                        if c in AGE_MAP:
                            return AGE_MAP[c]
            else:
                res = (d.get("content_ratings") or {}).get("results", [])
                for region in sorted(res, key=lambda r: r.get("iso_3166_1") != "US"):
                    c = (region.get("rating") or "").strip()
                    if c in AGE_MAP:
                        return AGE_MAP[c]
        except (TypeError, AttributeError):
            pass
        return 0

    def imdb_lookup(self, imdb_id: str) -> tuple:
        """(baho, sabab): baho «7.9» yoki ''. Sabab: '' (topildi), no_key, no_id, bad_key, none, error."""
        if not self.omdb_key:
            return "", "no_key"
        if not imdb_id:
            return "", "no_id"
        try:
            d = self._fetch(f"{self.omdb_base}?{urllib.parse.urlencode({'i': imdb_id, 'apikey': self.omdb_key})}", ttl=3600, timeout=OMDB_TIMEOUT)
        except TmdbError as e:
            return "", ("bad_key" if e.code in (401, 403) else "error")
        if str(d.get("Response")).lower() == "false":
            return "", ("bad_key" if "api key" in str(d.get("Error", "")).lower() else "none")
        try:
            v = float(str(d.get("imdbRating") or ""))
        except ValueError:
            return "", "none"
        return (f"{v:.1f}", "") if 0 < v <= 10 else ("", "none")

    def imdb_rating(self, imdb_id: str) -> str:
        """IMDb reytingi (faqat OMDb kaliti berilgan bo'lsa), masalan «7.9»."""
        return self.imdb_lookup(imdb_id)[0]


_inst: Dict[tuple, Tmdb] = {}


def get(app) -> Tmdb:
    c = app.config
    key = (c.tmdb_key, c.tmdb_lang, c.omdb_key, c.tmdb_base, c.omdb_base)
    if key not in _inst:
        _inst[key] = Tmdb(c.tmdb_key, c.tmdb_lang, c.omdb_key, c.tmdb_base or TMDB_BASE, c.omdb_base or OMDB_BASE)
    return _inst[key]


def apply_fields(db, movie_id: int, data: dict, with_description: bool = False) -> List[str]:
    """Topilgan ma'lumotni kinoga yozadi (bo'sh maydonlar o'tkazib yuboriladi). Nimalar o'zgargani ro'yxatini qaytaradi."""
    from . import genres as G
    m = db.get_movie(movie_id)
    if not m or m["category"] == "music":
        return []
    f: dict = {}
    changed: List[str] = []
    if data.get("year"):
        f["year"] = int(data["year"]); changed.append("yil")
    if data.get("genres"):
        f["genres"] = G.dump(data["genres"]); changed.append("janr")
    if data.get("country") in G.COUNTRIES:
        f["country"] = data["country"]; changed.append("davlat")
    if data.get("duration_min"):
        f["duration"] = int(data["duration_min"]) * 60; changed.append("davomiylik")
    if data.get("age"):
        f["age"] = int(data["age"]); changed.append("yosh")
    if data.get("imdb"):
        f["imdb"] = str(data["imdb"]); changed.append("IMDb")
    ex = data.get("extra") or {}
    if ex.get("cast") or ex.get("stills") or ex.get("budget") or ex.get("revenue"):
        f["extra"] = json.dumps(ex, ensure_ascii=False, separators=(",", ":")); changed.append("aktyorlar/kadrlar")
        if ex.get("stills"):
            f["backdrop"] = ex["stills"][0]; changed.append("keng rasm")
    if data.get("poster_path"):
        f["tposter"] = data["poster_path"]; changed.append("TMDB poster")
    if data.get("trailer") and not (m["trailer_url"] or "").strip():      # qo'lda kiritilgan treyler o'zgartirilmaydi
        f["trailer_url"] = data["trailer"]; changed.append("treyler")
    if data.get("overview") and (with_description or not (m["description"] or "").strip()):
        f["description"] = data["overview"][:3000]; f["desc_html"] = ""; changed.append("izoh")
    if f:
        db.update_movie(movie_id, **f)
        db.__dict__.pop("_memo", None)
    return changed



# ───── 🖼 eski kinolar uchun rasmlarni avtomatik topish (faqat rasm; boshqa ma'lumotga tegilmaydi) ─────
def _words(text: str) -> set:
    from .utils import normalize
    return {w for w in normalize(text or "").split() if len(w) > 2}


def overview_similarity(a: str, b: str) -> float:
    """Ikki tavsif o'xshashligi (0..1): umumiy so'zlar / kichikroq to'plam. Izoh TMDB dan olingan bo'lsa ~1 chiqadi."""
    wa, wb = _words(a), _words(b)
    if len(wa) < 6 or len(wb) < 6:
        return 0.0
    return len(wa & wb) / min(len(wa), len(wb))


def match_images(tm: "Tmdb", title: str, year: int, description: str) -> Optional[dict]:
    """Kinoga TMDB dan mos rasm topadi. Xato rasm qo'yishdan ko'ra topmaslik yaxshi, shuning uchun qat'iy shart:
    (a) tavsif TMDB tavsifiga ≥ 55% mos va yil ±1 (yoki yil noma'lum), yoki (b) nom aynan mos va yil aynan bir xil.
    Natija: {kind, id, title, tposter, backdrop, how} yoki None."""
    from .utils import normalize
    q = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", title or "")).strip()
    if len(q) < 2:
        return None
    paren = [x.strip() for x in re.findall(r"\(([^)]*)\)", title or "") if len(x.strip()) >= 2]      # «Senga atalgan orzu (Mening orzuyimsan)» — qavs ichi ham nom
    queries = [q] + [x for x in paren if x != q][:1]
    langs = list(dict.fromkeys(list(getattr(tm, "langs", [])) + ["ru-RU", "en-US"]))      # eski izohlar ruscha bo'lishi mumkin — ruscha ham qidiriladi
    cands: Dict[tuple, dict] = {}
    for lang, qq in [(l, x) for x in queries for l in langs]:
        try:
            d = tm._tmdb("/search/multi", query=qq, language=lang, include_adult="false")
        except TmdbError:
            continue
        for r in d.get("results", []):
            kind = r.get("media_type")
            if kind not in ("movie", "tv"):
                continue
            key = (kind, r["id"])
            c = cands.setdefault(key, {"kind": kind, "id": r["id"], "ov": "", "titles": set()})
            date = r.get("release_date") or r.get("first_air_date") or ""
            c["year"] = int(date[:4]) if date[:4].isdigit() else 0
            c["titles"] |= {normalize(r.get("title") or r.get("name") or ""), normalize(r.get("original_title") or r.get("original_name") or "")}
            ov_new = r.get("overview") or ""      # eski tavsifga eng o'xshash tildagisini saqlaymiz
            if ov_new and (not c["ov"] or overview_similarity(description, ov_new) > overview_similarity(description, c["ov"])):
                c["ov"] = ov_new
            c["poster"] = img_path(r.get("poster_path")) or c.get("poster", "")
            c["backdrop"] = img_path(r.get("backdrop_path")) or c.get("backdrop", "")
            c["title"] = r.get("title") or r.get("name") or c.get("title", "")
    best, best_score = None, 0.0
    nq = normalize(q)
    nqs = {normalize(x) for x in queries}
    for c in cands.values():
        sim = overview_similarity(description, c["ov"])
        dy = abs(c["year"] - year) if (year and c["year"]) else 0
        year_ok = (not year) or (c["year"] and dy <= 1)
        exact = bool(nqs & c["titles"]) and year and c["year"] == year
        if sim >= 0.55 and year_ok:
            how, score = "tavsif", 2 + sim
        elif exact:
            how, score = "nom+yil", 1.0
        else:
            continue
        if score > best_score:
            best, best_score = dict(c, how=how), score
    if not best:
        return None
    backdrop = best.get("backdrop", "")
    try:     # matnsiz (til belgisiz) eng yaxshi keng rasm
        im = tm._tmdb(f"/{best['kind']}/{best['id']}/images", include_image_language="null")
        bks = [b for b in (im.get("backdrops") or []) if img_path(b.get("file_path"))]
        bks.sort(key=lambda b: -(b.get("vote_average") or 0))
        if bks:
            backdrop = bks[0]["file_path"]
    except TmdbError:
        pass
    return {"kind": best["kind"], "id": best["id"], "title": best.get("title", ""), "tposter": best.get("poster", ""),
            "backdrop": backdrop, "how": best["how"]}
