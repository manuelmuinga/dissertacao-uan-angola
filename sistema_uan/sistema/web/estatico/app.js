// Sistema UAN – comportamento da interface (sem bibliotecas externas).
(function () {
  "use strict";

  // ---------- fila: atalhos de teclado ----------
  // J/K ou setas: item seguinte/anterior · 1-4: decisão · N: escrever nota
  var itens = Array.prototype.slice.call(document.querySelectorAll(".item[data-id]"));
  var actual = 0;

  function focar(i) {
    if (!itens.length) return;
    actual = Math.max(0, Math.min(itens.length - 1, i));
    itens.forEach(function (el, j) { el.classList.toggle("focado", j === actual); });
    itens[actual].focus({ preventScroll: true });
    itens[actual].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  itens.forEach(function (el, i) {
    el.addEventListener("click", function () { if (actual !== i) focar(i); });
  });
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

  // ---------- confirmação de acções sensíveis ----------
  document.querySelectorAll("form[data-confirmar]").forEach(function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirmar"))) e.preventDefault();
    });
  });

  // ---------- estado da classificação em segundo plano ----------
  var caixa = document.getElementById("estado-classificacao");
  if (caixa) {
    var texto = caixa.querySelector("[data-texto]");
    var barra = caixa.querySelector(".progresso > i");
    var verificar = function () {
      fetch("/estado", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (!d) return;
          if (!d.classificacao) { window.location.reload(); return; }
          var p = d.classificacao;
          if (texto) texto.textContent = "A classificar: " + p.feitos + " de " + p.total + " publicações.";
          if (barra && p.total) barra.style.width = Math.round(100 * p.feitos / p.total) + "%";
          setTimeout(verificar, 2000);
        })
        .catch(function () { setTimeout(verificar, 5000); });
    };
    setTimeout(verificar, 2000);
  }

  // ---------- modelo a carregar ----------
  var carregar = document.getElementById("modelo-a-carregar");
  if (carregar) {
    var esperar = function () {
      fetch("/estado", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d && d.modelo !== "a carregar") window.location.reload(); else setTimeout(esperar, 3000); })
        .catch(function () { setTimeout(esperar, 5000); });
    };
    setTimeout(esperar, 3000);
  }
})();
