"""🎬 /startmedia — /start xabariga rasm, GIF yoki video qo'yish (admin)."""

from __future__ import annotations

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, cancel_kb, ikb


def media_of(msg: dict):
    """Xabardan (tur, file_id): GIF → animation, video → video, rasm → photo. Yo'q bo'lsa — None."""
    if msg.get("animation"):
        return "animation", msg["animation"]["file_id"]
    if msg.get("video"):
        return "video", msg["video"]["file_id"]
    if msg.get("photo"):
        return "photo", msg["photo"][-1]["file_id"]
    doc = msg.get("document") or {}
    mime = doc.get("mime_type") or ""
    if mime == "image/gif" or mime == "video/mp4":
        return "animation", doc["file_id"]
    if mime.startswith("image/"):
        return "photo", doc["file_id"]
    return None


def save_media(ctx: Ctx, kind: str, file_id: str) -> None:
    ctx.app.set_setting("start_media", f"{kind}:{file_id}")
    ctx.clear_state()
    ctx.send("✅ <b>/start ochilish qiyofasi o'rnatildi!</b> Mana ko'rinishi 👇")
    from .user import send_welcome
    send_welcome(ctx)


@router.command("startmedia", admin=True)
def cmd_startmedia(ctx: Ctx) -> None:
    cur = ctx.app.setting("start_media")
    ctx.set_state("sm:wait")
    rows = [[btn("❌ Bekor qilish", "cancel", style=DANGER)]]
    if cur:
        rows.insert(0, [btn("🗑 Hozirgisini olib tashlash", "sm:off", style=DANGER)])
    ctx.send("🎬 <b>/start ochilish qiyofasi</b>\n\n"
             f"Hozir: <b>{'o‘rnatilgan ✅' if cur else 'yo‘q (faqat matn)'}</b>\n\n"
             "Yangi <b>rasm, GIF yoki video</b> yuboring — foydalanuvchi /start bosganda salom matni shu bilan birga chiqadi.\n"
             "💡 Eng yaxshisi: 16:9 shakldagi qisqa GIF/MP4 (masalan /animatsiya bergan video).", ikb(*rows))


@router.state("sm:wait", admin=True)
def st_startmedia(ctx: Ctx) -> None:
    got = media_of(ctx.message)
    if not got:
        ctx.send("❗️ Rasm, GIF yoki video yuboring.", cancel_kb())
        return
    save_media(ctx, *got)


@router.callback("sm", admin=True)
def cb_startmedia(ctx: Ctx) -> None:
    action = ctx.data.split(":")[1] if ":" in ctx.data else ""
    if action == "off":
        ctx.app.set_setting("start_media", "")
        ctx.clear_state()
        ctx.answer("🗑 Olib tashlandi")
        ctx.edit("🗑 /start qiyofasi olib tashlandi — endi faqat matn chiqadi.")
    elif action == "set":                       # /animatsiya yasagan videoni darhol o'rnatish
        pending = ctx.app.setting("_anim_pending")
        if not pending or ":" not in pending:
            ctx.answer("Video topilmadi — /animatsiya ni qayta yozing", alert=True)
            return
        ctx.answer("✅")
        kind, _, fid = pending.partition(":")
        save_media(ctx, kind, fid)
