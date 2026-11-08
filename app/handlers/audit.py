"""🧾 Admin harakatlari jurnali, egasiga ogohlantirish va 🧰 «Qo'shimcha» vositalar menyusi."""

from __future__ import annotations

import logging
import zlib

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb
from ..telegram import TelegramError
from ..texts import B
from ..utils import esc, fmt_datetime, truncate

log = logging.getLogger("admin.audit")

ACTION_LABELS = {
    "movie_add": "🎬 Kino qo'shdi", "movie_del": "🗑 Kino o'chirdi", "movie_restore": "♻️ Kinoni tikladi",
    "movie_edit": "✏️ Kinoni tahrirladi", "premium_give": "🎁 Premium berdi", "premium_take": "🚫 Premiumni oldi",
    "plan_add": "➕ Tarif qo'shdi", "plan_del": "🗑 Tarifni o'chirdi", "toggle": "⚙️ Sozlamani o'zgartirdi",
    "setting": "⚙️ Matn/sozlamani o'zgartirdi", "broadcast": "✉️ Xabar yubordi", "admin_add": "👮 Admin qo'shdi",
    "admin_del": "👮 Adminni o'chirdi", "announce": "📢 Kanalga e'lon qildi", "channel": "🔗 Kanalni o'zgartirdi",
    "ban": "🚫 Murojaatni cheklashni o'zgartirdi",
}


def audit(app, admin_id: int, action: str, detail: str = "", notify: bool = False) -> None:
    """Jurnalga yozadi; notify=True bo'lsa va harakat egasi bo'lmagan admindan kelsa — bosh adminlarga xabar yuboradi."""
    try:
        app.db.log_action(admin_id, action, detail)
    except Exception:
        log.exception("Jurnalga yozib bo'lmadi")
    if notify and admin_id not in app.config.owners:
        u = app.db.get_user(admin_id)
        name = esc(u["first_name"]) if u and u["first_name"] else str(admin_id)
        text = (f"🧾 <b>Admin harakati:</b> {ACTION_LABELS.get(action, action)}\n"
                f"👤 {name} (<code>{admin_id}</code>)\n{esc(truncate(detail, 200))}")
        for uid in app.config.owners:
            try:
                app.bot.send_message(uid, text)
            except TelegramError:
                pass


def journal_text(ctx: Ctx) -> str:
    rows = ctx.db.recent_actions(25)
    if not rows:
        return "🧾 <b>Admin harakatlari jurnali</b>\n\nHozircha yozuv yo'q."
    lines = ["🧾 <b>Admin harakatlari</b> (oxirgi 25 ta)", ""]
    for r in rows:
        name = esc(r["first_name"] or str(r["admin_id"]))
        lines.append(f"{fmt_datetime(r['ts'])} • <b>{name}</b>\n    {ACTION_LABELS.get(r['action'], r['action'])}"
                     + (f" — {esc(truncate(r['detail'], 80))}" if r["detail"] else ""))
    return "\n".join(lines)


@router.command("jurnal", owner=True)
def cmd_journal(ctx: Ctx) -> None:
    ctx.send(journal_text(ctx), ikb([btn("🔄 Yangilash", "tl:jr", style=PRIMARY)]))


# ═════════════════════════ 🧰 Qo'shimcha vositalar ═════════════════════════

def tools_menu(ctx: Ctx):
    db = ctx.db
    text = ("🧰 <b>Qo'shimcha vositalar</b>\n\n"
            f"📥 Ochiq murojaat/so'rovlar: <b>{db.open_tickets()}</b>\n"
            f"♻️ Chiqindi qutisida: <b>{len(db.list_trash(100))}</b> ta kino")
    rows = [
        [btn("📥 So'rovlar (eng ko'p so'ralgan)", "tl:rq", style=SUCCESS)],
        [btn("📈 Tahlil", "tl:an", style=PRIMARY), btn("🩺 Bot holati", "tl:st", style=PRIMARY)],
        [btn("📅 Kun kinosi", "tl:kk", style=PRIMARY), btn("🌐 Sayt posti", "tl:sp", style=PRIMARY)],
        [btn("♻️ Chiqindi qutisi", "tl:tr", style=SUCCESS), btn("✉️ Yuborilgan xabarlar", "tl:bc", style=SUCCESS)],
    ]
    if ctx.is_owner:
        rows.append([btn("🧾 Admin jurnali", "tl:jr", style=DANGER)])
    rows.append([btn("❌ Yopish", "x", style=DANGER)])
    return text, ikb(*rows)


@router.button(B.TOOLS, admin=True)
def btn_tools(ctx: Ctx) -> None:
    ctx.send(*tools_menu(ctx))


