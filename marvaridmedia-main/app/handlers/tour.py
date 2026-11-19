"""🧭 Yangi foydalanuvchi uchun 3 qadamli qisqa tanishtiruv (birinchi /start dan keyin, bir marta)."""

from __future__ import annotations

from ..core import Ctx, router
from ..keyboards import DANGER, PRIMARY, SUCCESS, btn, ikb

STEPS = [
    ("🧭 <b>1/3 — Qidirish</b>\n\nKino <b>nomini</b> yoki kanaldagi postdagi <b>kodni</b> yozing — kino darhol keladi.\n"
     "Topilmasa, /sorov bilan so'rang: kino qo'shilishi bilan xabar beramiz."),
    ("🧭 <b>2/3 — Sayt va saqlash</b>\n\nKino ostida 👍 baho, 📤 ulashish va «💬 Izohlar va batafsil» tugmalari bor. "
     "Sayt orqali kinolarni saqlab, izoh qoldirishingiz mumkin: pastdagi «🌐 Sayt» tugmasi (yoki /sayt)."),
    ("🧭 <b>3/3 — Xabardor bo'ling</b>\n\nSevimli janrlaringizni tanlang — shu janrda yangi kino chiqsa, bot o'zi xabar beradi. "
     "Faqat siz xohlagan kinolar, kuniga ko'pi bilan 3 ta."),
]


def _kb(step: int):
    if step < len(STEPS) - 1:
        return ikb([btn("Keyingisi ➡️", f"tu:{step + 1}", style=PRIMARY), btn("O'tkazib yuborish", "tu:x", style=DANGER)])
    return ikb([btn("🔔 Janrlarni tanlash", "tu:fw", style=SUCCESS)], [btn("✅ Tushunarli", "tu:x", style=PRIMARY)])


def start_tour(ctx: Ctx) -> None:
    ctx.send(STEPS[0], _kb(0))


@router.callback("tu", gate=False)
def cb_tour(ctx: Ctx) -> None:
    arg = ctx.data.split(":", 1)[1] if ":" in ctx.data else ""
    if arg.isdigit() and int(arg) < len(STEPS):
        ctx.answer()
        ctx.edit(STEPS[int(arg)], _kb(int(arg)))
    elif arg == "fw":
        ctx.answer()
        ctx.edit("✅ Tanishtiruv tugadi. Janrlarni tanlang 👇")
        from .follow import cmd_follow
        cmd_follow(ctx)
    else:
        ctx.answer("👍")
        ctx.edit("✅ Tayyor! Kino nomini yozing — qolganini o'zim bajaraman 🍿\n\n<i>Tanishtiruvni qayta ko'rish: /yordam</i>")
