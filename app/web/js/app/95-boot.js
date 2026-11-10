  // ───── sarlavha, navigatsiya ─────
  var lastScrollY = 0;
  function onScroll() {
    var top = $("top"), y = window.scrollY;
    top.classList.toggle("solid", current !== "home" || y > 40);
    var d = y - lastScrollY;                       // pastga aylantirganda sarlavha yashirinadi, tepaga — paydo bo'ladi (faqat telefonda)
    if (Math.abs(d) > 6) {
      top.classList.toggle("hide", d > 0 && y > 120 && !sheetOpen && current !== "shorts" && window.innerWidth < 900);
      lastScrollY = y;
    }
    if (y < 8) top.classList.remove("hide");
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  $("bSearch").appendChild(icon("search"));
  $("bSupport").appendChild(icon("heart"));
  $("bSupport").onclick = function () { haptic(); show("support"); };
  $("bStats").appendChild(icon("chart"));
  $("bStats").onclick = function () { haptic(); show("stats"); };
  $("bSearch").appendChild(h("span", "slabel", "Qidirish..."));
  $("bSearch").onclick = function () { haptic(); if (window.innerWidth >= 900) openQuickSearch(); else show("search"); };
  $("bChannel").appendChild(icon("send"));
  $("bChannel").onclick = function () { haptic(); if (me.channel) openLink(me.channel); };
  var NAV = { home: ["home", "Asosiy"], movie: ["film", "Kinolar"], serial: ["tv", "Serial"], cartoon: ["smile", "Multfilm"],
              shorts: ["clap", "Shorts"], music: ["music", "Musiqa"], saved: ["bookmark", "Saqlangan"] };
  document.querySelectorAll(".nav button").forEach(function (b) {
    var n = NAV[b.dataset.view];
    b.replaceChildren(icon(n[0]), h("span", null, n[1]));
    b.setAttribute("aria-label", n[1]);
    b.onclick = function () { haptic(); show(b.dataset.view); };
  });
  // katta ekranda — sarlavhadagi gorizontal menyu
  [["home", "Bosh sahifa"], ["movie", "Kinolar"], ["serial", "Seriallar"], ["cartoon", "Multfilmlar"], ["music", "Musiqa"],
   ["shorts", "Shorts"], ["saved", "Sevimlilar"]].forEach(function (n) {
    var b = h("button", n[0] === "home" ? "on" : "", n[1]);
    b.dataset.view = n[0];
    b.onclick = function () { haptic(); show(n[0]); };
    $("dnav").appendChild(b);
  });
  onKey($("avatar"), function () { haptic(); show("profile"); });
  $("avatar").onclick = function () { haptic(); show("profile"); };
  $("avatar").setAttribute("aria-label", "Profil");

  function setBrand(name) {
    var parts = (name || "Marvarid Media").toUpperCase().split(" ");
    var last = parts.length > 1 ? parts.pop() : "";
    $("word").replaceChildren(h("span", "w1", parts.join(" ")), last ? h("span", "w2", last) : null);
    if (!document.querySelector('link[rel="canonical"]')) document.title = name;   // SEO sahifalarda serverdagi sarlavha saqlanadi
  }
  function setAvatar(user) {
    var a = $("avatar");
    var name = (user && (user.first_name || "")) || "";
    var initials = (name.trim()[0] || "M") + ((user && user.last_name ? user.last_name[0] : "") || "");
    a.replaceChildren(initials.toUpperCase());
    if (user && user.photo_url) {
      var img = new Image();
      img.alt = "";
      img.onload = function () { a.replaceChildren(img); };
      img.src = user.photo_url;
    }
  }

  // 🖥 Telegram oynasini kengaytirish (Bot API 8.0+): kompyuterda avtomatik, foydalanuvchi profilda o'chirib qo'yishi mumkin
  function canFullscreen() {
    return !PUB && !!tg && typeof tg.requestFullscreen === "function" && !!tg.isVersionAtLeast && tg.isVersionAtLeast("8.0");
  }
  function applyInsets() {
    var t = ((tg.safeAreaInset || {}).top || 0) + ((tg.contentSafeAreaInset || {}).top || 0);
    document.documentElement.style.setProperty("--tgtop", t + "px");
  }
  // 📐 haqiqiy ko'rinadigan balandlik (iOS Safari manzil paneli, Telegram oynasi o'zgarganda ham to'g'ri): --vh
  function setVH() {
    var vv = window.visualViewport;
    var hgt = (!PUB && tg && tg.viewportStableHeight) || (vv && vv.height) || window.innerHeight;
    document.documentElement.style.setProperty("--vh", Math.round(hgt) + "px");
  }
  setVH();
  window.addEventListener("resize", setVH);
  window.addEventListener("orientationchange", function () { setTimeout(setVH, 250); });
  if (window.visualViewport) window.visualViewport.addEventListener("resize", setVH);
  if (!PUB && tg && tg.onEvent) { try { tg.onEvent("viewportChanged", setVH); } catch (e) {} }
  if (tg && !PUB) { tg.ready(); tg.expand(); try { tg.disableVerticalSwipes && tg.disableVerticalSwipes(); } catch (e) {} }
  if (canFullscreen()) {
    try {
      ["safeAreaChanged", "contentSafeAreaChanged", "fullscreenChanged"].forEach(function (ev) { tg.onEvent(ev, applyInsets); });
      applyInsets();
      var desktopApp = !/^(android|ios)$/.test(tg.platform || "");
      if (desktopApp && store.get("fs") !== "0" && !tg.isFullscreen) tg.requestFullscreen();
    } catch (e) {}
  }
  if (PUB && !AUTHED) $("avatar").replaceChildren(icon("user"));
  else if (!PUB) setAvatar(tg && tg.initDataUnsafe ? tg.initDataUnsafe.user : null);
  // 📱 Android ilovadagi «orqaga» tugmasi: true — sayt o'zi hal qildi, false — ilovadan chiqish
  window.mmBack = function () { return goBack(); };
  api("/api/me").then(function (d) {
    if (!d.ok) return;
    me = d;
    if (AUTHED) setAvatar({ first_name: d.name, photo_url: d.photo });
    setBrand(d.brand);
    if (d.channel) $("bChannel").classList.remove("hidden");
    if (d.admin) { $("bStats").classList.remove("hidden"); document.querySelector(".top").classList.add("adm"); }
  });
//WELCOME
  (function () {
    var el = $("welcome");
    if (!el) return;
    var link = "";
    try { var qp = new URLSearchParams(location.search); link = qp.get("k") || qp.get("v") || pathInfo().k || (pathInfo().view ? "v" : ""); } catch (e) {}
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    // kirish animatsiyasi faqat BIR MARTA: qurilma xotirasi (kesh) tozalanmaguncha qayta chiqmaydi
    var force = false;
    try { force = new URLSearchParams(location.search).get("welcome") === "1"; } catch (e) {}   // ?welcome=1 — qayta ko'rish (sinov uchun)
    // wt3: kalit yangilandi — animatsiya hamma qurilmada yana bir marta chiqadi (harakatni kamaytirish yoqilgan bo'lsa ham)
    if (!force && (link || store.get("wt3"))) { el.remove(); return; }
    store.set("wt3", "1");
    var user = !PUB && tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    var first = user && user.first_name ? String(user.first_name).trim().slice(0, 18) : "";
    var openGate;
    splashGate = new Promise(function (res) { openGate = res; });
    homePre = api("/api/home");
    var name = $("wName");
    var text = first ? first + "!" : "Kino olamiga!";
    Array.prototype.forEach.call(text, function (ch, i) {
      var s = document.createElement("span");
      s.textContent = ch;
      s.style.animationDelay = (2.3 + i * 0.045) + "s";
      name.appendChild(s);
    });
    if (!first) $("wSub").textContent = "Marvarid Media — eng sara kinolar bir joyda 🍿";
    var dust = $("wDust");
    for (var i = 0; i < 12; i++) {
      var d = document.createElement("i"), sz = 2 + Math.random() * 4;
      d.style.cssText = "left:" + (Math.random() * 100) + "%;width:" + sz + "px;height:" + sz + "px;animation-duration:" +
        (4 + Math.random() * 4) + "s;animation-delay:" + (Math.random() * 3.2) + "s;--dx:" + (Math.random() * 60 - 30) + "px";
      dust.appendChild(d);
    }
    if (!PUB) { try { tg.setHeaderColor("#050403"); tg.setBackgroundColor("#050403"); } catch (e) {} }
    var done = false;
    function finish() {
      if (done) return; done = true;
      el.classList.add("out");
      openGate();
      if (!PUB) { try { tg.setHeaderColor(theme === "dark" ? "#0b0a0d" : "#f8f5ef"); tg.setBackgroundColor(theme === "dark" ? "#0b0a0d" : "#f8f5ef"); } catch (e) {} }
      setTimeout(function () { el.remove(); }, 700);
    }
    setTimeout(function () { haptic("light"); }, 1900);
    setTimeout(function () { notify("success"); }, 2350);
    setTimeout(finish, 4300);
    el.addEventListener("click", finish);
  })();
  ///WELCOME
  var startView = "";
  try { startView = new URLSearchParams(location.search).get("v") || ""; } catch (e) {}
  var pI = pathInfo();
  if (pI.genre) show("video", { f: { genre: pI.genre } });
  else show(pI.view || (["stats", "support", "search", "saved", "movie", "serial", "cartoon", "music", "shorts", "profile", "catalog"].indexOf(startView) >= 0 ? startView : "home"));
  // 🔗 kanal postidagi havola: ?k=15 (kino) yoki ?k=m3 (musiqa) — shu kino oynasi darhol ochiladi
  (function () {
    var k = "";
    try { k = new URLSearchParams(location.search).get("k") || pathInfo().k || ""; } catch (e) {}
    if (!k && tg && tg.initDataUnsafe && /^k/.test(tg.initDataUnsafe.start_param || "")) k = tg.initDataUnsafe.start_param.slice(1);
    if (!/^m?\d{1,9}$/.test(k)) return;
    api("/api/catalog?k=" + k).then(function (d) {
      if (d.ok && d.items && d.items.length) openSheet(d.items[0]);
      else toast("😔 Bu kino topilmadi yoki o'chirilgan");
    }).catch(function () {});
    try { if (HIST) history.replaceState({ v: current, o: {} }, "", "/"); else history.replaceState(null, "", "/"); histFirst = false; } catch (e) {}
  })();
})();
