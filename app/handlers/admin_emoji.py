"""Admin: 💎 Botning emojilarini premium emojiga almashtirish (/almashtir).

Admin premium emojilarni yuboradi — bot har birini uning oddiy ko'rinishiga (masalan 🎬) bog'laydi.
Shundan so'ng bot yuboradigan HAMMA matnda (kino xabarlari, ro'yxatlar, e'lonlar) shu oddiy emoji
o'rniga premium emoji chiqadi, inline tugmalarda esa tugma ikonkasi bo'ladi.
"""

from __future__ import annotations

import json
import logging
import re

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb
from ..telegram import TelegramError
from ..utils import emoji_key, entity_text, esc

log = logging.getLogger("admin.emoji")

# Botda eng ko'p ishlatiladigan emojilar (mijoz ko'p ko'radiganlari oldinda)
STARTER = "🎬 📺 🧸 🎵 🎭 🌍 📅 🗣 🎞 🔢 📝 👁 💎 🤖 🌐 🔥 🆕 🎲 👍 👎 ✅ ❌ 👇 🍿 ⭐ 📚 🔎 🎉 📤 ⚡"


_EMOJI_CH = (r"(?:[\U0001F1E6-\U0001F1FF]{2}|[#*0-9]\ufe0f?\u20e3|"
             r"[\U0001F000-\U0001FAFF\u2190-\u21FF\u2300-\u23FF\u2460-\u24FF\u25A0-\u27BF\u2900-\u297F\u2B00-\u2BFF"
             r"\u3030\u303D\u3297\u3299\u00A9\u00AE\u203C\u2049\u2122\u2139][\ufe0f\U0001F3FB-\U0001F3FF]*"
             r"(?:\u200d[\U0001F000-\U0001FAFF\u2190-\u27BF\u2B00-\u2BFF][\ufe0f\U0001F3FB-\U0001F3FF]*)*)")
_PAIR_RE = re.compile(r"(" + _EMOJI_CH + r")\s*[=＝:]\s*$")


def parse_pairs(text: str, ents: list) -> dict:
    """Premium emojilarni juftlab oladi: «🥲=<premium emoji>» — chapdagi oddiy emoji kalit bo'ladi (aniq va xatosiz).
    «=» yozilmagan bo'lsa — premium emojining o'z oddiy ko'rinishi kalit bo'ladi (eski usul)."""
    raw = (text or "").encode("utf-16-le")
    found = {}
    for e in sorted((x for x in ents if x.get("type") == "custom_emoji" and x.get("custom_emoji_id")), key=lambda x: x["offset"]):
        before = raw[:e["offset"] * 2].decode("utf-16-le", errors="ignore")
        line = before.rsplit("\n", 1)[-1]
        m = _PAIR_RE.search(line)
        key = emoji_key(m.group(1)) if m else emoji_key(entity_text(text, e))
        if key:
            found[key] = e["custom_emoji_id"]
    return found


def status_view(ctx: Ctx):
    app = ctx.app
    mapping = app.emoji_mapping()
    on = app.setting("emoji_on") != "0"
    lines = ["💎 <b>Botning emojilarini premium qilish</b>", ""]
    if mapping:
        lines.append(f"Ulangan emojilar: <b>{len(mapping)}</b> ta  •  holati: <b>{'✅ yoniq' if on else '⏸ o‘chiq'}</b>")
        preview = " ".join(f'<tg-emoji emoji-id="{esc(i)}">{esc(k)}</tg-emoji>' for k, i in list(mapping.items())[:40])
        lines += ["", preview]
    else:
        lines.append("Hozircha hech narsa ulanmagan.")
    if app.bot.emoji_fail:
        lines.append(f"\n⚠️ Premium emoji qabul qilinmagan holatlar: <b>{app.bot.emoji_fail}</b> marta "
                     "(bunda xabar oddiy emoji bilan yuborilgan).")
    lines += ["", "<b>Qanday ulanadi?</b>",
              "1. «➕ Emoji ulash» ni bosing.",
              "2. Har birini <b>juft qilib</b> yozing: <code>oddiy emoji = premium emoji</code>, masalan <code>🥲=</code> va yoniga premium emoji. "
              "Bir xabarga bir nechta juft yozish mumkin.",
              "3. Bot oddiy emojini premium emojiga bog'laydi — shundan so'ng botda shu emoji har doim premium bo'lib chiqadi.",
              "",
              "💡 Botda eng ko'p ishlatiladiganlari:", STARTER,
              "",
              "ℹ️ Premium emoji animatsiyali chiqishi uchun <b>bot egasi akkauntida Telegram Premium</b> bo'lishi kerak. "
              "Kanal postlarida esa Telegram ba'zan buni cheklaydi — bunda post oddiy emoji bilan chiqadi."]
    rows = [[btn("➕ Emoji ulash", "pe:add", style=SUCCESS)]]
    if mapping:
        rows.append([btn("🧪 Sinab ko'rish", "pe:test", style=PRIMARY),
                     btn("⏸ O'chirish" if on else "▶️ Yoqish", "pe:toggle", style=PRIMARY)])
        rows.append([btn("🗑 Hammasini tozalash", "pe:clear", style=DANGER)])
    rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


