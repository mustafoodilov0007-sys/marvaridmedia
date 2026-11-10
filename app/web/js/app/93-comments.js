  // ───── 💬 izohlar ─────
  function ago(ts) {
    var d = Math.max(0, Date.now() / 1000 - ts);
    if (d < 60) return "hozir";
    if (d < 3600) return Math.floor(d / 60) + " daq";
    if (d < 86400) return Math.floor(d / 3600) + " soat";
    if (d < 7 * 86400) return Math.floor(d / 86400) + " kun";
    return fmtDate(ts);
  }
  function tapTwice(btn, ask, fn) {          // xavfli amal: ikki marta bosish kerak
    var t0 = 0, orig = btn.lastChild && btn.lastChild.textContent;
    btn.onclick = function (e) {
      e.stopPropagation();
      if (Date.now() - t0 < 3000) { fn(); return; }
      t0 = Date.now(); haptic();
      if (btn.lastChild) btn.lastChild.textContent = ask;
      setTimeout(function () { if (btn.lastChild && Date.now() - t0 >= 2900) btn.lastChild.textContent = orig; }, 3100);
    };
  }
  function commentsSection(it) {
    var st = { sort: "new", offset: 0, can: false, admin: false, max: 600, total: 0 };
    var box = h("section", "cmts");
    var countEl = h("span", "cm-count", "");
    var sortNew = h("button", "cm-sort on", "Yangi"), sortTop = h("button", "cm-sort", "Mashhur");
    var head = h("div", "cm-head", [h("h2", null, ["💬 Izohlar ", countEl]), h("div", "cm-sorts", [sortNew, sortTop])]);
    var list = h("div", "cm-list");
    var more = h("button", "loadmore hidden", "Yana izohlar");
    var slot = h("div", "cm-slot");
    box.appendChild(head); box.appendChild(slot); box.appendChild(list); box.appendChild(more);
    function setTotal(n) { st.total = n; countEl.textContent = n ? String(n) : ""; }
    function avatar(name) {
      var a = h("div", "cm-av", (name || "?").trim().charAt(0).toUpperCase() || "?");
      a.style.background = "hsl(" + hue(name || "") + ",45%,38%)";
      return a;
    }
    function composer(parentId, onDone, placeholder, autofocus) {
      var ta = h("textarea"); ta.rows = 1; ta.maxLength = st.max; ta.placeholder = placeholder || "Fikringizni yozing...";
      ta.setAttribute("aria-label", "Izoh matni");
      var left = h("span", "cm-left", ""); var send = h("button", "cm-send", "Yuborish"); send.disabled = true;
      var box2 = h("div", "cm-composer", [h("div", "cm-cbody", [ta, h("div", "cm-cfoot", [left, send])])]);
      function fit() { ta.style.height = "auto"; ta.style.height = Math.min(160, ta.scrollHeight) + "px"; }
      ta.addEventListener("input", function () {
        fit(); var n = ta.value.trim().length; send.disabled = n < 2;
        left.textContent = ta.value.length > st.max - 100 ? (st.max - ta.value.length) + "" : "";
      });
      send.onclick = function () {
        var text = ta.value.trim(); if (text.length < 2) return;
        send.disabled = true; send.textContent = "...";
        api("/api/comment", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: it.id, body: text, parent: parentId || 0 }) })
          .then(function (r) {
            send.textContent = "Yuborish";
            if (r.ok) { notify("success"); ta.value = ""; fit(); onDone(r); send.disabled = true; return; }
            notify("error"); send.disabled = false;
            toast("⚠️ " + (r.msg || "Izoh yuborilmadi. Qaytadan urinib ko'ring."));
          }).catch(function () { send.textContent = "Yuborish"; send.disabled = false; toast("⚠️ Ulanishda xatolik."); });
      };
      if (autofocus) setTimeout(function () { try { ta.focus({ preventScroll: false }); } catch (e) {} }, 50);
      return box2;
    }
    function node(c, top) {
      var meta = h("div", "cm-meta", [h("b", null, c.name)]);
      if (c.badge === "admin") meta.appendChild(h("span", "cm-badge adm", "ADMIN"));
      else if (c.badge === "premium") meta.appendChild(h("span", "cm-badge pre", "💎"));
      meta.appendChild(h("span", "cm-time", ago(c.ts)));
      var text = h("p", "cm-text", c.body);
      var like = h("button", "cm-btn like" + (c.liked ? " on" : ""), [icon("heart"), h("span", null, c.likes ? String(c.likes) : "")]);
      like.setAttribute("aria-label", "Yoqdi");
      like.onclick = function (e) {
        e.stopPropagation();
        if (guest()) { needLogin("Izohlarni baholash uchun hisobingizga kiring"); return; }
        haptic();
        api("/api/comment/like", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cid: c.id }) })
          .then(function (r) { if (!r.ok) return; c.liked = r.liked; c.likes = r.likes; like.classList.toggle("on", r.liked); if (r.liked) animOnce(like, "hpop", 550); like.lastChild.textContent = r.likes ? String(r.likes) : ""; });
      };
      var act = h("div", "cm-act", [like]);
      var repliesBox = h("div", "cm-replies");
      var wrap = h("div", "cm-body", [meta, text, act, repliesBox]);
      var slotR = h("div", "cm-rslot");
      var row = h("div", "cm" + (top ? "" : " reply"), [avatar(c.name), wrap]);
      if (st.can) {
        var rb = h("button", "cm-btn", [icon("reply"), h("span", null, "Javob")]);
        rb.onclick = function (e) {
          e.stopPropagation(); haptic();
          if (slotR.firstChild) { slotR.replaceChildren(); return; }
          slotR.replaceChildren(composer(top ? c.id : c.parentId, function (r) {
            slotR.replaceChildren(); setTotal(st.total + 1);
            var host = top ? repliesBox : row.parentNode;
            r.item.parentId = top ? c.id : c.parentId;
            var nn = node(r.item, false); nn.classList.add("cm-new"); host.appendChild(nn);
          }, "@" + c.name + " ga javob...", true));
        };
        act.appendChild(rb);
      }
      var tools = h("div", "cm-tools hidden");
      var mb = h("button", "cm-btn more", [icon("dots")]); mb.setAttribute("aria-label", "Yana");
      mb.onclick = function (e) { e.stopPropagation(); tools.classList.toggle("hidden"); };
      act.appendChild(mb);
      if (!c.mine && !guest()) {
        var fb = h("button", "cm-tool", [icon("flag"), h("span", null, "Shikoyat")]);
        tapTwice(fb, "Aniqmi?", function () {
          api("/api/comment/report", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cid: c.id }) })
            .then(function (r) { toast(r.ok ? "🙏 Shikoyat qabul qilindi" : "⚠️ Xatolik"); tools.classList.add("hidden"); if (r.hidden) row.remove(); });
        });
        tools.appendChild(fb);
      }
      if (c.mine || st.admin) {
        var db = h("button", "cm-tool danger", [icon("trash"), h("span", null, "O'chirish")]);
        tapTwice(db, "Aniqmi?", function () {
          api("/api/comment/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cid: c.id }) })
            .then(function (r) { if (r.ok) { row.remove(); setTotal(Math.max(0, st.total - 1 - (c.replies ? c.replies.length : 0))); toast("🗑 O'chirildi"); } else toast("⚠️ Xatolik"); });
        });
        tools.appendChild(db);
      }
      if (st.admin && !c.mine && c.uid) {
        var bb = h("button", "cm-tool danger", [icon("ban"), h("span", null, "Cheklash")]);
        tapTwice(bb, "Aniqmi?", function () {
          api("/api/comment/ban", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ cid: c.id }) })
            .then(function (r) { toast(r.ok ? (r.banned ? "🚫 Foydalanuvchi cheklandi" : "✅ Cheklash olindi") : "⚠️ Xatolik"); tools.classList.add("hidden"); });
        });
        tools.appendChild(bb);
      }
      if (tools.childNodes.length) wrap.insertBefore(tools, repliesBox); else mb.remove();
      wrap.insertBefore(slotR, repliesBox);
      (c.replies || []).forEach(function (r) { r.parentId = c.id; repliesBox.appendChild(node(r, false)); });
      return row;
    }
    function load(reset) {
      if (reset) { st.offset = 0; list.replaceChildren(h("div", "cm-skel", [h("i"), h("i"), h("i")])); more.classList.add("hidden"); }
      var q = "/api/comments?id=" + it.id + "&sort=" + st.sort + "&offset=" + st.offset;
      return api(q).then(function (d) {
        if (!d.ok) { list.replaceChildren(); return; }
        if (reset) list.replaceChildren();
        st.can = d.can_post; st.admin = d.admin; st.max = d.max || 600; setTotal(d.total);
        if (reset) {
          slot.replaceChildren();
          if (d.can_post) slot.appendChild(composer(0, function (r) {
            setTotal(r.total); var first = list.querySelector(".cm-empty"); if (first) first.remove();
            r.item.replies = []; var nn = node(r.item, true); nn.classList.add("cm-new"); list.insertBefore(nn, list.firstChild);
          }));
          else if (guest()) slot.appendChild(cmtCta(it));
          else slot.appendChild(h("div", "cm-note", "Izoh qoldirish sizga cheklangan."));
        }
        if (!d.items.length && reset) list.appendChild(h("div", "cm-empty", [icon("chat"), h("b", null, "Hali izoh yo'q"), h("span", null, "Birinchi bo'lib fikr qoldiring.")]));
        d.items.forEach(function (c) { list.appendChild(node(c, true)); });
        st.offset += d.items.length;
        more.classList.toggle("hidden", !d.more);
      }).catch(function () { if (reset) list.replaceChildren(); });
    }
    function cmtCta(it2) {
      var b = h("button", "btn primary", [icon("user"), "Kirish va izoh yozish"]);
      b.onclick = function () { haptic(); closeSheet(); show("login"); };
      return h("div", "cm-cta", [h("span", null, "Izoh qoldirish uchun hisobingizga kiring (Telegram yoki Google)."), b]);
    }
    more.onclick = function () { more.disabled = true; load(false).then(function () { more.disabled = false; }); };
    function setSort(k) { if (st.sort === k) return; st.sort = k; sortNew.classList.toggle("on", k === "new"); sortTop.classList.toggle("on", k === "top"); haptic(); load(true); }
    sortNew.onclick = function () { setSort("new"); }; sortTop.onclick = function () { setSort("top"); };
    // sahifa pastiga yaqinlashganda yuklanadi (kino oynasi tez ochilishi uchun)
    var started = false;
    function start() { if (started) return; started = true; load(true); }
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (e) { if (e[e.length - 1].isIntersecting) { io.disconnect(); start(); } }, { root: $("sheet"), rootMargin: "400px" });
      io.observe(box);
    } else start();
    return box;
  }
  // 🎬 pastdagi «yopishqoq» tugma: asosiy tugma ko'rinishdan chiqqach (izohlarni o'qiyotganda ham) kinoni ko'rish doim qo'l ostida
  function stickyBar(it, acts) {
    var b = h("button", "btn primary" + (it.locked ? " lock" : ""), [icon(it.locked ? "lock" : (PUB ? "send" : "play")), it.locked ? "Premium" : (PUB ? "Telegramda ko'rish" : "Kinoni ko'rish")]);
    b.onclick = function () { watch(it, b); };
    var bar = h("div", "sbar", [h("div", "sbar-t", [h("b", null, it.title), h("span", null, [yr(it), NAMES[it.cat] || ""].filter(Boolean).join(" · "))]), b]);
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (e) { bar.classList.toggle("on", !e[e.length - 1].isIntersecting); },
        { root: $("sheet"), threshold: 0 });
      io.observe(acts);
    }
    return bar;
  }
  // 🛫 Kartadan kino oynasiga: poster joyidan «uchib» o'tadi (qaytishda — orqasiga). Faqat transform/rect, 0.4 soniya.
  var flyEl = null, flySrc = null, flyId = null;
  function imgOf(posterEl) {          // poster rasmi: <img> yoki fon rasmi (karusel)
    if (!posterEl) return "";
    var im = posterEl.querySelector("img.ok");
    if (!im) Array.prototype.forEach.call(posterEl.querySelectorAll("img"), function (x) { if (!im && x.complete && x.naturalWidth) im = x; });
    if (im) return im.currentSrc || im.src;
    var m = /url\(["']?([^"')]+)["']?\)/.exec(posterEl.style.backgroundImage || "");
    return m ? m[1] : "";
  }
  function hidesSrc(el) { return !el.classList.contains("bg"); }      // karusel foni (butun slayd) yashirilmaydi — matn qolib ketmasin
  function flyBox(url, r, radius) {
    var d = document.createElement("div");
    d.className = "flyp";
    d.style.cssText = "left:" + r.left + "px;top:" + r.top + "px;width:" + r.width + "px;height:" + r.height + "px;border-radius:" + radius + ";background-image:url('" + url + "')";
    document.body.appendChild(d);
    return d;
  }
  function flyMove(d, r, radius, done) {
    void d.offsetWidth;
    d.style.transition = "left .42s cubic-bezier(.2,.8,.2,1), top .42s cubic-bezier(.2,.8,.2,1), width .42s cubic-bezier(.2,.8,.2,1), height .42s cubic-bezier(.2,.8,.2,1), border-radius .42s";
    d.style.left = r.left + "px"; d.style.top = r.top + "px"; d.style.width = r.width + "px"; d.style.height = r.height + "px"; d.style.borderRadius = radius;
    var fin = false;
    function end() { if (fin) return; fin = true; done(); }
    d.addEventListener("transitionend", end); setTimeout(end, 520);
  }
  function flyTarget(sheet) {          // telefonda poster butun ekranli muqovaga «kengayadi», kompyuterda — oynadagi postergacha
    return innerWidth < 900 ? sheet.querySelector(".sheet-top") : sheet.querySelector(".sheet-main .poster");
  }
  function flyCleanup() {
    if (flyEl) { flyEl.remove(); flyEl = null; }
    var tp = flyTarget($("sheet")); if (tp) tp.style.visibility = "";
    if (flySrc) flySrc.style.visibility = "";
  }
  function inView(r) { return r.width > 8 && r.height > 8 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; }
  function openSheet(it, fromPop, srcPoster) {
    haptic();
    if (!fromPop) pushSheet(it);
    var s = $("sheet");
    if (!sheetOpen) lastFocus = document.activeElement;
    var bg = h("div", "bg" + (it.poster ? "" : " ph"));
    if (it.poster) bg.style.backgroundImage = "url('" + posterUrl(it, innerWidth < 900 ? 720 : 360) + "')";
    var closeBtn = h("button", "ibtn close", [icon("x")]);
    closeBtn.setAttribute("aria-label", "Yopish");
    closeBtn.onclick = function () { closeSheet(); };
    var chips = h("div", "chips");
    (it.genres || []).forEach(function (g) { chips.appendChild(h("span", "chip g", g.label)); });
    if (it.premium) chips.appendChild(h("span", "chip gold", "PREMIUM"));
    var metaBits = [NAMES[it.cat] || "Kino"];
    if (it.year) metaBits.push(yr(it));
    if (fmtDur(it.duration)) metaBits.push(fmtDur(it.duration));
    if (it.country) metaBits.push(it.country);
    var metaLine = h("div", "smeta", [it.age ? h("span", "agebox", it.age + "+") : null, h("span", null, metaBits.join(" · "))]);
    var stats = h("div", "stats");
    if (it.views > 0) { var sv = h("span"); countUp(sv, "👁 ", it.views, fmt, " ko'rilgan"); stats.appendChild(sv); }
    var sc = score(it);
    if (sc !== null) { var ss = h("span"); countUp(ss, "👍 ", sc, String, "% yoqdi"); stats.appendChild(ss); }
    if (it.added) stats.appendChild(h("span", null, "📅 " + fmtDate(it.added) + " qo'shilgan"));
    var desc = null;
    if (it.desc) {
      desc = h("div", "descbox");
      var p = h("p", "desc" + (it.desc.length > 220 ? " clamp" : ""), it.desc);
      desc.appendChild(p);
      if (it.desc.length > 220) {
        var tgl = h("button", "more", "Ko'proq");
        tgl.onclick = function () { var c = p.classList.toggle("clamp"); tgl.textContent = c ? "Ko'proq" : "Kamroq"; };
        desc.appendChild(tgl);
      }
    }
    // «Tafsilotlar» yorlig'i uchun ma'lumotlar qatori
    function drow(label, value) { return value ? h("div", "drow", [h("span", null, label), h("b", null, String(value))]) : null; }
    var details = h("div", "sdetails", [
      drow("Turi", NAMES[it.cat] || "Kino"), drow("Yili", it.year ? yr(it) : ""), drow("Davomiyligi", fmtDur(it.duration)),
      drow("Davlat", it.country), drow("Til", it.lang), drow("Sifat", it.quality), drow("Yosh cheklovi", it.age ? it.age + "+" : ""),
      drow("IMDb", it.imdb), drow("Qismlar", it.parts > 1 ? it.parts + " qism" : ""), drow("Kod", it.code > 0 ? it.code : ""),
      drow("Ko'rilgan", it.views > 0 ? fmt(it.views) : ""), drow("Qo'shilgan", it.added ? fmtDate(it.added) : "")].filter(Boolean));
    var hasMain = useMain(it);
    s.classList.toggle("hasmain", hasMain);
    var similar = it.cat === "music" ? null : h("div", "similar");
    s.setAttribute("aria-label", it.title);
    var acts = actionRow(it, false);
    var noteNode = h("div", "note", it.locked ? "Bu kontent Premium a'zolar uchun. Bot chatida Premium olish tugmasi chiqadi."
      : it.cat === "music" ? "«Tinglash» — shu yerning o'zida eshitasiz. Yonidagi tugma qo'shiqni Telegram botga yuboradi."
      : PUB ? "«Kinoni ko'rish» bosilsa, Telegram'da botimiz ochiladi va kinoni yuboradi."
      : "«Kinoni ko'rish» bosilsa, bot kinoni chatga yuboradi.");
    var tabList = [{ label: "Umumiy", nodes: [desc, it.glink ? glinkRow(it) : null, it.cat === "music" ? null : rateRow(it), noteNode, similar] }];
    if (it.cat !== "music") tabList.push({ label: "Izohlar", lazy: function () { return [commentsSection(it)]; } });   // izohlar yorliq ochilganda quriladi (sahifa ochilishi yengil)
    if (it.trailer || it.turl) {
      var trBtn = h("button", "strailer", [posterNode(it, 720), h("span", "play", [icon("play")]), h("b", null, "Treylerni ko'rish")]);
      trBtn.onclick = function () { haptic(); openTrailer(it); };
      tabList.push({ label: "Treyler", nodes: [trBtn] });
    }
    tabList.push({ label: "Tafsilotlar", nodes: [details] });
    var tabsEl = h("div", "stabs"), panels = [];
    tabList.forEach(function (t, i) {
      var tb = h("button", "stab" + (i ? "" : " on"), t.label);
      var pn = h("div", "spanel" + (i ? " hidden" : ""), (t.nodes || []).filter(Boolean));
      tb.onclick = function () {
        haptic();
        if (t.lazy) { var mk = t.lazy; t.lazy = null; mk().forEach(function (n) { pn.appendChild(n); }); }
        tabsEl.querySelectorAll(".stab").forEach(function (x) { x.classList.toggle("on", x === tb); });
        panels.forEach(function (x) { x.classList.toggle("hidden", x !== pn); });
        try { tb.scrollIntoView({ inline: "center", block: "nearest" }); } catch (e) {}
      };
      tabsEl.appendChild(tb); panels.push(pn);
    });
    var topKids = [bg, h("div", "grip"), closeBtn];
    var heroVid = null;
    if (it.trailer && !LITE && !REDUCE && !(navigator.connection && navigator.connection.saveData)) {     // muqova ustida treyler jim o'ynaydi (poster qoladi)
      heroVid = document.createElement("video");
      heroVid.className = "svid"; heroVid.muted = true; heroVid.defaultMuted = true; heroVid.loop = true; heroVid.playsInline = true;
      heroVid.setAttribute("playsinline", ""); heroVid.setAttribute("muted", ""); heroVid.preload = "auto";
      heroVid.src = "/media/short/" + it.trailer;
      heroVid.addEventListener("playing", function () { setTimeout(function () { heroVid.classList.add("on"); }, 700); });
      heroVid.addEventListener("error", function () { heroVid.remove(); });
      topKids.splice(1, 0, heroVid);
    }
    var parts = [
      h("div", "sheet-top", topKids),
      h("div", "sheet-main", [posterNode(it, 720), h("div", "info", [h("h3", null, it.title), metaLine, ratingBadges(it), chips, stats.childNodes.length ? stats : null])]),
      acts,
      me.admin ? adminBar(it) : null,
      tabsEl
    ].concat(panels);
    var bar = (hasMain || it.cat === "music") ? null : stickyBar(it, acts);
    if (bar) parts.push(bar);
    s.replaceChildren.apply(s, parts.filter(Boolean));          // null qiymatlar «null» matni bo'lib chiqmasin
    if (similar) {
      var myS = ++sheetReq;
      setTimeout(function () {          // ochilish animatsiyasi tugagach (qotib qolmasin)
        if (myS !== sheetReq) return;
        api("/api/similar?id=" + it.id).then(function (d) {
          if (myS !== sheetReq || !d.ok || !d.items.length) return;
          var list = h("div", "rail");
          d.items.forEach(function (x) { list.appendChild(card(x)); });
          similar.replaceChildren(h("div", "sec-head", [h("h2", null, "🎭 O'xshash kinolar")]), list);
        }).catch(function () {});
      }, 480);
    }
    flyCleanup(); flySrc = null; flyId = null;
    if (heroVid) { var pv = heroVid.play(); if (pv && pv.catch) pv.catch(function () {}); }
    var url = (!sheetOpen && !REDUCE && srcPoster) ? imgOf(srcPoster) : "";
    if (url) { s.style.transition = "none"; s.style.opacity = "0"; }       // oyna o'z joyida paydo bo'ladi, poster «uchib» keladi
    $("veil").classList.add("on");
    s.classList.add("on");
    s.scrollTop = 0;
    if (url) {
      var tp = flyTarget(s), sr = srcPoster.getBoundingClientRect(), tr = tp ? tp.getBoundingClientRect() : null;
      if (tr && inView(sr) && tr.width > 8) {
        tp.style.visibility = "hidden";
        flyEl = flyBox(url, sr, getComputedStyle(srcPoster).borderRadius);
        flySrc = srcPoster; flyId = it.id;
        if (hidesSrc(srcPoster)) srcPoster.style.visibility = "hidden";
        void s.offsetWidth;
        s.style.transition = "opacity .3s"; s.style.opacity = "1";
        var mine = flyEl;
        flyMove(flyEl, tr, getComputedStyle(tp).borderRadius, function () {
          if (flyEl !== mine) return;
          tp.style.visibility = ""; srcPoster.style.visibility = ""; flyEl.remove(); flyEl = null;
          s.style.transition = ""; s.style.opacity = "";
        });
      } else { s.style.transition = ""; s.style.opacity = ""; }
    }
    sheetOpen = true;
    lockSwipes(true);
    stopHero();
    document.querySelectorAll(".short video").forEach(function (v) { v.pause(); });
    updateBack();
    setTimeout(function () { try { closeBtn.focus({ preventScroll: true }); } catch (e) {} }, 60);
  }
  function closeSheet(fromPop) {
    closeTrailer(true);
    document.querySelectorAll("#sheet video").forEach(function (v) { try { v.pause(); } catch (e) {} });
    var sh = $("sheet"), back = null;
    if (flySrc && flyId != null && document.body.contains(flySrc) && !REDUCE) {      // orqaga «uchib» qaytish
      var tp0 = flyTarget(sh), im0 = tp0 && tp0.classList.contains("sheet-top") ? imgOf(tp0.querySelector(".bg")) : imgOf(tp0), sr0 = flySrc.getBoundingClientRect(), tr0 = tp0 ? tp0.getBoundingClientRect() : null;
      if (im0 && tr0 && inView(sr0) && inView(tr0)) back = { url: im0, from: tr0, to: sr0, src: flySrc, tp: tp0 };
    }
    flyCleanup();
    if (back) {
      back.tp.style.visibility = "hidden"; if (hidesSrc(back.src)) back.src.style.visibility = "hidden";
      var cl = flyBox(back.url, back.from, getComputedStyle(back.tp).borderRadius);
      flyMove(cl, back.to, getComputedStyle(back.src).borderRadius, function () { back.src.style.visibility = ""; cl.remove(); });
      setTimeout(function () { back.src.style.visibility = ""; if (cl.parentNode) cl.remove(); }, 700);
    }
    flySrc = null; flyId = null;
    $("veil").classList.remove("on");
    $("sheet").classList.remove("on");
    sheetOpen = false;
    lockSwipes(false);
    setTimeout(flushUnsaved, 260);              // sevimlilardan olib tashlangan kartalar oyna yopilgach so'nadi
    hideMain();
    if (HIST && fromPop !== true) {
      try { if (history.state && history.state.sheet) { skipPop++; history.back(); } } catch (e) {}
    }
    if (current === "home") restartHero();
    updateBack();
    if (lastFocus && lastFocus.focus && document.body.contains(lastFocus)) { try { lastFocus.focus({ preventScroll: true }); } catch (e) {} }
  }
  $("veil").onclick = function () { closeSheet(); };

