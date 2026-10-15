"""Testes da aplicação web: acesso, papéis, revisão, avaliação e protecção de dados."""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sistema.base_dados import BaseDados  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config, carregar_env  # noqa: E402
from sistema.servico import classificar_pendentes, exportar_revisoes, gerar_amostra_controlo, importar, metricas  # noqa: E402
from sistema.utilizadores import (ErroAutenticacao, autenticar, criar_utilizador, hash_senha,  # noqa: E402
                                  verificar_senha)
from sistema.web.app import criar_app  # noqa: E402

SEGREDO = "segredo-de-teste"
SENHA = "palavra-passe-longa"
TEXTOS = [
    "Bom dia a todos, o jogo de ontem foi bom",
    "URGENTE partilha antes que apaguem, estão a esconder tudo",
    "Vamos todos amanhã às 8h, quem não aparecer é traidor, tragam tudo",
    "Esses não merecem estar aqui, são todos iguais",
    "A estrada do bairro continua cheia de buracos",
    "Fonte interna diz que estão a esconder os números, urgente",
    "Obrigado pela reportagem, muito bem feita",
    "Vamos todos à praça amanhã às 10h",
]


@pytest.fixture()
def csv_lote(tmp_path: Path) -> Path:
    p = tmp_path / "lote.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "authorDisplayName", "textDisplay", "publishedAt"])
        for i, t in enumerate(TEXTOS):
            w.writerow([f"c{i}", f"@pessoa{i}", t + f" ligue 923 456 78{i}", "2026-10-01T10:00:00Z"])
    return p


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "web.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", SEGREDO)
    monkeypatch.delenv("UAN_CHAVE_API", raising=False)
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "nao-existe.env"))
    return criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)


def csrf(resp) -> str:
    m = re.search(r'name="csrf" value="([^"]+)"', resp.text)
    assert m, "página sem token CSRF"
    return m.group(1)


