"""🏆 Oylik referal musobaqasi: eng ko'p do'st taklif qilgan 3 kishi oy oxirida Premium oladi. /reyting — jadval, /musobaqa — sozlash (admin)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import Forbidden, TelegramError
from ..utils import TZ, esc, now

log = logging.getLogger("contest")

MEDALS = ["🥇", "🥈", "🥉"]
MIN_REFS = 3                       # mukofot uchun kamida shuncha do'st (soxta akkauntlardan himoya)
PRESETS = {"a": "30,14,7", "b": "60,30,14", "c": "7,3,1"}


def month_bounds(dt: datetime):
    start = datetime(dt.year, dt.month, 1, tzinfo=TZ)
    nxt = datetime(dt.year + (dt.month == 12), dt.month % 12 + 1, 1, tzinfo=TZ)
    return int(start.timestamp()), int(nxt.timestamp())


def prize_days(app) -> list:
    raw = app.setting("contest_days") or "30,14,7"
    out = []
    for x in raw.split(","):
        x = x.strip()
        out.append(int(x) if x.isdigit() else 0)
    return (out + [0, 0, 0])[:3]


def enabled(app) -> bool:
    return app.setting("contest_on") != "0" and any(prize_days(app))


def _name(r) -> str:
    n = (r["first_name"] or "Foydalanuvchi")[:18]
    return esc(n)


def standings_text(app, uid: int) -> str:
    start, end = month_bounds(datetime.now(TZ))
    rows = app.db.top_referrers(start, end, 5)
    days = prize_days(app)
    left = (datetime.fromtimestamp(end, TZ) - datetime.now(TZ)).days
    lines = ["🏆 <b>Oylik taklif musobaqasi</b>", ""]
    if enabled(app):
        lines.append("Oy oxirigacha eng ko'p do'st taklif qilgan 3 kishi 💎 Premium oladi:")
        lines.append("   " + "  ".join(f"{MEDALS[i]} {d} kun" for i, d in enumerate(days) if d))
        lines.append(f"(mukofot uchun kamida {MIN_REFS} ta do'st kerak)")
    else:
        lines.append("Musobaqa hozir o'chiq.")
    lines.append("")
    if not rows:
        lines.append("Hali hech kim do'st taklif qilmagan — birinchi bo'ling! 🚀")
    for i, r in enumerate(rows):
        lines.append(f"{MEDALS[i] if i < 3 else f'{i + 1}.'} {_name(r)} — <b>{r['n']}</b> ta" + (" ← siz" if r["uid"] == uid else ""))
    mine = app.db.referral_count_between(uid, start, end)
    lines += ["", f"👥 Sizning bu oydagi takliflaringiz: <b>{mine}</b>", f"⏳ Oy tugashiga: {max(0, left)} kun", "",
              "Do'stlarni taklif qilish: /taklif"]
    return "\n".join(lines)


@router.command("reyting", "musobaqa_reyting", gate=False)
def cmd_rating(ctx: Ctx) -> None:
    ctx.send(standings_text(ctx.app, ctx.user_id))


# ───── admin sozlamasi ─────

def _admin_view(app):
    on = enabled(app)
    days = prize_days(app)
    text = ("🏆 <b>Oylik taklif musobaqasi</b>\n\n"
            f"Holati: <b>{'yoqilgan ✅' if on else 'o‘chiq ❌'}</b>\n"
            f"Mukofot: 🥇 {days[0]} • 🥈 {days[1]} • 🥉 {days[2]} kun Premium\n"
            f"Kamida {MIN_REFS} ta do'st kerak. Oy oxirida (1-kuni 10:00) g'oliblarga o'zi beriladi va sizga hisobot keladi.")
    rows = [[btn("⏸ O'chirish" if on else "▶️ Yoqish", "cn:tog", style=DANGER if on else SUCCESS)],
            [btn(f"🎁 {v.replace(',', '/')}", f"cn:p:{k}", style=PRIMARY) for k, v in PRESETS.items()]]
    return text, ikb(*rows)


@router.command("musobaqa", owner=True)
def cmd_contest_admin(ctx: Ctx) -> None:
    ctx.send(standings_text(ctx.app, ctx.user_id))
    ctx.send(*_admin_view(ctx.app))


@router.callback("cn", owner=True)
def cb_contest(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    if parts[1] == "tog":
        ctx.app.set_setting("contest_on", "0" if enabled(ctx.app) else "1")
    elif parts[1] == "p" and len(parts) > 2 and parts[2] in PRESETS:
        ctx.app.set_setting("contest_days", PRESETS[parts[2]])
        ctx.app.set_setting("contest_on", "1")
    ctx.answer("✅")
    ctx.edit(*_admin_view(ctx.app))


# ───── oy oxirida mukofotlash ─────

def award_month(app, year: int, month: int) -> list:
    """O'tgan oy g'oliblariga Premium beradi. [(o'rin, uid, taklif soni, kun)] qaytaradi."""
    start, end = month_bounds(datetime(year, month, 15, tzinfo=TZ))
    rows = [r for r in app.db.top_referrers(start, end, 3) if r["n"] >= MIN_REFS]
    days = prize_days(app)
    won = []
    for i, r in enumerate(rows):
        if not days[i]:
            continue
        app.db.grant_premium(r["uid"], days[i])
        won.append((i + 1, r["uid"], r["n"], days[i]))
        try:
            app.bot.send_message(r["uid"], f"{MEDALS[i]} <b>Tabriklaymiz!</b> Siz oylik taklif musobaqasida <b>{i + 1}-o'rin</b>ni egalladingiz "
                                           f"({r['n']} ta do'st).\n\n💎 Sizga <b>{days[i]} kun Premium</b> sovg'a qilindi. Rahmat! 🙏")
        except Forbidden:
            app.db.set_blocked(r["uid"], True)
        except TelegramError as exc:
            log.warning("G'olibga xabar yetmadi (%s): %s", r["uid"], exc)
    names = {r["uid"]: r for r in rows}
    if won:
        lines = [f"🏆 <b>Musobaqa yakunlandi</b> ({month:02d}.{year})", ""] + [
            f"{MEDALS[o - 1]} {_name(names[u])} (<code>{u}</code>) — {n} ta do'st → {d} kun Premium" for o, u, n, d in won]
    else:
        lines = [f"🏆 Musobaqa ({month:02d}.{year}): mukofotga arzigulik (kamida {MIN_REFS} ta do'st) ishtirokchi bo'lmadi."]
    app.notify_admins("\n".join(lines))
    return won


@router.task
def _contest_award(app) -> None:
    """Har oyning 1-kuni 10:00 (Toshkent) o'tgan oy g'oliblarini mukofotlaydi."""
    while not app.stopping.is_set():
        dt = datetime.now(TZ)
        key = f"{dt.year}-{dt.month:02d}"
        if dt.day == 1 and dt.hour >= 10 and app.setting("last_contest_award") != key and enabled(app):
            app.set_setting("last_contest_award", key)
            prev = dt.replace(day=1) - timedelta(days=1)
            try:
                award_month(app, prev.year, prev.month)
            except Exception:  # noqa: BLE001
                log.exception("Musobaqa mukofotlashda xatolik")
        if app.stopping.wait(1800):
            return
