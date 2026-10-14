"""Admin panel: kirish, 📊 Statistika, 💾 zaxira nusxa va 👮 Adminlar."""

from __future__ import annotations

import logging
import re

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, admin_menu, btn, cancel_kb, ikb
from ..telegram import InputFile, TelegramError
from ..texts import B
from ..utils import day_start, esc, fmt_datetime, fmt_num, now, truncate
from .user import send_welcome

log = logging.getLogger("admin")

ADMIN_COMMANDS = [
    {"command": "start", "description": "🏠 Bosh menyu"},
    {"command": "admin", "description": "👨‍💻 Admin panel"},
    {"command": "top", "description": "🔥 Top kinolar"},
    {"command": "new", "description": "🆕 Yangi kinolar"},
    {"command": "premium", "description": "💎 Premium obuna"},
    {"command": "id", "description": "🆔 ID raqamni bilish"},
    {"command": "cancel", "description": "❌ Amalni bekor qilish"},
]


def _channels_without_admin(ctx: Ctx) -> int:
    bad = 0
    for ch in ctx.db.list_channels():
        if ch["kind"] == "link" or not ch["chat_id"]:
            continue
        try:
            member = ctx.bot.get_chat_member(ch["chat_id"], ctx.app.me.get("id"))
            ok = member.get("status") in ("administrator", "creator")
        except TelegramError:
            ok = False
        bad += 0 if ok else 1
    return bad


def panel_text(ctx: Ctx) -> str:
    db = ctx.db
    text = ("👨‍💻 <b>Admin panel</b> — " + esc(ctx.app.brand) + "\n\n"
            f"👥 Foydalanuvchilar: <b>{fmt_num(db.count_users())}</b> "
            f"(+{fmt_num(db.count_joined_since(day_start()))} bugun)\n"
            f"🎬 Kinolar: <b>{fmt_num(db.count_movies())}</b>\n"
            f"💎 Premiumlar: <b>{fmt_num(db.count_premium())}</b>\n"
            f"⏳ Tekshirilmagan cheklar: <b>{fmt_num(db.count_pending())}</b>\n\n")
    bad = _channels_without_admin(ctx)
    if bad:
        text += (f"⚠️ <b>Diqqat:</b> bot {bad} ta kanalda admin emas — u yerda obuna tekshirilmaydi. "
                 "«🔗 Majburiy kanallar» bo'limini tekshiring.\n\n")
    return text + "Kerakli bo'limni tanlang 👇"


@router.command("admin", admin=True)
@router.button(B.ADMIN, admin=True)
def open_panel(ctx: Ctx) -> None:
    ctx.send(panel_text(ctx), admin_menu())


@router.button(B.HOME, admin=True)
def go_home(ctx: Ctx) -> None:
    send_welcome(ctx)


# ═════════════════════════ 📊 Statistika ═════════════════════════

