  // ───── ikonkalar (inline SVG) ─────
  var P = {
    star: '<path d="M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
    chart: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18"/>',
    chat: '<path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z"/>',
    flag: '<path d="M5 21V4m0 0h11l-2 4 2 4H5"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    dots: '<circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>',
    reply: '<path d="M9 14L4 9l5-5M4 9h10a6 6 0 0 1 6 6v3"/>',
    ban: '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
    heart: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1-1.1a5.5 5.5 0 0 0-7.8 7.8l1 1.1L12 21l7.8-7.5 1-1.1a5.5 5.5 0 0 0 0-7.8z"/>',
    edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    moon: '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    send: '<path d="m22 2-7 20-4-9-9-4 20-7z"/><path d="M22 2 11 13"/>',
    home: '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    film: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M7 3v18M17 3v18M3 8h4M3 16h4M17 8h4M17 16h4M3 12h18"/>',
    smile: '<circle cx="12" cy="13" r="8"/><circle cx="6" cy="5.5" r="2.5"/><circle cx="18" cy="5.5" r="2.5"/><path d="M9 15.5c1.6 1.6 4.4 1.6 6 0"/><path d="M9.5 11h.01M14.5 11h.01"/>',
    music: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    bookmark: '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>',
    share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4"/>',
    play: '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.5-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5z"/>',
    chev: '<path d="m9 18 6-6-6-6"/>',
    lock: '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    x: '<path d="M18 6 6 18M6 6l12 12"/>',
    check: '<path d="m5 12 5 5 9-10"/>',
    clap: '<path d="M4 11v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8z"/><path d="m4 11-.9-3.6a1 1 0 0 1 .7-1.2L17 3l1 4z"/><path d="m8.5 4.8 2.4 3.7M13.4 3.9l2.4 3.7"/>',
    vol: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/>',
    mute: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m22 9-6 6M16 9l6 6"/>',
    pause: '<rect x="6" y="4.5" width="4" height="15" rx="1.2"/><rect x="14" y="4.5" width="4" height="15" rx="1.2"/>',
    next: '<path d="M5 5.5v13a1 1 0 0 0 1.5.86L16 13.7V18a1 1 0 0 0 2 0V6a1 1 0 0 0-2 0v4.3L6.5 4.64A1 1 0 0 0 5 5.5z"/>',
    prev: '<path d="M19 5.5v13a1 1 0 0 1-1.5.86L8 13.7V18a1 1 0 0 1-2 0V6a1 1 0 0 1 2 0v4.3l9.5-5.66A1 1 0 0 1 19 5.5z"/>',
    tv: '<rect x="2.5" y="6" width="19" height="13.5" rx="2.5"/><path d="m8 2.5 4 3.5 4-3.5M8 22h8"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    dice: '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 8h.01M16 8h.01M12 12h.01M8 16h.01M16 16h.01"/>',
    grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="1.8"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.8"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.8"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.8"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    gem: '<path d="M6 3h12l4 6-10 12L2 9z"/><path d="M2 9h20M12 21 8 9l4-6 4 6z"/>'
  };
  var CAT_ICON = { movie: "film", serial: "tv", cartoon: "smile", music: "music", video: "film" };
  function icon(name) {
    var s = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.innerHTML = P[name] || "";
    return s;
  }
  function h(tag, cls, kids) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    (kids == null ? [] : [].concat(kids)).forEach(function (k) {
      if (k == null || k === false) return;
      n.appendChild(typeof k === "string" || typeof k === "number" ? document.createTextNode(String(k)) : k);
    });
    return n;
  }
  var $ = function (id) { return document.getElementById(id); };

  function fmt(n) {
    n = +n || 0;
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(".0", "") + "M";
    if (n >= 1e4) return Math.floor(n / 1e3) + "K";
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(".0", "") + "K";
    return String(n);
  }
  function haptic(kind) { try { tg.HapticFeedback.impactOccurred(kind || "light"); } catch (e) {} }
  function notify(kind) { try { tg.HapticFeedback.notificationOccurred(kind); } catch (e) {} }
  var toastT;
  function toast(text) {
    var t = $("toast"); t.textContent = text; t.classList.add("on");
    clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove("on"); }, 2600);
  }
  var kidsMode = false;
  try { kidsMode = localStorage.getItem("kids") === "1"; } catch (e) {}
  document.body.classList.toggle("kids", kidsMode);
  function api(path, opts) {
    opts = opts || {};
    if (PUB && !SESSION) path = path.replace(/^\/api\//, "/pub/");
    opts.headers = Object.assign({ "X-Init-Data": initData }, SESSION ? { "X-Session": SESSION } : {}, kidsMode ? { "X-Kids": "1" } : {}, opts.headers || {});
    return fetch(path, opts).then(function (r) {
      return r.json().catch(function () { return { ok: false, reason: "error" }; });
    }).then(function (d) {
      if (SESSION && d && d.reason === "auth") {          // sessiya eskirgan — mehmon rejimiga qaytamiz
        dropSession(); setTimeout(function () { location.reload(); }, 50);
      }
      return d;
    });
  }
  function hue(str) { var x = 0; for (var i = 0; i < str.length; i++) x = (x * 31 + str.charCodeAt(i)) % 360; return x; }
  function pubPost(path, body) {                  // kirish so'rovlari: sessiyasiz, har doim /pub/
    return fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) })
      .then(function (r) { return r.json().catch(function () { return { ok: false, reason: "error" }; }); });
  }
  function needLogin(msg) { toast(msg); setTimeout(function () { show("login"); }, 500); }
  function yr(it) { return it.year ? (it.year_end && it.year_end > it.year ? it.year + "–" + it.year_end : String(it.year)) : ""; }
  function posterUrl(it, w) { return it.poster ? "/api/poster/" + it.id + "?v=" + it.poster + (w ? "&w=" + w : "") : null; }

