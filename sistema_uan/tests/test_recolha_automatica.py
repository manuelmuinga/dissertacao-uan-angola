"""Recolha automática: o servidor percorre as fontes activas de tantos em tantos minutos."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sistema import recolha  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.recolha import adicionar_fonte  # noqa: E402
from sistema.utilizadores import criar_utilizador  # noqa: E402
from sistema.web.app import _unidades_youtube, criar_app  # noqa: E402

SENHA = "palavra-passe-longa"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "a.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    monkeypatch.delenv("UAN_DEMONSTRACAO", raising=False)
    chamadas = []

    def falso(bd, cfg, id_fonte, quem="sistema", http=None):
        chamadas.append((id_fonte, quem))
        return {"id_fonte": id_fonte, "estado": "ok"}
    monkeypatch.setattr("sistema.web.app.recolher_fonte", falso)
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    a.state.chamadas = chamadas
    criar_utilizador(a.state.bd, "sup", "Sup", "supervisor", SENHA)
    adicionar_fonte(a.state.bd, "youtube_canal", "@canal", "", "sup")
    adicionar_fonte(a.state.bd, "pagina", "https://exemplo.ao/x", "", "sup")
    return a


def entrar(app) -> TestClient:
    c = TestClient(app)
    c.post("/entrar", data={"utilizador": "sup", "senha": SENHA, "seguinte": "/"})
    return c


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def test_desligada_nao_recolhe(app):
    assert app.state.agendador_tick() is False and app.state.chamadas == []


def test_ligar_recolhe_ja_e_depois_no_intervalo(app):
    c = entrar(app)
    h = c.get("/fontes").text
    assert "Recolha automática" in h and "desligada" in h
    c.post("/fontes/automatica", data={"csrf": csrf(h), "minutos": "60"})
    t0 = datetime.now(timezone.utc)
    assert app.state.agendador_tick(t0) is True                      # primeira volta logo
    assert [q for _, q in app.state.chamadas] == ["recolha_automatica"] * 2
    assert app.state.agendador_tick(t0 + timedelta(minutes=30)) is False   # ainda não chegou a hora
    assert app.state.agendador_tick(t0 + timedelta(minutes=61)) is True
    assert len(app.state.chamadas) == 4
    h = c.get("/fontes").text
    assert "ligada" in h and "De hora a hora".lower() in h.lower()


def test_fontes_inactivas_ficam_de_fora(app):
    with app.state.bd.ligacao() as c:
        c.execute("UPDATE fontes SET activa = 0 WHERE tipo = 'pagina'")
    app.state.bd.definir("recolha_auto_minutos", "15", "t")
    assert app.state.agendador_tick() is True and [i for i, _ in app.state.chamadas] == [1]


def test_intervalo_invalido_e_quota(app):
    c = entrar(app)
    h = c.get("/fontes").text
    assert c.post("/fontes/automatica", data={"csrf": csrf(h), "minutos": "7"}).status_code == 400
    assert _unidades_youtube("youtube_pesquisa", 100) == 110 and _unidades_youtube("pagina", 100) == 0
    adicionar_fonte(app.state.bd, "youtube_pesquisa", "greve Luanda", "", "sup")
    c.post("/fontes/automatica", data={"csrf": csrf(h), "minutos": "15"})
    assert "quota diária do YouTube pode esgotar-se" in c.get("/fontes").text


def test_sem_segredo_nao_recolhe(app, monkeypatch):
    app.state.bd.definir("recolha_auto_minutos", "15", "t")
    monkeypatch.setattr(Config, "segredo_hash", "", raising=False)
    # a configuração do servidor já foi lida; simula-se uma instalação sem segredo
    a2 = criar_app(Config(segredo_hash=""), clf=ClassificadorDemonstracao(), sincrono=True)
    assert a2.state.agendador_tick() is False


def test_chave_do_youtube_nunca_aparece_nos_erros():
    class Falha:
        def obter(self, url, verificar_robots=True):
            raise recolha.ErroRecolha(f"Falha de ligação a {url}: 403")
    yt = recolha.ClienteYouTube("CHAVE-SECRETA-123", Falha())
    with pytest.raises(recolha.ErroRecolha) as e:
        yt.comentarios("abcdefghijk", "t", 10)
    assert "CHAVE-SECRETA-123" not in str(e.value) and "key=***" in str(e.value)
