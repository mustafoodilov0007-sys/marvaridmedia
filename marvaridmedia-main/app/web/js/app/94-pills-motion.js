  // ───── ✨ mayda animatsiyalar: siljuvchi tablar, sevimlidan chiqarish, raqam sanalishi, tema ─────

  // 1) Tema almashganda: belgi aylanadi, ranglar 0.3 soniyada yumshoq o'tadi
  function themeFx() {
    var html = document.documentElement;
    html.classList.add("theming");
    var tb = $("bTheme"); if (tb) animOnce(tb, "spin", 550);
    setTimeout(function () { html.classList.remove("theming"); }, 420);
  }

  // 2) Tablar (.seg, .tb-tabs): tanlangan tugma ostidagi «tabletka» keyingisiga siljib boradi
  function pillPlace(c, first) {
    var pill = c._pill, on = c.querySelector("button.on");
    if (!pill) return;
    if (!on || !on.offsetWidth) { pill.style.opacity = "0"; return; }
    if (first) pill.classList.add("first");
    pill.style.width = on.offsetWidth + "px"; pill.style.height = on.offsetHeight + "px";
    pill.style.transform = "translate(" + on.offsetLeft + "px," + on.offsetTop + "px)";
    pill.style.opacity = "1";
    if (first) requestAnimationFrame(function () { requestAnimationFrame(function () { pill.classList.remove("first"); }); });
  }
  function pillSetup(c) {
    if (c._pill) return;
    var pill = document.createElement("i"); pill.className = "slidepill first";
    c.insertBefore(pill, c.firstChild); c._pill = pill; c.classList.add("pillbar");
    requestAnimationFrame(function () { pillPlace(c, true); });
    new MutationObserver(function () { pillPlace(c, false); }).observe(c, { subtree: true, attributes: true, attributeFilter: ["class"] });
    if (window.ResizeObserver) new ResizeObserver(function () { pill.classList.add("first"); pillPlace(c, false); requestAnimationFrame(function () { pill.classList.remove("first"); }); }).observe(c);
  }
  function pillScan(root) {
    if (root.nodeType !== 1) return;
    if (root.matches && root.matches(".seg, .tb-tabs")) pillSetup(root);
    Array.prototype.forEach.call(root.querySelectorAll ? root.querySelectorAll(".seg, .tb-tabs") : [], pillSetup);
  }
  new MutationObserver(function (ms) {
    ms.forEach(function (m) { Array.prototype.forEach.call(m.addedNodes, pillScan); });
  }).observe(document.body, { childList: true, subtree: true });
  pillScan(document.body);

  // 3) Sevimlilardan olib tashlangan karta kichrayib so'nadi, qolganlari joyini to'ldiradi
  function savedGone(it, removed) {
    if (current !== "saved") return;
    var c = document.querySelector('#view .card[data-id="' + it.id + '"]');
    if (!c) return;
    c.classList.toggle("unsaved", !!removed);
    if (removed && !sheetOpen) flushUnsaved();
  }
  function flushUnsaved() {
    if (current !== "saved") return;
    var gone = document.querySelectorAll("#view .card.unsaved");
    if (!gone.length) return;
    Array.prototype.forEach.call(gone, function (c) {
      c.classList.add("leaving");
      setTimeout(function () {
        c.remove();
        var left = document.querySelectorAll("#view .grid .card").length;
        if (!left) { renderSaved($("view")); return; }
        var lead = document.querySelector("#view .lead");
        if (lead) lead.textContent = lead.textContent.replace(/^\d+/, String(left));
      }, REDUCE ? 0 : 320);
    });
  }

  // 4) Raqamlar 0 dan sanalib chiqadi (ko'rishlar, foiz)
  function countUp(el, prefix, n, fmtFn, suffix) {
    fmtFn = fmtFn || String; suffix = suffix || "";
    el.textContent = prefix + fmtFn(n) + suffix;
    if (REDUCE || n < 8 || !window.requestAnimationFrame) return;
    var t0 = null, dur = 700;
    el.textContent = prefix + fmtFn(0) + suffix;
    function step(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = prefix + fmtFn(k < 1 ? Math.round(n * e) : n) + suffix;
      if (k < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
