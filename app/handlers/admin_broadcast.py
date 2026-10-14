"""Admin: ✉️ Xabar yuborish (reklama, e'lon) — tugmalar, auditoriya va jonli hisobot bilan."""

from __future__ import annotations

import logging
import threading
import time

from ..core import App, Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..telegram import BadRequest, Forbidden, TelegramError
from ..texts import B
from ..utils import esc, fmt_duration, fmt_num, parse_url_buttons, progress_bar

log = logging.getLogger("admin.broadcast")

AUDIENCE = {
    "all": "👥 Barcha foydalanuvchilar",
    "free": "🆓 Oddiy foydalanuvchilar (premiumsiz)",
    "premium": "💎 Faqat premiumlar",
}
MODES = {"copy": "📨 Nusxa (forward belgisiz)", "forward": "↪️ Forward (manba ko'rinadi)"}
BUTTONS_HELP = (
    "🔘 <b>Tugma qo'shish</b>\n\n"
    "Har bir qatorga bitta tugma yozing:\n"
    "<code>Tugma matni - https://havola</code>\n\n"
    "Bir qatorda bir nechta tugma uchun «|» belgisidan foydalaning:\n"
    "<code>Kanal - https://t.me/kanal | Sayt - https://sayt.uz</code>"
)


class BroadcastJob:
    def __init__(self, admin_chat: int, src_chat: int, src_msg: int, mode: str, audience: str, buttons):
        self.admin_chat = admin_chat
        self.src_chat = src_chat
        self.src_msg = src_msg
        self.mode = mode
        self.audience = audience
        self.buttons = buttons
        self.cancelled = False
        self.total = self.done = self.ok = self.blocked = self.failed = 0
        self.started = time.time()
        self.status_msg = None


# ═════════════════════════ tayyorlash ═════════════════════════

@router.button(B.BROADCAST, admin=True)
def btn_broadcast(ctx: Ctx) -> None:
    if ctx.app.broadcast is not None:
        ctx.send("⏳ Hozir boshqa xabar yuborilmoqda. U tugashini kuting yoki to'xtating.")
        return
    ctx.set_state("bc:msg")
    ctx.send("✉️ <b>Xabar yuborish</b>\n\n"
             "Foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring:\n"
             "matn, rasm, video, GIF, ovozli xabar yoki fayl.\n\n"
             "ℹ️ Albom (bir nechta rasm) o'rniga bitta xabar yuboring.", cancel_kb())


@router.state("bc:msg", admin=True)
def st_message(ctx: Ctx) -> None:
    msg = ctx.message
    ctx.goto("bc:confirm", src_chat=ctx.chat_id, src_msg=msg["message_id"], mode="copy",
             audience="all", buttons=[], group=msg.get("media_group_id"))
    send_preview(ctx)


@router.state("bc:confirm", admin=True)
def st_confirm(ctx: Ctx) -> None:
    group = ctx.sdata.get("group")
    if group and ctx.message.get("media_group_id") == group:
        return  # albomning qolgan qismlarini e'tiborsiz qoldiramiz
    ctx.send("👆 Yuqoridagi tugmalardan birini tanlang yoki «❌ Bekor qilish» ni bosing.")


@router.state("bc:buttons", admin=True)
def st_buttons(ctx: Ctx) -> None:
    rows, bad = parse_url_buttons(ctx.text)
    if rows is None:
        ctx.send(f"❗️ Noto'g'ri format: <code>{esc(bad[:100])}</code>\n\n{BUTTONS_HELP}", cancel_kb())
        return
    ctx.goto("bc:confirm", buttons=rows, mode="copy")
    send_preview(ctx)


