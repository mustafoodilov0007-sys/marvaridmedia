  // ───── 🗂 Kategoriyalar ─────
  function renderCats(view, my) {
    var page = h("div", "page", [h("h1", null, "Kategoriyalar"), h("p", "lead", "Nimani tomosha qilamiz?")]);
    var c = me.counts || {};
    var tiles = h("div", "ctiles");
    [["movie", "Kinolar", "film", c.movie], ["serial", "Seriallar", "tv", c.serial], ["cartoon", "Multfilmlar", "smile", c.cartoon],
     ["music", "Musiqa", "music", c.music], ["shorts", "Shorts", "clap", c.shorts], ["video", "Hammasi", "grid",
       (c.movie || 0) + (c.serial || 0) + (c.cartoon || 0)]].forEach(function (t) {
      var b = h("button", "ctile", [h("span", "ci", [icon(t[2])]), h("b", null, t[1]),
        h("span", "cn", t[3] != null ? t[3] + " ta" : "")]);
      b.onclick = function () { haptic(); show(t[0]); };
      tiles.appendChild(b);
    });
    page.appendChild(tiles);
    var more = h("div");
    page.appendChild(more);
    view.replaceChildren(page);
    getMeta().then(function (d) {
      if (my !== reqId || !d || !d.ok) return;
      function block(title, list, key) {
        if (!list || !list.length) return;
        var row = h("div", "gchips wrapchips");
        list.forEach(function (g) {
          var b = h("button", "gchip", [g.label, h("i", null, String(g.n))]);
          b.onclick = function () { haptic(); var f = {}; f[key] = g.key; show("video", { f: f }); };
          row.appendChild(b);
        });
        more.appendChild(h("h3", "group-title", title));
        more.appendChild(row);
      }
      block("🎭 Janrlar", d.genres, "genre");
      block("🌍 Davlatlar", (d.filters || {}).country, "country");
      block("🗣 Tillar", (d.filters || {}).lang, "lang");
    });
    api("/api/collections").then(function (d) {
      if (my !== reqId || !d.ok || !d.items.length) return;
      more.appendChild(h("h3", "group-title", "📚 To'plamlar"));
      var list = h("div", "clist");
      d.items.forEach(function (c) {
        var b = h("button", "crow", [h("b", null, c.title), h("span", null, c.n + " ta"), icon("chev")]);
        b.onclick = function () { haptic(); show("col", { id: c.id }); };
        list.appendChild(b);
      });
      more.appendChild(list);
    }).catch(function () {});
  }

  function rateRow(it) {
    var row = h("div", "rate");
    var up = h("button", "rbtn", ["👍 ", h("b", null, String(it.likes || 0))]);
    var down = h("button", "rbtn", ["👎 ", h("b", null, String(it.dislikes || 0))]);
    up.setAttribute("aria-label", "Yoqdi"); down.setAttribute("aria-label", "Yoqmadi");
    var label = h("span", "rlabel", "Kino yoqdimi?");
    function paint(r) {
      up.lastChild.textContent = r.likes; down.lastChild.textContent = r.dislikes;
      up.classList.toggle("on", r.mine === 1); down.classList.toggle("on", r.mine === -1);
      var n = r.likes + r.dislikes;
      label.textContent = n >= 3 ? "Tomoshabinlarning " + Math.round(r.likes * 100 / n) + "% iga yoqdi" : "Kino yoqdimi?";
      it.likes = r.likes; it.dislikes = r.dislikes;
    }
    function vote(v) {
      haptic("medium");
      if (guest()) { needLogin("⭐ Baho berish uchun hisobingizga kiring"); return; }
      api("/api/rate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: it.id, v: v }) })
        .then(function (r) { if (r.ok) { paint(r); animOnce(v === 1 ? up : down, "vpop", 500); notify("success"); } else toast("⚠️ Baho saqlanmadi"); })
        .catch(function () { toast("⚠️ Ulanishda xatolik"); });
    }
    up.onclick = function () { vote(1); };
    down.onclick = function () { vote(-1); };
    paint({ likes: it.likes || 0, dislikes: it.dislikes || 0, mine: 0 });
    if (!guest()) api("/api/rating?id=" + it.id).then(function (r) { if (r.ok) paint(r); }).catch(function () {});
    row.appendChild(label); row.appendChild(up); row.appendChild(down);
    return row;
  }

  function renderSaved(view) {
    var items = Object.keys(saved).map(function (k) { return saved[k]; })
      .sort(function (a, b) { return (b.t || 0) - (a.t || 0); });
    var page = h("div", "page", [h("h1", null, "Sevimlilar"),
      h("p", "lead", items.length ? items.length + (guest() ? " ta — shu qurilmada saqlanadi (kirsangiz, hamma joyda ko'rinadi)" :
        " ta — hisobingizda, botda ham ko'rinadi") : "")]);
    if (!guest() && (!PUB || me.tg)) {            // 🔔 «Keyin ko'raman» eslatmasi (bot orqali, kechqurun 19:30, 3 kunda ko'pi bilan bir marta)
      var rem = h("button", "remind-pill", [icon("bell"), h("span", null, "Ko'rmagan kinolarim haqida eslatib tur"), h("i", "sw", [h("b")])]);
      rem.type = "button"; rem.setAttribute("role", "switch"); rem.setAttribute("aria-checked", "false");
      page.appendChild(rem);
      api("/api/saved").then(function (d) {
        if (!d || !d.ok || !rem.isConnected) return;
        function paint(on) { rem.classList.toggle("on", on); rem.setAttribute("aria-checked", on ? "true" : "false"); }
        paint(!!d.remind);
        rem.onclick = function () {
          haptic();
          var want = !rem.classList.contains("on");
          paint(want);
          api("/api/saved", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ remind: want }) })
            .then(function (r) { if (!r || !r.ok) { paint(!want); toast("⚠️ Hozir imkoni yo'q"); } else toast(want ? "🔔 Eslatma yoqildi — kechqurun 19:30 da" : "🔕 Eslatma o'chirildi"); })
            .catch(function () { paint(!want); toast("⚠️ Ulanishda xatolik"); });
        };
      }).catch(function () {});
    }
    if (!items.length) {
      page.appendChild(emptyBox("bookmark", "Hali hech narsa saqlanmagan",
        "Yoqqan kinoni 🔖 belgisi bilan saqlang — shu yerda turadi."));
      var go = h("button", "loadmore", "Kinolarni ko'rish");
      go.onclick = function () { show("home"); };
      page.appendChild(go);
    } else {
      var grid = h("div", "grid");
      items.forEach(function (it) { grid.appendChild(card(it)); });
      page.appendChild(grid);
    }
    view.replaceChildren(page);
  }

  // ───── 🎯 Siz uchun: shaxsiy tavsiyalar («nega» izohi bilan) ─────
  function renderForYou(view, my) {
    var grid = h("div", "grid foryou");
    var lead = h("p", "lead", "Ko'rgan, yoqtirgan va saqlagan kinolaringiz asosida");
    view.replaceChildren(h("div", "page", [h("h1", null, "🎯 Siz uchun"), lead, grid]));
    for (var i = 0; i < 6; i++) grid.appendChild(h("div", "card", [h("div", "poster sk"), h("div", "t sk", " ")]));
    api("/api/foryou").then(function (d) {
      if (my !== reqId) return;
      if (!d || !d.ok) return renderError(view, (d && d.reason) || "network");
      grid.replaceChildren();
      if (d.personal && d.top && d.top.length) lead.textContent = "Siz ko'proq " + d.top.join(", ") + " janrlarini yoqtirasiz";
      else if (d.guest) { lead.textContent = "Hozir ommabop kinolar. Hisobingizga kirsangiz — shaxsiy tavsiyalar chiqadi"; }
      else lead.textContent = "Ko'proq kino ko'rsangiz va 👍 bossangiz — tavsiyalar aniqlashadi. Hozircha ommabop kinolar:";
      if (!d.items.length) return grid.replaceWith(emptyBox("film", "Hozircha tavsiya yo'q", "Bir nechta kino ko'rib, 👍 bosing — shu yerda paydo bo'ladi."));
      d.items.forEach(function (it) {
        var c = card(it);
        if (it.why) { var w = h("div", "why", it.why); var m = c.querySelector(".cmain"); (m || c).appendChild(w); }
        grid.appendChild(c);
      });
      if (d.guest) {
        var cta = h("button", "loadmore", "Hisobga kirish");
        cta.onclick = function () { haptic(); show("login"); };
        view.querySelector(".page").appendChild(cta);
      }
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }

  // ───── 👤 Profil ─────
  function askConfirm(text, yes) {
    if (!PUB && tg && tg.showConfirm) { try { tg.showConfirm(text, function (ok) { if (ok) yes(); }); return; } catch (e) {} }
    if (window.confirm(text)) yes();
  }

  // ───── ⭐ Baholarim ─────
  function renderRatings(view, my) {
    var page = h("div", "page", [h("h1", null, "⭐ Baholarim")]);
    view.replaceChildren(page);
    api("/api/myratings").then(function (d) {
      if (my !== reqId) return;
      if (!d.ok) return renderError(view, d.reason);
      if (!d.items.length) {
        page.appendChild(emptyBox("star", "Hali baho bermagansiz", "Kino sahifasida 👍 yoki 👎 bosing — shu yerda ko'rinadi."));
        return;
      }
      page.appendChild(h("p", "lead", d.items.length + " ta kinoga baho berdingiz"));
      var grid = h("div", "grid");
      d.items.forEach(function (it) {
        var c = card(it);
        c.appendChild(h("span", "mine", it.mine > 0 ? "👍" : "👎"));
        grid.appendChild(c);
      });
      page.appendChild(grid);
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }

  // ───── 💎 Obuna va xaridlar ─────
  function renderSub(view) {
    var page = h("div", "page narrow", [h("h1", null, "💎 Obuna va xaridlar")]);
    var until = me.premium_until || 0, now = Date.now() / 1000;
    var active = until > now;
    var days = Math.ceil((until - now) / 86400);
    var dt = new Date(until * 1000);
    var card1 = h("div", "donate" + (active ? "" : " free"), [
      h("small", null, active ? "Faol obuna" : "Obuna"),
      h("div", "num", active ? "💎 Premium" : "Oddiy foydalanuvchi"),
      h("div", "who", active ? ("Tugaydi: " + dt.getDate() + "." + String(dt.getMonth() + 1).padStart(2, "0") + "." + dt.getFullYear() + " · qoldi " + days + " kun")
        : "Premium bilan majburiy obunasiz va maxsus kinolar")]);
    page.appendChild(card1);
    var acts = h("div", "donate-actions");
    function go(label, start, cls) {
      var b = h("button", "btn " + (cls || "soft"), label);
      b.onclick = function () { haptic(); openLink("https://t.me/" + me.bot + "?start=" + start); };
      acts.appendChild(b);
    }
    if (me.bot && !PUB) {
      go(active ? "💎 Muddatni uzaytirish" : "💎 Premium olish", "premium", "primary");
      go("🎟 Promokod kiritish", "promo");
      go("🤝 Do'st taklif qilish (+1 kun)", "taklif");
    } else {
      page.appendChild(emptyBox("lock", "Telegram ichida oching", "Obuna va xaridlar faqat Telegram botdagi akkaunt bilan ishlaydi."));
    }
    page.appendChild(acts);
    view.replaceChildren(page);
  }

  // ───── 💝 Bizni qo'llab-quvvatlang ─────
  function copyText(text, done) {
    function fallback() {
      var t = document.createElement("textarea"); t.value = text; t.style.position = "fixed"; t.style.opacity = "0";
      document.body.appendChild(t); t.select();
      var ok = false; try { ok = document.execCommand("copy"); } catch (e) {}
      document.body.removeChild(t); done(ok);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { done(true); }, fallback);
    else fallback();
  }
  function renderSupport(view, my) {
    var page = h("div", "page narrow", [h("h1", null, "💝 Qo'llab-quvvatlash")]);
    view.replaceChildren(page);
    api("/api/support").then(function (d) {
      if (my !== reqId) return;
      if (!d.ok) return renderError(view, d.reason);
      page.appendChild(h("p", "lead", "Loyiha sizning yordamingiz bilan rivojlanadi. Har bir hissa yangi kinolar va yaxshi xizmat uchun sarflanadi. Katta rahmat! 🙏"));
      if (d.digits) {
        page.appendChild(h("div", "donate", [h("small", null, "Plastik karta"), h("div", "num", d.card),
          h("div", "who", d.holder || me.brand)]));
        var cp = h("button", "btn primary", [icon("send"), "Karta raqamini nusxalash"]);
        cp.onclick = function () { haptic(); copyText(d.digits, function (ok) { toast(ok ? "✅ Karta raqami nusxalandi" : d.card); }); };
        var acts = h("div", "donate-actions", [cp]);
        page.appendChild(acts);
        page.appendChild(h("div", "note", "Karta orqali o'tkazma qilgach, chekni botga yuboring — rahmat aytamiz."));
      } else {
        page.appendChild(emptyBox("heart", "Karta hozircha ulanmagan", "Bot orqali qo'llab-quvvatlash mumkin."));
      }
      var bot = h("div", "donate-actions");
      if (d.bot) {
        var b1 = h("button", "btn soft", "🧾 Chekni botga yuborish");
        b1.onclick = function () { openLink("https://t.me/" + d.bot + "?start=donat"); };
        bot.appendChild(b1);
        if (d.stars) {
          var b2 = h("button", "btn soft", "⭐ Telegram Stars bilan");
          b2.onclick = function () { openLink("https://t.me/" + d.bot + "?start=donat"); };
          bot.appendChild(b2);
        }
      }
      page.appendChild(bot);
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }


  // ───── 📈 Tahlil (faqat admin) ─────
  function pctText(v) { return v === null || v === undefined ? "—" : (Math.round(v * 10) / 10) + "%"; }
  function money(n) { return (n || 0).toLocaleString("ru-RU").replace(/,/g, " "); }
  function hbars(rows, unit) {
    var max = Math.max.apply(null, rows.map(function (r) { return r.n; }).concat([1]));
    var box = h("div", "hbl");
    rows.forEach(function (r) {
      var fill = h("i"); fill.style.width = Math.max(2, r.n / max * 100) + "%";
      box.appendChild(h("div", "hb", [h("div", "hbt", [h("span", null, r.label), h("b", null, fmt(r.n) + (r.pct !== undefined && r.pct !== null ? " · " + pctText(r.pct) : "") + (unit || ""))]), h("div", "hbbar", [fill])]));
    });
    return box;
  }
  function dayChart(list, key, tip) {
    var max = Math.max.apply(null, list.map(function (x) { return x[key]; }).concat([1]));
    var bars = h("div", "bars thin");
    list.forEach(function (x) {
      var dt = new Date((x.day + 18000) * 1000);
      var col = h("div", null, [h("u", null, x[key] ? String(x[key]) : ""), h("i"), h("em", null, dt.getUTCDate() + "." + String(dt.getUTCMonth() + 1).padStart(2, "0"))]);
      col.querySelector("i").style.height = Math.max(2, Math.round(x[key] / max * 78)) + "px";
      col.title = tip + ": " + x[key];
      bars.appendChild(col);
    });
    return bars;
  }
  function loadAnalytics(box, my) {
    box.appendChild(h("div", "note", "Yuklanmoqda..."));
    api("/api/admin/analytics").then(function (d) {
      box.replaceChildren();
      if (!d.ok) { box.appendChild(emptyBox("lock", "Ruxsat yo'q", "Bu sahifa faqat adminlar uchun.")); return; }
      var a = d.active, r = d.retention;
      function tile(n, label, gold) { return h("div", "tile" + (gold ? " gold" : ""), [h("b", null, n), h("span", null, label)]); }
      box.appendChild(h("div", "tiles", [
        tile(fmt(a.dau), "Bugun faol (DAU)", true), tile(fmt(a.wau), "Haftalik faol (WAU)"),
        tile(fmt(a.mau), "Oylik faol (MAU)"), tile(pctText(a.stickiness), "Yopishtirish (DAU/MAU)", true),
        tile(pctText(r.d1), "Ertasi kuni qaytdi"), tile(pctText(r.d7), "7 kundan keyin qaytdi")
      ]));
      box.appendChild(h("h3", "group-title", "🧭 Qayerdan kelishdi (30 kun, " + fmt(d.new_total) + " ta)"));
      box.appendChild(d.sources.length ? hbars(d.sources) : h("div", "note", "Hali ma'lumot yo'q — yangi foydalanuvchilar kelgach to'ladi"));
      box.appendChild(h("h3", "group-title", "Kunlik yangi foydalanuvchilar (30 kun)"));
      box.appendChild(dayChart(d.new_daily, "n", "Yangi"));
      box.appendChild(h("h3", "group-title", "🪜 Voronka (30 kunda qo'shilganlar)"));
      var fn = h("div", "funnel");
      d.funnel.forEach(function (f, i) {
        var bar = h("div", "fbar"); bar.style.width = Math.max(8, f.pct || 0) + "%"; bar.style.opacity = String(1 - i * 0.18);
        fn.appendChild(h("div", "frow", [h("div", "fl", [h("span", null, f.label), h("b", null, fmt(f.n) + " · " + pctText(f.pct))]), h("div", "ftrack", [bar])]));
      });
      box.appendChild(fn);
      box.appendChild(h("h3", "group-title", "🔁 Saqlanib qolish (haftalik kohortalar)"));
      if (!r.cohorts.length) box.appendChild(h("div", "note", "Hali yetarli ma'lumot yo'q"));
      else {
        var tb = h("div", "rtable");
        tb.appendChild(h("div", "rrow head", [h("span", null, "Hafta"), h("span", null, "Soni"), h("span", null, "1 kun"), h("span", null, "7 kun"), h("span", null, "30 kun")]));
        r.cohorts.forEach(function (c) {
          function cell(v) { var e = h("span", "rc", pctText(v)); if (v !== null) e.style.background = "rgba(226,180,80," + (0.08 + Math.min(v, 100) / 100 * 0.5).toFixed(2) + ")"; else e.classList.add("na"); return e; }
          var f = new Date((c.from + 18000) * 1000), t = new Date((c.to + 18000) * 1000);
          tb.appendChild(h("div", "rrow", [h("span", null, f.getUTCDate() + "." + String(f.getUTCMonth() + 1).padStart(2, "0") + "–" + t.getUTCDate() + "." + String(t.getUTCMonth() + 1).padStart(2, "0")),
            h("span", null, String(c.n)), cell(c.d1), cell(c.d7), cell(c.d30)]));
        });
        box.appendChild(tb);
        box.appendChild(h("div", "note", "«1 kun» — qo'shilganidan kamida 1 kun o'tib ham botdan foydalanganlar ulushi. Yangi kohortalarda «—» chiqadi."));
      }
      box.appendChild(h("h3", "group-title", "💰 Daromad (oxirgi 6 oy)"));
      var rv = h("div", "rtable");
      rv.appendChild(h("div", "rrow head rev", [h("span", null, "Oy"), h("span", null, "Premium"), h("span", null, "Donat"), h("span", null, "⭐"), h("span", null, "To'lov")]));
      d.revenue.slice().reverse().forEach(function (m) {
        rv.appendChild(h("div", "rrow rev", [h("span", null, m.month), h("span", null, money(m.premium_uzs)), h("span", null, money(m.donate_uzs)), h("span", null, String(m.stars)), h("span", null, String(m.n))]));
      });
      box.appendChild(rv);
      box.appendChild(h("div", "note", "So'mda. Promokod va do'st bonuslari daromad hisoblanmaydi."));
      box.appendChild(h("h3", "group-title", "▶️ Ko'rishlar (14 kun)"));
      box.appendChild(dayChart(d.daily14, "plays", "Ko'rish"));
      box.appendChild(h("h3", "group-title", "🕒 Soat bo'yicha faollik (14 kun, Toshkent vaqti)"));
      var hmax = Math.max.apply(null, (d.hours || []).map(function (x) { return x.n; }).concat([1])), hb = h("div", "bars thin hours");
      (d.hours || []).forEach(function (x) {
        var col = h("div", null, [h("u", null, ""), h("i"), h("em", null, x.h % 3 === 0 ? String(x.h) : "")]);
        col.querySelector("i").style.height = Math.max(2, Math.round(x.n / hmax * 78)) + "px"; col.title = x.h + ":00 — " + x.n;
        if (x.n === hmax && x.n > 0) col.querySelector("i").style.background = "var(--gold, #e2b450)";
        hb.appendChild(col);
      });
      box.appendChild(hb);
      box.appendChild(h("div", "note", "Ko'rishlar qaysi soatda ko'p bo'lishi — kanalga post qo'yish uchun eng yaxshi vaqt."));
      box.appendChild(h("h3", "group-title", "🔥 Eng ko'p ko'rilganlar (7 kun)"));
      box.appendChild((d.top7 || []).length ? hbars(d.top7) : h("div", "note", "Hali ma'lumot yo'q"));
      box.appendChild(h("h3", "group-title", "🗂 Bo'limlar bo'yicha ko'rishlar (14 kun)"));
      box.appendChild((d.cats || []).length ? hbars(d.cats) : h("div", "note", "Hali ma'lumot yo'q"));
      box.appendChild(h("h3", "group-title", "🌐 Sayt tashriflari (14 kun)"));
      var vis = d.daily14.map(function (x) { return { day: x.day, v: x.tg + x.web }; });
      box.appendChild(dayChart(vis, "v", "Tashrif"));
      if (d.site_sources.length) box.appendChild(hbars(d.site_sources));
      box.appendChild(h("div", "note", "Telegram ichida: kuniga bir marta har bir foydalanuvchi. Brauzer: har bir sessiya."));
    }).catch(function () { box.replaceChildren(h("div", "note", "⚠️ Yuklab bo'lmadi")); });
  }

  // ───── 📊 Statistika (faqat admin) ─────
  function renderStats(view, my) {
    var page = h("div", "page narrow", [h("h1", null, "📊 Statistika")]);
    var box1 = h("div"), box2 = h("div", "hidden");
    var tabs = h("div", "seg");
    var tab = "general";
    try { if (new URLSearchParams(location.search).get("tab") === "analytics") tab = "analytics"; } catch (e) {}
    var analyticsLoaded = false;
    function setTab(t) {
      tab = t;
      box1.classList.toggle("hidden", t !== "general"); box2.classList.toggle("hidden", t !== "analytics");
      tabs.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b.dataset.t === t); });
      if (t === "analytics" && !analyticsLoaded) { analyticsLoaded = true; loadAnalytics(box2, my); }
    }
    [["general", "Umumiy"], ["analytics", "📈 Tahlil"]].forEach(function (x) {
      var b = h("button", "", x[1]); b.dataset.t = x[0]; b.onclick = function () { haptic(); setTab(x[0]); }; tabs.appendChild(b);
    });
    page.appendChild(tabs); page.appendChild(box1); page.appendChild(box2);
    view.replaceChildren(page);
    setTab(tab);
    page = box1;
    api("/api/admin/stats").then(function (d) {
      if (my !== reqId) return;
      if (!d.ok) { page.appendChild(emptyBox("lock", "Ruxsat yo'q", "Bu sahifa faqat adminlar uchun.")); return; }
      var u = d.users;
      function tile(n, label, gold) { return h("div", "tile" + (gold ? " gold" : ""), [h("b", null, fmt(n)), h("span", null, label)]); }
      page.appendChild(h("div", "tiles", [
        tile(u.total, "Jami foydalanuvchi"), tile(u.today, "Bugun qo'shilgan", true),
        tile(u.week, "7 kunda yangi"), tile(u.month, "30 kunda yangi"),
        tile(u.active24, "24 soatda faol"), tile(u.premium, "💎 Premium", true),
        tile((d.counts.movie || 0) + (d.counts.serial || 0) + (d.counts.cartoon || 0), "Kino/serial/multfilm"), tile(d.views_total, "Jami ko'rishlar")
      ]));
      page.appendChild(h("h3", "group-title", "Kunlik yangi foydalanuvchilar (14 kun)"));
      var max = Math.max.apply(null, d.daily.map(function (x) { return x.n; }).concat([1]));
      var bars = h("div", "bars");
      d.daily.forEach(function (x) {
        var dt = new Date((x.ts + 18000) * 1000);
        var col = h("div", null, [h("u", null, x.n ? String(x.n) : ""), h("i"), h("em", null, dt.getUTCDate() + "." + String(dt.getUTCMonth() + 1).padStart(2, "0"))]);
        col.querySelector("i").style.height = Math.max(2, Math.round(x.n / max * 78)) + "px";
        bars.appendChild(col);
      });
      page.appendChild(bars);
      page.appendChild(h("h3", "group-title", "🔥 Eng ko'p ko'rilgan kinolar"));
      var top = h("ol", "rank");
      if (!d.top.length) top.appendChild(h("li", null, [h("b", null, "Hozircha ma'lumot yo'q")]));
      d.top.forEach(function (x, i) { top.appendChild(h("li", null, [h("span", "no", String(i + 1)), h("b", null, x.title), h("span", null, "👁 " + fmt(x.views))])); });
      page.appendChild(top);
      page.appendChild(h("h3", "group-title", "🔎 Qidiruvda topilmaganlar (30 kun)"));
      var fl = h("ol", "rank");
      if (!d.failed.length) fl.appendChild(h("li", null, [h("b", null, "Hammasi topilgan 🎉")]));
      d.failed.forEach(function (x, i) { fl.appendChild(h("li", null, [h("span", "no", String(i + 1)), h("b", null, x.q), h("span", null, x.n + " marta")])); });
      page.appendChild(fl);
      page.appendChild(h("div", "note", "Jami qidiruvlar (30 kun): " + fmt(d.searches30) + " • Ochiq so'rovlar: " + d.requests_open));
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }


