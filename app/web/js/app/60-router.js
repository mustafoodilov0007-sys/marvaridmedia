  // ───── 🧭 brauzer tarixi (oddiy brauzer / o'rnatilgan ilova): «orqaga» tugmasi oynani yopadi, URL kino manzili bo'ladi ─────
  // Telegram ichida o'zining «Orqaga» tugmasi bor — u yerda tarix yozuvlari qo'shilmaydi.
  var HIST = PUB, histFirst = true, skipPop = 0;
  var VIEW_PATH = { home: "/", movie: "/kinolar", serial: "/seriallar", cartoon: "/multfilmlar", video: "/?v=catalog" };
  function kOf(it) { return it.code > 0 ? String(it.code) : "m" + (-it.code); }
  function pushView(name, opts) {
    if (!HIST) return;
    try {
      var o = {};
      if (opts) { if (opts.id != null) o.id = opts.id; if (opts.sort) o.sort = opts.sort; if (opts.f) o.f = opts.f; if (opts.start != null) o.start = opts.start; }
      var st = { v: name, o: o };
      if (histFirst) { histFirst = false; history.replaceState(st, "", undefined); return; }   // birinchi ko'rinish: yangi yozuv yo'q
      var cur = history.state;
      if (cur && !cur.sheet && cur.v === name && JSON.stringify(cur.o || {}) === JSON.stringify(o)) return;
      var path = VIEW_PATH[name] || ("/?v=" + name);
      if (name === "col" && opts && opts.id != null) path = /^\d+$/.test(String(opts.id)) ? "/kolleksiya/" + opts.id : "/janr/" + String(opts.id).replace(/^g_/, "");
      if (name === "cols") path = "/kolleksiyalar";
      history.pushState(st, "", path);
    } catch (e) {}
  }
  function pushSheet(it) {
    if (!HIST) return;
    try {
      var st = { sheet: kOf(it) };
      if (sheetOpen) history.replaceState(st, "", moviePath(it)); else history.pushState(st, "", moviePath(it));
    } catch (e) {}
  }
  window.addEventListener("popstate", function (e) {
    if (!HIST) return;
    if (skipPop > 0) { skipPop--; return; }
    var st = e.state || {};
    if (trailerOpen) closeTrailer(true);
    if (st.sheet) {
      if (sheetOpen) return;
      api("/api/catalog?k=" + st.sheet).then(function (d) { if (d.ok && d.items && d.items.length) openSheet(d.items[0], true); }).catch(function () {});
      return;
    }
    if (sheetOpen) closeSheet(true);
    if (st.v && st.v !== current) show(st.v, Object.assign({ nopush: true }, st.o || {}));
    else if (!st.v && current !== "home") show("home", { nopush: true });
  });

  // pastki menyudagi oltin chiziq tanlangan bo'limga siljib boradi
  function moveNavInd() {
    var nav = $("nav");
    if (!nav) return;
    var ind = nav.querySelector(".navind"), first = false;
    if (!ind) { ind = document.createElement("i"); ind.className = "navind first"; nav.appendChild(ind); nav.classList.add("hasind"); first = true; }
    var on = nav.querySelector("button.on");
    if (!on) { ind.style.opacity = "0"; return; }
    ind.style.transform = "translateX(" + Math.round(on.offsetLeft + on.offsetWidth / 2 - 14) + "px)";
    ind.style.opacity = "1";
    if (first) requestAnimationFrame(function () { requestAnimationFrame(function () { ind.classList.remove("first"); }); });
  }
  window.addEventListener("resize", function () { var i = document.querySelector(".nav .navind"); if (i) { i.classList.add("first"); moveNavInd(); requestAnimationFrame(function () { i.classList.remove("first"); }); } });
  var curOpts = {};
  function show(name, opts) {
    opts = opts || {};
    curOpts = opts;
    if (name === "catalog") name = "video";          // «Katalog» tugmasi — barcha turlar (tepada tur tablari bor)
    if (!opts.nopush) pushView(name, opts);
    current = name;
    stopHero();
    leaveShorts();
    if (name !== "login") stopLoginPoll();
    var key = navKey(name);
    document.querySelectorAll(".nav button").forEach(function (b) {
      var on = b.dataset.view === key;
      b.classList.toggle("on", on);
      if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    });
    document.querySelectorAll(".dnav button").forEach(function (b) {
      var on = b.dataset.view === key;
      b.classList.toggle("on", on);
      if (on) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current");
    });
    moveNavInd();
    window.scrollTo(0, 0);
    onScroll();
    updateBack();
    var view = $("view");
    view.classList.remove("enter"); void view.offsetWidth; view.classList.add("enter");
    var my = ++reqId;
    if (name === "home") {
      var sk = h("div", "page", [h("div", "rail", skeletonCards(4))]);
      view.replaceChildren(h("section", "hero sk"), sk);
      var dataP = homePre || api("/api/home");
      homePre = null;
      (splashGate ? Promise.all([dataP, splashGate]).then(function (r) { return r[0]; }) : dataP).then(function (d) {
        if (my !== reqId) return;
        if (!d.ok) return renderError(view, d.reason);
        renderHome(view, d);
      }).catch(function () { if (my === reqId) renderError(view, "network"); });
      return;
    }
    if (name === "saved") return renderSaved(view);
    if (name === "tv") return renderTV(view, my);
    if (name === "shorts") {
      try { return renderShorts(view, opts.start); }
      catch (err) {
        document.body.classList.remove("in-shorts");
        view.replaceChildren(h("div", "page", [emptyBox("clap", "Shorts ochilmadi", String((err && err.message) || err).slice(0, 160))]));
        return;
      }
    }
    if (name === "search") return renderSearch(view);
    if (name === "cats") return renderCats(view, my);
    if (name === "profile") return renderProfile(view);
    if (name === "login") return renderLogin(view);
    if (name === "support") return renderSupport(view, my);
    if (name === "ratings") return renderRatings(view, my);
    if (name === "sub") return renderSub(view);
    if (name === "stats") return renderStats(view, my);
    if (name === "col") return renderCollection(view, opts.id, my);
    if (name === "cols") return renderCols(view, my);
    renderCategory(view, name, opts.sort || "new", my, opts.f || {});
  }

  // meta-ma'lumot (janr, davlat, til ro'yxatlari) — bir marta olinadi
  var metaP = null;
  function getMeta() {
    if (!metaP) metaP = api("/api/catalog?cat=video&meta=1").catch(function () { metaP = null; return { ok: false }; });
    return metaP;
  }

  // filtrlar: janr (chiplar) + davlat, yil, til (tanlash maydonlari)
  var FILTERS = [["country", "🌍 Davlat"], ["year", "📅 Yil"], ["lang", "🗣 Til"]];
  function renderCategory(view, cat, sort, my, f) {
    f = f || {};
    var any = !!(f.genre || f.country || f.year || f.lang);
    function go(changes) {
      haptic();
      renderCategory(view, cat, sort, ++reqId, Object.assign({}, f, changes));
    }
    var page = h("div", "page");
    var count = h("span");
    page.appendChild(h("h1", null, cat === "video" ? "Katalog" : (PLURAL[cat] || "Kinolar")));
    page.appendChild(h("p", "lead", [count]));

    var seg = h("div", "seg");
    [["new", "Yangi"], ["top", "Top"]].concat(cat === "music" ? [] : [["rating", "Reyting"]]).forEach(function (o) {
      var b = h("button", o[0] === sort ? "on" : "", o[1]);
      b.onclick = function () { if (o[0] !== sort) { haptic(); renderCategory(view, cat, o[0], ++reqId, f); } };
      seg.appendChild(b);
    });
    page.appendChild(seg);
    var chipsRow = h("div", "gchips hidden");
    var selRow = h("div", "fsel hidden");
    page.appendChild(chipsRow);
    page.appendChild(selRow);
    function fillFilters(genresList, filters) {
      if (genresList && genresList.length) {
        var all = h("button", "gchip" + (f.genre ? "" : " on"), "Barcha janrlar");
        all.onclick = function () { if (f.genre) go({ genre: "" }); };
        chipsRow.replaceChildren(all);
        genresList.forEach(function (g) {
          var c = h("button", "gchip" + (g.key === f.genre ? " on" : ""), [g.label, h("i", null, String(g.n))]);
          c.onclick = function () { go({ genre: g.key === f.genre ? "" : g.key }); };
          chipsRow.appendChild(c);
        });
        chipsRow.classList.remove("hidden");
        var on = chipsRow.querySelector(".on");
        if (on && f.genre) setTimeout(function () { on.scrollIntoView({ inline: "center", block: "nearest" }); }, 0);
      }
      var shown = 0;
      selRow.replaceChildren();
      FILTERS.forEach(function (fl) {
        var opts = (filters && filters[fl[0]]) || [];
        if (!opts.length) return;
        shown++;
        selRow.appendChild(filterDrop(fl, opts, f[fl[0]] || "", function (k) { var c = {}; c[fl[0]] = k; go(c); }));
      });
      if (any) {
        var reset = h("button", "fpill reset", "✕ Tozalash");
        reset.onclick = function () { go({ genre: "", country: "", year: "", lang: "" }); };
        selRow.appendChild(reset);
      }
      if (shown || any) selRow.classList.remove("hidden");
    }
    var grid = h("div", "grid" + (cat === "music" ? " music" : ""), skeletonCards(6));
    page.appendChild(grid);
    view.replaceChildren(page);
    var offset = 0, first = true;
    function query() {
      var q = "";
      ["genre", "country", "year", "lang"].forEach(function (k) { if (f[k]) q += "&" + k + "=" + encodeURIComponent(f[k]); });
      return q;
    }
    function total(d) {
      var c = d.counts || {};
      return cat === "video" ? (c.movie || 0) + (c.serial || 0) + (c.cartoon || 0) : (c[cat] || 0);
    }
    function load() {
      api("/api/catalog?cat=" + cat + "&sort=" + sort + "&offset=" + offset + query()).then(function (d) {
        if (my !== reqId) return;
        if (!d.ok) return renderError(view, d.reason);
        if (first) { grid.replaceChildren(); first = false; fillFilters(d.genres, d.filters); }
        if (offset === 0) count.textContent = any ? "Topildi: " + (d.items.length + (d.more ? "+" : "")) + " ta"
          : (d.counts ? total(d) + " ta" : "");
        if (!d.items.length && offset === 0) {
          grid.replaceWith(emptyBox(CAT_ICON[cat], any ? "Hech narsa topilmadi" : "Hozircha bo'sh",
            any ? "Boshqa filtrni tanlab ko'ring." : "Bu bo'limga tez orada qo'shiladi."));
          return;
        }
        d.items.forEach(function (it) { grid.appendChild(card(it)); });
        offset += d.items.length;
        var old = page.querySelector(".loadmore");
        if (old) old.remove();
        if (d.more) {
          var mb = h("button", "loadmore", "Yana yuklash");
          mb.onclick = function () { mb.textContent = "Yuklanmoqda..."; load(); };
          page.appendChild(mb);
          if (window.IntersectionObserver) {
            var io = new IntersectionObserver(function (en) {
              if (en[0].isIntersecting) { io.disconnect(); mb.textContent = "Yuklanmoqda..."; load(); }
            }, { rootMargin: "500px" });
            io.observe(mb);
          }
        }
      }).catch(function () { if (my === reqId) renderError(view, "network"); });
    }
    load();
  }

  function renderCollection(view, id, my) {
    var title = h("h1", null, "📚 To'plam");
    var grid = h("div", "grid", skeletonCards(6));
    var page = h("div", "page", [title, h("p", "lead", "Biz siz uchun saralab qo'ydik 🍿"), grid]);
    view.replaceChildren(page);
    api("/api/collection?id=" + id).then(function (d) {
      if (my !== reqId) return;
      if (!d.ok) return renderError(view, d.reason);
      title.textContent = d.title;
      grid.replaceChildren();
      if (!d.items.length) return grid.replaceWith(emptyBox("film", "Hozircha bo'sh", "Tez orada kinolar qo'shiladi."));
      d.items.forEach(function (it) { grid.appendChild(card(it)); });
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }

