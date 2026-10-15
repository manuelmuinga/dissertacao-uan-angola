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
  var DESTINOS = { f: "/fila", a: "/alertas", m: "/mapa", r: "/relatorio", p: "/", o: "/modelo" };
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

  // ---------- mapa interactivo: acender, cartão flutuante, destaque na tabela ----------
  function corEscala(v, max) {
    if (!(v > 0)) return "#f6efe6";
    var t = max > 0 ? Math.min(1, v / max) : 0, f = 0.12 + 0.88 * t;
    var a = [0xf6, 0xef, 0xe6], b = [0xa3, 0x26, 0x1a];
    return "#" + a.map(function (x, i) { var c = Math.round(x + (b[i] - x) * f).toString(16); return c.length < 2 ? "0" + c : c; }).join("");
  }
  function fmt(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function dataCurta(iso) { var p = iso.split("-"); return p[2] + "/" + p[1]; }

  cada("svg[data-mapa]", function (svg) {
    var caixaMapa = svg.closest(".mapa-caixa");
    var cartao = caixaMapa && caixaMapa.querySelector(".mapa-cartao");
    var escolhida = null;
    var tempo = { indice: null, serie: null };   // preenchido pela reprodução no tempo
    if (!reduzirMovimento) {
      svg.classList.add("acender");
      setTimeout(function () { svg.classList.remove("acender"); }, 1600);
    }
    function linha(dt, dd) { return "<dt>" + dt + "</dt><dd>" + dd + "</dd>"; }
    function esc(t) { var d = document.createElement("div"); d.textContent = t; return d.innerHTML; }
    function mostrar(a) {
      if (!cartao) return;
      var d = a.dataset, html;
      if (tempo.indice !== null && tempo.serie) {
        var s = tempo.serie, i = tempo.indice, b = s.baldes[i];
        html = "<b>" + esc(d.nome) + "</b><dl>" +
          linha(s.passo_dias === 1 ? "Dia" : "De", dataCurta(b.inicio) + (b.inicio === b.fim ? "" : " a " + dataCurta(b.fim))) +
          linha("Publicações", fmt(s.mencoes[d.prov][i])) + linha("Ameaças", fmt(s.valores[d.prov][i])) + "</dl>";
      } else {
        var v = Number(d.variacao);
        html = "<b>" + esc(d.nome) + "</b><dl>" +
          linha("Publicações", fmt(d.mencoes)) + linha("Ameaças", fmt(d.valor)) +
          linha("Taxa", d.taxa || "dados insuficientes") + linha("Período anterior", fmt(d.antes)) +
          linha("Variação", "<span class='" + (v > 0 ? "sobe" : v < 0 ? "desce" : "") + "'>" + (v > 0 ? "▲ +" : v < 0 ? "▼ −" : "") + Math.abs(v) + "</span>") + "</dl>";
      }
      cartao.innerHTML = html;
      cartao.hidden = false;
      var r = a.getBoundingClientRect(), c = caixaMapa.getBoundingClientRect();
      var x = r.left - c.left + r.width / 2 + 14, y = r.top - c.top + r.height / 2 - 20;
      var w = cartao.offsetWidth, h = cartao.offsetHeight;
      if (x + w > c.width) x = Math.max(0, r.left - c.left + r.width / 2 - w - 14);
      y = Math.max(0, Math.min(y, c.height - h));
      cartao.style.left = x + "px"; cartao.style.top = y + "px";
    }
    function esconder() { if (cartao && !escolhida) cartao.hidden = true; }
    function destacarLinha(cod, rolar) {
      cada("tr.destacada", function (tr) { tr.classList.remove("destacada"); });
      if (!cod) return;
      var tr = document.querySelector('tr[data-prov="' + cod + '"]');
      if (tr) {
        tr.classList.add("destacada");
        if (rolar) tr.scrollIntoView({ behavior: reduzirMovimento ? "auto" : "smooth", block: "nearest" });
      }
    }
    function escolher(a) {
      if (escolhida) escolhida.classList.remove("escolhida");
      if (escolhida === a || !a) {
        escolhida = null; svg.classList.remove("com-escolha"); destacarLinha(null);
        if (cartao) cartao.hidden = true;
        return;
      }
      escolhida = a; a.classList.add("escolhida"); svg.classList.add("com-escolha");
      mostrar(a); destacarLinha(a.dataset.prov, true);
    }
    cada("a[data-prov]", function (a) {
      a.addEventListener("mouseenter", function () { if (!escolhida) mostrar(a); });
      a.addEventListener("mouseleave", esconder);
      a.addEventListener("focus", function () { if (!escolhida) mostrar(a); });
      a.addEventListener("blur", esconder);
      a.addEventListener("click", function (e) { e.preventDefault(); escolher(a); });
    }, svg);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && escolhida) escolher(null); });
    document.addEventListener("click", function (e) { if (escolhida && !svg.contains(e.target)) escolher(null); });
    // Clicar numa linha da tabela acende a província no mapa.
    cada("tr[data-prov]", function (tr) {
      tr.addEventListener("click", function (e) {
        if (e.target.closest("a, button")) return;
        e.stopPropagation();
        var a = svg.querySelector('a[data-prov="' + tr.dataset.prov + '"]');
        if (a) { escolher(a); if (escolhida) svg.scrollIntoView({ behavior: reduzirMovimento ? "auto" : "smooth", block: "nearest" }); }
      });
    });

    // ---------- reprodução no tempo (▶ e cursor) ----------
    var blocoTempo = document.querySelector("[data-tempo]");
    var dadosSerie = document.getElementById("mapa-serie");
    if (!blocoTempo || !dadosSerie) return;
    var serie;
    try { serie = JSON.parse(dadosSerie.textContent); } catch (err) { return; }
    tempo.serie = serie;
    var n = serie.baldes.length, cursor = blocoTempo.querySelector("[data-cursor]");
    var rotulo = blocoTempo.querySelector("[data-rotulo]"), botao = blocoTempo.querySelector("[data-tocar]");
    var maximo = 0;
    Object.keys(serie.valores).forEach(function (k) {
      if (k !== "NAC") serie.valores[k].forEach(function (v) { if (v > maximo) maximo = v; });
    });
    var unidade = serie.passo_dias === 1 ? "Dia" : (serie.passo_dias === 7 ? "Semana" : "Bloco de " + serie.passo_dias + " dias");
    function desenhar(i) {
      var completo = i >= n;
      tempo.indice = completo ? null : i;
      svg.classList.toggle("em-tempo", !completo);
      cada("a[data-prov]", function (a) {
        var p = a.querySelector("path"), cod = a.dataset.prov;
        if (completo) { p.setAttribute("fill", p.dataset.cor); return; }
        p.setAttribute("fill", serie.mencoes[cod][i] ? corEscala(serie.valores[cod][i], maximo) : "#eceee9");
      }, svg);
      if (completo) rotulo.textContent = "Período completo";
      else {
        var b = serie.baldes[i];
        rotulo.textContent = unidade + " " + (i + 1) + " de " + n + ": " + dataCurta(b.inicio) +
          (b.inicio === b.fim ? "" : " a " + dataCurta(b.fim)) + " · " + fmt(serie.valores.NAC[i]) + " ameaças no país";
      }
      if (escolhida) mostrar(escolhida);
    }
    var relogio = null;
    function parar() {
      clearInterval(relogio); relogio = null;
      blocoTempo.classList.remove("a-tocar");
      botao.textContent = "▶ Reproduzir"; botao.setAttribute("aria-label", "Reproduzir a evolução no tempo");
    }
    function tocar() {
      if (relogio) { parar(); return; }
      var i = Number(cursor.value);
      if (i >= n) i = 0;
      cursor.value = i; desenhar(i);
      blocoTempo.classList.add("a-tocar");
      botao.textContent = "❚❚ Pausa"; botao.setAttribute("aria-label", "Pausar a reprodução");
      relogio = setInterval(function () {
        i += 1; cursor.value = i; desenhar(i);
        if (i >= n) parar();
      }, 900);
    }
    botao.addEventListener("click", tocar);
    cursor.addEventListener("input", function () { if (relogio) parar(); desenhar(Number(cursor.value)); });
  });

  // ---------- descarregar o mapa em PNG (convertido no navegador, sem serviços externos) ----------
  cada("[data-png]", function (b) {
    b.addEventListener("click", function () {
      b.disabled = true; b.classList.add("a-carregar");
      var fim = function () { b.disabled = false; b.classList.remove("a-carregar"); };
      fetch(b.dataset.png, { credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (texto) {
          return new Promise(function (ok, falha) {
            var img = new Image();
            img.onload = function () { ok(img); };
            img.onerror = function () { falha(new Error("imagem")); };
            img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(texto);
          });
        })
        .then(function (img) {
          var c = document.createElement("canvas");
          c.width = img.naturalWidth || 1280; c.height = img.naturalHeight || 1720;
          var g = c.getContext("2d");
          g.fillStyle = "#fff"; g.fillRect(0, 0, c.width, c.height);
          g.drawImage(img, 0, 0, c.width, c.height);
          c.toBlob(function (blob) {
            var a = document.createElement("a");
            a.href = URL.createObjectURL(blob); a.download = b.dataset.nome || "mapa.png";
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
            fim(); toast("Mapa descarregado em PNG.");
          }, "image/png");
        })
        .catch(function () { fim(); toast("Não foi possível gerar o PNG. Use o SVG.", { tipo: "erro" }); });
    });
  });

  // ---------- tabelas: ordenar por clique no cabeçalho ----------
  function chaveCelula(td, numerica) {
    if (!td) return numerica ? -Infinity : "";
    if (td.hasAttribute("data-v")) { var v = td.getAttribute("data-v"); return numerica || !isNaN(Number(v)) ? Number(v) : v; }
    var t = td.textContent.trim();
    if (!numerica) return t.toLocaleLowerCase("pt");
    var x = parseFloat(t.replace(/[\s  %+]/g, "").replace(",", "."));
    return isNaN(x) ? -Infinity : x;
  }
  cada("table[data-ordenar]", function (tabela) {
    var corpo = tabela.tBodies[0];
    if (!corpo) return;
    cada("thead th", function (th, col) {
      if (th.hasAttribute("data-sem-ordem")) return;
      var b = document.createElement("button");
      b.type = "button"; b.className = "ordenar";
      while (th.firstChild) b.appendChild(th.firstChild);
      th.appendChild(b);
      b.addEventListener("click", function () {
        var numerica = th.classList.contains("num");
        var actual = th.getAttribute("aria-sort");
        var dir = actual ? (actual === "descending" ? "ascending" : "descending") : (numerica ? "descending" : "ascending");
        cada("thead th", function (o) { o.removeAttribute("aria-sort"); }, tabela);
        th.setAttribute("aria-sort", dir);
        var linhas = Array.prototype.filter.call(corpo.rows, function (r) { return !r.querySelector("td[colspan]"); });
        var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
        linhas.sort(function (a, z) {
          var x = chaveCelula(a.cells[idx], numerica), y = chaveCelula(z.cells[idx], numerica);
          var r = (typeof x === "number" && typeof y === "number") ? x - y : String(x).localeCompare(String(y), "pt");
          return dir === "ascending" ? r : -r;
        });
        linhas.forEach(function (r) { corpo.appendChild(r); });
      });
    }, tabela);
  });

  // ---------- números dos indicadores: contagem animada ao abrir a página ----------
  if (!reduzirMovimento && window.requestAnimationFrame) {
    cada(".kpi .valor", function (el) {
      var t = el.textContent.trim();
      var m = /^([+−-]?)([\d\s  ]+)(?:,(\d+))?(\s*%|\s*p\.p\.)?$/.exec(t);
      if (!m) return;
      var inteiro = Number(m[2].replace(/[\s  ]/g, "")), casas = m[3] ? m[3].length : 0;
      var alvo = inteiro + (casas ? Number("0." + m[3]) : 0);
      if (!(alvo > 0)) return;
      el.setAttribute("data-contar", "");
      var inicio = null, dur = 700;
      var formatar = function (v) {
        var p = v.toFixed(casas).split(".");
        return m[1] + p[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (casas ? "," + p[1] : "") + (m[4] || "");
      };
      var passo = function (ts) {
        if (inicio === null) inicio = ts;
        var f = Math.min(1, (ts - inicio) / dur), e = 1 - Math.pow(1 - f, 3);
        el.textContent = f < 1 ? formatar(alvo * e) : t;
        if (f < 1) requestAnimationFrame(passo);
      };
      el.textContent = formatar(0);
      requestAnimationFrame(passo);
    });
  }

  // ---------- tema: automático, escuro ou claro (guardado num cookie, lido pelo servidor) ----------
  var botaoTema = document.querySelector("[data-tema-alternar]");
  function aplicarTema(tema) {
    var raiz = document.documentElement;
    if (tema) raiz.setAttribute("data-tema", tema); else raiz.removeAttribute("data-tema");
    document.cookie = "uan_tema=" + (tema || "") + "; path=/; SameSite=Lax; max-age=" + (tema ? 31536000 : 0);
    if (botaoTema) {
      var nome = { escuro: "escuro", claro: "claro" }[tema] || "automático";
      botaoTema.setAttribute("aria-label", "Tema: " + nome);
      botaoTema.title = "Tema: " + (tema ? nome : "automático (segue o sistema)");
      botaoTema.querySelector("use").setAttribute("href", "#i-" + ({ escuro: "lua", claro: "sol" }[tema] || "auto"));
    }
  }
  if (botaoTema) {
    botaoTema.addEventListener("click", function () {
      var actual = document.documentElement.getAttribute("data-tema") || "";
      var seguinte = { "": "escuro", escuro: "claro", claro: "" }[actual];
      aplicarTema(seguinte);
      toast("Tema: " + ({ escuro: "escuro", claro: "claro" }[seguinte] || "automático, segue o sistema") + ".", { tipo: "info", ms: 2000 });
    });
  }

  // ---------- sino: últimos alertas ----------
  var sino = document.querySelector("[data-sino]"), sinoLista = document.getElementById("sino-lista");
  var sinoN = document.querySelector("[data-sino-n]");
  function esc(t) { var d = document.createElement("div"); d.textContent = t == null ? "" : String(t); return d.innerHTML; }
  function fecharSino() { if (sinoLista && !sinoLista.hidden) { sinoLista.hidden = true; sino.setAttribute("aria-expanded", "false"); } }
  function mostrarPorVer(n) {
    if (sinoN) { sinoN.hidden = !n; sinoN.textContent = n > 99 ? "99+" : String(n || ""); }
    if (sino) sino.setAttribute("aria-label", "Alertas" + (n ? ": " + n + " por ver" : ""));
    actualizarContador("/alertas", n);
  }
  if (sino && sinoLista) {
    sino.addEventListener("click", function (e) {
      e.stopPropagation();
      if (!sinoLista.hidden) { fecharSino(); return; }
      sinoLista.hidden = false; sino.setAttribute("aria-expanded", "true");
      var ul = sinoLista.querySelector("[data-sino-itens]");
      fetch("/alertas/recentes", { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) {
          mostrarPorVer(d.por_ver);
          if (!d.alertas.length) { ul.innerHTML = '<li class="sino-vazio">Ainda não há alertas.</li>'; return; }
          ul.innerHTML = d.alertas.map(function (a) {
            return '<li class="' + (a.visto ? "" : "por-ver") + '"><a href="' + esc(a.ligacao) + '">' + esc(a.titulo) +
              "<small>" + (a.tipo === "tendencia" ? "Tendência" : "Confirmado") + " · " + esc(a.quando) + "</small></a></li>";
          }).join("");
        })
        .catch(function () { ul.innerHTML = '<li class="sino-vazio">Não foi possível carregar os alertas.</li>'; });
    });
    document.addEventListener("click", function (e) { if (!sinoLista.contains(e.target)) fecharSino(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !sinoLista.hidden) { fecharSino(); sino.focus(); } });
  }

  // ---------- alertas em tempo real: o servidor é consultado em segundo plano ----------
  if (sino && window.fetch) {
    var porVer = sinoN && !sinoN.hidden ? parseInt(sinoN.textContent, 10) || 0 : 0;
    var ultimoVisto = null, primeira = true;
    var vigiar = function () {
      if (document.hidden) { setTimeout(vigiar, 15000); return; }
      fetch("/estado", { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (!d) return;
          var novo = d.ultimo_alerta && d.ultimo_alerta.id;
          if (!primeira && novo && novo !== ultimoVisto && d.alertas_por_ver > porVer) {
            sino.classList.remove("pulsar"); void sino.offsetWidth; sino.classList.add("pulsar");
            var link = document.querySelector('.menu a[href="/alertas"]');
            if (link) { link.classList.remove("pulsar"); void link.offsetWidth; link.classList.add("pulsar"); }
            toast("Novo alerta: " + d.ultimo_alerta.titulo, { tipo: "info", ms: 8000,
              accao: { rotulo: "Ver", fn: function () { window.location.href = d.ultimo_alerta.ligacao; } } });
          }
          if (novo) ultimoVisto = novo;
          primeira = false;
          porVer = d.alertas_por_ver;
          mostrarPorVer(porVer);
          if (typeof d.fila === "number" && !itens.length) actualizarContador("/fila", d.fila);
        })
        .catch(function () {})
        .then(function () { setTimeout(vigiar, 20000); });
    };
    setTimeout(vigiar, 1500);
  }

  // ---------- paleta de comandos (Ctrl+K) ----------
  var paleta = document.getElementById("paleta"), paletaFundo = document.getElementById("paleta-fundo");
  var paletaTexto = document.getElementById("paleta-texto"), paletaLista = document.getElementById("paleta-lista");
  var paletaOrigem = null, paletaItens = [], paletaSel = 0;
  function semAcentos(t) { return (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }
  function comandos() {
    var cmds = [];
    cada(".menu a", function (a) {
      var u = a.querySelector("use");
      cmds.push({ grupo: "Páginas", texto: a.querySelector("span").textContent.trim(), url: a.getAttribute("href"),
                  icone: u ? u.getAttribute("href") : "#i-panorama" });
    });
    [["Mapa: últimos 7 dias", "/mapa?dias=7", "mapa"], ["Mapa: últimos 30 dias", "/mapa?dias=30", "mapa"],
     ["Mapa: últimos 90 dias", "/mapa?dias=90", "mapa"], ["Mapa: sinalizadas pelo modelo (sem revisão)", "/mapa?modo=sinalizadas", "mapa"],
     ["Relatório: últimos 7 dias", "/relatorio?dias=7", "relatorio"], ["Relatório: últimos 30 dias", "/relatorio?dias=30", "relatorio"],
     ["Descarregar relatório em CSV (30 dias)", "/relatorio.csv?dias=30", "relatorio"],
     ["Descarregar o mapa em SVG (30 dias)", "/mapa.svg?dias=30", "mapa"],
     ["Fila: só Mobilização Hostil", "/fila?categoria=Mobilizacao", "fila"], ["Fila: só Discurso de Ódio", "/fila?categoria=Odio", "fila"],
     ["Fila: só Desinformação", "/fila?categoria=Desinformacao", "fila"],
     ["Alertas de tendência", "/alertas?tipo=tendencia", "alertas"], ["Alertas confirmados", "/alertas?tipo=confirmado", "alertas"],
     ["A minha conta e palavra-passe", "/conta", "utilizadores"]
    ].forEach(function (c) { cmds.push({ grupo: "Atalhos", texto: c[0], url: c[1], icone: "#i-" + c[2] }); });
    [["Tema escuro", function () { aplicarTema("escuro"); }, "lua"], ["Tema claro", function () { aplicarTema("claro"); }, "sol"],
     ["Tema automático (segue o sistema)", function () { aplicarTema(""); }, "auto"],
     ["Visita guiada", function () { iniciarVisita(); }, "visita"],
     ["Atalhos de teclado", function () { mostrarAjuda(true); }, "definicoes"],
     ["Imprimir esta página", function () { window.print(); }, "relatorio"]
    ].forEach(function (c) { cmds.push({ grupo: "Acções", texto: c[0], fn: c[1], icone: "#i-" + c[2] }); });
    return cmds;
  }
  function desenharPaleta() {
    var q = semAcentos(paletaTexto.value).trim().split(/\s+/).filter(Boolean);
    var todos = comandos();
    paletaItens = todos.filter(function (c) {
      var t = semAcentos(c.texto + " " + c.grupo);
      return q.every(function (p) { return t.indexOf(p) >= 0; });
    });
    if (q.length) paletaItens.sort(function (a, b) { return semAcentos(a.texto).indexOf(q[0]) - semAcentos(b.texto).indexOf(q[0]); });
    paletaSel = Math.min(paletaSel, Math.max(0, paletaItens.length - 1));
    var html = "", grupo = null;
    paletaItens.forEach(function (c, i) {
      if (!q.length && c.grupo !== grupo) { grupo = c.grupo; html += '<li class="paleta-grupo" role="presentation">' + esc(grupo) + "</li>"; }
      html += '<li role="option" id="paleta-op-' + i + '" data-i="' + i + '" aria-selected="' + (i === paletaSel) + '">' +
        '<svg class="icone" aria-hidden="true"><use href="' + esc(c.icone) + '"></use></svg>' + esc(c.texto) +
        (c.url ? "<small>" + esc(c.url.split("?")[0]) + "</small>" : "<small>acção</small>") + "</li>";
    });
    paletaLista.innerHTML = html || '<li class="sino-vazio" role="presentation">Nada encontrado.</li>';
    paletaTexto.setAttribute("aria-activedescendant", paletaItens.length ? "paleta-op-" + paletaSel : "");
    var sel = document.getElementById("paleta-op-" + paletaSel);
    if (sel) sel.scrollIntoView({ block: "nearest" });
  }
  function abrirPaleta() {
    if (!paleta) return;
    paletaOrigem = document.activeElement;
    paleta.hidden = false; paletaFundo.hidden = false; paletaTexto.value = ""; paletaSel = 0;
    desenharPaleta(); paletaTexto.focus();
  }
  function fecharPaleta() {
    if (!paleta || paleta.hidden) return;
    paleta.hidden = true; paletaFundo.hidden = true;
    if (paletaOrigem && paletaOrigem.focus) paletaOrigem.focus();
  }
  function executar(i) {
    var c = paletaItens[i];
    if (!c) return;
    fecharPaleta();
    if (c.fn) c.fn(); else window.location.href = c.url;
  }
  if (paleta) {
    cada("[data-paleta-abrir]", function (b) { b.addEventListener("click", abrirPaleta); });
    paletaFundo.addEventListener("click", fecharPaleta);
    paletaTexto.addEventListener("input", function () { paletaSel = 0; desenharPaleta(); });
    paletaTexto.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown") { e.preventDefault(); paletaSel = Math.min(paletaItens.length - 1, paletaSel + 1); desenharPaleta(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); paletaSel = Math.max(0, paletaSel - 1); desenharPaleta(); }
      else if (e.key === "Enter") { e.preventDefault(); executar(paletaSel); }
      else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); fecharPaleta(); }
    });
    paletaLista.addEventListener("click", function (e) {
      var li = e.target.closest("li[data-i]");
      if (li) executar(Number(li.getAttribute("data-i")));
    });
    document.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (paleta.hidden) abrirPaleta(); else fecharPaleta();
      }
    });
  }

  // ---------- visita guiada (4 passos; aparece na primeira entrada e pode repetir-se no menu) ----------
  var PASSOS = [
    { titulo: "Fila de revisão", texto: "Começa aqui. A fila mostra primeiro o que o modelo considera mais provável ser ameaça. Decida com as teclas 1 a 4 e desfaça com U. O modelo sugere; quem decide é o analista." },
    { titulo: "Alertas", texto: "Os alertas nascem só de decisões humanas: um alerta quando um analista confirma uma ameaça e outro quando as ameaças confirmadas crescem numa província. O sino no topo mostra os últimos." },
    { titulo: "Mapa por província", texto: "A cor é a taxa de ameaças confirmadas sobre as publicações que mencionam cada província. Passe o rato para ver os números, clique para destacar na tabela e use ▶ para ver a evolução semana a semana." },
    { titulo: "Relatório e Sobre o modelo", texto: "O relatório reúne o período escolhido para imprimir, descarregar em CSV ou enviar por e-mail. Em Sobre o modelo vê o que o modelo sabe e onde falha, sobretudo em conteúdo angolano." }
  ];
  var visita = { i: 0, activa: false };
  var visitaFoco = document.getElementById("visita-foco"), visitaCartao = document.getElementById("visita-cartao");
  function posicionarVisita() {
    var passo = PASSOS[visita.i];
    var alvo = document.querySelector('[data-visita-passo="' + (visita.i + 1) + '"]');
    visitaCartao.querySelector("[data-visita-contagem]").textContent = "Passo " + (visita.i + 1) + " de " + PASSOS.length;
    visitaCartao.querySelector("[data-visita-titulo]").textContent = passo.titulo;
    visitaCartao.querySelector("[data-visita-texto]").textContent = passo.texto;
    visitaCartao.querySelector("[data-visita-anterior]").disabled = visita.i === 0;
    visitaCartao.querySelector("[data-visita-seguinte]").textContent = visita.i === PASSOS.length - 1 ? "Concluir" : "Seguinte";
    if (alvo && lateral && window.innerWidth <= 960 && !lateral.classList.contains("aberto")) {
      lateral.classList.add("aberto"); alternar.setAttribute("aria-expanded", "true");
    }
    var r = alvo ? alvo.getBoundingClientRect() : null;
    visitaCartao.hidden = false;
    var w = visitaCartao.offsetWidth, h = visitaCartao.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
    if (r && r.width && r.height) {
      visitaFoco.hidden = false;
      visitaFoco.style.top = (r.top - 4) + "px"; visitaFoco.style.left = (r.left - 4) + "px";
      visitaFoco.style.width = (r.width + 8) + "px"; visitaFoco.style.height = (r.height + 8) + "px";
      var x = r.right + 16, y = r.top - 10;
      if (x + w > vw - 12) { x = Math.max(12, Math.min(vw - w - 12, r.left)); y = r.bottom + 14; }
      y = Math.max(12, Math.min(y, vh - h - 12));
      visitaCartao.style.left = x + "px"; visitaCartao.style.top = y + "px";
    } else {
      visitaFoco.hidden = true;
      visitaCartao.style.left = Math.max(12, (vw - w) / 2) + "px"; visitaCartao.style.top = Math.max(12, (vh - h) / 3) + "px";
    }
    visitaCartao.querySelector("[data-visita-seguinte]").focus();
  }
  function iniciarVisita() {
    if (!visitaCartao) return;
    visita.i = 0; visita.activa = true; posicionarVisita();
  }
  function terminarVisita() {
    if (!visita.activa) return;
    visita.activa = false; visitaCartao.hidden = true; visitaFoco.hidden = true;
    if (lateral && window.innerWidth <= 960) { lateral.classList.remove("aberto"); alternar.setAttribute("aria-expanded", "false"); }
    if (document.body.hasAttribute("data-visita-auto")) {
      document.body.removeAttribute("data-visita-auto");
      enviar("/visita/vista", { csrf: csrf() }).catch(function () {});
    }
  }
  if (visitaCartao) {
    visitaCartao.querySelector("[data-visita-seguinte]").addEventListener("click", function () {
      if (visita.i >= PASSOS.length - 1) { terminarVisita(); toast("Visita concluída. Pode repeti-la no menu, em Visita guiada.", { tipo: "info" }); return; }
      visita.i += 1; posicionarVisita();
    });
    visitaCartao.querySelector("[data-visita-anterior]").addEventListener("click", function () { if (visita.i > 0) { visita.i -= 1; posicionarVisita(); } });
    visitaCartao.querySelector("[data-visita-saltar]").addEventListener("click", terminarVisita);
    document.addEventListener("keydown", function (e) {
      if (!visita.activa) return;
      if (e.key === "Escape") { e.stopPropagation(); terminarVisita(); }
      else if (e.key === "ArrowRight") visitaCartao.querySelector("[data-visita-seguinte]").click();
      else if (e.key === "ArrowLeft") visitaCartao.querySelector("[data-visita-anterior]").click();
    }, true);
    window.addEventListener("resize", function () { if (visita.activa) posicionarVisita(); });
    cada("[data-visita-iniciar]", function (b) { b.addEventListener("click", function (e) { e.stopPropagation(); iniciarVisita(); }); });
    if (document.body.hasAttribute("data-visita-auto")) setTimeout(iniciarVisita, reduzirMovimento ? 0 : 700);
  }
})();
