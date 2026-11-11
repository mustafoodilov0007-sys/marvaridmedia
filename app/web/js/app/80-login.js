  // ───── 🔐 kirish sahifasi: Telegram (bot orqali tasdiqlash) yoki Google ─────
  var loginPoll = null, loginPollNow = null;
  function stopLoginPoll() { clearInterval(loginPoll); loginPoll = null; loginPollNow = null; }
  document.addEventListener("visibilitychange", function () { if (!document.hidden && loginPollNow) loginPollNow(); });
  function finishLogin(session, name) {
    stopLoginPoll();
    try { localStorage.setItem("sess", session); } catch (e) {}
    SESSION = session; AUTHED = true;
    return api("/api/me").then(function (d) {
      if (d && d.ok) { me = d; setAvatar({ first_name: d.name, photo_url: d.photo }); if (d.admin) { $("bStats").classList.remove("hidden"); document.querySelector(".top").classList.add("adm"); } }
      notify("success"); toast("✅ Xush kelibsiz, " + (name || (d && d.name) || "") + "!");
      syncSaved();
      show("profile");
    });
  }
  function loadGoogle(wrap) {
    function init() {
      try {
        window.google.accounts.id.initialize({ client_id: me.google, callback: function (resp) {
          pubPost("/pub/auth/google", { credential: resp.credential }).then(function (d) {
            if (d.ok) finishLogin(d.session, d.name); else toast("⚠️ Google orqali kirib bo'lmadi. Qaytadan urinib ko'ring.");
          });
        } });
        window.google.accounts.id.renderButton(wrap, { theme: "outline", size: "large", shape: "pill", text: "signin_with", locale: "uz", width: Math.min(320, wrap.clientWidth || 300) });
      } catch (e) { wrap.textContent = "Google yuklanmadi"; }
    }
    if (window.google && window.google.accounts) return init();
    var sc = document.createElement("script");
    sc.src = "https://accounts.google.com/gsi/client"; sc.async = true; sc.onload = init;
    sc.onerror = function () { wrap.textContent = "Google yuklanmadi — internetni tekshiring"; };
    document.head.appendChild(sc);
  }
  function renderLogin(view) {
    stopLoginPoll();
    if (!PUB) { show("profile"); return; }
    if (AUTHED) { show("profile"); return; }
    if (!me.bot) { api("/api/me").then(function (d) { if (d && d.ok) { me = d; renderLogin(view); } }); return; }
    var page = h("div", "page narrow login");
    page.appendChild(h("h1", null, "Kirish"));
    page.appendChild(h("p", "lead", "Izoh yozish, baho berish va kinoni Telegramingizga yuborish uchun hisobingizga kiring."));
    var box = h("div", "lbox");
    var tgBtn = h("button", "lbtn tg", [icon("send"), h("span", null, "Telegram orqali kirish")]);
    var status = h("div", "lstat hidden");
    function expired() { stopLoginPoll(); status.replaceChildren(h("div", null, [h("b", null, "⏳ Vaqt tugadi"), h("span", null, "Qaytadan «Telegram orqali kirish» ni bosing.")])); }
    tgBtn.onclick = function () {
      haptic(); tgBtn.disabled = true;
      pubPost("/pub/auth/tg/start").then(function (r) {
        tgBtn.disabled = false;
        if (!r.ok) { toast("⚠️ Hozir kirib bo'lmadi. Keyinroq urinib ko'ring."); return; }
        openLink(r.link);
        var again = h("button", "lgo", "Telegramni qayta ochish"); again.onclick = function () { openLink(r.link); };
        var cancel = h("button", "lgo ghost", "Bekor qilish"); cancel.onclick = function () { stopLoginPoll(); status.classList.add("hidden"); };
        status.classList.remove("hidden");
        status.replaceChildren(h("div", "lspin"), h("div", null, [h("b", null, "Telegramda «Start» va «✅ Ha, men» ni bosing"),
          h("span", null, "Tasdiqlagach, shu sahifa o'zi hisobingizga kiradi."), h("div", "lrow", [again, cancel])]));
        var tries = 0, busy = false;
        function check() {
          if (busy) return; busy = true;
          pubPost("/pub/auth/tg/poll", { token: r.token }).then(function (d) {
            busy = false;
            if (d.ok && d.status === "done") finishLogin(d.session, d.name);
            else if (!d.ok) expired();
          }).catch(function () { busy = false; });
        }
        stopLoginPoll();
        loginPollNow = check;
        loginPoll = setInterval(function () { if (++tries > 200) { expired(); return; } check(); }, 2200);
      }).catch(function () { tgBtn.disabled = false; toast("⚠️ Ulanishda xatolik"); });
    };
    box.appendChild(tgBtn);
    if (me.google) {
      var gw = h("div", "gbtn");
      box.appendChild(h("div", "lor", "yoki")); box.appendChild(gw);
      setTimeout(function () { loadGoogle(gw); }, 0);
    }
    box.appendChild(status);
    page.appendChild(box);
    page.appendChild(h("p", "pnote", "🔒 Telegram orqali kirishda parolingiz so'ralmaydi: faqat botda tasdiqlaysiz. Ismingizdan boshqa ma'lumot olinmaydi."));
    page.appendChild(langSeg());
    view.replaceChildren(page);
  }
  function langSeg() {
    var cur = window.LANG || "uz", sg = h("div", "seg");
    [["uz", "O'zbek"], ["ru", "Русский"], ["en", "English"]].forEach(function (o) {
      var b = h("button", o[0] === cur ? "on" : "", o[1]);
      b.setAttribute("data-notr", "1");
      b.onclick = function () { if (o[0] !== cur) { haptic(); window.setLang(o[0]); } };
      sg.appendChild(b);
    });
    return sg;
  }
  function renderProfile(view) {
    var user = !PUB && tg && tg.initDataUnsafe ? tg.initDataUnsafe.user : null;
    if (AUTHED) user = { first_name: me.name, photo_url: me.photo };
    var name = (user && user.first_name) || (PUB ? "Mehmon" : "Foydalanuvchi");
    var av = h("div", "pavatar");
    av.textContent = (name.trim()[0] || "M").toUpperCase();
    if (user && user.photo_url) {
      var im = new Image(); im.alt = "";
      im.onload = function () { av.replaceChildren(im); };
      im.src = user.photo_url;
    }
    var status = AUTHED ? (me.premium ? "💎 Premium a'zo" : (me.tg ? "Telegram hisobi" : "Google hisobi")) :
      (PUB ? "Mehmon — kirmagansiz" : (me.premium ? "💎 Premium a'zo" : "Oddiy foydalanuvchi"));
    var page = h("div", "page narrow");
    var pc = h("div", "pcard", [av, h("div", "pinfo", [h("b", null, name), h("span", null, status)])]);
    var pu = me.premium_until || 0, nowS = Date.now() / 1000;
    if (me.premium && !guest()) {                       // 💎 Premium a'zo: oltin karta, qolgan kunlar va uzaytirish
      pc.classList.add("prem");
      var days = pu > nowS ? Math.ceil((pu - nowS) / 86400) : 0;
      var left = days ? (days > 3650 ? "Cheksiz" : days + " kun qoldi") : "Faol";
      var ext = h("button", "pext", [icon("gem"), "Uzaytirish"]);
      ext.onclick = function () { haptic(); show("sub"); };
      var pbar = h("div", "pbar", [h("i")]);
      pbar.firstChild.style.transform = "scaleX(" + (days ? Math.max(.04, Math.min(1, days / 30)) : 1).toFixed(3) + ")";
      pc.appendChild(h("div", "pprem", [h("div", "pprem-row", [h("span", "pbadge", [icon("gem"), "PREMIUM"]), h("em", null, left), ext]), pbar]));
    }
    page.appendChild(pc);
    if (guest()) {
      var lc = h("button", "logincard", [h("div", null, [h("b", null, "Hisobingizga kiring"),
        h("span", null, "Izoh yozish, baho berish va kinoni Telegramga yuborish uchun")]), h("em", null, "Kirish")]);
      lc.onclick = function () { haptic(); show("login"); };
      page.appendChild(lc);
    }
    var nSaved = Object.keys(saved).length;
    var savedBox = h("button", "pbox", [h("b", null, String(nSaved)), h("span", null, "Sevimlilar")]);
    savedBox.type = "button";
    savedBox.onclick = function () { haptic(); show("saved"); };
    page.appendChild(h("div", "pstats", [
      savedBox,
      h("div", null, [h("b", null, String(PUB ? localHist.length : "—")), h("span", null, "Ko'rilgan")]),
      h("div", null, [h("b", null, String(((me.counts || {}).movie || 0) + ((me.counts || {}).serial || 0) + ((me.counts || {}).cartoon || 0))), h("span", null, "Jami kino")])
    ]));
    weekCard(page);
    yearCard(page);
    // mavzu
    var seg = h("div", "seg");
    [["dark", "🌙 Qorong'i"], ["light", "☀️ Yorug'"]].forEach(function (o) {
      var b = h("button", o[0] === theme ? "on" : "", o[1]);
      b.onclick = function () {
        haptic(); themeFx(); theme = o[0]; store.set("theme", theme); applyTheme(theme);
        seg.querySelectorAll("button").forEach(function (x) { x.classList.toggle("on", x === b); });
      };
      seg.appendChild(b);
    });
    page.appendChild(h("h3", "group-title", "Mavzu"));
    page.appendChild(seg);
    page.appendChild(h("h3", "group-title", "Kartalar"));
    var cc = document.documentElement.classList.contains("cols3") ? 3 : 2;
    var colSeg = h("div", "seg");
    [[2, "2 ustun (katta)"], [3, "3 ustun"]].forEach(function (o) {
      var b = h("button", o[0] === cc ? "on" : "", o[1]);
      b.onclick = function () {
        haptic(); setCols(o[0]);
        colSeg.querySelectorAll("button").forEach(function (x) { x.classList.toggle("on", x === b); });
      };
      colSeg.appendChild(b);
    });
    page.appendChild(colSeg);
    page.appendChild(h("h3", "group-title", "Tezlik"));
    var pf = ""; try { pf = localStorage.getItem("perf") || ""; } catch (e) {}
    var perf = h("div", "seg");
    [["", "Avto"], ["lite", "Yengil"], ["full", "To'liq"]].forEach(function (o) {
      var b = h("button", o[0] === pf ? "on" : "", o[1]);
      b.onclick = function () { if (o[0] !== pf) { haptic(); setPerf(o[0]); } };
      perf.appendChild(b);
    });
    page.appendChild(perf);
    page.appendChild(h("p", "pnote", "Telefon sekin ishlasa — «Yengil» ni tanlang: animatsiyalar va xira effektlar kamayadi."));
    page.appendChild(h("h3", "group-title", "Interfeys tili"));
    page.appendChild(langSeg());
    // havolalar
    var links = h("div", "clist");
    function row(label, sub, fn) {
      var b = h("button", "crow", [h("b", null, label), h("span", null, sub || ""), icon("chev")]);
      b.onclick = function () { haptic(); fn(); };
      links.appendChild(b);
    }
    if (PUB && !APP && !STANDALONE && (installEv || IOS)) {
      row("📲 Ilovani o'rnatish", "Bosh ekranga qo'shing — ilova kabi ochiladi", function () {
        if (installEv) { installEv.prompt(); installEv = null; } else toast("Safari: «Ulashish» → «Bosh ekranga qo'shish»");
      });
    }
    if (me.bot) row("🤖 Telegram botni ochish", "@" + me.bot, function () { openLink("https://t.me/" + me.bot); });
    if (me.channel) row("📢 Kanalimiz", "Yangiliklar va e'lonlar", function () { openLink(me.channel); });
    if (!guest()) row("📚 Ro'yxatlarim", "O'z kolleksiyalaringiz — havola bilan ulashing", function () { show("lists"); });
    if (!guest()) row("⭐ Baholarim", "Siz 👍/👎 bergan kinolar", function () { show("ratings"); });
    if (!PUB || (AUTHED && me.tg)) row("💎 Obuna va xaridlar", me.premium ? "Premium faol" : "Premium, promokod, taklif", function () { show("sub"); });
    var kidsRow = h("button", "crow", [h("b", null, "👶 Bolalar rejimi: " + (kidsMode ? "yoqilgan" : "o'chiq")),
      h("span", null, "Faqat multfilm va 12+ gacha kontent"), icon("chev")]);
    kidsRow.onclick = function () {
      haptic(); kidsMode = !kidsMode; store.set("kids", kidsMode ? "1" : "0");
      document.body.classList.toggle("kids", kidsMode);
      toast(kidsMode ? "👶 Bolalar rejimi yoqildi" : "Bolalar rejimi o'chirildi");
      if (kidsMode && current === "shorts") show("home"); else renderProfile(view);
    };
    links.appendChild(kidsRow);
    row("💝 Bizni qo'llab-quvvatlang", "Loyihaga yordam bering", function () { show("support"); });
    if (me.admin) row("📊 Statistika", "Foydalanuvchilar, top kinolar, qidiruvlar", function () { show("stats"); });
    row("🗂 Kategoriyalar", "Janr, davlat, til", function () { show("cats"); });
    row("🎲 Tasodifiy kino", "Omadingizni sinang", function () { randomMovie(); });
    if (canFullscreen()) {
      var fsRow = h("button", "crow", [h("b", null, tg.isFullscreen ? "🗗 Oddiy oyna" : "🖥 To'liq ekran"),
        h("span", null, "Telegram oynasini kengaytirish"), icon("chev")]);
      fsRow.onclick = function () {
        haptic();
        try {
          if (tg.isFullscreen) { tg.exitFullscreen(); store.set("fs", "0"); } else { tg.requestFullscreen(); store.set("fs", "1"); }
        } catch (e) {}
        setTimeout(function () { renderProfile(view); }, 400);
      };
      links.appendChild(fsRow);
    }
    page.appendChild(h("h3", "group-title", "Tezkor"));
    page.appendChild(links);
    // ma'lumotlar
    var data = h("div", "clist");
    function drow(label, fn) {
      var b = h("button", "crow danger", [h("b", null, label), icon("chev")]);
      b.onclick = function () { haptic(); fn(); };
      data.appendChild(b);
    }
    drow("🕘 Ko'rish tarixini tozalash", function () {
      askConfirm("Ko'rish tarixi o'chirilsinmi?", function () {
        localHist = []; store.set("hist", "[]");
        if (!guest()) api("/api/history/clear", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(function () {});
        toast("🧹 Ko'rish tarixi tozalandi");
      });
    });
    drow("🔎 Qidiruv tarixini tozalash", function () { store.set("recentq", "[]"); toast("🧹 Qidiruv tarixi tozalandi"); });
    drow("🔖 Sevimlilarni tozalash", function () {
      askConfirm("Barcha sevimlilar o'chirilsinmi?", function () {
        Object.keys(saved).forEach(function (k) {
          if (cloud) cloud.removeItem(k);
          if (!guest()) api("/api/saved", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: +k.slice(1), on: false }) }).catch(function () {});
        });
        saved = {}; persistSaved(); toast("🧹 Sevimlilar tozalandi"); renderProfile(view);
      });
    });
    if (AUTHED) drow("🚪 Hisobdan chiqish", function () {
      askConfirm("Hisobdan chiqasizmi?", function () {
        api("/api/auth/logout", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(function () {})
          .then(function () { dropSession(); store.set("svsync", ""); store.set("saved", "{}"); location.reload(); });
      });
    });
    page.appendChild(h("h3", "group-title", "Ma'lumotlar"));
    page.appendChild(data);
    page.appendChild(h("p", "pnote", "🔒 Sevimlilar va qidiruv tarixi sizning qurilmangiz yoki Telegram akkauntingizda saqlanadi. " +
      "Biz sizning shaxsiy ma'lumotlaringizni boshqalarga bermaymiz."));
    view.replaceChildren(page);
  }

