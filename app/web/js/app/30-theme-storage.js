  // ───── mavzu (yorug' / qorong'i) ─────
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    $("bTheme").replaceChildren(icon(t === "dark" ? "sun" : "moon"));
    var c = t === "dark" ? "#0b0a0d" : "#f8f5ef";
    if (!PUB) { try { tg.setHeaderColor(c); tg.setBackgroundColor(c); tg.setBottomBarColor && tg.setBottomBarColor(c); } catch (e) {} }
    try { window.MarvaridApp && window.MarvaridApp.setTheme(t); } catch (e) {}
  }
  var theme = store.get("theme") || (!PUB && tg && tg.colorScheme === "light" ? "light" : "dark");
  applyTheme(theme);
  $("bTheme").onclick = function () { haptic(); theme = theme === "dark" ? "light" : "dark"; store.set("theme", theme); applyTheme(theme); };
  // Telegram mavzusi o'zgarsa (va foydalanuvchi o'zi tanlamagan bo'lsa) — shunga moslashamiz
  if (!PUB && tg && tg.onEvent) {
    try { tg.onEvent("themeChanged", function () {
      if (store.get("theme")) return;
      theme = tg.colorScheme === "light" ? "light" : "dark"; applyTheme(theme);
    }); } catch (e) {}
  }

  // ───── saqlanganlar (Telegram CloudStorage + zaxira localStorage) ─────
  var saved = {};
  try { saved = JSON.parse(store.get("saved") || "{}") || {}; } catch (e) { saved = {}; }
  var cloud = !PUB && tg && tg.CloudStorage && tg.isVersionAtLeast && tg.isVersionAtLeast("6.9") ? tg.CloudStorage : null;
  function snap(it) {
    return { id: it.id, code: it.code, cat: it.cat, title: it.title, poster: it.poster, parts: it.parts,
             views: it.views, premium: it.premium, locked: it.locked, year: it.year, year_end: it.year_end, desc: (it.desc || "").slice(0, 300),
             genres: it.genres || [], country: it.country || "", lang: it.lang || "", quality: it.quality || "", t: Date.now() };
  }
  function gname(g) { return (g.label || "").replace(/^\S+\s/, ""); }
  function score(it) {
    var n = (it.likes || 0) + (it.dislikes || 0);
    return n >= 3 ? Math.round(it.likes * 100 / n) : null;
  }
  function fmtDur(sec) {
    var m = Math.round((sec || 0) / 60);
    if (!m) return "";
    var hh = Math.floor(m / 60), mm = m % 60;
    return hh ? hh + " soat" + (mm ? " " + mm + " daq" : "") : mm + " daq";
  }
  function countryName(it) { return it.country ? it.country.split(" ").slice(1).join(" ") : ""; }
  function ageBadge(it) { return it.age ? h("span", "agebadge", it.age + "+") : null; }
  // IMDb va o'zimizning (tomoshabinlar bahosi asosida) reyting nishonlari
  function ratingBadges(it) {
    var box = h("div", "rbadges");
    if (it.imdb) box.appendChild(h("span", "rb", [h("b", "imdb", "IMDb"), h("em", null, it.imdb)]));
    var sc = score(it);
    if (sc !== null) box.appendChild(h("span", "rb", [h("b", "own", "M"), h("em", null, (sc / 10).toFixed(1))]));
    return box.childNodes.length ? box : null;
  }
  function shortMeta(it) {
    var bits = [];
    var sc = score(it);
    if (sc !== null) bits.push("👍 " + sc + "%");
    if (it.year) bits.push(yr(it));
    if (it.genres && it.genres.length) bits.push(gname(it.genres[0]));
    if (!bits.length) bits.push(NAMES[it.cat] || "Kino");
    return bits.slice(0, 2).join(" · ");
  }
  // 🕘 ko'rilganlar: Telegram'da serverda (bot va saytdan), ilova/brauzerda shu qurilmada
  var localHist = [];
  try { localHist = JSON.parse(store.get("hist") || "[]") || []; } catch (e) { localHist = []; }
  function rememberWatch(it) {
    if (it.cat === "music") return;
    localHist = [snap(it)].concat(localHist.filter(function (x) { return x.id !== it.id; })).slice(0, 15);
    store.set("hist", JSON.stringify(localHist));
  }
  function persistSaved() { store.set("saved", JSON.stringify(saved)); }
  function animOnce(el, cls, ms) {   // CSS-animatsiyani qayta ishga tushiradi (sinf qo'yib, keyin olib tashlaydi)
    if (!el) return;
    el.classList.remove(cls); void el.offsetWidth; el.classList.add(cls);
    setTimeout(function () { el.classList.remove(cls); }, ms || 600);
  }
  function popBtn(el) {          // 🔖 bosilganda «pop» animatsiyasini qayta ishga tushiradi
    if (!el) return;
    el.classList.remove("pop"); void el.offsetWidth; el.classList.add("pop");
    setTimeout(function () { el.classList.remove("pop"); }, 600);
  }
  function toggleSaved(it) {
    var key = "b" + it.id;
    if (saved[key]) {
      delete saved[key];
      if (cloud) cloud.removeItem(key);
      toast("Saqlanganlardan olib tashlandi");
    } else {
      saved[key] = snap(it);
      if (cloud) cloud.setItem(key, JSON.stringify(saved[key]).slice(0, 4000));
      toast("🔖 Saqlanganlarga qo'shildi");
    }
    haptic("medium");
    persistSaved();
    return !!saved[key];
  }
  function isSaved(it) { return !!saved["b" + it.id]; }
  if (cloud) {
    cloud.getKeys(function (err, keys) {
      if (err || !keys) return;
      keys = keys.filter(function (k) { return /^b\d+$/.test(k); });
      if (!keys.length) return;
      cloud.getItems(keys, function (err2, vals) {
        if (err2 || !vals) return;
        Object.keys(vals).forEach(function (k) { try { if (vals[k]) saved[k] = JSON.parse(vals[k]); } catch (e) {} });
        persistSaved();
        if (current === "saved") show("saved");
      });
    });
  }

  // ───── qurilma imkoniyatlari ─────
  var HOVER = !!(window.matchMedia && matchMedia("(hover: hover) and (pointer: fine)").matches);
  var REDUCE = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
  var MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"];
  function fmtDate(ts) {
    if (!ts) return "";
    var d = new Date(ts * 1000);
    return d.getDate() + "-" + MONTHS[d.getMonth()] + " " + d.getFullYear();
  }
  function langCode(it) {
    var m = /(O'zbek|Rus|Ingliz)/.exec(it.lang || "");
    return m ? { "O'zbek": "UZ", "Rus": "RU", "Ingliz": "EN" }[m[1]] : "";
  }
  function topQuality(it) {
    var m = /(4K|2K|1080p|720p|480p|360p)/.exec(it.quality || "");
    return m ? m[1] : "";
  }
  function onKey(el, fn) {   // div orqali yasalgan tugmalar uchun klaviatura (Enter / bo'sh joy)
    el.setAttribute("role", "button");
    el.tabIndex = 0;
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fn(e); }
    });
  }

