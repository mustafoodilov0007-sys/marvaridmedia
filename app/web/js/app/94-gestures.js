  // ───── 👆 ishoralar: Shorts'da ikki marta bosish, oynani tortib yopish, yangilash uchun tortish, parallaks ─────

  // Telegram mini-ilovasida vertikal surish ilovani yopib qo'yadi — oyna ochiq paytda o'chirib turamiz
  function lockSwipes(on) {
    try { if (tg && (on ? tg.disableVerticalSwipes : tg.enableVerticalSwipes)) (on ? tg.disableVerticalSwipes : tg.enableVerticalSwipes)(); } catch (e) {}
  }

  // 10) Shorts: bir marta bosish — pauza, ikki marta — 👍 (yurak chiqadi)
  var lastTapT = 0, tapTimer = null;
  function tapShort(e, el, toggle, getLike) {
    var now = Date.now();
    if (now - lastTapT < 320) {
      clearTimeout(tapTimer); lastTapT = 0;
      var r = el.getBoundingClientRect(), hrt = h("div", "sheart", ["❤️"]);
      hrt.style.left = (e.clientX - r.left) + "px"; hrt.style.top = (e.clientY - r.top) + "px";
      el.appendChild(hrt); setTimeout(function () { hrt.remove(); }, 900);
      var lk = getLike && getLike();
      if (lk && !lk.classList.contains("on")) lk.onclick(); else haptic("light");
      return;
    }
    lastTapT = now;
    if (toggle) tapTimer = setTimeout(toggle, 280);
  }

  // 8) Kino oynasini pastga tortib yopish (telefonda), 11) tepasidagi fon sekinroq siljiydi
  (function () {
    var s = $("sheet"), sy = 0, sx = 0, dy = 0, dragging = false, tracking = false, t0 = 0, raf = 0;
    function parallax() {
      raf = 0;
      var bg = s.querySelector(".sheet-top .bg"); if (!bg) return;
      var y = Math.max(0, s.scrollTop);
      bg.style.transform = "translate3d(0," + (y * 0.42).toFixed(1) + "px,0) scale(" + (1 + Math.min(y, 240) / 900).toFixed(3) + ")";
    }
    s.addEventListener("scroll", function () { if (!raf && !REDUCE) raf = requestAnimationFrame(parallax); }, { passive: true });
    s.addEventListener("touchstart", function (e) {
      if (window.innerWidth >= 900 || e.touches.length !== 1) { tracking = false; return; }
      tracking = s.scrollTop <= 0; dragging = false; dy = 0;
      sy = e.touches[0].clientY; sx = e.touches[0].clientX; t0 = Date.now();
    }, { passive: true });
    s.addEventListener("touchmove", function (e) {
      if (!tracking) return;
      var y = e.touches[0].clientY - sy, x = e.touches[0].clientX - sx;
      if (!dragging) {
        if (y > 10 && Math.abs(y) > Math.abs(x) * 1.4 && s.scrollTop <= 0) { dragging = true; s.style.transition = "none"; }
        else if (y < -6 || s.scrollTop > 0) { tracking = false; return; }
        else return;
      }
      e.preventDefault();
      dy = Math.max(0, y);
      s.style.transform = "translateY(" + dy + "px)";
      $("veil").style.opacity = String(Math.max(0, 1 - dy / 420));
    }, { passive: false });
    function end() {
      if (!dragging) { tracking = false; return; }
      dragging = false; tracking = false;
      var fast = dy / Math.max(1, Date.now() - t0) > 0.6;
      s.style.transition = "";
      $("veil").style.opacity = "";
      if (dy > 100 || (fast && dy > 40)) { s.style.transform = ""; closeSheet(); haptic("light"); }
      else s.style.transform = "";            // joyiga prujinadek qaytadi
    }
    s.addEventListener("touchend", end, { passive: true });
    s.addEventListener("touchcancel", end, { passive: true });
  })();

  // 9) Yangilash uchun tepadan tortish (brauzer/o'rnatilgan ilovada; Telegram'da — vertikal surish o'chirilgan bo'lsa)
  (function () {
    if (!("ontouchstart" in window)) return;
    if (!PUB && !(tg && tg.isVerticalSwipesEnabled === false)) return;
    var ind = h("div", "ptr", [icon("refresh")]);
    document.body.appendChild(ind);
    document.documentElement.style.overscrollBehaviorY = "contain";
    var y0 = 0, x0 = 0, pull = 0, active = false, busy = false;
    var THRESH = 64;
    function ok() { return window.scrollY <= 0 && !sheetOpen && !busy && current !== "shorts" && !document.querySelector(".fdpanel.in, .trailer.on"); }
    document.addEventListener("touchstart", function (e) {
      active = ok() && e.touches.length === 1; pull = 0;
      if (active) { y0 = e.touches[0].clientY; x0 = e.touches[0].clientX; }
    }, { passive: true });
    document.addEventListener("touchmove", function (e) {
      if (!active) return;
      var dy = e.touches[0].clientY - y0, dx = e.touches[0].clientX - x0;
      if (dy < 0 || Math.abs(dx) > Math.abs(dy)) { if (pull === 0) active = false; return; }
      if (window.scrollY > 0) { active = false; return; }
      pull = Math.min(dy * 0.5, 96);
      ind.style.transition = "none";
      ind.style.opacity = String(Math.min(1, pull / 40));
      ind.style.transform = "translateY(" + pull + "px) rotate(" + (pull * 4) + "deg)";
      ind.classList.toggle("ready", pull >= THRESH);
    }, { passive: true });
    function release() {
      if (!active) return;
      active = false;
      ind.style.transition = "";
      if (pull >= THRESH) {
        busy = true; haptic("medium");
        ind.classList.add("spin"); ind.style.transform = "translateY(" + THRESH + "px)";
        show(current, Object.assign({}, curOpts, { nopush: true }));
        setTimeout(function () { ind.classList.remove("spin", "ready"); ind.style.opacity = "0"; ind.style.transform = ""; busy = false; }, 900);
      } else { ind.style.opacity = "0"; ind.style.transform = ""; ind.classList.remove("ready"); }
      pull = 0;
    }
    document.addEventListener("touchend", release, { passive: true });
    document.addEventListener("touchcancel", release, { passive: true });
  })();
