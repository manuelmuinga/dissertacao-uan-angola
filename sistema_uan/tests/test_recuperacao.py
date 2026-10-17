"""Recuperação do acesso quando se esquece a palavra-passe: código pessoal, pedido ao supervisor,
palavra-passe temporária com mudança obrigatória e reposição na linha de comandos."""

from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sistema.base_dados import BaseDados  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.utilizadores import (ErroAutenticacao, autenticar, criar_utilizador, gerar_codigo_recuperacao,  # noqa: E402
                                  pedidos_pendentes, pedir_recuperacao, recuperar_com_codigo, repor_temporaria)
from sistema.web.app import criar_app  # noqa: E402

SENHA = "palavra-passe-longa"
NOVA = "outra-senha-segura"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "r.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", "s")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "x.env"))
    monkeypatch.delenv("UAN_DEMONSTRACAO", raising=False)
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    criar_utilizador(a.state.bd, "sup", "Sup", "supervisor", SENHA)
    criar_utilizador(a.state.bd, "ana", "Ana", "analista", SENHA)
    return a


def entrar(app, u="sup", senha=SENHA) -> TestClient:
    c = TestClient(app)
    c.post("/entrar", data={"utilizador": u, "senha": senha, "seguinte": "/"})
    return c


def csrf(html: str) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


# ------------------------------------------------------------------ funções
def test_codigo_serve_uma_vez(app):
    bd = app.state.bd
    codigo = gerar_codigo_recuperacao(bd, "ana")
    assert re.fullmatch(r"[A-Z2-9]{4}(-[A-Z2-9]{4}){3}", codigo)
    guardado = bd.consultar("SELECT codigo_recuperacao FROM utilizadores WHERE utilizador='ana'")[0][0]
    assert codigo.replace("-", "") not in guardado  # só o hash
    # minúsculas e sem hífenes também valem
    recuperar_com_codigo(bd, "ana", codigo.lower().replace("-", " "), NOVA, NOVA)
    assert autenticar(bd, "ana", NOVA)["utilizador"] == "ana"
    with pytest.raises(ErroAutenticacao):
        recuperar_com_codigo(bd, "ana", codigo, "terceira-senha-x", "terceira-senha-x")


def test_codigo_errado_conta_para_o_bloqueio(app):
    bd = app.state.bd
    gerar_codigo_recuperacao(bd, "ana")
    for _ in range(5):
        with pytest.raises(ErroAutenticacao):
            recuperar_com_codigo(bd, "ana", "AAAA-BBBB-CCCC-DDDD", NOVA, NOVA)
    with pytest.raises(ErroAutenticacao, match="bloqueada"):
        autenticar(bd, "ana", SENHA)


def test_mensagem_igual_para_conta_inexistente(app):
    bd = app.state.bd
    with pytest.raises(ErroAutenticacao) as e1:
        recuperar_com_codigo(bd, "ninguem", "AAAA", NOVA, NOVA)
    with pytest.raises(ErroAutenticacao) as e2:
        recuperar_com_codigo(bd, "ana", "AAAA", NOVA, NOVA)  # sem código gerado
    assert str(e1.value) == str(e2.value)
    with pytest.raises(ValueError):
        recuperar_com_codigo(bd, "ana", "AAAA", NOVA, "diferente-xx")


def test_pedido_e_temporaria(app):
    bd = app.state.bd
    pedir_recuperacao(bd, "ana")
    pedir_recuperacao(bd, "ana")      # repetido: um só pedido
    pedir_recuperacao(bd, "ninguem")  # inexistente: não cria pedido
    assert [p["utilizador"] for p in pedidos_pendentes(bd)] == ["ana"]
    temp = repor_temporaria(bd, "ana", "sup")
    assert len(temp) >= 10 and pedidos_pendentes(bd) == []
    autenticar(bd, "ana", temp)
    assert bd.consultar("SELECT senha_temporaria FROM utilizadores WHERE utilizador='ana'")[0][0] == 1
    with pytest.raises(ValueError):
        repor_temporaria(bd, "sup", "sup")


def test_migracao_de_base_antiga(tmp_path):
    caminho = tmp_path / "antiga.db"
    c = sqlite3.connect(caminho)
    c.execute("""CREATE TABLE utilizadores (utilizador TEXT PRIMARY KEY, nome TEXT NOT NULL, papel TEXT NOT NULL,
                 hash_senha TEXT NOT NULL, activo INTEGER NOT NULL DEFAULT 1, criado_em TEXT NOT NULL,
                 ultimo_acesso TEXT, falhas INTEGER NOT NULL DEFAULT 0, bloqueado_ate TEXT)""")
    c.commit(); c.close()
    bd = BaseDados(caminho)
    cols = {r[1] for r in bd.consultar("PRAGMA table_info(utilizadores)")}
    assert {"senha_temporaria", "codigo_recuperacao", "codigo_criado_em"} <= cols
    assert bd.consultar("SELECT COUNT(*) FROM pedidos_recuperacao")[0][0] == 0


