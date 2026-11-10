  // ───── ✨ «Sizning yilingiz»: profil sahifasidagi statistika kartasi ─────
  function yearCard(page) {
    var local = guest();
    var box = h("section", "ycard hidden");
    page.appendChild(box);
    function paint(st) {
      if (!st || !st.watched) { box.classList.add("hidden"); return; }
      var gl = (st.genres || []).map(function (g) { return g.label; });
      var tiles = h("div", "ytiles", [
        h("div", null, [h("b", null, String(st.watched)), h("span", null, "kino ko'rdingiz")]),
        st.hours ? h("div", null, [h("b", null, String(st.hours)), h("span", null, "soat tomosha")]) : null,
        h("div", null, [h("b", null, String(st.likes || 0)), h("span", null, "👍 bergansiz")]),
        h("div", null, [h("b", null, String(st.comments || 0)), h("span", null, "izoh yozdingiz")])
      ].filter(Boolean));
      var kids = [h("div", "yhead", [h("b", null, "✨ " + (st.year || new Date().getFullYear()) + "-yilingiz"), h("span", null, "Marvarid Media bilan")]), tiles];
      if (gl.length) kids.push(h("div", "ygen", [h("span", null, "Sevimli janrlaringiz:"), h("div", "gpills", (st.genres || []).map(function (g) { return h("span", "gpill", g.label); }))]));
      var sh = h("button", "btn primary yshare", [icon("send"), "Ulashish"]);
      sh.type = "button";
      sh.onclick = function () {
        haptic();
        var text = "🎬 Men Marvarid Media'da " + st.watched + " ta kino ko'rdim" + (gl.length ? "! Sevimli janrlarim: " + gl.join(", ") : "!") + " Siz ham sinab ko'ring:";
        var url = location.origin + "/";
        if (!PUB && tg && tg.openTelegramLink) { try { tg.openTelegramLink("https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(text)); return; } catch (e) {} }
        if (navigator.share) { navigator.share({ text: text, url: url }).catch(function () {}); return; }
        openLink("https://t.me/share/url?url=" + encodeURIComponent(url) + "&text=" + encodeURIComponent(text));
      };
      kids.push(sh);
      box.replaceChildren.apply(box, kids);
      box.classList.remove("hidden");
    }
    if (!local) {
      api("/api/mystats").then(function (d) { if (d && d.ok) paint(d); }).catch(function () {});
    } else {                                    // mehmon: faqat shu qurilmadagi tarix
      var freq = {};
      localHist.forEach(function (x) { (x.genres || []).forEach(function (g) { freq[g.key || g] = freq[g.key || g] || { n: 0, label: g.label || String(g) }; freq[g.key || g].n++; }); });
      var top = Object.keys(freq).sort(function (a, b) { return freq[b].n - freq[a].n; }).slice(0, 3).map(function (k) { return { key: k, label: freq[k].label }; });
      paint({ watched: localHist.length, genres: top, likes: 0, comments: 0, year: new Date().getFullYear() });
    }
  }
