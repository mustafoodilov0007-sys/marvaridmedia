  // ───── kartochkalar ─────
  function posterNode(it, w) {
    var box = h("div", "poster");
    var ph = h("div", "ph", [icon(CAT_ICON[it.cat] || "film"), h("span", null, it.title)]);
    var x = hue(it.title || "");
    ph.style.setProperty("--c1", "hsl(" + (24 + x % 22) + "," + (42 + x % 20) + "%," + (30 + x % 12) + "%)");
    ph.style.setProperty("--c2", "hsl(" + (20 + x % 15) + ",25%,8%)");
    box.appendChild(ph);
    var url = posterUrl(it, w || 360);
    if (url) {
      var img = new Image();
      img.alt = ""; img.loading = "lazy"; img.decoding = "async";
      img.onload = function () { img.classList.add("ok"); ph.remove(); };
      img.onerror = function () { img.remove(); };   // rasm yuklanmasa — rangli joy egasi qoladi
      img.src = url;
      box.appendChild(img);
    }
    return box;
  }
  function quickView(it) {      // faqat sichqonchali qurilmada (hover) ko'rinadi; asosiy tugmaning ichida EMAS
    var info = [];
    var sc = score(it);
    if (sc !== null) info.push("👍 " + sc + "%");
    if (it.genres && it.genres.length) info.push(it.genres.slice(0, 2).map(gname).join(", "));
    var qv = h("div", "qv");
    qv.appendChild(h("div", "qv-info", info.join(" · ") || (it.desc ? it.desc.slice(0, 70) : NAMES[it.cat] || "")));
    var row = h("div", "qv-row");
    var go = h("button", "qb main", [icon(it.locked ? "lock" : "play")]);
    go.setAttribute("aria-label", (it.locked ? "Premium: " : "Ko'rish: ") + it.title);
    go.onclick = function (e) { e.stopPropagation(); watch(it, go); };
    var bm = h("button", "qb" + (isSaved(it) ? " on" : ""), [icon("bookmark")]);
    bm.setAttribute("aria-label", "Saqlash: " + it.title);
    bm.onclick = function (e) { e.stopPropagation(); bm.classList.toggle("on", toggleSaved(it)); popBtn(bm); };
    var more = h("button", "qb", [icon("info")]);
    more.setAttribute("aria-label", "Batafsil: " + it.title);
    more.onclick = function (e) { e.stopPropagation(); openSheet(it); };
    row.appendChild(go); row.appendChild(bm); row.appendChild(more);
    qv.appendChild(row);
    return h("div", "qvwrap", [qv]);
  }
  function card(it) {
    var b = h("div", "card");
    var main = h("button", "cmain");
    main.type = "button";
    var p = posterNode(it);
    if (it.parts > 1) p.appendChild(h("span", "tag l", it.parts + " qism"));
    if (it.premium) p.appendChild(h("span", "tag r", "PREMIUM"));
    var qlt = topQuality(it), lc = langCode(it);
    if (qlt) p.appendChild(h("span", "tag bl", qlt));
    if (lc) p.appendChild(h("span", "tag br", lc));
    main.appendChild(p);
    main.appendChild(h("div", "t", it.title));
    main.appendChild(h("div", "m", shortMeta(it)));
    b.appendChild(main);
    b._item = it;
    b.dataset.id = it.id;
    var activate;
    if (it.cat === "music") {
      p.appendChild(h("span", "eq", [h("i"), h("i"), h("i")]));
      if (Player.current && Player.current.id === it.id) b.classList.add("playing");
      activate = function () { Player.playFrom(it, b); };
    } else {
      if (HOVER) b.appendChild(quickView(it));
      activate = function () { openSheet(it, false, b.querySelector(".poster")); };
    }
    b.onclick = activate;      // tugma bosilganda ham, kartochkaning o'zi bosilganda ham ishlaydi
    return b;
  }
  function skeletonCards(n) {
    var out = [];
    for (var i = 0; i < n; i++) {
      var c = h("div", "card", [h("div", "poster sk"), h("div", "t sk", " ")]);
      c.style.pointerEvents = "none";
      out.push(c);
    }
    return out;
  }
  function emptyBox(ic, title, text) {
    var big = h("div", "big", [icon(ic)]);
    return h("div", "empty", [big, h("b", null, title), text]);
  }

  // ───── hero karusel ─────
  var heroTimer = null, heroIdx = 0, heroItems = [], HERO_MS = 6500;
  function heroView(items) {
    heroItems = items;
    var wrap = h("section", "hero");
    wrap.setAttribute("aria-roledescription", "karusel");
    wrap.setAttribute("aria-label", "Yangi qo'shilgan kinolar");
    if (!items.length) {
      var s = h("div", "slide on", [h("div", "bg ph"), h("div", "ph-icon", [icon("film")]), h("div", "shade")]);
      s.appendChild(h("div", "hero-body", [h("h1", "hero-title", "Tez orada"),
        h("div", "hsub", "Yangi kinolar va multfilmlar shu yerda chiqadi")]));
      wrap.appendChild(s);
      return wrap;
    }
    items.forEach(function (it, i) {
      var bg = h("div", "bg" + (it.poster ? "" : " ph"));
      if (it.poster) bg.style.backgroundImage = "url('" + posterUrl(it, 720) + "')";
      var s = h("div", "slide" + (i === 0 ? " on" : ""), [bg]);
      s.setAttribute("aria-hidden", i === 0 ? "false" : "true");
      if (i !== 0) s.inert = true;
      if (it.poster) {   // keng ekranda — o'tkir poster kartasi (orqa fon xira)
        var hp = h("div", "hp");
        var im = new Image(); im.alt = ""; im.decoding = "async"; im.src = posterUrl(it, 720);
        hp.appendChild(im);
        s.appendChild(hp);
      } else {
        s.appendChild(h("div", "ph-icon", [icon(CAT_ICON[it.cat] || "film")]));
      }
      s.appendChild(h("div", "shade"));
      var badges = h("div", "badges");
      badges.appendChild(h("span", "badge", i === 0 ? "YANGI" : "TAVSIYA"));
      if (it.premium) badges.appendChild(h("span", "badge gold", "PREMIUM"));
      if (it.parts > 1) badges.appendChild(h("span", "badge glass", it.parts + " qism"));
      var qlt = topQuality(it); if (qlt) badges.appendChild(h("span", "badge glass", qlt));
      var lc = langCode(it); if (lc) badges.appendChild(h("span", "badge glass", lc));
      var meta = metaNode(it);
      var body = h("div", "hero-body", [badges, h("h2", "hero-title", it.title), meta, ratingBadges(it)]);
      body.appendChild(actionRow(it, true));
      s.appendChild(body);
      s.classList.add("tap");          // posterga bosilsa — tafsilot (izoh shu yerda chiqadi)
      s.onclick = function (e) {
        if (e.target.closest("button, a")) return;
        haptic();
        var hpEl = s.querySelector(".hp"), src = hpEl && getComputedStyle(hpEl).display !== "none" ? hpEl : s.querySelector(".bg:not(.ph)");
        openSheet(it, false, src);
      };
      wrap.appendChild(s);
    });
    if (items.length > 1) {
      var nav = h("div", "hnav");
      items.forEach(function (_, k) {
        var d = h("button", "dot" + (k === 0 ? " on" : ""), [h("i")]);
        d.setAttribute("aria-label", (k + 1) + "-slayd");
        d.onclick = function (e) { e.stopPropagation(); goSlide(k); restartHero(); };
        nav.appendChild(d);
      });
      wrap.appendChild(nav);
      [["l", "chev", -1, "Oldingi"], ["r", "chev", 1, "Keyingi"]].forEach(function (a) {
        var ar = h("button", "harrow " + a[0], [icon(a[1])]);
        ar.setAttribute("aria-label", a[3]);
        ar.onclick = function (e) { e.stopPropagation(); goSlide(heroIdx + a[2]); restartHero(); };
        wrap.appendChild(ar);
      });
      // surish (swipe)
      var x0 = null, y0 = null;
      wrap.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; stopHero(); }, { passive: true });
      wrap.addEventListener("touchend", function (e) {
        if (x0 == null) return;
        var dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
        if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) { goSlide(heroIdx + (dx < 0 ? 1 : -1)); haptic(); }
        x0 = null; restartHero();
      }, { passive: true });
      if (HOVER) {   // sichqoncha ustida — to'xtaydi
        wrap.addEventListener("mouseenter", function () { wrap.classList.add("paused"); stopHero(); });
        wrap.addEventListener("mouseleave", function () { wrap.classList.remove("paused"); restartHero(); });
      }
      wrap.addEventListener("keydown", function (e) {
        if (e.key === "ArrowLeft") { goSlide(heroIdx - 1); restartHero(); }
        else if (e.key === "ArrowRight") { goSlide(heroIdx + 1); restartHero(); }
      });
    }
    heroIdx = 0;
    restartHero();
    return wrap;
  }
  function goSlide(i) {
    var slides = document.querySelectorAll(".hero .slide");
    if (!slides.length) return;
    heroIdx = (i + slides.length) % slides.length;
    slides.forEach(function (s, k) {
      s.classList.toggle("on", k === heroIdx);
      s.setAttribute("aria-hidden", k === heroIdx ? "false" : "true");
      s.inert = k !== heroIdx;
    });
    var dots = document.querySelectorAll(".hero .dot");
    dots.forEach(function (d) { d.classList.remove("on"); });
    void document.body.offsetWidth;                 // progress animatsiyasi qaytadan boshlansin
    if (dots[heroIdx]) dots[heroIdx].classList.add("on");
  }
  function stopHero() { clearTimeout(heroTimer); heroTimer = null; }
  function restartHero() {
    stopHero();
    if (heroItems.length < 2 || REDUCE) return;
    var dots = document.querySelectorAll(".hero .dot");
    if (dots[heroIdx]) { dots[heroIdx].classList.remove("on"); void document.body.offsetWidth; dots[heroIdx].classList.add("on"); }
    heroTimer = setTimeout(function () { goSlide(heroIdx + 1); restartHero(); }, HERO_MS);
  }

  function openExternal(url) {
    if (!PUB && tg && tg.openLink) { try { tg.openLink(url); return; } catch (e) {} }
    var a = document.createElement("a");
    a.href = url; a.target = "_blank"; a.rel = "noopener noreferrer";
    document.body.appendChild(a); a.click(); a.remove();
  }
  function actionRow(it, hero) {
    var row = h("div", "actions");
    var hasSite = !!it.wurl && it.cat !== "music" && !it.locked && !hero;      // 🌐 boshqa saytdagi link (ixtiyoriy)
    var watchBtn = h("button", "btn primary" + (it.locked ? " lock" : ""),
      [icon(it.locked ? "lock" : (PUB && it.cat !== "music" ? "send" : "play")),
       it.locked ? "Premium" : (it.cat === "music" ? "Tinglash" : (hasSite ? "Botda ko'rish" : (PUB ? "Telegramda ko'rish" : "Kinoni ko'rish")))]);
    watchBtn.onclick = function (e) {
      e.stopPropagation();
      if (it.cat === "music" && !it.locked) { Player.play(it, [it]); closeSheet(); }
      else watch(it, watchBtn);
    };
    row.appendChild(watchBtn);
    if (hasSite) {
      row.classList.add("two");
      var siteBtn = h("button", "btn soft site", [icon("globe"), "Saytda ko'rish"]);
      siteBtn.onclick = function (e) { e.stopPropagation(); haptic(); rememberWatch(it); openExternal(it.wurl); };
      row.appendChild(siteBtn);
    }
    if (it.cat === "music" && !it.locked) {
      var toBot = h("button", "btn sq", [icon("send")]);
      toBot.setAttribute("aria-label", "Botga yuborish");
      toBot.onclick = function (e) { e.stopPropagation(); watch(it, toBot); };
      row.appendChild(toBot);
    }
    if (it.trailer) {      // treyler — faqat admin shorts (video) qo'shgan bo'lsa
      var tr = h("button", "btn soft", [icon("clap"), "Treyler"]);
      tr.onclick = function (e) { e.stopPropagation(); openTrailer(it); };
      row.appendChild(tr);
    }
    if (hero) {
      var more = h("button", "btn soft", "Batafsil");
      more.onclick = function (e) { e.stopPropagation(); openSheet(it); };
      row.appendChild(more);
    }
    var bm = h("button", "btn sq" + (isSaved(it) ? " on" : ""), [icon("bookmark")]);
    bm.setAttribute("aria-label", "Saqlash");
    bm.onclick = function (e) { e.stopPropagation(); bm.classList.toggle("on", toggleSaved(it)); popBtn(bm); };
    var sh = h("button", "btn sq", [icon("share")]);
    sh.setAttribute("aria-label", "Ulashish");
    sh.onclick = function (e) { e.stopPropagation(); share(it); };
    row.appendChild(bm);
    row.appendChild(sh);
    return row;
  }

  function glinkRow(it) {
    var b = h("button", "btn soft glink", [icon("tv"), "Qolgan qismlar — guruhda"]);
    b.onclick = function () { haptic(); openLink(it.glink); };
    return h("div", "actions", [b]);
  }
  function openLink(url) {
    if (!PUB && tg && tg.openTelegramLink && /^https:\/\/t\.me\//.test(url)) { try { tg.openTelegramLink(url); return; } catch (e) {} }
    if (PUB && !APP) {            // brauzerda: sayt ochiq qolsin — havola yangi varaqda
      var a = document.createElement("a");
      a.href = url; a.target = "_blank"; a.rel = "noopener";
      document.body.appendChild(a); a.click(); a.remove();
      return;
    }
    window.location.href = url;  // ilovada Telegram ilovasida ochiladi
  }
  function botLink(it) { return "https://t.me/" + me.bot + "?start=" + (it.code < 0 ? "m" + (-it.code) : it.code); }
  function share(it) {
    haptic();
    // sayt havolasi ulashiladi: Telegram/WhatsApp'da poster va nom bilan chiroyli kartochka bo'lib chiqadi
    var link = location.origin + moviePath(it);
    var text = "🎬 " + it.title + " — " + me.brand;
    if (PUB && navigator.share) {
      navigator.share({ title: it.title, text: text, url: link }).catch(function () {});
      return;
    }
    openLink("https://t.me/share/url?url=" + encodeURIComponent(link) + "&text=" + encodeURIComponent(text));
  }
  function randomMovie(btn) {
    haptic("medium");
    if (btn) btn.disabled = true;
    api("/api/random").then(function (d) {
      if (btn) btn.disabled = false;
      if (d.ok && d.item) openSheet(d.item); else toast("😔 Hozircha kinolar yo'q");
    }).catch(function () { if (btn) btn.disabled = false; toast("⚠️ Ulanishda xatolik"); });
  }

