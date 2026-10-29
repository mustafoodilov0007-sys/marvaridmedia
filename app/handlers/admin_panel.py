"""Admin panel: kirish, 📊 Statistika, 💾 zaxira nusxa va 👮 Adminlar."""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

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
    {"command": "emoji", "description": "💎 Premium emoji tekshiruvi"},
    {"command": "almashtir", "description": "💎 Bot emojilarini premium qilish"},
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
    c = db.count_by_category()
    text = ("👨‍💻 <b>Admin panel</b> — " + esc(ctx.app.brand) + "\n\n"
            f"👥 Foydalanuvchilar: <b>{fmt_num(db.count_users())}</b> "
            f"(+{fmt_num(db.count_joined_since(day_start()))} bugun)\n"
            f"🎬 Kontent: <b>{fmt_num(db.count_movies())}</b>"
            f" (🎬 {c['movie']} • 📺 {c['serial']} • 🧸 {c['cartoon']} • 🎵 {c['music']})\n"
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
    cats = db.count_by_category()

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
        f"🎬 <b>Kontent:</b> {fmt_num(db.count_movies())}",
        f"├ 🎬 Kinolar: {fmt_num(cats['movie'])}",
        f"├ 📺 Seriallar: {fmt_num(cats['serial'])}",
        f"├ 🧸 Multfilmlar: {fmt_num(cats['cartoon'])}",
        f"├ 🎵 Musiqalar: {fmt_num(cats['music'])}",
        f"├ 🎞 Ko'p qismlilar: {fmt_num(db.count_serials())}",
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
        rows.append([btn("💾 Zaxira nusxa (backup)", "stat:backup", style=SUCCESS),
                     btn("📥 Bazani tiklash", "stat:restore", style=DANGER)])
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
    elif action == "restore":
        if not ctx.is_owner:
            ctx.answer("⛔️ Faqat bosh adminlar uchun!", alert=True)
            return
        ctx.answer()
        ctx.set_state("db:restore")
        ctx.send("📥 <b>Bazani tiklash</b>\n\n"
                 "Eski bazaning faylini (<code>bot.db</code> yoki «💾 Zaxira nusxa» bergan "
                 "<code>marvarid_backup_....db</code>) <b>fayl</b> ko'rinishida yuboring.\n\n"
                 "Bot faylni tekshiradi va ichida nechta kino, foydalanuvchi borligini ko'rsatadi — "
                 "tasdiqlamaguningizcha hech narsa o'zgarmaydi.", cancel_kb())
    elif action in ("restok", "restno"):
        if not ctx.is_owner:
            ctx.answer("⛔️ Faqat bosh adminlar uchun!", alert=True)
            return
        path = ctx.sdata.get("path") if ctx.state == "db:confirm" else None
        ctx.clear_state()
        if action == "restno" or not path or not Path(path).exists():
            if path:
                _drop_restore_files(Path(path))
            ctx.answer("❌ Bekor qilindi")
            ctx.edit("❌ Bazani tiklash bekor qilindi.")
            return
        ctx.answer("⏳ Tiklanmoqda...")
        ctx.edit("⏳ <b>Tiklanmoqda...</b> Avval hozirgi bazaning zaxira nusxasi yuboriladi.")
        send_backup(ctx)
        try:
            ctx.db.restore_from(Path(path))
        finally:
            _drop_restore_files(Path(path))
        app = ctx.app
        app.load_settings()
        app.invalidate_admins()
        app.search_cache.clear()
        app.sub_cache.clear()
        c = ctx.db.count_by_category()
        log.warning("Baza zaxira nusxadan tiklandi (admin %s)", ctx.user_id)
        ctx.send("✅ <b>Baza tiklandi!</b>\n\n"
                 f"🎬 Kontent: <b>{fmt_num(ctx.db.count_movies())}</b> "
                 f"(🎬 {c['movie']} • 🧸 {c['cartoon']} • 🎵 {c['music']})\n"
                 f"👥 Foydalanuvchilar: <b>{fmt_num(ctx.db.count_users())}</b>")


def _drop_restore_files(path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        Path(str(path) + suffix).unlink(missing_ok=True)


def _download(ctx: Ctx, doc: dict, target: Path) -> bool:
    if (doc.get("file_size") or 0) > 20 * 1024 * 1024:
        ctx.send("❌ Fayl 20 MB dan katta — Telegram bot orqali yuklab bo'lmaydi.", cancel_kb())
        return False
    try:
        info = ctx.bot.call("getFile", {"file_id": doc["file_id"]})
        target.write_bytes(ctx.bot.download_file(info["file_path"]))
    except (TelegramError, KeyError, OSError) as exc:
        ctx.send(f"❌ Faylni yuklab bo'lmadi: {esc(str(exc))}", cancel_kb())
        return False
    return True


def _confirm_restore(ctx: Ctx, path: Path, movies: int, users: int, with_wal: bool) -> None:
    ctx.set_state("db:confirm", path=str(path), wal=with_wal, started=True)
    wal_line = ("✅ <code>bot.db-wal</code> fayli ham qo'shildi.\n\n" if with_wal else
                "💡 Kompyuterdagi <code>data</code> papkasida <code>bot.db</code> yonida "
                "<code>bot.db-wal</code> fayli ham bo'lsa — uni ham hozir yuboring "
                "(unda oxirgi qo'shilgan kinolar bo'lishi mumkin).\n\n")
    ctx.send("📦 <b>Fayl tekshirildi:</b>\n\n"
             f"🎬 Kinolar: <b>{fmt_num(movies)}</b>\n"
             f"👥 Foydalanuvchilar: <b>{fmt_num(users)}</b>\n\n"
             + wal_line +
             f"Hozirgi bazada: 🎬 <b>{fmt_num(ctx.db.count_movies())}</b> kino, "
             f"👥 <b>{fmt_num(ctx.db.count_users())}</b> foydalanuvchi.\n\n"
             "⚠️ Tiklasangiz, hozirgi baza shu fayl bilan <b>almashtiriladi</b> "
             "(hozirgisining zaxira nusxasi avval sizga yuboriladi). Davom etamizmi?",
             ikb([btn("✅ Ha, tiklash", "stat:restok", style=SUCCESS)],
                 [btn("❌ Yo'q", "stat:restno", style=DANGER)]))


def inspect_db(path: Path):
    """Faylni SQLite baza sifatida ochib, (kinolar, foydalanuvchilar) sonini qaytaradi. Yaroqsiz — None."""
    try:
        conn = sqlite3.connect(str(path))  # yonidagi -wal fayl ham hisobga olinadi
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"movies", "parts", "users"} <= tables:
                return None
            movies = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
            users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            return movies, users
        finally:
            conn.close()
    except sqlite3.Error:
        return None


@router.state("db:restore", "db:confirm", admin=True)
def st_restore(ctx: Ctx) -> None:
    """bot.db va (bo'lsa) bot.db-wal fayllarini istalgan tartibda qabul qiladi."""
    if not ctx.is_owner:
        ctx.clear_state()
        return
    doc = ctx.message.get("document")
    if not doc:
        if ctx.state == "db:confirm":
            ctx.send("👆 Yuqoridagi tugmalardan birini tanlang: «✅ Ha, tiklash» yoki «❌ Yo'q».")
        else:
            ctx.send("❗️ Baza faylini <b>fayl (document)</b> ko'rinishida yuboring.", cancel_kb())
        return
    name = doc.get("file_name") or ""
    if name.endswith("-shm"):
        ctx.send("ℹ️ <code>-shm</code> fayl kerak emas — faqat <code>bot.db</code> va <code>bot.db-wal</code>.")
        return
    path = ctx.db.path.with_name(f"restore_{ctx.user_id}.db")
    is_wal = name.endswith("-wal")
    if not ctx.sdata.get("started"):
        _drop_restore_files(path)  # yangi tiklash — eski qoldiqlarni tozalaymiz
    target = Path(str(path) + "-wal") if is_wal else path
    if not _download(ctx, doc, target):
        return
    has_main = path.exists()
    has_wal = Path(str(path) + "-wal").exists()
    ctx.set_state("db:restore", started=True)
    if not has_main:
        ctx.send("✅ <code>bot.db-wal</code> qabul qilindi. Endi asosiy <code>bot.db</code> faylini yuboring.",
                 cancel_kb())
        return
    found = inspect_db(path)
    if not found and has_wal:
        Path(str(path) + "-wal").unlink(missing_ok=True)  # mos kelmagan wal — usiz urinib ko'ramiz
        Path(str(path) + "-shm").unlink(missing_ok=True)
        has_wal = False
        found = inspect_db(path)
    if not found:
        ctx.send("⚠️ Bu fayldan kinolarni o'qib bo'lmadi.\n\n"
                 "Agar papkada <code>bot.db-wal</code> fayli ham bo'lsa — uni yuboring (ma'lumotlar unda "
                 "bo'lishi mumkin). Bo'lmasa, to'g'ri <code>bot.db</code> faylini yuboring.", cancel_kb())
        return
    _confirm_restore(ctx, path, found[0], found[1], has_wal)


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


@router.task
def _auto_backup(app) -> None:
    """Har 24 soatda bazaning nusxasini bosh adminlarga o'zi yuboradi (server o'chib qolsa ham ma'lumot saqlansin)."""
    import time
    day = 24 * 3600
    while not app.stopping.is_set():
        try:
            last = int(app.db.get_settings().get("last_auto_backup", "0") or 0)
        except ValueError:
            last = 0
        wait = last + day - time.time()
        if wait > 0:
            if app.stopping.wait(min(wait, 3600)):
                return
            continue
        db = app.db
        tmp = db.path.with_name("auto_backup_tmp.db")
        try:
            db.backup_to(tmp)
            data = tmp.read_bytes()
        except Exception:
            log.exception("Avto-zaxira yaratib bo'lmadi")
            app.stopping.wait(3600)
            continue
        finally:
            try:
                tmp.unlink()
            except OSError:
                pass
        db.set_setting("last_auto_backup", str(int(time.time())))
        if len(data) > 49 * 1024 * 1024:
            continue
        name = f"marvarid_avto_{fmt_datetime(now()).replace(' ', '_').replace(':', '-')}.db"
        for uid in app.config.owners:
            try:
                app.bot.send_document(uid, file=InputFile(name, data),
                                      caption="💾 <b>Kunlik avtomatik zaxira nusxa</b>\n\n"
                                              "Faylni saqlab qo'ying. Kerak bo'lsa admin panel → Zaxira → "
                                              "«tiklash» orqali qaytarasiz.")
            except TelegramError:
                log.warning("Avto-zaxirani %s ga yuborib bo'lmadi", uid)


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
