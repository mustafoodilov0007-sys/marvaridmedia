"""🔎 SEO: har bir kino/ro'yxat uchun alohida sahifa manzili, sarlavha, tavsif, kanonik havola, JSON-LD (Google boy natijalari),
<noscript> matni (JS ishlatmaydigan qidiruv tizimlari uchun), sitemap.xml va robots.txt.

Odam ko'radigan sahifa — oddiy sayt (SPA); qidiruv robotlari ko'radigan ma'lumot — xuddi shu kontentning matn ko'rinishi.
"""

from __future__ import annotations

import hashlib
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
            '<meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">\n'
            f'<meta property="og:locale" content="uz_UZ">\n'
            f'<meta property="og:type" content="website">\n<meta property="og:site_name" content="{_e(brand, True)}">\n'
            f'<meta property="og:title" content="{_e(title, True)}">\n<meta property="og:description" content="{_e(desc, True)}">\n'
            f'<meta property="og:url" content="{_e(url, True)}">\n<meta property="og:image" content="{_e(image, True)}">\n'
            + ('<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n' if "/og/" in image else "") +
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
    try:
        from . import sharecard
        if sharecard.available():          # katta ulashish kartochkasi (poster, nom, yil, reyting) — havola chiroyli ko'rinadi
            image = f"{base}/og/{m['id']}.jpg?v={poster_key(m['poster_id']) if m['poster_id'] else 0}"
    except Exception:  # noqa: BLE001
        pass
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
    ld["isAccessibleForFree"] = not bool(m["is_premium"])
    if "country" in keys and m["country"]:
        ld["countryOfOrigin"] = {"@type": "Country", "name": genres.country_label(m["country"]).split(" ", 1)[-1]}
    r = db.rating(m["id"])
    n = r["likes"] + r["dislikes"]
    if n >= 3:       # faqat haqiqiy ovozlar (kamida 3 ta): 👍 ulushi 1–5 shkalaga o'tkaziladi
        ld["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": round(1 + 4 * r["likes"] / n, 1), "bestRating": 5,
                                 "worstRating": 1, "ratingCount": n}
    if "imdb" in keys and m["imdb"]:
        ld["sameAs"] = []
    ld["potentialAction"] = {"@type": "WatchAction", "target": [
        {"@type": "EntryPoint", "urlTemplate": url, "actionPlatform": ["http://schema.org/DesktopWebPlatform", "http://schema.org/MobileWebPlatform"]},
        {"@type": "EntryPoint", "urlTemplate": f"https://t.me/{app.bot_username}?start={m['code']}"}]}
    tu = (m["trailer_url"] if "trailer_url" in keys else "") or ""
    ym = re.search(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})", tu)
    if ym:           # YouTube treyler: Google qidiruvida video sifatida ham chiqishi mumkin
        ld["trailer"] = {"@type": "VideoObject", "name": f"{m['title']} — treyler", "description": truncate((m["description"] or desc), 200),
                         "thumbnailUrl": f"https://i.ytimg.com/vi/{ym.group(1)}/hqdefault.jpg",
                         "uploadDate": datetime.fromtimestamp(m["created_at"], TZ).strftime("%Y-%m-%d"),
                         "embedUrl": f"https://www.youtube.com/embed/{ym.group(1)}", "contentUrl": tu}
    if not ld.get("sameAs"):
        ld.pop("sameAs", None)
    crumbs = {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Bosh sahifa", "item": base + "/"},
        {"@type": "ListItem", "position": 2, "name": {"movie": "Kinolar", "serial": "Seriallar", "cartoon": "Multfilmlar"}.get(m["category"], "Kinolar"),
         "item": base + {"movie": "/kinolar", "serial": "/seriallar", "cartoon": "/multfilmlar"}.get(m["category"], "/kinolar")},
        {"@type": "ListItem", "position": 3, "name": m["title"], "item": url}]}
    ld.pop("@context", None)
    ld = {"@context": "https://schema.org", "@graph": [ld, crumbs]}
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


def collection_path(cid: int, title: str) -> str:
    s = slug(title)
    return f"/kolleksiya/{cid}" + (f"-{s}" if s else "")


def _list_ld_html(base: str, h1: str, desc: str, url: str, items, brand: str, extra_nav: str = "") -> Dict:
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": h1, "url": url,
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": base + movie_path(r["code"], r["title"]), "name": r["title"]}
                              for i, r in enumerate(items[:50])]}
    lis = ""
    for r in items:
        yr = f" ({r['year']})" if r["year"] else ""
        lis += f'<li><a href="{_e(movie_path(r["code"], r["title"]))}">{_e(r["title"])}</a>{yr}</li>'
    noscript = f'<article><h1>{_e(h1)}</h1><p>{_e(desc)}</p><ol>{lis}</ol><nav><a href="/">Bosh sahifa</a> {extra_nav}</nav></article>'
    return {"ld": ld, "noscript": noscript}