def entrar(app, utilizador, senha=SENHA) -> TestClient:
    c = TestClient(app)
    r = c.post("/entrar", data={"utilizador": utilizador, "senha": senha, "seguinte": "/"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return c


@pytest.fixture()
def contas(app):
    bd = app.state.bd
    criar_utilizador(bd, "sup", "Supervisor", "supervisor", SENHA)
    criar_utilizador(bd, "ana", "Analista A", "analista", SENHA)
    criar_utilizador(bd, "beto", "Analista B", "analista", SENHA)
    return bd


# ---------------- palavras-passe e sessões ----------------
def test_hash_senha():
    h = hash_senha("abcdefghij")
    assert h.startswith("pbkdf2_sha256$") and "abcdefghij" not in h
    assert verificar_senha("abcdefghij", h) and not verificar_senha("abcdefghik", h)


def test_bloqueio_apos_falhas(tmp_path):
    bd = BaseDados(tmp_path / "b.db")
    criar_utilizador(bd, "ana", "Ana", "analista", SENHA)
    for _ in range(5):
        with pytest.raises(ErroAutenticacao):
            autenticar(bd, "ana", "errada")
    with pytest.raises(ErroAutenticacao, match="bloqueada"):
        autenticar(bd, "ana", SENHA)


def test_configuracao_inicial_e_entrada(app):
    c = TestClient(app)
    assert c.get("/", follow_redirects=False).headers["location"].startswith("/entrar")
    assert c.get("/entrar", follow_redirects=False).headers["location"] == "/configurar"
    r = c.post("/configurar", data={"utilizador": "chefe", "nome": "Chefe", "senha": SENHA, "senha2": SENHA},
               follow_redirects=False)
    assert r.status_code == 303
    # depois do primeiro utilizador, a configuração inicial fecha
    assert c.get("/configurar", follow_redirects=False).headers["location"] == "/entrar"
    assert c.post("/entrar", data={"utilizador": "chefe", "senha": "errada"}).status_code == 401
    c = entrar(app, "chefe")
    r = c.get("/")
    assert r.status_code == 200 and "Panorama" in r.text
    assert r.headers["X-Frame-Options"] == "DENY" and "default-src 'self'" in r.headers["Content-Security-Policy"]


def test_redireccionamento_externo_bloqueado(app, contas):
    c = TestClient(app)
    r = c.post("/entrar", data={"utilizador": "ana", "senha": SENHA, "seguinte": "//mal.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_papeis(app, contas):
    ana = entrar(app, "ana")
    for url in ("/metricas", "/utilizadores", "/auditoria", "/definicoes"):
        assert ana.get(url).status_code == 403
    assert ana.get("/fila").status_code == 200
    sup = entrar(app, "sup")
    for url in ("/metricas", "/utilizadores", "/auditoria", "/definicoes", "/lotes"):
        assert sup.get(url).status_code == 200


def test_csrf_obrigatorio(app, contas, csv_lote):
    sup = entrar(app, "sup")
    with csv_lote.open("rb") as f:
        r = sup.post("/lotes/importar", data={"csrf": "falso", "plataforma": "YouTube", "via": "api_oficial"},
                     files={"ficheiro": ("lote.csv", f, "text/csv")})
    assert r.status_code == 400
    assert app.state.bd.consultar("SELECT COUNT(*) AS n FROM lotes")[0]["n"] == 0


# ---------------- fluxo completo pela web ----------------
def importar_web(app, cli, ficheiro: Path):
    token = csrf(cli.get("/lotes"))
    with ficheiro.open("rb") as f:
        r = cli.post("/lotes/importar", data={"csrf": token, "plataforma": "YouTube", "via": "api_oficial",
                                             "descricao": "teste"},
                     files={"ficheiro": ("comentarios.csv", f, "text/csv")}, follow_redirects=False)
    assert r.status_code == 303, r.text


def test_fluxo_web_com_dois_analistas(app, contas, csv_lote):
    bd = app.state.bd
    sup = entrar(app, "sup")
    importar_web(app, sup, csv_lote)
    assert bd.consultar("SELECT COUNT(*) AS n FROM classificacoes")[0]["n"] == len(TEXTOS)
    # anonimização: nem nomes de autor nem telefones ficam guardados
    textos = " ".join(r["texto"] for r in bd.consultar("SELECT texto FROM publicacoes"))
    autores = {r["autor_pseudo"] for r in bd.consultar("SELECT autor_pseudo FROM publicacoes")}
    assert "923 456" not in textos and "[TELEFONE]" in textos and not any("pessoa" in (a or "") for a in autores)
    lote = bd.consultar("SELECT * FROM lotes")[0]
    assert lote["importado_por"] == "sup" and lote["ficheiro"] == "comentarios.csv"

    ana, beto = entrar(app, "ana"), entrar(app, "beto")
    pagina = ana.get("/fila")
    ids = re.findall(r'name="id_pub" value="([^"]+)"', pagina.text)
    n_sinalizadas = bd.n_fila()
    assert len(ids) == n_sinalizadas > 0
    t = csrf(pagina)
    for i, idp in enumerate(ids):
        r = ana.post("/rever", data={"csrf": t, "id_pub": idp, "categoria": "Odio" if i == 0 else "Normal",
                                     "posicao": str(i + 1), "voltar": "/fila"}, follow_redirects=False)
        assert r.status_code == 303 and "aviso=revisao" in r.headers["location"]
    assert bd.n_fila("ana") == 0
    # o segundo analista continua a ver todos os itens (revisão independente)
    assert bd.n_fila("beto") == n_sinalizadas
    tb = csrf(beto.get("/fila"))
    for idp in ids:
        beto.post("/rever", data={"csrf": tb, "id_pub": idp, "categoria": "Normal", "voltar": "/fila"})
    m = metricas(bd)
    assert set(m["por_analista"]) == {"ana", "beto"}
    par = m["entre_analistas"][0]
    assert par["analistas"] == ["ana", "beto"] and par["n_comuns"] == len(ids)
    assert par["concordancia"] == pytest.approx((len(ids) - 1) / len(ids), abs=1e-3)
    # exportação: o item em que discordaram fica de fora
    sup_csv = sup.get("/metricas/revisoes.csv")
    linhas = list(csv.DictReader(sup_csv.text.splitlines()))
    assert len(linhas) == len(ids) - 1 and {l["origem"] for l in linhas} == {"revisao_sistema"}
    assert sup.get("/metricas").status_code == 200
    accoes = {r["accao"] for r in bd.consultar("SELECT DISTINCT accao FROM auditoria")}
    assert {"entrada", "importacao", "classificacao", "revisao", "exportacao_revisoes"} <= accoes


def test_revisao_cega_esconde_sugestao(app, contas, csv_lote):
    bd = app.state.bd
    sup = entrar(app, "sup")
    importar_web(app, sup, csv_lote)
    ana = entrar(app, "ana")
    assert "Sugestão do modelo" in ana.get("/fila").text
    sup.post("/definicoes", data={"csrf": csrf(sup.get("/definicoes")), "cega": "1"})
    pagina = ana.get("/fila")
    assert "Sugestão do modelo" not in pagina.text and "Revisão cega activa" in pagina.text
    idp = re.findall(r'name="id_pub" value="([^"]+)"', pagina.text)[0]
    ana.post("/rever", data={"csrf": csrf(pagina), "id_pub": idp, "categoria": "Normal", "voltar": "/fila"})
    assert bd.consultar("SELECT cega FROM revisoes WHERE analista='ana'")[0]["cega"] == 1


def test_amostra_de_controlo(app, contas, csv_lote):
    bd = app.state.bd
    sup = entrar(app, "sup")
    importar_web(app, sup, csv_lote)
    n_normais = bd.consultar("SELECT COUNT(*) AS n FROM classificacoes WHERE categoria='Normal'")[0]["n"]
    sup.post("/amostra/gerar", data={"csrf": csrf(sup.get("/amostra")), "n": "3", "semente": "42"})
    assert bd.consultar("SELECT COUNT(*) AS n FROM amostra_controlo")[0]["n"] == min(3, n_normais)
    ana = entrar(app, "ana")
    pagina = ana.get("/amostra")
    assert "Sugestão do modelo" not in pagina.text
    ids = re.findall(r'name="id_pub" value="([^"]+)"', pagina.text)
    t = csrf(pagina)
    for i, idp in enumerate(ids):
        ana.post("/rever", data={"csrf": t, "id_pub": idp, "categoria": "Mobilizacao" if i == 0 else "Normal",
                                 "origem": "amostra", "voltar": "/amostra"})
    am = metricas(bd)["amostra_controlo"]["ana"]
    assert am["revistos"] == len(ids) and am["ameacas_nao_sinalizadas"] == 1 and am["ic95"][0] < am["taxa"]
    # revisões da amostra não contam para a precisão da fila
    assert metricas(bd)["n_revistas"] == 0


def test_amostra_reprodutivel(tmp_path, csv_lote):
    res = []
    for k in range(2):
        bd = BaseDados(tmp_path / f"r{k}.db")
        importar(bd, csv_lote, "YouTube", "manual", SEGREDO)
        classificar_pendentes(bd, ClassificadorDemonstracao())
        gerar_amostra_controlo(bd, 2, "sup", semente=7)
        res.append([r["id_pub"] for r in bd.consultar("SELECT id_pub FROM amostra_controlo ORDER BY ordem")])
    assert res[0] == res[1]


def test_utilizadores_pela_web(app, contas):
    sup = entrar(app, "sup")
    t = csrf(sup.get("/utilizadores"))
    assert sup.post("/utilizadores/criar", data={"csrf": t, "utilizador": "Nova Pessoa", "nome": "x", "papel": "analista",
                                                 "senha": SENHA}).status_code == 400
    assert sup.post("/utilizadores/criar", data={"csrf": t, "utilizador": "carla", "nome": "Carla", "papel": "analista",
                                                 "senha": SENHA}, follow_redirects=False).status_code == 303
    carla = entrar(app, "carla")
    sup.post("/utilizadores/carla/estado", data={"csrf": t, "activo": "0"})
    # a sessão aberta deixa de valer quando a conta é desactivada
    assert carla.get("/", follow_redirects=False).status_code == 303
    with pytest.raises(AssertionError):
        entrar(app, "carla")


def test_pagina_publicacao_esconde_revisoes_de_outros(app, contas, csv_lote):
    bd = app.state.bd
    sup = entrar(app, "sup")
    importar_web(app, sup, csv_lote)
    idp = bd.fila(1)[0]["id_pub"]
    bd.gravar_revisao(idp, "beto", "Odio", 1, "nota do beto")
    assert "nota do beto" not in entrar(app, "ana").get(f"/publicacao/{idp}").text
    assert "nota do beto" in sup.get(f"/publicacao/{idp}").text


def test_texto_escapado(app, contas, tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("texto\n<script>alert(1)</script> vamos todos amanhã às 8h\n", encoding="utf-8")
    sup = entrar(app, "sup")
    importar_web(app, sup, p)
    pagina = entrar(app, "ana").get("/fila").text
    assert "<script>alert(1)</script>" not in pagina and "&lt;script&gt;" in pagina


# ---------------- base de dados e serviço ----------------
def test_migracao_da_versao_01(tmp_path):
    caminho = tmp_path / "v01.db"
    con = sqlite3.connect(caminho)
    con.executescript("""
        CREATE TABLE lotes (id_lote INTEGER PRIMARY KEY AUTOINCREMENT, plataforma TEXT NOT NULL, via TEXT NOT NULL,
            descricao TEXT, ficheiro TEXT, importado_em TEXT NOT NULL, n_recebidos INTEGER NOT NULL DEFAULT 0,
            n_novos INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE publicacoes (id_pub TEXT PRIMARY KEY, id_lote INTEGER, plataforma TEXT NOT NULL, autor_pseudo TEXT,
            texto TEXT NOT NULL, data_publicacao TEXT, recolhido_em TEXT NOT NULL, contexto TEXT);
        CREATE TABLE classificacoes (id_pub TEXT PRIMARY KEY, modelo TEXT NOT NULL, versao TEXT NOT NULL,
            probabilidades TEXT NOT NULL, categoria TEXT NOT NULL, confianca REAL NOT NULL, prioridade REAL NOT NULL,
            classificado_em TEXT NOT NULL, duracao_ms REAL NOT NULL);
        CREATE TABLE revisoes (id_pub TEXT PRIMARY KEY, analista TEXT NOT NULL, categoria TEXT NOT NULL,
            concorda INTEGER NOT NULL, posicao_fila INTEGER, nota TEXT, revisto_em TEXT NOT NULL);
        INSERT INTO lotes VALUES (1,'YouTube','manual',NULL,NULL,'2026-10-01T00:00:00+00:00',1,1);
        INSERT INTO publicacoes VALUES ('p1',1,'YouTube',NULL,'texto','2026-10-01','2026-10-01T00:00:00+00:00',NULL);
        INSERT INTO classificacoes VALUES ('p1','m','v','{"Normal":0.2,"Desinformacao":0.1,"Odio":0.6,"Mobilizacao":0.1}',
            'Odio',0.6,0.8,'2026-10-01T00:00:01+00:00',5);
        INSERT INTO revisoes VALUES ('p1','antigo','Odio',1,1,NULL,'2026-10-01T00:00:02+00:00');
    """)
    con.commit(); con.close()
    bd = BaseDados(caminho)
    r = bd.consultar("SELECT * FROM revisoes")
    assert len(r) == 1 and r[0]["origem_fila"] == "fila" and r[0]["analista"] == "antigo"
    bd.gravar_revisao("p1", "novo", "Normal", None, None)
    assert bd.consultar("SELECT COUNT(*) AS n FROM revisoes")[0]["n"] == 2


def test_gravacao_por_sublote(tmp_path, csv_lote):
    bd = BaseDados(tmp_path / "s.db")
    importar(bd, csv_lote, "YouTube", "manual", SEGREDO)
    passos = []
    out = classificar_pendentes(bd, ClassificadorDemonstracao(), sublote=3, progresso=lambda f, t: passos.append((f, t)))
    assert out["classificados"] == len(TEXTOS) and out["sublote"] == 3
    assert passos == [(3, 8), (6, 8), (8, 8)]
    assert "segundos_ate_primeiro_sublote" in out


def test_carregar_env(tmp_path, monkeypatch):
    f = tmp_path / "uan.env"
    f.write_text("# comentário\nUAN_TESTE_A=um valor\nUAN_TESTE_B=\"entre aspas\"\nUAN_TESTE_C=ficheiro\n", encoding="utf-8")
    monkeypatch.delenv("UAN_TESTE_A", raising=False)
    monkeypatch.delenv("UAN_TESTE_B", raising=False)
    monkeypatch.setenv("UAN_TESTE_C", "ambiente")
    definidas = carregar_env(f)
    import os
    assert os.environ["UAN_TESTE_A"] == "um valor" and os.environ["UAN_TESTE_B"] == "entre aspas"
    assert os.environ["UAN_TESTE_C"] == "ambiente" and "UAN_TESTE_C" not in definidas
    for k in definidas:
        monkeypatch.delenv(k)


def test_copia_de_seguranca(tmp_path, csv_lote):
    bd = BaseDados(tmp_path / "o.db")
    importar(bd, csv_lote, "YouTube", "manual", SEGREDO)
    copia = bd.copia_seguranca(tmp_path / "copias" / "c.db")
    assert BaseDados(copia).consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"] == len(TEXTOS)
