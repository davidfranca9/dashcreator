/* Métricas de cliques/visitas — envia eventos anônimos ao app Django.
   Uso no site:  <script src="https://app.thecreatorsclub.com.br/static/studio/track.js" data-site="layfe" defer></script>
   Marque CTAs com  data-track="nome-do-evento"  para registrar cliques. */
(function () {
  "use strict";
  var ENDPOINT = "https://app.thecreatorsclub.com.br/api/track/";

  var script = document.currentScript;
  if (!script) {
    var all = document.getElementsByTagName("script");
    script = all[all.length - 1];
  }
  var SITE = (script && script.getAttribute("data-site")) || "";
  if (!SITE) return;

  function uid() {
    try {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    } catch (e) {}
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  }
  function read(store, key) { try { return store.getItem(key); } catch (e) { return null; } }
  function write(store, key, val) { try { store.setItem(key, val); } catch (e) {} }

  var visitor = read(localStorage, "_m_vid");
  if (!visitor) { visitor = uid(); write(localStorage, "_m_vid", visitor); }
  var session = read(sessionStorage, "_m_sid");
  if (!session) { session = uid(); write(sessionStorage, "_m_sid", session); }

  function send(kind, label) {
    var data = {
      site: SITE,
      kind: kind,
      // Inclui o #tag: é o que identifica de qual perfil/story do Instagram
      // a visita veio. O navegador não manda o "#" pro servidor sozinho,
      // por isso enviamos aqui explicitamente.
      path: location.pathname + location.search + location.hash,
      label: (label || "").slice(0, 80),
      visitor: visitor,
      session: session,
      referrer: document.referrer || ""
    };
    var body = JSON.stringify(data);
    try {
      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: "text/plain" });
        if (navigator.sendBeacon(ENDPOINT, blob)) return;
      }
    } catch (e) {}
    try {
      fetch(ENDPOINT, {
        method: "POST",
        body: body,
        headers: { "Content-Type": "text/plain" },
        keepalive: true,
        mode: "cors"
      });
    } catch (e) {}
  }

  // Visita
  send("pageview", "");

  // Cliques em elementos com data-track (usa o mais próximo na árvore)
  document.addEventListener("click", function (e) {
    var el = e.target && e.target.closest ? e.target.closest("[data-track]") : null;
    if (!el) return;
    send("click", el.getAttribute("data-track") || "");
  }, true);
})();
