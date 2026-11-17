"""🧾 Admin harakatlari jurnali, egasiga ogohlantirish va 🧰 «Qo'shimcha» vositalar menyusi."""

from __future__ import annotations

import logging
import zlib

from .. import genres
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
    "ban": "🚫 Murojaat/izoh cheklashni o'zgartirdi", "comment_del": "💬 Izohni o'chirdi",
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
        [btn("💬 Izohlar (moderatsiya)", "tl:cm", style=PRIMARY), btn("🧩 To'ldirish kerak", "tl:mi", style=SUCCESS)],
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
    elif action == "cm":
        ctx.edit(*comments_view(ctx))
    elif action == "mi":
        ctx.edit(*missing_view(ctx))
    elif action in ("af", "afy", "afu"):                  # 🤖 avto to'ldirish: ko'rib chiqish → qo'llash → qaytarish (faqat bosh adminlar)
        from .. import autofill
        if not ctx.is_owner:
            ctx.send("⛔️ Faqat bosh adminlar uchun!")
        elif action == "afu":
            n = autofill.undo(ctx.app)
            ctx.edit(f"↩️ Qaytarildi: <b>{n}</b> ta kino avvalgi (bo'sh) holatiga keltirildi." if n else "Qaytarish uchun ma'lumot yo'q.",
                     ikb([btn("⬅️ Orqaga", "tl:mi", style=DANGER)]))
        else:
            items = autofill.plan(ctx.db)
            if not items:
                ctx.edit("🤖 Avto to'ldirish uchun ma'lumot topilmadi: nom va izohdan janr, yil, davlat yoki til aniqlanmadi.",
                         ikb([btn("⬅️ Orqaga", "tl:mi", style=DANGER)]))
            elif action == "af":
                cnt = autofill.summary(items)
                lines = [f"🤖 <b>Avto to'ldirish</b> — <b>{len(items)}</b> ta kino", "",
                         "Faqat <b>bo'sh</b> maydonlar to'ldiriladi, mavjud ma'lumot o'zgarmaydi:"]
                lines += [f"• {autofill.LABELS[k]}: <b>{n}</b> ta" for k, n in cnt.items() if n]
                lines += ["", "<b>Namuna:</b>"]
                for _mid, title, upd in items[:6]:
                    bits = []
                    if "genres" in upd:
                        bits.append(", ".join(genres.name(k) for k in genres.parse(upd["genres"])))
                    if "year" in upd:
                        bits.append(str(upd["year"]))
                    if "country" in upd:
                        bits.append(genres.country_label(upd["country"]))
                    if "lang" in upd:
                        bits.append(genres.lang_label(upd["lang"]))
                    lines.append(f"• {esc(truncate(title, 28))} → {esc(' · '.join(b for b in bits if b))}")
                lines += ["", "Qo'llagandan keyin «↩️ Qaytarish» bilan bekor qilish mumkin."]
                ctx.edit("\n".join(lines), ikb([btn(f"✅ Qo'llash ({len(items)} ta)", "tl:afy", style=SUCCESS)],
                                               [btn("⬅️ Orqaga", "tl:mi", style=DANGER)]))
            else:
                n = autofill.apply(ctx.app, items)
                audit(ctx.app, ctx.user_id, "movie_edit", f"avto to'ldirish: {n} ta kino")
                ctx.edit(f"✅ <b>{n}</b> ta kino to'ldirildi.", ikb([btn("↩️ Qaytarish", "tl:afu", style=DANGER)],
                                                                     [btn("⬅️ Orqaga", "tl:mi", style=PRIMARY)]))
    elif action == "ml" and len(ctx.data.split(":")) > 3:
        parts = ctx.data.split(":")
        ctx.edit(*missing_list_view(ctx, parts[2], int(parts[3]) if parts[3].isdigit() else 0))
    elif action == "mo" and len(ctx.data.split(":")) > 2 and ctx.data.split(":")[2].isdigit():
        from .admin_movies import send_manage
        movie = ctx.db.get_movie(int(ctx.data.split(":")[2]))
        if movie:
            send_manage(ctx, movie)
        else:
            ctx.send("😔 Kino topilmadi.")


def missing_view(ctx: Ctx):
    """🧩 Qaysi kinolarda ma'lumot yetishmayotgani: turlari bo'yicha sonlar."""
    counts = ctx.db.missing_counts()
    total = sum(counts.values())
    lines = ["🧩 <b>To'ldirish kerak bo'lgan ma'lumotlar</b>", ""]
    rows = []
    for k, (label, _) in ctx.db.MISSING.items():
        n = counts[k]
        lines.append(f"{label}: <b>{n}</b>" + (" ✅" if not n else ""))
        if n:
            rows.append([btn(f"{label} ({n})", f"tl:ml:{k}:0", style=PRIMARY)])
    lines.append("")
    lines.append("Hammasi to'liq 🎉" if not total else "Kerakli bo'limni tanlang — kino ro'yxati chiqadi, bosganda tahrirlash oynasi ochiladi. "
                 "💡 Tahrirlash oynasida «🌐 TMDB dan avtomatik to'ldirish» tugmasi bor.")
    if total and getattr(ctx, "is_owner", False):
        rows.append([btn("🤖 Hammasini avto to'ldirish (nom va izohdan)", "tl:af", style=SUCCESS)])
    rows.append([btn("⬅️ Orqaga", "tl:menu", style=DANGER)])
    return "\n".join(lines), ikb(*rows)


