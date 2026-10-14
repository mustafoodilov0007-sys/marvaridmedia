"""Admin: 🔗 Majburiy kanallar (oddiy, yopiq, zayavkali kanallar va havolalar)."""

from __future__ import annotations

import logging
import re
import urllib.parse

from ..core import App, Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..telegram import TelegramError
from ..texts import B
from ..utils import channel_ref, esc, is_private_invite, truncate

log = logging.getLogger("admin.channels")

KIND_LABEL = {
    "public": "🌐 Ochiq kanal",
    "private": "🔐 Yopiq kanal",
    "request": "📨 Zayavkali kanal",
    "link": "🌍 Havola (tekshirilmaydi)",
}

ADD_PROMPT = (
    "➕ <b>Kanal qo'shish</b>\n\n"
    "Quyidagilardan birini yuboring:\n"
    "• kanal useri: <code>@kanal_nomi</code>\n"
    "• kanal havolasi: <code>https://t.me/kanal_nomi</code>\n"
    "• kanal ID raqami: <code>-100…</code>\n"
    "• yoki kanaldan istalgan postni <b>forward</b> qiling (yopiq kanallar uchun)\n\n"
    "🌍 Instagram, YouTube kabi havolani yuborsangiz — tugma sifatida qo'shiladi (obuna tekshirilmaydi).\n\n"
    "⚠️ Avval botni kanalga <b>admin</b> qilib qo'shing!"
)


def bot_is_admin(app: App, chat_id) -> bool:
    try:
        member = app.bot.get_chat_member(chat_id, app.me.get("id"))
    except TelegramError:
        return False
    return member.get("status") in ("administrator", "creator")


def channels_view(ctx: Ctx):
    app = ctx.app
    chans = ctx.db.list_channels()
    lines = [f"🔗 <b>Majburiy obuna kanallari:</b> {len(chans)} ta", ""]
    rows = [[btn("➕ Kanal qo'shish", "ch:add", style=SUCCESS)]]
    if not chans:
        lines.append("— hozircha kanal yo'q, majburiy obuna o'chiq.")
    for i, ch in enumerate(chans, 1):
        info = [KIND_LABEL.get(ch["kind"], ch["kind"])]
        if ch["kind"] != "link":
            info.append("✅ bot admin" if bot_is_admin(app, ch["chat_id"]) else "⚠️ bot admin emas!")
        lines.append(f"<b>{i}. {esc(truncate(ch['title'], 40))}</b>")
        lines.append("    " + " • ".join(info))
        lines.append(f"    🔗 {esc(ch['url'])}")
        rows.append([btn(f"🗑 {i}. {truncate(ch['title'], 28)}", f"ch:del:{ch['id']}", style=DANGER)])
    lines += ["", "ℹ️ Obunani tekshirish uchun bot har bir kanalda <b>admin</b> bo'lishi shart."]
    return "\n".join(lines), ikb(*rows)


@router.button(B.CHANNELS, admin=True)
def btn_channels(ctx: Ctx) -> None:
    text, kb = channels_view(ctx)
    ctx.send(text, kb)


