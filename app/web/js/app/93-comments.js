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
  // 🛫 Kartadan kino sahifasiga o'tish (FLIP). Faqat transform va opacity, Web Animations API orqali — brauzer buni alohida
  // (kompozitor) oqimda bajaradi, shuning uchun sahifa qurilayotgan paytda ham poster silliq uchadi, qotmaydi.
  var M_EASE = "cubic-bezier(.32,.72,0,1)", M_OPEN = 560, M_CLOSE = 460;     // iOS uslubidagi yumshoq sekinlashish, sakrashsiz
  var WAAPI = !!(document.body && document.body.animate);
  var flyEl = null, flySrc = null, flyId = null, flyAnim = null, sheetAnim = null;
  function imgOf(posterEl) {          // poster rasmi: <img> yoki fon rasmi (karusel)
    if (!posterEl) return "";
    var im = posterEl.querySelector("img.ok");
    if (!im) Array.prototype.forEach.call(posterEl.querySelectorAll("img"), function (x) { if (!im && x.complete && x.naturalWidth) im = x; });
    if (im) return im.currentSrc || im.src;
    var m = /url\(["']?([^"')]+)["']?\)/.exec(posterEl.style.backgroundImage || "");
    return m ? m[1] : "";
  }
  function hidesSrc(el) { return !el.classList.contains("bg"); }      // karusel foni (butun slayd) yashirilmaydi — matn qolib ketmasin
  function radiusOf(el) { return parseFloat(getComputedStyle(el).borderTopLeftRadius) || 0; }
  function inView(r) { return r.width > 8 && r.height > 8 && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; }
  // poster nusxasi KATTA (oxirgi) holatida joylanadi; kichik holat — transform (scale + translate)
  function makeFly(url, box, radius) {
    var d = document.createElement("div");
    d.className = "flyp";
    d.style.cssText = "left:" + box.left + "px;top:" + box.top + "px;width:" + box.width + "px;height:" + box.height + "px;border-radius:" +
      radius.toFixed(1) + "px;background-image:url('" + url + "')";
    document.body.appendChild(d);
    return d;
  }
  function flipT(from, box) {        // box joyidagi elementni from to'rtburchagiga «qisqartiradigan» transform
    return "translate3d(" + (from.left - box.left).toFixed(1) + "px," + (from.top - box.top).toFixed(1) + "px,0) scale(" +
      (from.width / box.width).toFixed(4) + "," + (from.height / box.height).toFixed(4) + ")";
  }
  function maskFly(d, h, heroH) {    // telefonda: poster muqova pastida yumshoq so'nadi (sarlavha uning ostida ko'rinadi)
    var a = Math.max(0, (heroH - 190) / h * 100), b = Math.min(100, (heroH - 20) / h * 100);
    var m = "linear-gradient(180deg,#000 " + a.toFixed(1) + "%,transparent " + b.toFixed(1) + "%)";
    d.style.webkitMaskImage = m; d.style.maskImage = m;
  }
  function decodeUrl(url, maxMs) {   // katta muqova rasmi tayyor bo'lguncha kutamiz (ko'pi bilan maxMs) — «sakrash» bo'lmasin
    return new Promise(function (res) {
      if (!url) return res();
      var im = new Image(), done = false;
      function ok() { if (!done) { done = true; res(); } }
      im.src = url;
      if (im.decode) im.decode().then(ok, ok); else { im.onload = ok; im.onerror = ok; }
      setTimeout(ok, maxMs);
    });
  }
  function stopAnims() {
    if (flyAnim) { try { flyAnim.cancel(); } catch (e) {} flyAnim = null; }
    if (sheetAnim) { try { sheetAnim.cancel(); } catch (e) {} sheetAnim = null; }
  }
  function flyCleanup() {
    if (flyEl) { flyEl.remove(); flyEl = null; }
    var sh = $("sheet"), bgx = sh.querySelector(".sheet-top .bg"), tp = sh.querySelector(".sheet-main .poster");
    if (bgx) bgx.style.opacity = "";
    if (tp) tp.style.visibility = "";
    if (flySrc) flySrc.style.visibility = "";
  }
  function openSheet(it, fromPop, srcPoster) {
    haptic();
    if (!fromPop) pushSheet(it);
    var s = $("sheet");
    if (!sheetOpen) lastFocus = document.activeElement;
    var wasOpen = sheetOpen, mobile = innerWidth < 900;
    stopAnims(); flyCleanup(); flySrc = null; flyId = null;
    document.body.classList.remove("sheet-cover");
    sheetOpen = true;
    // 1) poster DARHOL ucha boshlaydi (kompozitorda), sahifa esa keyingi kadrda quriladi — bosilgan zahoti javob, qotish yo'q
    var url = (!wasOpen && !REDUCE && WAAPI && srcPoster) ? imgOf(srcPoster) : "";
    var sr = url ? srcPoster.getBoundingClientRect() : null;
    if (sr && !inView(sr)) url = "";
    var heroBox = null;
    if (url && mobile) {
      heroBox = { left: 0, top: 0, width: innerWidth, height: innerWidth * sr.height / sr.width };
      flyEl = makeFly(url, heroBox, radiusOf(srcPoster) * heroBox.width / sr.width);
      flySrc = srcPoster; flyId = it.id;
      if (hidesSrc(srcPoster)) srcPoster.style.visibility = "hidden";
      flyAnim = flyEl.animate([{ transform: flipT(sr, heroBox) }, { transform: "none" }], { duration: M_OPEN, easing: M_EASE, fill: "both" });
      requestAnimationFrame(function () { setTimeout(build, 0); });
    } else build();
    function build() {
    if (!sheetOpen) return;                 // ochilish to'xtatilgan (tez yopildi)
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
    if (it.views > 0) stats.appendChild(h("span", null, "👁 " + fmt(it.views) + " ko'rilgan"));
    var sc = score(it);
    if (sc !== null) stats.appendChild(h("span", null, "👍 " + sc + "% yoqdi"));
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
    var topKids = [bg, h("div", "sdim"), h("div", "grip"), closeBtn];
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
      h("div", "sbody", [      // poster joyida turadi, shu qism (matn, tugmalar, yorliqlar) surilganda uning ustiga chiqadi
        h("div", "sheet-main", [posterNode(it, 720), h("div", "info", [h("h3", null, it.title), metaLine, ratingBadges(it), chips, stats.childNodes.length ? stats : null])]),
        acts,
        me.admin ? adminBar(it) : null,
        tabsEl
      ].concat(panels).filter(Boolean))
    ];
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
    if (heroVid) { var pv = heroVid.play(); if (pv && pv.catch) pv.catch(function () {}); }
    s.style.transition = "none";
    s.style.transform = "";
    $("veil").classList.add("on");
    s.classList.add("on");
    s.scrollTop = 0;
    var dimEl = s.querySelector(".sheet-top .sdim"); if (dimEl) dimEl.style.opacity = "0";
    var finishOpen = function () { if (sheetOpen && mobile) document.body.classList.add("sheet-cover"); };   // orqadagi sahifa chizilmaydi
    if (flyEl && heroBox) {                                   // telefon: poster muqovaga aylanadi
      var bgEl = s.querySelector(".sheet-top .bg"), heroT = s.querySelector(".sheet-top");
      if (bgEl) bgEl.style.opacity = "0";
      maskFly(flyEl, heroBox.height, heroT ? heroT.getBoundingClientRect().height : innerHeight * .6);
      sheetAnim = s.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 380, easing: "ease-out" });
      var myFly = flyEl, myAnim = flyAnim;
      Promise.all([myAnim.finished.catch(function () {}), decodeUrl(it.poster ? posterUrl(it, 720) : "", 900)]).then(function () {
        if (flyEl !== myFly) return;
        if (bgEl) bgEl.style.opacity = "";
        if (flySrc) flySrc.style.visibility = "";
        var fade = myFly.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 260, easing: "ease-out", fill: "forwards" });
        fade.onfinish = function () { myFly.remove(); if (flyEl === myFly) flyEl = null; finishOpen(); };
        flyAnim = null;
      });
    } else if (url && !mobile) {                              // kompyuter: poster oynadagi posterga uchadi
      var tp = s.querySelector(".sheet-main .poster"), tr = tp ? tp.getBoundingClientRect() : null;
      if (tr && tr.width > 8) {
        tp.style.visibility = "hidden";
        flyEl = makeFly(url, tr, radiusOf(tp));
        flySrc = srcPoster; flyId = it.id;
        if (hidesSrc(srcPoster)) srcPoster.style.visibility = "hidden";
        flyAnim = flyEl.animate([{ transform: flipT(sr, tr) }, { transform: "none" }], { duration: M_OPEN, easing: M_EASE });
        sheetAnim = s.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 360, easing: "ease-out" });
        var dFly = flyEl;
        flyAnim.onfinish = function () {
          tp.style.visibility = ""; if (flySrc) flySrc.style.visibility = "";
          dFly.remove(); if (flyEl === dFly) flyEl = null; flyAnim = null;
        };
      }
    } else if (!wasOpen && mobile && WAAPI && !REDUCE) {      // telefon, manbasiz (qidiruv, havola): sahifa pastdan yumshoq chiqadi
      sheetAnim = s.animate([{ opacity: 0, transform: "translate3d(0,28px,0)" }, { opacity: 1, transform: "none" }], { duration: 480, easing: M_EASE });
      sheetAnim.onfinish = function () { sheetAnim = null; finishOpen(); };
    } else finishOpen();
    requestAnimationFrame(function () { s.style.transition = ""; });
    }
    lockSwipes(true);
    stopHero();
    document.querySelectorAll(".short video").forEach(function (v) { v.pause(); });
    updateBack();
    setTimeout(function () { var cb = s.querySelector(".close"); try { if (cb) cb.focus({ preventScroll: true }); } catch (e) {} }, 60);
  }
  function closeSheet(fromPop) {
    closeTrailer(true);
    var sh = $("sheet"), mobile = innerWidth < 900;
    sh.querySelectorAll("video").forEach(function (v) { try { v.pause(); } catch (e) {} });
    document.body.classList.remove("sheet-cover");             // orqadagi sahifa yana ko'rinadi (yopilish ostida)
    stopAnims();
    var src = flySrc, id = flyId;
    if (flyEl) { flyEl.remove(); flyEl = null; }
    flySrc = null; flyId = null;
    var back = null;
    if (src && !sh.classList.contains("on")) { src.style.visibility = ""; src = null; }   // sahifa hali qurilmagan — qaytish uchishi yo'q
    if (src && id != null && document.body.contains(src) && !REDUCE && WAAPI) {      // orqaga «uchib» qaytish
      var sr0 = src.getBoundingClientRect();
      if (inView(sr0)) {
        if (mobile) {
          var bg0 = sh.querySelector(".sheet-top .bg"), hero0 = sh.querySelector(".sheet-top"), url0 = imgOf(bg0);
          if (url0 && hero0) back = { url: url0, box: { left: 0, top: 0, width: innerWidth, height: innerWidth * sr0.height / sr0.width },
                                      heroH: hero0.getBoundingClientRect().height, hide: bg0 };
        } else {
          var tp0 = sh.querySelector(".sheet-main .poster"), tr0 = tp0 ? tp0.getBoundingClientRect() : null;
          if (tp0 && tr0 && inView(tr0)) back = { url: imgOf(tp0) || imgOf(src), box: tr0, hide: tp0 };
        }
        if (back && back.url) {
          var cl = makeFly(back.url, back.box, mobile ? radiusOf(src) * back.box.width / sr0.width : radiusOf(back.hide));
          if (back.heroH) maskFly(cl, back.box.height, back.heroH);
          back.hide.style.visibility = "hidden";
          if (hidesSrc(src)) src.style.visibility = "hidden";
          var ba = cl.animate([{ transform: "none" }, { transform: flipT(sr0, back.box) }], { duration: M_CLOSE, easing: M_EASE, fill: "forwards" });
          var fin = function () { src.style.visibility = ""; back.hide.style.visibility = ""; cl.remove(); };
          ba.onfinish = fin; setTimeout(function () { if (cl.parentNode) fin(); }, M_CLOSE + 400);
        } else back = null;
      }
    }
    if (src && !back) src.style.visibility = "";
    sheetOpen = false;
    $("veil").classList.remove("on");
    if (mobile && WAAPI && !REDUCE) {                          // telefon: sahifa yumshoq so'nadi, so'ng yashirinadi
      var from = sh.style.transform || "none";
      sheetAnim = sh.animate([{ opacity: 1, transform: from }, { opacity: 0, transform: back ? from : "translate3d(0,22px,0)" }],
                             { duration: back ? 300 : 340, easing: "ease-out", fill: "forwards" });
      var mine = sheetAnim;
      sheetAnim.onfinish = function () {
        if (sheetAnim !== mine) return;
        if (!sheetOpen) { sh.classList.remove("on"); sh.style.transform = ""; }
        mine.cancel(); sheetAnim = null;
      };
    } else sh.classList.remove("on");
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

