  // ───── ▦ kartalar: telefonda 2 ustun (katta poster) yoki 3 ustun ─────
  (function colsInit() { try { if (localStorage.getItem("cols") === "3") document.documentElement.classList.add("cols3"); } catch (e) {} })();
  function setCols(n) {
    try { localStorage.setItem("cols", String(n)); } catch (e) {}
    document.documentElement.classList.toggle("cols3", n === 3);
  }
  // ───── ⚡ tezlik: sekin telefonlar uchun yengil rejim ─────
  // Qiymat: localStorage "perf" = "lite" (yoqilgan) | "full" (o'chiq) | bo'sh (avto: qurilma va haqiqiy tezlikka qarab)
  function liteInit() {
    var pref = ""; try { pref = localStorage.getItem("perf") || ""; } catch (e) {}
    var on = pref === "lite";
    if (!pref) {
      var con = navigator.connection || {}, mem = navigator.deviceMemory || 8, cores = navigator.hardwareConcurrency || 8;
      on = !!(con.saveData || mem <= 4 || (/Android/i.test(navigator.userAgent) && cores <= 6));
    }
    document.documentElement.classList.toggle("lite", on);
    return on;
  }
  function setPerf(v) {                       // "lite" | "full" | "" — sahifani yangilab qo'llaydi
    try { if (v) localStorage.setItem("perf", v); else localStorage.removeItem("perf"); } catch (e) {}
    location.reload();
  }
  // Avto: aylantirish paytida kadrlar sekin bo'lsa (30 dan ortig'i 28 ms dan uzoq) — o'zi yengil rejimga o'tadi va eslab qoladi
  (function monitor() {
    var pref = ""; try { pref = localStorage.getItem("perf") || ""; } catch (e) {}
    if (pref || LITE || !window.requestAnimationFrame) return;
    var samples = [], last = 0, running = false, idle = 0, done = false;
    function loop(t) {
      if (done) return;
      if (last) samples.push(t - last);
      last = t;
      if (samples.length >= 60) {
        var slow = samples.filter(function (x) { return x > 28; }).length;
        if (slow / samples.length > 0.3) {
          done = true;
          try { localStorage.setItem("perf", "lite"); } catch (e) {}
          document.documentElement.classList.add("lite"); LITE = true;
          toast("⚡ Telefon sekin ishlayotgani sezildi — yengil rejim yoqildi (Profil → Tezlik)");
          return;
        }
        if (samples.length >= 120) { done = true; return; }          // yetarli kuzatildi — hammasi joyida
      }
      if (performance.now() - idle < 160) requestAnimationFrame(loop); else { running = false; last = 0; }
    }
    window.addEventListener("scroll", function () {
      idle = performance.now();
      if (!running && !done) { running = true; last = 0; requestAnimationFrame(loop); }
    }, { passive: true });
  })();
