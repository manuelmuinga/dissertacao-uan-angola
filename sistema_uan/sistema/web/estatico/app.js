// Sistema UAN – comportamento da interface (JavaScript nativo, sem bibliotecas).
// Tudo é melhoria progressiva: sem JavaScript, as páginas e os formulários continuam a funcionar.
(function () {
  "use strict";

  var reduzirMovimento = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function cada(seletor, fn, raiz) {
    Array.prototype.forEach.call((raiz || document).querySelectorAll(seletor), fn);
  }

  // ---------- menu compacto (ecrãs estreitos) ----------
  var lateral = document.querySelector(".lateral");
  var alternar = document.querySelector(".menu-alternar");
  if (lateral && alternar) {
    var definirMenu = function (aberto) {
      lateral.classList.toggle("aberto", aberto);
      alternar.setAttribute("aria-expanded", aberto ? "true" : "false");
      alternar.setAttribute("aria-label", aberto ? "Fechar o menu" : "Abrir o menu");
    };
    alternar.addEventListener("click", function () { definirMenu(!lateral.classList.contains("aberto")); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && lateral.classList.contains("aberto")) { definirMenu(false); alternar.focus(); }
    });
    document.addEventListener("click", function (e) {
      if (lateral.classList.contains("aberto") && !lateral.contains(e.target)) definirMenu(false);
    });
    window.addEventListener("resize", function () { if (window.innerWidth > 960) definirMenu(false); });
  }

  // ---------- faixas: entrada animada (CSS) e saída suave das confirmações ----------
  function fecharFaixa(faixa) {
    if (!faixa || faixa.classList.contains("a-sair")) return;
    faixa.style.maxHeight = faixa.offsetHeight + "px";
    // força o cálculo antes de animar a altura
    void faixa.offsetHeight;
    faixa.classList.add("a-sair");
    faixa.style.maxHeight = "0px";
    faixa.style.marginBottom = "0px";
    faixa.style.paddingTop = "0px";
    faixa.style.paddingBottom = "0px";
    setTimeout(function () { if (faixa.parentNode) faixa.parentNode.removeChild(faixa); }, reduzirMovimento ? 0 : 350);
  }
  // As confirmações ("Decisão gravada.") desaparecem sozinhas; avisos e erros ficam até o utilizador sair.
  cada('.faixa.ok[role="status"]', function (f) {
    var t = setTimeout(function () { fecharFaixa(f); }, 6000);
    f.addEventListener("mouseenter", function () { clearTimeout(t); });
  });
  // Retira ?aviso= do endereço, para a mensagem não voltar ao recarregar a página.
  if (window.history && history.replaceState && /[?&]aviso=/.test(location.search)) {
    var q = location.search.replace(/([?&])aviso=[^&]*(&|$)/, function (m, a, b) { return b ? a : ""; });
    history.replaceState(null, "", location.pathname + (q === "?" ? "" : q) + location.hash);
  }

  // ---------- fila: atalhos de teclado ----------
  // J/K ou setas: item seguinte/anterior · 1-4: decisão · N: escrever nota
  var itens = Array.prototype.slice.call(document.querySelectorAll(".item[data-id]"));
  var actual = 0;
  function focar(i) {
    if (!itens.length) return;
    actual = Math.max(0, Math.min(itens.length - 1, i));
    itens.forEach(function (el, j) { el.classList.toggle("focado", j === actual); });
    itens[actual].focus({ preventScroll: true });
    itens[actual].scrollIntoView({ block: "nearest", behavior: reduzirMovimento ? "auto" : "smooth" });
  }
  itens.forEach(function (el, i) { el.addEventListener("click", function () { if (actual !== i) focar(i); }); });
  if (itens.length) focar(0);
  document.addEventListener("keydown", function (e) {
    if (!itens.length || e.ctrlKey || e.metaKey || e.altKey) return;
    var alvo = e.target;
    if (alvo && (alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.tagName === "SELECT")) {
      if (e.key === "Escape") { alvo.blur(); focar(actual); }
      return;
    }
    var k = e.key.toLowerCase();
    if (k === "j" || k === "arrowdown") { e.preventDefault(); focar(actual + 1); }
    else if (k === "k" || k === "arrowup") { e.preventDefault(); focar(actual - 1); }
    else if (k === "n") {
      var nota = itens[actual].querySelector("input[name=nota]");
      if (nota) { e.preventDefault(); nota.focus(); }
    } else if (["1", "2", "3", "4"].indexOf(k) >= 0) {
      var botao = itens[actual].querySelector("button[data-tecla='" + k + "']");
      if (botao) { e.preventDefault(); botao.click(); }
    }
  });

  // ---------- formulários: confirmação e estado "a enviar" ----------
  cada("form[data-confirmar]", function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirmar"))) e.preventDefault();
    });
  });
  cada("form", function (f) {
    f.addEventListener("submit", function (e) {
      if (e.defaultPrevented || f.method.toLowerCase() !== "post") return;
      if (f.dataset.aEnviar) { e.preventDefault(); return; }   // evita envios duplicados
      f.dataset.aEnviar = "1";
      var botao = e.submitter || f.querySelector("button[type=submit], button:not([type])");
      // Só depois do envio começar: um botão desactivado antes perderia o seu name/value.
      setTimeout(function () {
        if (botao && botao.classList.contains("botao")) botao.classList.add("a-carregar");
        cada("button", function (b) { b.disabled = true; }, f);
      }, 0);
    });
  });
  // Voltar à página com o botão "Atrás" do navegador repõe os formulários.
  window.addEventListener("pageshow", function (e) {
    if (!e.persisted) return;
    cada("form", function (f) {
      delete f.dataset.aEnviar;
      cada("button", function (b) { b.disabled = b.hasAttribute("data-desactivado"); b.classList.remove("a-carregar"); }, f);
    });
  });
  // Botões desactivados no servidor guardam esse estado (para o "pageshow" acima).
  cada("button[disabled]", function (b) { b.setAttribute("data-desactivado", ""); });

  // ---------- imprimir (relatório) ----------
  cada("[data-imprimir]", function (b) { b.addEventListener("click", function () { window.print(); }); });

  // ---------- estado em segundo plano: classificação, recolha e modelo ----------
  function consultarEstado(cada_ms, aoReceber) {
    var parar = false;
    var pedir = function () {
      if (parar) return;
      fetch("/estado", { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d && aoReceber(d) === false) parar = true; else setTimeout(pedir, cada_ms); })
        .catch(function () { setTimeout(pedir, cada_ms * 2); });
    };
    setTimeout(pedir, cada_ms);
  }
  function recarregarSuave() {
    document.body.style.transition = "opacity .2s ease";
    document.body.style.opacity = ".6";
    setTimeout(function () { window.location.reload(); }, reduzirMovimento ? 0 : 200);
  }

  var caixa = document.getElementById("estado-classificacao");
  if (caixa) {
    var texto = caixa.querySelector("[data-texto]");
    var barra = caixa.querySelector(".progresso > i");
    consultarEstado(2000, function (d) {
      if (!d.classificacao) { recarregarSuave(); return false; }
      var p = d.classificacao;
      if (texto) texto.textContent = "A classificar: " + p.feitos + " de " + p.total + " publicações.";
      if (barra && p.total) barra.style.width = Math.round(100 * p.feitos / p.total) + "%";
    });
  }
  if (document.getElementById("estado-recolha")) {
    consultarEstado(4000, function (d) { if (!d.recolha) { recarregarSuave(); return false; } });
  }
  if (document.getElementById("modelo-a-carregar")) {
    consultarEstado(3000, function (d) { if (d.modelo !== "a carregar") { recarregarSuave(); return false; } });
  }
})();
