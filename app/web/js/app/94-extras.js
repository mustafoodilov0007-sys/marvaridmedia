  // ───── 💎 Premium tugashi eslatmasi · 📲 o'rnatish banneri · 👥 Birga ko'ramiz ─────
  function dismissed(key, days) {
    try { var t = +localStorage.getItem(key) || 0; return t && Date.now() - t < days * 86400000; } catch (e) { return false; }
  }
  function dismiss(key) { try { localStorage.setItem(key, String(Date.now())); } catch (e) {} }

  function premiumBanner() {
    if (guest() || !me.premium) return null;
    var until = me.premium_until || 0, left = until - Date.now() / 1000;
    if (!until || left <= 0 || left > 3 * 86400 || dismissed("mm_pexp", 1)) return null;
    var days = Math.max(1, Math.ceil(left / 86400));
    var go = h("button", "btn primary", [icon("gem"), "Uzaytirish"]);
    var x = h("button", "nbx", "✕"); x.setAttribute("aria-label", "Yopish");
    var box = h("div", "nbanner", [h("div", "nb-t", [h("b", null, "💎 Premium " + days + " kundan keyin tugaydi"),
      h("span", null, "Uzilishsiz tomosha uchun hozir uzaytiring")]), go, x]);
    go.onclick = function () { haptic(); show("sub"); };
    x.onclick = function () { dismiss("mm_pexp"); box.remove(); };
    return box;
  }

  function installBanner() {
    if (!PUB || APP || STANDALONE || !(installEv || IOS) || dismissed("mm_inst", 14)) return null;
    var go = h("button", "btn primary", [icon("download"), "O'rnatish"]);
    var x = h("button", "nbx", "✕"); x.setAttribute("aria-label", "Yopish");
    var box = h("div", "nbanner", [h("div", "nb-t", [h("b", null, "📲 Ilova kabi o'rnating"),
      h("span", null, "Bosh ekranda belgisi bo'ladi, to'liq ekranda ochiladi")]), go, x]);
    go.onclick = function () {
      haptic();
      if (installEv) { installEv.prompt(); installEv.userChoice && installEv.userChoice.then(function () { box.remove(); }); installEv = null; }
      else toast("Safari: «Ulashish» → «Bosh ekranga qo'shish»");
    };
    x.onclick = function () { dismiss("mm_inst"); box.remove(); };
    return box;
  }

  function togetherBtn(it) {
    if (it.cat === "music" || it.locked) return null;
    var b = h("button", "btn soft", [icon("users"), "Birga ko'ramiz"]);
    b.onclick = function (e) {
      e.stopPropagation(); haptic();
      var base = location.origin + moviePath(it), nm = (me.name || "").trim().slice(0, 24);
      var link = base + (base.indexOf("?") < 0 ? "?" : "&") + "birga=" + encodeURIComponent(nm || "do'stingiz");
      var text = "👥 " + (nm ? nm + " sizni" : "Sizni") + " «" + it.title + "» ni birga ko'rishga taklif qiladi! 🍿";
      if (PUB && navigator.share) { navigator.share({ title: it.title, text: text, url: link }).catch(function () {}); return; }
      openLink("https://t.me/share/url?url=" + encodeURIComponent(link) + "&text=" + encodeURIComponent(text));
    };
    return b;
  }

  // taklif havolasi bilan kirgan do'st: kim taklif qilgani ko'rsatiladi
  (function () {
    var who = "";
    try { who = (new URLSearchParams(location.search).get("birga") || "").trim().slice(0, 24); } catch (e) {}
    if (!who) return;
    setTimeout(function () { toast("👥 " + who + " sizni birga kino ko'rishga taklif qildi 🍿"); }, 1800);
  })();
