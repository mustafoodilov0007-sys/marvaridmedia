  // ───── ✏️ admin: kinoni shu yerning o'zida tahrirlash ─────
  function adminBar(it) {
    var b = h("button", "btn", [icon("edit"), "Tahrirlash"]);
    b.onclick = function () { openEditor(it); };
    return h("div", "adminbar", [b]);
  }
  function openEditor(it) {
    var s = $("sheet");
    s.replaceChildren(h("div", "ed", [h("div", "note", "Yuklanmoqda...")]));
    api("/api/admin/movie?id=" + it.id).then(function (d) {
      if (!d.ok) { toast("⚠️ Ruxsat yo'q"); openSheet(it); return; }
      var m = d.movie, meta = d.meta, music = m.category === "music";
      var title = h("input"); title.value = m.title; title.maxLength = 200;
      var desc = h("textarea"); desc.value = m.description; desc.maxLength = 3000;
      var cat = document.createElement("select");
      [["movie", "Kino"], ["serial", "Serial"], ["cartoon", "Multfilm"]].forEach(function (o) { cat.appendChild(new Option(o[1], o[0])); });
      cat.value = m.category;
      var year = h("input"); year.type = "text"; year.inputMode = "numeric"; year.value = m.year ? (m.year_end && m.year_end > m.year ? m.year + "-" + m.year_end : m.year) : ""; year.placeholder = "2024 yoki 2012-2015";
      function sel(list, cur, empty) {
        var x = document.createElement("select"); x.appendChild(new Option(empty, ""));
        list.forEach(function (o) { x.appendChild(new Option(o.label, o.key)); }); x.value = cur || ""; return x;
      }
      var country = sel(meta.countries, m.country, "— tanlanmagan —");
      var lang = sel(meta.langs, m.lang, "— tanlanmagan —");
      var dur = h("input"); dur.type = "number"; dur.inputMode = "numeric"; dur.value = m.duration_min || ""; dur.placeholder = "Daqiqada: 145";
      var imdb = h("input"); imdb.inputMode = "decimal"; imdb.value = m.imdb || ""; imdb.placeholder = "Masalan: 7.9";
      var age = document.createElement("select"); age.appendChild(new Option("— ko'rsatilmasin —", "0"));
      (meta.ages || []).forEach(function (a) { age.appendChild(new Option(a + "+", String(a))); }); age.value = String(m.age || 0);
      var link = h("input"); link.type = "url"; link.value = m.group_link; link.placeholder = "https://t.me/...";
      var wurl = h("input"); wurl.type = "url"; wurl.value = m.watch_url || ""; wurl.placeholder = "https://sayt.uz/kino/123";
      function multi(list, chosen) {
        var box = h("div", "gchips"), on = chosen.slice(), chips = {};
        list.forEach(function (o) {
          var c = h("button", "gchip" + (on.indexOf(o.key) >= 0 ? " on" : ""), o.label); c.type = "button";
          c.onclick = function () {
            var i = on.indexOf(o.key); if (i >= 0) on.splice(i, 1); else on.push(o.key);
            c.classList.toggle("on", i < 0);
          };
          chips[o.key] = c;
          box.appendChild(c);
        });
        return { box: box, get: function () { return on; },
          set: function (keys) { on = keys.filter(function (k) { return chips[k]; }); Object.keys(chips).forEach(function (k) { chips[k].classList.toggle("on", on.indexOf(k) >= 0); }); } };
      }
      var gen = multi(meta.genres, m.genres), qual = multi(meta.qualities, m.quality);
      var prem = h("button", "gchip" + (m.premium ? " on" : ""), "💎 Premium"); prem.type = "button";
      var isPrem = m.premium; prem.onclick = function () { isPrem = !isPrem; prem.classList.toggle("on", isPrem); };
      function f(label, node) { return h("label", "f", [label, node]); }
      // 🌐 TMDB dan avtomatik to'ldirish: asl nomi bilan qidiriladi, admin to'g'ri variantni tanlaydi, maydonlar to'ladi (saqlanmaydi)
      var tmBox = h("div", "tmbox hidden"), tmRes = h("div", "tmres");
      var tmQ = h("input"); tmQ.placeholder = "Asl (inglizcha) nomi: Avengers Endgame 2019";
      var tmGo = h("button", "btn primary", "Qidirish"); tmGo.type = "button";
      var tmDescChk = h("input"); tmDescChk.type = "checkbox";
      var tmBtn = h("button", "btn soft tmbtn", "🌐 TMDB dan to'ldirish"); tmBtn.type = "button";
      tmBox.appendChild(h("div", "row2 tmrow", [tmQ, tmGo]));
      tmBox.appendChild(h("label", "tmchk", [tmDescChk, " Izohni ham olish (hozirgisini almashtiradi)"]));
      tmBox.appendChild(tmRes);
      function tmFill(d) {
        if (d.year) year.value = d.year;
        if (d.duration_min) dur.value = d.duration_min;
        if (d.imdb) imdb.value = d.imdb;
        if (d.age) age.value = String(d.age);
        if (d.country) country.value = d.country;
        if (d.genres && d.genres.length) gen.set(d.genres);
        if (d.category && cat.value !== d.category) cat.value = d.category;
        if (d.overview && (tmDescChk.checked || !desc.value.trim())) desc.value = d.overview;
        tmBox.classList.add("hidden");
        toast("✅ To'ldirildi — tekshirib, «Saqlash» ni bosing");
      }
      function tmSearch() {
        var q = tmQ.value.trim();
        if (!q) { toast("Asl (inglizcha) nomini yozing"); return; }
        var ym = q.match(/\b(19[2-9]\d|20[0-4]\d)\s*$/), yr = ym ? ym[1] : "";
        if (ym) q = q.slice(0, ym.index).trim();
        tmRes.replaceChildren(h("div", "note", "Qidirilmoqda..."));
        api("/api/admin/tmdb?q=" + encodeURIComponent(q) + (yr ? "&year=" + yr : "")).then(function (r) {
          if (!r.ok) { tmRes.replaceChildren(h("div", "note", r.reason === "not_configured" ? "TMDB ulanmagan: Railway → Variables → TMDB_API_KEY" : "⚠️ " + (r.message || "Xatolik"))); return; }
          if (!r.items.length) { tmRes.replaceChildren(h("div", "note", "Topilmadi. Boshqacha yozib ko'ring.")); return; }
          tmRes.replaceChildren();
          r.items.forEach(function (x) {
            var img = h("div", "tmimg"); if (x.poster) img.style.backgroundImage = "url('" + x.poster + "')";
            var it = h("button", "tmitem", [img, h("div", "tmtx", [h("b", null, x.title + (x.year ? " (" + x.year + ")" : "")),
              h("span", null, (x.kind === "tv" ? "Serial" : "Kino") + (x.original && x.original !== x.title ? " · " + x.original : "")), h("em", null, x.overview || "")])]);
            it.type = "button";
            it.onclick = function () {
              tmRes.replaceChildren(h("div", "note", "Yuklanmoqda..."));
              api("/api/admin/tmdb?kind=" + x.kind + "&id=" + x.id).then(function (dd) { if (dd.ok) tmFill(dd.data); else toast("⚠️ " + (dd.message || "Xatolik")); })
                .catch(function () { toast("⚠️ Ulanishda xatolik"); });
            };
            tmRes.appendChild(it);
          });
        }).catch(function () { tmRes.replaceChildren(h("div", "note", "⚠️ Ulanishda xatolik")); });
      }
      tmGo.onclick = tmSearch;
      tmQ.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); tmSearch(); } });
      tmBtn.onclick = function () { tmBox.classList.toggle("hidden"); if (!tmBox.classList.contains("hidden")) tmQ.focus(); };
      var save = h("button", "btn primary", "Saqlash");
      var cancel = h("button", "btn soft", "Bekor");
      var del = h("button", "btn danger", "🗑");
      del.setAttribute("aria-label", "O'chirish");
      cancel.onclick = function () { openSheet(it); };
      save.onclick = function () {
        var body = { id: m.id, title: title.value, description: desc.value, premium: isPrem };
        if (!music) Object.assign(body, { category: cat.value, year: year.value, country: country.value, lang: lang.value,
          group_link: link.value, watch_url: wurl.value, genres: gen.get(), quality: qual.get(), duration_min: dur.value, age: age.value, imdb: imdb.value });
        save.disabled = true;
        api("/api/admin/save", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
          .then(function (r) {
            save.disabled = false;
            if (!r.ok) { toast({ title: "⚠️ Nom bo'sh bo'lmasin", year: "⚠️ Yil noto'g'ri", link: "⚠️ Havola https:// bilan boshlansin", wlink: "⚠️ Sayt linki https:// bilan boshlansin",
              imdb: "⚠️ IMDb 0 dan 10 gacha bo'lsin", duration: "⚠️ Davomiylik noto'g'ri" }[r.reason] || "⚠️ Saqlanmadi"); return; }
            toast("✅ Saqlandi"); closeSheet(); show(current);
          }).catch(function () { save.disabled = false; toast("⚠️ Internet xatosi"); });
      };
      del.onclick = function () {
        if (!confirm("«" + m.title + "» butunlay o'chirilsinmi? Bu qaytarilmaydi.")) return;
        api("/api/admin/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: m.id }) })
          .then(function (r) { if (r.ok) { toast("🗑 O'chirildi"); closeSheet(); show(current); } else toast("⚠️ O'chirilmadi"); });
      };
      var kids = [h("h3", null, "✏️ Tahrirlash · Kod " + m.code), music ? null : h("div", "tmwrap", [tmBtn, tmBox]), f("Nomi", title), f("Izoh", desc)];
      if (!music) kids.push(h("div", "row2", [f("Turi", cat), f("Yili", year)]), h("div", "row2", [f("Davlat", country), f("Til", lang)]),
        h("div", "row2", [f("Davomiyligi (daq)", dur), f("IMDb reyting", imdb)]), f("Yosh cheklovi", age),
        f("Janrlar", gen.box), f("Sifat", qual.box), f("Serial guruh havolasi", link), f("Saytdagi link («Saytda ko'rish»)", wurl));
      kids.push(h("div", "gchips", [prem]), h("div", "eactions", [cancel, save, del]));
      s.replaceChildren(h("div", "ed", kids));
      s.scrollTop = 0;
    }).catch(function () { toast("⚠️ Internet xatosi"); openSheet(it); });
  }

  // ───── 🎬 treyler (admin shorts sifatida qo'shgan video) ─────
  function openTrailer(it) {
    closeTrailer(true);
    var box = $("trailer");
    var v = document.createElement("video");
    v.controls = true; v.autoplay = true; v.playsInline = true; v.setAttribute("playsinline", "");
    v.preload = "metadata";
    if (it.poster) v.poster = posterUrl(it, 720);
    v.src = "/media/short/" + it.trailer;
    var close = h("button", "ibtn tclose", [icon("x")]);
    close.setAttribute("aria-label", "Yopish");
    close.onclick = function () { closeTrailer(); };
    var go = h("button", "btn primary", [icon(it.locked ? "lock" : "play"), it.locked ? "Premium" : "Kinoni ko'rish"]);
    go.onclick = function () { closeTrailer(); watch(it, go); };
    box.replaceChildren(h("div", "tbox", [v, h("div", "tbar", [h("b", null, it.title), go])]), close);
    box.classList.add("on");
    trailerOpen = true;
    stopHero();
    updateBack();
    var pr = v.play(); if (pr && pr.catch) pr.catch(function () {});
    setTimeout(function () { try { close.focus({ preventScroll: true }); } catch (e) {} }, 60);
  }
  function closeTrailer(silent) {
    var box = $("trailer");
    if (!trailerOpen) return;
    var v = box.querySelector("video");
    if (v) { try { v.pause(); v.removeAttribute("src"); v.load(); } catch (e) {} }
    box.classList.remove("on");
    box.replaceChildren();
    trailerOpen = false;
    if (!silent) { if (current === "home" && !sheetOpen) restartHero(); updateBack(); }
  }

  function updateBack() {
    if (PUB || !tg || !tg.BackButton) return;
    if (sheetOpen || trailerOpen || current !== "home") tg.BackButton.show(); else tg.BackButton.hide();
  }
  function goBack() {
    if (trailerOpen) { closeTrailer(); return true; }
    if (sheetOpen) { closeSheet(); return true; }
    if (current !== "home") { show("home"); return true; }
    return false;
  }
  if (tg && tg.BackButton) tg.BackButton.onClick(function () { goBack(); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { goBack(); return; }
    if (e.key === "Tab" && sheetOpen && !trailerOpen) {   // oyna ochiq: Tab oyna ichida aylansin
      var f = $("sheet").querySelectorAll("button:not([disabled]), [tabindex='0'], select, a[href]");
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  });

  function watch(it, btn) {
    haptic("medium");
    rememberWatch(it);
    if (guest() || (PUB && !me.tg)) {            // mehmon yoki Google hisobi: Telegram botda ochiladi
      if (!me.bot) { toast("⏳ Biroz kuting..."); return; }
      toast("📲 Telegram ochilmoqda...");
      openLink(botLink(it));
      return;
    }
    btn.disabled = true;
    var old = Array.prototype.slice.call(btn.childNodes);
    btn.replaceChildren("Yuborilmoqda...");
    api("/api/watch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: it.id }) })
      .then(function (res) {
        btn.disabled = false; btn.replaceChildren.apply(btn, old);
        var msg = {
          sub: "📢 Avval kanallarga obuna bo'ling — bot chatida tugmalar chiqdi.",
          premium: "💎 Bu Premium kontent — bot chatida Premium olish tugmasi bor.",
          blocked: "🤖 Avval botga /start bosing, so'ng qayta urinib ko'ring.",
          flood: "⏳ Juda tez! Biroz kuting.",
          not_found: "😔 Bu kontent o'chirilgan.",
          auth: "🔐 Saytni bot ichidan qayta oching."
        }[res.reason];
        if (res.ok) {
          notify("success");
          toast("✅ Botga yuborildi! Chatni oching.");
          setTimeout(function () { if (tg && !PUB) tg.close(); else { closeSheet(); openLink("https://t.me/" + me.bot); } }, 1100);
        } else if (res.reason === "sub" || res.reason === "premium") {
          notify("warning");
          toast(msg);
          setTimeout(function () { if (tg && !PUB) tg.close(); else { closeSheet(); openLink("https://t.me/" + me.bot); } }, 1800);
        } else {
          notify("error");
          toast(msg || "⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.");
        }
      })
      .catch(function () { btn.disabled = false; btn.replaceChildren.apply(btn, old); toast("⚠️ Ulanishda xatolik."); });
  }

