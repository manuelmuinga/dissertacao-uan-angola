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

  // ---------- notificações no canto ----------
  var canto = document.getElementById("avisos-canto");
  function sairToast(t) {
    if (!t || t.classList.contains("a-sair")) return;
    t.classList.add("a-sair");
    setTimeout(function () { if (t.parentNode) t.parentNode.removeChild(t); }, reduzirMovimento ? 0 : 220);
  }
  // toast(texto, {tipo: "ok"|"erro"|"info", accao: {rotulo, tecla, fn}, ms})
  function toast(texto, op) {
    op = op || {};
    if (!canto) return null;
    var ms = op.ms || (op.accao ? 5000 : 4000);
    var t = document.createElement("div");
    t.className = "toast " + (op.tipo || "ok");
    t.setAttribute("role", op.tipo === "erro" ? "alert" : "status");
    var span = document.createElement("span"); span.className = "toast-texto"; span.textContent = texto; t.appendChild(span);
    if (op.accao) {
      var b = document.createElement("button"); b.type = "button"; b.textContent = op.accao.rotulo;
      if (op.accao.tecla) { var k = document.createElement("kbd"); k.textContent = op.accao.tecla; b.appendChild(k); }
      b.addEventListener("click", function () { sairToast(t); op.accao.fn(); });
      t.appendChild(b);
      var barra = document.createElement("i"); barra.className = "toast-tempo"; barra.style.animationDuration = ms + "ms"; t.appendChild(barra);
    }
    canto.appendChild(t);
    while (canto.children.length > 3) sairToast(canto.firstElementChild);
    var tempo = setTimeout(function () { sairToast(t); }, ms);
    t.addEventListener("mouseenter", function () { clearTimeout(tempo); });
    t.addEventListener("mouseleave", function () { tempo = setTimeout(function () { sairToast(t); }, 1500); });
    return t;
  }
  cada("[data-toast-servidor]", function (t) { setTimeout(function () { sairToast(t); }, 4500); });

  function csrf() { var i = document.querySelector("input[name=csrf]"); return i ? i.value : ""; }
  function enviar(url, dados) {
    var corpo = new URLSearchParams();
    Object.keys(dados).forEach(function (k) { corpo.append(k, dados[k]); });
    return fetch(url, { method: "POST", credentials: "same-origin", body: corpo,
                        headers: { "X-Pedido": "fetch", "Accept": "application/json" } })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) throw new Error(d.detail || "Não foi possível concluir. Tente de novo.");
          return d;
        });
      });
  }
  function actualizarContador(href, n) {
    var a = document.querySelector('.menu a[href="' + href + '"]');
    if (!a) return;
    var c = a.querySelector(".contador");
    if (!n) { if (c) c.parentNode.removeChild(c); return; }
    if (!c) { c = document.createElement("span"); c.className = "contador"; a.appendChild(c); }
    c.textContent = String(n);
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
    } else if (k === "d") {
      var det = itens[actual].querySelector("a[data-painel]");
      if (det) { e.preventDefault(); det.click(); }
    } else if (["1", "2", "3", "4"].indexOf(k) >= 0) {
      var botao = itens[actual].querySelector("button[data-tecla='" + k + "']");
      if (botao) { e.preventDefault(); botao.click(); }
    }
  });

  // ---------- decisão sem recarregar e desfazer ----------
  var ultimaDecisao = null;   // {item, id, proximo, pai, toast}
  function retirarItem(item) {
    var i = itens.indexOf(item);
    item.classList.add("a-sair-item");
    setTimeout(function () {
      if (item.parentNode) item.parentNode.removeChild(item);
      itens = itens.filter(function (x) { return x !== item; });
      if (!itens.length) { setTimeout(recarregarSuave, 5300); return; }   // página vazia: trazer os seguintes depois do prazo de desfazer
      focar(Math.min(i, itens.length - 1));
    }, reduzirMovimento ? 0 : 280);
  }
  function desfazer() {
    var u = ultimaDecisao;
    if (!u) return;
    ultimaDecisao = null;
    if (u.toast) sairToast(u.toast);
    enviar("/rever/desfazer", { csrf: csrf(), id_pub: u.id }).then(function (d) {
      u.item.classList.remove("a-sair-item");
      cada("button", function (b) { b.disabled = false; }, u.item);
      u.item.querySelector("form").reset();
      if (u.proximo && u.proximo.parentNode) u.pai.insertBefore(u.item, u.proximo); else u.pai.insertBefore(u.item, u.pai.querySelector(".paginacao"));
      u.item.classList.add("a-voltar-item");
      setTimeout(function () { u.item.classList.remove("a-voltar-item"); }, 320);
      itens = Array.prototype.slice.call(document.querySelectorAll(".item[data-id]"));
      focar(itens.indexOf(u.item));
      actualizarContador("/fila", d.n_fila); actualizarContador("/amostra", d.n_amostra);
      toast(d.alerta_anulado ? "Decisão desfeita. O alerta que tinha gerado foi anulado." : "Decisão desfeita.", { tipo: "info" });
    }).catch(function (err) { toast(err.message, { tipo: "erro" }); });
  }
  cada("form[data-decisao]", function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.fetch || !window.URLSearchParams) return;   // navegador antigo: envio normal
      e.preventDefault();
      var botao = e.submitter;
      if (!botao || botao.name !== "categoria" || f.dataset.aEnviar) return;
      f.dataset.aEnviar = "1";
      var item = f.closest(".item");
      var dados = {};
      Array.prototype.forEach.call(f.elements, function (el) { if (el.name && el.type !== "submit") dados[el.name] = el.value; });
      dados.categoria = botao.value;
      cada("button", function (b) { b.disabled = true; }, f);
      enviar("/rever", dados).then(function (d) {
        delete f.dataset.aEnviar;
        if (ultimaDecisao && ultimaDecisao.toast) sairToast(ultimaDecisao.toast);
        ultimaDecisao = { item: item, id: d.id_pub, proximo: item.nextElementSibling, pai: item.parentNode };
        retirarItem(item);
        actualizarContador("/fila", d.n_fila); actualizarContador("/amostra", d.n_amostra);
        var esta = ultimaDecisao;
        esta.toast = toast("Decisão gravada: " + d.nome + (d.alertas_novos ? " · alerta gerado" : "") + ".",
          { accao: { rotulo: "Desfazer", tecla: "U", fn: desfazer } });
        setTimeout(function () { if (ultimaDecisao === esta) ultimaDecisao = null; }, 5200);
      }).catch(function (err) {
        delete f.dataset.aEnviar;
        cada("button", function (b) { b.disabled = false; }, f);
        toast(err.message, { tipo: "erro" });
      });
    });
  });

  // ---------- painel lateral de detalhe ----------
  var painel = document.getElementById("painel"), painelFundo = document.getElementById("painel-fundo");
  var painelCorpo = document.getElementById("painel-corpo"), painelOrigem = null;
  function fecharPainel() {
    if (!painel || painel.hidden) return;
    painel.classList.add("a-sair");
    setTimeout(function () { painel.hidden = true; painel.classList.remove("a-sair"); painelFundo.hidden = true; painelCorpo.innerHTML = ""; },
      reduzirMovimento ? 0 : 200);
    if (painelOrigem) painelOrigem.focus();
  }
  if (painel) {
    painel.querySelector(".painel-fechar").addEventListener("click", fecharPainel);
    painelFundo.addEventListener("click", fecharPainel);
    cada("a[data-painel]", function (a) {
      a.addEventListener("click", function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || !window.fetch) return;   // abrir noutro separador continua a funcionar
        e.preventDefault();
        painelOrigem = a;
        document.getElementById("painel-abrir").href = a.getAttribute("href");
        painelCorpo.innerHTML = '<div class="carregar"></div>';
        painelFundo.hidden = false; painel.hidden = false;
        painel.querySelector(".painel-fechar").focus();
        fetch(a.getAttribute("href") + "?parcial=1", { credentials: "same-origin", headers: { "X-Pedido": "fetch" } })
          .then(function (r) { if (!r.ok) throw new Error(); return r.text(); })
          .then(function (html) { painelCorpo.innerHTML = html; })
          .catch(function () { fecharPainel(); toast("Não foi possível abrir o detalhe.", { tipo: "erro" }); });
      });
    });
  }

  // ---------- ajuda de atalhos e navegação por teclado ----------
  var ajuda = document.getElementById("atalhos-ajuda"), ajudaFundo = document.getElementById("atalhos-fundo");
  function mostrarAjuda(v) {
    if (!ajuda) return;
    ajuda.hidden = !v; ajudaFundo.hidden = !v;
    if (v) ajuda.querySelector("[data-fechar-atalhos]").focus();
  }
  if (ajuda) {
    ajuda.querySelector("[data-fechar-atalhos]").addEventListener("click", function () { mostrarAjuda(false); });
    ajudaFundo.addEventListener("click", function () { mostrarAjuda(false); });
  }
  var esperaG = 0;
  var DESTINOS = { f: "/fila", a: "/alertas", m: "/mapa", r: "/relatorio", p: "/" };
  document.addEventListener("keydown", function (e) {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "Escape") { mostrarAjuda(false); fecharPainel(); return; }
    var alvo = e.target;
    if (alvo && (alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.tagName === "SELECT" || alvo.isContentEditable)) return;
    var k = e.key.toLowerCase();
    if (e.key === "?") { e.preventDefault(); mostrarAjuda(ajuda && ajuda.hidden); return; }
    if (esperaG && Date.now() - esperaG < 1200 && DESTINOS[k]) { e.preventDefault(); esperaG = 0; window.location.href = DESTINOS[k]; return; }
    esperaG = (k === "g") ? Date.now() : 0;
    if (k === "u" && ultimaDecisao) { e.preventDefault(); desfazer(); }
  });

  // ---------- formulários: confirmação e estado "a enviar" ----------
  cada("form[data-confirmar]", function (f) {
    f.addEventListener("submit", function (e) {
      if (!window.confirm(f.getAttribute("data-confirmar"))) e.preventDefault();
    });
  });
  cada("form", function (f) {
    f.addEventListener("submit", function (e) {
      if (e.defaultPrevented || f.method.toLowerCase() !== "post" || f.hasAttribute("data-decisao")) return;
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
