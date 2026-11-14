  // ───── 🎭 Aktyorlar tarkibi, Kadrlar, Byudjet va Kassa (TMDB dan admin saqlagan bo'lsa; bo'lmasa hech narsa ko'rinmaydi) ─────
  var TMG = "https://image.tmdb.org/t/p/";
  function money(n) { return "$" + String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0"); }
  function initials(name) {
    var p = String(name || "").trim().split(/\s+/);
    return ((p[0] || "").charAt(0) + (p.length > 1 ? p[p.length - 1].charAt(0) : "")).toUpperCase();
  }
  function person(c) {
    var ph = h("div", "cph");
    if (c.p) {
      var im = new Image();
      im.loading = "lazy"; im.decoding = "async"; im.alt = c.n; im.src = TMG + "w185" + c.p;
      im.onerror = function () { im.remove(); ph.textContent = initials(c.n); };
      ph.appendChild(im);
    } else ph.textContent = initials(c.n);
    return h("div", "cperson", [ph, h("b", null, c.n), c.r ? h("span", null, c.r) : null]);
  }
  // kadrni katta ko'rish: ← → tugmalari, surish (telefon), Esc va fonga bosish yopadi
  function openLightbox(list, start) {
    var i = start || 0, sx = 0;
    var img = document.createElement("img"); img.alt = "";
    var cnt = h("span", "lbcnt");
    var prev = h("button", "lbnav prev", "‹"), next = h("button", "lbnav next", "›"), close = h("button", "lbx", "✕");
    [prev, next, close].forEach(function (b) { b.type = "button"; });
    prev.setAttribute("aria-label", "Oldingi"); next.setAttribute("aria-label", "Keyingi"); close.setAttribute("aria-label", "Yopish");
    var box = h("div", "lbox", [img, prev, next, close, cnt]);
    box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true");
    function show(n) {
      i = (n + list.length) % list.length;
      img.src = TMG + "w1280" + list[i];
      cnt.textContent = (i + 1) + " / " + list.length;
      prev.style.display = next.style.display = list.length > 1 ? "" : "none";
    }
    function done() {
      document.removeEventListener("keydown", key, true);
      box.classList.remove("in");
      setTimeout(function () { box.remove(); }, 180);
    }
    function key(e) {
      if (e.key === "Escape") { e.stopPropagation(); e.preventDefault(); done(); }
      else if (e.key === "ArrowRight") { e.stopPropagation(); show(i + 1); }
      else if (e.key === "ArrowLeft") { e.stopPropagation(); show(i - 1); }
    }
    prev.onclick = function (e) { e.stopPropagation(); show(i - 1); };
    next.onclick = function (e) { e.stopPropagation(); show(i + 1); };
    close.onclick = function (e) { e.stopPropagation(); done(); };
    box.onclick = function (e) { if (e.target === box) done(); };
    box.addEventListener("touchstart", function (e) { sx = e.touches[0].clientX; }, { passive: true });
    box.addEventListener("touchend", function (e) {
      var dx = e.changedTouches[0].clientX - sx;
      if (Math.abs(dx) > 50) show(i + (dx < 0 ? 1 : -1));
    }, { passive: true });
    document.addEventListener("keydown", key, true);
    document.body.appendChild(box);
    show(i);
    requestAnimationFrame(function () { box.classList.add("in"); });
  }
  function loadExtra(it, box, details, alive) {
    api("/api/extra?id=" + it.id).then(function (d) {
      if (!alive() || !d || !d.ok) return;
      function drow2(label, value) { return h("div", "drow", [h("span", null, label), h("b", null, value)]); }
      if (d.budget && details) details.appendChild(drow2("Byudjet", money(d.budget)));
      if (d.revenue && details) details.appendChild(drow2("Jahon bo'yicha kassa", money(d.revenue)));
      var kids = [];
      if (d.cast && d.cast.length) {
        var rail = h("div", "cast", d.cast.map(person));
        var head = [h("h2", null, "Aktyorlar tarkibi")];
        if (d.cast.length > 6) {
          var tg = h("button", "xall", [h("span", null, "Hammasi"), h("i", null, String(d.cast.length))]);
          tg.type = "button";
          tg.onclick = function () { haptic(); var on = rail.classList.toggle("grid"); tg.classList.toggle("on", on); };
          head.push(tg);
        }
        kids.push(h("div", "xsec", [h("div", "sec-head", head), rail]));
      }
      if (d.stills && d.stills.length) {
        var SHOW = 6, grid = h("div", "stills");
        d.stills.forEach(function (path, idx) {
          var im = new Image();
          im.loading = "lazy"; im.decoding = "async"; im.alt = ""; im.src = TMG + "w500" + path;
          var b = h("button", "still" + (idx >= SHOW ? " extra" : ""), [im]);
          b.type = "button"; b.setAttribute("aria-label", "Kadr " + (idx + 1));
          b.onclick = function () { haptic(); openLightbox(d.stills, idx); };
          grid.appendChild(b);
        });
        var shead = [h("h2", null, "Kadrlar")];
        if (d.stills.length > SHOW) {
          var more = h("button", "xall", [h("span", null, "Barcha rasmlar"), h("i", null, String(d.stills.length))]);
          more.type = "button";
          more.onclick = function () { haptic(); var on = grid.classList.toggle("all"); more.classList.toggle("on", on); };
          shead.push(more);
        }
        kids.push(h("div", "xsec", [h("div", "sec-head", shead), grid]));
      }
      if (kids.length) box.replaceChildren.apply(box, kids);
    }).catch(function () {});
  }
