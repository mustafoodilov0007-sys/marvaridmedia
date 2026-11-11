(function () {
  "use strict";
  var tg = window.Telegram && window.Telegram.WebApp;
  var initData = tg ? tg.initData : "";
  // Telegram'dan tashqarida (📱 ilova yoki brauzer) — mehmon rejimi: katalog ochiq, ko'rish Telegram botda
  var PUB = !initData;
  // 🔐 brauzerda hisob bilan kirish (Telegram yoki Google): sessiya shu qurilmada saqlanadi
  var SESSION = "";
  try { if (PUB) SESSION = localStorage.getItem("sess") || ""; } catch (e) {}
  // 🛠 Xatolar haqida xabar: saytda JavaScript xatosi chiqsa, egalarga qisqa hisobot ketadi (shaxsiy ma'lumotsiz; bir sessiyada 4 tagacha)
  var errSent = {}, errCount = 0;
  function reportError(m, s, l, extra) {
    try {
      m = String(m || "").slice(0, 220);
      var k = m + "|" + (s || "") + "|" + (l || "");
      if (!m || errSent[k] || errCount >= 4) return;
      errSent[k] = 1; errCount++;
      var sc = document.querySelector('script[src*="/assets/app.js"]'), ver = sc ? (/v=([a-f0-9]+)/.exec(sc.src) || [])[1] : "";
      fetch("/pub/err", { method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
        body: JSON.stringify({ m: m, s: String(s || "").slice(0, 90), l: l || 0, v: (typeof current !== "undefined" ? current : ""), ver: ver || "", x: extra || "" }) }).catch(function () {});
    } catch (e) {}
  }
  window.addEventListener("error", function (e) {
    if (e.target && e.target !== window) return;                          // rasm/skript yuklanmadi — xato emas
    if (!e.filename || e.filename.indexOf(location.host) < 0) return;      // begona skript (kengaytma, reklama) — bizniki emas
    reportError(e.message, e.filename, e.lineno);
  });
  window.addEventListener("unhandledrejection", function (e) {
    var r = e.reason; reportError((r && (r.message || r)) || "Promise xatosi", "promise", 0);
  });
  var AUTHED = PUB && !!SESSION;              // /api/me javobida tasdiqlanadi; yaroqsiz bo'lsa — mehmonga qaytadi
  function guest() { return PUB && !AUTHED; }
  function dropSession() {
    SESSION = ""; AUTHED = false;
    try { localStorage.removeItem("sess"); } catch (e) {}
  }
  var APP = /MarvaridApp/.test(navigator.userAgent);
  // 🔎 SEO manzillar: /kino/123-nomi, /janr/comedy, /kinolar ... — qidiruv tizimlari uchun alohida sahifalar, odam uchun — shu sayt
  function pathInfo() {
    var p = location.pathname, m;
    if ((m = p.match(/^\/kino\/(\d{1,9})/))) return { k: m[1] };
    if ((m = p.match(/^\/janr\/([a-z]{3,20})$/))) return { view: "video", genre: m[1] };
    if ((m = p.match(/^\/kolleksiya\/(\d{1,9})/))) return { view: "col", colId: m[1] };
    if (p === "/kolleksiyalar") return { view: "cols" };
    var v = { "/kinolar": "movie", "/seriallar": "serial", "/multfilmlar": "cartoon" }[p];
    return v ? { view: v } : {};
  }
  function slugOf(t) { return String(t || "").toLowerCase().replace(/[ʻʼ'`’‘]/g, "").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60); }
  function moviePath(it) { return it.code > 0 ? "/kino/" + it.code + (slugOf(it.title) ? "-" + slugOf(it.title) : "") : "/?k=m" + (-it.code); }
  // 📲 oddiy brauzerda: ilova sifatida o'rnatish (PWA) — Telegram ichida kerak emas
  var installEv = null;
  var IOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
  var STANDALONE = !!((window.matchMedia && matchMedia("(display-mode: standalone)").matches) || navigator.standalone);
  window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); installEv = e; });
  // 📈 tahlil: mehmon (brauzer / o'rnatilgan ilova) sayt ochdi — manba bo'yicha, shaxsiy ma'lumotsiz, sessiyada bir marta
  if (PUB) {
    try {
      if (!sessionStorage.getItem("hit")) {
        sessionStorage.setItem("hit", "1");
        var hq = new URLSearchParams(location.search), hr = document.referrer || "";
        var hsrc = APP ? "apk" : hq.get("utm") || (/google|bing|yandex|duckduckgo/.test(hr) ? "qidiruv" : (hq.get("k") || pathInfo().k) ? "havola" : !hr ? "direct" : /t\.me|telegram/.test(hr) ? "telegram" : "boshqa");
        fetch("/pub/hit", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ src: hsrc }) }).catch(function () {});
      }
    } catch (e) {}
  }
  if (PUB && !APP && "serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("/sw.js").catch(function () {}); });
  }
  // CSS animatsiyani qayta boshlash — «void el.offsetWidth» (butun sahifani majburan qayta hisoblash, qotish sababi) o'rniga 2 kadr kutamiz
  function replayClass(el, cls, then) {
    if (!el) return;
    el.classList.remove(cls);
    requestAnimationFrame(function () { requestAnimationFrame(function () { el.classList.add(cls); if (then) then(); }); });
  }
  var me = { bot: "", brand: "Marvarid Media", channel: null };
  var NAMES = { movie: "Kino", serial: "Serial", cartoon: "Multfilm", music: "Musiqa", video: "Kino" };
  var PLURAL = { movie: "Kinolar", serial: "Seriallar", cartoon: "Multfilmlar", music: "Musiqalar", video: "Barcha kinolar" };

