"""🔔 Kuzatish: foydalanuvchi sevimli janrlarini tanlaydi — shu janrda yangi kino chiqsa bot xabar beradi;
haftalik tavsiya (dushanba) — ko'rgan janrlariga mos 3 ta kino."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from .. import genres
from .. import i18n_bot
from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import Forbidden, TelegramError
from ..utils import TZ, esc

log = logging.getLogger("follow")

DAILY_CAP = 3          # bitta foydalanuvchiga kuniga ko'pi bilan nechta yangi-kino xabari
SEND_GAP = 0.05        # xabarlar orasidagi pauza (Telegram cheklovlariga tushmaslik uchun ~20/s)
_sent_today: dict = {}


def follow_text(follows: set) -> str:
    chosen = [genres.label(k) for k in genres.PICKER if k in follows]
    return ("🔔 <b>Yangi kinolardan xabardor bo'ling</b>\n\n"
            "Sevimli janrlaringizni tanlang — shu janrda yangi kino qo'shilishi bilan bot sizga xabar beradi "
            "(kuniga ko'pi bilan %d ta).\n\n" % DAILY_CAP
            + (f"Tanlangan: {' • '.join(chosen)}\n\n" if chosen else "")
            + ("📬 Haftalik tavsiya: <b>yoqilgan</b>" if "weekly" in follows else "📬 Haftalik tavsiya: o'chiq")
            + ("\n📺 Ko'rgan seriallaringizning yangi qismlari: <b>o'chiq</b>" if "noparts" in follows
               else "\n📺 Ko'rgan seriallaringizning yangi qismlari: <b>yoqilgan</b>"))


def follow_kb(follows: set) -> dict:
    rows, row = [], []
    for k in genres.PICKER:
        on = k in follows
        row.append(btn(("✅ " if on else "") + genres.label(k), f"fw:g:{k}", style=SUCCESS if on else None))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn("📬 Haftalik tavsiya: " + ("o'chirish" if "weekly" in follows else "yoqish"), "fw:w", style=PRIMARY)])
    rows.append([btn("📺 Serial yangi qismlari: " + ("yoqish" if "noparts" in follows else "o'chirish"), "fw:np", style=PRIMARY)])
    rows.append([btn("✅ Tayyor", "fw:ok", style=SUCCESS)])
    return {"inline_keyboard": rows}


@router.command("kuzatish", "follow")
def cmd_follow(ctx: Ctx) -> None:
    f = ctx.db.user_follows(ctx.user_id)
    ctx.send(follow_text(f), follow_kb(f))


@router.callback("fw")
def cb_follow(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    db = ctx.db
    if action == "ok":
        f = db.user_follows(ctx.user_id)
        ctx.answer("✅")
        n = len([k for k in f if k != "weekly"])
        ctx.edit("🔔 <b>Saqlandi!</b> " + (f"{n} ta janr kuzatilmoqda." if n else "Hozircha janr tanlanmadi.")
                 + (" Haftalik tavsiya yoqilgan." if "weekly" in f else "") + "\n\nO'zgartirish uchun /kuzatish")
        return
    if action == "g" and len(parts) > 2 and parts[2] in genres.GENRES:
        on = db.follow_toggle(ctx.user_id, parts[2])
        ctx.answer(("✅ " if on else "🔕 ") + genres.name(parts[2]))
    elif action == "w":
        on = db.follow_toggle(ctx.user_id, "weekly")
        ctx.answer("📬 Haftalik tavsiya yoqildi" if on else "📬 O'chirildi")
    elif action == "np":
        off = db.follow_toggle(ctx.user_id, "noparts")
        ctx.answer("📺 Serial xabarlari o'chirildi" if off else "📺 Serial xabarlari yoqildi")
    elif action == "woff":
        if "weekly" in db.user_follows(ctx.user_id):
            db.follow_toggle(ctx.user_id, "weekly")
        ctx.answer("🔕 O'chirildi")
        ctx.edit("📬 Haftalik tavsiya o'chirildi. Qayta yoqish: /kuzatish")
        return
    elif action == "set":                       # yangi-kino xabaridagi «Obunani sozlash» tugmasi
        ctx.answer()
        f = db.user_follows(ctx.user_id)
        ctx.send(follow_text(f), follow_kb(f))
        return
    else:
        ctx.answer()
        return
    f = db.user_follows(ctx.user_id)
    ctx.edit(follow_text(f), follow_kb(f))


# ═════════════════════════ 📨 yangi kino chiqqanda ═════════════════════════

def _movie_card(movie):
    gl = ", ".join(genres.name(k) for k in genres.parse(movie["genres"])[:3])
    bits = [b for b in (gl, genres.year_text(movie["year"], movie["year_end"] if "year_end" in movie.keys() else 0)) if b]
    text = f"🆕 <b>Yangi kino qo'shildi!</b>\n\n🎬 <b>{esc(movie['title'])}</b>" + (f"\n🎭 {' • '.join(bits)}" if bits else "")
    kb = ikb([btn("▶️ Ko'rish", f"mv:{movie['id']}", style=SUCCESS)], [btn("🔔 Obunani sozlash", "fw:set", style=PRIMARY)])
    return text, kb


def notify_followers(app, movie_id: int) -> None:
    """Yangi kinoning janrlarini kuzatganlarga xabar yuboradi (orqa fonda, kuniga DAILY_CAP tagacha)."""
    if app.setting("follow_notify") == "0":
        return
    movie = app.db.get_movie(movie_id)
    if not movie or movie["category"] == "music":
        return
    keys = genres.parse(movie["genres"])
    users = app.db.followers_of(keys)
    if not users:
        return

    def work() -> None:
        text, kb = _movie_card(movie)
        day = int(time.time() // 86400)
        sent = 0
        for uid in users:
            if app.stopping.is_set():
                return
            k = (uid, day)
            if _sent_today.get(k, 0) >= DAILY_CAP:
                continue
            lg = app.user_lang(uid)
            t_text, t_kb = i18n_bot.translate(text, lg), i18n_bot.translate_markup(kb, lg)
            try:
                if movie["poster_id"]:
                    app.bot.call("sendPhoto", {"chat_id": uid, "photo": movie["poster_id"], "caption": t_text, "parse_mode": "HTML", "reply_markup": t_kb})
                else:
                    app.bot.send_message(uid, t_text, t_kb)
                _sent_today[k] = _sent_today.get(k, 0) + 1
                sent += 1
            except Forbidden:
                app.db.set_blocked(uid, True)
            except TelegramError as exc:
                log.warning("Kuzatuvchiga xabar yetmadi (%s): %s", uid, exc)
            time.sleep(SEND_GAP)
        for key in [k for k in _sent_today if k[1] != day]:
            _sent_today.pop(key, None)
        log.info("«%s» — %s ta kuzatuvchiga xabar yuborildi", movie["title"], sent)

    threading.Thread(target=work, name="follow-notify", daemon=True).start()


# ═════════════════════════ 📺 serialning yangi qismi ═════════════════════════

_parts_today: dict = {}
PARTS_CAP = 5              # bitta foydalanuvchiga kuniga ko'pi bilan nechta serial xabari


def notify_new_parts(app, movie_id: int, part_nos: list) -> None:
    """Serialga yangi qism(lar) qo'shilsa, uni ilgari ko'rgan foydalanuvchilarga xabar yuboradi (orqa fonda)."""
    movie = app.db.get_movie(movie_id)
    if not movie or movie["category"] not in ("serial", "cartoon") or not part_nos:
        return
    nos = sorted(part_nos)
    first = app.db.get_part_by_no(movie_id, nos[0])
    if not first or app.db.count_parts(movie_id) < 2:
        return
    users = app.db.watchers(movie_id)
    if not users:
        return
    label = f"{nos[0]}-qism" if len(nos) == 1 else f"{nos[0]}–{nos[-1]}-qismlar"
    text = f"🆕 <b>{esc(movie['title'])}</b>\n\n📺 <b>{label}</b> qo'shildi!"
    kb = ikb([btn(f"▶️ {nos[0]}-qismni ko'rish", f"pt:{first['id']}", style=SUCCESS)],
             [btn("🔕 Serial xabarlarini o'chirish", "fw:np", style=PRIMARY)])

    def work() -> None:
        day = int(time.time() // 86400)
        sent = 0
        for uid in users:
            if app.stopping.is_set():
                return
            k = (uid, day)
            if _parts_today.get(k, 0) >= PARTS_CAP:
                continue
            lg = app.user_lang(uid)
            try:
                app.bot.send_message(uid, i18n_bot.translate(text, lg), i18n_bot.translate_markup(kb, lg))
                _parts_today[k] = _parts_today.get(k, 0) + 1
                sent += 1
            except Forbidden:
                app.db.set_blocked(uid, True)
            except TelegramError as exc:
                log.warning("Serial xabari yetmadi (%s): %s", uid, exc)
            time.sleep(SEND_GAP)
        for key in [k for k in _parts_today if k[1] != day]:
            _parts_today.pop(key, None)
        log.info("«%s» %s — %s ta tomoshabinga xabar yuborildi", movie["title"], label, sent)

    threading.Thread(target=work, name="parts-notify", daemon=True).start()


# ═════════════════════════ 📬 haftalik tavsiya ═════════════════════════

def weekly_pick(app, uid: int):
    """Foydalanuvchiga 3 ta kino: ko'rgan janrlariga mos; bo'lmasa — haftaning TOP'idan."""
    rows = list(app.db.recommend(uid, 3))
    if len(rows) < 3:
        have = {r["id"] for r in rows}
        for r in app.db.weekly_top(10):
            if r["id"] not in have and not r["is_premium"]:
                rows.append(r)
                have.add(r["id"])
            if len(rows) >= 3:
                break
    return rows[:3]


