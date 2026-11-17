  // ───── 📚 Ro'yxatlarim · 👥 Tomoshabinlar ham ko'rdi · 🖼 izohni rasm qilib ulashish ─────
  function post(url, body) {
    return api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  }
  function listLink(token) { return location.origin + "/?l=" + token; }
  function shareList(title, token) {
    var link = listLink(token), text = "📚 «" + title + "» — kinolar ro'yxati · " + (me.brand || "Marvarid Media");
    if (PUB && navigator.share) { navigator.share({ title: title, text: text, url: link }).catch(function () {}); return; }
    openLink("https://t.me/share/url?url=" + encodeURIComponent(link) + "&text=" + encodeURIComponent(text));
  }

  // kino oynasidagi «Ro'yxatga» tugmasi: ro'yxatlar tanlanadi yoki yangisi yaratiladi
  function listBtn(it) {
    if (it.cat === "music") return null;
    var b = h("button", "btn soft half", [icon("plus"), "Ro'yxatga"]);
    b.onclick = function (e) {
      e.stopPropagation(); haptic();
      if (guest()) { toast("Ro'yxat yaratish uchun hisobingizga kiring"); show("login"); return; }
      pickList(it);
    };
    return b;
  }
  function pickList(it) {
    var ov = h("div", "lpick-ov"), box = h("div", "lpick");
    function close() { ov.remove(); }
    ov.onclick = function (e) { if (e.target === ov) close(); };
    box.appendChild(h("b", "lp-t", "📚 Ro'yxatga qo'shish"));
    var body = h("div", "lp-body", h("div", "note", "Yuklanmoqda..."));
    box.appendChild(body); ov.appendChild(box); document.body.appendChild(ov);
    function load() {
      api("/api/lists?movie=" + it.id).then(function (d) {
        if (!d.ok) { body.replaceChildren(h("div", "note", "⚠️ Xatolik")); return; }
        body.replaceChildren();
        d.lists.forEach(function (l) {
          var row = h("button", "lp-row" + (l.has ? " on" : ""), [h("span", null, l.title), h("em", null, l.has ? "✓" : l.n + " ta")]);
          row.onclick = function () {
            haptic();
            post("/api/list", { act: l.has ? "remove" : "add", id: l.id, movie: it.id }).then(function (r) {
              if (!r.ok) { toast(r.reason === "limit" ? "Ro'yxat to'lgan" : "⚠️ Xatolik"); return; }
              toast(l.has ? "Ro'yxatdan olindi" : "✅ «" + l.title + "» ga qo'shildi"); close();
            });
          };
          body.appendChild(row);
        });
        var inp = h("input"); inp.placeholder = "Yangi ro'yxat nomi"; inp.maxLength = 60;
        var add = h("button", "btn primary", "Yaratish");
        add.onclick = function () {
          var t = inp.value.trim(); if (!t) { inp.focus(); return; }
          post("/api/list", { act: "create", title: t, movie: it.id }).then(function (r) {
            if (r.ok) { toast("✅ Ro'yxat yaratildi"); close(); } else toast(r.reason === "limit" ? "Ro'yxatlar soni chegarasiga yetdingiz" : "⚠️ Xatolik");
          });
        };
        body.appendChild(h("div", "lp-new", [inp, add]));
      }).catch(function () { body.replaceChildren(h("div", "note", "⚠️ Ulanishda xatolik")); });
    }
    load();
  }

  // 📚 mening ro'yxatlarim
  function renderLists(view, my) {
    var page = h("div", "page narrow", [h("h1", null, "📚 Ro'yxatlarim")]);
    view.replaceChildren(page);
    if (guest()) { page.appendChild(emptyBox("bookmark", "Kirish kerak", "Ro'yxat yaratish uchun hisobingizga kiring.")); return; }
    var sk = h("div", "clist", [1, 2, 3].map(function () { var r = h("div", "crow sk"); r.style.height = "56px"; return r; })); page.appendChild(sk);
    api("/api/lists").then(function (d) {
      sk.remove();
      if (my !== reqId) return;
      if (!d.ok) return renderError(view, d.reason);
      if (!d.lists.length) { page.appendChild(emptyBox("bookmark", "Hali ro'yxat yo'q", "Kino sahifasida «Ro'yxatga» tugmasini bosing — o'z kolleksiyangizni yarating va do'stlarga ulashing.")); return; }
      var box = h("div", "clist");
      d.lists.forEach(function (l) {
        var b = h("button", "crow", [h("b", null, l.title), h("span", null, l.n + " ta kino"), icon("chev")]);
        b.onclick = function () { haptic(); show("ulist", { t: l.token }); };
        box.appendChild(b);
      });
      page.appendChild(box);
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }

  // 📚 bitta ro'yxat (havola orqali hamma ko'ra oladi)
  function renderUList(view, token, my) {
    var page = h("div", "page", [h("h1", null, "📚 Ro'yxat")]);
    view.replaceChildren(page);
    var sk = h("div", "grid", skeletonCards(6)); page.appendChild(sk);
    api("/api/list?t=" + encodeURIComponent(token)).then(function (d) {
      sk.remove();
      if (my !== reqId) return;
      if (!d.ok) { page.replaceChildren(emptyBox("bookmark", "Ro'yxat topilmadi", "Havola eskirgan yoki ro'yxat o'chirilgan.")); return; }
      page.replaceChildren(h("h1", null, "📚 " + d.title));
      page.appendChild(h("p", "lead", (d.owner ? d.owner + " tuzgan · " : "") + d.items.length + " ta kino"));
      var tools = h("div", "ltools");
      var sh = h("button", "btn soft", [icon("share"), "Ulashish"]);
      sh.onclick = function () { haptic(); shareList(d.title, d.token); };
      tools.appendChild(sh);
      if (d.mine) {
        var rn = h("button", "btn soft", "✏️ Nomi");
        rn.onclick = function () {
          var t = (prompt("Yangi nom", d.title) || "").trim(); if (!t) return;
          post("/api/list", { act: "rename", id: d.id, title: t }).then(function (r) { if (r.ok) show("ulist", { t: d.token, nopush: true }); });
        };
        var del = h("button", "btn soft danger", "🗑 O'chirish");
        tapTwice(del, "Aniqmi?", function () {
          post("/api/list", { act: "delete", id: d.id }).then(function (r) { if (r.ok) { toast("🗑 O'chirildi"); show("lists"); } });
        });
        var pub = h("button", "btn soft" + (d.public ? " on" : ""), d.public ? "🌍 Hammaga ko'rinadi" : "🔒 Faqat havola bilan");
        pub.onclick = function () {
          haptic();
          post("/api/list", { act: "public", id: d.id, on: !d.public }).then(function (r) {
            if (!r.ok) return;
            d.public = !d.public; pub.classList.toggle("on", d.public);
            pub.textContent = d.public ? "🌍 Hammaga ko'rinadi" : "🔒 Faqat havola bilan";
            toast(d.public ? "🌍 Ro'yxat bosh sahifadagi «Ommabop»ga qo'shiladi (3+ kino bo'lsa)" : "🔒 Endi faqat havola bilan ochiladi");
          });
        };
        tools.appendChild(pub); tools.appendChild(rn); tools.appendChild(del);
      } else if (d.admin) {
        var adel = h("button", "btn soft danger", "🗑 O'chirish (admin)");
        tapTwice(adel, "Aniqmi?", function () {
          post("/api/list", { act: "delete", id: d.id }).then(function (r) { if (r.ok) { toast("🗑 O'chirildi"); show("home"); } });
        });
        tools.appendChild(adel);
      }
      page.appendChild(tools);
      if (!d.items.length) { page.appendChild(emptyBox("film", "Ro'yxat bo'sh", "Kino sahifasidagi «Ro'yxatga» tugmasi bilan kino qo'shing.")); return; }
      var grid = h("div", "grid");
      d.items.forEach(function (it) {
        var c = card(it);
        if (d.mine) {
          var x = h("button", "lrm", "✕"); x.setAttribute("aria-label", "Ro'yxatdan olib tashlash");
          x.onclick = function (e) {
            e.stopPropagation(); e.preventDefault(); haptic();
            post("/api/list", { act: "remove", id: d.id, movie: it.id }).then(function (r) { if (r.ok) c.remove(); });
          };
          c.appendChild(x);
        }
        grid.appendChild(c);
      });
      page.appendChild(grid);
    }).catch(function () { if (my === reqId) renderError(view, "network"); });
  }

  // 👥 «Tomoshabinlar ham ko'rdi»
  function alsoRail(box, it) {
    api("/api/also?id=" + it.id).then(function (d) {
      if (!d.ok || !d.items.length || !box.isConnected) return;
      var list = h("div", "rail");
      d.items.forEach(function (x) { list.appendChild(card(x)); });
      box.replaceChildren(h("div", "sec-head", [h("h2", null, "👥 Tomoshabinlar ham ko'rdi")]), list);
    }).catch(function () {});
  }

  // 🖼 izohni rasm kartochka qilib ulashish
  function shareComment(c, it, btn) {
    var url = "/og/c/" + c.id + ".jpg", link = location.origin + moviePath(it);
    var text = "💬 «" + it.title + "» haqida — " + (me.brand || "Marvarid Media");
    function fallback() {
      if (PUB && navigator.share) { navigator.share({ title: it.title, text: text, url: link }).catch(function () {}); return; }
      openLink("https://t.me/share/url?url=" + encodeURIComponent(link) + "&text=" + encodeURIComponent(text));
    }
    if (btn) btn.disabled = true;
    fetch(url).then(function (r) { if (!r.ok) throw 0; return r.blob(); }).then(function (bl) {
      if (btn) btn.disabled = false;
      var f = new File([bl], "izoh.jpg", { type: "image/jpeg" });
      if (navigator.canShare && navigator.canShare({ files: [f] })) { navigator.share({ files: [f], text: text + "\n" + link }).catch(function () {}); return; }
      var a = document.createElement("a"); a.href = URL.createObjectURL(bl); a.download = "izoh.jpg";
      document.body.appendChild(a); a.click(); a.remove(); toast("🖼 Rasm yuklab olindi");
    }).catch(function () { if (btn) btn.disabled = false; fallback(); });
  }

  // 🔥 bosh sahifa: ommabop ro'yxatlar
  function popularListsRail(lists) {
    if (!lists || !lists.length) return null;
    var sec = h("section", "section"), rail = h("div", "rail cols");
    sec.appendChild(h("div", "sec-head", [h("h2", null, "🔥 Ommabop ro'yxatlar")]));
    lists.forEach(function (l) {
      var strip = h("div", "cstrip");
      (l.covers || []).slice(0, 4).forEach(function (cv) {
        var im = new Image(); im.alt = ""; im.loading = "lazy"; im.decoding = "async"; im.src = posterUrl(cv, 360); strip.appendChild(im);
      });
      var b = h("button", "colcard", [strip, h("b", null, l.title), h("span", null, (l.owner ? l.owner + " · " : "") + l.n + " ta kino")]);
      b.type = "button"; b.onclick = function () { haptic(); show("ulist", { t: l.token }); };
      rail.appendChild(b);
    });
    sec.appendChild(h("div", "railwrap", [rail]));
    return sec;
  }
