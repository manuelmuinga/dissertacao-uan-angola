"""Testes da recolha: sítio web local com robots.txt, artigos, página com login e feed RSS; YouTube simulado."""

from __future__ import annotations

import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sistema.base_dados import BaseDados  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.recolha import (ClienteHTTP, ErroRecolha, Resposta, adicionar_fonte, extrair_feed,  # noqa: E402
                             extrair_pagina, recolher_fonte)

ARTIGO = """<html><head><title>Título técnico</title>
<meta property="og:title" content="Moradores do bairro reclamam da falta de água">
<meta property="article:published_time" content="2026-10-01T09:00:00Z"></head>
<body><nav><p>Início Política Economia Desporto e mais ligações do menu principal</p></nav>
<article><h1>Moradores do bairro reclamam da falta de água</h1>
<p>Os moradores do bairro dizem que a água não chega às torneiras há três semanas e que já fizeram queixa.</p>
<p>A administração municipal prometeu uma solução para os próximos dias, segundo um comunicado divulgado ontem.</p>
<p>Ligue 923 456 789 para mais informações ou escreva para leitor@jornal.ao.</p></article>
<footer><p>Todos os direitos reservados ao jornal e aos seus autores desde sempre</p></footer>
<script>var x = "não deve aparecer";</script></body></html>"""

INICIO = """<html><body><a href="/2026/10/moradores-do-bairro-reclamam-da-falta-de-agua">a</a>
<a href="/2026/10/segunda-noticia-com-um-titulo-bem-comprido">b</a>
<a href="/privado/2026/10/noticia-que-o-robots-txt-proibe-recolher">c</a>
<a href="/categoria/politica">d</a><a href="https://outro.exemplo/2026/10/noticia-de-outro-sitio-qualquer">e</a>
<a href="/login">f</a></body></html>"""

LOGIN = """<html><body><form><input type="text" name="u"><input type="password" name="p"></form></body></html>"""

FEED = """<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><title>Preço do táxi sobe na capital</title><link>http://HOST/2026/10/moradores-do-bairro-reclamam-da-falta-de-agua</link>
<description><![CDATA[<p>Os taxistas anunciaram um aumento do preço das corridas a partir de segunda-feira, depois de reunião com a associação.</p>]]></description>
<pubDate>Wed, 01 Oct 2026 10:00:00 GMT</pubDate><guid>n1</guid></item>
<item><title>Notícia curta</title><link>http://HOST/2026/10/segunda-noticia-com-um-titulo-bem-comprido</link><description>Curta.</description><guid>n2</guid></item>
</channel></rss>"""


@pytest.fixture()
def sitio(tmp_path, monkeypatch):
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    raiz = tmp_path / "www"
    (raiz / "2026" / "10").mkdir(parents=True)
    (raiz / "privado" / "2026" / "10").mkdir(parents=True)
    (raiz / "robots.txt").write_text("User-agent: *\nDisallow: /privado/\n", encoding="utf-8")
    (raiz / "index.html").write_text(INICIO, encoding="utf-8")
    (raiz / "login").write_text(LOGIN, encoding="utf-8")
    for nome in ("moradores-do-bairro-reclamam-da-falta-de-agua", "segunda-noticia-com-um-titulo-bem-comprido"):
        (raiz / "2026" / "10" / nome).write_text(ARTIGO, encoding="utf-8")
    (raiz / "privado" / "2026" / "10" / "noticia-que-o-robots-txt-proibe-recolher").write_text(ARTIGO, encoding="utf-8")

    class H(SimpleHTTPRequestHandler):
        extensions_map = {"": "text/html; charset=utf-8", ".txt": "text/plain", ".xml": "application/rss+xml"}

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(H, directory=str(raiz)))
    host = f"127.0.0.1:{srv.server_address[1]}"
    (raiz / "feed.xml").write_text(FEED.replace("HOST", host), encoding="utf-8")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://{host}"
    srv.shutdown()


@pytest.fixture()
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "nao.env"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "segredo")
    monkeypatch.setenv("UAN_RECOLHA_INTERVALO", "0")
    monkeypatch.setenv("UAN_YOUTUBE_CHAVE", "chave-falsa")
    return Config()


def test_extrair_pagina_ignora_menus_e_scripts():
    p = extrair_pagina(ARTIGO, "http://x/a")
    assert p.titulo == "Moradores do bairro reclamam da falta de água"
    assert "três semanas" in p.lead and "menu principal" not in p.lead and "não deve aparecer" not in p.lead
    assert p.data == "2026-10-01T09:00:00Z" and not p.requer_login
    assert extrair_pagina(LOGIN, "http://x/login").requer_login


def test_extrair_feed():
    itens = extrair_feed(FEED.replace("HOST", "x"))
    assert [i["titulo"] for i in itens] == ["Preço do táxi sobe na capital", "Notícia curta"]
    assert "<p>" not in itens[0]["resumo"] and itens[0]["id"] == "n1"


def test_recolha_de_sitio_respeita_robots_e_anonimiza(tmp_path, sitio, cfg):
    bd = BaseDados(tmp_path / "r.db")
    idf = adicionar_fonte(bd, "sitio", sitio + "/index.html", "Jornal local", "sup", max_itens=10)
    r = recolher_fonte(bd, cfg, idf, "sup")
    assert r["estado"].startswith("ok"), r
    pubs = bd.consultar("SELECT texto, plataforma, contexto FROM publicacoes")
    # dois artigos recolhidos; o de /privado/ (robots.txt), a categoria, o outro sítio e o login ficam de fora
    assert len(pubs) == 2
    assert all("[TELEFONE]" in p["texto"] and "[EMAIL]" in p["texto"] for p in pubs)
    assert pubs[0]["plataforma"] == "127.0.0.1" and pubs[0]["contexto"] == "Jornal local"
    lote = bd.consultar("SELECT * FROM lotes")[0]
    assert lote["via"] == "scraping_publico" and lote["id_fonte"] == idf and lote["descricao"].startswith("recolha automática")
    # uma segunda recolha não duplica
    assert recolher_fonte(bd, cfg, idf, "sup")["novos"] == 0
    assert bd.consultar("SELECT ultimo_estado FROM fontes")[0]["ultimo_estado"].startswith("ok")


def test_pagina_proibida_pelo_robots(tmp_path, sitio, cfg):
    bd = BaseDados(tmp_path / "r.db")
    idf = adicionar_fonte(bd, "pagina", sitio + "/privado/2026/10/noticia-que-o-robots-txt-proibe-recolher", "x", "sup")
    r = recolher_fonte(bd, cfg, idf, "sup")
    assert r["estado"].startswith("erro") and "robots" in r["estado"]
    assert bd.consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"] == 0


def test_pagina_com_login_nao_e_recolhida(tmp_path, sitio, cfg):
    bd = BaseDados(tmp_path / "r.db")
    idf = adicionar_fonte(bd, "pagina", sitio + "/login", "x", "sup")
    assert "autenticação" in recolher_fonte(bd, cfg, idf, "sup")["estado"]


def test_feed_rss(tmp_path, sitio, cfg):
    bd = BaseDados(tmp_path / "r.db")
    idf = adicionar_fonte(bd, "rss", sitio + "/feed.xml", "Feed", "sup")
    r = recolher_fonte(bd, cfg, idf, "sup")
    textos = [p["texto"] for p in bd.consultar("SELECT texto FROM publicacoes ORDER BY texto")]
    assert r["novos"] == 2
    assert any(t.startswith("Preço do táxi") and "taxistas" in t for t in textos)
    # resumo curto: o sistema vai à página buscar os primeiros parágrafos
    assert any(t.startswith("Notícia curta") and "três semanas" in t for t in textos)


class YouTubeFalso(ClienteHTTP):
    def __init__(self):
        super().__init__("teste", 0)
        self.pedidos = []

    def obter(self, url, verificar_robots=True):
        self.pedidos.append(url)
        if "/channels?" in url:
            d = {"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UUx"}}, "snippet": {}}]}
        elif "/playlistItems?" in url:
            d = {"items": [{"snippet": {"title": "Vídeo A", "resourceId": {"videoId": "vA"}}}]}
        elif "/commentThreads?" in url:
            if "pageToken" in url:
                d = {"items": [self._fio("c3", "Terceiro comentário com texto suficiente", "Ana")]}
            else:
                d = {"items": [self._fio("c1", "Primeiro comentário sobre o vídeo, @kota liga 912345678", "Joao Silva",
                                         [("c2", "Resposta ao primeiro comentário", "Maria")])], "nextPageToken": "p2"}
        else:
            raise AssertionError(url)
        return Resposta(200, "application/json", json.dumps(d).encode(), url)

    @staticmethod
    def _fio(cid, texto, autor, respostas=()):
        sn = lambda i, t, a: {"id": i, "snippet": {"textOriginal": t, "authorDisplayName": a,  # noqa: E731
                                                   "publishedAt": "2026-10-01T10:00:00Z"}}
        return {"snippet": {"topLevelComment": sn(cid, texto, autor)},
                "replies": {"comments": [sn(i, t, a) for i, t, a in respostas]}}


