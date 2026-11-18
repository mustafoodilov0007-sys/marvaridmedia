"""🩺 Ishonchlilik: xatolar haqida egaga darhol xabar va /status (bot holati)."""

from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import traceback
from collections import deque

from ..core import Ctx, router
from ..keyboards import PRIMARY, btn, ikb
from ..utils import esc, fmt_datetime, fmt_duration, fmt_num, now

log = logging.getLogger("ops")

ALERT_WINDOW = 900        # bir xil xato shuncha soniya ichida qayta yuborilmaydi
ALERT_PER_HOUR = 6        # soatiga ko'pi bilan shuncha xabar (xato yog'ilib ketsa, chat to'lib qolmasin)


class OwnerAlerts(logging.Handler):
    """ERROR darajasidagi har bir xatoni bosh adminlarga yuboradi (takrorlarini va ortiqchasini bostirib)."""

    def __init__(self, app):
        super().__init__(level=logging.ERROR)
        self.app = app
        self.seen: dict = {}
        self.sent: deque = deque()
        self.suppressed = 0
        self._mu = threading.Lock()   # (logging.Handler.lock bilan adashmasin)
        app.recent_errors = deque(maxlen=30)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name in ("ops", "telegram.send"):
                return
            msg = record.getMessage()
            t = time.time()
            self.app.recent_errors.append((t, record.name, msg[:160]))
            key = (record.name, msg[:90])
            with self._mu:
                if t - self.seen.get(key, 0) < ALERT_WINDOW:
                    return
                self.seen[key] = t
                if len(self.seen) > 500:
                    self.seen.clear()
                while self.sent and t - self.sent[0] > 3600:
                    self.sent.popleft()
                if len(self.sent) >= ALERT_PER_HOUR:
                    self.suppressed += 1
                    return
                self.sent.append(t)
                extra, self.suppressed = self.suppressed, 0
            trace = ""
            if record.exc_info:
                trace = "".join(traceback.format_exception(*record.exc_info))[-650:]
            text = (f"🚨 <b>Bot xatosi</b>\n🕐 {fmt_datetime(int(t))}\n📍 <code>{esc(record.name)}</code>\n"
                    f"❗️ {esc(msg[:300])}" + (f"\n<pre>{esc(trace)}</pre>" if trace else "") +
                    (f"\n\nℹ️ Oldingi soatda yana {extra} ta xato bostirildi." if extra else "") +
                    "\n\n<i>Shu xato 15 daqiqa ichida takror yuborilmaydi. Holat: /status</i>")
            threading.Thread(target=self._send, args=(text,), daemon=True, name="owner-alert").start()
        except Exception:  # noqa: BLE001 — jurnal yozuvi hech qachon dasturni buzmasligi kerak
            pass

    def _send(self, text: str) -> None:
        for uid in self.app.config.owners:
            self.app.bot.safe("sendMessage", {"chat_id": uid, "text": text[:4000], "parse_mode": "HTML",
                                              "disable_web_page_preview": True})


@router.on_startup
def install_alerts(app) -> None:
    root = logging.getLogger()
    if not any(isinstance(h, OwnerAlerts) for h in root.handlers):
        root.addHandler(OwnerAlerts(app))


def _rss_mb() -> float:
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:  # noqa: BLE001
        return 0.0


def status_text(ctx: Ctx) -> str:
    app, db = ctx.app, ctx.db
    t0 = time.perf_counter()
    ok = app.bot.safe("getMe") is not None
    ping = (time.perf_counter() - t0) * 1000
    c = db.count_by_category()
    errs = [e for e in getattr(app, "recent_errors", []) if time.time() - e[0] < 86400]
    queue = sum(q.qsize() for q in app.workers.queues) if app.workers else 0
    try:
        du = shutil.disk_usage(db.path.parent)
        disk = f"{du.free / 1e9:.1f} GB bo'sh ({du.used * 100 // du.total}% band)"
    except OSError:
        disk = "—"
    size = sum(p.stat().st_size for p in db.path.parent.glob(db.path.name + "*") if p.is_file()) / 1e6
    last_backup = int(db.get_settings().get("last_auto_backup", "0") or 0)
    sha = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:7]
    lines = [
        "🩺 <b>Bot holati</b>", "",
        f"{'🟢' if ok else '🔴'} Telegram: <b>{'ulangan' if ok else 'javob bermayapti'}</b> ({ping:.0f} ms)",
        f"⏱ Ishlash vaqti: <b>{fmt_duration(now() - app.started_at)}</b>" + (f" • versiya <code>{sha}</code>" if sha else ""),
        f"🧠 Xotira: <b>{_rss_mb():.0f} MB</b> • navbat: <b>{queue}</b>",
        f"🗄 Baza: <b>{size:.1f} MB</b> • disk: {disk}",
        f"👥 Foydalanuvchilar: <b>{fmt_num(db.count_users())}</b> • 🎬 {fmt_num(c['movie'])} / 📺 {fmt_num(c['serial'])} / "
        f"🧸 {fmt_num(c['cartoon'])} / 🎵 {fmt_num(c['music'])}",
        f"💾 Oxirgi avto-zaxira: <b>{fmt_datetime(last_backup) if last_backup else 'hali yo‘q'}</b>",
        f"💎 Premium emoji rad etilgan: <b>{app.bot.emoji_fail}</b> marta",
        f"{'⚠️' if errs else '✅'} 24 soatdagi xatolar: <b>{len(errs)}</b>",
    ]
    for ts, name, msg in errs[-3:]:
        lines.append(f"   • <code>{esc(name)}</code> {esc(msg[:90])}")
    lines += ["", f"🕐 {fmt_datetime(now())}"]
    return "\n".join(lines)


@router.command("status", admin=True)
def cmd_status(ctx: Ctx) -> None:
    ctx.send(status_text(ctx), ikb([btn("🔄 Yangilash", "ops:status", style=PRIMARY)]))


@router.callback("ops", admin=True)
def cb_ops(ctx: Ctx) -> None:
    ctx.answer("🔄")
    try:
        ctx.edit(status_text(ctx), ikb([btn("🔄 Yangilash", "ops:status", style=PRIMARY)]))
    except Exception:  # noqa: BLE001 — matn o'zgarmagan bo'lsa Telegram xato beradi
        pass
