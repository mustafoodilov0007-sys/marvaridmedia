  // ───── 📺 Marvarid TV: kunlik «efir» jadvali (kutubxonadagi kinolardan) ─────
  var tvData = null, tvLock = null, tvOff = 0, tvFetchedAt = 0, tvP = null;
  function tvNow() { return Date.now() / 1000 + tvOff; }
  function tvHM(ts) {      // Toshkent vaqti (UTC+5), qurilma vaqt mintaqasidan qat'i nazar
    var d = new Date((ts + 5 * 3600) * 1000);
    return (d.getUTCHours() < 10 ? "0" : "") + d.getUTCHours() + ":" + (d.getUTCMinutes() < 10 ? "0" : "") + d.getUTCMinutes();
  }
  function tvLeft(sec) {
    sec = Math.max(0, Math.round(sec));
    var hh = Math.floor(sec / 3600), mm = Math.floor(sec % 3600 / 60);
    if (hh) return hh + " soat " + mm + " daqiqa";
    return Math.max(1, mm) + " daqiqa";
  }
  function tvLoad(force) {
    if (tvP) return tvP;
    if (!force && (tvData || tvLock) && Date.now() - tvFetchedAt < 120000) return Promise.resolve(tvData);
    tvP = api("/api/tv").then(function (d) {
      tvP = null;
      if (!d || !d.ok) return tvData;
      tvOff = d.now - Date.now() / 1000;
      tvFetchedAt = Date.now();
      tvLock = d.locked ? d : null;          // Premium'siz foydalanuvchi: yopiq holat (sinov taklif qilinadi)
      tvData = !d.locked && d.slots && d.slots.length ? d : null;
      return tvData;
    }).catch(function () { tvP = null; return tvData; });
    return tvP;
  }
  // hozirgi holat: efirdagi slot (live) yoki navbatdagi (soon), keyingisi
  function tvState() {
    if (!tvData || !tvData.slots) return null;
    var t = tvNow(), sl = tvData.slots, i, live = -1, nxt = -1;
    for (i = 0; i < sl.length; i++) {
      if (sl[i].s <= t && t < sl[i].e) { live = i; break; }
      if (sl[i].s > t) { nxt = i; break; }
    }
    if (live < 0 && nxt < 0) return null;           // jadval tugadi — yangisi olinadi
    var idx = live >= 0 ? live : nxt;
    return { live: live >= 0, i: idx, cur: sl[idx], next: sl[idx + 1] || null, t: t };
  }
  function tvStale() {       // jadvalda 2 tadan kam kelajak slot qoldi yoki tugab bo'ldi — yangilash kerak
    if (!tvData) return true;
    var t = tvNow(), n = 0;
    tvData.slots.forEach(function (s) { if (s.s > t) n++; });
    return n < 2;
  }
  function tvProgress(st) { return st.live ? Math.max(0, Math.min(1, (st.t - st.cur.s) / (st.cur.e - st.cur.s))) : 0; }

  // bosh sahifadagi karta
  function tvHomeCard() {
    var box = h("button", "tvcard hidden");
    box.type = "button";
    box.onclick = function () { haptic(); show("tv"); };
    function paint() {
      if (tvLock) {
        var pic0 = h("div", "poster tvlockpic", [icon("lock")]);
        box.replaceChildren(pic0, h("div", "tvinfo", [h("small", null, "MARVARID TV · PREMIUM"), h("b", null, "Kunlik efir jadvali"),
          h("em", null, tvLock.trial_days ? "🎁 " + tvLock.trial_days + " kun bepul — sinab ko'ring" : "Premium egalari uchun")]));
        box.classList.remove("hidden");
        return;
      }
      var st = tvState();
      if (!st) { box.classList.add("hidden"); return; }
      var it = st.cur.it;
      var pic = posterNode(it, 360);
      if (st.live) pic.appendChild(h("span", "livebadge", [h("i"), "JONLI"]));
      var bar = h("div", "tvbar", [h("i")]);
      bar.firstChild.style.width = Math.round(tvProgress(st) * 100) + "%";
      var info = [h("small", null, "MARVARID TV · " + (st.live ? "HOZIR EFIRDA" : "TEZ ORADA")), h("b", null, it.title),
        h("div", "tvtime", [h("span", null, tvHM(st.cur.s) + " – " + tvHM(st.cur.e)), st.live ? bar : null])];
      if (st.next) info.push(h("em", null, "Keyingisi " + tvHM(st.next.s) + " da: " + st.next.it.title));
      box.replaceChildren(pic, h("div", "tvinfo", info));
      box.classList.remove("hidden");
    }
    tvLoad(false).then(function () { paint(); });
    var timer = setInterval(function () {
      if (!document.body.contains(box)) { clearInterval(timer); return; }
      if (!tvLock && tvStale()) tvLoad(true).then(paint); else paint();
    }, 30000);
    return box;
  }

  // efir oynasi: treyleri bor kino efirda bo'lsa — treyler ekranda o'ynaydi (admin shorts videosi yoki YouTube), aks holda poster
  function tvStage(it, st) {
    var box = h("div", "tvstage");
    var hero = posterNode(it, 720);
    hero.classList.add("tvhero");
    hero.onclick = function () { haptic(); openSheet(it); };
    box.appendChild(hero);
    var yid = !it.trailer && it.turl && typeof youtubeId === "function" ? youtubeId(it.turl) : null;
    if (!st.live || !(it.trailer || yid)) return box;
    var elapsed = Math.max(0, st.t - st.cur.s);
    var wrap = h("div", "tvplayer");
    if (it.trailer) {
      var v = document.createElement("video");
      v.muted = true; v.defaultMuted = true; v.loop = true; v.autoplay = true; v.playsInline = true;
      v.setAttribute("playsinline", ""); v.setAttribute("muted", ""); v.preload = "auto";
      v.src = "/media/short/" + it.trailer;
      v.addEventListener("loadedmetadata", function () {        // «jonli» his: hamma efirning bir joyida turadi
        if (v.duration && isFinite(v.duration)) { try { v.currentTime = elapsed % v.duration; } catch (e) {} }
      });
      v.addEventListener("playing", function () { wrap.classList.add("on"); });
      v.addEventListener("error", function () { wrap.remove(); });     // treyler yuklanmasa — poster qoladi
      var snd = h("button", "tvsound", [icon("mute")]);
      snd.setAttribute("aria-label", "Ovoz");
      snd.onclick = function (e) { e.stopPropagation(); haptic(); v.muted = !v.muted; snd.replaceChildren(icon(v.muted ? "mute" : "vol")); if (!v.muted) { var pr = v.play(); if (pr && pr.catch) pr.catch(function () {}); } };
      wrap.appendChild(v); wrap.appendChild(snd);
      var pl = v.play(); if (pl && pl.catch) pl.catch(function () {});
    } else {
      var fr = document.createElement("iframe");
      fr.src = "https://www.youtube-nocookie.com/embed/" + yid + "?autoplay=1&mute=1&loop=1&playlist=" + yid + "&rel=0&playsinline=1&modestbranding=1";
      fr.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen"; fr.allowFullscreen = true;
      fr.setAttribute("title", it.title + " — treyler");
      fr.onload = function () { wrap.classList.add("on"); };
      wrap.appendChild(fr);
    }
    wrap.appendChild(h("span", "tvpill", [h("i"), "TREYLER"]));
    box.appendChild(wrap);
    return box;
  }

  // TV sahifasi
  function renderTV(view, my) {
    var page = h("div", "page tvpage");
    var live = h("div", "tvlive");
    var prog = h("div", "tvprog");
    page.appendChild(h("h1", null, [h("span", "tvlogo", [icon("live")]), "Marvarid TV"]));
    page.appendChild(h("p", "lead", "Kunlik efir jadvali — hozir nima ko'rsatilayotganini bilib oling"));
    page.appendChild(live);
    page.appendChild(h("h2", "tvh", "Dastur"));
    page.appendChild(prog);
    live.appendChild(h("div", "tvsk"));
    view.replaceChildren(page);
    var scrolled = false, timer = null;
    var stageNode = null, bodyNode = h("div", "tvbodywrap"), stageKey = "";

    function row(sl, st) {
      var it = sl.it, on = st && st.live && st.cur === sl, nx = st && st.next === sl;
      var past = sl.e <= tvNow();
      var tag = on ? h("span", "tvtag live", [h("i"), "Efirda"]) : (nx || (st && !st.live && st.cur === sl) ? h("span", "tvtag next", "Keyingisi") : null);
      var meta = h("span", "tvmeta", [it.premium ? icon("gem") : null, [it.genres && it.genres.length ? it.genres.slice(0, 2).map(gname).join(", ") : (NAMES[it.cat] || ""),
        it.year ? yr(it) : ""].filter(Boolean).join(" · ")]);
      var b = h("button", "tvrow" + (on ? " on" : "") + (past ? " past" : ""), [
        h("time", null, tvHM(sl.s)), posterNode(it, 360),
        h("div", "tvri", [h("b", null, it.title), h("div", null, [tag, meta])])]);
      b.type = "button";
      b.onclick = function () { haptic(); openSheet(it, false, b.querySelector(".poster")); };
      return b;
    }
    function lockView() {
      var d = tvLock, act;
      var msg = h("p", null, "Marvarid TV — kunlik efir jadvali, faqat Premium egalari uchun.");
      if (d.trial_days) {
        act = h("button", "tvgo", [icon("play"), "🎁 " + d.trial_days + " kunni bepul olish"]);
        act.onclick = function () {
          haptic(); act.disabled = true;
          api("/api/tv/trial", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then(function (r) {
            if (r && r.ok) { toast("🎁 " + r.days + " kunlik Premium faollashdi"); notify("success"); tvLock = null; tvLoad(true).then(function () { if (my === reqId) { scrolled = false; start(); } }); }
            else { act.disabled = false; toast(r && r.reason === "used" ? "Sinov allaqachon olingan" : "⚠️ Hozir imkoni yo'q"); }
          }).catch(function () { act.disabled = false; toast("⚠️ Ulanishda xatolik"); });
        };
      } else if (d.guest) {
        act = h("button", "tvgo", [icon("user"), "Hisobga kirish"]);
        act.onclick = function () { haptic(); show("login"); };
        msg = h("p", null, "Marvarid TV — Premium egalari uchun. Kirib, bepul sinov kunini oling.");
      } else {
        act = h("button", "tvgo", [icon("gem"), "Premium olish"]);
        act.onclick = function () { haptic(); show("sub"); };
      }
      var more = d.trial_days ? h("button", "tvmore", [icon("gem"), "Premium"]) : null;
      if (more) more.onclick = function () { haptic(); show("sub"); };
      stageKey = ""; stageNode = null;
      live.replaceChildren(h("div", "tvlock", [h("span", "tvlogo big", [icon("live")]), h("h2", null, "Marvarid TV — Premium"), msg,
        h("div", "tvbtns", [act, more])]));
      prog.replaceChildren();
    }
    function paint() {
      if (my !== reqId) { clearInterval(timer); return; }
      if (tvLock) { lockView(); return; }
      var st = tvState();
      if (!st) {
        stageKey = ""; stageNode = null;
        live.replaceChildren(emptyBox("tv", "Hozircha efir yo'q", "Kinolar qo'shilishi bilan jadval paydo bo'ladi."));
        prog.replaceChildren();
        return;
      }
      var it = st.cur.it, pct = Math.round(tvProgress(st) * 100);
      var go = h("button", "tvgo", [icon(it.locked ? "lock" : "play"), it.locked ? "Premium" : (PUB && it.cat !== "music" ? "Telegramda ko'rish" : "Ko'rish")]);
      go.onclick = function () { haptic(); watch(it, go); };
      var more = h("button", "tvmore", [icon("info"), "Film haqida"]);
      more.onclick = function () { haptic(); openSheet(it); };
      var bar = h("div", "tvbar big", [h("i")]);
      bar.firstChild.style.width = pct + "%";
      var bits = [it.year ? yr(it) : "", it.genres && it.genres.length ? it.genres.slice(0, 2).map(gname).join(", ") : "",
        it.age ? it.age + "+" : "", it.imdb ? "IMDb " + it.imdb : ""].filter(Boolean).join(" · ");
      var nextBox = null;
      if (st.next) {
        nextBox = h("button", "tvnext", [posterNode(st.next.it, 360), h("div", null, [h("small", null, "Keyingisi · " + tvHM(st.next.s)), h("b", null, st.next.it.title)])]);
        nextBox.type = "button";
        nextBox.onclick = function () { haptic(); openSheet(st.next.it); };
      }
      var key = it.id + ":" + st.cur.s + ":" + (st.live ? 1 : 0);      // efir oynasi (video/iframe) faqat kino yoki holat o'zgarganda yangilanadi
      if (key !== stageKey || !stageNode || stageNode.parentNode !== live) {
        stageKey = key;
        stageNode = tvStage(it, st);
        live.replaceChildren(stageNode, bodyNode);
      }
      bodyNode.replaceChildren(h("div", "tvbody", [
        h("div", "tvkick", [st.live ? h("span", "tvtag live", [h("i"), "HOZIR EFIRDA"]) : h("span", "tvtag next", "TEZ ORADA"), h("span", null, st.cur.b)]),
        h("h2", null, it.title), h("div", "tvbits", bits),
        h("div", "tvtime", [h("span", null, tvHM(st.cur.s)), st.live ? bar : h("div", "tvbar big"), h("span", null, tvHM(st.cur.e))]),
        h("p", "tvleft", st.live ? "Yana " + tvLeft(st.cur.e - st.t) : tvHM(st.cur.s) + " da boshlanadi · " + tvLeft(st.cur.s - st.t) + " qoldi"),
        h("div", "tvbtns", [go, more]), nextBox]));
      // jadval: kun bo'laklari bo'yicha
      var frag = [], lastB = "", t0 = tvNow() - 3 * 3600;
      tvData.slots.forEach(function (sl) {
        if (sl.e < t0) return;                       // 3 soatdan ko'p o'tib ketganlar ko'rsatilmaydi
        if (sl.b !== lastB) { lastB = sl.b; frag.push(h("div", "tvblock", sl.b)); }
        frag.push(row(sl, st));
      });
      prog.replaceChildren.apply(prog, frag);
      if (!scrolled) {
        scrolled = true;
        var onr = prog.querySelector(".tvrow.on");
        if (onr) setTimeout(function () { try { onr.scrollIntoView({ block: "center", behavior: "auto" }); window.scrollTo(0, 0); } catch (e) {} }, 0);
      }
    }
    function start() {
      if (my !== reqId) return;
      paint();
      clearInterval(timer);
      timer = setInterval(function () {
        if (my !== reqId || !document.body.contains(page)) { clearInterval(timer); return; }
        if (!tvLock && tvStale()) tvLoad(true).then(paint); else paint();
      }, 20000);
    }
    tvLoad(true).then(start);
  }
