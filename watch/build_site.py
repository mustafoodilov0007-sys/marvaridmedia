"""Ko'rish saytining bosh sahifasini yasaydi: hozirgi sayt (app/web/index.html) dizayni asos qilinadi —
uning fayliga TEGILMAYDI, faqat o'qiladi. Natija: watch/web/index.html

Hozirgi sayt yangilangach (dizayn o'zgarsa) shu skriptni qayta ishga tushiring:  python build_site.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE.parent / "app" / "web" / "index.html"
OUT = HERE / "web" / "index.html"

# (eski matn, yangi matn) — har biri asl faylda aynan 1 marta uchrashi shart
PATCHES = [
    ('<script src="https://telegram.org/js/telegram-web-app.js"></script>\n', ''),
    ('var PUB = !initData;', 'var PUB = true;   // alohida ko\'rish sayti: hamma mehmon, kino shu yerda ko\'riladi'),
    ('''    if (PUB) {
      if (!me.bot) { toast("⏳ Biroz kuting..."); return; }
      toast("📲 Telegram ochilmoqda...");
      openLink(botLink(it));
      return;
    }''', '''    if (PUB) { openPlayer(it); return; }'''),
    ('function botLink(it) { return "https://t.me/" + me.bot + "?start=" + (it.code < 0 ? "m" + (-it.code) : it.code); }',
     'function botLink(it) { return location.origin + "/?k=" + it.code; }'),
    ('''    if (!me.bot) return;
    var text = "🎬 " + it.title + " — " + me.brand + " botida tomosha qiling!";''',
     '''    var text = "🎬 " + it.title + " — " + me.brand + " saytida tomosha qiling!";'''),
    ('''    openLink("https://t.me/share/url?url=" + encodeURIComponent(botLink(it)) + "&text=" + encodeURIComponent(text));''',
     '''    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(botLink(it)).then(function () { toast("🔗 Havola nusxalandi"); }, function () { openLink("https://t.me/share/url?url=" + encodeURIComponent(botLink(it)) + "&text=" + encodeURIComponent(text)); });
    else openLink("https://t.me/share/url?url=" + encodeURIComponent(botLink(it)) + "&text=" + encodeURIComponent(text));'''),
    ('''PUB ? "«Kinoni ko'rish» bosilsa, Telegram'da botimiz ochiladi va kinoni yuboradi."''',
     '''PUB ? "«Kinoni ko'rish» — kino shu yerning o'zida ochiladi. Qayta kirsangiz, to'xtagan joyingizdan davom etadi."'''),
    ('''  function requestButton(q) {
''', '''  function requestButton(q) {
    if (!me.bot) return h("div");
'''),
    ('''    row("💝 Bizni qo'llab-quvvatlang", "Loyihaga yordam bering", function () { show("support"); });\n''', ''),
    ('''  function goBack() {
''', '''  function goBack() {
    if (window.__playerOpen) { closePlayer(); return true; }
'''),
    ('  // ───── sarlavha, navigatsiya ─────\n', '@@PLAYER_JS@@\n  // ───── sarlavha, navigatsiya ─────\n'),
    ('</style>', '@@PLAYER_CSS@@</style>'),
]


def build() -> str:
    s = SRC.read_text(encoding="utf-8")
    for old, new in PATCHES:
        n = s.count(old)
        if n != 1:
            raise SystemExit(f"❌ Patch topilmadi/takror ({n} marta): {old[:70]!r}\n"
                             "   Hozirgi sayt o'zgargan — build_site.py dagi PATCHES ni yangilang.")
        s = s.replace(old, new)
    s = s.replace("@@PLAYER_JS@@\n", (HERE / "patches" / "player.js").read_text(encoding="utf-8"))
    s = s.replace("@@PLAYER_CSS@@", (HERE / "patches" / "player.css").read_text(encoding="utf-8"))
    return s


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"✅ {OUT} yaratildi ({OUT.stat().st_size // 1024} KB)")
