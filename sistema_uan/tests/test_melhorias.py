"""Testes das melhorias de 17/10: várias fontes de uma vez, dados fictícios estruturados, troca de modo,
aspecto em Definições, visita guiada completa e mapa sem dica nativa do navegador."""

from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sistema import alertas as al  # noqa: E402
from sistema import controlo  # noqa: E402
from sistema.base_dados import BaseDados  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.demonstracao import ACERTO_SIMULADO, ClassificadorSimulado  # noqa: E402
from sistema.demonstracao_dados import gerar  # noqa: E402
from sistema.recolha import (ClienteHTTP, ClienteYouTube, Resposta, adicionar_fontes, detectar_tipo,  # noqa: E402
                             normalizar_endereco, recolher_youtube)
from sistema.servico import classificar_pendentes, importar  # noqa: E402
from sistema.utilizadores import criar_utilizador  # noqa: E402
from sistema.web.app import criar_app  # noqa: E402

SENHA = "palavra-passe-longa"
JS = (RAIZ / "sistema" / "web" / "estatico" / "app.js").read_text(encoding="utf-8")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "m.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    monkeypatch.delenv("UAN_DEMONSTRACAO", raising=False)
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    criar_utilizador(a.state.bd, "sup", "Sup", "supervisor", SENHA)
    criar_utilizador(a.state.bd, "ana", "Ana", "analista", SENHA)
    f = tmp_path / "l.csv"
    f.write_text("id,textDisplay,publishedAt\n"
                 f"a,Vamos todos à praça do Huambo amanhã às 10h tragam tudo,{al.hoje_luanda()}\n", encoding="utf-8")
    importar(a.state.bd, f, "YouTube", "api_oficial", "s")
    classificar_pendentes(a.state.bd, ClassificadorDemonstracao())
    return a


def entrar(app, u="sup") -> TestClient:
    c = TestClient(app)
    c.post("/entrar", data={"utilizador": u, "senha": SENHA, "seguinte": "/"})
    return c


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


# ------------------------------------------------------------------ várias fontes
@pytest.mark.parametrize("endereco,tipo", [
    ("https://www.youtube.com/watch?v=abcdefghijk", "youtube_video"),
    ("https://youtu.be/abcdefghijk", "youtube_video"),
    ("https://www.youtube.com/shorts/abcdefghijk", "youtube_video"),
    ("https://www.youtube.com/@canal", "youtube_canal"),
    ("@canal", "youtube_canal"),
    ("https://www.youtube.com/playlist?list=PLabcdefghij12345", "youtube_lista"),
    ("https://www.youtube.com/results?search_query=greve+professores", "youtube_pesquisa"),
    ("manifestação Luanda taxistas", "youtube_pesquisa"),
    ("pesquisa: propinas", "youtube_pesquisa"),
    ("https://www.jornal.ao/feed/", "rss"),
    ("https://www.jornal.ao/rss.xml", "rss"),
    ("https://www.jornal.ao/", "sitio"),
    ("https://www.jornal.ao/politica", "sitio"),
    ("https://www.jornal.ao/politica/2026/10/governo-aprova-plano-de-transportes", "pagina"),
    ("www.jornal.ao", "sitio"),
])
def test_detectar_tipo(endereco, tipo):
    assert detectar_tipo(endereco) == tipo


def test_normalizar():
    assert normalizar_endereco("youtube_lista", "https://www.youtube.com/playlist?list=PLx123456789") == "PLx123456789"
    assert normalizar_endereco("youtube_pesquisa", "pesquisa:  greve   professores ") == "greve professores"
    assert normalizar_endereco("sitio", "www.jornal.ao") == "https://www.jornal.ao"


def test_adicionar_varias_fontes(tmp_path):
    bd = BaseDados(tmp_path / "f.db")
    texto = """https://www.youtube.com/@canal
# comentário ignorado
https://www.jornal.ao/feed/
taxistas Luanda

https://www.youtube.com/@canal
ftp://nao.serve"""
    r = adicionar_fontes(bd, texto, "sup", nome="Lote X")
    assert [t for _, t, _ in r["criadas"]] == ["youtube_canal", "rss", "youtube_pesquisa"]
    assert r["repetidas"] == ["https://www.youtube.com/@canal"] and len(r["erros"]) == 1
    nomes = [x["nome"] for x in bd.consultar("SELECT nome FROM fontes ORDER BY id_fonte")]
    assert nomes[0].startswith("Lote X (") and len(set(nomes)) == 3
    r2 = adicionar_fontes(bd, "outra pesquisa", "sup")
    assert bd.consultar("SELECT nome FROM fontes WHERE id_fonte = ?", (r2["criadas"][0][0],))[0]["nome"] == "Pesquisa: outra pesquisa"