def send_weekly(app, uid: int) -> bool:
    rows = weekly_pick(app, uid)
    if not rows:
        return False
    lines = ["📬 <b>Bu hafta siz uchun</b>\n"]
    for r in rows:
        g = ", ".join(genres.name(k) for k in genres.parse(r["genres"])[:2])
        lines.append(f"🎬 <b>{esc(r['title'])}</b>" + (f" — {g}" if g else ""))
    lines.append("\nYoqimli hordiq! 🍿")
    kb = ikb(*[[btn(f"▶️ {r['title'][:28]}", f"mv:{r['id']}", style=SUCCESS)] for r in rows],
             [btn("🔕 Haftalik tavsiyani o'chirish", "fw:woff", style=DANGER)])
    lg = app.user_lang(uid)
    try:
        app.bot.send_message(uid, i18n_bot.translate("\n".join(lines), lg), i18n_bot.translate_markup(kb, lg))
        return True
    except Forbidden:
        app.db.set_blocked(uid, True)
    except TelegramError as exc:
        log.warning("Haftalik tavsiya yetmadi (%s): %s", uid, exc)
    return False


@router.task
def _weekly_digest(app) -> None:
    """Har dushanba 10:00 (Toshkent) — yoqilgan foydalanuvchilarga haftalik tavsiya (bir haftada bir marta)."""
    while not app.stopping.is_set():
        dt = datetime.now(TZ)
        week = f"{dt.isocalendar()[0]}-W{dt.isocalendar()[1]:02d}"
        if dt.weekday() == 0 and dt.hour >= 10 and app.setting("last_weekly_digest") != week:
            app.set_setting("last_weekly_digest", week)
            users = app.db.weekly_subscribers()
            sent = 0
            for uid in users:
                if app.stopping.is_set():
                    return
                if send_weekly(app, uid):
                    sent += 1
                time.sleep(SEND_GAP)
            log.info("Haftalik tavsiya: %s/%s ta foydalanuvchiga yuborildi", sent, len(users))
        if app.stopping.wait(1800):
            return