def send_preview(ctx: Ctx) -> None:
    d = ctx.sdata
    kb = {"inline_keyboard": d["buttons"]} if d["buttons"] and d["mode"] == "copy" else None
    try:
        if d["mode"] == "forward":
            ctx.bot.forward_message(ctx.chat_id, d["src_chat"], d["src_msg"])
        else:
            ctx.bot.copy_message(ctx.chat_id, d["src_chat"], d["src_msg"], reply_markup=kb)
    except BadRequest as exc:
        if d["buttons"]:
            ctx.goto("bc:confirm", buttons=[])
            ctx.send(f"❌ Tugma havolasi noto'g'ri, tugmalar olib tashlandi.\n<i>{esc(exc.description)}</i>")
            return send_preview(ctx)
        ctx.send(f"⚠️ Ko'rinishni chiqarib bo'lmadi: {esc(exc.description)}")
    ctx.send(control_text(ctx), control_kb(ctx))


def control_text(ctx: Ctx) -> str:
    d = ctx.sdata
    count = ctx.db.count_audience(d["audience"])
    n_buttons = sum(len(r) for r in d["buttons"])
    text = ("👆 <b>Xabar shunday ko'rinadi.</b>\n\n"
            f"🎯 Auditoriya: <b>{AUDIENCE[d['audience']]}</b> — {fmt_num(count)} ta\n"
            f"📤 Usul: <b>{MODES[d['mode']]}</b>\n"
            f"🔘 Tugmalar: <b>{n_buttons} ta</b>")
    if d["mode"] == "forward" and n_buttons:
        text += "\n⚠️ Forward usulida tugmalar qo'shilmaydi."
    return text + "\n\nHammasi to'g'ri bo'lsa «✅ Yuborish» ni bosing."


def control_kb(ctx: Ctx) -> dict:
    d = ctx.sdata
    rows = [[btn("🎯 Auditoriya", "bc:aud"), btn("📤 Usul", "bc:mode")],
            [btn("🔘 Tugma qo'shish", "bc:btn", style=PRIMARY)]]
    if d["buttons"]:
        rows[1].append(btn("🧹 Tugmalarni o'chirish", "bc:clr"))
    rows.append([btn("✅ Yuborish", "bc:go", style=SUCCESS), btn("❌ Bekor qilish", "cancel", style=DANGER)])
    return ikb(*rows)


# ═════════════════════════ boshqaruv tugmalari ═════════════════════════

@router.callback("bc", admin=True)
def cb_broadcast(ctx: Ctx) -> None:
    app = ctx.app
    action = ctx.data.split(":")[1] if ":" in ctx.data else ""
    if action == "stop":
        job = app.broadcast
        if job is not None:
            job.cancelled = True
            ctx.answer("⏹ To'xtatilmoqda...")
        else:
            ctx.answer("ℹ️ Faol yuborish yo'q")
        return
    if ctx.state not in ("bc:confirm", "bc:buttons"):
        ctx.answer("⚠️ Bu tugma eskirgan. Qaytadan boshlang.", alert=True)
        return
    d = ctx.sdata
    if action == "aud":
        order = ["all", "free", "premium"] if app.setting_bool("premium_enabled") else ["all"]
        cur = d["audience"] if d["audience"] in order else "all"
        ctx.goto("bc:confirm", audience=order[(order.index(cur) + 1) % len(order)])
        ctx.answer()
        ctx.edit(control_text(ctx), control_kb(ctx))
    elif action == "mode":
        ctx.goto("bc:confirm", mode="forward" if d["mode"] == "copy" else "copy")
        ctx.answer()
        ctx.edit(control_text(ctx), control_kb(ctx))
    elif action == "btn":
        ctx.goto("bc:buttons")
        ctx.answer()
        ctx.send(BUTTONS_HELP, cancel_kb())
    elif action == "clr":
        ctx.goto("bc:confirm", buttons=[])
        ctx.answer("🧹 Tugmalar o'chirildi")
        send_preview(ctx)
    elif action == "go":
        if app.broadcast is not None:
            ctx.answer("⏳ Boshqa xabar yuborilmoqda", alert=True)
            return
        job = BroadcastJob(ctx.chat_id, d["src_chat"], d["src_msg"], d["mode"], d["audience"],
                           d["buttons"] if d["mode"] == "copy" else [])
        app.broadcast = job
        ctx.clear_state()
        ctx.answer("🚀 Yuborish boshlandi!")
        ctx.edit(progress_text(job), stop_kb())
        job.status_msg = ctx.cb_message.get("message_id")
        threading.Thread(target=run_job, args=(app, job), name="broadcast", daemon=True).start()


