"""📜 Saytdagi huquqiy sahifalar: foydalanish shartlari va maxfiylik siyosati."""

from __future__ import annotations

from html import escape as _e

TERMS = [
    ("Umumiy", "Ushbu sayt va Telegram bot kinolar, seriallar, multfilmlar va musiqalarni qulay topish va tomosha qilish uchun xizmat qiladi. "
               "Saytdan foydalanish orqali siz quyidagi shartlarga rozilik bildirasiz."),
    ("Foydalanish", "Xizmatdan faqat shaxsiy, notijorat maqsadda foydalaning. Saytga zarar yetkazish, avtomatik ommaviy so'rovlar yuborish, "
                    "boshqa foydalanuvchilarni aldash yoki bezovta qilish taqiqlanadi."),
    ("Izohlar", "Izohlarda haqorat, spam, reklama va begona havolalar yozish mumkin emas. Qoidabuzar izohlar o'chiriladi, "
                "takrorlansa izoh qoldirish huquqi cheklanadi."),
    ("Kontent va mualliflik huquqi", "Agar biror kontent mualliflik huquqingizni buzayotgan bo'lsa, botdagi «Aloqa» orqali yozing — "
                                     "tekshirib, zarur bo'lsa olib tashlaymiz."),
    ("Premium va to'lovlar", "Premium obuna belgilangan muddatga beriladi. To'lovlar Telegram Stars yoki to'lov tizimlari orqali amalga oshadi; "
                             "to'lovga oid savollar bo'yicha botdagi /paysupport buyrug'idan foydalaning."),
    ("Javobgarlik", "Xizmat «mavjud holda» taqdim etiladi: uzilishlar yoki o'zgarishlar bo'lishi mumkin. Ma'muriyat shartlarni o'zgartirish huquqini saqlab qoladi."),
]

PRIVACY = [
    ("Qanday ma'lumot yig'iladi", "Telegram orqali kirganda: Telegram ID, ism va (bo'lsa) foydalanuvchi nomi. Google orqali kirganda: ism, email va profil rasmi. "
                                  "Shuningdek: sevimli kinolar, ko'rish tarixi, qidiruvlar, baholar va izohlaringiz."),
    ("Nima uchun kerak", "Xizmatni ishlatish (sevimlilar, «Davom ettiring», tavsiyalar), izoh va bahoni saqlash, Premium'ni boshqarish va "
                         "umumiy statistika (qaysi kinolar mashhur) uchun."),
    ("Parol so'ralmaydi", "Telegram orqali kirishda parolingiz so'ralmaydi: kirish botda tasdiqlanadi. Google bilan kirishda faqat Google tasdiqlagan ma'lumot olinadi."),
    ("Uchinchi tomonlar", "Saytda reklama tarmog'i (Yandex) ishlatilishi mumkin: u o'z cookie-fayllari va qurilma ma'lumotlaridan foydalanadi. "
                          "Ma'lumotlaringizni sotmaymiz va reklama uchun shaxsiy ma'lumotingizni uzatmaymiz."),
    ("Saqlash va qurilmangizdagi ma'lumot", "Mavzu, til va sessiya kabi sozlamalar brauzeringizda (localStorage) saqlanadi. Brauzer ma'lumotlarini tozalasangiz, ular o'chadi."),
    ("Ma'lumotni o'chirish", "Hisobingiz va izohlaringizni o'chirish uchun botdagi «Aloqa» orqali yozing — murojaatni ko'rib chiqib, ma'lumotni o'chiramiz."),
]


def page(kind: str, brand: str, bot: str, base: str) -> str:
    title, blocks = ("Foydalanish shartlari", TERMS) if kind == "terms" else ("Maxfiylik siyosati", PRIVACY)
    body = "".join(f"<h2>{_e(h)}</h2><p>{_e(t)}</p>" for h, t in blocks)
    contact = f'<p class="c">Savollar bo\'yicha: <a href="https://t.me/{_e(bot)}">@{_e(bot)}</a></p>' if bot else ""
    return f"""<!doctype html><html lang="uz"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(title)} — {_e(brand)}</title><meta name="robots" content="index,follow"><link rel="canonical" href="{_e(base)}/{'shartlar' if kind == 'terms' else 'maxfiylik'}">
<style>:root{{color-scheme:dark light}}body{{margin:0;background:#0b0a0d;color:#f1e8d4;font:16px/1.65 Inter,system-ui,sans-serif}}
main{{max-width:720px;margin:0 auto;padding:32px 20px 64px}}a{{color:#f4b840}}h1{{font-size:28px;margin:0 0 6px}}h2{{font-size:18px;margin:26px 0 4px;color:#f4b840}}
p{{margin:0;color:#d9cfb8}}.c{{margin-top:28px}}.back{{display:inline-block;margin-bottom:18px;text-decoration:none}}
@media(prefers-color-scheme:light){{body{{background:#f8f5ef;color:#2a2113}}p{{color:#4a3e28}}a,h2{{color:#9a6a0e}}}}</style></head>
<body><main><a class="back" href="/">← {_e(brand)}</a><h1>{_e(title)}</h1>{body}{contact}</main></body></html>"""
