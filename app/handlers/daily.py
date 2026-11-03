"""📅 «Kun kinosi»: har kuni belgilangan vaqtda kanalga avtomatik post (haftaning mashhur kinolaridan, takrorlanmasdan)."""

from __future__ import annotations

import logging
import random
from datetime import datetime

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import TelegramError
from ..utils import TZ, esc, post_link
from .admin_movies import announce_kb, announce_text

log = logging.getLogger("daily")

TIMES = ("12:00", "18:00", "19:00", "20:00", "21:00", "22:00")
LATE_LIMIT = 4 * 3600       # bot o'chiq bo'lib qolgan bo'lsa: belgilangan vaqtdan 4 soat o'tguncha hali joylaydi
REMEMBER = 40               # oxirgi shuncha kino qayta tanlanmaydi


def _history(app) -> list:
    return [int(x) for x in app.setting("daily_history").split(",") if x.strip().isdigit()]


def pick_movie(app):
    """Haftaning mashhurlaridan, yaqinda joylanmagan, posterli va Premiumsiz kinoni tanlaydi."""
    db = app.db
    seen = set(_history(app))
    pool = [r for r in db.weekly_top(30) if r["id"] not in seen]
    good = [r for r in pool if r["poster_id"] and not r["is_premium"]] or [r for r in pool if not r["is_premium"]] or pool
    if not good:   # hammasi ishlatilgan — tarixni tozalab, umumiy topdan
        good = [r for r in db.top_movies(30, include_premium=False)]
    if not good:
        return None
    return db.get_movie(random.choice(good[:8])["id"])


def publish(app, movie, channel: str, chat=None):
    """Postni kanalga (yoki sinov uchun adminga) yuboradi; yuborilgan xabarni qaytaradi."""
    target = chat or channel
    text = "📅 <b>Kun kinosi</b>\n\n" + announce_text(app, movie, app.db.count_parts(movie["id"]))
    kb = announce_kb(app, movie)
    if movie["poster_id"]:
        try:
            return app.bot.send_photo(target, movie["poster_id"], text, kb)
        except TelegramError as exc:
            if not exc.has("file", "photo", "identifier", "wrong type"):
                raise
    return app.bot.send_message(target, text, kb)


def post_daily(app, auto: bool = True):
    """Kun kinosini kanalga joylaydi. Muvaffaqiyatli bo'lsa (movie, xabar), aks holda None qaytaradi."""
    channel = app.setting("post_channel")
    if not channel:
        return None
    movie = pick_movie(app)
    if not movie:
        log.warning("Kun kinosi uchun kino topilmadi (baza bo'sh)")
        return None
    try:
        sent = publish(app, movie, channel)
    except TelegramError as exc:
        log.error("Kun kinosi kanalga yuborilmadi: %s", exc)
        return None
    app.set_setting("daily_last", datetime.now(TZ).strftime("%Y%m%d"))
    app.set_setting("daily_history", ",".join(str(i) for i in ([movie["id"]] + _history(app))[:REMEMBER]))
    link = post_link(sent.get("chat") or {}, sent.get("message_id"))
    for uid in app.config.owners:
        app.bot.safe("sendMessage", {"chat_id": uid, "parse_mode": "HTML", "disable_web_page_preview": True,
                                     "text": f"📅 Kun kinosi joylandi{' (avtomatik)' if auto else ''}: <b>{esc(movie['title'])}</b>"
                                             + (f"\n{link}" if link else "")})
    return movie, sent


@router.task
def _daily_loop(app) -> None:
    while not app.stopping.wait(45):
        if not app.setting_bool("daily_on"):
            continue
        now_dt = datetime.now(TZ)
        if app.setting("daily_last") == now_dt.strftime("%Y%m%d"):
            continue
        hh, _, mm = (app.setting("daily_time") or "20:00").partition(":")
        due = now_dt.replace(hour=int(hh or 20), minute=int(mm or 0), second=0, microsecond=0)
        late = (now_dt - due).total_seconds()
        if late < 0:
            continue
        if late > LATE_LIMIT:      # juda kech — bugun o'tkazib yuboramiz (ertaga o'z vaqtida)
            app.set_setting("daily_last", now_dt.strftime("%Y%m%d"))
            continue
        if not post_daily(app, auto=True):
            app.set_setting("daily_last", now_dt.strftime("%Y%m%d"))   # xato bo'lsa ham kuniga bir marta urinadi


def view(ctx: Ctx):
    app = ctx.app
    on = app.setting_bool("daily_on")
    t = app.setting("daily_time") or "20:00"
    ch = app.setting("post_channel")
    last = app.setting("daily_last")
    lines = ["📅 <b>Kun kinosi</b>", "",
             "Har kuni belgilangan vaqtda kanalga haftaning mashhur kinolaridan biri chiroyli post bo'lib chiqadi "
             "(takrorlanmaydi).", "",
             f"Holat: <b>{'✅ yoniq' if on else '⏸ o‘chiq'}</b>",
             f"🕗 Vaqt: <b>{t}</b> (Toshkent)",
             f"📣 Kanal: <b>{esc(ch) if ch else '❗️ sozlanmagan (⚙️ Matnlar → 📣 E’lon kanali)'}</b>",
             f"🗓 Oxirgi post: <b>{last[6:]}.{last[4:6]}.{last[:4]}</b>" if len(last) == 8 else "🗓 Oxirgi post: —"]
    rows = [[btn("⏸ O'chirish" if on else "✅ Yoqish", "kk:tog", style=DANGER if on else SUCCESS)],
            [btn(("• " if x == t else "") + x, f"kk:t:{x.replace(':', '')}", style=PRIMARY) for x in TIMES[:3]],
            [btn(("• " if x == t else "") + x, f"kk:t:{x.replace(':', '')}", style=PRIMARY) for x in TIMES[3:]],
            [btn("👀 Menga namuna", "kk:test", style=PRIMARY), btn("📣 Hozir kanalga", "kk:now", style=SUCCESS)]]
    return "\n".join(lines), ikb(*rows)


@router.command("kunkino", admin=True)
def cmd_daily(ctx: Ctx) -> None:
    text, kb = view(ctx)
    ctx.send(text, kb)


@router.callback("kk", admin=True)
def cb_daily(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    if action == "tog":
        app.set_setting("daily_on", "" if app.setting_bool("daily_on") else "1")
        if app.setting_bool("daily_on") and not app.setting("daily_time"):
            app.set_setting("daily_time", "20:00")
        ctx.answer("✅ Saqlandi")
    elif action == "t" and len(parts) > 2 and parts[2].isdigit() and len(parts[2]) == 4:
        app.set_setting("daily_time", f"{parts[2][:2]}:{parts[2][2:]}")
        ctx.answer("🕗 Vaqt o'zgardi")
    elif action == "test":
        movie = pick_movie(app)
        if not movie:
            ctx.answer("😔 Kino topilmadi", alert=True)
            return
        ctx.answer()
        try:
            publish(app, movie, "", chat=ctx.chat_id)
        except TelegramError as exc:
            ctx.send(f"❌ Namuna yuborilmadi: {esc(exc.description)}")
        return
    elif action == "now":
        if not app.setting("post_channel"):
            ctx.answer("❗️ E'lon kanali sozlanmagan", alert=True)
            return
        ctx.answer("📣 Yuborilmoqda...")
        if not post_daily(app, auto=False):
            ctx.send("❌ Kanalga yuborib bo'lmadi. Bot kanalda admin ekanini tekshiring.")
        return
    text, kb = view(ctx)
    ctx.edit(text, kb)
