  // ───── 📅 Hafta natijalari (profil), 🎬 Kunning kinosi (bosh sahifa), 📴 oflayn holat, 🎙 ovozli qidiruv ─────
  function weekCard(page) {
    if (guest()) return;
    var box = h("section", "wcard hidden");
    page.appendChild(box);
    api("/api/week").then(function (d) {
      if (!d || !d.ok) return;
      var hrs = d.minutes >= 60 ? Math.floor(d.minutes / 60) + " soat" + (d.minutes % 60 ? " " + (d.minutes % 60) + " daq" : "") : (d.minutes ? d.minutes + " daq" : "");
      var head = h("div", "whead", [h("b", null, "📅 Shu hafta"), h("span", null, "oxirgi 7 kun")]);
      if (!d.watched) {
        var go = h("button", "wempty", [h("b", null, "Bu hafta hali kino ko'rmadingiz"), h("span", null, "«Siz uchun» tavsiyalarini ochish →")]);
        go.type = "button"; go.onclick = function () { haptic(); show("foryou"); };
        box.replaceChildren(head, go);
      } else {
        var big = h("div", "wbig", [h("b", null, String(d.watched)), h("span", null, d.watched === 1 ? "ta kino ko'rdingiz" : "ta kino ko'rdingiz"),
          hrs ? h("em", null, "≈ " + hrs) : null]);
        var chips = h("div", "wchips", [
          d.top && d.top.length ? h("span", "wchip hot", "🔥 " + d.top.join(", ")) : null,
          d.likes ? h("span", "wchip", "👍 " + d.likes) : null,
          d.comments ? h("span", "wchip", "💬 " + d.comments) : null,
          d.saved ? h("span", "wchip", "🔖 " + d.saved) : null].filter(Boolean));
        box.replaceChildren(head, big, chips);
      }
      box.classList.remove("hidden");
    }).catch(function () {});
  }

  // 🎬 «Kunning kinosi»: bosh sahifadagi katta karta (kanaldagi tanlov bilan bir xil)
  function dailyCard(it) {
    var pic = posterNode(it, 360);
    if (it.premium) pic.appendChild(h("span", "tag r", "PREMIUM")); else if (it.free) pic.appendChild(h("span", "tag r free", "BEPUL"));
    var meta = [NAMES[it.cat] || "Kino", it.year ? yr(it) : "", it.genres && it.genres[0] ? gname(it.genres[0]) : "", fmtDur(it.duration)].filter(Boolean).join(" · ");
    var go = h("button", "btn primary", [icon(it.locked ? "lock" : "play"), it.locked ? "Premium" : "Ko'rish"]);
    go.onclick = function (e) { e.stopPropagation(); watch(it, go); };
    var more = h("button", "btn soft", "Batafsil");
    more.onclick = function (e) { e.stopPropagation(); openSheet(it, false, pic); };
    var body = h("div", "dbody", [h("small", null, "📅 KUNNING KINOSI"), h("b", null, it.title), h("span", "dmeta", meta),
      ratingBadges(it), h("div", "dbtns", [go, more])]);
    var box = h("div", "dcard", [pic, body]);
    box.setAttribute("role", "button"); box.tabIndex = 0;
    box.onclick = function () { haptic(); openSheet(it, false, pic); };
    return box;
  }

  // 📴 Internet yo'q: oq ekran o'rniga — saqlanganlar (qurilmada bor) va qayta urinish
  function renderOffline(view) {
    var items = Object.keys(saved).map(function (k) { return saved[k]; }).sort(function (a, b) { return (b.t || 0) - (a.t || 0); });
    var retry = h("button", "btn primary", [icon("refresh"), "Qayta urinish"]);
    retry.onclick = function () { haptic(); show(current === "shorts" ? "home" : current, { nopush: true }); };
    var kids = [h("div", "offline", [h("span", "ofico", [icon("live")]), h("h2", null, "Internet yo'q"),
      h("p", null, items.length ? "Aloqa tiklanguncha saqlangan kinolaringizni ko'rishingiz mumkin." : "Aloqani tekshiring — tiklanishi bilan sahifa o'zi ochiladi."), retry])];
    if (items.length) {
      var grid = h("div", "grid");
      items.slice(0, 24).forEach(function (it) { grid.appendChild(card(it)); });
      kids.push(h("h3", "group-title", "🔖 Saqlanganlar"), grid);
    }
    view.replaceChildren(h("div", "page", kids));
    var back = function () { window.removeEventListener("online", back); if (view.isConnected && view.querySelector(".offline")) show(current, { nopush: true }); };
    window.addEventListener("online", back);
  }
  window.addEventListener("offline", function () { toast("📴 Internet uzildi"); });
  window.addEventListener("online", function () { toast("✅ Aloqa tiklandi"); });

  // 🎙 ovozli qidiruv (Chrome/Android/Safari: SpeechRecognition) — qo'llab-quvvatlanmasa tugma ko'rinmaydi
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  function voiceButton(input, onResult) {
    if (!SR) return null;
    var btn = h("button", "vbtn", [icon("mic")]);
    btn.type = "button"; btn.setAttribute("aria-label", "Ovozli qidiruv");
    var rec = null, on = false;
    function stop() { on = false; btn.classList.remove("on"); try { rec && rec.stop(); } catch (e) {} }
    btn.onclick = function (e) {
      e.preventDefault(); e.stopPropagation(); haptic();
      if (on) { stop(); return; }
      try {
        rec = new SR();
        var L = window.LANG || "uz";
        rec.lang = { ru: "ru-RU", en: "en-US" }[L] || "uz-UZ";
        rec.interimResults = true; rec.maxAlternatives = 1; rec.continuous = false;
        rec.onstart = function () { on = true; btn.classList.add("on"); toast("🎙 Gapiring..."); };
        rec.onresult = function (ev) {
          var txt = "", fin = false;
          for (var i = ev.resultIndex; i < ev.results.length; i++) { txt += ev.results[i][0].transcript; if (ev.results[i].isFinal) fin = true; }
          input.value = txt.trim();
          if (fin) { stop(); onResult(txt.trim()); }
        };
        rec.onerror = function (ev) {
          stop();
          toast(ev.error === "not-allowed" || ev.error === "service-not-allowed" ? "🎙 Mikrofonga ruxsat bering" :
                ev.error === "no-speech" ? "🎙 Ovoz eshitilmadi" : "🎙 Ovozli qidiruv hozir ishlamayapti");
        };
        rec.onend = function () { on = false; btn.classList.remove("on"); };
        rec.start();
      } catch (err) { stop(); toast("🎙 Ovozli qidiruv hozir ishlamayapti"); }
    };
    return btn;
  }
