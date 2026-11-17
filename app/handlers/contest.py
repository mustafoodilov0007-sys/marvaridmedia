"""🏆 Taklif musobaqasi: admin muddatni (1/2/3/7 kun, 1 oy yoki o'zi yozgan), g'oliblar sonini va mukofotni (Premium yoki pul) tayinlaydi.
Yoqilganda kanalga e'lon boradi; muddat tugagach g'oliblar o'zi mukofotlanadi. /reyting — jadval, /tekshir — natija, /musobaqa — sozlash."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import Forbidden, TelegramError
from ..utils import TZ, esc, now

log = logging.getLogger("contest")

MEDALS = ["🥇", "🥈", "🥉"]
MIN_REFS = 3                       # mukofot uchun kamida shuncha do'st (soxta akkauntlardan himoya)
MAX_PLACES = 10
MAX_DAYS = 90
LEN_PRESETS = [1, 2, 3, 7, 30]
DEFAULT_PRIZES = [{"t": "p", "v": 30}, {"t": "p", "v": 14}, {"t": "p", "v": 7}]


# ───── mukofotlar ─────

def prizes(app) -> list:
    """[{"t": "p", "v": kun}] — Premium, [{"t": "m", "v": "50 000 so'm"}] — pul. Ro'yxat uzunligi = g'oliblar soni."""
    raw = app.setting("contest_prizes")
    if raw:
        try:
            out = [x for x in json.loads(raw) if isinstance(x, dict) and x.get("t") in ("p", "m")][:MAX_PLACES]
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


def prize_lines(app) -> list:
    return [f"{place_mark(i)} {prize_text(pz)}" for i, pz in enumerate(prizes(app))]


def _name(r) -> str:
    return esc((r["first_name"] or "Foydalanuvchi")[:18])


# ───── muddat ─────

def contest_len(app) -> int:
    raw = app.setting("contest_len")
    return max(1, min(MAX_DAYS, int(raw))) if raw.isdigit() else 30


def human_len(days: int) -> str:
    return "1 oy" if days == 30 else f"{days} kun"


def enabled(app) -> bool:
    return app.setting("contest_on") == "1"


def active_period(app):
    """Hozirgi musobaqaning (boshlanishi, tugashi) — faol bo'lmasa None."""
    if not enabled(app):
        return None
    s, e = app.setting("contest_start"), app.setting("contest_end")
    return (int(s), int(e)) if s.isdigit() and e.isdigit() else None


def last_period(app):
    s, e = app.setting("contest_last_start"), app.setting("contest_last_end")
    return (int(s), int(e)) if s.isdigit() and e.isdigit() else None


def fmt_dt(ts: int) -> str:
    return datetime.fromtimestamp(ts, TZ).strftime("%d.%m.%Y %H:%M")


def left_text(end: int) -> str:
    sec = max(0, end - now())
    d, h, m = sec // 86400, sec % 86400 // 3600, sec % 3600 // 60
    if d:
        return f"{d} kun {h} soat"
    return f"{h} soat {m} daqiqa" if h else f"{m} daqiqa"


# ───── jadval va natija ─────

def standings_text(app, uid: int) -> str:
    per = active_period(app)
    pz = prizes(app)
    lines = ["🏆 <b>Taklif musobaqasi</b>", ""]
    if not per:
        lines.append("Hozir musobaqa yo'q." + (" So'nggi natija: /tekshir" if last_period(app) else ""))
        return "\n".join(lines)
    start, end = per
    rows = app.db.top_referrers(start, end, max(5, len(pz)))
    lines.append(f"Eng ko'p do'st taklif qilgan <b>{len(pz)} kishi</b> mukofot oladi:")
    lines += ["   " + x for x in prize_lines(app)]
    lines.append(f"(mukofot uchun kamida {MIN_REFS} ta do'st kerak)")
    lines += ["", f"⏳ Tugashiga: <b>{left_text(end)}</b> ({fmt_dt(end)})", ""]
    if not rows:
        lines.append("Hali hech kim do'st taklif qilmagan — birinchi bo'ling! 🚀")
    for i, r in enumerate(rows):
        lines.append(f"{MEDALS[i] if i < 3 else f'{i + 1}.'} {_name(r)} — <b>{r['n']}</b> ta" + (" ← siz" if r["uid"] == uid else ""))
    lines += ["", f"👥 Sizning takliflaringiz: <b>{app.db.referral_count_between(uid, start, end)}</b>", "", "Do'stlarni taklif qilish: /taklif"]
    return "\n".join(lines)


@router.command("reyting", "musobaqa_reyting", gate=False)
def cmd_rating(ctx: Ctx) -> None:
    ctx.send(standings_text(ctx.app, ctx.user_id))


def check_text(app, uid: int) -> str:
    """/tekshir: faol musobaqa bo'lsa — hozirgi holat, aks holda so'nggi tugagan musobaqa natijasi (g'oliblar va foydalanuvchining o'z natijasi)."""
    per = active_period(app)
    final = per is None
    per = per or last_period(app)
    pz = prizes(app)
    if not per:
        return "🔎 Hozircha musobaqa o'tkazilmagan. Yangisi boshlanganda e'lon qilamiz!"
    start, end = per
    rows = app.db.top_referrers(start, end, max(len(pz), 5))
    lines = [f"🔎 <b>Musobaqa natijalari</b> ({fmt_dt(start)[:10]} — {fmt_dt(end)[:10]})" + ("" if final else " — <i>davom etmoqda</i>"), ""]
    if not rows:
        lines.append("Hech kim do'st taklif qilmagan. Keyingisida birinchi bo'ling: /taklif 🚀")
        return "\n".join(lines)
    best = rows[0]["n"]
    for i, r in enumerate(rows[:max(len(pz), 3)]):
        prize = " → " + prize_text(pz[i]) if i < len(pz) and r["n"] >= MIN_REFS else ""
        lines.append(f"{place_mark(i)} {_name(r)} — <b>{r['n']}</b> ta{prize}" + ("  ← siz" if r["uid"] == uid else ""))
    mine = app.db.referral_count_between(uid, start, end)
    rank = app.db.referral_rank(uid, start, end)
    lines.append("")
    if not mine:
        lines.append(f"Sizning natijangiz: <b>0 ta</b> (g'olibda {best} ta). Keyingisida qatnashing: /taklif")
    else:
        won = rank and rank <= len(pz) and mine >= MIN_REFS
        lines.append(f"Sizning natijangiz: <b>{mine} ta</b> — {rank}-o'rin" + (f" (g'olibda {best} ta, sizda {mine} ta)" if rank > 1 else " 🏆"))
        if final and won:
            lines.append(f"🎉 <b>Tabriklaymiz, siz g'olibsiz!</b> Mukofot: {prize_text(pz[rank - 1])}")
        elif mine < MIN_REFS:
            lines.append(f"Mukofot uchun kamida {MIN_REFS} ta do'st kerak{' edi' if final else ''}.")
        elif final:
            lines.append("Keyingisida yana urinib ko'ring: /taklif 💪")
    return "\n".join(lines)


@router.command("tekshir", "natija", gate=False)
def cmd_check(ctx: Ctx) -> None:
    ctx.send(check_text(ctx.app, ctx.user_id))


# ───── kanalga e'lonlar ─────

def _channel_kb(app):
    return ikb([{"text": "🤖 Botda qatnashish", "url": f"https://t.me/{app.bot_username}?start=taklif"}])


def announce_text(app) -> str:
    per = active_period(app) or (now(), now() + contest_len(app) * 86400)
    lines = ["🏆 <b>Taklif musobaqasi boshlandi!</b>", "",
             f"Do'stlaringizni botimizga taklif qiling — <b>{fmt_dt(per[1])}</b> gacha ({human_len(contest_len(app))}) eng ko'p taklif qilgan "
             f"<b>{len(prizes(app))} kishi</b> mukofot oladi:", ""]
    lines += prize_lines(app)
    lines += ["", "<b>Qanday qatnashiladi?</b>", f"1️⃣ Botni oching: @{app.bot_username}",
              "2️⃣ /taklif buyrug'ini yuboring va shaxsiy havolangizni oling",
              "3️⃣ Havolani do'stlaringizga yuboring — har biri botga kirsa, sizga ham, unga ham +1 kun Premium sovg'a 🎁", "",
              "📊 Hozirgi reyting: /reyting", f"(mukofot uchun kamida {MIN_REFS} ta do'st taklif qilish kerak)", "",
              "G'oliblar muddat tugashi bilan e'lon qilinadi. Omad! 🍀"]
    return "\n".join(lines)


def delete_announcement(app) -> bool:
    """Kanaldagi oldingi «musobaqa boshlandi» e'lonini o'chiradi (xato kiritilgan bo'lsa yoki qayta e'lon qilinayotganda)."""
    ref = app.setting("contest_ann")
    app.set_setting("contest_ann", "")
    if ":" not in ref:
        return False
    chat, _, mid = ref.rpartition(":")
    if not mid.isdigit():
        return False
    return bool(app.bot.safe("deleteMessage", {"chat_id": chat, "message_id": int(mid)}))


def announce_contest(app):
    channel = app.setting("post_channel")
    if not channel:
        return False, "E'lon kanali belgilanmagan (Matnlar → 📣 E'lon kanali)."
    delete_announcement(app)                              # eski e'lon qolib ketmasin — yangisi uning o'rnida chiqadi
    try:
        sent = app.bot.send_message(channel, announce_text(app), _channel_kb(app))
        if isinstance(sent, dict) and sent.get("message_id"):
            app.set_setting("contest_ann", f"{channel}:{sent['message_id']}")
        return True, ""
    except TelegramError as exc:
        log.error("Musobaqa e'loni kanalga yuborilmadi: %s", exc)
        return False, exc.description
    except Exception as exc:  # noqa: BLE001 — tarmoq xatosi musobaqa boshlanishini buzmasin
        log.exception("Musobaqa e'loni yuborilmadi")
        return False, str(exc)[:200]


def announce_winners_text(app, start: int, end: int, won: list, names: dict) -> str:
    lines = [f"🏆 <b>Musobaqa g'oliblari!</b> ({fmt_dt(start)[:10]} — {fmt_dt(end)[:10]})", ""]
    for o, u, n, p in won:
        lines.append(f"{place_mark(o - 1)} <b>{_name(names[u])}</b> — {n} ta do'st → {prize_text(p)}")
    lines += ["", "Tabriklaymiz! 🎉 Mukofotlar g'oliblarga yuborildi.", "",
              f"Keyingi musobaqaga qatnashing: @{app.bot_username} → /taklif", "📊 Natijani tekshirish: /tekshir"]
    return "\n".join(lines)


def announce_winners(app, start: int, end: int, won: list, names: dict) -> bool:
    channel = app.setting("post_channel")
    if not channel or app.setting("contest_post_winners") == "0":
        return False
    try:
        app.bot.send_message(channel, announce_winners_text(app, start, end, won, names), _channel_kb(app))
        return True
    except TelegramError as exc:
        log.error("G'oliblar e'loni kanalga yuborilmadi: %s", exc)
        return False


# ───── boshlash / yakunlash ─────

def start_contest(app):
    t = now()
    app.set_setting("contest_start", str(t))
    app.set_setting("contest_end", str(t + contest_len(app) * 86400))
    app.set_setting("contest_on", "1")
    return announce_contest(app)