# ------------------------------------------------------------------ páginas
def test_ligacao_na_entrada_e_pagina_recuperar(app):
    c = TestClient(app)
    assert 'href="/recuperar' in c.get("/entrar").text
    h = c.get("/recuperar?utilizador=ana").text
    assert "código de recuperação" in h and 'action="/recuperar/codigo"' in h and 'action="/recuperar/pedido"' in h


def test_fluxo_pedido_supervisor_temporaria(app):
    anon = TestClient(app)
    r = anon.post("/recuperar/pedido", data={"utilizador": "ana"})
    assert "Pedido registado" in r.text
    # a resposta é a mesma para uma conta que não existe
    assert "Pedido registado" in anon.post("/recuperar/pedido", data={"utilizador": "zzz"}).text

    sup = entrar(app)
    h = sup.get("/utilizadores").text
    assert "Pedidos de recuperação" in h and 'class="contador">1<' in h
    r = sup.post("/utilizadores/ana/repor", data={"csrf": csrf(h)})
    temp = re.search(r'id="temp-valor">([^<]+)<', r.text).group(1)
    assert "Pedidos de recuperação" not in r.text

    ana = TestClient(app)
    r = ana.post("/entrar", data={"utilizador": "ana", "senha": temp, "seguinte": "/fila"}, follow_redirects=False)
    assert r.headers["location"] == "/conta?aviso=temporaria"
    # enquanto não mudar, as outras páginas levam a «A minha conta»
    r = ana.get("/fila", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/conta")
    assert ana.get("/fila", headers={"X-Pedido": "fetch"}).status_code == 403
    h = ana.get("/conta").text
    assert "Palavra-passe temporária" in h
    r = ana.post("/conta/senha", data={"csrf": csrf(h), "actual": temp, "senha": NOVA, "senha2": NOVA},
                 follow_redirects=False)
    assert r.status_code == 303
    ana2 = entrar(app, "ana", NOVA)
    assert ana2.get("/fila", follow_redirects=False).status_code == 200


def test_fluxo_codigo_pela_web(app):
    ana = entrar(app, "ana")
    h = ana.get("/conta").text
    assert "Gerar código de recuperação" in h
    r = ana.post("/conta/codigo", data={"csrf": csrf(h), "actual": "errada-errada"})
    assert r.status_code == 400
    r = ana.post("/conta/codigo", data={"csrf": csrf(h), "actual": SENHA})
    codigo = re.search(r'id="codigo-valor">([^<]+)<', r.text).group(1)
    assert "não volta a ser mostrado" in r.text.lower()
    assert "Gerado em" in ana.get("/conta").text or "Código gerado em" in ana.get("/conta").text

    anon = TestClient(app)
    r = anon.post("/recuperar/codigo", data={"utilizador": "ana", "codigo": codigo, "senha": NOVA, "senha2": NOVA},
                  follow_redirects=False)
    assert r.headers["location"] == "/entrar?aviso=recuperada"
    r = anon.post("/recuperar/codigo", data={"utilizador": "ana", "codigo": codigo, "senha": NOVA, "senha2": NOVA})
    assert r.status_code == 400 and "incorrectos" in r.text
    assert entrar(app, "ana", NOVA).get("/fila", follow_redirects=False).status_code == 200


def test_supervisor_define_senha_e_obriga_a_mudar(app):
    sup = entrar(app)
    h = sup.get("/utilizadores").text
    sup.post("/utilizadores/ana/senha", data={"csrf": csrf(h), "senha": "escolhida-pelo-sup"})
    ana = TestClient(app)
    r = ana.post("/entrar", data={"utilizador": "ana", "senha": "escolhida-pelo-sup", "seguinte": "/"},
                 follow_redirects=False)
    assert r.headers["location"] == "/conta?aviso=temporaria"


def test_recusar_pedido(app):
    pedir_recuperacao(app.state.bd, "ana")
    sup = entrar(app)
    h = sup.get("/utilizadores").text
    pid = re.search(r"/utilizadores/pedidos/(\d+)/recusar", h).group(1)
    r = sup.post(f"/utilizadores/pedidos/{pid}/recusar", data={"csrf": csrf(h)})
    assert "Pedido de recuperação recusado" in r.text and pedidos_pendentes(app.state.bd) == []


def test_linha_de_comandos_repor_senha(tmp_path):
    bd_caminho = tmp_path / "cli.db"
    bd = BaseDados(bd_caminho)
    criar_utilizador(bd, "sup", "Sup", "supervisor", SENHA)
    env = {"UAN_BD": str(bd_caminho), "UAN_ENV": str(tmp_path / "x.env"), "UAN_SEGREDO_HASH": "s",
           "PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(RAIZ / "uan.py"), "repor-senha", "sup", "--temporaria"],
                       capture_output=True, text=True, env=env, cwd=RAIZ, timeout=60)
    assert r.returncode == 0, r.stderr
    temp = re.search(r"temporária de sup: (\S+)", r.stdout).group(1)
    assert autenticar(BaseDados(bd_caminho), "sup", temp)["utilizador"] == "sup"
    r = subprocess.run([sys.executable, str(RAIZ / "uan.py"), "repor-senha", "zzz", "--temporaria"],
                       capture_output=True, text=True, env=env, cwd=RAIZ, timeout=60)
    assert r.returncode != 0 and "não existe" in r.stderr


# ------------------------------------------------------------------ uan.env
def test_uan_env_txt_e_recarregar(tmp_path, monkeypatch):
    from sistema import config
    monkeypatch.delenv("UAN_SEGREDO_HASH", raising=False)
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "uan.env"))
    (tmp_path / "uan.env.txt").write_text("UAN_SEGREDO_HASH=um\n", encoding="utf-8")  # o Bloco de Notas acrescenta .txt
    config.DO_FICHEIRO.clear()
    config.carregar_env()
    assert config.Config().segredo_hash == "um"
    (tmp_path / "uan.env.txt").write_text("UAN_SEGREDO_HASH=dois\n", encoding="utf-8")
    config.recarregar_env()  # cada arranque do servidor volta a ler o ficheiro
    assert config.Config().segredo_hash == "dois"
    monkeypatch.delenv("UAN_SEGREDO_HASH", raising=False)
    config.DO_FICHEIRO.clear()


