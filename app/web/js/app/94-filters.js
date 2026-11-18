  // ───── 🎛 filtrlar: Davlat / Yil / Til — chiroyli ochiluvchi oyna (oddiy brauzer ro'yxati o'rniga) ─────
  var WIN = /Windows/i.test(navigator.userAgent || "");          // Windows bayroq emojilarini harf («US») qilib ko'rsatadi — u yerda olib tashlaymiz
  function cleanLabel(s) { s = String(s || ""); return WIN ? s.replace(/^[\u{1F1E6}-\u{1F1FF}]{2}\s*/u, "") : s; }
  var openDrop = null;
  function closeDrop() {
    if (!openDrop) return;
    var d = openDrop; openDrop = null;
    d.panel.classList.remove("in"); d.veil.classList.remove("in");
    d.btn.setAttribute("aria-expanded", "false");
    setTimeout(function () { d.panel.remove(); d.veil.remove(); }, 220);
    document.removeEventListener("keydown", d.key, true);
    try { d.btn.focus({ preventScroll: true }); } catch (e) {}
  }
  // fl: [kalit, sarlavha], opts: [{key,label,n}], value: tanlangan kalit, pick(kalit)
  function filterDrop(fl, opts, value, pick) {
    var cur = null;
    opts.forEach(function (o) { if (o.key === value) cur = o; });
    var isYear = fl[0] === "year", sortMode = fl[2] === "sort";          // saralash: «Hammasi» qatori va rangli holat yo'q
    var btn = h("button", "fpill fdbtn" + (value && !sortMode ? " on" : ""), [
      h("span", "fdl", fl[1]),
      cur ? h("b", null, cleanLabel(cur.label)) : null,
      icon("chev")]);
    btn.type = "button";
    btn.setAttribute("aria-haspopup", "listbox"); btn.setAttribute("aria-expanded", "false");
    btn.onclick = function () {
      if (openDrop && openDrop.btn === btn) { closeDrop(); return; }
      closeDrop(); haptic();
      var veil = h("div", "fdveil"), panel = h("div", "fdpanel" + (isYear ? " years" : ""));
      panel.setAttribute("role", "listbox"); panel.setAttribute("aria-label", fl[1]);
      var head = h("div", "fdhead", [h("b", null, fl[1].replace(/^[^\p{L}\p{N}]+/u, "")), (function () {
        var x = h("button", "fdx", [icon("x")]); x.type = "button"; x.setAttribute("aria-label", "Yopish"); x.onclick = closeDrop; return x; })()]);
      panel.appendChild(h("div", "fdgrip"));
      panel.appendChild(head);
      var q = null;
      if (!isYear && opts.length > 8) {
        q = h("input", "fdq"); q.type = "search"; q.placeholder = "Qidirish..."; q.autocomplete = "off";
        panel.appendChild(q);
      }
      var list = h("div", "fdlist");
      function row(key, label, n) {
        var on = key === (value || "") && (!sortMode || key !== "");
        var b = h("button", "fdo" + (on ? " on" : ""), [h("span", "fdn", label), n != null ? h("i", null, String(n)) : null, on ? icon("check") : null]);
        b.type = "button"; b.setAttribute("role", "option"); b.setAttribute("aria-selected", on ? "true" : "false"); b.dataset.k = key;
        b.onclick = function () { closeDrop(); if (key !== (value || "")) pick(key); };
        return b;
      }
      function fill(term) {
        list.replaceChildren();
        if (!sortMode) list.appendChild(row("", "Hammasi", null));
        var t = (term || "").trim().toLowerCase(), any = false;
        opts.forEach(function (o) {
          var lb = cleanLabel(o.label);
          if (t && lb.toLowerCase().indexOf(t) < 0) return;
          any = true; list.appendChild(row(o.key, lb, o.n));
        });
        if (!any) list.appendChild(h("div", "fdempty", "Topilmadi"));
      }
      fill("");
      if (q) q.oninput = function () { fill(q.value); };
      panel.appendChild(list);
      document.body.appendChild(veil); document.body.appendChild(panel);
      // joylashuv: keng ekranda — tugma tagida, telefonda — pastdan chiqadi
      if (window.innerWidth >= 700) {
        var r = btn.getBoundingClientRect(), w = isYear ? 300 : 280;
        panel.style.width = w + "px";
        panel.style.left = Math.max(12, Math.min(innerWidth - w - 12, r.left)) + "px";
        var below = innerHeight - r.bottom - 16, top = r.bottom + 8, mh = Math.min(380, below);
        if (below < 220 && r.top > below) { mh = Math.min(380, r.top - 24); panel.style.top = "auto"; panel.style.bottom = (innerHeight - r.top + 8) + "px"; }
        else panel.style.top = top + "px";
        panel.style.maxHeight = Math.max(200, mh) + "px";
        panel.classList.add("pop");
      }
      var d = { btn: btn, panel: panel, veil: veil, key: function (e) { if (e.key === "Escape") { e.stopPropagation(); closeDrop(); } } };
      openDrop = d;
      document.addEventListener("keydown", d.key, true);
      veil.onclick = closeDrop;
      btn.setAttribute("aria-expanded", "true");
      requestAnimationFrame(function () {
        veil.classList.add("in"); panel.classList.add("in");
        var on = list.querySelector(".on"); if (on && on.dataset.k) on.scrollIntoView({ block: "center" });
        if (q && window.innerWidth >= 700) { try { q.focus({ preventScroll: true }); } catch (e) {} }
      });
    };
    return btn;
  }
