  // ───── ▶ pleyer: kinoni shu yerning o'zida ko'rish ─────
  var playerOpen = false, plRoot = null, plKeyHandler = null, plPopped = false;
  function posKey(id, no) { return "pos:" + id + ":" + no; }
  function fmtClock(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    var hh = Math.floor(sec / 3600), mm = Math.floor(sec % 3600 / 60), ss = sec % 60;
    return (hh ? hh + ":" + String(mm).padStart(2, "0") : mm) + ":" + String(ss).padStart(2, "0");
  }
  function openPlayer(it) {
    if (playerOpen) return;
    toast("⏳ Yuklanmoqda...");
    api("/api/playinfo?id=" + it.id).then(function (d) {
      if (!d.ok || !d.parts || !d.parts.length) { toast("😔 Bu kino hozircha ko'rsatilmaydi"); return; }
      startPlayer(it, d.parts);
    }).catch(function () { toast("⚠️ Ulanishda xatolik. Qaytadan urinib ko'ring."); });
  }
  function startPlayer(it, parts) {
    if (playerOpen) return;
    if (sheetOpen) closeSheet();
    stopHero();
    playerOpen = true; window.__playerOpen = true;
    var cur = 0, idleT = 0, counted = false, lastSave = 0, retried = false;
    // oxirgi ko'rilgan qismdan davom ettiramiz
    for (var i = parts.length - 1; i >= 0; i--) { if (+store.get(posKey(it.id, parts[i].no)) > 10) { cur = i; break; } }

    var v = document.createElement("video");
    v.setAttribute("playsinline", ""); v.playsInline = true; v.controls = true; v.preload = "metadata";
    v.setAttribute("controlsList", "nodownload");
    if (it.poster) v.poster = posterUrl(it);
    var msg = h("div", "wp-msg");
    var closeBtn = h("button", "ibtn wp-close", [icon("chev")]);
    closeBtn.setAttribute("aria-label", "Yopish"); closeBtn.querySelector("svg").style.transform = "rotate(180deg)";
    var titleEl = h("b", null, it.title), subEl = h("span", null, "");
    var spd = h("button", "ibtn wp-spd", "1×"); spd.setAttribute("aria-label", "Tezlik");
    var pip = h("button", "ibtn wp-pip", [icon("film")]); pip.setAttribute("aria-label", "Kichik oyna");
    var top = h("div", "wp-top", [closeBtn, h("div", "wp-title", [titleEl, subEl]), spd]);
    if (document.pictureInPictureEnabled) top.appendChild(pip);
    var stage = h("div", "wp-stage", [v, msg]);
    var eps = h("div", "wp-eps");
    plRoot = h("div", "wp", [top, stage, eps]);
    plRoot.setAttribute("role", "dialog"); plRoot.setAttribute("aria-modal", "true"); plRoot.setAttribute("aria-label", it.title);
    document.body.appendChild(plRoot);
    document.body.classList.add("wp-on");
    try { history.pushState({ wp: 1 }, ""); plPopped = false; } catch (e) {}

    function save() {
      var p = parts[cur];
      if (!p || !v.duration || !isFinite(v.duration)) return;
      var t = v.currentTime;
      if (t > 10 && t < v.duration - 30) store.set(posKey(it.id, p.no), String(Math.floor(t))); else store.set(posKey(it.id, p.no), "");
    }
    function paintEps() {
      eps.replaceChildren();
      if (parts.length < 2) return;
      parts.forEach(function (p, k) {
        var seen = +store.get(posKey(it.id, p.no)) > 10;
        var b = h("button", "wp-ep" + (k === cur ? " on" : "") + (seen ? " seen" : ""), p.no + "-qism");
        b.onclick = function () { if (k !== cur) { save(); load(k, true); } };
        eps.appendChild(b);
      });
      var on = eps.querySelector(".on"); if (on && on.scrollIntoView) on.scrollIntoView({ inline: "center", block: "nearest" });
    }
    function showMsg(text, retry) {
      msg.replaceChildren(h("div", null, text));
      if (retry) { var b = h("button", "btn primary", "Qayta urinish"); b.onclick = retry; msg.appendChild(b); }
      msg.classList.add("on");
    }
    function load(k, autoplay) {
      cur = k; counted = false;
      var p = parts[cur];
      msg.classList.remove("on");
      subEl.textContent = parts.length > 1 ? p.no + "-qism" : (p.duration ? fmtClock(p.duration) : "");
      v.src = p.url;
      var start = +store.get(posKey(it.id, p.no)) || 0;
      v.onloadedmetadata = function () {
        if (start > 10 && v.duration && start < v.duration - 30) { try { v.currentTime = start; } catch (e) {} toast("⏪ " + fmtClock(start) + " dan davom etamiz"); }
        start = 0;
      };
      var pr = v.play(); if (pr && pr.catch) pr.catch(function () {});
      paintEps();
    }
    v.addEventListener("playing", function () {
      msg.classList.remove("on");
      if (!counted) { counted = true; api("/api/played", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: it.id }) }).catch(function () {}); }
    });
    v.addEventListener("timeupdate", function () { var n = Date.now(); if (n - lastSave > 4000) { lastSave = n; save(); } });
    v.addEventListener("pause", save);
    v.addEventListener("waiting", function () { if (plRoot) plRoot.classList.add("buf"); });
    v.addEventListener("canplay", function () { if (plRoot) plRoot.classList.remove("buf"); });
    v.addEventListener("ended", function () {
      store.set(posKey(it.id, parts[cur].no), "");
      if (cur + 1 < parts.length) { toast("▶ Keyingi qism"); load(cur + 1, true); } else { paintEps(); showMsg("Tomosha tugadi. Yoqdimi? 🍿"); }
    });
    v.addEventListener("error", function () {   // havola muddati o'tgan bo'lishi mumkin — bir marta yangisini olamiz
      if (!retried) {
        retried = true;
        api("/api/playinfo?id=" + it.id).then(function (d) {
          if (d.ok) { parts = d.parts; var t = v.currentTime; store.set(posKey(it.id, parts[cur].no), String(Math.floor(t))); load(cur, true); }
          else showMsg("⚠️ Videoni yuklab bo'lmadi", function () { retried = false; load(cur, true); });
        }).catch(function () { showMsg("⚠️ Internet yo'q yoki video topilmadi", function () { retried = false; load(cur, true); }); });
      } else showMsg("⚠️ Videoni yuklab bo'lmadi", function () { retried = false; load(cur, true); });
    });
    // tezlik, kichik oyna
    var SPEEDS = [1, 1.25, 1.5, 2, 0.75], si = 0;
    spd.onclick = function () { si = (si + 1) % SPEEDS.length; v.playbackRate = SPEEDS[si]; spd.textContent = SPEEDS[si] + "×"; };
    pip.onclick = function () { try { if (document.pictureInPictureElement) document.exitPictureInPicture(); else v.requestPictureInPicture(); } catch (e) {} };
    // boshqaruv paneli harakatsizlikda yashirinadi
    var root = plRoot;
    function wake() {
      if (!root.isConnected) return;
      root.classList.remove("idle"); clearTimeout(idleT);
      idleT = setTimeout(function () { if (root.isConnected && !v.paused) root.classList.add("idle"); }, 3200);
    }
    ["mousemove", "touchstart", "click", "keydown"].forEach(function (ev) { root.addEventListener(ev, wake, { passive: true }); });
    v.addEventListener("pause", wake); wake();
    // klaviatura: bo'shliq/K — to'xtatish, ←/→ — 10 soniya, F — to'liq ekran, M — ovoz, N — keyingi qism
    plKeyHandler = function (e) {
      if (!playerOpen || e.target.closest && e.target.closest("input, textarea, select")) return;
      var k = e.key;
      if (k === " " || k === "k" || k === "K") { e.preventDefault(); if (v.paused) v.play(); else v.pause(); }
      else if (k === "ArrowRight") { e.preventDefault(); v.currentTime = Math.min((v.duration || 1e9), v.currentTime + 10); }
      else if (k === "ArrowLeft") { e.preventDefault(); v.currentTime = Math.max(0, v.currentTime - 10); }
      else if (k === "f" || k === "F") { try { if (document.fullscreenElement) document.exitFullscreen(); else plRoot.requestFullscreen(); } catch (x) {} }
      else if (k === "m" || k === "M") { v.muted = !v.muted; }
      else if ((k === "n" || k === "N") && cur + 1 < parts.length) { save(); load(cur + 1, true); }
    };
    document.addEventListener("keydown", plKeyHandler);
    closeBtn.onclick = function () { closePlayer(); };
    load(cur, true);
    setTimeout(function () { try { closeBtn.focus({ preventScroll: true }); } catch (e) {} }, 100);
    plRoot._save = save;
  }
  function closePlayer(fromPop) {
    if (!playerOpen) return;
    playerOpen = false; window.__playerOpen = false;
    try { if (plRoot._save) plRoot._save(); } catch (e) {}
    var v = plRoot.querySelector("video");
    if (v) { try { v.pause(); v.removeAttribute("src"); v.load(); } catch (e) {} }
    try { if (document.fullscreenElement) document.exitFullscreen(); } catch (e) {}
    var gone = plRoot; plRoot = null; gone.remove();
    document.body.classList.remove("wp-on");
    document.removeEventListener("keydown", plKeyHandler);
    if (!fromPop && history.state && history.state.wp) { plPopped = true; try { history.back(); } catch (e) {} }
    if (current === "home") restartHero();
  }
  window.addEventListener("popstate", function () { if (playerOpen && !plPopped) closePlayer(true); plPopped = false; });
