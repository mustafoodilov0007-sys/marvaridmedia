  // ───── 🎬 topilmagan kinoni so'rash ─────
  function requestButton(q) {
    var b = h("button", "btn primary", ["🎬 «" + (q.length > 24 ? q.slice(0, 23) + "…" : q) + "» ni so'rash"]);
    b.style.cssText = "display:flex;margin:4px auto 0;padding:0 22px;";
    var note = h("div", "note", "So'rovingizni adminlarga yuboramiz. Kino qo'shilishi bilan bot sizga xabar beradi.");
    var wrap = h("div", null, [b, note]);
    b.onclick = function () {
      haptic("medium");
      if (PUB) {
        toast("📲 Telegram'da botga kino nomini yozing");
        openLink("https://t.me/" + me.bot + "?start=sorov");
        return;
      }
      b.disabled = true;
      api("/api/request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ q: q }) })
        .then(function (res) {
          if (res.ok) {
            notify("success");
            b.replaceChildren("✅ So'rov yuborildi");
            toast("✅ So'rovingiz qabul qilindi! Kino qo'shilgach, bot xabar beradi.");
          } else { b.disabled = false; toast("⚠️ Yuborib bo'lmadi. Qaytadan urinib ko'ring."); }
        })
        .catch(function () { b.disabled = false; toast("⚠️ Ulanishda xatolik."); });
    };
    return wrap;
  }

  var searchQ = "", searchScope = "all", searchSort = "new";
  var SCOPES = [["all", "Hammasi"], ["movie", "Kino"], ["serial", "Serial"], ["cartoon", "Multfilm"], ["music", "Musiqa"]];
  function recentList() { try { return JSON.parse(store.get("recentq") || "[]") || []; } catch (e) { return []; } }
  function pushRecent(q) {
    var l = recentList().filter(function (x) { return x.toLowerCase() !== q.toLowerCase(); });
    l.unshift(q);
    store.set("recentq", JSON.stringify(l.slice(0, 8)));
  }
  function renderSearch(view) {
    var input = h("input");
    input.type = "search"; input.placeholder = "Nomi, kodi, yili yoki janri...";
    input.setAttribute("enterkeyhint", "search"); input.autocomplete = "off"; input.spellcheck = false;
    input.setAttribute("aria-label", "Qidiruv");
    input.value = searchQ;
    var clear = h("button", "sclear" + (searchQ ? "" : " hidden"), [icon("x")]);
    clear.type = "button"; clear.setAttribute("aria-label", "Tozalash");
    var results = h("div");
    var scopeRow = h("div", "gchips");
    var sortHost = h("span", "sorthost");
    function paintSort() {
      sortHost.replaceChildren(filterDrop(["sort", "↕ Saralash", "sort"],
        [{ key: "new", label: "Yangi" }, { key: "top", label: "Top" }, { key: "rating", label: "Reyting" }], searchSort,
        function (k) { searchSort = k; paintSort(); run(); }));
    }
    paintSort();
    var filters = h("div", "sfilters", [scopeRow, sortHost]);
    var mic = voiceButton(input, function (txt) { searchQ = txt; clear.classList.toggle("hidden", !txt); run(); });
    var page = h("div", "page", [h("h1", null, "Qidiruv"), h("label", "searchbox", [icon("search"), input, clear, mic]), filters, results]);
    view.replaceChildren(page);
    if (!searchQ) setTimeout(function () { input.focus(); }, 250);

    function paintScopes() {
      scopeRow.replaceChildren();
      SCOPES.forEach(function (s) {
        var b = h("button", "gchip" + (s[0] === searchScope ? " on" : ""), s[1]);
        b.onclick = function () { searchScope = s[0]; paintScopes(); run(); };
        scopeRow.appendChild(b);
      });
    }
    paintScopes();
    function chip(text, fn, cls) {
      var b = h("button", "gchip" + (cls ? " " + cls : ""), text);
      b.onclick = fn;
      return b;
    }
    function setQuery(q) { input.value = q; run(); }

    function popularBlock(into, title) {
      api("/api/popular").then(function (d) {
        if (!d.ok || !d.queries.length) return;
        var row = h("div", "gchips wrapchips");
        d.queries.forEach(function (q) { row.appendChild(chip("🔥 " + q, function () { haptic(); setQuery(q); })); });
        into.appendChild(h("h3", "group-title", title));
        into.appendChild(row);
      }).catch(function () {});
    }
    function suggestIdle(into) {
      api("/api/suggest").then(function (d) {
        if (!d || !d.ok || !into.isConnected) return;
        function block(title, list) {
          if (!list || !list.length) return;
          var r = h("div", "rail trend-rail");
          list.forEach(function (it) { r.appendChild(card(it)); });
          into.appendChild(h("h3", "group-title", title));
          into.appendChild(r);
        }
        block("🔥 Hozir ommabop", d.trending);
        block("🕘 Yaqinda ko'rganlaringiz", d.recent);
      }).catch(function () {});
    }
    // ⚡ yozish paytida darhol (120 ms): poster bilan ixcham ro'yxat; to'liq natijalar keyin uning o'rnini oladi
    function hilite(text, q) {
      var i = text.toLowerCase().indexOf(q.toLowerCase());
      if (i < 0 || !q) return [document.createTextNode(text)];
      var m = document.createElement("mark"); m.textContent = text.slice(i, i + q.length);
      return [document.createTextNode(text.slice(0, i)), m, document.createTextNode(text.slice(i + q.length))];
    }
    var suggSeq = 0;
    function instant(q) {
      var my = ++suggSeq;
      api("/api/suggest?q=" + encodeURIComponent(q)).then(function (d) {
        if (my !== suggSeq || input.value.trim() !== q || results.dataset.full === q) return;
        if (!d || !d.ok || !d.items || !d.items.length) return;
        var box = h("div", "sugg");
        if (d.fuzzy) box.appendChild(h("div", "sugg-note", "🤔 O'xshash nomlar:"));
        d.items.forEach(function (it) {
          var tx = h("div", "tx"), b = document.createElement("b");
          hilite(it.title, q).forEach(function (n) { b.appendChild(n); });
          tx.appendChild(b);
          tx.appendChild(h("span", null, [NAMES[it.cat] || "Kino", it.year ? yr(it) : "", it.genres && it.genres[0] ? gname(it.genres[0]) : ""].filter(Boolean).join(" · ")));
          var row = h("button", "sugg-row", [posterNode(it, 360), tx, icon("chev")]);
          row.type = "button";
          row.onclick = function () { haptic(); openSheet(it, false, row.querySelector(".poster")); pushRecent(it.title); };
          box.appendChild(row);
        });
        results.replaceChildren(box);
      }).catch(function () {});
    }
    function idle() {
      results.dataset.full = "";
      results.replaceChildren();
      var rec = recentList();
      if (rec.length) {
        var clearBtn = h("button", "more", "Tozalash");
        clearBtn.onclick = function () { store.set("recentq", "[]"); idle(); };
        results.appendChild(h("div", "sec-head tight", [h("h3", "group-title", "🕘 Oxirgi qidiruvlar"), clearBtn]));
        var row = h("div", "gchips wrapchips");
        rec.forEach(function (q) { row.appendChild(chip(q, function () { haptic(); setQuery(q); })); });
        results.appendChild(row);
      }
      var vis = h("div"); results.appendChild(vis);
      suggestIdle(vis);                                  // 🔥 hozir ommabop (poster bilan) va 🕘 yaqinda ko'rganlaringiz
      var pop = h("div"); results.appendChild(pop);
      popularBlock(pop, "🔥 Ommabop qidiruvlar");
      var gl = homeGenres;
      function genreBlock(list) {
        if (!list || !list.length) return;
        var row = h("div", "gchips wrapchips");
        list.forEach(function (g) { row.appendChild(chip(g.label, function () { haptic(); show("video", { f: { genre: g.key } }); })); });
        results.appendChild(h("h3", "group-title", "🎭 Janr bo'yicha"));
        results.appendChild(row);
        var rnd = h("button", "gchip rnd", [icon("dice"), "Tasodifiy kino"]);
        rnd.onclick = function () { randomMovie(rnd); };
        results.appendChild(h("div", "gchips", [rnd]));
      }
      if (gl.length) genreBlock(gl); else getMeta().then(function (d) { if (d && d.ok) genreBlock(d.genres); });
      if (!rec.length) results.insertBefore(h("p", "lead", "Kino nomi, kodi, chiqqan yili yoki janrini yozing."), results.firstChild);
    }

    var t;
    function run() {
      var q = input.value.trim();
      searchQ = q;
      clear.classList.toggle("hidden", !q);
      var my = ++reqId;
      if (q.length < 2) { idle(); return; }
      results.dataset.full = "";
      if (!results.querySelector(".sugg")) results.replaceChildren(h("div", "grid", skeletonCards(6)));   // tez ro'yxat bor bo'lsa — skelet qo'yilmaydi
      instant(q);
      var numeric = /^#?\d+$/.test(q), year = /^(19[2-9]\d|20[0-4]\d)$/.test(q);
      var cats;
      if (searchScope !== "all") cats = [searchScope];
      else if (year) cats = ["movie", "serial", "cartoon"];
      else cats = numeric ? ["movie"] : ["movie", "serial", "cartoon", "music"];
      var wide = (searchScope !== "all" || year) ? "&all=1" : "";
      Promise.all(cats.map(function (c) {
        return api("/api/catalog?cat=" + c + "&sort=" + searchSort + wide + "&q=" + encodeURIComponent(q));
      })).then(function (res) {
        if (my !== reqId) return;
        results.dataset.full = q;
        results.replaceChildren();
        var total = 0;
        res.forEach(function (d, i) {
          if (!d.ok || !d.items.length) return;
          total += d.items.length;
          if (d.fuzzy && !results.querySelector(".fuzzy-note")) results.appendChild(h("div", "fuzzy-note", "🤔 Aniq mos kelmadi — o'xshash nomlar:"));
          var cat = d.items[0].cat || cats[i];
          results.appendChild(h("div", "group-title", PLURAL[cat] + " · " + d.items.length + (d.more ? "+" : "")));
          var g = h("div", "grid" + (cat === "music" ? " music" : ""));
          d.items.forEach(function (it) { g.appendChild(card(it)); });
          results.appendChild(g);
        });
        if (!total) {
          results.appendChild(emptyBox("search", "Hech narsa topilmadi", "Boshqacha yozib ko'ring yoki kodini kiriting."));
          results.appendChild(requestButton(q));
          var pop = h("div"); results.appendChild(pop);
          popularBlock(pop, "🔥 Ommabop qidiruvlar");
        } else { pushRecent(q); }
        if (q.length >= 3) api("/api/searched", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ q: q, n: total }) }).catch(function () {});
      }).catch(function () { if (my === reqId) renderError(results, "network"); });
    }
    var ti;
    input.addEventListener("input", function () {
      clearTimeout(t); clearTimeout(ti); clear.classList.toggle("hidden", !input.value);
      var v = input.value.trim();
      if (v.length >= 2) ti = setTimeout(function () { instant(v); }, 120);          // darhol
      t = setTimeout(run, 450);                                                        // keyin — to'liq natijalar (turlar bo'yicha)
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { clearTimeout(t); input.blur(); run(); }
      else if (e.key === "Escape") { input.value = ""; run(); }
    });
    clear.onclick = function () { input.value = ""; run(); input.focus(); };
    run();
  }

  function renderError(view, reason) {
    if (reason === "network" && navigator.onLine === false) { renderOffline(view); return; }
    if (reason === "auth") {
      view.replaceChildren(h("div", "page", [emptyBox("lock", "Bot ichidan oching",
        "Saytni Telegram botdagi «" + me.brand + "» tugmasi orqali oching.")]));
      return;
    }
    var retry = h("button", "loadmore", "Qayta urinish");
    retry.onclick = function () { show(current); };
    var busy = reason === "rate";
    view.replaceChildren(h("div", "page", [emptyBox("x", busy ? "Biroz sekinroq" : "Ulanishda xatolik",
      busy ? "So'rovlar juda tez bo'ldi. Bir daqiqadan so'ng qayta urinib ko'ring." : "Internetni tekshirib, qaytadan urinib ko'ring."), retry]));
  }

  // ───── batafsil oyna ─────
  var sheetOpen = false, sheetReq = 0, lastFocus = null, mainHandler = null, trailerOpen = false;
  // Telegram'ning pastki «asosiy tugma»si (MainButton) — bor bo'lsa, ko'rish tugmasi shu bo'ladi
  function useMain(it) {
    if (PUB || !tg || !tg.MainButton || !tg.MainButton.setParams) return false;
    try {
      var label = it.locked ? "💎 Premium" : (it.cat === "music" ? "▶ Tinglash" : "▶ Kinoni ko'rish");
      if (mainHandler) tg.MainButton.offClick(mainHandler);
      var dummy = document.createElement("button");
      mainHandler = function () {
        if (it.cat === "music" && !it.locked) { Player.play(it, [it]); closeSheet(); }
        else watch(it, dummy);
      };
      tg.MainButton.onClick(mainHandler);
      tg.MainButton.setParams({ text: label, color: "#e2b450", text_color: "#1d1405", is_visible: true, is_active: true });
      return true;
    } catch (e) { return false; }
  }
  function hideMain() {
    try {
      if (tg && tg.MainButton) { if (mainHandler) tg.MainButton.offClick(mainHandler); mainHandler = null; tg.MainButton.hide(); }
    } catch (e) {}
  }

