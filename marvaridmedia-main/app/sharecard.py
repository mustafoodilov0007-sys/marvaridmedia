"""🖼 Ulashish kartochkasi (Open Graph rasmi, 1200×630): kino havolasi Telegram, Instagram yoki boshqa joyga tashlanganda
chiqadigan katta rasm — xira fon, chapda poster, o'ngda nom, yil, janr, reyting va «Tomosha qilish» tugmasi.
Pillow bo'lmasa — None (sahifada oddiy poster ishlatiladi)."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("sharecard")

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    Image = None

ASSETS = Path(__file__).resolve().parent / "assets"
W, H = 1200, 630
GOLD = (233, 196, 106)


def available() -> bool:
    return Image is not None and (ASSETS / "interdisplay-bold.otf").exists()


def _font(name: str, size: int):
    return ImageFont.truetype(str(ASSETS / name), size)


def _cover(img, w: int, h: int):
    k = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * k)), max(h, round(img.height * k))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _wrap(draw, text: str, font, max_w: int, max_lines: int):
    words, lines, cur = text.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if draw.textlength(t, font=font) <= max_w:
            cur = t
            continue
        if cur:
            lines.append(cur)
        cur = wd
        if len(lines) == max_lines:
            break
    if cur and len(lines) < max_lines:
        lines.append(cur)
    joined = " ".join(lines)
    if len(joined) < len(text.strip()):                 # sig'madi — oxiriga «…»
        last = lines[-1]
        while last and draw.textlength(last + "…", font=font) > max_w:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


def _avg_color(img):
    sm = img.convert("RGB").resize((8, 12))
    px = list(sm.getdata())
    best = max(px, key=lambda p: (max(p) - min(p)) * (1 if 40 < sum(p) / 3 < 220 else 0.2))
    return best


def render(poster: Optional[bytes], title: str, meta: str, genres_line: str, imdb: str = "", code: int = 0,
           brand: str = "Marvarid Media", cta: str = "Tomosha qilish") -> Optional[bytes]:
    if not available():
        return None
    try:
        p = Image.open(io.BytesIO(poster)).convert("RGB") if poster else None
    except Exception:  # noqa: BLE001 — buzuq poster: rasmsiz kartochka
        p = None
    # 1) fon: posterning o'zi, xira va qorong'i + poster rangidagi yorug'lik
    if p is not None:
        bg = _cover(p, W, H).filter(ImageFilter.GaussianBlur(34))
        bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 7, 10)), 0.62)
        tint = _avg_color(p)
    else:
        bg, tint = Image.new("RGB", (W, H), (14, 12, 18)), (120, 90, 40)
    glow = Image.new("RGB", (W, H), tint)
    mask = Image.linear_gradient("L").rotate(90).resize((W, H)).point(lambda v: int(v * 0.32))
    bg = Image.composite(glow, bg, mask)
    shade = Image.linear_gradient("L").rotate(90).resize((W, H)).point(lambda v: int(255 - v * 0.75))
    bg = Image.composite(Image.new("RGB", (W, H), (6, 5, 8)), bg, shade.point(lambda v: int(v * 0.55)))
    d = ImageDraw.Draw(bg)
    # 2) chapda poster (soya bilan, yumaloq burchak)
    x0, ph = 64, 502
    pw = round(ph * 2 / 3)
    y0 = (H - ph) // 2
    if p is not None:
        pc = _cover(p, pw, ph)
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).rounded_rectangle((x0 + 6, y0 + 16, x0 + pw + 6, y0 + ph + 16), 26, fill=150)
        sh = sh.filter(ImageFilter.GaussianBlur(18))
        bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, sh)
        m = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, pw, ph), 24, fill=255)
        bg.paste(pc, (x0, y0), m)
        d = ImageDraw.Draw(bg)
        d.rounded_rectangle((x0, y0, x0 + pw, y0 + ph), 24, outline=(78, 70, 60), width=2)
    # 3) o'ngda matn
    tx, tw = x0 + pw + 56, W - (x0 + pw + 56) - 64
    y = 84
    d.text((tx, y), brand.upper(), font=_font("inter-semibold.otf", 22), fill=GOLD, spacing=4)
    y += 50
    size = 66
    while size > 38:
        f = _font("interdisplay-bold.otf", size)
        lines = _wrap(d, title, f, tw, 3)
        if len(lines) <= 2 or size <= 46:
            break
        size -= 4
    for ln in lines:
        d.text((tx, y), ln, font=f, fill=(250, 246, 238))
        y += round(size * 1.12)
    y += 14
    fm = _font("inter-medium.otf", 30)
    if meta:
        d.text((tx, y), meta, font=fm, fill=(214, 206, 192))
        y += 44
    if genres_line:
        d.text((tx, y), _wrap(d, genres_line, fm, tw, 1)[0], font=fm, fill=(170, 162, 150))
        y += 44
    # reyting va kod «tabletkalari»
    y += 14
    px = tx
    fp = _font("inter-semibold.otf", 26)
    if imdb:
        lab = "IMDb " + str(imdb)
        wpx = round(d.textlength(lab, font=fp)) + 36
        d.rounded_rectangle((px, y, px + wpx, y + 48), 14, fill=(245, 197, 24))
        d.text((px + 18, y + 9), lab, font=fp, fill=(20, 16, 6))
        px += wpx + 14
    if code > 0:
        lab = f"Kod: {code}"
        wpx = round(d.textlength(lab, font=fp)) + 36
        d.rounded_rectangle((px, y, px + wpx, y + 48), 14, fill=(26, 23, 30), outline=(110, 102, 92), width=2)
        d.text((px + 18, y + 9), lab, font=fp, fill=(250, 246, 238))
    # 4) pastda «Tomosha qilish» tugmasi
    fc = _font("inter-semibold.otf", 30)
    lab = cta
    bw = round(d.textlength(lab, font=fc)) + 64 + 34
    by = y0 + ph - 72
    btn = Image.linear_gradient("L").rotate(90).resize((bw, 72))
    btn_rgb = Image.merge("RGB", [btn.point(lambda v: int(248 - v * 0.2)), btn.point(lambda v: int(214 - v * 0.35)),
                                  btn.point(lambda v: int(120 - v * 0.3))])
    bm = Image.new("L", (bw, 72), 0)
    ImageDraw.Draw(bm).rounded_rectangle((0, 0, bw, 72), 22, fill=255)
    bg.paste(btn_rgb, (tx, by), bm)
    d = ImageDraw.Draw(bg)
    d.polygon([(tx + 30, by + 22), (tx + 30, by + 50), (tx + 54, by + 36)], fill=(29, 20, 5))    # ▶ belgisi (shriftga bog'liq emas)
    d.text((tx + 32 + 34, by + 18), lab, font=fc, fill=(29, 20, 5))
    out = io.BytesIO()
    bg.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    return out.getvalue()


def render_review(poster: Optional[bytes], title: str, body: str, author: str, likes: int = 0,
                  brand: str = "Marvarid Media") -> Optional[bytes]:
    """💬 Izoh kartochkasi 1080×1080: xira poster foni, tepada kichik poster va kino nomi, o'rtada izoh, pastda muallif."""
    if not available():
        return None
    S = 1080
    try:
        p = Image.open(io.BytesIO(poster)).convert("RGB") if poster else None
    except Exception:  # noqa: BLE001
        p = None
    if p is not None:
        bg = _cover(p, S, S).filter(ImageFilter.GaussianBlur(40))
        bg = Image.blend(bg, Image.new("RGB", (S, S), (8, 7, 10)), 0.68)
    else:
        bg = Image.new("RGB", (S, S), (14, 12, 18))
    d = ImageDraw.Draw(bg)
    m = 76
    d.text((m, 64), brand.upper(), font=_font("inter-semibold.otf", 26), fill=GOLD)
    y = 130
    if p is not None:
        pw, ph = 120, 180
        pc = _cover(p, pw, ph)
        mk = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(mk).rounded_rectangle((0, 0, pw, ph), 16, fill=255)
        bg.paste(pc, (m, y), mk)
        d = ImageDraw.Draw(bg)
        tx = m + pw + 28
    else:
        tx = m
    ft = _font("interdisplay-bold.otf", 46)
    ty = y + 30
    for ln in _wrap(d, title, ft, S - tx - m, 2):
        d.text((tx, ty), ln, font=ft, fill=(250, 246, 238))
        ty += 56
    # izoh matni: katta, shriftni sig'diriladi
    top, bottom = 360, 880
    size = 54
    while True:
        f = _font("inter-medium.otf", size)
        lines = _wrap(d, body.strip(), f, S - 2 * m - 40, 12)
        if len(lines) * round(size * 1.34) <= bottom - top or size <= 30:
            break
        size -= 4
    d.text((m, top - 120), "“", font=_font("interdisplay-bold.otf", 200), fill=(233, 196, 106))
    yy = top
    for ln in lines:
        d.text((m + 20, yy), ln, font=f, fill=(244, 240, 232))
        yy += round(size * 1.34)
    d.rounded_rectangle((m, 936, m + 8, 1000), 4, fill=GOLD)
    d.text((m + 28, 934), author, font=_font("inter-semibold.otf", 36), fill=(250, 246, 238))
    sub = "izoh" + (f" \u00b7 {likes} yoqdi" if likes else "")
    d.text((m + 28, 978), sub, font=_font("inter-medium.otf", 26), fill=(170, 162, 150))
    out = io.BytesIO()
    bg.save(out, "JPEG", quality=88, optimize=True, progressive=True)
    return out.getvalue()
