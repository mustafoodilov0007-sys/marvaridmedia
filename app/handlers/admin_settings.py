"""Admin: ⚙️ Matnlar va sozlamalar (start, obuna, kino izohi, donat, premium, karta, e'lon kanali)."""

from __future__ import annotations

import logging
import re

from ..core import App, Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..telegram import BadRequest, TelegramError
from ..texts import B, TEXT_TITLES
from ..utils import channel_ref, entities_to_html, esc, fmt_card, render, visible_len

log = logging.getLogger("admin.settings")

OTHER_TITLES = {
    "card_number": "💳 Karta raqami",
    "card_holder": "👤 Karta egasi",
    "post_channel": "📣 E'lon kanali",
}
TOGGLES = {"protect_content"}


def sample(app: App, template: str) -> str:
    return render(template, name="Ali", brand=esc(app.brand), bot=app.bot_username,
                  card=fmt_card(app.setting("card_number")), holder=esc(app.setting("card_holder") or "—"))


def is_custom(app: App, key: str) -> bool:
    return key in app.db.get_settings()


def settings_menu(app: App):
    protect = app.setting_bool("protect_content")
    t = TEXT_TITLES
    text = ("⚙️ <b>Matnlar va sozlamalar</b>\n\n"
            "O'zgartirmoqchi bo'lgan bo'limni tanlang 👇\n\n"
            "🔒 <b>Kontent himoyasi</b> yoqilganda oddiy foydalanuvchilar kinolarni saqlay olmaydi va "
            "forward qila olmaydi (Premium a'zolar va adminlar bundan mustasno).")
    rows = [
        [btn(t["start_text"][0], "st:k:start_text", style=PRIMARY),
         btn(t["sub_text"][0], "st:k:sub_text", style=SUCCESS)],
        [btn(t["caption_footer"][0], "st:k:caption_footer", style=SUCCESS),
         btn(t["donate_text"][0], "st:k:donate_text", style=PRIMARY)],
        [btn(t["premium_text"][0], "st:k:premium_text", style=PRIMARY),
         btn(OTHER_TITLES["card_number"], "st:k:card_number", style=SUCCESS)],
        [btn(OTHER_TITLES["card_holder"], "st:k:card_holder", style=SUCCESS),
         btn(OTHER_TITLES["post_channel"], "st:k:post_channel", style=PRIMARY)],
        [btn("🔒 Kontent himoyasi: " + ("✅ Yoqilgan" if protect else "❌ O'chiq"),
             "st:tog:protect_content", style=SUCCESS if protect else DANGER)],
    ]
    return text, ikb(*rows)


def item_view(app: App, key: str):
    custom = is_custom(app, key)
    badge = "🟢 O'zgartirilgan" if custom else "⚪️ Standart"
    if key in TEXT_TITLES:
        title, variables = TEXT_TITLES[key]
        text = (f"✏️ <b>{title}</b>  •  {badge}\n\n━━━━━━━━━━━━━━━\n{sample(app, app.setting(key))}\n"
                f"━━━━━━━━━━━━━━━\n\n🔤 O'zgaruvchilar: {esc(variables)}")
    elif key == "card_number":
        text = f"💳 <b>Karta raqami</b>  •  {badge}\n\nHozirgi: <code>{fmt_card(app.setting(key)) or '—'}</code>"
    elif key == "card_holder":
        text = f"👤 <b>Karta egasi</b>  •  {badge}\n\nHozirgi: <b>{esc(app.setting(key) or '—')}</b>"
    else:
        title = app.setting("post_channel_title") or app.setting("post_channel") or "—"
        text = (f"📣 <b>E'lon kanali</b>  •  {badge}\n\nHozirgi: <b>{esc(title)}</b>\n\n"
                "Yangi kino qo'shilganda «📢 Kanalga e'lon qilish» tugmasi shu kanalga post joylaydi.")
    rows = [[btn("✏️ O'zgartirish", f"st:edit:{key}", style=PRIMARY)]]
    if custom:
        rows.append([btn("♻️ Standart holatga qaytarish", f"st:reset:{key}", style=DANGER)])
    rows.append([btn("⬅️ Orqaga", "st:menu", style=DANGER)])
    return text, ikb(*rows)


PROMPTS = {
    "card_number": "💳 Yangi <b>karta raqamini</b> yuboring (16 xonali):",
    "card_holder": "👤 Karta egasining <b>ism-familiyasini</b> yuboring:",
    "post_channel": ("📣 E'lon kanalining <b>@userini</b> yuboring yoki kanaldan postni <b>forward</b> qiling.\n\n"
                     "⚠️ Bot kanalda admin va post joylash huquqiga ega bo'lishi kerak."),
}


@router.button(B.TEXTS, admin=True)
def btn_texts(ctx: Ctx) -> None:
    text, kb = settings_menu(ctx.app)
    ctx.send(text, kb)


