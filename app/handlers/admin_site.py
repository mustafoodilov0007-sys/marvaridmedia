"""Admin: kanal obunachilarini saytga tortish — Mini App havolasi (/miniapp) va kanalga taklif posti (/saytpost)."""

from __future__ import annotations

import logging
import re

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import TelegramError
from ..utils import esc, fmt_num, post_link

log = logging.getLogger("admin.site")

NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,31}")


def _site_url(app) -> str:
    return app.site_home_link() or ""


@router.command("miniapp", owner=True)
def cmd_miniapp(ctx: Ctx) -> None:
    """Mini App qisqa nomini kiritish: /miniapp nom   (o'chirish: /miniapp off)."""
    app = ctx.app
    arg = ctx.args.strip()
    if arg:
        if arg.lower() in ("off", "ochir", "o'chir", "0"):
            app.set_setting("miniapp", "")
            ctx.send("✅ To'g'ridan-to'g'ri Mini App havolasi o'chirildi. Kanal tugmalari oddiy sayt havolasiga qaytdi.")
            return
        name = arg.lstrip("/@ ").split("/")[-1]
        if not NAME_RE.fullmatch(name):
            ctx.send("❗️ Nom faqat lotin harf, raqam va _ dan iborat bo'lishi kerak (3–32 belgi). "
                     "Masalan: <code>/miniapp marvarid</code>")
            return
        app.set_setting("miniapp", name)
        link = app.miniapp_link()
        ctx.send(f"✅ Saqlandi!\n\n🔗 Mini App havolasi:\n{esc(link)}\n\n"
                 "Endi kanaldagi «🌐 Saytda tomosha qilish» tugmalari sayt(Mini App)ni Telegram ichida, "
                 "foydalanuvchi akkaunti bilan ochadi.\n\n"
                 "👉 Tekshirish uchun pastdagi tugmani bosing. Ochilmasa, nom @BotFather'dagi bilan bir xil emas.",
                 ikb([btn("🌐 Tekshirish", url=link, style=SUCCESS)]))
        return
    cur = app.setting("miniapp")
    status = (f"✅ Ulangan: <code>{esc(app.miniapp_link())}</code>" if cur
              else "⚠️ Hozircha ulanmagan — kanaldan sayt oddiy brauzer havolasi bilan ochiladi (akkauntsiz).")
    ctx.send("🌐 <b>Kanaldan saytga to'g'ridan-to'g'ri kirish</b>\n\n" + status + "\n\n"
             "<b>Nima beradi?</b> Kanaldagi tugma bosilsa sayt <b>Telegram ichida Mini App</b> bo'lib ochiladi: "
             "foydalanuvchi tanilgan, kino bir bosishda botga keladi, baho va sevimlilar saqlanadi.\n\n"
             "<b>Sozlash (1 daqiqa):</b>\n"
             "1. @BotFather → <code>/newapp</code> → botingizni tanlang\n"
             "2. Nom va tavsif yozing, rasm yuboring (640×360), GIF kerak emas — <code>/empty</code>\n"
             f"3. <b>Web App URL</b>: <code>{esc(app.config.webapp_url or '—')}</code>\n"
             "4. <b>Short name</b> so'ralganda lotin nom kiriting (masalan <code>marvarid</code>)\n"
             "5. Shu yerga qaytib: <code>/miniapp marvarid</code>\n\n"
             "Qo'shimcha: @BotFather → Bot Settings → <b>Configure Mini App</b> — bot profilida katta «Ochish» "
             "tugmasi chiqadi.")


def _invite_text(app) -> str:
    c = app.db.count_by_category()
    total = c["movie"] + c["serial"] + c["cartoon"]
    return (f"🌐 <b>{esc(app.brand)} sayti ochiq!</b>\n\n"
            f"🎬 <b>{fmt_num(total)}</b> dan ortiq kino, serial va multfilm — bir joyda\n"
            "🔎 Tez qidiruv • janr, davlat, yil bo'yicha saralash\n"
            "⭐ Tomoshabin baholari • 🎲 tasodifiy kino • 📚 to'plamlar\n"
            "🔖 Sevimlilar — yoqqanini saqlab qo'ying\n"
            "🎞 Shorts va 🎵 musiqalar ham shu yerda\n\n"
            "👇 Bir bosishda oching — kinoni tanlang, bot darhol yuboradi!")


def _invite_kb(app) -> dict:
    url = _site_url(app)
    rows = []
    if url:
        rows.append([btn("🌐 Saytni ochish", url=url, style=SUCCESS)])
    rows.append([btn("🤖 Botni ochish", url=f"https://t.me/{app.bot_username}", style=PRIMARY)])
    return ikb(*rows)


@router.command("saytpost", admin=True)
def cmd_saytpost(ctx: Ctx) -> None:
    """Kanalga «saytimiz ochiq» taklif postini tayyorlaydi (avval adminga ko'rsatadi)."""
    app = ctx.app
    if not _site_url(app):
        ctx.send("🌐 Sayt hali ishga tushirilmagan (WEBAPP_URL yo'q).")
        return
    note = "" if app.setting("miniapp") else ("\n\n💡 Tugma oddiy brauzer havolasi bilan ochiladi. Yaxshiroq natija uchun "
                                                "/miniapp orqali Mini App ulang.")
    ctx.send("👀 <b>Kanalga yuboriladigan post:</b>" + note)
    ctx.send(_invite_text(app), _invite_kb(app))
    ctx.send("Kanalga yuboramizmi?",
             ikb([btn("📣 Kanalga yuborish", "sp:send", style=SUCCESS), btn("📌 Yuborib, qadash", "sp:pin", style=PRIMARY)],
                 [btn("❌ Bekor", "x", style=DANGER)]))


@router.callback("sp", admin=True)
def cb_saytpost(ctx: Ctx) -> None:
    app = ctx.app
    channel = app.setting("post_channel")
    if not channel:
        ctx.answer("❗️ E'lon kanali sozlanmagan (⚙️ Matnlar → 📣 E'lon kanali)", alert=True)
        return
    pin = ctx.data.endswith(":pin")
    try:
        sent = ctx.bot.send_message(channel, _invite_text(app), _invite_kb(app))
    except TelegramError as exc:
        log.warning("Taklif posti yuborilmadi: %s", exc)
        ctx.answer("❌ Kanalga yuborib bo'lmadi. Bot kanalda admin ekanini tekshiring.", alert=True)
        return
    pinned = False
    if pin:
        r = ctx.bot.safe("pinChatMessage", {"chat_id": channel, "message_id": sent.get("message_id"),
                                            "disable_notification": True})
        pinned = r is not None
    ctx.answer("✅ Yuborildi")
    link = post_link(sent.get("chat") or {}, sent.get("message_id"))
    ctx.edit("📢 <b>Taklif posti kanalga joylandi!</b>" + (" 📌 Qadaldi." if pinned else
             ("\n\nℹ️ Qadab bo'lmadi — postni o'zingiz qadang." if pin else "")),
             ikb([btn("👁 Postni ko'rish", url=link, style=PRIMARY)]) if link else None)