def test_fontes_pela_pagina(app):
    c = entrar(app)
    h = c.get("/fontes").text
    assert 'name="enderecos"' in h and "Detectar automaticamente" in h and "Pesquisa no YouTube" in h
    d = c.post("/fontes/detectar", data={"csrf": csrf(h), "enderecos": "https://youtu.be/abcdefghijk\ngreve"},
               headers={"X-Pedido": "fetch"}).json()
    assert [x["tipo"] for x in d["linhas"]] == ["youtube_video", "youtube_pesquisa"]
    r = c.post("/fontes/adicionar", data={"csrf": csrf(h), "tipo": "auto", "max_itens": "50",
                                          "enderecos": "https://youtu.be/abcdefghijk\nhttps://www.jornal.ao/feed/\ngreve"},
               follow_redirects=False)
    assert r.status_code == 303 and "3+fonte" in r.headers["location"].replace("%28", "(")
    assert "3 fonte(s) acrescentada(s)" in c.get(r.headers["location"]).text
    assert app.state.bd.consultar("SELECT COUNT(*) AS n FROM fontes")[0]["n"] == 3
    assert c.post("/fontes/adicionar", data={"csrf": csrf(h), "enderecos": "ftp://x"}).status_code == 400


class YTPesquisa(ClienteHTTP):
    def __init__(self):
        super().__init__("t", 0)
        self.pedidos = []

    def obter(self, url, verificar_robots=True):
        self.pedidos.append(url)
        if "/search?" in url:
            d = {"items": [{"id": {"videoId": "v1"}, "snippet": {"title": "Greve em Luanda"}}, {"id": {"channelId": "x"}}]}
        elif "/playlistItems?" in url:
            d = {"items": [{"snippet": {"title": "Da lista", "resourceId": {"videoId": "v2"}}}]}
        else:
            c = {"id": "c1", "snippet": {"textOriginal": "Comentário de teste suficiente", "authorDisplayName": "A",
                                         "publishedAt": "2026-10-01T10:00:00Z"}}
            d = {"items": [{"snippet": {"topLevelComment": c}}]}
        return Resposta(200, "application/json", json.dumps(d).encode(), url)


def test_youtube_pesquisa_e_lista():
    http = YTPesquisa()
    yt = ClienteYouTube("k", http)
    regs, _ = recolher_youtube({"tipo": "youtube_pesquisa", "endereco": "greve Luanda", "nome": "P", "max_itens": 10}, yt)
    assert regs and regs[0]["contexto"] == "Greve em Luanda"
    assert "regionCode=AO" in http.pedidos[0] and "q=greve+Luanda" in http.pedidos[0]
    regs, _ = recolher_youtube({"tipo": "youtube_lista", "endereco": "PLx", "nome": "L", "max_itens": 10}, yt)
    assert regs[0]["contexto"] == "Da lista"


# ------------------------------------------------------------------ dados fictícios
def test_dados_ficticios_estruturados():
    regs = gerar(al.hoje_luanda())
    textos = [r["textDisplay"] for r, _, _ in regs]
    assert len(set(textos)) / len(textos) > 0.8          # pouca repetição
    assert not any("{" in t or "  " in t for t in textos)
    cats = Counter(c for _, c, _ in regs)
    assert cats["Normal"] > cats["Desinformacao"] > 50 and cats["Odio"] > 50 and cats["Mobilizacao"] > 50
    assert len({p for *_, p in regs}) == 3 and all(p.endswith("(fictício)") for *_, p in regs)
    assert any("pacífica" in t for t in textos)            # casos de fronteira: protesto legal é Normal
    assert len({r["contexto"] for r, _, _ in regs}) > 100   # muitas conversas diferentes
    # a frase muda de forma, não só o lugar: com os lugares retirados, continua quase tudo diferente
    sem_lugar = {re.sub(r"\b[A-ZÁÉÍÓÚÂÊÔ][\wçãõáéíóúâêô'’-]+", "X", t) for t in textos}
    assert len(sem_lugar) / len(textos) > 0.6


