  // ───── 🎞 Shorts ─────
  var shortsMuted = false, shortsIO = null, shortsLoadIO = null, shortsRO = null, shortsKeyFn = null;
  function leaveShorts() {
    document.body.classList.remove("in-shorts");
    if (shortsIO) { shortsIO.disconnect(); shortsIO = null; }
    if (shortsLoadIO) { shortsLoadIO.disconnect(); shortsLoadIO = null; }
    if (shortsRO) { shortsRO.disconnect(); shortsRO = null; }
    if (shortsKeyFn) { document.removeEventListener("keydown", shortsKeyFn); shortsKeyFn = null; }
    document.querySelectorAll(".short video").forEach(function (v) { try { v.pause(); } catch (e) {} });
    document.querySelectorAll(".shorts-head, .sarrows").forEach(function (n) { n.remove(); });
  }
  function renderShorts(view, startIdx) {
    document.body.classList.add("in-shorts");
    var feed = h("div", "shorts");
    var muteBtn = h("button", "ibtn", [icon(shortsMuted ? "mute" : "vol")]);
    muteBtn.setAttribute("aria-label", "Ovoz");
    var sBtn = h("button", "ibtn", [icon("search")]);
    sBtn.setAttribute("aria-label", "Qidiruv");
    sBtn.onclick = function () { haptic(); show("search"); };
    var head = h("div", "shorts-head", [h("b", null, "Shorts"), h("div", "shead-btns", [sBtn, muteBtn])]);
    function setMuted(m) {
      shortsMuted = m;
      muteBtn.replaceChildren(icon(m ? "mute" : "vol"));
      feed.querySelectorAll("video").forEach(function (v) { v.muted = m; });
      feed.querySelectorAll(".smute").forEach(function (b) { b.replaceChildren(icon(m ? "mute" : "vol")); });
    }
    muteBtn.onclick = function () { haptic(); setMuted(!shortsMuted); };
    // kompyuterda: yuqoriga / pastga strelkalar
    function step(d) { feed.scrollBy({ top: d * feed.clientHeight, behavior: REDUCE ? "auto" : "smooth" }); }
    var up = h("button", "ibtn", [icon("chev")]), down = h("button", "ibtn", [icon("chev")]);
    up.setAttribute("aria-label", "Oldingi short"); down.setAttribute("aria-label", "Keyingi short");
    up.classList.add("sup"); down.classList.add("sdown");
    up.onclick = function () { step(-1); }; down.onclick = function () { step(1); };
    var arrows = h("div", "sarrows", [up, down]);
    function current() { return feed.children[Math.round(feed.scrollTop / Math.max(1, feed.clientHeight))]; }
    shortsKeyFn = function (e) {
      if (!document.body.classList.contains("in-shorts") || sheetOpen || trailerOpen) return;
      var tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "select" || tag === "textarea") return;
      var k = e.key;
      if (k === "ArrowDown" || k === "PageDown" || k === "j") { e.preventDefault(); step(1); }
      else if (k === "ArrowUp" || k === "PageUp" || k === "k") { e.preventDefault(); step(-1); }
      else if (k === "m" || k === "M") { setMuted(!shortsMuted); }
      else if (k === " " && tag !== "button") {
        var v = current() && current().querySelector("video");
        if (v) { e.preventDefault(); v._toggle(); }
      }
    };
    document.addEventListener("keydown", shortsKeyFn);
    view.replaceChildren(feed);
    document.body.appendChild(head);
    document.body.appendChild(arrows);
    var my = reqId, offset = 0, more = true, loading = false;

    // kadr o'lchami: butun kadr sig'adi, cho'zilmaydi va kesilmaydi
    function fit(el) {
      feed.style.setProperty("--feedH", feed.clientHeight + "px");     // har bir short aynan ko'rinadigan oyna balandligida
      var fr = el._frame, vw = el._vw || 9, vh = el._vh || 16;
      var cw = feed.clientWidth, wide = cw >= 900, ch = feed.clientHeight - (wide ? 28 : 0);
      var sc = Math.min((wide ? Math.min(cw * 0.92, 1180) : cw) / vw, ch / vh);
      fr.style.width = Math.round(vw * sc) + "px";
      fr.style.height = Math.round(vh * sc) + "px";
      var host = wide ? fr : el;   // telefonda matn va tugmalar kichik kadrga siqilmasin
      (el._ui || []).forEach(function (n) { if (n.parentNode !== host) host.appendChild(n); });
    }
    if (window.ResizeObserver) {
      shortsRO = new ResizeObserver(function () {
        Array.prototype.forEach.call(feed.children, function (el) { if (el._frame) fit(el); });
        var H = feed.clientHeight;                       // o'lcham o'zgarsa (iOS paneli, burilish) — joriy short o'z joyiga qaytadi
        if (H && feed.scrollTop % H) feed.scrollTop = Math.round(feed.scrollTop / H) * H;
      });
      shortsRO.observe(feed);
    }

    var soundArmed = false;
    function armSound() {
      if (soundArmed) return; soundArmed = true;
      function on() {
        soundArmed = false;
        ["pointerdown", "keydown", "touchend"].forEach(function (ev) { document.removeEventListener(ev, on, true); });
        if (shortsMuted) return;
        feed.querySelectorAll("video").forEach(function (v) { if (!v.paused) { v.muted = false; fadeVolume(v); } });
      }
      ["pointerdown", "keydown", "touchend"].forEach(function (ev) { document.addEventListener(ev, on, true); });
    }
    shortsIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        var el = en.target, v = el.querySelector("video");
        if (!v) return;
        if (en.isIntersecting && en.intersectionRatio > .6) {
          if (v.dataset.src) { v.src = v.dataset.src; v.removeAttribute("data-src"); }   // iOS: src o'rnatilgach ijro etiladi
          v.muted = shortsMuted;
          if (!shortsMuted) fadeVolume(v);                                                   // ovoz keskin emas, yumshoq kiradi
          var p = v.play();
          if (p && p.catch) p.catch(function () {
            if (shortsMuted) { el.classList.add("is-paused"); return; }
            // brauzer ovozli avto-ijroni to'sdi (sahifa to'g'ridan-to'g'ri ochilgan): ovozsiz boshlaymiz, birinchi bosishda ovoz yoqiladi
            v.muted = true;
            var p2 = v.play(); if (p2 && p2.catch) p2.catch(function () { el.classList.add("is-paused"); });
            armSound(); toast("🔊 Ovoz uchun ekranga tegining");
          });
          el.classList.remove("is-paused");
          var idx = +el.dataset.idx;
          around(idx);
          if (more && !loading && idx >= feed.children.length - 3) load();
        } else { v.pause(); }
      });
    }, { root: feed, threshold: [0, .6, 1] });
    // ⏭ qo'shnilar: keyingi va oldingi video oldindan yuklanadi (surganda qora ekran/kutish yo'q),
    // uzoqdagilari esa bo'shatiladi (telefon xotirasi va video dekoderlari to'lib, qotib qolmasin)
    function around(idx) {
      Array.prototype.forEach.call(feed.children, function (c, k) {
        var vv = c.querySelector && c.querySelector("video");
        if (!vv) return;
        var d = Math.abs(k - idx);
        if (d === 1) {
          if (vv.dataset.src) { vv.src = vv.dataset.src; vv.removeAttribute("data-src"); }
          if (vv.preload !== "auto") { vv.preload = "auto"; try { vv.load(); } catch (e) {} }
        } else if (d > 2 && vv.getAttribute("src") && !vv.dataset.src) {
          try { vv.pause(); } catch (e) {}
          vv.dataset.src = vv.getAttribute("src"); vv.removeAttribute("src"); vv.preload = "metadata";
          try { vv.load(); } catch (e) {}
        }
      });
    }
    function fadeVolume(vv) {
      if (REDUCE) { vv.volume = 1; return; }
      var t0 = performance.now();
      vv.volume = 0;
      (function step(t) {
        var k = Math.min(1, (t - t0) / 380);
        try { vv.volume = k * k; } catch (e) { return; }
        if (k < 1) requestAnimationFrame(step);
      })(t0);
    }
    // videoni faqat yaqinlashganda yuklaymiz (trafikni tejash)
    shortsLoadIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var v = en.target.querySelector("video[data-src]");
        if (v) { v.src = v.dataset.src; v.removeAttribute("data-src"); }
      });
    }, { root: feed, rootMargin: "120% 0px" });

    // yuklanmagan short oqimni to'xtatib qo'ymasin: keyingisiga o'tadi (qayta urinish tugmasi qoladi)
    function failShort(el) {
      var H = feed.clientHeight;
      if (!H || Math.round(feed.scrollTop / H) !== +el.dataset.idx) return;
      var next = feed.children[+el.dataset.idx + 1];
      if (next && next.querySelector("video, .pic")) setTimeout(function () {
        if (el.classList.contains("is-error") && Math.round(feed.scrollTop / H) === +el.dataset.idx) step(1);
      }, 1200);
    }
    function item(it, idx) {
      var el = h("section", "short");
      el.dataset.idx = idx;
      var isVideo = it.short.kind === "video";
      // 1) orqa fon: shu kadrning o'zi (yoki poster) xira holda
      var bgSrc = isVideo ? (it.poster ? posterUrl(it, 720) : "") : "/media/short/" + it.short.id;
      var sbg = h("div", "sbg" + (bgSrc ? "" : " none"));
      if (bgSrc) sbg.style.backgroundImage = "url('" + bgSrc + "')";
      el.appendChild(sbg);
      // 2) o'rtadagi kadr
      var frame = h("div", "sframe");
      el._frame = frame;
      var media;
      if (isVideo) {
        media = document.createElement("video");
        media.setAttribute("playsinline", ""); media.setAttribute("webkit-playsinline", "");
        media.muted = shortsMuted; media.defaultMuted = shortsMuted; if (shortsMuted) media.setAttribute("muted", "");
        media.loop = true; media.preload = "metadata"; media.setAttribute("disableRemotePlayback", "");
        if (it.poster) media.poster = posterUrl(it, 720);
        media.dataset.src = "/media/short/" + it.short.id;
        media._toggle = function () {
          if (media.paused) { media.play(); el.classList.remove("is-paused"); }
          else { media.pause(); el.classList.add("is-paused"); }
        };
        media.onclick = function (e) { tapShort(e, el, media._toggle, function () { return likeB; }); };
        media.addEventListener("loadedmetadata", function () {
          if (media.videoWidth) { el._vw = media.videoWidth; el._vh = media.videoHeight; fit(el); }
        });
        media.addEventListener("waiting", function () { el.classList.add("is-loading"); });
        ["playing", "canplay"].forEach(function (ev) { media.addEventListener(ev, function () { el.classList.remove("is-loading", "is-error"); }); });
        media.addEventListener("error", function () {
          el.classList.remove("is-loading"); el.classList.add("is-error");
          if (media.src && !el._failed) { el._failed = 1; setTimeout(function () { try { media.load(); } catch (e) {} }, 1500); return; }   // bir marta o'zi qayta urinadi
          failShort(el);
        });
        media.addEventListener("timeupdate", function () {
          if (media.duration) prog.firstChild.style.transform = "scaleX(" + (media.currentTime / media.duration).toFixed(4) + ")";   // kenglik emas — transform (qayta hisoblashsiz)
        });
        el.classList.add("is-loading");
      } else {
        media = new Image(); media.className = "pic"; media.alt = it.title; media.decoding = "async";
        media.onload = function () { el._vw = media.naturalWidth; el._vh = media.naturalHeight; fit(el); el.classList.remove("is-loading"); };
        media.onerror = function () { el.classList.remove("is-loading"); el.classList.add("is-error"); };
        media.src = "/media/short/" + it.short.id;
        el.classList.add("is-loading");
      }
      frame.appendChild(media);
      if (!isVideo) media.onclick = function (e) { tapShort(e, el, null, function () { return likeB; }); };
      frame.appendChild(h("div", "fade"));
      frame.appendChild(h("div", "paused", [icon("play")]));
      frame.appendChild(h("div", "sspin"));
      var retry = h("button", "serr", [h("b", null, "Video yuklanmadi"), h("span", null, "Qayta urinish")]);
      retry.onclick = function (e) {
        e.stopPropagation();
        el.classList.remove("is-error"); el.classList.add("is-loading");
        if (isVideo) { media.src = "/media/short/" + it.short.id + "?r=" + Date.now(); media.load(); var pr = media.play(); if (pr && pr.catch) pr.catch(function () {}); }
        else media.src = "/media/short/" + it.short.id + "?r=" + Date.now();
      };
      frame.appendChild(retry);
      // vaqt chizig'i (siljitish mumkin)
      var prog = h("div", "sprog", [h("i")]);
      if (isVideo) {
        var seek = function (e) {
          var r = prog.getBoundingClientRect();
          if (media.duration) media.currentTime = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * media.duration;
        };
        prog.addEventListener("pointerdown", function (e) { e.stopPropagation(); seek(e); });
        frame.appendChild(prog);
      }
      var mb = h("button", "ibtn smute", [icon(shortsMuted ? "mute" : "vol")]);
      mb.setAttribute("aria-label", "Ovoz");
      mb.onclick = function (e) { e.stopPropagation(); haptic(); setMuted(!shortsMuted); };
      if (isVideo) frame.appendChild(mb);
      var saveB = h("button", isSaved(it) ? "on" : "", [h("span", "rnd", [icon("bookmark")]), "Saqlash"]);
      saveB.onclick = function () { saveB.classList.toggle("on", toggleSaved(it)); popBtn(saveB); };
      var shareB = h("button", null, [h("span", "rnd", [icon("share")]), "Ulashish"]);
      shareB.onclick = function () { share(it); };
      var infoB = h("button", null, [h("span", "rnd", [icon(CAT_ICON[it.cat] || "film")]), "Batafsil"]);
      infoB.onclick = function () { openSheet(it); };
      var likeCount = h("span", null, String(it.likes || 0));
      var likeB = h("button", null, [h("span", "rnd", ["👍"]), likeCount]);
      likeB.setAttribute("aria-label", "Yoqdi");
      likeB.onclick = function () {
        haptic("medium");
        if (guest()) { needLogin("⭐ Baho berish uchun hisobingizga kiring"); return; }
        api("/api/rate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: it.id, v: 1 }) })
          .then(function (r) {
            if (!r.ok) return toast("⚠️ Baho saqlanmadi");
            likeCount.textContent = r.likes; it.likes = r.likes; it.dislikes = r.dislikes;
            likeB.classList.toggle("on", r.mine === 1); notify("success");
          }).catch(function () { toast("⚠️ Ulanishda xatolik"); });
      };
      var sideBox = h("div", "side", [likeB, saveB, shareB, infoB]);
      var bits = [NAMES[it.cat] || "Kino"];
      if (it.year) bits.push(yr(it));
      if (it.genres && it.genres.length) bits.push(gname(it.genres[0]));
      if (it.parts > 1) bits.push(it.parts + " qism");
      if (it.code > 0) bits.push("Kod: " + it.code);
      var go = h("button", "go" + (it.locked ? " lock" : ""),
        [icon(it.locked ? "lock" : (PUB && it.cat !== "music" ? "send" : "play")), it.locked ? "Premium" : (it.cat === "music" ? "To'liq tinglash" : (PUB ? "Telegramda ko'rish" : "To'liq ko'rish"))]);
      go.onclick = function () { watch(it, go); };
      var bottomBox = h("div", "bottom", [it.premium ? h("span", "badge gold", "PREMIUM") : null,
        h("h3", null, it.title), h("div", "m", bits.join(" · ")), go]);
      el._ui = [sideBox, bottomBox];
      el.appendChild(frame);
      fit(el);
      shortsIO.observe(el);
      shortsLoadIO.observe(el);
      return el;
    }
    function load() {
      loading = true;
      api("/api/shorts?offset=" + offset).then(function (d) {
        loading = false;
        if (my !== reqId) return;
        if (!d.ok) { more = false; if (!offset) renderError(feed, d.reason); return; }
        if (!d.items.length && !offset) {
          feed.replaceChildren(emptyBox("clap", "Hozircha shorts yo'q", "Tez orada qisqa videolar qo'shiladi!"));
          more = false; return;
        }
        d.items.forEach(function (it) { feed.appendChild(item(it, feed.children.length)); });
        offset += d.items.length;
        more = d.more;
        if (startIdx && feed.children[startIdx]) {
          feed.children[startIdx].scrollIntoView({ block: "start" });
          startIdx = 0;
        }
      }).catch(function () { loading = false; if (my === reqId && !offset) renderError(feed, "network"); });
    }
    load();
  }

