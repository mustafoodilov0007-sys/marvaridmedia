  // ───── 🎵 saytda musiqa tinglash ─────
  var Player = (function () {
    var audio = new Audio();
    audio.preload = "none";
    var queue = [], idx = -1, req = 0;
    var self = { current: null };
    function el(id) { return document.getElementById(id); }
    function setPlayingFlag() {
      var on = !audio.paused;
      el("plPlay").replaceChildren(icon(on ? "pause" : "play"));
      document.querySelectorAll(".card[data-id]").forEach(function (c) {
        var mine = self.current && +c.dataset.id === self.current.id;
        c.classList.toggle("playing", !!mine);
        c.classList.toggle("paused", !!mine && !on);
      });
      try { window.MarvaridApp && window.MarvaridApp.setPlaying && window.MarvaridApp.setPlaying(on); } catch (e) {}
      if ("mediaSession" in navigator) navigator.mediaSession.playbackState = on ? "playing" : "paused";
    }
    function split(title) {
      var p = (title || "").split(" - ");
      return p.length > 1 ? { artist: p[0], song: p.slice(1).join(" - ") } : { artist: me.brand, song: title };
    }
    function show(it) {
      var nm = split(it.title);
      el("plTitle").textContent = nm.song;
      el("plSub").textContent = nm.artist;
      var cover = el("plCover");
      cover.replaceChildren(icon("music"));
      if (it.poster) {
        var img = new Image(); img.alt = "";
        img.onload = function () { cover.replaceChildren(img); };
        img.src = posterUrl(it, 360);
      }
      document.body.classList.add("has-player");
      if ("mediaSession" in navigator) {
        try {
          navigator.mediaSession.metadata = new MediaMetadata({ title: nm.song, artist: nm.artist, album: me.brand,
            artwork: it.poster ? [{ src: location.origin + posterUrl(it, 360), sizes: "320x320", type: "image/jpeg" }] : [] });
        } catch (e) {}
      }
    }
    self.play = function (it, list) {
      // navbatda faqat ochiq qo'shiqlar (Premium qulflilari o'tkazib yuboriladi)
      queue = (list && list.length ? list : [it]).filter(function (x) {
        return x.cat === "music" && (!x.locked || x.id === it.id);
      });
      idx = Math.max(0, queue.findIndex(function (x) { return x.id === it.id; }));
      load(queue[idx]);
    };
    self.playFrom = function (it, cardEl) {
      haptic();
      if (self.current && self.current.id === it.id) { self.toggle(); return; }
      var list = [];
      if (cardEl && cardEl.parentNode) {
        Array.prototype.forEach.call(cardEl.parentNode.children, function (c) { if (c._item) list.push(c._item); });
      }
      self.play(it, list);
    };
    function load(it) {
      if (!it) return;
      if (it.locked) { toast("💎 Bu qo'shiq Premium a'zolar uchun"); openSheet(it); return; }
      var my = ++req;
      self.current = it;
      show(it);
      audio.pause();
      el("plPlay").replaceChildren(h("span", null, "…"));
      setPlayingFlag();
      api("/api/play", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: it.id }) })
        .then(function (res) {
          if (my !== req) return;
          if (res.ok) {
            audio.src = res.url;
            var p = audio.play();
            if (p && p.catch) p.catch(function () { setPlayingFlag(); });
            return;
          }
          var msg = {
            premium: "💎 Bu qo'shiq Premium a'zolar uchun",
            sub: "📢 Tinglash uchun avval kanallarga obuna bo'ling — bot chatida tugmalar chiqdi",
            big: "📦 Fayl katta — botga yuboramiz",
            not_found: "😔 Bu qo'shiq o'chirilgan"
          }[res.reason] || "⚠️ Ijro etib bo'lmadi";
          toast(msg);
          if (res.reason === "big") watch(it, el("plPlay"));
          self.close();
        })
        .catch(function () { if (my === req) { toast("⚠️ Ulanishda xatolik"); setPlayingFlag(); } });
    }
    self.toggle = function () {
      if (!self.current) return;
      if (audio.paused) { var p = audio.play(); if (p && p.catch) p.catch(function () {}); } else audio.pause();
    };
    self.next = function () { if (idx < queue.length - 1) { idx++; load(queue[idx]); } else { audio.pause(); audio.currentTime = 0; } };
    self.prev = function () {
      if (audio.currentTime > 3 || idx <= 0) { audio.currentTime = 0; return; }
      idx--; load(queue[idx]);
    };
    self.close = function () {
      audio.pause(); req++;
      self.current = null;
      document.body.classList.remove("has-player");
      setPlayingFlag();
    };
    audio.addEventListener("play", setPlayingFlag);
    audio.addEventListener("pause", setPlayingFlag);
    audio.addEventListener("ended", function () { self.next(); });
    audio.addEventListener("error", function () { if (self.current && audio.src) { toast("⚠️ Qo'shiqni yuklab bo'lmadi"); setPlayingFlag(); } });
    audio.addEventListener("timeupdate", function () {
      var d = audio.duration;
      el("plFill").style.width = d ? (audio.currentTime / d * 100) + "%" : "0";
    });
    function seek(e) {
      var r = el("plBar").getBoundingClientRect();
      var x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
      if (audio.duration) audio.currentTime = Math.max(0, Math.min(1, x / r.width)) * audio.duration;
    }
    el("plBar").addEventListener("click", seek);
    el("plBar").addEventListener("touchstart", seek, { passive: true });
    el("plPlay").onclick = function () { haptic(); self.toggle(); };
    el("plNext").onclick = function () { haptic(); self.next(); };
    el("plPrev").onclick = function () { haptic(); self.prev(); };
    el("plClose").onclick = function () { haptic(); self.close(); };
    // nomi yoki muqovasi bosilsa — batafsil oyna (u yerda «botga yuborish» tugmasi bor)
    document.querySelector(".pl-meta").onclick = el("plCover").onclick = function () {
      if (self.current) openSheet(self.current);
    };
    el("plPlay").appendChild(icon("play"));
    el("plNext").appendChild(icon("next"));
    el("plPrev").appendChild(icon("prev"));
    el("plClose").appendChild(icon("x"));
    if ("mediaSession" in navigator) {
      try {
        navigator.mediaSession.setActionHandler("play", self.toggle);
        navigator.mediaSession.setActionHandler("pause", self.toggle);
        navigator.mediaSession.setActionHandler("nexttrack", self.next);
        navigator.mediaSession.setActionHandler("previoustrack", self.prev);
      } catch (e) {}
    }
    return self;
  })();