@router.callback("st", admin=True)
def cb_settings(ctx: Ctx) -> None:
    app = ctx.app
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else "menu"
    key = parts[2] if len(parts) > 2 else ""
    valid = key in TEXT_TITLES or key in OTHER_TITLES
    if action == "menu":
        ctx.answer()
        text, kb = settings_menu(app)
        ctx.edit(text, kb)
    elif action == "k" and valid:
        ctx.answer()
        text, kb = item_view(app, key)
        ctx.edit(text, kb)
    elif action == "edit" and valid:
        ctx.answer()
        ctx.set_state("st:edit", key=key)
        if key in TEXT_TITLES:
            prompt = ("✏️ Yangi matnni yuboring.\n"
                      "Qalin, kursiv, havola kabi formatlash saqlanadi.\n\n"
                      f"🔤 O'zgaruvchilar: {esc(TEXT_TITLES[key][1])}")
        else:
            prompt = PROMPTS[key]
        ctx.send(prompt, cancel_kb())
    elif action == "reset" and valid:
        app.reset_setting(key)
        if key == "post_channel":
            app.reset_setting("post_channel_title")
        ctx.answer("♻️ Standart holatga qaytarildi")
        text, kb = item_view(app, key)
        ctx.edit(text, kb)
    elif action == "tog" and key in TOGGLES:
        app.set_setting(key, "0" if app.setting_bool(key) else "1")
        ctx.answer("✅ Saqlandi")
        text, kb = settings_menu(app)
        ctx.edit(text, kb)


@router.state("st:edit", admin=True)
def st_edit(ctx: Ctx) -> None:
    app, msg = ctx.app, ctx.message
    key = ctx.sdata.get("key")
    back = ikb([btn("⬅️ Sozlamalarga qaytish", "st:menu", style=PRIMARY)])

    if key in TEXT_TITLES:
        if not msg.get("text"):
            ctx.send("❗️ Iltimos, matn ko'rinishida yuboring.", cancel_kb())
            return
        html_text = entities_to_html(msg["text"], msg.get("entities"))
        limit = 300 if key == "caption_footer" else 3500
        if visible_len(html_text) > limit:
            ctx.send(f"❗️ Matn juda uzun — {limit} belgigacha qisqartiring.", cancel_kb())
            return
        old = app.db.get_settings().get(key)
        app.set_setting(key, html_text)
        try:
            ctx.send("✅ <b>Saqlandi!</b> Yangi ko'rinish:\n\n" + sample(app, html_text), back)
        except BadRequest as exc:
            if old is None:
                app.reset_setting(key)
            else:
                app.set_setting(key, old)
            ctx.send(f"❌ Matnni saqlab bo'lmadi: {esc(exc.description)}", cancel_kb())
            return
        ctx.clear_state()
        return

    text = ctx.text.strip()
    if key == "card_number":
        digits = re.sub(r"\D", "", text)
        if not 12 <= len(digits) <= 19:
            ctx.send("❗️ Karta raqami 16 xonali son bo'lishi kerak.", cancel_kb())
            return
        app.set_setting(key, digits)
        ctx.clear_state()
        ctx.send(f"✅ Karta raqami saqlandi: <code>{fmt_card(digits)}</code>", back)
    elif key == "card_holder":
        if not text or len(text) > 64:
            ctx.send("❗️ Ism-familiya 1–64 belgidan iborat bo'lishi kerak.", cancel_kb())
            return
        app.set_setting(key, text)
        ctx.clear_state()
        ctx.send(f"✅ Karta egasi saqlandi: <b>{esc(text)}</b>", back)
    elif key == "post_channel":
        origin = msg.get("forward_origin") or {}
        ref = str(origin["chat"]["id"]) if origin.get("type") == "channel" else channel_ref(text)
        if not ref:
            ctx.send("❗️ Kanal @userini yuboring yoki kanaldan postni forward qiling.", cancel_kb())
            return
        try:
            chat = app.bot.get_chat(ref)
            member = app.bot.get_chat_member(chat["id"], app.me.get("id"))
        except TelegramError as exc:
            ctx.send(f"❌ Kanal topilmadi: {esc(exc.description)}", cancel_kb())
            return
        can_post = member.get("status") == "creator" or (
            member.get("status") == "administrator" and member.get("can_post_messages", True))
        if not can_post:
            ctx.send("⚠️ Bot bu kanalda admin emas yoki post joylash huquqi yo'q.", cancel_kb())
            return
        app.set_setting("post_channel", str(chat["id"]))
        app.set_setting("post_channel_title", chat.get("title") or str(chat["id"]))
        ctx.clear_state()
        ctx.send(f"✅ E'lon kanali saqlandi: <b>{esc(chat.get('title'))}</b>", back)
    else:
        ctx.clear_state()