def test_verificar_config_nao_mostra_segredos(tmp_path):
    (tmp_path / "uan.env").write_text("UAN_SEGREDO_HASH=segredo-muito-secreto\nUAN_YOUTUBE_CHAVE=AIzaXYZ\n", encoding="utf-8")
    env = {"UAN_ENV": str(tmp_path / "uan.env"), "UAN_BD": str(tmp_path / "v.db"), "PATH": "/usr/bin:/bin",
           "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(RAIZ / "uan.py"), "verificar-config"], capture_output=True, text=True,
                       env=env, cwd=RAIZ, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "UAN_SEGREDO_HASH     definido" in r.stdout and "segredo-muito-secreto" not in r.stdout and "AIzaXYZ" not in r.stdout


# ------------------------------------------------------------------ fechar a janela termina a sessão
def test_fechar_janela_termina_sessao(app, monkeypatch):
    from sistema import utilizadores as ut
    c = entrar(app, "ana")
    h = c.get("/conta").text
    assert c.post("/sessao/fecho", data={"csrf": csrf(h)}).status_code == 204
    # recarregar logo a seguir: a sessão continua
    assert c.get("/fila", follow_redirects=False).status_code == 200
    c.post("/sessao/fecho", data={"csrf": csrf(h)})
    monkeypatch.setattr(ut, "SEGUNDOS_FECHO", -1)  # o prazo já passou
    assert ut.limpar_sessoes_fechadas(app.state.bd) == 1
    r = c.get("/fila", follow_redirects=False)
    assert r.status_code == 303 and "/entrar" in r.headers["location"]
    assert app.state.bd.consultar("SELECT COUNT(*) FROM auditoria WHERE accao='saida' AND detalhe LIKE '%janela_fechada%'")[0][0] == 1


def test_fecho_sem_csrf_e_ignorado_e_cookie_de_sessao(app):
    c = TestClient(app)
    r = c.post("/entrar", data={"utilizador": "ana", "senha": SENHA, "seguinte": "/"}, follow_redirects=False)
    assert "max-age" not in r.headers["set-cookie"].lower() and "expires" not in r.headers["set-cookie"].lower()
    c.post("/sessao/fecho", data={"csrf": "errado"})
    assert app.state.bd.consultar("SELECT COUNT(*) FROM sessoes WHERE fecho_em IS NOT NULL")[0][0] == 0


def test_js_avisa_ao_fechar():
    js = (RAIZ / "sistema" / "web" / "estatico" / "app.js").read_text(encoding="utf-8")
    assert "beforeunload" in js and 'sendBeacon("/sessao/fecho"' in js and "window.location.href =" in js
    assert js.count("window.location.href =") == 1  # só dentro de navegar(): a navegação interna não pergunta