def stop_kb() -> dict:
    return ikb([btn("⏹ To'xtatish", "bc:stop", style=DANGER)])


def progress_text(job: BroadcastJob) -> str:
    pct = int(job.done * 100 / job.total) if job.total else 0
    return ("📤 <b>Xabar yuborilmoqda...</b>\n\n"
            f"{progress_bar(job.done, job.total)} {pct}%\n"
            f"👥 {fmt_num(job.done)} / {fmt_num(job.total)}\n"
            f"✅ Yetkazildi: {fmt_num(job.ok)}\n"
            f"🚫 Bloklagan: {fmt_num(job.blocked)}\n"
            f"❌ Xatolik: {fmt_num(job.failed)}\n"
            f"⏱ O'tgan vaqt: {fmt_duration(time.time() - job.started)}")


def final_text(job: BroadcastJob) -> str:
    head = "⏹ <b>Xabar yuborish to'xtatildi.</b>" if job.cancelled else "✅ <b>Xabar yuborish yakunlandi!</b>"
    return (f"{head}\n\n"
            f"👥 Jami: {fmt_num(job.total)}\n"
            f"✅ Yetkazildi: {fmt_num(job.ok)}\n"
            f"🚫 Bloklagan: {fmt_num(job.blocked)}\n"
            f"❌ Xatolik: {fmt_num(job.failed)}\n"
            f"⏱ Davomiyligi: {fmt_duration(time.time() - job.started)}")


def _update_status(app: App, job: BroadcastJob, text: str, kb=None) -> None:
    if job.status_msg:
        try:
            app.bot.edit_message_text(job.admin_chat, job.status_msg, text, kb)
            return
        except TelegramError:
            pass
    app.bot.safe("sendMessage", {"chat_id": job.admin_chat, "text": text, "parse_mode": "HTML"})


def run_job(app: App, job: BroadcastJob) -> None:
    try:
        ids = app.db.user_ids(job.audience)
        job.total = len(ids)
        kb = {"inline_keyboard": job.buttons} if job.buttons else None
        last_update = time.time()
        for uid in ids:
            if job.cancelled or app.stopping.is_set():
                break
            try:
                if job.mode == "forward":
                    app.bot.forward_message(uid, job.src_chat, job.src_msg)
                else:
                    app.bot.copy_message(uid, job.src_chat, job.src_msg, reply_markup=kb)
                job.ok += 1
            except Forbidden:
                job.blocked += 1
                app.db.set_blocked(uid, True)
            except BadRequest as exc:
                if exc.has("chat not found", "user is deactivated", "peer_id_invalid"):
                    job.blocked += 1
                    app.db.set_blocked(uid, True)
                else:
                    job.failed += 1
            except TelegramError:
                job.failed += 1
            job.done += 1
            if time.time() - last_update > 3:
                last_update = time.time()
                _update_status(app, job, progress_text(job), stop_kb())
            time.sleep(0.04)  # ~25 ta xabar/soniya — Telegram cheklovidan oshmaslik uchun
        _update_status(app, job, final_text(job))
        log.info("Xabar yuborish yakunlandi: %s/%s yetkazildi", job.ok, job.total)
    except Exception:
        log.exception("Xabar yuborishda xatolik")
        app.bot.safe("sendMessage", {"chat_id": job.admin_chat,
                                     "text": "⚠️ Xabar yuborish kutilmagan xatolik bilan to'xtadi."})
    finally:
        app.broadcast = None
