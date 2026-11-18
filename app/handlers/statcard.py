"""📊 /stat — bugungi qisqa hisobot (kecha bilan solishtirib) va «nimani qo'shish kerak» ro'yxati."""

from __future__ import annotations

from datetime import datetime

from ..analytics import DAY, OFF
from ..core import Ctx, router
from ..keyboards import PRIMARY, SUCCESS, btn, ikb
from ..utils import TZ, esc, fmt_num, now, truncate


def _delta(cur: int, prev: int) -> str:
    if not prev:
        return "" if not cur else " 🆕"
    d = (cur - prev) * 100.0 / prev
    if abs(d) < 1:
        return " ＝"
    return f" {'↑' if d > 0 else '↓'}{abs(round(d))}%"


def stat_text(ctx: Ctx) -> str:
    db, t = ctx.db, now()
    day = (t + OFF) // DAY
    t0 = day * DAY - OFF                 # bugun 00:00 (Toshkent)
    y0 = t0 - DAY
    new_t = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ?", (t0,))
    new_y = db.val("SELECT COUNT(*) FROM users WHERE joined_at >= ? AND joined_at < ?", (y0, t0))
    dau = db.val("SELECT COUNT(*) FROM users WHERE last_active >= ?", (t0,))
    wau = db.val("SELECT COUNT(*) FROM users WHERE last_active >= ?", (t0 - 6 * DAY,))
    v_t = db.val("SELECT COALESCE(SUM(n),0) FROM view_days WHERE day = ?", (day,))
    v_y = db.val("SELECT COALESCE(SUM(n),0) FROM view_days WHERE day = ?", (day - 1,))
    s_t = db.val("SELECT COUNT(*) FROM searches WHERE created_at >= ?", (t0,))
    s_y = db.val("SELECT COUNT(*) FROM searches WHERE created_at >= ? AND created_at < ?", (y0, t0))
    f_t = db.val("SELECT COUNT(*) FROM searches WHERE results = 0 AND created_at >= ?", (t0,))
    rev = db.revenue_since(t0)
    som = rev.get("card", 0) + rev.get("provider", 0)
    added = db.val("SELECT COUNT(*) FROM movies WHERE category<>'music' AND created_at >= ?", (t0,))
    open_req = db.count_open_requests(t - 60 * DAY)
    top = db.q("SELECT m.title, SUM(v.n) AS n FROM view_days v JOIN movies m ON m.id=v.movie_id WHERE v.day = ? AND m.category<>'music'"
               " GROUP BY v.movie_id ORDER BY n DESC LIMIT 3", (day,))
    lines = [f"📊 <b>Bugun</b> · {datetime.fromtimestamp(t, TZ).strftime('%d.%m.%Y')}", "",
             f"👥 Yangi: <b>{fmt_num(new_t)}</b>{_delta(new_t, new_y)} <i>(kecha {fmt_num(new_y)})</i>",
             f"🟢 Faol: <b>{fmt_num(dau)}</b> bugun · {fmt_num(wau)} hafta",
             f"👁 Ko'rishlar: <b>{fmt_num(v_t)}</b>{_delta(v_t, v_y)} <i>(kecha {fmt_num(v_y)})</i>",
             f"🔎 Qidiruvlar: <b>{fmt_num(s_t)}</b>{_delta(s_t, s_y)}"
             + (f" · topilmadi <b>{fmt_num(f_t)}</b> ({round(f_t * 100 / s_t)}%)" if s_t else ""),
             f"💰 Tushum: <b>{fmt_num(som)}</b> so'm" + (f" · ⭐ {fmt_num(rev.get('stars', 0))}" if rev.get("stars") else ""),
             f"🎬 Bugun qo'shildi: <b>{fmt_num(added)}</b> · 📥 ochiq so'rovlar: <b>{fmt_num(open_req)}</b>"]
    if top:
        lines += ["", "🔥 <b>Bugun eng ko'p ko'rilgan:</b>"]
        lines += [f"{i}. {esc(truncate(r['title'], 36))} — {fmt_num(r['n'])}" for i, r in enumerate(top, 1)]
    failed = db.failed_queries_detail(t - 7 * DAY, 5)
    if failed:
        lines += ["", "❓ <b>Shularni qo'shing</b> (7 kunda topilmaganlar):"]
        lines += [f"• «{esc(truncate(r['query'], 30))}» — {r['u']} kishi, {r['n']} marta" for r in failed]
    try:
        from .. import webapp
        errs = sum(r[0] for r in webapp._CLIENT_ERRS.values())
        if errs:
            lines += ["", f"🛠 Saytdagi xatolar: <b>{errs}</b> (batafsil: /xatolar)"]
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines)


def _kb():
    return ikb([btn("🔄 Yangilash", "st2:r", style=PRIMARY), btn("❓ Topilmaganlar (15)", "st2:f", style=SUCCESS)],
               [btn("📈 Tahlil", "st2:a", style=PRIMARY)])


def fail_text(ctx: Ctx) -> str:
    rows = ctx.db.failed_queries_detail(now() - 14 * DAY, 15)
    if not rows:
        return "❓ <b>Topilmagan qidiruvlar</b>\n\nOxirgi 14 kunda topilmagan qidiruv yo'q 👍"
    lines = ["❓ <b>Topilmagan qidiruvlar</b> (14 kun) — eng ko'p odam qidirganlari oldin", ""]
    lines += [f"{i}. «{esc(truncate(r['query'], 34))}» — <b>{r['u']}</b> kishi, {r['n']} marta" for i, r in enumerate(rows, 1)]
    lines += ["", "Bu kinolar qo'shilsa, qidirgan foydalanuvchilarga bot o'zi xabar beradi 🔔"]
    return "\n".join(lines)


@router.command("stat", admin=True)
def cmd_stat(ctx: Ctx) -> None:
    ctx.send(stat_text(ctx), _kb())


@router.callback("st2", admin=True)
def cb_stat(ctx: Ctx) -> None:
    act = ctx.data.split(":")[1] if ":" in ctx.data else "r"
    if act == "a":
        from . import analytics_cmd
        ctx.answer()
        ctx.send(analytics_cmd.summary(ctx), analytics_cmd._kb(ctx))
        return
    ctx.answer("🔄" if act == "r" else None)
    try:
        if act == "f":
            ctx.edit(fail_text(ctx), ikb([btn("⬅️ Orqaga", "st2:r", style=PRIMARY)]))
        else:
            ctx.edit(stat_text(ctx), _kb())
    except Exception:  # noqa: BLE001 — matn o'zgarmasa Telegram xato beradi
        pass
