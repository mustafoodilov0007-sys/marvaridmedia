"""🏆 Oylik referal musobaqasi: eng ko'p do'st taklif qilgan 3 kishi oy oxirida Premium oladi. /reyting — jadval, /musobaqa — sozlash (admin)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import Forbidden, TelegramError
from ..utils import TZ, esc, now

log = logging.getLogger("contest")

MEDALS = ["🥇", "🥈", "🥉"]
MIN_REFS = 3                       # mukofot uchun kamida shuncha do'st (soxta akkauntlardan himoya)
MAX_PLACES = 10
DEFAULT_PRIZES = [{"t": "p", "v": 30}, {"t": "p", "v": 14}, {"t": "p", "v": 7}]


def month_bounds(dt: datetime):
    start = datetime(dt.year, dt.month, 1, tzinfo=TZ)
    nxt = datetime(dt.year + (dt.month == 12), dt.month % 12 + 1, 1, tzinfo=TZ)
    return int(start.timestamp()), int(nxt.timestamp())


def prizes(app) -> list:
    """G'oliblar mukofoti ro'yxati: [{"t": "p", "v": kun}] — Premium, [{"t": "m", "v": "50 000 so'm"}] — pul. Uzunligi = g'oliblar soni."""
    raw = app.setting("contest_prizes")
    if raw:
        try:
            data = json.loads(raw)
            out = [x for x in data if isinstance(x, dict) and x.get("t") in ("p", "m")][:MAX_PLACES]
            if out:
                return out
        except ValueError:
            pass
    return [dict(x) for x in DEFAULT_PRIZES]


def save_prizes(app, items: list) -> None:
    app.set_setting("contest_prizes", json.dumps(items[:MAX_PLACES], ensure_ascii=False))


def prize_text(pz: dict) -> str:
    return f"{int(pz['v'])} kun 💎 Premium" if pz["t"] == "p" else f"💵 {pz['v']}"


def place_mark(i: int) -> str:
    return MEDALS[i] if i < 3 else f"{i + 1}-o'rin"


def enabled(app) -> bool:
    return app.setting("contest_on") == "1"


def _name(r) -> str:
    n = (r["first_name"] or "Foydalanuvchi")[:18]
    return esc(n)


def prize_lines(app) -> list:
    return [f"{place_mark(i)} {prize_text(pz)}" for i, pz in enumerate(prizes(app))]


def standings_text(app, uid: int) -> str:
    start, end = month_bounds(datetime.now(TZ))
    pz = prizes(app)
    rows = app.db.top_referrers(start, end, max(5, len(pz)))
    left = (datetime.fromtimestamp(end, TZ) - datetime.now(TZ)).days
    lines = ["🏆 <b>Oylik taklif musobaqasi</b>", ""]
    if enabled(app):
        lines.append(f"Oy oxirigacha eng ko'p do'st taklif qilgan <b>{len(pz)} kishi</b> mukofot oladi:")
        lines += ["   " + x for x in prize_lines(app)]
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


def check_text(app, uid: int) -> str:
    """/tekshir: o'tgan oy musobaqa natijasi (g'oliblar va foydalanuvchining o'z natijasi). O'tgan oyda ishtirokchi bo'lmasa — joriy oy."""
    now_dt = datetime.now(TZ)
    prev = now_dt.replace(day=1) - timedelta(days=1)
    start, end = month_bounds(prev)
    pz = prizes(app)
    rows = app.db.top_referrers(start, end, max(len(pz), 5))
    final = bool(rows)
    if not final:
        start, end = month_bounds(now_dt)
        rows = app.db.top_referrers(start, end, max(len(pz), 5))
    period = datetime.fromtimestamp(start, TZ).strftime("%m.%Y")
    lines = [f"🔎 <b>Musobaqa natijalari</b> ({period})" + ("" if final else " — <i>davom etmoqda</i>"), ""]
    if not rows:
        lines.append("Hali hech kim do'st taklif qilmagan. Birinchi bo'ling: /taklif 🚀")
        return "\n".join(lines)
    best = rows[0]["n"]
    for i, r in enumerate(rows[:max(len(pz), 3)]):
        prize = ""
        if i < len(pz) and r["n"] >= MIN_REFS:
            prize = " → " + prize_text(pz[i])
        lines.append(f"{place_mark(i)} {_name(r)} — <b>{r['n']}</b> ta{prize}" + ("  ← siz" if r["uid"] == uid else ""))
    mine = app.db.referral_count_between(uid, start, end)
    rank = app.db.referral_rank(uid, start, end)
    lines.append("")
    if not mine:
        lines.append(f"Sizning natijangiz: <b>0 ta</b> (g'olibda {best} ta). Keyingi oy qatnashing: /taklif")
    else:
        won = rank and rank <= len(pz) and mine >= MIN_REFS
        lines.append(f"Sizning natijangiz: <b>{mine} ta</b> — {rank}-o'rin" + (f" (g'olibda {best} ta, sizda {mine} ta)" if rank > 1 else " 🏆"))
        if final and won:
            lines.append(f"🎉 <b>Tabriklaymiz, siz g'olibsiz!</b> Mukofot: {prize_text(pz[rank - 1])}")
        elif mine < MIN_REFS:
            lines.append(f"Mukofot uchun kamida {MIN_REFS} ta do'st kerak edi.")
        elif final:
            lines.append("Keyingi oy yana urinib ko'ring: /taklif 💪")
    return "\n".join(lines)