@router.command("almashtir", "emojilar", admin=True)
def cmd_replace(ctx: Ctx) -> None:
    ctx.clear_state()
    ctx.send(*status_view(ctx))


@router.callback("pe", admin=True)
def cb_replace(ctx: Ctx) -> None:
    app = ctx.app
    action = ctx.data.split(":")[1] if ":" in ctx.data else ""
    if action == "add":
        ctx.answer()
        ctx.set_state("pe:wait", ttl=3600)
        ctx.send("💎 <b>Premium emojilarni yuboring</b>\n\n"
                 "Juft qilib yozing: <code>🥲=</code> va yoniga premium emojini qo'ying. Bot oddiy 🥲 ni shu premium emojiga bog'laydi "
                 "va hamma xabarda shuni ishlatadi. Bir xabarga bir nechta juft yozish mumkin, masalan:\n"
                 "<code>🎬=[premium] 🎭=[premium] 🌍=[premium]</code>\n\n"
                 "(Faqat premium emoji yuborsangiz, bot uni o'zining oddiy ko'rinishiga bog'laydi — bu ba'zan noto'g'ri chiqadi, "
                 "shuning uchun «=» bilan yozing.)\n\n"
                 f"💡 Avval shularni ulang:\n{STARTER}\n\n"
                 "Tugatgach «✅ Tayyor» ni bosing.", ikb([btn("✅ Tayyor", "pe:done", style=SUCCESS)],
                                                      [btn("❌ Bekor qilish", "cancel", style=DANGER)]))
    elif action == "done":
        ctx.answer()
        ctx.clear_state()
        ctx.send(*status_view(ctx))
    elif action == "toggle":
        app.set_setting("emoji_on", "0" if app.setting("emoji_on") != "0" else "1")
        app.sync_emoji()
        ctx.answer("▶️ Yoqildi" if app.setting("emoji_on") != "0" else "⏸ O'chirildi")
        ctx.edit(*status_view(ctx))
    elif action == "clear":
        app.set_setting("emoji_map", "{}")
        app.sync_emoji()
        ctx.answer("🗑 Tozalandi")
        ctx.edit(*status_view(ctx))
    elif action == "test":
        ctx.answer()
        mapping = app.emoji_mapping()
        before = app.bot.emoji_fail
        sample = " ".join(list(mapping)[:20])
        try:
            ctx.send(f"🧪 <b>Sinov xabari</b>\n\n{sample}\n\n"
                     "Yuqoridagi emojilar <b>animatsiyali</b> bo'lsa — hammasi to'g'ri ishlayapti ✅\n"
                     "Oddiy ko'rinsa — bot egasi akkauntida Telegram Premium yo'q ❌",
                     ikb([btn("🎬 Tugma ikonkasi", "pe:noop", style=SUCCESS)]))
        except TelegramError as exc:
            ctx.send(f"❌ Yuborib bo'lmadi: <i>{esc(str(exc))}</i>")
            return
        if app.bot.emoji_fail > before:
            ctx.send("⚠️ Telegram premium emojini qabul qilmadi — xabar oddiy emoji bilan yuborildi.\n"
                     "Sabab: bot egasi akkauntida Telegram Premium yo'q yoki obuna tugagan.")
    else:
        ctx.answer()


@router.state("pe:wait", admin=True)
def st_replace(ctx: Ctx) -> None:
    msg = ctx.message
    text = msg.get("text") or msg.get("caption") or ""
    ents = msg.get("entities") or msg.get("caption_entities") or []
    found = parse_pairs(text, ents)
    if not found:
        ctx.send("❗️ Xabarda premium emoji topilmadi. Premium emojilarni yuboring yoki «✅ Tayyor» ni bosing.",
                 ikb([btn("✅ Tayyor", "pe:done", style=SUCCESS)]))
        return
    app = ctx.app
    mapping = app.emoji_mapping()
    mapping.update(found)
    app.set_setting("emoji_map", json.dumps(mapping, ensure_ascii=False))
    if app.setting("emoji_on") == "0":
        app.set_setting("emoji_on", "1")
    app.sync_emoji()
    shown = " ".join(f'<tg-emoji emoji-id="{esc(i)}">{esc(k)}</tg-emoji>' for k, i in found.items())
    ctx.send(f"✅ <b>{len(found)} ta emoji ulandi:</b>\n{shown}\n\n"
             f"Jami ulangan: <b>{len(mapping)}</b> ta. Yana yuborishingiz yoki «✅ Tayyor» ni bosishingiz mumkin.",
             ikb([btn("✅ Tayyor", "pe:done", style=SUCCESS)]))
