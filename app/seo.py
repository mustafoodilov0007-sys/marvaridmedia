"""🔎 SEO: har bir kino/ro'yxat uchun alohida sahifa manzili, sarlavha, tavsif, kanonik havola, JSON-LD (Google boy natijalari),
<noscript> matni (JS ishlatmaydigan qidiruv tizimlari uchun), sitemap.xml va robots.txt.

Odam ko'radigan sahifa — oddiy sayt (SPA); qidiruv robotlari ko'radigan ma'lumot — xuddi shu kontentning matn ko'rinishi.
"""

from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional

from . import genres
from .utils import TZ, normalize, truncate

CATEGORY_NAMES = {"movie": "Kino", "serial": "Serial", "cartoon": "Multfilm"}
LIST_PAGES = {
    "/kinolar": ("movie", "Kinolar", "Eng sara kinolar o'zbek tilida"),
    "/seriallar": ("serial", "Seriallar", "Eng sara seriallar o'zbek tilida"),
    "/multfilmlar": ("cartoon", "Multfilmlar", "Eng sara multfilmlar o'zbek tilida"),
}
_e = html.escape


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", normalize(title).replace(" ", "-"))[:60].strip("-")


def movie_path(code: int, title: str) -> str:
    s = slug(title)
    return f"/kino/{code}" + (f"-{s}" if s else "")


def og_tags(brand: str, title: str, desc: str, image: str, url: str) -> str:
    return (f'<meta name="description" content="{_e(desc, True)}">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="{_e(brand, True)}">\n'
            f'<meta property="og:title" content="{_e(title, True)}">\n<meta property="og:description" content="{_e(desc, True)}">\n'
            f'<meta property="og:url" content="{_e(url, True)}">\n<meta property="og:image" content="{_e(image, True)}">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n<meta name="twitter:title" content="{_e(title, True)}">\n'
            f'<meta name="twitter:description" content="{_e(desc, True)}">\n<meta name="twitter:image" content="{_e(image, True)}">')


def _iso_duration(seconds: int) -> str:
    m = int(round(seconds / 60))
    return f"PT{m // 60}H{m % 60}M" if m >= 60 else f"PT{m}M"


def _poster_url(base: str, movie, key_fn) -> str:
    return f"{base}/api/poster/{movie['id']}?v={key_fn(movie['poster_id'])}" if movie["poster_id"] else f"{base}/og.png"


def movie_page(app, base: str, code: int, poster_key) -> Optional[Dict]:
    """Bitta kino sahifasi uchun SEO ma'lumotlari. Kino topilmasa (yoki musiqa bo'lsa) — None."""
    db = app.db
    m = db.get_movie_by_code(code)
    if not m or m["category"] == "music":
        return None
    brand = app.brand
    cat = CATEGORY_NAMES.get(m["category"], "Kino")
    gnames = [genres.name(k) for k in genres.parse(m["genres"])]
    year = m["year"] or 0
    keys = m.keys()
    duration = m["duration"] if "duration" in keys else 0
    url = base + movie_path(m["code"], m["title"])
    title = f"{m['title']}{f' ({year})' if year else ''} — {cat.lower()} o'zbek tilida | {brand}"
    bits = [cat] + ([str(year)] if year else []) + gnames[:3]
    desc = " • ".join(bits) + ((" — " + truncate((m["description"] or "").strip(), 150)) if (m["description"] or "").strip() else
                               f". {brand} saytida tomosha qiling.")
    image = _poster_url(base, m, poster_key)
    ld: Dict = {"@context": "https://schema.org", "@type": "TVSeries" if m["category"] == "serial" else "Movie",
                "name": m["title"], "url": url, "image": image, "description": truncate((m["description"] or desc), 300),
                "inLanguage": "uz"}
    if gnames:
        ld["genre"] = gnames
    if year:
        ld["datePublished"] = str(year)
    if duration and m["category"] != "serial":
        ld["duration"] = _iso_duration(duration)
    if "age" in keys and m["age"]:
        ld["contentRating"] = f"{m['age']}+"
    related = db.similar(m["id"], 8)
    rel = "".join(f'<li><a href="{_e(movie_path(r["code"], r["title"]))}">{_e(r["title"])}</a></li>' for r in related if r["code"] > 0)
    info = "".join(f"<li>{_e(x)}</li>" for x in genres.info_lines(m))
    noscript = (f'<article><h1>{_e(m["title"])}{f" ({year})" if year else ""}</h1><p>{_e(" • ".join(bits))}</p>'
                f'<ul>{info}</ul><p>{_e(truncate((m["description"] or "").strip(), 600))}</p>'
                f'<p><a href="https://t.me/{_e(app.bot_username)}?start={m["code"]}">Telegram botda tomosha qilish</a></p>'
                + (f"<h2>O'xshash {cat.lower()}lar</h2><ul>{rel}</ul>" if rel else "")
                + '<nav><a href="/">Bosh sahifa</a> · <a href="/kinolar">Kinolar</a> · <a href="/seriallar">Seriallar</a> · '
                  '<a href="/multfilmlar">Multfilmlar</a></nav></article>')
    return {"title": title, "og": og_tags(brand, title, desc, image, url), "canonical": url, "jsonld": ld, "noscript": noscript,
            "status": 200}