@router.command("tekshir", "natija", gate=False)
def cmd_check(ctx: Ctx) -> None:
    ctx.send(check_text(ctx.app, ctx.user_id))


# ───── kanalga e'lon ─────

def announce_text(app) -> str:
    start, end = month_bounds(datetime.now(TZ))
    last = datetime.fromtimestamp(end - 1, TZ).strftime("%d.%m.%Y")
    lines = ["🏆 <b>Oylik taklif musobaqasi boshlandi!</b>", "",
             f"Do'stlaringizni botimizga taklif qiling — <b>{last}</b> gacha eng ko'p taklif qilgan <b>{len(prizes(app))} kishi</b> mukofot oladi:", ""]
    lines += [f"{x}" for x in prize_lines(app)]
    lines += ["", "<b>Qanday qatnashiladi?</b>",
              f"1️⃣ Botni oching: @{app.bot_username}", "2️⃣ /taklif buyrug'ini yuboring va shaxsiy havolangizni oling",
              "3️⃣ Havolani do'stlaringizga yuboring — har biri botga kirsa, sizga ham, unga ham +1 kun Premium sovg'a 🎁", "",
              "📊 Hozirgi reyting: /reyting", f"(mukofot uchun kamida {MIN_REFS} ta do'st taklif qilish kerak)", "",
              "G'oliblar har oyning 1-kuni e'lon qilinadi. Omad! 🍀"]
    return "\n".join(lines)


def announce_winners_text(app, year: int, month: int, won: list, names: dict) -> str:
    months = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun", "Iyul", "Avgust", "Sentabr", "Oktyabr", "Noyabr", "Dekabr"]
    lines = [f"🏆 <b>{months[month]} oyi musobaqasi g'oliblari!</b>", ""]
    for o, u, n, p in won:
        lines.append(f"{place_mark(o - 1)} <b>{_name(names[u])}</b> — {n} ta do'st → {prize_text(p)}")
    lines += ["", "Tabriklaymiz! 🎉 Mukofotlar g'oliblarga yuborildi.", "",
              f"Keyingi musobaqaga qatnashing: @{app.bot_username} → /taklif", "📊 Natijani tekshirish: /tekshir"]
    return "\n".join(lines)


def announce_winners(app, year: int, month: int, won: list, names: dict) -> bool:
    """G'oliblar e'lonini kanalga yuboradi (kanal belgilangan bo'lsa)."""
    channel = app.setting("post_channel")
    if not channel or app.setting("contest_post_winners") == "0":
        return False
    kb = ikb([{"text": "🤖 Botda qatnashish", "url": f"https://t.me/{app.bot_username}?start=taklif"}])
    try:
        app.bot.send_message(channel, announce_winners_text(app, year, month, won, names), kb)
        return True
    except TelegramError as exc:
        log.error("G'oliblar e'loni kanalga yuborilmadi: %s", exc)
        return False