def stats_text(ctx: Ctx) -> str:
    db = ctx.db
    t = now()
    today = day_start(t)
    users = db.count_users()
    blocked = db.count_blocked()
    totals = db.payment_totals()
    zero = {"n": 0, "total": 0}
    prem_card = totals.get("premium:card", zero)
    prem_stars = totals.get("premium:stars", zero)
    don_card = totals.get("donate:card", zero)
    don_stars = totals.get("donate:stars", zero)

    lines = [
        "📊 <b>Bot statistikasi</b>", "",
        f"👥 <b>Foydalanuvchilar:</b> {fmt_num(users)}",
        f"├ 🟢 Faol: {fmt_num(users - blocked)}",
        f"├ 🔴 Botni bloklagan: {fmt_num(blocked)}",
        f"├ ⚡️ So'nggi 24 soatda faol: {fmt_num(db.count_active_since(t - 86400))}",
        f"├ 📅 Bugun qo'shilgan: {fmt_num(db.count_joined_since(today))}",
        f"├ 🗓 Oxirgi 7 kun: {fmt_num(db.count_joined_since(t - 7 * 86400))}",
        f"└ 📆 Oxirgi 30 kun: {fmt_num(db.count_joined_since(t - 30 * 86400))}",
        "",
        f"🎬 <b>Kinolar:</b> {fmt_num(db.count_movies())}",
        f"├ 📺 Seriallar: {fmt_num(db.count_serials())}",
        f"├ 💎 Premium kinolar: {fmt_num(db.count_premium_movies())}",
        f"├ 🎞 Jami fayllar (qismlar): {fmt_num(db.count_parts_total())}",
        f"└ 👁 Jami ko'rishlar: {fmt_num(db.total_views())}",
        "",
        f"💎 <b>Faol premiumlar:</b> {fmt_num(db.count_premium())}",
        f"├ 💳 Karta orqali: {fmt_num(prem_card['n'])} ta — {fmt_num(prem_card['total'])} so'm",
        f"└ ⭐ Stars orqali: {fmt_num(prem_stars['n'])} ta — {fmt_num(prem_stars['total'])} ⭐",
        f"💝 <b>Donatlar:</b> {fmt_num(don_card['n'])} ta karta, "
        f"{fmt_num(don_stars['n'])} ta Stars ({fmt_num(don_stars['total'])} ⭐)",
        f"🔎 <b>Bugungi qidiruvlar:</b> {fmt_num(db.count_searches_since(today))}",
    ]
    top = db.top_movies(5)
    if top:
        lines += ["", "🏆 <b>Top 5 kino:</b>"]
        for i, m in enumerate(top, 1):
            lines.append(f"{i}. {esc(truncate(m['title'], 40))} — 👁 {fmt_num(m['views'])}")
    failed = db.top_failed_queries(t - 7 * 86400, 5)
    if failed:
        lines += ["", "❓ <b>Topilmagan so'rovlar (7 kun):</b>"]
        for f in failed:
            lines.append(f"• {esc(truncate(f['query'], 40))} — {f['n']} marta")
    lines += ["", f"🕐 Yangilandi: {fmt_datetime(t)}"]
    return "\n".join(lines)


def stats_kb(is_owner: bool) -> dict:
    rows = [[btn("🔄 Yangilash", "stat:refresh", style=PRIMARY)]]
    if is_owner:
        rows.append([btn("💾 Zaxira nusxa (backup)", "stat:backup", style=SUCCESS)])
    return ikb(*rows)


@router.button(B.STATS, admin=True)
def btn_stats(ctx: Ctx) -> None:
    ctx.send(stats_text(ctx), stats_kb(ctx.is_owner))


@router.callback("stat", admin=True)
def cb_stats(ctx: Ctx) -> None:
    action = ctx.data.split(":")[1] if ":" in ctx.data else "refresh"
    if action == "refresh":
        ctx.answer("🔄 Yangilandi")
        ctx.edit(stats_text(ctx), stats_kb(ctx.is_owner))
    elif action == "backup":
        if not ctx.is_owner:
            ctx.answer("⛔️ Faqat bosh adminlar uchun!", alert=True)
            return
        ctx.answer("💾 Tayyorlanmoqda...")
        send_backup(ctx)


def send_backup(ctx: Ctx) -> None:
    db = ctx.db
    tmp = db.path.with_name("backup_tmp.db")
    try:
        db.backup_to(tmp)
        data = tmp.read_bytes()
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
    if len(data) > 49 * 1024 * 1024:
        ctx.send("⚠️ Baza hajmi 50 MB dan katta — Telegram orqali yuborib bo'lmaydi. "
                 "Serverdagi <code>data/bot.db</code> faylidan nusxa oling.")
        return
    name = f"marvarid_backup_{fmt_datetime(now()).replace(' ', '_').replace(':', '-')}.db"
    try:
        ctx.bot.send_document(ctx.chat_id, file=InputFile(name, data),
                              caption="💾 <b>Ma'lumotlar bazasi zaxira nusxasi</b>\n\n"
                                      "Tiklash uchun: botni to'xtating va faylni <code>data/bot.db</code> "
                                      "nomi bilan almashtiring.")
    except TelegramError as exc:
        ctx.send(f"❌ Zaxira nusxani yuborib bo'lmadi: {esc(exc.description)}")


# ═════════════════════════ 👮 Adminlar ═════════════════════════

