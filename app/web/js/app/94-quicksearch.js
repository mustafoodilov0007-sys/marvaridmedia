  // ───── 🔎 tezkor qidiruv (kompyuter): sarlavhadagi qidiruv bosilganda — yozgan sari poster bilan natijalar chiqadi ─────
  var qsOpen = null;
  function closeQuickSearch() {
    if (!qsOpen) return;
    var q = qsOpen; qsOpen = null;
    q.box.classList.remove("in"); q.veil.classList.remove("in");
    document.removeEventListener("keydown", q.key, true);
    setTimeout(function () { q.box.remove(); q.veil.remove(); }, 180);
  }
  function openQuickSearch() {
    if (qsOpen) { closeQuickSearch(); return; }
    var veil = h("div", "qsveil");
    var input = h("input", "qsin"); input.type = "search"; input.placeholder = "Kino nomi, kodi, yili yoki janri..."; input.autocomplete = "off";
    input.setAttribute("aria-label", "Qidirish");
    var list = h("div", "qslist");
    var foot = h("button", "qsall hidden", "Barcha natijalar ↵"); foot.type = "button";
    var box = h("div", "qsbox", [h("div", "qshead", [icon("search"), input]), list, foot]);
    document.body.appendChild(veil); document.body.appendChild(box);
    var items = [], sel = -1, t = 0, my = 0;
    function paintSel() {
      Array.prototype.forEach.call(list.querySelectorAll(".qsrow"), function (r, i) { r.classList.toggle("on", i === sel); });
      var cur = list.querySelectorAll(".qsrow")[sel]; if (cur) cur.scrollIntoView({ block: "nearest" });
    }
    function pick(it) { closeQuickSearch(); openSheet(it); }
    function full() { var q = input.value.trim(); closeQuickSearch(); searchQ = q; show("search"); }
    function render(q) {
      list.replaceChildren(); sel = -1; foot.classList.toggle("hidden", !items.length);
      if (!items.length) { list.appendChild(h("div", "qsempty", q.length < 2 ? "Kamida 2 ta harf yozing" : "Hech narsa topilmadi")); return; }
      items.forEach(function (it, i) {
        var th = h("div", "qsth");
        var u = posterUrl(it, 360);
        if (u) { var im = new Image(); im.alt = ""; im.src = u; th.appendChild(im); } else th.appendChild(icon(CAT_ICON[it.cat] || "film"));
        var meta = [NAMES[it.cat] || "Kino", yr(it), it.genres && it.genres[0] ? it.genres[0].label : ""].filter(Boolean).join(" · ");
        var row = h("button", "qsrow", [th, h("div", "qstx", [h("b", null, it.title), h("span", null, meta)]), it.locked ? icon("lock") : null]);
        row.type = "button";
        row.onclick = function () { pick(it); };
        row.onmouseenter = function () { sel = i; paintSel(); };
        list.appendChild(row);
      });
    }
    function run() {
      var q = input.value.trim(), id = ++my;
      if (q.length < 2) { items = []; render(q); return; }
      api("/api/catalog?cat=video&sort=top&q=" + encodeURIComponent(q)).then(function (d) {
        if (id !== my || !qsOpen) return;
        items = d.ok ? d.items.slice(0, 6) : [];
        render(q);
      }).catch(function () {});
    }
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 160); });
    foot.onclick = full;
    var key = function (e) {
      if (e.key === "Escape") { e.stopPropagation(); closeQuickSearch(); }
      else if (e.key === "ArrowDown") { e.preventDefault(); if (items.length) { sel = (sel + 1) % items.length; paintSel(); } }
      else if (e.key === "ArrowUp") { e.preventDefault(); if (items.length) { sel = (sel - 1 + items.length) % items.length; paintSel(); } }
      else if (e.key === "Enter") { e.preventDefault(); if (sel >= 0 && items[sel]) pick(items[sel]); else if (input.value.trim().length >= 2) full(); }
    };
    document.addEventListener("keydown", key, true);
    veil.onclick = closeQuickSearch;
    qsOpen = { box: box, veil: veil, key: key };
    render("");
    requestAnimationFrame(function () { veil.classList.add("in"); box.classList.add("in"); input.focus(); });
  }
  // «/» tugmasi — qidiruvni ochadi (kompyuterda)
  document.addEventListener("keydown", function (e) {
    if (e.key !== "/" || window.innerWidth < 900 || /^(INPUT|TEXTAREA|SELECT)$/.test((document.activeElement || {}).tagName || "")) return;
    e.preventDefault(); openQuickSearch();
  });