def test_classificador_simulado_erra_como_um_modelo():
    regs = gerar(al.hoje_luanda())
    mapa = {r["textDisplay"]: c for r, c, _ in regs}
    clf = ClassificadorSimulado(mapa)
    res = clf.classificar(list(mapa))
    acertos = Counter(c for (t, c), r in zip(mapa.items(), res) if r.categoria == c)
    totais = Counter(mapa.values())
    for c, alvo in ACERTO_SIMULADO.items():
        assert abs(acertos[c] / totais[c] - alvo) < 0.12
    assert all(abs(sum(r.probabilidades.values()) - 1) < 1e-9 for r in res)
    assert clf.classificar(["texto desconhecido, vamos todos amanhã às 9h"])[0].categoria == "Mobilizacao"


# ------------------------------------------------------------------ troca de modo
def test_troca_de_modo(app, monkeypatch):
    c = entrar(app)
    h = c.get("/definicoes").text
    assert "Modo do sistema" in h and "python uan.py servir" in h        # sem o ciclo do uan.py, não há troca
    r = c.post("/sistema/modo", data={"csrf": csrf(h), "modo": "demonstracao"}, headers={"X-Pedido": "fetch"})
    assert r.status_code == 409
    falso = SimpleNamespace(should_exit=False)
    monkeypatch.setattr(controlo, "servidor", falso)
    h = c.get("/definicoes").text
    assert 'data-trocar-modo="demonstracao"' in h
    assert c.post("/sistema/modo", data={"csrf": csrf(h), "modo": "real"}, headers={"X-Pedido": "fetch"}).status_code == 400
    r = c.post("/sistema/modo", data={"csrf": csrf(h), "modo": "demonstracao"}, headers={"X-Pedido": "fetch"})
    assert r.json() == {"ok": True, "modo": "demonstracao"} and controlo.pedido == "demonstracao"
    time.sleep(0.6)
    assert falso.should_exit is True
    assert c.get("/sistema/estado").json()["modo"] == "real"
    assert entrar(app, "ana").post("/sistema/modo", data={"csrf": "x", "modo": "demonstracao"}).status_code == 403
    assert app.state.bd.consultar("SELECT COUNT(*) AS n FROM auditoria WHERE accao='troca_de_modo'")[0]["n"] == 1
    controlo.pedido = None


# ------------------------------------------------------------------ aspecto
def test_aspecto(app):
    c = entrar(app, "ana")
    h = c.get("/definicoes").text
    for nome in ("tema", "cor", "menu", "mapa", "cantos", "movimento"):
        assert f'name="{nome}"' in h
    r = c.post("/aspecto", data={"csrf": csrf(h), "cor": "verde", "menu": "claro", "cantos": "rectos",
                                 "movimento": "reduzido", "mapa": "azul"}, headers={"X-Pedido": "fetch"})
    assert r.json()["aspecto"]["cor"] == "verde"
    p = c.get("/").text.split("<head>")[0]
    assert 'data-cor="verde"' in p and 'data-menu="claro"' in p and 'data-cantos="rectos"' in p and 'data-movimento="reduzido"' in p
    m = c.get("/mapa?dias=7").text
    assert 'data-escala-b="#143a5e"' in m          # a paleta azul chega ao mapa e à legenda
    # outra conta mantém o aspecto por omissão
    assert "data-cor" not in entrar(app, "sup").get("/").text.split("<head>")[0]
    assert c.post("/aspecto", data={"csrf": csrf(h), "cor": "rosa"}).status_code == 400
    c.post("/aspecto", data={"csrf": csrf(h), "repor": "1", "cor": "verde", "tema": "escuro"}, headers={"X-Pedido": "fetch"})
    assert "data-cor" not in c.get("/").text.split("<head>")[0]


# ------------------------------------------------------------------ visita e mapa
def test_mapa_sem_dica_nativa(app):
    m = entrar(app).get("/mapa?dias=7").text
    svg = re.search(r'<svg class="grafico mapa".*?</svg>', m, re.S).group(0)
    assert "<title>" not in svg and 'aria-label="Huambo:' in svg


def test_visita_completa():
    alvos = re.findall(r'alvo: \'\.menu a\[href="(/[a-z]*)"\]\'', JS)
    for pagina in ("/", "/fila", "/amostra", "/alertas", "/mapa", "/relatorio", "/modelo", "/lotes", "/fontes",
                   "/metricas", "/utilizadores", "/auditoria", "/definicoes"):
        assert pagina in alvos
    assert "[data-sino]" in JS and "[data-paleta-abrir]" in JS and "data-visita-progresso" in JS
