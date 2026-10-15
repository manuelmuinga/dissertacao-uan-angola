"""Testes do bloco 2 da interface: mapa interactivo, evolução no tempo, exportação e tabelas ordenáveis."""

from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sistema import alertas as al  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.servico import classificar_pendentes, importar  # noqa: E402
from sistema.utilizadores import criar_utilizador  # noqa: E402
from sistema.web.app import criar_app, linha_tendencia  # noqa: E402

SENHA = "palavra-passe-longa"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "m.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    bd = a.state.bd
    criar_utilizador(bd, "ana", "Ana", "analista", SENHA)
    hoje = al.hoje_luanda()
    linhas = ["id,textDisplay,publishedAt"]
    for i in range(6):
        d = hoje - timedelta(days=7 * i)
        linhas.append(f"l{i},Vamos todos à praça do Lubango amanhã tragam tudo número {i},{d}")
        linhas.append(f"c{i},Notícia de Cabinda sobre o mercado {i},{d}")
    f = tmp_path / "l.csv"
    f.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    importar(bd, f, "YouTube", "api_oficial", "s")
    classificar_pendentes(bd, ClassificadorDemonstracao())
    for i in range(6):
        idp = bd.consultar("SELECT id_pub FROM publicacoes WHERE texto LIKE ?", (f"%Lubango%número {i}%",))[0]["id_pub"]
        bd.gravar_revisao(idp, "ana", "Mobilizacao", 1, None)
    return a


def entrar(app) -> TestClient:
    c = TestClient(app)
    c.post("/entrar", data={"utilizador": "ana", "senha": SENHA, "seguinte": "/"})
    return c


def test_baldes_semanais_e_diarios():
    p = al.Periodo(date(2026, 1, 1), date(2026, 3, 31))  # 90 dias
    b = al.baldes(p)
    assert b[0].inicio == p.inicio and b[-1].fim == p.fim
    assert all(x.dias == 7 for x in b[1:]) and len(b) == 13
    assert sum(x.dias for x in b) == p.dias
    d = al.baldes(al.Periodo(date(2026, 1, 1), date(2026, 1, 10)))
    assert len(d) == 10 and all(x.dias == 1 for x in d)
    longo = al.baldes(al.Periodo(date(2025, 1, 1), date(2026, 12, 31)))
    assert len(longo) <= 26 and sum(x.dias for x in longo) == 730


def test_serie_por_provincia(app):
    bd = app.state.bd
    per = al.periodo(dias=42)
    s = al.serie(bd, per, "confirmadas")
    assert len(s["baldes"]) == 6 and s["passo_dias"] == 7
    assert sum(s["valores"]["HUI"]) == 6 and sum(s["valores"]["CAB"]) == 0
    assert sum(s["mencoes"]["CAB"]) == 6 and sum(s["mencoes"]["NAC"]) == 12
    assert sum(s["valores"]["NAC"]) == al.dados_mapa(bd, per)["nacional"]["valor"]


def test_linha_tendencia_svg():
    h = str(linha_tendencia([0, 2, 5, 3], rotulo="Huíla"))
    assert h.startswith("<svg") and 'class="linha-tendencia desce"' in h and "Huíla: 0, 2, 5, 3" in h
    assert "script" not in h
    assert str(linha_tendencia([4])) == ""
    assert "sobe" in str(linha_tendencia([1, 3]))


def test_pagina_do_mapa_interactiva(app):
    c = entrar(app)
    r = c.get("/mapa?dias=42")
    assert r.status_code == 200
    h = r.text
    assert 'data-prov="HUI"' in h and 'data-nome="Huíla"' in h and 'class="mapa-cartao"' in h
    assert "data-tempo" in h and 'data-ordenar' in h and 'tabela-envolvente fixa' in h
    assert h.count('class="linha-tendencia') >= 19  # 18 províncias + KPI
    serie = json.loads(re.search(r'<script type="application/json" id="mapa-serie">(.*?)</script>', h, re.S).group(1))
    assert len(serie["baldes"]) == 6 and sum(serie["valores"]["HUI"]) == 6
    # o JSON embutido não fecha a etiqueta <script> (escape de "<")
    assert "</script>" not in re.search(r'id="mapa-serie">(.*?)</script>', h, re.S).group(1)
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


def test_exportar_mapa_svg(app):
    c = entrar(app)
    r = c.get("/mapa.svg?dias=42")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml")
    t = r.text
    assert t.startswith("<?xml") and 'xmlns="http://www.w3.org/2000/svg"' in t
    assert t.count("<path") == 18 and "menos de 5 publicações" in t and "uso interno" in t
    per = al.periodo(dias=42)
    assert per.rotulo() in t
    assert app.state.bd.consultar("SELECT COUNT(*) AS n FROM auditoria WHERE accao='exportacao_mapa'")[0]["n"] == 1
    # sem sessão não há mapa
    assert TestClient(app).get("/mapa.svg", follow_redirects=False).status_code == 303


def test_relatorio_com_tendencias_e_tabelas_ordenaveis(app):
    c = entrar(app)
    h = c.get("/relatorio?dias=42").text
    assert h.count("data-ordenar") >= 3 and 'data-png="/mapa.svg' in h and 'class="linha-tendencia' in h
    assert '<tr data-prov="HUI">' in h
