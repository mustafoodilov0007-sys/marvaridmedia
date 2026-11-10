"""🏆 «Haftaning TOP-5»: har yakshanba kechqurun kanalga avtomatik post (shu haftada eng ko'p ko'rilgan 5 ta kino). Admin: /haftatop."""

from __future__ import annotations

import logging
from datetime import datetime

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import TelegramError
from ..utils import TZ, esc

log = logging.getLogger("weekly")

POST_HOUR = 19            # yakshanba, Toshkent vaqti
LATE_LIMIT = 5 * 3600
MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


def top_rows(app) -> list:
    rows = [r for r in app.db.weekly_top(10) if not r["is_premium"]] or list(app.db.weekly_top(5))
    return rows[:5]


def post_text(app, rows) -> str:
    lines = ["🏆 <b>Haftaning TOP-5 kinosi</b>", "", "Shu hafta eng ko'p ko'rilganlar:", ""]
    for i, r in enumerate(rows):
        bits = [str(r["year"])] if r["year"] else []
        lines.append(f"{MEDALS[i]} <b>{esc(r['title'])}</b>" + (f" ({', '.join(bits)})" if bits else "")
                     + (f" — kod <code>{r['code']}</code>" if r["code"] > 0 else ""))
    lines += ["", "Qaysi birini ko'rdingiz? 👇"]
    return "\n".join(lines)


def post_kb(app, rows) -> dict:
    btns = [[btn(f"{MEDALS[i]} {r['title'][:32]}", url=app.deep_link(r["code"], channel=True), style=PRIMARY)] for i, r in enumerate(rows) if r["code"] > 0]
    return ikb(*btns) if btns else None


def publish(app, target) -> bool:
    rows = top_rows(app)
    if not rows:
        return False
    text, kb = post_text(app, rows), post_kb(app, rows)
    first = rows[0]
    try:
        if first["poster_id"]:
            try:
                app.bot.send_photo(target, first["poster_id"], text, kb)
                return True
            except TelegramError as exc:
                if not exc.has("file", "photo", "identifier", "wrong type"):
                    raise
        app.bot.send_message(target, text, kb)
        return True
    except TelegramError as exc:
        log.error("Haftaning TOP-5 postini yuborib bo'lmadi: %s", exc)
        return False


def _week_key(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}{w:02d}"


@router.task
def _weekly_loop(app) -> None:
    while not app.stopping.wait(60):
        if not app.setting_bool("weekly_on") or not app.setting("post_channel"):
            continue
        dt = datetime.now(TZ)
        if dt.weekday() != 6 or app.setting("weekly_last") == _week_key(dt):
            continue
        due = dt.replace(hour=POST_HOUR, minute=0, second=0, microsecond=0)
        late = (dt - due).total_seconds()
        if late < 0:
            continue
        app.set_setting("weekly_last", _week_key(dt))       # kuniga ko'pi bilan bir urinish
        if late <= LATE_LIMIT:
            publish(app, app.setting("post_channel"))


def _view(app):
    on = app.setting_bool("weekly_on")
    ch = app.setting("post_channel")
    text = ("🏆 <b>Haftaning TOP-5</b>\n\n"
            f"Har yakshanba soat <b>{POST_HOUR}:00</b> da (Toshkent) kanalga shu haftaning eng ko'p ko'rilgan 5 ta kinosi poster va tugmalar bilan chiqadi.\n\n"
            f"Holat: <b>{'✅ yoniq' if on else '⏸ o‘chiq'}</b>\n"
            f"📣 Kanal: <b>{esc(ch) if ch else '❗️ sozlanmagan (⚙️ Matnlar → 📣 E’lon kanali)'}</b>")
    return text, ikb([btn("⏸ O'chirish" if on else "✅ Yoqish", "wk:tog", style=DANGER if on else SUCCESS)],
                     [btn("👀 Menga namuna", "wk:test", style=PRIMARY), btn("📣 Hozir kanalga", "wk:now", style=SUCCESS)])


@router.command("haftatop", admin=True)
def cmd_weekly(ctx: Ctx) -> None:
    ctx.send(*_view(ctx.app))


@router.callback("wk", admin=True)
def cb_weekly(ctx: Ctx) -> None:
    app = ctx.app
    act = ctx.data.split(":")[1] if ":" in ctx.data else ""
    if act == "tog":
        app.set_setting("weekly_on", "" if app.setting_bool("weekly_on") else "1")
        ctx.answer("✅ Saqlandi")
    elif act == "test":
        ok = publish(app, ctx.user_id)
        ctx.answer("👀 Yuborildi" if ok else "⚠️ Kinolar yo'q yoki yuborilmadi", alert=not ok)
        return
    elif act == "now":
        ch = app.setting("post_channel")
        ok = bool(ch) and publish(app, ch)
        ctx.answer("📣 Kanalga yuborildi" if ok else "⚠️ Kanal sozlanmagan yoki yuborilmadi", alert=not ok)
        return
    else:
        ctx.answer()
    ctx.edit(*_view(app))
