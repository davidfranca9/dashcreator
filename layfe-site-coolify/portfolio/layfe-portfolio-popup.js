/* Popup de captação do portfólio da Layfe.
   Aparece ~15s depois de entrar (uma vez por visita) e, ao enviar, cria um
   lead na Prospecção dela (app.thecreatorsclub.com.br). Autônomo: injeta o
   próprio CSS/HTML, tudo com prefixo lfp- para não colidir com o site. */
(function () {
  "use strict";
  if (window.__lfpLoaded) return;
  window.__lfpLoaded = true;

  var ENDPOINT = "https://app.thecreatorsclub.com.br/api/portfolio-lead/";
  var DELAY_MS = 15000;

  function stored(store, key) { try { return store.getItem(key); } catch (e) { return null; } }
  function keep(store, key, val) { try { store.setItem(key, val); } catch (e) {} }

  // Já converteu antes, ou já viu nesta visita: não mostra.
  if (stored(localStorage, "lfp_sent") || stored(sessionStorage, "lfp_shown")) return;

  var CSS = ""
    + "#lfp-overlay{position:fixed;inset:0;z-index:2147483000;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(10,20,16,.55);-webkit-backdrop-filter:blur(3px);backdrop-filter:blur(3px);font-family:'Inter',system-ui,-apple-system,sans-serif}"
    + "#lfp-overlay.lfp-on{display:flex;animation:lfpFade .25s ease}"
    + "@keyframes lfpFade{from{opacity:0}to{opacity:1}}"
    + ".lfp-card{position:relative;width:100%;max-width:420px;background:#f5f1e8;border:1px solid rgba(10,36,99,.14);box-shadow:0 30px 80px -20px rgba(8,20,50,.55);padding:30px clamp(22px,5vw,34px);max-height:92vh;overflow:auto}"
    + ".lfp-x{position:absolute;top:12px;right:14px;background:none;border:none;font-size:24px;line-height:1;color:#8a7d6b;cursor:pointer;padding:4px}"
    + ".lfp-x:hover{color:#0a2463}"
    + ".lfp-eyebrow{font-size:10px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:#c9956a}"
    + ".lfp-title{font-family:'Playfair Display',Georgia,serif;font-size:24px;line-height:1.15;color:#0a2463;margin:8px 0 6px;font-weight:600}"
    + ".lfp-sub{font-size:13.5px;color:#5a5345;line-height:1.5;margin-bottom:18px}"
    + ".lfp-field{margin-bottom:12px}"
    + ".lfp-field label{display:block;font-size:10px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#8a7d6b;margin-bottom:5px}"
    + ".lfp-field input,.lfp-field textarea{width:100%;border:1px solid rgba(10,36,99,.22);background:#fff;padding:11px 12px;font:inherit;font-size:14px;color:#12224a;border-radius:0}"
    + ".lfp-field input:focus,.lfp-field textarea:focus{outline:none;border-color:#c9956a}"
    + ".lfp-field textarea{resize:vertical;min-height:64px}"
    + ".lfp-hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden}"
    + ".lfp-send{width:100%;margin-top:6px;border:1px solid #0a2463;background:#0a2463;color:#f5f1e8;padding:14px;font:inherit;font-size:12.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;cursor:pointer;transition:background .2s}"
    + ".lfp-send:hover{background:#16306e}"
    + ".lfp-send:disabled{opacity:.6;cursor:default}"
    + ".lfp-legal{font-size:11px;color:#8a7d6b;text-align:center;margin-top:12px}"
    + ".lfp-ok{text-align:center;padding:16px 0}"
    + ".lfp-ok .lfp-check{width:56px;height:56px;border-radius:50%;background:rgba(45,122,95,.14);color:#1a5240;display:flex;align-items:center;justify-content:center;margin:0 auto 14px;font-size:28px}"
    + ".lfp-err{font-size:12.5px;color:#b84040;margin-bottom:10px;display:none}";

  var HTML = ""
    + '<div class="lfp-card" role="dialog" aria-modal="true" aria-labelledby="lfp-title">'
    + '  <button type="button" class="lfp-x" data-lfp-close aria-label="Fechar">&times;</button>'
    + '  <div data-lfp-form-wrap>'
    + '    <div class="lfp-eyebrow">Vamos criar juntas</div>'
    + '    <h2 class="lfp-title" id="lfp-title">Quer a Layfe na sua marca?</h2>'
    + '    <p class="lfp-sub">Deixa seu contato que ela te chama pra conversar sobre o seu projeto.</p>'
    + '    <div class="lfp-err" data-lfp-err></div>'
    + '    <form data-lfp-form novalidate>'
    + '      <div class="lfp-field"><label for="lfp-name">Seu nome</label><input id="lfp-name" name="name" type="text" autocomplete="name" required></div>'
    + '      <div class="lfp-field"><label for="lfp-company">Marca / empresa</label><input id="lfp-company" name="company" type="text" autocomplete="organization"></div>'
    + '      <div class="lfp-field"><label for="lfp-whats">WhatsApp</label><input id="lfp-whats" name="whatsapp" type="tel" inputmode="tel" autocomplete="tel" placeholder="(00) 00000-0000" required></div>'
    + '      <div class="lfp-field"><label for="lfp-insta">Instagram da marca</label><input id="lfp-insta" name="instagram" type="text" placeholder="@suamarca"></div>'
    + '      <div class="lfp-field"><label for="lfp-msg">Conta rápido o que precisa</label><textarea id="lfp-msg" name="message" rows="2"></textarea></div>'
    + '      <div class="lfp-hp"><label>Não preencha<input type="text" name="site" tabindex="-1" autocomplete="off"></label></div>'
    + '      <button type="submit" class="lfp-send" data-lfp-send>Quero conversar</button>'
    + '      <p class="lfp-legal">Seu contato vai direto pra Layfe. Sem spam.</p>'
    + '    </form>'
    + '  </div>'
    + '  <div class="lfp-ok" data-lfp-ok style="display:none">'
    + '    <div class="lfp-check">&#10003;</div>'
    + '    <h2 class="lfp-title" style="margin-top:0">Recebido!</h2>'
    + '    <p class="lfp-sub" style="margin-bottom:0">A Layfe vai te chamar no WhatsApp pra conversar. Obrigada. 💛</p>'
    + '  </div>'
    + '</div>';

  function build() {
    var style = document.createElement("style");
    style.textContent = CSS;
    document.head.appendChild(style);

    var overlay = document.createElement("div");
    overlay.id = "lfp-overlay";
    overlay.innerHTML = HTML;
    document.body.appendChild(overlay);

    var closed = false;
    function open() {
      if (closed) return;
      overlay.classList.add("lfp-on");
      keep(sessionStorage, "lfp_shown", "1");
    }
    function close() {
      closed = true;
      overlay.classList.remove("lfp-on");
      keep(sessionStorage, "lfp_shown", "1");
    }

    overlay.querySelectorAll("[data-lfp-close]").forEach(function (b) { b.addEventListener("click", close); });
    overlay.addEventListener("click", function (e) { if (e.target === overlay) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });

    var form = overlay.querySelector("[data-lfp-form]");
    var err = overlay.querySelector("[data-lfp-err]");
    var sendBtn = overlay.querySelector("[data-lfp-send]");

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      err.style.display = "none";
      var data = {
        name: form.name.value.trim(),
        company: form.company.value.trim(),
        whatsapp: form.whatsapp.value.trim(),
        instagram: form.instagram.value.trim(),
        message: form.message.value.trim(),
        site: form.site.value.trim()
      };
      var digits = (data.whatsapp.match(/\d/g) || []).length;
      if (data.name.length < 2 || digits < 8) {
        err.textContent = "Preencha seu nome e um WhatsApp válido com DDD.";
        err.style.display = "block";
        return;
      }
      sendBtn.disabled = true;
      sendBtn.textContent = "Enviando...";
      fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: JSON.stringify(data)
      })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function (res) {
          if (!res || res.ok !== true) return Promise.reject();
          keep(localStorage, "lfp_sent", "1");
          overlay.querySelector("[data-lfp-form-wrap]").style.display = "none";
          overlay.querySelector("[data-lfp-ok]").style.display = "block";
          setTimeout(close, 4500);
        })
        .catch(function () {
          sendBtn.disabled = false;
          sendBtn.textContent = "Quero conversar";
          err.textContent = "Não consegui enviar agora. Tenta de novo em instantes.";
          err.style.display = "block";
        });
    });

    setTimeout(open, DELAY_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