def award_period(app, start: int, end: int, exclude=()) -> list:
    """[start, end) oralig'idagi g'oliblarni mukofotlaydi: Premium — darhol, pul — adminga hisobot. [(o'rin, uid, soni, mukofot)].
    exclude — admin chiqarib tashlagan (firibgar) foydalanuvchilar: ularning o'rniga keyingilar o'tadi."""
    pz = prizes(app)
    skip = {int(x) for x in exclude}
    rows = [r for r in app.db.top_referrers(start, end, len(pz) + len(skip)) if r["n"] >= MIN_REFS and r["uid"] not in skip][:len(pz)]
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
            app.bot.send_message(r["uid"], f"{place_mark(i)} <b>Tabriklaymiz!</b> Siz taklif musobaqasida <b>{i + 1}-o'rin</b>ni "
                                           f"egalladingiz ({r['n']} ta do'st).\n\n{body}")
        except Forbidden:
            app.db.set_blocked(r["uid"], True)
        except TelegramError as exc:
            log.warning("G'olibga xabar yetmadi (%s): %s", r["uid"], exc)
    names = {r["uid"]: r for r in rows}
    if won:
        lines = [f"🏆 <b>Musobaqa yakunlandi</b> ({fmt_dt(start)[:10]} — {fmt_dt(end)[:10]})", ""]
        for o, u, n, p in won:
            lines.append(f"{place_mark(o - 1)} {_name(names[u])} (<code>{u}</code>) — {n} ta do'st → "
                         + ("Premium berildi: " if p["t"] == "p" else "<b>⚠️ PUL TO'LANADI:</b> ") + prize_text(p))
        if any(p["t"] == "m" for _, _, _, p in won):
            lines += ["", "💵 Pul mukofotlarini o'zingiz to'lab, g'oliblar bilan bog'laning (foydalanuvchi nomi/ID yuqorida)."]
    else:
        lines = [f"🏆 Musobaqa ({fmt_dt(start)[:10]} — {fmt_dt(end)[:10]}): mukofotga arzigulik (kamida {MIN_REFS} ta do'st) ishtirokchi bo'lmadi."]
    app.notify_admins("\n".join(lines))
    if won:
        announce_winners(app, start, end, won, names)
    return won


# ───── g'oliblarni qo'lda tasdiqlash ─────

def approval_on(app) -> bool:
    return app.setting("contest_approve") != "0"        # standart: yoqilgan


def _candidates(app, start: int, end: int) -> list:
    pz = prizes(app)
    return [r for r in app.db.top_referrers(start, end, len(pz) + 4) if r["n"] >= MIN_REFS]


def _pending(app):
    try:
        d = json.loads(app.setting("contest_pending") or "")
        return d if isinstance(d, dict) and "start" in d else None
    except ValueError:
        return None


def _save_pending(app, d) -> None:
    app.set_setting("contest_pending", json.dumps(d) if d else "")


def pending_view(app):
    d = _pending(app)
    if not d:
        return "Tasdiqlashni kutayotgan musobaqa yo'q.", ikb()
    pz, skip = prizes(app), {int(x) for x in d["ex"]}
    rows = _candidates(app, d["start"], d["end"])
    lines = [f"🏆 Musobaqa ({fmt_dt(d['start'])[:10]} — {fmt_dt(d['end'])[:10]})", ""]
    kb, place = [], 0
    for r in rows:
        out = r["uid"] in skip
        if not out and place < len(pz):
            tag = f"{place_mark(place)} → {prize_text(pz[place])}"
            place += 1
        else:
            tag = "🚫 chiqarilgan" if out else "zaxira"
        lines.append(f"• {_name(r)} (<code>{r['uid']}</code>) — <b>{r['n']}</b> ta do'st · {tag}")
        kb.append([btn(("↩️ Qaytarish: " if out else "🚫 Chiqarish: ") + (r["first_name"] or str(r["uid"]))[:24], f"cn:px:{r['uid']}",
                       style=PRIMARY if out else DANGER)])
    lines += ["", "Shubhali (soxta akkaunt) ishtirokchini chiqaring — o'rniga keyingisi o'tadi. Tayyor bo'lsa «Tasdiqlash» ni bosing."]
    kb.append([btn("✅ Tasdiqlash va mukofotlash", "cn:pok", style=SUCCESS), btn("🗑 Mukofotsiz yopish", "cn:pno", style=DANGER)])
    return "\n".join(lines), ikb(*kb)


