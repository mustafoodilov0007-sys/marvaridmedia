"""🎬 Botning «What can this bot do?» kartasi (BotFather → Edit Description Picture) uchun animatsiya.

Bazadagi haqiqiy posterlardan ustun-ustun suzib o'tuvchi kollaj, so'ng logotip va «MARVARID MEDIA» yozuvi.
Pillow bilan kadrlar chiziladi, ffmpeg MP4 qiladi (ikkalasi ham ixtiyoriy kutubxona — bo'lmasa `available()` False).
"""

from __future__ import annotations

import io
import math
import random
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    Image = None

ASSETS = Path(__file__).parent / "assets"
LOGO = Path(__file__).parent / "web" / "icon-512.png"
GOLD = (244, 184, 64)
W, H = 640, 360
TW, TH, GAP, COLS = 88, 132, 8, 8


def available() -> bool:
    return Image is not None and shutil.which("ffmpeg") is not None


def _ease(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def _cover(img: "Image.Image", w: int, h: int) -> "Image.Image":
    img = img.convert("RGB")
    k = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * k)), max(h, round(img.height * k))), Image.LANCZOS)
    x, y = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def _font(size: int, weight: int = 700):
    f = ImageFont.truetype(str(ASSETS / "cinzel.ttf"), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:  # noqa: BLE001 — o'zgaruvchan shrift qo'llab-quvvatlanmasa ham ishlaydi
        pass
    return f


def build(posters: List[bytes], out_path: str, fps: int = 30, dur: float = 8.0, seed: int = 7) -> None:
    """posters — rasm baytlari (kamida 3 ta). out_path — MP4 (640×360, ovozsiz, 8 s, boshiga yumshoq qaytadi)."""
    if not available():
        raise RuntimeError("Pillow yoki ffmpeg o'rnatilmagan")
    rnd = random.Random(seed)
    tiles = []
    for b in posters:
        try:
            tiles.append(_cover(Image.open(io.BytesIO(b)), TW, TH))
        except Exception:  # noqa: BLE001 — buzuq rasm o'tkazib yuboriladi
            continue
    if len(tiles) < 3:
        raise ValueError("kamida 3 ta yaroqli poster kerak")
    per = 10
    strips = []
    for c in range(COLS):
        order = [tiles[(c * 3 + i * 5 + rnd.randint(0, 2)) % len(tiles)] for i in range(per)]
        col_h = (TH + GAP) * per
        s = Image.new("RGB", (TW, col_h * 2), (11, 10, 13))
        for rep in range(2):
            for i, t in enumerate(order):
                s.paste(t, (0, rep * col_h + i * (TH + GAP)))
        strips.append((s, col_h))
    x0 = (W - (COLS * (TW + GAP) - GAP)) // 2
    black = Image.new("RGB", (W, H), (8, 7, 9))
    vig = Image.radial_gradient("L").resize((W, H), Image.BICUBIC).point(lambda v: int(max(0, v - 60) * 1.25 * 0.9)).filter(ImageFilter.GaussianBlur(8))
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(glow).ellipse((W / 2 - 170, H / 2 - 150, W / 2 + 170, H / 2 + 150), fill=(95, 62, 12))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    logo = Image.open(LOGO).convert("RGBA")
    f_title, f_sub = _font(46, 700), _font(15, 600)
    parts = [(rnd.random() * W, rnd.random() * H, rnd.uniform(8, 26), rnd.uniform(0.6, 1.8), rnd.uniform(0, 6.28)) for _ in range(46)]

    def spaced(d, text, font, cx, cy, sp, rgb, alphas):
        ws = [d.textlength(ch, font=font) for ch in text]
        x = cx - (sum(ws) + sp * (len(text) - 1)) / 2
        for i, ch in enumerate(text):
            if alphas[i] > 0:
                d.text((x, cy), ch, font=font, fill=rgb + (int(255 * alphas[i]),), anchor="lm")
            x += ws[i] + sp

    n = int(fps * dur)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-preset", "medium", "-movflags", "+faststart", "-an", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in range(n):
            t = f / fps * (8.0 / dur)                      # vaqt 8 soniyalik rejaga keltiriladi
            img = Image.new("RGB", (W, H), (11, 10, 13))
            for c, (s, col_h) in enumerate(strips):
                sp = (0.55 + 0.12 * (c % 3)) * (1 if c % 2 == 0 else -1)
                off = int((f * sp * 1.6) % col_h)
                if sp < 0:
                    off = col_h - off
                img.paste(s.crop((0, off % col_h, TW, off % col_h + H + TH)), (x0 + c * (TW + GAP), -(c * 37 % TH)))
            show = 1 - _ease((t - 6.8) / 1.2) if t > 6.8 else 1.0
            dim = 0.25 + 0.75 * (1 - _ease((t - 1.6) / 1.2)) if t < 6.8 else 0.25 + 0.75 * _ease((t - 6.8) / 1.2)
            img = Image.blend(black, img, dim * 0.9 + 0.1)
            img = Image.composite(black, img, vig)
            g = (0.0 if t < 1.4 else min(1.0, (t - 1.4) / 1.4)) * show
            if g > 0:
                img = ImageChops.add(img, Image.blend(Image.new("RGB", (W, H), (0, 0, 0)), glow, g))
            p = _ease((t - 1.5) / 1.3)
            if p > 0 and show > 0:
                s = int(150 * (0.55 + 0.45 * p))
                lg = logo.resize((s, s), Image.LANCZOS)
                lg.putalpha(lg.getchannel("A").point(lambda v: int(v * p * show)))
                lx, ly = W // 2 - s // 2, int(H / 2 - s / 2 - 34 + (1 - p) * 20)
                img.paste(lg, (lx, ly), lg)
                sw = (t - 3.4) / 1.2
                if 0 < sw < 1:
                    sh = Image.new("RGBA", (s, s), (0, 0, 0, 0))
                    x = int(-40 + sw * (s + 80))
                    ImageDraw.Draw(sh).polygon([(x, 0), (x + 26, 0), (x + 6, s), (x - 20, s)], fill=(255, 244, 210, 120))
                    sh.putalpha(ImageChops.multiply(sh.getchannel("A"), lg.getchannel("A")))
                    img.paste(sh, (lx, ly), sh)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            spaced(od, "MARVARID", f_title, W // 2, H - 84, 9, GOLD, [_ease((t - 2.6 - i * 0.09) / 0.5) * show for i in range(8)])
            sa = _ease((t - 3.7) / 0.7) * show
            if sa > 0:
                spaced(od, "MEDIA", f_sub, W // 2, H - 48, 14, (236, 226, 206), [sa] * 5)
                ln = int(70 * _ease((t - 3.9) / 0.8))
                od.line((W // 2 - ln, H - 62, W // 2 + ln, H - 62), fill=GOLD + (int(200 * sa),), width=1)
            for (px, py, sz, spd, ph) in parts:
                x, y = (px + math.sin(t * 0.7 + ph) * 14) % W, (py - t * spd * 9) % H
                r = sz / 26 * 1.8
                od.ellipse((x - r, y - r, x + r, y + r), fill=(255, 214, 120, int(150 * (0.5 + 0.5 * math.sin(t * 2 + ph)))))
            img = img.convert("RGBA")
            img.alpha_composite(ov)
            proc.stdin.write(img.convert("RGB").tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg xatosi: " + err[-300:])
    finally:
        if proc.poll() is None:
            proc.kill()
