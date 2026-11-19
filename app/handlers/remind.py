"""🔔 «Keyin ko'raman» eslatmasi: saqlangan, lekin hali ko'rilmagan kino haqida kechqurun bir marta (3 kunda ko'pi bilan bir marta) eslatadi.
Faqat yoqqan foydalanuvchiga — /saqlangan ichidagi «🔔 Eslatma» tugmasi yoki saytdagi Sevimlilar sahifasidan."""

from __future__ import annotations

import logging
import time
from datetime import datetime

from .. import genres
from ..core import Ctx, router
from ..keyboards import PRIMARY, SUCCESS, btn, ikb
from ..telegram import Forbidden, TelegramError
from ..texts import title_icon
from ..utils import TZ, esc, now, truncate

log = logging.getLogger("remind")

TOPIC = "savedremind"
SEND_HOUR, SEND_MIN = 19, 30          # Toshkent vaqti
SEND_GAP = 0.06


def enabled(db, uid: int) -> bool:
    return TOPIC in db.user_follows(uid)


def remind_text(movie) -> str:
    keys = movie.keys()
    year = genres.year_text(movie["year"], movie["year_end"] if "year_end" in keys else 0) if movie["year"] else ""
    g = " · ".join(genres.name(k) for k in genres.parse(movie["genres"])[:3])
    sub = "  ·  ".join(x for x in (year, g) if x)
    return (f"🔖 <b>Saqlagan kinongiz kutmoqda</b>\n\n{title_icon(movie['category'])} <b>{esc(movie['title'])}</b>"
            + (f"\n{esc(sub)}" if sub else "") + "\n\nBugun kechqurun tomosha qilasizmi? 🍿")


def send_reminder(app, uid: int, movie) -> bool:
    kb = ikb([btn("▶️ Ko'rish", f"mv:{movie['id']}", style=SUCCESS)], [btn("🔕 Eslatmani o'chirish", "svr:0", style=PRIMARY)])
    text = remind_text(movie)
    try:
        if movie["poster_id"]:
            try:
                app.bot.send_photo(uid, movie["poster_id"], text, kb)
                return True
            except TelegramError as exc:
                if isinstance(exc, Forbidden) or not exc.has("file", "photo", "identifier", "wrong type"):
                    raise
        app.bot.send_message(uid, text, kb)
        return True
    except Forbidden:
        app.db.set_blocked(uid, True)
    except TelegramError as exc:
        log.warning("Eslatma yetmadi (%s): %s", uid, exc.description)
    return False


def run_once(app) -> int:
    """Hozir eslatma kerak bo'lgan hamma foydalanuvchiga yuboradi. Yuborilganlar sonini qaytaradi."""
    sent = 0
    for row in app.db.remind_candidates(now()):
        if app.stopping.is_set():
            break
        movie = app.db.unwatched_saved(row["user_id"], row["last_movie"])
        if not movie:
            continue
        if send_reminder(app, row["user_id"], movie):
            sent += 1
        app.db.mark_reminded(row["user_id"], movie["id"])
        time.sleep(SEND_GAP)
    return sent


@router.task
def _remind_loop(app) -> None:
    while not app.stopping.wait(300):
        dt = datetime.now(TZ)
        today = dt.strftime("%Y%m%d")
        if (dt.hour, dt.minute) < (SEND_HOUR, SEND_MIN) or app.setting("remind_last") == today:
            continue
        app.set_setting("remind_last", today)
        try:
            n = run_once(app)
            log.info("Saqlangan kino eslatmasi: %s ta yuborildi", n)
        except Exception:  # noqa: BLE001
            log.exception("Eslatmalarni yuborishda xatolik")


@router.callback("svr")
def cb_toggle(ctx: Ctx) -> None:
    want = ctx.data.endswith(":1")
    on = enabled(ctx.db, ctx.user_id)
    if on != want:
        ctx.db.follow_toggle(ctx.user_id, TOPIC)
    ctx.answer("🔔 Eslatma yoqildi — kechqurun 19:30 da" if want else "🔕 Eslatma o'chirildi")
    if "photo" not in ctx.cb_message and ctx.cb_message.get("text", "").startswith("🔖 Sevimlilar"):
        from .user import edit_or_send, saved_view
        text, kb = saved_view(ctx.app, ctx.user_id)
        edit_or_send(ctx, text, kb)