def missing_list_view(ctx: Ctx, kind: str, page: int):
    if kind not in ctx.db.MISSING:
        return missing_view(ctx)
    per = 8
    total = ctx.db.missing_counts()[kind]
    page = max(0, min(page, max(0, (total - 1) // per)))
    rows_db = ctx.db.missing_list(kind, per, page * per)
    label = ctx.db.MISSING[kind][0]
    lines = [f"{label} — <b>{total}</b> ta (eng ko'p ko'rilganlari oldin)", ""]
    kb = []
    for r in rows_db:
        code = f" • kod {r['code']}" if r["code"] > 0 else ""
        kb.append([btn(truncate(f"{r['title']}{code}", 48), f"tl:mo:{r['id']}", style=PRIMARY)])
    if not rows_db:
        lines.append("Bu bo'limda hammasi to'liq 🎉")
    nav = []
    if page > 0:
        nav.append(btn("⬅️", f"tl:ml:{kind}:{page - 1}", style=PRIMARY))
    if (page + 1) * per < total:
        nav.append(btn("➡️", f"tl:ml:{kind}:{page + 1}", style=PRIMARY))
    if nav:
        kb.append(nav)
    kb.append([btn("⬅️ Orqaga", "tl:mi", style=DANGER)])
    return "\n".join(lines), ikb(*kb)


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


# ═════════════════════════ 💬 Izohlar moderatsiyasi ═════════════════════════

def comments_view(ctx: Ctx):
    rows = ctx.db.recent_comments(8)
    hidden = ctx.db.recent_comments(5, "hidden")
    lines = ["💬 <b>Oxirgi izohlar</b>", ""]
    kb = []
    if not rows:
        lines.append("Hozircha izoh yo'q.")
    for r in rows:
        lines.append(f"<b>{esc(r['first_name'] or r['user_id'])}</b> → {esc(truncate(r['title'] or '—', 28))}\n"
                     f"    {esc(truncate(r['body'], 90))}")
        kb.append([btn(f"🗑 #{r['id']}", f"cm:del:{r['id']}", style=DANGER),
                   btn(f"🚫 {truncate(str(r['first_name'] or r['user_id']), 14)}", f"cm:ban:{r['id']}", style=DANGER)])
    if hidden:
        lines += ["", "🙈 <b>Shikoyatlar tufayli yashirilgan:</b>"]
        for r in hidden:
            lines.append(f"#{r['id']} — {esc(truncate(r['body'], 70))} ({r['reports']} shikoyat)")
            kb.append([btn(f"♻️ #{r['id']} qaytarish", f"cm:ok:{r['id']}", style=SUCCESS),
                       btn(f"🗑 #{r['id']}", f"cm:del:{r['id']}", style=DANGER)])
    kb.append([btn("🔄 Yangilash", "tl:cm", style=PRIMARY), btn("⬅️ Orqaga", "tl:menu", style=PRIMARY)])
    return "\n".join(lines), ikb(*kb)


def notify_hidden_comment(app, cid: int) -> None:
    row = app.db.get_comment(cid)
    if not row:
        return
    text = (f"🙈 <b>Izoh yashirildi</b> — {row['reports']} ta shikoyat\n\n💬 {esc(truncate(row['body'], 300))}")
    kb = ikb([btn("♻️ Qaytarish", f"cm:ok:{cid}", style=SUCCESS), btn("🗑 O'chirish", f"cm:del:{cid}", style=DANGER)],
             [btn("🚫 Muallifni cheklash", f"cm:ban:{cid}", style=DANGER)])
    for uid in app.config.owners:
        try:
            app.bot.send_message(uid, text, kb)
        except TelegramError:
            pass


@router.callback("cm", admin=True)
def cb_comments(ctx: Ctx) -> None:
    parts = ctx.data.split(":")
    if len(parts) < 3 or not parts[2].isdigit():
        return
    action, cid = parts[1], int(parts[2])
    row = ctx.db.get_comment(cid)
    if action == "del":
        if row:
            ctx.db.delete_comment(cid)
            audit(ctx.app, ctx.user_id, "comment_del", f"{row['body'][:80]} (user {row['user_id']})")
        ctx.answer("🗑 O'chirildi")
    elif action == "ok" and row:
        ctx.db.restore_comment(cid)
        ctx.answer("♻️ Qaytarildi")
    elif action == "ban" and row:
        if ctx.app.is_admin(row["user_id"]):
            ctx.answer("Adminni cheklab bo'lmaydi", alert=True)
            return
        banned = not ctx.db.is_contact_banned(row["user_id"])
        ctx.db.set_contact_banned(row["user_id"], banned)
        audit(ctx.app, ctx.user_id, "ban", f"{row['user_id']}: izoh — {'cheklandi' if banned else 'cheklash olindi'}")
        ctx.answer("🚫 Cheklandi" if banned else "✅ Cheklash olindi", alert=True)
    else:
        ctx.answer("Topilmadi")
        return
    try:
        ctx.edit(*comments_view(ctx))
    except Exception:  # noqa: BLE001 — xabar o'zgarmagan bo'lsa
        pass