def admins_view(ctx: Ctx):
    app, db = ctx.app, ctx.db
    lines = ["👮 <b>Adminlar ro'yxati</b>", "", "👑 <b>Bosh adminlar</b> (.env faylida):"]
    for i, uid in enumerate(app.config.owners, 1):
        u = db.get_user(uid)
        name = esc(u["first_name"]) if u and u["first_name"] else "—"
        lines.append(f"{i}. <code>{uid}</code> — {name}")
    extra = [a for a in db.list_admins() if a["user_id"] not in app.config.owners]
    lines += ["", "👮 <b>Qo'shilgan adminlar:</b>"]
    if not extra:
        lines.append("— hozircha yo'q")
    rows = []
    for i, a in enumerate(extra, 1):
        name = esc(a["first_name"]) if a["first_name"] else "—"
        lines.append(f"{i}. <code>{a['user_id']}</code> — {name}")
        if ctx.is_owner:
            rows.append([btn(f"🗑 {truncate(a['first_name'] or str(a['user_id']), 20)} — o'chirish",
                             f"ad:del:{a['user_id']}", style=DANGER)])
    if ctx.is_owner:
        rows.insert(0, [btn("➕ Admin qo'shish", "ad:add", style=SUCCESS)])
    else:
        lines += ["", "ℹ️ Adminlarni faqat bosh adminlar o'zgartira oladi."]
    return "\n".join(lines), ikb(*rows) if rows else None


@router.button(B.ADMINS, admin=True)
def btn_admins(ctx: Ctx) -> None:
    text, kb = admins_view(ctx)
    ctx.send(text, kb)


@router.callback("ad", owner=True)
def cb_admins(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    if action == "add":
        ctx.answer()
        ctx.set_state("ad:add")
        ctx.send("➕ <b>Yangi admin qo'shish</b>\n\n"
                 "Yangi adminning <b>ID raqamini</b> yuboring yoki uning biror xabarini forward qiling.\n\n"
                 "💡 ID raqamni bilish uchun u botga /id buyrug'ini yuborsin.", cancel_kb())
    elif action == "del" and len(parts) > 2 and parts[2].isdigit():
        uid = int(parts[2])
        ctx.db.remove_admin(uid)
        ctx.app.invalidate_admins()
        ctx.bot.safe("deleteMyCommands", {"scope": {"type": "chat", "chat_id": uid}})
        ctx.answer("🗑 Admin o'chirildi")
        text, kb = admins_view(ctx)
        ctx.edit(text, kb)


@router.state("ad:add", admin=True)
def st_add_admin(ctx: Ctx) -> None:
    if not ctx.is_owner:
        ctx.clear_state()
        return
    msg = ctx.message
    uid = None
    origin = msg.get("forward_origin") or {}
    if origin.get("type") == "user":
        uid = origin["sender_user"]["id"]
    elif origin.get("type") == "hidden_user":
        ctx.send("⚠️ Bu foydalanuvchi profilini yashirgan. Iltimos, uning <b>ID raqamini</b> yuboring.",
                 cancel_kb())
        return
    elif msg.get("forward_from"):
        uid = msg["forward_from"]["id"]
    elif re.fullmatch(r"\d{1,15}", ctx.text.strip()):
        uid = int(ctx.text.strip())
    if not uid:
        ctx.send("❗️ ID raqam faqat sonlardan iborat bo'lishi kerak (masalan: <code>123456789</code>).",
                 cancel_kb())
        return
    ctx.clear_state()
    if ctx.app.is_admin(uid):
        ctx.send("ℹ️ Bu foydalanuvchi allaqachon admin.")
    else:
        ctx.db.add_admin(uid, ctx.user_id)
        ctx.app.invalidate_admins()
        ctx.bot.safe("setMyCommands", {"commands": ADMIN_COMMANDS, "scope": {"type": "chat", "chat_id": uid}})
        notified = True
        try:
            ctx.bot.send_message(uid, "🎉 <b>Tabriklaymiz!</b> Siz botga <b>admin</b> etib tayinlandingiz.\n\n"
                                      "👨‍💻 Admin panelni ochish: /admin", admin_menu())
        except TelegramError:
            notified = False
        ctx.send(f"✅ <code>{uid}</code> admin qilib qo'shildi!" +
                 ("" if notified else "\n\nℹ️ U hali botni ishga tushirmagan — /start bossin, keyin /admin."))
    text, kb = admins_view(ctx)
    ctx.send(text, kb)