def test_youtube_canal(tmp_path, cfg):
    bd = BaseDados(tmp_path / "y.db")
    idf = adicionar_fonte(bd, "youtube_canal", "@canalangolano", "Canal X", "sup", max_itens=50)
    http = YouTubeFalso()
    r = recolher_fonte(bd, cfg, idf, "sup", http)
    assert r["novos"] == 3 and r["estado"].startswith("ok")
    assert "forHandle=%40canalangolano" in http.pedidos[0] and "key=chave-falsa" in http.pedidos[0]
    pubs = bd.consultar("SELECT texto, autor_pseudo, contexto, plataforma FROM publicacoes")
    assert all(p["plataforma"] == "YouTube" and p["contexto"] == "Vídeo A" for p in pubs)
    assert all("Joao" not in (p["autor_pseudo"] or "") for p in pubs)
    assert any("@[UTILIZADOR]" in p["texto"] and "[TELEFONE]" in p["texto"] for p in pubs)
    assert bd.consultar("SELECT via FROM lotes")[0]["via"] == "api_oficial"


def test_youtube_sem_chave(tmp_path, cfg, monkeypatch):
    monkeypatch.setenv("UAN_YOUTUBE_CHAVE", "")
    bd = BaseDados(tmp_path / "y.db")
    idf = adicionar_fonte(bd, "youtube_video", "vA", "Vídeo", "sup")
    assert "UAN_YOUTUBE_CHAVE" in recolher_fonte(bd, Config(), idf, "sup")["estado"]


def test_fonte_invalida(tmp_path):
    bd = BaseDados(tmp_path / "f.db")
    with pytest.raises(ValueError):
        adicionar_fonte(bd, "sitio", "ftp://x", "x", "sup")
    with pytest.raises(ValueError):
        adicionar_fonte(bd, "facebook", "https://x", "x", "sup")


def test_endereco_nao_http():
    with pytest.raises(ErroRecolha):
        ClienteHTTP("t", 0).obter("file:///etc/passwd")


def test_paginas_web_de_fontes(tmp_path, sitio, cfg, monkeypatch):
    pytest.importorskip("fastapi")
    import re
    from fastapi.testclient import TestClient
    from sistema.classificador import ClassificadorDemonstracao
    from sistema.utilizadores import criar_utilizador
    from sistema.web.app import criar_app

    monkeypatch.setenv("UAN_BD", str(tmp_path / "w.db"))
    app = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    criar_utilizador(app.state.bd, "sup", "Sup", "supervisor", "palavra-passe-longa")
    criar_utilizador(app.state.bd, "ana", "Ana", "analista", "palavra-passe-longa")
    c = TestClient(app)
    c.post("/entrar", data={"utilizador": "sup", "senha": "palavra-passe-longa"})
    pg = c.get("/fontes")
    assert pg.status_code == 200
    t = re.search(r'name="csrf" value="([^"]+)"', pg.text).group(1)
    c.post("/fontes/adicionar", data={"csrf": t, "tipo": "rss", "endereco": sitio + "/feed.xml", "nome": "Feed", "max_itens": "10"})
    r = c.post("/fontes/recolher", data={"csrf": t}, follow_redirects=False)
    assert r.status_code == 303
    bd = app.state.bd
    assert bd.consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"] == 2
    assert bd.consultar("SELECT COUNT(*) AS n FROM classificacoes")[0]["n"] == 2  # classificadas no fim da recolha
    a = TestClient(app)
    a.post("/entrar", data={"utilizador": "ana", "senha": "palavra-passe-longa"})
    assert a.get("/fontes").status_code == 403