def announce_contest(app):
    """E'lonni kanalga yuboradi. (True, "") yoki (False, sabab)."""
    channel = app.setting("post_channel")
    if not channel:
        return False, "E'lon kanali belgilanmagan (Matnlar → 📣 E'lon kanali)."
    kb = ikb([{"text": "🤖 Botda qatnashish", "url": f"https://t.me/{app.bot_username}?start=taklif"}])
    try:
        app.bot.send_message(channel, announce_text(app), kb)
        return True, ""
    except TelegramError as exc:
        log.error("Musobaqa e'loni kanalga yuborilmadi: %s", exc)
        return False, exc.description


# ───── admin sozlamasi ─────

def _admin_view(app):
    on = enabled(app)
    pz = prizes(app)
    text = ("🏆 <b>Oylik taklif musobaqasi</b>\n\n"
            f"Holati: <b>{'yoqilgan ✅' if on else 'o‘chiq ❌'}</b>\n"
            f"G'oliblar soni: <b>{len(pz)}</b>\n" + "\n".join(f"   {x}" for x in prize_lines(app)) + "\n\n"
            f"Kamida {MIN_REFS} ta do'st kerak. Oy oxirida (1-kuni 10:00) g'oliblarga mukofot beriladi: Premium — o'zi, "
            "pul mukofoti — sizga hisobot keladi, o'zingiz to'laysiz.\n\n"
            "Yoqsangiz — «Musobaqa boshlandi» e'loni kanalga avtomatik yuboriladi.")
    rows = [[btn("⏸ O'chirish" if on else "▶️ Yoqish va kanalga e'lon qilish", "cn:tog", style=DANGER if on else SUCCESS)],
            [btn("➖ O'rin", "cn:del", style=PRIMARY), btn(f"{len(pz)} ta g'olib", "cn:noop", style=PRIMARY), btn("➕ O'rin", "cn:add", style=PRIMARY)]]
    for i, p in enumerate(pz):
        rows.append([btn(f"✏️ {place_mark(i)}: {prize_text(p)}", f"cn:e:{i}", style=SUCCESS)])
    if on:
        rows.append([btn("📣 Kanalga qayta e'lon qilish", "cn:ann", style=PRIMARY)])
    return text, ikb(*rows)


@router.command("musobaqa", owner=True)
def cmd_contest_admin(ctx: Ctx) -> None:
    ctx.send(standings_text(ctx.app, ctx.user_id))
    ctx.send(*_admin_view(ctx.app))


