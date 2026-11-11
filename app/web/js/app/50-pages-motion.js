  // ───── sahifalar ─────
  var current = "home", reqId = 0;
  var CAT_VIEWS = { video: 1, movie: 1, serial: 1, cartoon: 1, music: 1, shorts: 1, col: 1, cols: 1 };
  function rail(r) {
    var sec = h("section", "section");
    var moreBtn = null;
    if (r.cat || r.more) {
      moreBtn = h("button", "more", ["Hammasi", icon("chev")]);
      moreBtn.onclick = r.more || function () { show(r.cat, { sort: r.sort, f: r.f }); };
    }
    sec.appendChild(h("div", "sec-head", [h("h2", null, String(r.title || "").replace(/^[^\p{L}\p{N}]+/u, "")), moreBtn]));
    var list = h("div", "rail" + (r.cat === "music" ? " music" : "") + (r.cls ? " " + r.cls : ""));
    r.items.forEach(function (it, i) { list.appendChild(r.wrapItem ? r.wrapItem(it, i) : card(it)); });
    var wrap = h("div", "railwrap", [list]);
    var l = h("button", "rarrow l", [icon("chev")]), rr = h("button", "rarrow r", [icon("chev")]);
    l.setAttribute("aria-label", "Orqaga"); rr.setAttribute("aria-label", "Oldinga");
    function step(dir) { list.scrollBy({ left: dir * list.clientWidth * 0.85, behavior: REDUCE ? "auto" : "smooth" }); }
    l.onclick = function () { step(-1); }; rr.onclick = function () { step(1); };
    function upd() {
      l.classList.toggle("off", list.scrollLeft < 8);
      rr.classList.toggle("off", list.scrollLeft + list.clientWidth >= list.scrollWidth - 8);
    }
    list.addEventListener("scroll", upd, { passive: true });
    setTimeout(upd, 60);
    wrap.appendChild(l); wrap.appendChild(rr);
    sec.appendChild(wrap);
    return sec;
  }
  function shortCard(it, idx) {
    var b = h("div", "card");
    var main = h("button", "cmain");
    main.type = "button";
    var p;
    if (it.short.kind === "photo") {
      p = h("div", "poster");
      var img = new Image(); img.alt = ""; img.loading = "lazy";
      img.onload = function () { img.classList.add("ok"); };
      img.src = "/media/short/" + it.short.id;
      p.appendChild(img);
    } else {
      p = posterNode(it);
    }
    p.appendChild(h("span", "playmark", [icon("play")]));
    main.appendChild(p);
    main.appendChild(h("div", "t", it.title));
    main.setAttribute("aria-label", it.title + " — shorts");
    b.appendChild(main);
    b.onclick = function () { show("shorts", { start: idx }); };
    return b;
  }
  var homeGenres = [];
  function quickChips(genresList, noRandom) {
    var row = h("div", "gchips qchips");
    if (!noRandom) {
      var rnd = h("button", "gchip rnd", [icon("dice"), "Tasodifiy kino"]);
      rnd.onclick = function () { randomMovie(rnd); };
      row.appendChild(rnd);
    }
    (genresList || []).forEach(function (g) {
      var c = h("button", "gchip", [gname(g), h("i", null, String(g.n))]);
      c.onclick = function () { haptic(); show("video", { f: { genre: g.key } }); };
      row.appendChild(c);
    });
    return h("div", "qwrap", [row]);
  }

  // ───── ✨ jonli animatsiyalar: fon zarralari, ikonkalar qatori, 3D karusel, kolleksiya va davlatlar ─────
  var ambientOn = false;
  function startAmbient() {
    if (ambientOn || REDUCE || LITE) return;
    ambientOn = true;
    var box = h("div", "amb");
    box.setAttribute("aria-hidden", "true");
    var n = (navigator.hardwareConcurrency || 4) <= 4 ? 9 : 15;
    for (var i = 0; i < n; i++) {
      var d = document.createElement("i"), sz = 3 + Math.random() * 5;
      d.style.cssText = "left:" + (Math.random() * 100) + "%;width:" + sz + "px;height:" + sz + "px;animation-duration:" +
        (11 + Math.random() * 12) + "s;animation-delay:" + (-Math.random() * 18) + "s;--dx:" + (Math.random() * 90 - 45) + "px";
      box.appendChild(d);
    }
    document.body.insertBefore(box, document.body.firstChild);
    document.addEventListener("visibilitychange", function () { box.classList.toggle("paused", document.hidden); });
  }

  // meta-satr: [16+] Film · 2026 · 2 soat 25 daq · AQSH
  function metaNode(it) {
    var bits = [NAMES[it.cat] || "Kino"];
    if (it.year) bits.push(yr(it));
    var dur = fmtDur(it.duration); if (dur) bits.push(dur);
    var cn = countryName(it); if (cn) bits.push(cn);
    var meta = h("div", "meta");
    var ab = ageBadge(it); if (ab) meta.appendChild(ab);
    bits.forEach(function (bt, k) { if (k) meta.appendChild(h("i", null, "·")); meta.appendChild(document.createTextNode(bt)); });
    return meta;
  }

  // 3D karusel (haftaning TOP'i): cheksiz aylanadi, sichqoncha bilan sudraladi, poster bosilsa qisqa ma'lumot ochiladi
  function coverflow(r) {
    var sec = h("section", "section cfsec");
    var moreBtn = null;
    if (r.cat || r.more) {
      moreBtn = h("button", "more", ["Hammasi", icon("chev")]);
      moreBtn.onclick = r.more || function () { show(r.cat, { sort: r.sort, f: r.f }); };
    }
    sec.appendChild(h("div", "sec-head", [h("h2", null, r.title), moreBtn]));
    var items = r.items.slice(0, 10), n = items.length, COPIES = 3, mid = n;   // 3 nusxa: o'rtadagisida turamiz, chekkaga yetsak sezdirmay ko'chamiz
    var cf = h("div", "cf");
    var inner = h("div", "cfin");
    var info = h("div", "cfinfo", [inner]);
    info.setAttribute("aria-live", "polite");
    var cur = -1, curG = 0, tgt = null, open = false, idleT = 0, ticking = false;   // tgt — oxirgi bosilgan maqsad (tez bosilganda adashmaslik uchun)
    function childLeft(el) { return el.offsetLeft - cf.offsetLeft - (cf.clientWidth - el.offsetWidth) / 2; }
    var glideRaf = 0;
    function glide(to) {                 // sekin, yumshoq (ease-in-out) surilish — poster «sakramaydi»
      cancelAnimationFrame(glideRaf);
      var from = cf.scrollLeft, dist = to - from;
      if (Math.abs(dist) < 2) return;
      var dur = Math.min(760, 420 + Math.abs(dist) * 0.3), t0 = performance.now();
      cf.style.scrollSnapType = "none";
      (function frame(t) {
        var k = Math.min(1, (t - t0) / dur), e = k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        cf.scrollLeft = from + dist * e;
        if (k < 1) glideRaf = requestAnimationFrame(frame); else cf.style.scrollSnapType = "";
      })(t0);
    }
    cf.addEventListener("touchstart", function () { if (glideRaf) { cancelAnimationFrame(glideRaf); glideRaf = 0; cf.style.scrollSnapType = ""; } }, { passive: true });
    function centerOn(g, instant) {
      var el = cf.children[g];
      if (!el) return;
      tgt = g;
      if (REDUCE || instant) cf.scrollTo({ left: childLeft(el), behavior: "auto" });
      else glide(childLeft(el));
    }
    var lastStep = 0;
    function shiftSet(d) {   // bir nusxa kengligiga sezdirmay ko'chish (ko'rinish bir xil qoladi)
      cf.style.scrollSnapType = "none";
      cf.scrollLeft += d;
      requestAnimationFrame(function () { cf.style.scrollSnapType = ""; });
    }
    function step(dir) {
      lastStep = Date.now();
      var base = tgt == null ? bestChild() : tgt;
      if (base < n || base >= 2 * n) {   // chekka nusxada bo'lsak, avval o'rtadagisiga ko'chamiz — shunda qadam adashmaydi
        var setW = cf.children[n].offsetLeft - cf.children[0].offsetLeft;
        shiftSet(base < n ? setW : -setW);
        base += base < n ? n : -n;
      }
      centerOn(base + dir);
    }
    function build(it) {   // poster bosilganda chiqadigan qisqa ma'lumot
      var gp = h("div", "gpills");
      (it.genres || []).slice(0, 3).forEach(function (g) { gp.appendChild(h("span", "gpill", gname(g))); });
      var t = h("button", "cft", [it.title, icon("chev")]);
      t.type = "button"; t.onclick = function () { openSheet(it, false, cf.querySelector(".cfc.on .poster")); };
      var cx = h("button", "cfx", [icon("x")]);
      cx.type = "button"; cx.setAttribute("aria-label", "Yopish"); cx.onclick = function (e) { e.stopPropagation(); setOpen(false); };
      inner.replaceChildren(cx, t, metaNode(it), ratingBadges(it), gp.childNodes.length ? gp : null, actionRow(it, false));
    }
    function place() {         // ma'lumot oynasi aynan o'rtadagi poster ustida turadi
      var c = cf.children[curG], pe = c && c.querySelector(".poster");
      if (!pe) return;
      var wr = info.parentNode.getBoundingClientRect(), pr = pe.getBoundingClientRect();
      var w = Math.min(wr.width - 16, Math.max(pr.width + 56, 252));
      info.style.width = w + "px";
      info.style.left = Math.round(pr.left - wr.left + pr.width / 2 - w / 2) + "px";
      info.style.top = Math.round(pr.top - wr.top) + "px";
      info.style.minHeight = Math.round(pr.height) + "px";
    }
    info.onclick = function (e) { if (!e.target.closest("button, a")) setOpen(false); };
    window.addEventListener("resize", function () { if (open) setOpen(false); });
    function setOpen(v) {
      open = v;
      if (v) { build(items[cur]); place(); }
      info.classList.toggle("open", v);
      if (cf.children[curG]) cf.children[curG].setAttribute("aria-expanded", v ? "true" : "false");
    }
    for (var k = 0; k < COPIES; k++) {
      items.forEach(function (it, i) {
        var c = h("button", "cfc", [posterNode(it, 720), h("span", "rkb", String(i + 1))]);
        c.type = "button"; c._i = i;
        c.setAttribute("aria-label", (i + 1) + ". " + it.title);
        c.setAttribute("aria-expanded", "false");
        if (k !== 1) { c.setAttribute("aria-hidden", "true"); c.tabIndex = -1; }
        c.onclick = function () {
          haptic();
          var g = Array.prototype.indexOf.call(cf.children, c);
          if (c.classList.contains("on")) openSheet(items[c._i], false, c.querySelector(".poster"));   // o'rtadagi poster — kino sahifasi ochiladi
          else centerOn(g);                                                                              // yonidagisi — yumshoq o'rtaga keladi
        };
        cf.appendChild(c);
      });
    }
    var l = h("button", "cfa l", [icon("chev")]), rr = h("button", "cfa r", [icon("chev")]);
    l.type = rr.type = "button";
    l.setAttribute("aria-label", "Oldingi"); rr.setAttribute("aria-label", "Keyingi");
    l.onclick = function () { setOpen(false); step(-1); };
    rr.onclick = function () { setOpen(false); step(1); };
    sec.appendChild(h("div", "cfwrap", [cf, l, rr]));
    function bestChild() {
      var cr = cf.getBoundingClientRect(), cx = cr.left + cr.width / 2, best = 0, bd = 1e9;
      Array.prototype.forEach.call(cf.children, function (c, i) {
        var b = c.getBoundingClientRect(), d = Math.abs(b.left + b.width / 2 - cx);
        if (d < bd) { bd = d; best = i; }
      });
      return best;
    }
    var geo = null;                    // kartochkalar joyi (bir marta o'lchanadi; o'lcham o'zgarsa qayta) — har kadrda o'lchash yo'q
    function measure() {
      var base = cf.offsetLeft;
      geo = Array.prototype.map.call(cf.children, function (c) { return { x: c.offsetLeft - base, w: c.offsetWidth || 1 }; });
    }
    function layout() {
      ticking = false;
      if (!geo || geo.length !== cf.children.length) measure();
      var kids = cf.children, cw = cf.clientWidth, mid = cf.scrollLeft + cw / 2, best = 0, bd = 1e9;
      for (var i = 0; i < kids.length; i++) {
        var c = kids[i], g = geo[i], d = (g.x + g.w / 2 - mid) / g.w;
        if (Math.abs(d) < bd) { bd = Math.abs(d); best = i; }
        if (Math.abs(d) * g.w > cw / 2 + 2 * g.w) { if (c._on) { c.classList.remove("on"); c._on = false; } continue; }   // ko'rinmaydiganlarga tegmaymiz
        var ad = Math.min(Math.abs(d), 2.2), on = ad < 0.4;
        c.style.transform = (LITE ? "" : "perspective(800px) rotateY(" + (Math.max(-1.2, Math.min(1.2, d)) * -14).toFixed(1) + "deg) ") + "scale(" + (1 - ad * 0.08).toFixed(3) + ")";
        if (c.firstChild) c.firstChild.style.opacity = (1 - Math.min(ad, 1.5) * 0.32).toFixed(2);
        c.style.zIndex = String(10 - Math.round(ad * 3));
        if (on !== c._on) { c.classList.toggle("on", on); c._on = on; }
      }
      curG = best;
      var oi = cf.children[best]._i;
      if (oi !== cur) { cur = oi; if (open) { open = false; info.classList.remove("open"); } }   // boshqa kinoga o'tilsa panel yopiladi
    }
    function queue() { if (!ticking) { ticking = true; requestAnimationFrame(layout); } }
    // to'xtagach: chekka nusxaga o'tib qolgan bo'lsak, bir xil joyga (o'rtadagi nusxaga) ko'chamiz — foydalanuvchi sezmaydi
    function settle() {
      if (cf.classList.contains("dragging") || !document.body.contains(cf)) return;
      if (Date.now() - lastStep < 400) { clearTimeout(idleT); idleT = setTimeout(settle, 200); return; }   // qadam hali tugamagan
      tgt = null;
      var bi = bestChild(), setW = cf.children[n].offsetLeft - cf.children[0].offsetLeft, d = 0;
      if (bi < n) d = setW; else if (bi >= 2 * n) d = -setW;
      if (!d) return;
      cf.style.scrollSnapType = "none";
      cf.scrollLeft += d;
      requestAnimationFrame(function () { cf.style.scrollSnapType = ""; layout(); });
    }
    cf.addEventListener("scroll", function () { queue(); clearTimeout(idleT); idleT = setTimeout(settle, 140); }, { passive: true });
    cf._dragEnd = function () { centerOn(bestChild()); };
    window.addEventListener("resize", function () { geo = null; queue(); });
    cf.addEventListener("keydown", function (e) {   // klaviatura: ← → strelkalar
      var dir = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
      if (!dir) return;
      e.preventDefault(); setOpen(false);
      step(dir);
      setTimeout(function () {   // fokusni o'rtadagi nusxadagi markaziy kartochkaga beramiz
        var g = bestChild(), t = cf.children[g < n ? g + n : g >= 2 * n ? g - n : g];
        if (t) { try { t.focus({ preventScroll: true }); } catch (x) {} }
      }, 500);
    });
    requestAnimationFrame(function () { requestAnimationFrame(function () { centerOn(mid, true); queue(); }); });
    // avtomatik aylanish yo'q: posterlar faqat foydalanuvchi surganda harakatlanadi (o'zidan «o'ynab ketmaydi»)
    return sec;
  }

  // 🖱 kompyuterda: gorizontal ro'yxatlarni sichqonchaning chap tugmasini bosib ushlab sudrash
  (function () {
    var SEL = ".rail, .cf, .gchips", el = null, sx = 0, sl = 0, moved = false, suppress = false;
    document.addEventListener("pointerdown", function (e) {
      if (e.pointerType !== "mouse" || e.button !== 0 || !e.target.closest) return;
      var t = e.target.closest(SEL);
      if (!t || t.scrollWidth <= t.clientWidth + 2) return;
      el = t; sx = e.clientX; sl = t.scrollLeft; moved = false;
    });
    document.addEventListener("pointermove", function (e) {
      if (!el) return;
      var dx = e.clientX - sx;
      if (!moved) { if (Math.abs(dx) < 6) return; moved = true; el.classList.add("dragging"); }
      el.scrollLeft = sl - dx;
    });
    function end() {
      if (!el) return;
      var t = el; el = null;
      if (!moved) return;
      suppress = true; setTimeout(function () { suppress = false; }, 0);   // sudrashdan keyin tasodifan bosilib ketmasin
      t.classList.remove("dragging");
      if (t._dragEnd) t._dragEnd();
    }
    document.addEventListener("pointerup", end);
    document.addEventListener("pointercancel", end);
    document.addEventListener("click", function (e) { if (suppress) { e.stopPropagation(); e.preventDefault(); } }, true);
    document.addEventListener("dragstart", function (e) { if (e.target.closest && e.target.closest(SEL)) e.preventDefault(); });
  })();

  // umumiy TOP: katta raqamli «Top 10» qatori
  function rankItem(it, i) {
    var w = h("div", "rk", [h("span", "rn", String(i + 1)), card(it)]);
    w.firstChild.setAttribute("aria-hidden", "true");
    return w;
  }

  // mehmon (brauzer) uchun: Telegram ilovasida ochishni taklif qilish
  function openInTelegram() {
    var b = h("a", "tgbanner", [h("span", "ti", "📱"), h("div", null, [h("b", null, "Telegram'da oching"),
      h("span", null, "Kino bir bosishda chatga keladi, baho va sevimlilar saqlanadi")]), h("em", null, "Ochish")]);
    b.href = me.miniapp; b.target = "_blank"; b.rel = "noopener";
    return b;
  }

  // bo'limlar ekranga kirganda silliq paydo bo'ladi
  function reveal(view) {
    var els = view.querySelectorAll(".section, .foot");
    if (REDUCE || !("IntersectionObserver" in window)) return;
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { threshold: 0.06, rootMargin: "0px 0px -4% 0px" });
    Array.prototype.forEach.call(els, function (el, i) { if (i > 0) { el.classList.add("rv"); io.observe(el); } });
  }

  function catPills() {
    var row = h("div", "gchips qchips cpills");
    [["video", "Hammasi", "grid"], ["movie", "Kinolar", "film"], ["serial", "Seriallar", "tv"], ["cartoon", "Multfilmlar", "smile"], ["music", "Musiqa", "music"]].forEach(function (o) {
      var c = h("button", "gchip", [icon(o[2]), o[1]]);
      c.dataset.k = o[0];
      c.onclick = function () { haptic(); show(o[0]); };
      row.appendChild(c);
    });
    var rnd = h("button", "gchip rnd", [icon("dice"), "Tasodifiy"]);
    rnd.onclick = function () { randomMovie(rnd); };
    row.appendChild(rnd);
    return h("div", "qwrap", [row]);
  }
  // 🔎 qidiruv qatori va dumaloq tezkor ikonkalar (Ommabop, Yangi, ...)
  function homeTools() {
    var sb = h("button", "hsearch", [icon("search"), h("span", null, "Kino nomi yoki kodi..."), h("i", null, [icon("dice")])]);
    sb.setAttribute("aria-label", "Qidirish");
    sb.onclick = function (e) {
      haptic();
      if (e.target.closest("i")) randomMovie(); else show("search");
    };
    var row = h("div", "scs");
    [["🔥", "Ommabop", "linear-gradient(145deg,#ff8a3d,#e0481b)", function () { show("video", { sort: "top" }); }],
     ["🆕", "Yangi", "linear-gradient(145deg,#4cc9ff,#2a7de1)", function () { show("video", { sort: "new" }); }],
     ["📺", "Seriallar", "linear-gradient(145deg,#b58cff,#6a45d6)", function () { show("serial"); }],
     ["🧸", "Multfilm", "linear-gradient(145deg,#ffcf5c,#e8962b)", function () { show("cartoon"); }],
     ["🎵", "Musiqa", "linear-gradient(145deg,#ff7aa8,#d63d78)", function () { show("music"); }],
     ["🗂", "Kategoriya", "linear-gradient(145deg,#6fe0b5,#1f9d7a)", function () { show("cats"); }],
     ["🎲", "Tasodifiy", "linear-gradient(145deg,#c9c3b8,#7d7668)", function () { randomMovie(); }]].forEach(function (o) {
      var b = h("button", "sc", [h("span", "scico", o[0]), h("span", "sclab", o[1])]);
      b.querySelector(".scico").style.background = o[2];
      b.onclick = function () { haptic(); o[3](); };
      row.appendChild(b);
    });
    return h("div", "htools", [sb, row]);
  }
  // 🏆 Haftaning TOP-5: tablar (Hammasi / Filmlar / Seriallar) va yon tomonga suriladigan kartalar
  function topBanner(items) {
    var sec = h("section", "section tb");
    var mode = "all", idx = 0, timer = null, list = [];
    var tabsRow = h("div", "tb-tabs");
    var track = h("div", "tb-track"), dots = h("div", "tb-dots");
    var view = h("div", "tb-view", [track]);
    function pool(m) {
      return items.filter(function (it) { return m === "all" || (m === "movie" ? it.cat !== "serial" : it.cat === "serial"); }).slice(0, 5);
    }
    [["all", "Hammasi"], ["movie", "Filmlar"], ["serial", "Seriallar"]].forEach(function (o) {
      if (o[0] !== "all" && !pool(o[0]).length) return;
      var b = h("button", "tb-tab" + (o[0] === mode ? " on" : ""), o[1]);
      b.onclick = function () {
        if (mode === o[0]) return; haptic(); mode = o[0];
        tabsRow.querySelectorAll(".tb-tab").forEach(function (x) { x.classList.toggle("on", x === b); });
        build();
      };
      tabsRow.appendChild(b);
    });
    function metaOf(it) {
      var bits = [yr(it), (it.genres && it.genres[0]) ? it.genres[0].label : "", it.imdb ? "★ " + it.imdb : ""].filter(Boolean);
      return bits.join(" · ");
    }
    function slide(it, i) {
      var btn = h("button", "tb-go", [icon(it.locked ? "lock" : "send"), it.locked ? "Premium" : (PUB ? "Telegramda ochish" : "Botga yuborish")]);
      btn.onclick = function (e) { e.stopPropagation(); watch(it, btn); };
      var s2 = h("div", "tb-slide", [
        h("div", "tb-txt", [h("div", "tb-kick", "🏆 Hafta topi №" + (i + 1)), h("h3", null, it.title),
          h("div", "tb-meta", metaOf(it)), h("div", "tb-type", NAMES[it.cat] || "Kino"), btn]),
        h("div", "tb-poster", [posterNode(it, 360)])]);
      s2.onclick = function () { openSheet(it, false, s2.querySelector(".tb-poster .poster")); };
      return s2;
    }
    function go(i, instant) {
      if (!list.length) return;
      idx = (i + list.length) % list.length;
      track.style.transition = instant || REDUCE ? "none" : "transform .55s cubic-bezier(.22,.8,.22,1)";
      track.style.transform = "translateX(" + (-idx * 100) + "%)";
      track.querySelectorAll(".tb-slide").forEach(function (x, k) { x.classList.toggle("on", k === idx); });
      dots.querySelectorAll("i").forEach(function (d, k) { d.classList.toggle("on", k === idx); });
    }
    function restart() { clearInterval(timer); if (list.length > 1 && !REDUCE) timer = setInterval(function () { if (document.body.contains(sec) && !sheetOpen) go(idx + 1); }, 4500); }
    function build() {
      list = pool(mode);
      track.replaceChildren(); dots.replaceChildren();
      list.forEach(function (it, i) {
        track.appendChild(slide(it, i));
        var d = h("i"); d.onclick = function () { go(i); restart(); }; dots.appendChild(d);
      });
      go(0, true); restart();
    }
    var x0 = null;
    view.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; clearInterval(timer); }, { passive: true });
    view.addEventListener("touchend", function (e) {
      if (x0 != null) { var dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 40) go(idx + (dx < 0 ? 1 : -1)); }
      x0 = null; restart();
    }, { passive: true });
    build();
    sec.appendChild(tabsRow); sec.appendChild(view); sec.appendChild(dots);
    return sec;
  }
  // 📚 Kolleksiyalar: har biri — 4 ta poster «ramkasi», nomi va kinolar soni
  function colCard(c) {
    var strip = h("div", "cstrip");
    (c.covers || []).slice(0, 4).forEach(function (cv) {
      var im = new Image(); im.alt = ""; im.loading = "lazy"; im.decoding = "async";
      im.src = posterUrl(cv, 360);
      strip.appendChild(im);
    });
    var b = h("button", "colcard", [strip, h("b", null, c.title), h("span", null, c.n + " ta kino")]);
    b.type = "button";
    b.onclick = function () { haptic(); show("col", { id: c.id }); };
    return b;
  }
  function collectionsRail(list) {
    var sec = h("section", "section");
    var more = h("button", "more", ["Hammasi", icon("chev")]);
    more.onclick = function () { show("cols"); };
    sec.appendChild(h("div", "sec-head", [h("h2", null, "📚 Kolleksiyalar"), more]));
    var rl = h("div", "rail cols");
    list.forEach(function (c) { rl.appendChild(colCard(c)); });
    sec.appendChild(h("div", "railwrap", [rl]));
    return sec;
  }
  function renderCols(view, my) {
    var grid = h("div", "colgrid");
    view.replaceChildren(h("div", "page", [h("h1", null, "📚 Kolleksiyalar"), h("p", "lead", "Biz siz uchun saralab qo'ydik 🍿"), grid]));
    api("/api/collections").then(function (d) {
      if (my !== reqId) return;
      if (!d.ok || !d.items.length) return grid.replaceWith(emptyBox("film", "Hozircha bo'sh", "Tez orada kinolar qo'shiladi."));
      d.items.forEach(function (c) { grid.appendChild(colCard(c)); });
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }
  function renderHome(view, data) {
    startAmbient();
    homeGenres = data.genres || [];
    view.replaceChildren(h("h1", "sr-only", (me.brand || "Marvarid Media") + " — kinolar, seriallar va multfilmlar"), heroView(data.hero || []));
    if (PUB && me.miniapp) view.appendChild(openInTelegram());
    var pb = premiumBanner(); if (pb) view.appendChild(pb);
    var ib = installBanner(); if (ib) view.appendChild(ib);
    var plr = popularListsRail(data.lists); if (plr) view.appendChild(plr);
    view.appendChild(tvHomeCard());
    if (data.daily) view.appendChild(dailyCard(data.daily));
    var any = false;
    var byKey = {};
    (data.rails || []).forEach(function (r) { byKey[r.key] = r; });
    function add(node) { any = true; view.appendChild(node); }
    // 1-qator: haftaning TOP'i (shu haftadagi ko'rishlar), 2-qator: umumiy davr uchun eng ko'p ko'rilganlar
    var tp = byKey.top, weekly = data.weekly || [];
    var topRail = tp && tp.items.length ? rail(Object.assign({}, tp, { title: "Eng ko'p ko'rilgan", items: tp.items.slice(0, 10),
      cls: "rankrail", wrapItem: rankItem })) : null;
    var fresh = guest() ? [] : (data.fresh || []);
    ["serial", "cartoon"].forEach(function (c) {                 // 🔴 pastki menyuda: shu bo'limda yangi qism bor
      var bt = document.querySelector('#nav button[data-view="' + c + '"]');
      if (bt) bt.classList.toggle("dotted", fresh.some(function (x) { return x.cat === c; }));
    });
    if (fresh.length) add(rail({ title: "🆕 Yangi qism chiqdi", items: fresh, cls: "hist freshrail" }));
    if (weekly.length >= 1) add(topBanner(weekly));
    if ((data.collections || []).length) add(collectionsRail(data.collections));
    if (weekly.length >= 3) add(coverflow({ title: "🔥 Haftaning TOP'i", items: weekly, cat: "video", sort: "top" }));
    var hist = guest() ? localHist : (data.history || []);          // «Davom ettiring» — haftaning TOP'idan keyin
    if (hist.length) add(rail({ title: "🕘 Davom ettiring", items: hist, cls: "hist", wrapItem: function (it) {
      var c = card(it);
      if (it.resume) { var pill = h("span", "resume", "▶ " + it.resume + "-qism"); (c.querySelector(".poster") || c).appendChild(pill); }
      return c;
    } }));
    if (data.foryou && data.foryou.length) add(rail({ title: "🎯 Siz uchun", items: data.foryou, more: function () { show("foryou"); } }));
    var nw = byKey["new"]; if (nw && nw.items.length) add(rail(nw));
    if (topRail && weekly.length < 3) add(topRail);
    (data.extra || []).slice(0, 2).forEach(function (r) { add(rail(r)); });
    ["serial", "cartoon"].forEach(function (k) { var r = byKey[k]; if (r && r.items.length) add(rail(r)); });
    if (data.shorts && data.shorts.length) {
      var sec = h("section", "section");
      var mb = h("button", "more", ["Hammasi", icon("chev")]);
      mb.onclick = function () { show("shorts"); };
      sec.appendChild(h("div", "sec-head", [h("h2", null, "Shorts"), mb]));
      var list = h("div", "rail shorts-rail");
      data.shorts.forEach(function (it, i) { list.appendChild(shortCard(it, i)); });
      sec.appendChild(list);
      add(sec);
    }
    var mu = byKey.music; if (mu && mu.items.length) add(rail(mu));
    if (!any) view.appendChild(emptyBox("film", "Hozircha bo'sh", "Kinolar qo'shilishi bilan shu yerda paydo bo'ladi."));
    var heart = h("button", "more", "💝 Bizni qo'llab-quvvatlang");
    heart.onclick = function () { haptic(); show("support"); };
    var legal = h("div", "legal", [h("a", null, "Foydalanish shartlari"), h("a", null, "Maxfiylik siyosati")]);
    legal.children[0].href = "/shartlar"; legal.children[1].href = "/maxfiylik";
    view.appendChild(h("div", "foot", [h("span", null, (me.brand || "Marvarid Media") + " — eng sara kinolar bir joyda"), heart, legal]));
    reveal(view);
  }

  // splash animatsiyasi paytida bosh sahifa chizilmaydi (qotib qolmasin): ma'lumot oldindan olinadi, chizish animatsiya tugagach
  var splashGate = null, homePre = null;
  function navKey(name) { return name === "video" || name === "cats" || name === "col" || name === "cols" ? "movie" : name === "foryou" ? "home" : name; }