def finish_contest(app, award: bool = True) -> list:
    """Faol musobaqani tugatadi. award=True — g'oliblarni mukofotlaydi; False — bekor qilish (mukofotsiz, kanaldagi e'lon ham o'chiriladi)."""
    per = active_period(app)
    if not per:
        return []
    if not award:
        delete_announcement(app)
    start, end = per[0], min(per[1], now())
    app.set_setting("contest_on", "0")
    app.set_setting("contest_last_start", str(per[0]))
    app.set_setting("contest_last_end", str(end))
    if not award:
        return []
    if approval_on(app) and _candidates(app, start, end):
        _save_pending(app, {"start": start, "end": end, "ex": []})
        text, kb = pending_view(app)
        for oid in app.config.owners:
            try:
                app.bot.send_message(oid, "⏳ <b>Musobaqa tugadi — g'oliblarni tasdiqlang</b>\n\n" + text, kb)
            except TelegramError as exc:
                log.warning("Tasdiqlash so'rovi yetmadi (%s): %s", oid, exc)
        return []
    return award_period(app, start, end)


@router.task
def _contest_watch(app) -> None:
    """Har daqiqada: muddati tugagan musobaqani o'zi yakunlaydi va g'oliblarni mukofotlaydi."""
    while not app.stopping.is_set():
        per = active_period(app)
        if per and now() >= per[1]:
            try:
                finish_contest(app, award=True)
            except Exception:  # noqa: BLE001
                log.exception("Musobaqani yakunlashda xatolik")
        if app.stopping.wait(60):
            return


# ───── admin sozlamasi ─────

def _admin_view(app):
    per = active_period(app)
    pz = prizes(app)
    ln = contest_len(app)
    state = (f"yoqilgan ✅ — tugashi: <b>{fmt_dt(per[1])}</b> (qoldi {left_text(per[1])})" if per else "o‘chiq ❌")
    text = ("🏆 <b>Taklif musobaqasi</b>\n\n"
            f"Holati: <b>{state}</b>\n"
            f"Davomiyligi: <b>{human_len(ln)}</b>\n"
            f"G'oliblar soni: <b>{len(pz)}</b>\n" + "\n".join(f"   {x}" for x in prize_lines(app)) + "\n\n"
            f"Kamida {MIN_REFS} ta do'st kerak. Yoqsangiz — «Musobaqa boshlandi» e'loni kanalga yuboriladi; muddat tugagach g'oliblar o'zi "
            "aniqlanadi: Premium avtomatik beriladi, pul mukofoti bo'yicha sizga hisobot keladi (pulni o'zingiz to'laysiz).")
    rows = []
    if per:
        rows.append([btn("🏁 Yakunlash (mukofotlash)", "cn:fin", style=SUCCESS), btn("❌ Bekor qilish", "cn:cx", style=DANGER)])
        rows.append([btn("🔄 Qayta boshlash (eskisi bekor)", "cn:rs", style=PRIMARY)])
        rows.append([btn("📣 Kanalga qayta e'lon qilish", "cn:ann", style=PRIMARY), btn("🗑 Kanaldagi e'lonni o'chirish", "cn:dann", style=DANGER)])
    else:
        rows.append([btn(f"▶️ Boshlash ({human_len(ln)}) va kanalga e'lon qilish", "cn:tog", style=SUCCESS)])
    rows.append([btn(("✅ " if ln == d else "") + human_len(d), f"cn:l:{d}", style=SUCCESS if ln == d else PRIMARY) for d in LEN_PRESETS])
    rows.append([btn("✏️ Boshqa muddat (kun)", "cn:lc", style=PRIMARY)])
    if _pending(app):
        rows.insert(0, [btn("⏳ G'oliblarni tasdiqlash", "cn:pv", style=SUCCESS)])
    rows.append([btn("🔒 G'oliblarni qo'lda tasdiqlash: " + ("yoqilgan ✅" if approval_on(app) else "o'chiq"), "cn:apr", style=PRIMARY)])
    rows.append([btn("➖ O'rin", "cn:del", style=PRIMARY), btn(f"{len(pz)} ta g'olib", "cn:noop", style=PRIMARY), btn("➕ O'rin", "cn:add", style=PRIMARY)])
    for i, p in enumerate(pz):
        rows.append([btn(f"✏️ {place_mark(i)}: {prize_text(p)}", f"cn:e:{i}", style=SUCCESS)])
    return text, ikb(*rows)


@router.command("musobaqa", owner=True)
def cmd_contest_admin(ctx: Ctx) -> None:
    ctx.send(standings_text(ctx.app, ctx.user_id))
    ctx.send(*_admin_view(ctx.app))


@router.command("bekorqilish", owner=True)
def cmd_contest_cancel(ctx: Ctx) -> None:
    """/bekorqilish — faol musobaqani mukofotsiz bekor qiladi, kanaldagi e'lonni o'chiradi va keyingi avtomatik boshlanishlarni to'xtatadi."""
    app = ctx.app
    was = enabled(app)
    if was:
        finish_contest(app, award=False)
    else:
        delete_announcement(app)
    app.set_setting("contest_on", "0")
    ctx.send("❌ <b>Musobaqa bekor qilindi.</b> Mukofot berilmadi, kanaldagi e'lon o'chirildi.\n"
             "Yangisini /musobaqa orqali boshlashingiz mumkin." if was else
             "ℹ️ Faol musobaqa yo'q edi. Kanaldagi eski e'lon (bo'lsa) o'chirildi.\nYangisini /musobaqa orqali boshlang.")


def _set_len(app, days: int) -> None:
    app.set_setting("contest_len", str(days))
    per = active_period(app)
    if per:                                              # faol musobaqa bo'lsa — tugash vaqti ham yangilanadi
        app.set_setting("contest_end", str(per[0] + days * 86400))


