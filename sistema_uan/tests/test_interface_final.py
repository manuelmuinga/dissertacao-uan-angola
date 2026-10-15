"""Testes dos blocos 3 a 5 da interface: Sobre o modelo, demonstração, visita guiada, sino e tempo real, tema."""

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
from sistema import demonstracao as demo  # noqa: E402
from sistema.base_dados import BaseDados  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.servico import classificar_pendentes, importar  # noqa: E402
from sistema.utilizadores import criar_utilizador  # noqa: E402
from sistema.web.app import criar_app  # noqa: E402

SENHA = "palavra-passe-longa"
CSS = (RAIZ / "sistema" / "web" / "estatico" / "estilo.css").read_text(encoding="utf-8")
JS = (RAIZ / "sistema" / "web" / "estatico" / "app.js").read_text(encoding="utf-8")


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "i.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    monkeypatch.delenv("UAN_DEMONSTRACAO", raising=False)
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    bd = a.state.bd
    criar_utilizador(bd, "ana", "Ana", "analista", SENHA)
    criar_utilizador(bd, "rui", "Rui", "analista", SENHA)
    f = tmp_path / "l.csv"
    f.write_text("id,textDisplay,publishedAt\n"
                 f"a,Vamos todos à praça do Huambo amanhã às 10h tragam tudo,{al.hoje_luanda()}\n"
                 f"b,Hoje choveu no Lubango,{al.hoje_luanda()}\n", encoding="utf-8")
    importar(bd, f, "YouTube", "api_oficial", "s")
    classificar_pendentes(bd, ClassificadorDemonstracao())
    return a


def entrar(app, u="ana") -> TestClient:
    c = TestClient(app)
    c.post("/entrar", data={"utilizador": u, "senha": SENHA, "seguinte": "/"})
    return c


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_sobre_o_modelo(app):
    c = entrar(app)
    h = c.get("/modelo").text
    assert "Sobre o modelo" in h and "bertimbau_uan_v13_s42" in h
    assert "80,8%" in h and "53,3%" in h and "23,5%" in h  # F1 global, angolano e Desinformação angolana
    assert "Limitações conhecidas" in h and "classificador de demonstração" in h
    assert "Ainda não há decisões de analistas" in h
    # depois de uma decisão, aparece o acordo observado nesta instalação
    bd = app.state.bd
    idp = bd.consultar("SELECT id_pub FROM publicacoes WHERE texto LIKE '%Huambo%'")[0]["id_pub"]
    bd.gravar_revisao(idp, "ana", "Mobilizacao", 1, None)
    h = c.get("/modelo").text
    assert "Concordância analista–modelo" in h and "100,0%" in h


def test_visita_guiada_so_na_primeira_entrada(app):
    c = entrar(app)
    h = c.get("/").text
    assert "data-visita-auto" in h and 'data-visita-passo="1"' in h and 'data-visita-passo="4"' in h
    assert c.post("/visita/vista", data={"csrf": csrf(h)}).json() == {"ok": True}
    assert "data-visita-auto" not in c.get("/").text
    assert "data-visita-auto" in entrar(app, "rui").get("/").text  # cada utilizador tem a sua
    assert c.post("/visita/vista", data={"csrf": "x"}).status_code == 400


def test_sino_e_estado_em_tempo_real(app):
    c = entrar(app)
    assert c.get("/alertas/recentes").json() == {"por_ver": 0, "alertas": []}
    bd = app.state.bd
    idp = bd.consultar("SELECT id_pub FROM publicacoes WHERE texto LIKE '%Huambo%'")[0]["id_pub"]
    h = c.get("/fila").text
    c.post("/rever", data={"csrf": csrf(h), "id_pub": idp, "categoria": "Mobilizacao", "origem": "fila"},
           headers={"X-Pedido": "fetch"})
    e = entrar(app, "rui").get("/estado").json()
    assert e["alertas_por_ver"] == 1 and e["ultimo_alerta"]["titulo"].startswith("Ameaça confirmada")
    assert e["ultimo_alerta"]["ligacao"] == f"/publicacao/{idp}" and "fila" in e
    r = c.get("/alertas/recentes").json()
    assert r["por_ver"] == 1 and len(r["alertas"]) == 1 and r["alertas"][0]["visto"] is False
    assert "tragam" not in str(r)  # o sino não mostra o texto da publicação
    h = c.get("/").text
    assert 'data-sino' in h and re.search(r'data-sino-n\s*>1<', h)


def test_tema_icones_e_paleta(app):
    c = entrar(app)
    h = c.get("/").text
    assert "<html lang=\"pt\">" in h  # automático por omissão
    assert '<symbol id="i-mapa"' in h and '<use href="#i-fila">' in h and 'id="paleta"' in h
    c.cookies.set("uan_tema", "escuro")
    assert '<html lang="pt" data-tema="escuro">' in c.get("/").text
    c.cookies.set("uan_tema", "<script>")
    assert "data-tema" not in c.get("/").text.split("<head>")[0]
    assert ":root[data-tema=\"escuro\"]" in CSS and "prefers-color-scheme: dark" in CSS
    assert "Control+K" in h and '"k"' in JS and "/visita/vista" in JS
    # estados vazios ilustrados: só imagens embutidas (a CSP só permite 'self' e data:)
    assert "--i-alertas: url(\"data:image/svg+xml," in CSS and "http://" not in CSS.replace("http://www.w3.org", "")


def test_modo_demonstracao(tmp_path, monkeypatch):
    real = tmp_path / "real.db"
    BaseDados(real)  # a base real existe e fica intacta
    monkeypatch.setenv("UAN_BD", str(tmp_path / "demonstracao.db"))
    monkeypatch.setenv("UAN_DEMONSTRACAO", "1")
    monkeypatch.setenv("UAN_SMTP_SERVIDOR", "smtp.exemplo.ao")
    monkeypatch.setenv("UAN_SMTP_REMETENTE", "a@exemplo.ao")
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    cfg = Config()
    assert cfg.demonstracao and not cfg.email_configurado  # na demonstração nenhum e-mail sai
    a = criar_app(cfg, sincrono=True)
    bd = a.state.bd
    n = bd.consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"]
    assert n > 800 and bd.consultar("SELECT COUNT(*) AS n FROM revisoes")[0]["n"] > 50
    assert bd.consultar("SELECT COUNT(*) AS n FROM alertas")[0]["n"] > 10
    assert bd.consultar("SELECT COUNT(*) AS n FROM publicacoes WHERE plataforma != 'YouTube (fictício)'")[0]["n"] == 0
    assert BaseDados(real).consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"] == 0
    c = TestClient(a)
    assert "demo.analista" in c.get("/entrar").text and "Demonstração" in c.get("/entrar").text
    c.post("/entrar", data={"utilizador": "demo.analista", "senha": demo.SENHA, "seguinte": "/"})
    h = c.get("/mapa?dias=84").text
    assert 'class="faixa-demo"' in h and "Dados fictícios" in h
    assert "Classificador de demonstração.</b>" not in h  # a faixa da demonstração substitui o aviso
    # arrancar outra vez não duplica os dados
    criar_app(Config(), sincrono=True)
    assert bd.consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"] == n


def test_dados_ficticios_reprodutiveis():
    hoje = al.hoje_luanda()
    a, b = demo.gerar_registos(hoje), demo.gerar_registos(hoje)
    assert a == b and len({r["id"] for r, _ in a}) == len(a)
    assert all(r["id"].startswith("demo-") for r, _ in a)
