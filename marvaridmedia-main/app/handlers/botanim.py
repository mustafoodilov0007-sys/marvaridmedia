"""🎬 /animatsiya — bazadagi haqiqiy posterlardan botning ochilish animatsiyasini (MP4) yasab beradi."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path

from .. import trailer_anim, webapp
from ..core import Ctx, router
from ..keyboards import SUCCESS, btn, ikb
from ..telegram import InputFile, TelegramError

log = logging.getLogger("botanim")
_busy = threading.Lock()


@router.command("animatsiya", admin=True)
def cmd_animation(ctx: Ctx) -> None:
    if not trailer_anim.available():
        ctx.send("❌ Serverda <b>Pillow</b> yoki <b>ffmpeg</b> o'rnatilmagan — animatsiya yasab bo'lmaydi.")
        return
    app, db = ctx.app, ctx.db
    cache = Path(app.config.db_path).parent / "posters"
    rows = [r for r in db.catalog("video", "top", None, 60) if r["poster_id"]][:32]
    if len(rows) < 4:
        ctx.send("❗️ Animatsiya uchun kamida <b>4 ta posterli kino</b> kerak. Avval kinolarga poster qo'shing.")
        return
    if not _busy.acquire(blocking=False):
        ctx.send("⏳ Animatsiya allaqachon tayyorlanmoqda — biroz kuting.")
        return
    chat = ctx.chat_id
    ctx.send(f"⏳ <b>{len(rows)} ta poster</b>dan animatsiya tayyorlanmoqda… (1–2 daqiqa)")

    def work() -> None:
        try:
            posters = []
            for r in rows:
                data = webapp.poster_bytes(app, r["id"], cache, 360)
                if data:
                    posters.append(data)
            with tempfile.TemporaryDirectory() as tmp:
                out = os.path.join(tmp, "marvarid_start.mp4")
                trailer_anim.build(posters, out)
                data = Path(out).read_bytes()
            sent = app.bot.call("sendAnimation", {"chat_id": chat, "width": 640, "height": 360, "duration": 8,
                                                  "caption": ("🎬 <b>Tayyor!</b>\n\n"
                                                              "1️⃣ Pastdagi tugma bilan /start xabariga qo'ying.\n"
                                                              "2️⃣ @BotFather → /mybots → botingiz → Edit Bot → <b>Edit Description Picture</b> → "
                                                              "shu videoni yuboring (forward qiling)."),
                                                  "parse_mode": "HTML",
                                                  "reply_markup": ikb([btn("✅ /start ga qo'yish", "sm:set", style=SUCCESS)])},
                                files={"animation": InputFile("marvarid_start.mp4", data, "video/mp4")})
            fid = ((sent or {}).get("animation") or {}).get("file_id")
            if fid:
                app.set_setting("_anim_pending", f"animation:{fid}")
        except (TelegramError, RuntimeError, ValueError, OSError) as exc:
            log.exception("Animatsiya yasab bo'lmadi")
            app.bot.safe("sendMessage", {"chat_id": chat, "text": f"❌ Animatsiya yasab bo'lmadi: {str(exc)[:200]}"})
        finally:
            _busy.release()

    threading.Thread(target=work, name="botanim", daemon=True).start()