def collection_page(app, base: str, cid: int) -> Optional[Dict]:
    """Bitta kolleksiya sahifasi (masalan «Marvel to'plami»): Google'da «Marvel kinolari o'zbek tilida» kabi so'rovlar uchun."""
    db, brand = app.db, app.brand
    col = db.get_collection(cid)
    if not col:
        return None
    rows = [r for r in db.collection_movies(cid, 100) if r["code"] > 0]
    if not rows:
        return None
    h1 = col["title"]
    desc = f"{h1}: {len(rows)} ta kino va serial o'zbek tilida. " + ", ".join(r["title"] for r in rows[:4]) + " va boshqalar. Qidiring, saqlang, tomosha qiling."
    url = base + collection_path(cid, h1)
    title = f"{h1} — kinolar o'zbek tilida | {brand}"
    first = next((r for r in rows if r["poster_id"]), None)
    image = f"{base}/api/poster/{first['id']}?v=" + hashlib.sha1(first["poster_id"].encode()).hexdigest()[:12] if first else f"{base}/og.png"
    parts = _list_ld_html(base, h1, desc, url, rows, brand, '<a href="/kolleksiyalar">Barcha kolleksiyalar</a>')
    return {"title": title, "og": og_tags(brand, title, desc, image, url), "canonical": url, "jsonld": parts["ld"],
            "noscript": parts["noscript"], "status": 200}


def collections_index_page(app, base: str) -> Optional[Dict]:
    db, brand = app.db, app.brand
    cols = [c for c in db.list_collections() if c["n"]]
    if not cols:
        return None
    h1 = "Kolleksiyalar"
    desc = "Mavzu bo'yicha kino to'plamlari: " + ", ".join(c["title"] for c in cols[:6]) + ". O'zbek tilida tomosha qiling."
    url = base + "/kolleksiyalar"
    title = f"Kolleksiyalar — mavzu bo'yicha kinolar | {brand}"
    lis = "".join(f'<li><a href="{_e(collection_path(c["id"], c["title"]))}">{_e(c["title"])}</a> ({c["n"]} ta)</li>' for c in cols)
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": h1, "url": url,
          "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": base + collection_path(c["id"], c["title"]), "name": c["title"]}
                              for i, c in enumerate(cols[:50])]}
    noscript = f'<article><h1>{_e(h1)}</h1><p>{_e(desc)}</p><ul>{lis}</ul><nav><a href="/">Bosh sahifa</a></nav></article>'
    return {"title": title, "og": og_tags(brand, title, desc, f"{base}/og.png", url), "canonical": url, "jsonld": ld,
            "noscript": noscript, "status": 200}


def home_jsonld(app, base: str) -> Dict:
    """Bosh sahifa: sayt + tashkilot (logotip) + Google qidiruvidagi «saytda qidirish» kutisi."""
    return {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": base + "/#site", "url": base + "/", "name": app.brand, "inLanguage": "uz",
         "potentialAction": {"@type": "SearchAction", "target": {"@type": "EntryPoint", "urlTemplate": base + "/?q={search_term_string}"},
                             "query-input": "required name=search_term_string"}},
        {"@type": "Organization", "@id": base + "/#org", "name": app.brand, "url": base + "/", "logo": base + "/apple-touch-icon.png"}]}


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
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    urls: List[tuple] = [(base + "/", today, "1.0", "daily", None)]
    urls += [(base + p, today, "0.8", "daily", None) for p in LIST_PAGES]
    urls += [(f"{base}/janr/{k}", today, "0.6", "weekly", None) for k in db.genre_counts("video")]
    cols = [c for c in db.list_collections() if c["n"]]
    if cols:
        urls.append((base + "/kolleksiyalar", today, "0.7", "weekly", None))
        urls += [(base + collection_path(c["id"], c["title"]), today, "0.7", "weekly", None) for c in cols]
    recent = time.time() - 30 * 86400
    for r in db.q("SELECT id, code, title, created_at, poster_id FROM movies WHERE category<>'music' AND code>0 ORDER BY id DESC LIMIT 49000"):
        img = f"{base}/api/poster/{r['id']}?w=720" if r["poster_id"] else None
        urls.append((base + movie_path(r["code"], r["title"]), datetime.fromtimestamp(r["created_at"], TZ).strftime("%Y-%m-%d"),
                     "0.8" if r["created_at"] >= recent else "0.7", "monthly", (img, r["title"])))
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for loc, last, prio, freq, img in urls:
        row = f"<url><loc>{_e(loc)}</loc>" + (f"<lastmod>{last}</lastmod>" if last else "") + f"<changefreq>{freq}</changefreq><priority>{prio}</priority>"
        if img and img[0]:
            row += f"<image:image><image:loc>{_e(img[0])}</image:loc><image:title>{_e(img[1])}</image:title></image:image>"
        out.append(row + "</url>")
    out.append("</urlset>")
    xml = "\n".join(out)
    _cache["sitemap"] = (time.time(), xml, base)
    return xml


def robots(base: str) -> str:
    return ("User-agent: *\nAllow: /\nAllow: /api/poster/\nAllow: /og/\nDisallow: /api/\nDisallow: /pub/\nDisallow: /media/\nDisallow: /admin\n"
            f"\nSitemap: {base}/sitemap.xml\n")