@router.callback("tl", admin=True)
def cb_tools(ctx: Ctx) -> None:
    from . import admin_site, analytics_cmd, daily, ops
    action = ctx.data.split(":")[1] if ":" in ctx.data else ""
    if action in ("jr",) and not ctx.is_owner:
        ctx.answer("⛔️ Faqat bosh adminlar uchun!", alert=True)
        return
    ctx.answer()
    if action == "menu":
        ctx.edit(*tools_menu(ctx))
    elif action == "jr":
        kb = ikb([btn("🔄 Yangilash", "tl:jr", style=PRIMARY)], [btn("⬅️ Orqaga", "tl:menu", style=DANGER)])
        try:
            ctx.edit(journal_text(ctx), kb)
        except Exception:  # noqa: BLE001 — matn o'zgarmasa Telegram xato beradi
            pass
    elif action == "an":
        ctx.send(analytics_cmd.summary(ctx), analytics_cmd._kb(ctx))
    elif action == "st":
        ctx.send(ops.status_text(ctx), ikb([btn("🔄 Yangilash", "ops:status", style=PRIMARY)]))
    elif action == "kk":
        ctx.send(*daily.view(ctx))
    elif action == "sp":
        admin_site.cmd_saytpost(ctx)
    elif action == "rq":
        ctx.edit(*requests_view(ctx))
    elif action == "rqx" and len(ctx.data.split(":")) > 2:
        # shu so'rovni yopish (qo'shilmaydi) — nomning birinchi 40 belgisi bo'yicha
        key = ctx.data.split(":", 2)[2]
        for r in ctx.db.top_requests(40):
            if _h(r["norm"]) == key:
                ctx.db.dismiss_request_norm(r["norm"])
                audit(ctx.app, ctx.user_id, "movie_edit", f"so'rov yopildi: {r['query']}")
                break
        ctx.edit(*requests_view(ctx))
    elif action == "tr":
        ctx.edit(*trash_view(ctx))
    elif action == "trr" and len(ctx.data.split(":")) > 2 and ctx.data.split(":")[2].isdigit():
        mid = ctx.db.restore_trash(int(ctx.data.split(":")[2]))
        if mid:
            m = ctx.db.get_movie(mid)
            audit(ctx.app, ctx.user_id, "movie_restore", f"{m['title']} (kod {m['code']})")
            ctx.send(f"♻️ <b>{esc(m['title'])}</b> qaytarildi. Kodi: <code>{m['code']}</code>")
        else:
            ctx.send("😔 Qutida topilmadi.")
        ctx.edit(*trash_view(ctx))
    elif action == "bc":
        ctx.edit(*broadcasts_view(ctx))


def _h(norm: str) -> str:
    return "%08x" % zlib.crc32(norm.encode("utf-8"))


def requests_view(ctx: Ctx):
    from ..utils import now
    rows = ctx.db.top_requests(15, now() - 30 * 86400)
    lines = ["📥 <b>Foydalanuvchilar so'ragan kinolar</b> (oxirgi 30 kun)", ""]
    kb = []
    if not rows:
        lines.append("Hozircha ochiq so'rov yo'q 👍")
    for i, r in enumerate(rows, 1):
        lines.append(f"<b>{i}.</b> {esc(truncate(r['query'], 50))} — 👥 {r['n']} kishi")
        kb.append([btn(f"🗑 {i}. yopish (qo'shilmaydi)", f"tl:rqx:{_h(r['norm'])}", style=DANGER)])
    lines += ["", "ℹ️ Kino qo'shilganda, so'ragan hammaga avtomatik xabar boradi. "
                  "Qo'shmaslikka qaror qilsangiz — «yopish» ni bosing."]
    kb.append([btn("⬅️ Orqaga", "tl:menu", style=PRIMARY)])
    return "\n".join(lines), ikb(*kb)


def trash_view(ctx: Ctx):
    rows = ctx.db.list_trash(12)
    lines = ["♻️ <b>Chiqindi qutisi</b> — o'chirilgan kinolar 30 kun saqlanadi", ""]
    kb = []
    if not rows:
        lines.append("Quti bo'sh.")
    for r in rows:
        who = ctx.db.get_user(r["deleted_by"])
        lines.append(f"• {esc(truncate(r['title'], 40))} (kod {r['code']}) — {fmt_datetime(r['deleted_at'])}"
                     f", {esc((who['first_name'] if who else '') or r['deleted_by'])}")
        kb.append([btn(f"♻️ {truncate(r['title'], 30)} — qaytarish", f"tl:trr:{r['id']}", style=SUCCESS)])
    lines.append("\nℹ️ Qaytarilganda kino, qismlari va shortslari tiklanadi (baho va tarix tiklanmaydi).")
    kb.append([btn("⬅️ Orqaga", "tl:menu", style=PRIMARY)])
    return "\n".join(lines), ikb(*kb)


def broadcasts_view(ctx: Ctx):
    from ..utils import fmt_num
    rows = ctx.db.recent_broadcasts(8)
    lines = ["✉️ <b>Yuborilgan xabarlar</b> (oxirgi 8 ta)", ""]
    if not rows:
        lines.append("Hozircha yuborilmagan.")
    label = {"running": "⏳ davom etmoqda", "done": "✅ yakunlandi", "cancelled": "⏹ to'xtatildi", "interrupted": "⚠️ uzilgan"}
    for r in rows:
        lines.append(f"{fmt_datetime(r['created_at'])} • {label.get(r['status'], r['status'])}\n"
                     f"    👥 {fmt_num(r['done'])}/{fmt_num(r['total'])} • ✅ {fmt_num(r['ok'])} • "
                     f"🚫 {fmt_num(r['blocked'])} • ❌ {fmt_num(r['failed'])}")
    return "\n".join(lines), ikb([btn("⬅️ Orqaga", "tl:menu", style=PRIMARY)])
