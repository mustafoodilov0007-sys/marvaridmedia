  // ───── 📺 Qismlar: mavsum tanlash + qism kartalari. Qism bosilsa — aynan shu qism botga (chatga) yuboriladi ─────
  function epPad(n) { return n < 10 ? "0" + n : String(n); }
  function epSend(it, p, card) {
    haptic("medium");
    card.classList.add("sending");
    setTimeout(function () { card.classList.remove("sending"); }, 1700);
    watch(it, document.createElement("button"), p.id);          // watch() natijani (toast, botni ochish) o'zi ko'rsatadi
  }
  function episodesSection(it) {
    var wrap = h("div", "epsec");
    var skel = [];
    for (var k = 0; k < 8; k++) skel.push(h("div", "ep sk", [h("span", "epthumb"), h("span", "epinfo", [h("b", null, " ")])]));
    wrap.appendChild(h("div", "eps", skel));
    api("/api/parts?id=" + it.id).then(function (d) {
      if (!d || !d.ok || !d.parts || !d.parts.length) {
        wrap.replaceChildren(h("div", "epempty", "Qismlar hozircha topilmadi."));
        return;
      }
      build(d);
    }).catch(function () { wrap.replaceChildren(h("div", "epempty", "⚠️ Qismlarni yuklab bo'lmadi. Internetni tekshiring.")); });

    function build(d) {
      var by = {}, seaList = d.seasons.map(function (s) { return s.n; });
      d.parts.forEach(function (p) { (by[p.season] = by[p.season] || []).push(p); });
      var lastNo = d.last || 0;
      var nextPart = lastNo ? (d.parts.filter(function (p) { return p.no > lastNo; })[0] || null) : null;
      var lastPart = lastNo ? d.parts.filter(function (p) { return p.no === lastNo; })[0] : null;
      var cur = (nextPart || lastPart || d.parts[0]).season;
      var seen = lastNo ? d.parts.filter(function (p) { return p.no <= lastNo; }).length : 0;

      var head = h("div", "ephead", [
        h("div", "epttl", [h("h3", null, "Qismlar"),
          h("span", null, (d.multi ? seaList.length + " mavsum · " : "") + d.parts.length + " qism")]),
        seen ? h("div", "epprog", [h("span", null, seen + " / " + d.parts.length + " ko'rilgan"),
          h("div", "epbar", [h("i")])]) : null]);
      if (seen) head.querySelector(".epbar i").style.transform = "scaleX(" + Math.min(1, seen / d.parts.length).toFixed(3) + ")";
      var pills = null, grid = h("div", "eps");
      var hint = h("p", "epnote", it.locked ? "Bu serial Premium a'zolar uchun — qism bosilsa, bot Premium olish tugmasini chiqaradi."
        : "Qism ustiga bosing — bot aynan shu qismni chatga yuboradi.");

      function paintPills() {
        if (!pills) return;
        Array.prototype.forEach.call(pills.children, function (b) { b.classList.toggle("on", +b.dataset.n === cur); });
      }
      function paintGrid() {
        var list = by[cur] || [], dense = list.length > 24;
        grid.className = "eps" + (dense ? " dense" : "");
        grid.replaceChildren.apply(grid, list.map(function (p, i) { return epCard(p, i, dense); }));
      }
      function epCard(p, i, dense) {
        var isSeen = lastNo && p.no <= lastNo, isNext = nextPart && nextPart.id === p.id;
        var label = p.title || (p.ep + "-qism");
        var b = h("button", "ep" + (isSeen ? " seen" : "") + (isNext ? " next" : "") + (it.locked ? " lock" : ""));
        b.type = "button";
        b.style.setProperty("--i", Math.min(i, 14));
        b.setAttribute("aria-label", it.title + " — " + label);
        b.title = label;
        if (dense) {
          b.appendChild(h("span", "epn", String(p.ep)));
          if (isSeen) b.appendChild(h("i", "epdot", [icon("check")]));
          else if (it.locked) b.appendChild(h("i", "epdot lk", [icon("lock")]));
        } else {
          var th = h("span", "epthumb"), u = posterUrl(it, 360);
          if (u) { th.style.backgroundImage = "url('" + u + "')"; th.style.backgroundPosition = "center " + (6 + (i * 23) % 58) + "%"; }
          else th.style.background = "linear-gradient(135deg, hsl(" + (24 + hue(it.title || "") % 22) + ",45%,30%), #14110c)";
          th.appendChild(h("span", "epno", epPad(p.ep)));
          if (isNext) th.appendChild(h("span", "epchip", lastNo ? "KEYINGI" : "BOSHLASH"));
          else if (isSeen) th.appendChild(h("span", "epchip done", [icon("check"), "Ko'rilgan"]));
          th.appendChild(h("span", "epplay", [icon(it.locked ? "lock" : "play")]));
          b.appendChild(th);
          b.appendChild(h("span", "epinfo", [h("b", null, label),
            h("em", null, [fmtDur(p.dur), d.multi ? p.season + "-mavsum" : ""].filter(Boolean).join(" · ") || "Ko'rish")]));
        }
        b.onclick = function () { epSend(it, p, b); };
        return b;
      }
      if (d.multi) {
        pills = h("div", "epsea");
        seaList.forEach(function (n) {
          var cnt = d.seasons.filter(function (x) { return x.n === n; })[0].count;
          var pb = h("button", "sp", [n + "-mavsum", h("em", null, String(cnt))]);
          pb.type = "button"; pb.dataset.n = n;
          pb.onclick = function () { if (cur === n) return; haptic(); cur = n; paintPills(); paintGrid(); };
          pills.appendChild(pb);
        });
      }
      paintPills(); paintGrid();
      wrap.replaceChildren.apply(wrap, [head, pills, grid, hint].filter(Boolean));
      var onEl = pills && pills.querySelector(".on");
      if (onEl && pills) pills.scrollLeft = Math.max(0, onEl.offsetLeft - 16);
    }
    return wrap;
  }
