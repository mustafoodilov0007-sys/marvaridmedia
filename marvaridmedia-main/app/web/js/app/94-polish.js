  // ───── ✨ silliqlik: hamma tugmada vibratsiya, «pop» animatsiyalar, chetdan surib orqaga qaytish ─────
  (function () {
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    var origHaptic = haptic, lastHap = 0;
    haptic = function (kind) {
      var n = Date.now(); if (n - lastHap < 45) return; lastHap = n;
      try {
        if (tg && tg.HapticFeedback) { origHaptic(kind); return; }
        if (navigator.vibrate && !reduce && !IOS) navigator.vibrate(kind === "medium" ? 14 : 7);
      } catch (e) {}
    };
    var TAPS = "button, .card, .crow, .tab, .chip, .gchip, .nav button, a.card";
    document.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      var t = e.target && e.target.closest && e.target.closest(TAPS);
      if (t && !t.disabled) haptic("light");
    }, { passive: true, capture: true });

    // ❤️ saqlash / like / ovoz tugmalari bosilganda yumshoq «pop» (faqat transform)
    var POP = ".qb, .btn.sq, .smute, .short .sbtns button, .short .acts button, .rate button";
    document.addEventListener("click", function (e) {
      if (reduce) return;
      var t = e.target && e.target.closest && e.target.closest(POP);
      if (t) replayClass(t, "tap-pop");
    }, true);

    // 👈 chetdan surib orqaga qaytish (faqat brauzer o'zi bunday ishora bermaydigan joylarda: Mini App, iOS'da o'rnatilgan ilova)
    var EDGE = !PUB || APP || (STANDALONE && IOS) || /[?&]edge=1/.test(location.search);
    if (!EDGE) return;
    var ind = h("div", "edgeback", [icon("chev")]);
    document.body.appendChild(ind);
    var sx = 0, sy = 0, dx = 0, on = false;
    function canGoBack() { return !!(trailerOpen || sheetOpen || current !== "home"); }
    document.addEventListener("touchstart", function (e) {
      var t = e.touches[0]; on = false;
      if (e.touches.length !== 1 || t.clientX > 22 || !canGoBack()) return;
      sx = t.clientX; sy = t.clientY; dx = 0; on = true;
    }, { passive: true });
    document.addEventListener("touchmove", function (e) {
      if (!on) return;
      var t = e.touches[0]; dx = t.clientX - sx;
      if (Math.abs(t.clientY - sy) > Math.max(30, dx * 1.2)) { on = false; ind.style.transform = ""; ind.classList.remove("show"); return; }
      ind.classList.add("show");
      ind.style.transform = "translate3d(" + (Math.min(dx, 90) - 44) + "px,-50%,0)";
      ind.classList.toggle("ready", dx > 70);
    }, { passive: true });
    function end() {
      if (!on) return; on = false;
      var go = dx > 70;
      ind.classList.remove("show", "ready"); ind.style.transform = "";
      if (!go) return;
      haptic("medium");
      if (trailerOpen || sheetOpen) { goBack(); return; }
      if (HIST && history.state && history.length > 1) history.back(); else goBack();
    }
    document.addEventListener("touchend", end, { passive: true });
    document.addEventListener("touchcancel", function () { on = false; ind.classList.remove("show", "ready"); ind.style.transform = ""; }, { passive: true });
  })();