@router.callback("cn", owner=True)
def cb_contest(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    act = parts[1] if len(parts) > 1 else ""
    pz = prizes(app)
    if act in ("px", "pok", "pno", "pv"):              # g'oliblarni qo'lda tasdiqlash
        d = _pending(app)
        if not d:
            ctx.answer("Tasdiqlanadigan musobaqa yo'q", alert=True)
            return
        if act == "px" and len(parts) > 2 and parts[2].isdigit():
            ex = {int(x) for x in d["ex"]} ^ {int(parts[2])}
            d["ex"] = sorted(ex)
            _save_pending(app, d)
            ctx.answer()
        elif act == "pok":
            _save_pending(app, None)
            won = award_period(app, d["start"], d["end"], d["ex"])
            ctx.answer(f"🏁 Mukofotlandi: {len(won)} ta g'olib", alert=True)
            ctx.edit(f"✅ Tasdiqlandi — {len(won)} ta g'olib mukofotlandi.")
            return
        elif act == "pno":
            _save_pending(app, None)
            ctx.answer("Mukofotsiz yopildi")
            ctx.edit("🗑 Musobaqa mukofotsiz yopildi.")
            return
        else:
            ctx.answer()
        text, kb = pending_view(app)
        ctx.edit("⏳ <b>G'oliblarni tasdiqlang</b>\n\n" + text, kb)
        return
    if act == "apr":                                   # tasdiqlash rejimini almashtirish
        app.set_setting("contest_approve", "0" if approval_on(app) else "1")
        ctx.answer("🔒 Qo'lda tasdiqlash: " + ("yoqildi" if approval_on(app) else "o'chdi"))
    elif act == "cx":                                  # bekor qilish — avval tasdiq so'raladi
        ctx.answer()
        ctx.edit("❌ <b>Musobaqani bekor qilasizmi?</b>\n\nMukofot berilmaydi, kanaldagi «boshlandi» e'loni o'chiriladi. "
                 "Keyin to'g'ri sozlamalar bilan qaytadan boshlashingiz mumkin.",
                 ikb([btn("✅ Ha, bekor qilish", "cn:cxy", style=DANGER), btn("⬅️ Yo'q", "cn:back", style=PRIMARY)]))
        return
    if act == "cxy":
        finish_contest(app, award=False)
        ctx.answer("❌ Bekor qilindi")
    elif act == "rs":                                  # eskisini bekor qilib, hozirgi sozlamalar bilan yangidan boshlash
        if enabled(app):
            finish_contest(app, award=False)
        ok, why = start_contest(app)
        ctx.answer("🔄 Qayta boshlandi" + (" va kanalga yangi e'lon chiqdi" if ok else ""))
        if not ok:
            ctx.send(f"⚠️ Musobaqa qayta boshlandi, lekin e'lon yuborilmadi: {esc(why)}")
    elif act == "dann":
        ctx.answer("🗑 E'lon o'chirildi" if delete_announcement(app) else "E'lon topilmadi (allaqachon o'chirilgan)", alert=True)
        return
    elif act == "tog":
        per = active_period(app)
        if per and now() >= per[1]:                    # muddati o'tgan, lekin hali yakunlanmagan — avval mukofotlab yakunlaymiz
            finish_contest(app, award=True)
        if enabled(app):
            finish_contest(app, award=False)
            ctx.answer("❌ Bekor qilindi (mukofotsiz)")
        else:
            ok, why = start_contest(app)
            ctx.answer("▶️ Boshlandi" + (" va kanalga e'lon qilindi" if ok else ""))
            if not ok:
                ctx.send(f"⚠️ Musobaqa boshlandi, lekin e'lon kanalga yuborilmadi: {esc(why)}")
    elif act == "fin":
        won = finish_contest(app, award=True)
        ctx.answer(f"🏁 Yakunlandi: {len(won)} ta g'olib" if not _pending(app) else "⏳ Yakunlandi — g'oliblarni tasdiqlang", alert=True)
        if _pending(app):
            ctx.send("⏳ <b>G'oliblarni tasdiqlang</b>\n\n" + pending_view(app)[0], pending_view(app)[1])
    elif act == "ann":
        ok, why = announce_contest(app)
        ctx.answer("📣 Yuborildi" if ok else "⚠️ Yuborilmadi", alert=not ok)
        if not ok:
            ctx.send(f"⚠️ E'lon yuborilmadi: {esc(why)}")
        return
    elif act == "l" and len(parts) > 2 and parts[2].isdigit() and 1 <= int(parts[2]) <= MAX_DAYS:
        _set_len(app, int(parts[2]))
        ctx.answer(f"⏱ {human_len(int(parts[2]))}")
    elif act == "lc":
        ctx.answer()
        ctx.set_state("cn:len")
        ctx.send(f"✏️ Musobaqa muddatini <b>kun</b> bilan yuboring (1 dan {MAX_DAYS} gacha), masalan <code>5</code>.",
                 ikb([btn("❌ Bekor qilish", "cancel", style=DANGER)]))
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
    else:
        ctx.answer()
    ctx.edit(*_admin_view(app))


@router.state("cn:len", admin=True)
def st_len_input(ctx: Ctx) -> None:
    if not ctx.is_owner:
        ctx.clear_state()
        return
    text = ctx.text.strip()
    if not text.isdigit() or not 1 <= int(text) <= MAX_DAYS:
        ctx.send(f"❗️ 1 dan {MAX_DAYS} gacha kun sonini yuboring.")
        return
    _set_len(ctx.app, int(text))
    ctx.clear_state()
    ctx.send("✅ Saqlandi.")
    ctx.send(*_admin_view(ctx.app))


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