def list_page(app, base: str, cat: Optional[str] = None, genre: Optional[str] = None) -> Optional[Dict]:
    """Ro'yxat sahifasi: tur (kinolar/seriallar/multfilmlar) yoki janr bo'yicha eng mashhur 100 ta."""
    db, brand = app.db, app.brand
    if genre:
        if genre not in genres.GENRES:
            return None
        name = genres.name(genre)
        rows = db.catalog("video", "top", None, 100, 0, genre=genre)
        h1, path, desc = f"{name} kinolar", f"/janr/{genre}", f"{name} janridagi eng sara kinolar, seriallar va multfilmlar o'zbek tilida."
    else:
        h1 = {"movie": "Kinolar", "serial": "Seriallar", "cartoon": "Multfilmlar"}.get(cat or "")
        if not h1:
            return None
        rows = db.catalog(cat, "top", None, 100, 0)
        path = {"movie": "/kinolar", "serial": "/seriallar", "cartoon": "/multfilmlar"}[cat]
        desc = LIST_PAGES[path][2] + ". Qidiring, saqlang, tomosha qiling."
    url = base + path
    title = f"{h1} o'zbek tilida | {brand}"
    items = [r for r in rows if r["code"] > 0]
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": h1, "url": url,
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": base + movie_path(r["code"], r["title"]), "name": r["title"]}
                              for i, r in enumerate(items[:50])]}
    lis = ""
    for r in items:
        yr = f" ({r['year']})" if r["year"] else ""
        lis += f'<li><a href="{_e(movie_path(r["code"], r["title"]))}">{_e(r["title"])}</a>{yr}</li>'
    noscript = f'<article><h1>{_e(h1)}</h1><p>{_e(desc)}</p><ol>{lis}</ol><nav><a href="/">Bosh sahifa</a></nav></article>'
    return {"title": title, "og": og_tags(brand, title, desc, f"{base}/og.png", url), "canonical": url, "jsonld": ld,
            "noscript": noscript, "status": 200}


def apply(page_html: str, seo: Dict) -> str:
    """Asosiy sahifaga SEO ma'lumotlarini kiritadi: sarlavha, OG, kanonik havola, JSON-LD, <noscript>."""
    s = page_html
    s = re.sub(r"<title>.*?</title>", lambda m: f"<title>{_e(seo['title'])}</title>", s, count=1, flags=re.S)
    s = re.sub(r"<!--OG-->.*?<!--/OG-->", lambda m: "<!--OG-->\n" + seo["og"] + "\n<!--/OG-->", s, count=1, flags=re.S)
    extra = f'<link rel="canonical" href="{_e(seo["canonical"], True)}">\n'
    if seo.get("jsonld"):
        extra += '<script type="application/ld+json">' + json.dumps(seo["jsonld"], ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
    s = s.replace("</head>", extra + "</head>", 1)
    if seo.get("noscript"):
        s = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n<noscript>" + seo["noscript"] + "</noscript>", s, count=1)
    return s


# ───── sitemap.xml va robots.txt ─────

_cache: Dict[str, tuple] = {}


def sitemap(app, base: str) -> str:
    hit = _cache.get("sitemap")
    if hit and time.time() - hit[0] < 3600 and hit[2] == base:
        return hit[1]
    db = app.db
    urls: List[tuple] = [(base + "/", None, "1.0")]
    urls += [(base + p, None, "0.8") for p in LIST_PAGES]
    urls += [(f"{base}/janr/{k}", None, "0.6") for k in db.genre_counts("video")]
    for r in db.q("SELECT code, title, created_at FROM movies WHERE category<>'music' AND code>0 ORDER BY id DESC LIMIT 49000"):
        urls.append((base + movie_path(r["code"], r["title"]), datetime.fromtimestamp(r["created_at"], TZ).strftime("%Y-%m-%d"), "0.7"))
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, last, prio in urls:
        out.append(f"<url><loc>{_e(loc)}</loc>" + (f"<lastmod>{last}</lastmod>" if last else "") + f"<priority>{prio}</priority></url>")
    out.append("</urlset>")
    xml = "\n".join(out)
    _cache["sitemap"] = (time.time(), xml, base)
    return xml


def robots(base: str) -> str:
    return ("User-agent: *\nAllow: /\nAllow: /api/poster/\nDisallow: /api/\nDisallow: /pub/\nDisallow: /media/\nDisallow: /admin\n"
            f"\nSitemap: {base}/sitemap.xml\n")