@router.callback("cn", owner=True)
def cb_contest(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    act = parts[1] if len(parts) > 1 else ""
    pz = prizes(app)
    if act == "tog":
        if enabled(app):
            app.set_setting("contest_on", "0")
            ctx.answer("⏸ O'chirildi")
        else:
            app.set_setting("contest_on", "1")
            ok, why = announce_contest(app)
            ctx.answer("▶️ Yoqildi" + (" va kanalga e'lon qilindi" if ok else ""))
            if not ok:
                ctx.send(f"⚠️ Musobaqa yoqildi, lekin e'lon kanalga yuborilmadi: {esc(why)}")
    elif act == "ann":
        ok, why = announce_contest(app)
        ctx.answer("📣 Yuborildi" if ok else "⚠️ Yuborilmadi", alert=not ok)
        if not ok:
            ctx.send(f"⚠️ E'lon yuborilmadi: {esc(why)}")
        return
    elif act == "add" and len(pz) < MAX_PLACES:
        pz.append({"t": "p", "v": 3})
        save_prizes(app, pz)
        ctx.answer("➕")
    elif act == "del" and len(pz) > 1:
        pz.pop()
        save_prizes(app, pz)
        ctx.answer("➖")
    elif act == "e" and len(parts) > 2 and parts[2].isdigit() and int(parts[2]) < len(pz):
        i = int(parts[2])
        ctx.answer()
        ctx.edit(f"✏️ <b>{place_mark(i)}</b> mukofoti — turini tanlang:",
                 ikb([btn("💎 Premium (kun)", f"cn:t:{i}:p", style=SUCCESS), btn("💵 Pul mukofoti", f"cn:t:{i}:m", style=PRIMARY)],
                     [btn("⬅️ Orqaga", "cn:back", style=DANGER)]))
        return
    elif act == "t" and len(parts) > 3 and parts[2].isdigit() and parts[3] in ("p", "m"):
        ctx.answer()
        ctx.set_state("cn:in", place=int(parts[2]), kind=parts[3])
        ask = ("Necha kun Premium? Raqam yuboring (masalan <code>30</code>)." if parts[3] == "p" else
               "Pul mukofoti matnini yuboring (masalan <code>50 000 so'm</code> yoki <code>$10</code>).")
        ctx.send(f"✏️ <b>{place_mark(int(parts[2]))}</b>: {ask}", ikb([btn("❌ Bekor qilish", "cancel", style=DANGER)]))
        return
    elif act == "noop":
        ctx.answer()
        return
    else:
        ctx.answer()
    ctx.edit(*_admin_view(app))


@router.state("cn:in", admin=True)
def st_prize_input(ctx: Ctx) -> None:
    if not ctx.is_owner:
        ctx.clear_state()
        return
    app = ctx.app
    place, kind = ctx.sdata.get("place", 0), ctx.sdata.get("kind", "p")
    text = ctx.text.strip()
    pz = prizes(app)
    if place >= len(pz):
        ctx.clear_state()
        return
    if kind == "p":
        if not text.isdigit() or not 1 <= int(text) <= 365:
            ctx.send("❗️ 1 dan 365 gacha kun sonini yuboring.")
            return
        pz[place] = {"t": "p", "v": int(text)}
    else:
        if not text or len(text) > 40 or text.startswith("/"):
            ctx.send("❗️ Mukofot matnini yuboring (40 belgigacha), masalan <code>50 000 so'm</code>.")
            return
        pz[place] = {"t": "m", "v": text}
    save_prizes(app, pz)
    ctx.clear_state()
    ctx.send("✅ Saqlandi.")
    ctx.send(*_admin_view(app))


# ───── oy oxirida mukofotlash ─────

def award_month(app, year: int, month: int) -> list:
    """O'tgan oy g'oliblarini mukofotlaydi: Premium — darhol, pul — adminga hisobot. [(o'rin, uid, taklif soni, mukofot)] qaytaradi."""
    start, end = month_bounds(datetime(year, month, 15, tzinfo=TZ))
    pz = prizes(app)
    rows = [r for r in app.db.top_referrers(start, end, len(pz)) if r["n"] >= MIN_REFS]
    won = []
    for i, r in enumerate(rows):
        p = pz[i]
        won.append((i + 1, r["uid"], r["n"], p))
        if p["t"] == "p":
            app.db.grant_premium(r["uid"], int(p["v"]))
            body = f"💎 Sizga <b>{int(p['v'])} kun Premium</b> sovg'a qilindi. Rahmat! 🙏"
        else:
            body = f"💵 Mukofotingiz: <b>{esc(p['v'])}</b>. Administrator tez orada siz bilan bog'lanadi. Rahmat! 🙏"
        try:
            app.bot.send_message(r["uid"], f"{place_mark(i)} <b>Tabriklaymiz!</b> Siz oylik taklif musobaqasida <b>{i + 1}-o'rin</b>ni "
                                           f"egalladingiz ({r['n']} ta do'st).\n\n{body}")
        except Forbidden:
            app.db.set_blocked(r["uid"], True)
        except TelegramError as exc:
            log.warning("G'olibga xabar yetmadi (%s): %s", r["uid"], exc)
    if won:
        names = {r["uid"]: r for r in rows}
        lines = [f"🏆 <b>Musobaqa yakunlandi</b> ({month:02d}.{year})", ""]
        for o, u, n, p in won:
            who = f"{_name(names[u])} (<code>{u}</code>)"
            lines.append(f"{place_mark(o - 1)} {who} — {n} ta do'st → " + ("Premium berildi: " if p["t"] == "p" else "<b>⚠️ PUL TO'LANADI:</b> ") + prize_text(p))
        if any(p["t"] == "m" for _, _, _, p in won):
            lines += ["", "💵 Pul mukofotlarini o'zingiz to'lab, g'oliblar bilan bog'laning (foydalanuvchi nomi/ID yuqorida)."]
    else:
        lines = [f"🏆 Musobaqa ({month:02d}.{year}): mukofotga arzigulik (kamida {MIN_REFS} ta do'st) ishtirokchi bo'lmadi."]
    app.notify_admins("\n".join(lines))
    if won:
        announce_winners(app, year, month, won, {r["uid"]: r for r in rows})
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