@router.state("ch:add", admin=True)
def st_add_channel(ctx: Ctx) -> None:
    app, msg = ctx.app, ctx.message
    ref = None
    origin = msg.get("forward_origin") or {}
    if origin.get("type") == "channel":
        ref = str(origin["chat"]["id"])
    elif origin.get("type") == "chat" and origin.get("sender_chat"):
        ref = str(origin["sender_chat"]["id"])
    elif msg.get("forward_from_chat"):
        ref = str(msg["forward_from_chat"]["id"])
    text = ctx.text.strip()

    if not ref and text:
        if is_private_invite(text):
            ctx.send("❗️ Yopiq kanal havolasidan kanalni aniqlab bo'lmaydi.\n\n"
                     "Iltimos, o'sha kanaldan biror <b>postni forward</b> qiling.", cancel_kb())
            return
        ref = channel_ref(text)
        if not ref and re.match(r"https?://\S+$", text):
            host = (urllib.parse.urlsplit(text).hostname or "Havola").replace("www.", "")
            ctx.db.add_channel(None, host, text, "link")
            ctx.clear_state()
            ctx.send(f"✅ <b>{esc(host)}</b> havolasi qo'shildi!\n"
                     "ℹ️ Unga obuna tekshirilmaydi — obuna oynasida tugma sifatida ko'rinadi.")
            view, kb = channels_view(ctx)
            ctx.send(view, kb)
            return
    if not ref:
        ctx.send("❗️ Tushunmadim. Kanal <b>@useri</b>, <b>ID</b> raqamini yuboring yoki kanaldan postni "
                 "forward qiling.", cancel_kb())
        return

    try:
        chat = app.bot.get_chat(ref)
    except TelegramError as exc:
        ctx.send("❌ Kanal topilmadi yoki bot unga qo'shilmagan.\n"
                 f"<i>{esc(exc.description)}</i>\n\nAvval botni kanalga <b>admin</b> qilib qo'shing.", cancel_kb())
        return
    chat_id = str(chat["id"])
    title = chat.get("title") or chat_id
    if ctx.db.channel_exists(chat_id):
        ctx.send("ℹ️ Bu kanal allaqachon ro'yxatda bor.", cancel_kb())
        return
    if not bot_is_admin(app, chat_id):
        ctx.send(f"⚠️ Bot <b>{esc(title)}</b> kanalida admin emas!\n\n"
                 "Kanal sozlamalari → Administratorlar → Admin qo'shish → botni tanlang, so'ng qayta yuboring.",
                 cancel_kb())
        return
    ctx.goto("ch:kind", chat_id=chat_id, title=title, username=chat.get("username") or "")
    rows = []
    if chat.get("username"):
        rows.append([btn("🌐 Oddiy obuna (ochiq havola)", "ch:kind:public", style=SUCCESS)])
    else:
        rows.append([btn("🔐 Oddiy obuna (taklif havolasi)", "ch:kind:private", style=SUCCESS)])
    rows.append([btn("📨 Zayavka (so'rov) orqali", "ch:kind:request", style=PRIMARY)])
    rows.append([btn("❌ Bekor qilish", "cancel", style=DANGER)])
    ctx.send(f"📢 <b>{esc(title)}</b> topildi — bot admin ✅\n\n"
             "Obuna turini tanlang:\n\n"
             "• <b>Oddiy</b> — foydalanuvchi kanalga a'zo bo'lishi kerak.\n"
             "• <b>Zayavka</b> — kanalga qo'shilish so'rovini yuborishning o'zi yetarli "
             "(so'rovni tasdiqlash shart emas).", ikb(*rows))


@router.state("ch:kind", admin=True)
def st_kind(ctx: Ctx) -> None:
    ctx.send("👆 Yuqoridagi tugmalardan obuna turini tanlang yoki «❌ Bekor qilish» ni bosing.")


@router.callback("ch", admin=True)
def cb_channels(ctx: Ctx) -> None:
    app, db = ctx.app, ctx.db
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else "list"

    if action == "list":
        ctx.answer()
        text, kb = channels_view(ctx)
        ctx.edit(text, kb)
    elif action == "add":
        ctx.answer()
        ctx.set_state("ch:add")
        ctx.send(ADD_PROMPT, cancel_kb())
    elif action == "del" and len(parts) > 2 and parts[2].isdigit():
        ch = db.get_channel(int(parts[2]))
        if not ch:
            ctx.answer("Kanal topilmadi", alert=True)
            return
        ctx.answer()
        ctx.edit(f"⚠️ <b>{esc(ch['title'])}</b> majburiy obunadan olib tashlansinmi?",
                 ikb([btn("✅ Ha, o'chirilsin", f"ch:delok:{ch['id']}", style=DANGER)],
                     [btn("⬅️ Orqaga", "ch:list", style=PRIMARY)]))
    elif action == "delok" and len(parts) > 2 and parts[2].isdigit():
        db.delete_channel(int(parts[2]))
        ctx.answer("🗑 Kanal o'chirildi")
        text, kb = channels_view(ctx)
        ctx.edit(text, kb)
    elif action == "kind" and len(parts) > 2:
        if ctx.state != "ch:kind":
            ctx.answer("⚠️ Bu tugma eskirgan. Qaytadan boshlang.", alert=True)
            return
        kind = parts[2]
        d = ctx.sdata
        if kind == "public" and d.get("username"):
            url = f"https://t.me/{d['username']}"
        elif kind in ("private", "request"):
            try:
                link = app.bot.create_chat_invite_link(
                    d["chat_id"], name="Marvarid bot • zayavka" if kind == "request" else "Marvarid bot",
                    creates_join_request=True if kind == "request" else None)
            except TelegramError as exc:
                ctx.answer("❌ Taklif havolasini yaratib bo'lmadi. Botga «Foydalanuvchilarni taklif qilish» "
                           "huquqini bering.", alert=True)
                log.warning("Invite link xatosi: %s", exc)
                return
            url = link["invite_link"]
        else:
            ctx.answer("⚠️ Noto'g'ri tanlov", alert=True)
            return
        db.add_channel(d["chat_id"], d["title"], url, kind)
        ctx.clear_state()
        ctx.answer("✅ Kanal qo'shildi!")
        ctx.edit(f"✅ <b>{esc(d['title'])}</b> majburiy obunaga qo'shildi!\n"
                 f"{KIND_LABEL.get(kind)} • {esc(url)}")
        text, kb = channels_view(ctx)
        ctx.send(text, kb)
