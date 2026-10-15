"""Testes do bloco 1 da interface: decisão sem recarregar, desfazer, realces, painel e revisão cega."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sistema import alertas as al  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.geografia import localizar_toponimos  # noqa: E402
from sistema.servico import classificar_pendentes, importar  # noqa: E402
from sistema.utilizadores import criar_utilizador  # noqa: E402
from sistema.web.app import criar_app, realcar  # noqa: E402

SENHA = "palavra-passe-longa"
FETCH = {"X-Pedido": "fetch"}


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "f.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    bd = a.state.bd
    criar_utilizador(bd, "sup", "Supervisor", "supervisor", SENHA)
    criar_utilizador(bd, "ana", "Ana", "analista", SENHA)
    f = tmp_path / "l.csv"
    f.write_text("id,textDisplay,publishedAt\n"
                 f"a,Vamos todos à praça do Lubango amanhã às 10h tragam tudo,{al.hoje_luanda()}\n"
                 f"b,Estão a esconder a verdade em Cabinda ligue 923456789,{al.hoje_luanda()}\n", encoding="utf-8")
    importar(bd, f, "YouTube", "api_oficial", "s")
    classificar_pendentes(bd, ClassificadorDemonstracao())
    return a


def entrar(app, u) -> TestClient:
    c = TestClient(app)
    assert c.post("/entrar", data={"utilizador": u, "senha": SENHA, "seguinte": "/"}, follow_redirects=False).status_code == 303
    return c


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_realce_de_lugares_e_mascaras_com_escape():
    h = str(realcar("<b>Ataque</b> no Lubango, ligue [TELEFONE] ou @[UTILIZADOR]"))
    assert "&lt;b&gt;Ataque&lt;/b&gt;" in h and "<b>" not in h
    assert '<mark class="lugar" title="Huíla">Lubango</mark>' in h
    assert '<mark class="mascara"' in h and h.count("<mark") == 3
    assert [(a, b) for a, b, _ in localizar_toponimos("Icolo e Bengo")] == [(0, 13)]


def test_decisao_por_fetch_e_desfazer(app):
    bd = app.state.bd
    ana = entrar(app, "ana")
    pag = ana.get("/fila")
    assert "data-decisao" in pag.text and 'mark class="lugar"' in pag.text and "item marca-" in pag.text
    ids = re.findall(r'data-id="([0-9a-f]+)"', pag.text)
    n0 = bd.n_fila("ana")
    r = ana.post("/rever", data={"csrf": csrf(pag.text), "id_pub": ids[0], "categoria": "Mobilizacao", "origem": "fila"},
                 headers=FETCH)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["nome"] == "Mobilização Hostil" and d["n_fila"] == n0 - 1 and d["alertas_novos"] >= 1
    assert bd.consultar("SELECT COUNT(*) AS n FROM alertas WHERE tipo='confirmado'")[0]["n"] == 1
    # desfazer: a decisão sai, o item volta à fila e o alerta é anulado (o e-mail ainda não saiu)
    u = ana.post("/rever/desfazer", data={"csrf": csrf(pag.text), "id_pub": ids[0]}, headers=FETCH)
    assert u.status_code == 200 and u.json()["alerta_anulado"] is True and u.json()["n_fila"] == n0
    assert bd.consultar("SELECT COUNT(*) AS n FROM revisoes")[0]["n"] == 0
    assert bd.consultar("SELECT COUNT(*) AS n FROM alertas")[0]["n"] == 0
    assert bd.consultar("SELECT COUNT(*) AS n FROM auditoria WHERE accao='revisao_desfeita'")[0]["n"] == 1
    # desfazer outra vez: já não há nada para desfazer, resposta JSON com o motivo
    again = ana.post("/rever/desfazer", data={"csrf": csrf(pag.text), "id_pub": ids[0]}, headers=FETCH)
    assert again.status_code == 409 and "desfazer" in again.json()["detail"]


def test_so_o_proprio_analista_desfaz(app):
    bd = app.state.bd
    ana, sup = entrar(app, "ana"), entrar(app, "sup")
    pag = ana.get("/fila")
    idp = re.findall(r'data-id="([0-9a-f]+)"', pag.text)[0]
    ana.post("/rever", data={"csrf": csrf(pag.text), "id_pub": idp, "categoria": "Normal", "origem": "fila"}, headers=FETCH)
    ps = sup.get("/fila")
    assert sup.post("/rever/desfazer", data={"csrf": csrf(ps.text), "id_pub": idp}, headers=FETCH).status_code == 409
    assert bd.consultar("SELECT COUNT(*) AS n FROM revisoes")[0]["n"] == 1


def test_envio_normal_continua_a_funcionar(app):
    ana = entrar(app, "ana")
    pag = ana.get("/fila")
    idp = re.findall(r'data-id="([0-9a-f]+)"', pag.text)[0]
    r = ana.post("/rever", data={"csrf": csrf(pag.text), "id_pub": idp, "categoria": "Normal", "origem": "fila",
                                 "voltar": "/fila"}, follow_redirects=True)
    assert r.status_code == 200 and "Decisão gravada" in r.text and "data-toast-servidor" in r.text


def test_painel_parcial_e_selo_de_revisao_cega(app):
    bd = app.state.bd
    ana = entrar(app, "ana")
    idp = bd.consultar("SELECT id_pub FROM publicacoes LIMIT 1")[0]["id_pub"]
    parcial = ana.get(f"/publicacao/{idp}?parcial=1")
    assert parcial.status_code == 200 and "publicacao-corpo" in parcial.text and 'class="menu"' not in parcial.text
    assert "Revisão cega activa" not in ana.get("/fila").text
    bd.definir("revisao_cega", "1", "sup")
    pag = ana.get("/fila").text
    assert "selo-cega" in pag and "item marca-" not in pag and "prob-pilha" not in pag   # cega: sem pistas da sugestão
