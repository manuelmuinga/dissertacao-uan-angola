"""Testes da localização por província, dos alertas, do mapa e do relatório de alertas."""

from __future__ import annotations

import csv
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
from sistema.base_dados import BaseDados  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao  # noqa: E402
from sistema.config import Config  # noqa: E402
from sistema.geografia import PROVINCIAS, detectar_provincias, mapa  # noqa: E402
from sistema.servico import classificar_pendentes, importar  # noqa: E402
from sistema.utilizadores import criar_utilizador  # noqa: E402
from sistema.web.app import criar_app  # noqa: E402

SEGREDO = "segredo-de-teste"
SENHA = "palavra-passe-longa"


class SMTPFalso:
    """Substitui o servidor de e-mail: guarda as mensagens em vez de as enviar."""
    enviadas: list = []
    falhar = False

    def __init__(self, servidor, porta, timeout=30):
        self.servidor, self.porta = servidor, porta

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, u, s):
        pass

    def send_message(self, msg):
        if SMTPFalso.falhar:
            raise OSError("servidor indisponível")
        SMTPFalso.enviadas.append(msg)


@pytest.fixture(autouse=True)
def limpar_smtp():
    SMTPFalso.enviadas, SMTPFalso.falhar = [], False


def escrever_csv(caminho: Path, linhas: list[tuple[str, str]]) -> Path:
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "authorDisplayName", "textDisplay", "publishedAt"])
        for i, (texto, dia) in enumerate(linhas):
            w.writerow([f"c{i}", f"@pessoa{i}", texto, f"{dia}T10:00:00Z"])
    return caminho


def ids_por_texto(bd: BaseDados) -> dict[str, str]:
    return {r["texto"]: r["id_pub"] for r in bd.consultar("SELECT id_pub, texto FROM publicacoes")}


# ------------------------------------------------------------------ geografia
def test_detecta_provincias_e_evita_ambiguidades():
    assert detectar_provincias("Manifestação amanhã no Kilamba, Luanda") == ["LUA"]
    assert detectar_provincias("Icolo e Bengo") == ["LUA"]          # não conta como Bengo
    assert detectar_provincias("Cuito Cuanavale") == ["CCU"]        # não conta como Cuito (Bié)
    assert detectar_provincias("o kwanza desvalorizou outra vez") == []
    assert detectar_provincias("Kwanza-Sul e Lunda Norte") == ["CUS", "LNO"]
    assert detectar_provincias("as ruas estão belas") == []
    assert detectar_provincias("N'dalatando", "vídeo sobre Moçâmedes") == ["CNO", "NAM"]
    assert detectar_provincias(None, "") == []


def test_mapa_tem_as_18_provincias():
    m = mapa()
    assert set(m["provincias"]) == set(PROVINCIAS) and len(PROVINCIAS) == 18
    assert all(p["d"].startswith("M") for p in m["provincias"].values())
    assert "anterior a 2025" in m["fonte"]


def test_indexa_na_importacao_e_reindexa_bases_antigas(tmp_path):
    bd = BaseDados(tmp_path / "g.db")
    f = escrever_csv(tmp_path / "l.csv", [("Greve no Lobito amanhã", "2026-10-01"), ("Sem lugar nenhum", "2026-10-01"),
                                          ("Luanda e Huambo hoje", "2026-10-02")])
    importar(bd, f, "YouTube", "api_oficial", SEGREDO)
    provs = sorted(r["provincia"] for r in bd.consultar("SELECT provincia FROM pub_provincias"))
    assert provs == ["BGU", "HUA", "LUA"]
    # base criada antes da localização: ao abrir, indexa as publicações existentes
    with bd.ligacao() as c:
        c.execute("DELETE FROM pub_provincias")
        c.execute("DELETE FROM definicoes WHERE chave = 'geo_versao'")
    bd2 = BaseDados(tmp_path / "g.db")
    assert bd2.consultar("SELECT COUNT(*) AS n FROM pub_provincias")[0]["n"] == 3


# ------------------------------------------------------------------ período
def test_periodo():
    p = al.periodo("2026-10-01", "2026-10-07")
    assert p.dias == 7 and p.anterior == al.Periodo(date(2026, 9, 24), date(2026, 9, 30))
    assert al.periodo("2026-10-07", "2026-10-01").inicio == date(2026, 10, 1)   # datas trocadas
    assert al.periodo(dias="7").dias == 7
    assert al.periodo("lixo", "lixo").dias == 30


# ------------------------------------------------------------------ alertas
def _bd_classificada(tmp_path, linhas) -> BaseDados:
    bd = BaseDados(tmp_path / "a.db")
    importar(bd, escrever_csv(tmp_path / "a.csv", linhas), "YouTube", "api_oficial", SEGREDO)
    classificar_pendentes(bd, ClassificadorDemonstracao())
    return bd


def test_alerta_confirmado_respeita_minimo_e_nao_repete(tmp_path):
    bd = _bd_classificada(tmp_path, [("Vamos todos à praça de Benguela amanhã às 10h", "2026-10-05")])
    idp = next(iter(ids_por_texto(bd).values()))
    bd.definir("alerta_min_confirmacoes", "2", "teste")
    bd.gravar_revisao(idp, "ana", "Mobilizacao", 1, None)
    assert al.alerta_confirmado(bd, idp) is None            # falta o segundo analista
    bd.gravar_revisao(idp, "beto", "Mobilizacao", 1, None)
    ida = al.alerta_confirmado(bd, idp)
    a = bd.consultar("SELECT * FROM alertas WHERE id_alerta = ?", (ida,))[0]
    assert a["tipo"] == "confirmado" and a["categoria"] == "Mobilizacao" and a["provincia"] == "BGU"
    assert al.alerta_confirmado(bd, idp) is None            # não repete


def test_revisao_normal_nao_gera_alerta(tmp_path):
    bd = _bd_classificada(tmp_path, [("Bom dia Luanda", "2026-10-05")])
    idp = next(iter(ids_por_texto(bd).values()))
    bd.gravar_revisao(idp, "ana", "Normal", 1, None)
    assert al.alerta_confirmado(bd, idp) is None
    # empate entre ameaça e Normal: não confirma
    bd.gravar_revisao(idp, "beto", "Odio", 1, None)
    assert al.alerta_confirmado(bd, idp) is None


def test_alerta_de_tendencia_normaliza_pelo_volume(tmp_path):
    hoje = date(2026, 10, 14)
    linhas = [(f"Benguela ataque {i}", (hoje - timedelta(days=i % 7)).isoformat()) for i in range(6)]   # esta semana
    linhas += [("Benguela antes 0", (hoje - timedelta(days=9)).isoformat())]                           # semana anterior
    linhas += [(f"Huambo {i}", (hoje - timedelta(days=i % 7)).isoformat()) for i in range(6)]           # só conversa
    linhas += [(f"Huambo antes {i}", (hoje - timedelta(days=7 + i % 7)).isoformat()) for i in range(6)]
    bd = _bd_classificada(tmp_path, linhas)
    for texto, idp in ids_por_texto(bd).items():
        bd.gravar_revisao(idp, "ana", "Odio" if texto.startswith("Benguela") else "Normal", 1, None)
    novos = al.verificar_tendencias(bd, hoje)
    alertas = bd.consultar("SELECT * FROM alertas WHERE tipo = 'tendencia'")
    assert {a["provincia"] for a in alertas} == {"BGU", "NAC"}
    bgu = next(a for a in alertas if a["provincia"] == "BGU")
    det = json.loads(bgu["detalhe"])
    assert det["confirmadas"] == 6 and det["confirmadas_antes"] == 1 and det["por_categoria"] == {"Odio": 6}
    assert len(novos) == 2 and al.verificar_tendencias(bd, hoje) == []   # não repete no mesmo dia


def test_mais_recolha_nao_gera_tendencia(tmp_path):
    # As ameaças em Benguela triplicam, mas a recolha também triplicou: o peso no total não sobe.
    hoje = date(2026, 10, 14)
    linhas = [(f"Benguela a {i}", hoje.isoformat()) for i in range(6)] + [(f"Outro a {i}", hoje.isoformat()) for i in range(24)]
    linhas += [(f"Benguela b {i}", (hoje - timedelta(days=8)).isoformat()) for i in range(2)]
    linhas += [(f"Outro b {i}", (hoje - timedelta(days=8)).isoformat()) for i in range(8)]
    bd = _bd_classificada(tmp_path, linhas)
    for texto, idp in ids_por_texto(bd).items():
        bd.gravar_revisao(idp, "ana", "Odio" if texto.startswith("Benguela") else "Normal", 1, None)
    assert al.verificar_tendencias(bd, hoje) == []


def test_sem_tendencia_abaixo_do_minimo(tmp_path):
    hoje = date(2026, 10, 14)
    bd = _bd_classificada(tmp_path, [(f"Cabinda {i}", hoje.isoformat()) for i in range(4)])
    for idp in ids_por_texto(bd).values():
        bd.gravar_revisao(idp, "ana", "Desinformacao", 1, None)
    assert al.verificar_tendencias(bd, hoje) == []


def test_email_sem_texto_nem_autor_e_falha_registada(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_SMTP_SERVIDOR", "smtp.teste")
    monkeypatch.setenv("UAN_SMTP_REMETENTE", "alertas@uan.ao")
    cfg = Config()
    bd = _bd_classificada(tmp_path, [("Vamos todos à praça do Lubango amanhã às 10h, liguem 923456789", "2026-10-05")])
    bd.definir("alerta_destinatarios", "chefe@uan.ao", "teste")
    idp = next(iter(ids_por_texto(bd).values()))
    bd.gravar_revisao(idp, "ana", "Mobilizacao", 1, None)
    al.apos_revisao(bd, cfg, idp, sincrono=True, fabrica_smtp=SMTPFalso)
    assert len(SMTPFalso.enviadas) == 1
    corpo = SMTPFalso.enviadas[0].get_content()
    assert "Huíla" in corpo and "Mobilização" in corpo and f"/publicacao/{idp}" in corpo
    assert "praça" not in corpo and "TELEFONE" not in corpo and "pessoa" not in corpo
    assert bd.consultar("SELECT email_estado FROM alertas")[0]["email_estado"] == "enviado"
    # uma falha do servidor fica registada e não apaga o alerta
    SMTPFalso.falhar = True
    (tmp_path / "segunda").mkdir()
    bd2 = _bd_classificada(tmp_path / "segunda", [("Ataque em Cabinda", "2026-10-05")])
    idp2 = next(iter(ids_por_texto(bd2).values()))
    bd2.definir("alerta_destinatarios", "chefe@uan.ao", "teste")
    bd2.gravar_revisao(idp2, "ana", "Odio", 1, None)
    al.apos_revisao(bd2, cfg, idp2, sincrono=True, fabrica_smtp=SMTPFalso)
    assert bd2.consultar("SELECT email_estado FROM alertas")[0]["email_estado"].startswith("falhou")


def test_sem_email_configurado(tmp_path):
    bd = _bd_classificada(tmp_path, [("Ódio em Malanje", "2026-10-05")])
    idp = next(iter(ids_por_texto(bd).values()))
    bd.gravar_revisao(idp, "ana", "Odio", 1, None)
    al.apos_revisao(bd, Config(), idp, sincrono=True, fabrica_smtp=SMTPFalso)
    assert SMTPFalso.enviadas == []
    assert bd.consultar("SELECT email_estado FROM alertas")[0]["email_estado"] == "nao_configurado"


def test_destinatarios_validados():
    assert al.validar_destinatarios("a@uan.ao; b@uan.ao") == ["a@uan.ao", "b@uan.ao"]
    with pytest.raises(ValueError):
        al.validar_destinatarios("a@uan.ao, nao-e-email")


# ------------------------------------------------------------------ mapa e relatório
def test_mapa_taxa_e_minimo(tmp_path):
    hoje = date(2026, 10, 14)
    linhas = [(f"Luanda {i}", hoje.isoformat()) for i in range(10)] + [("Namibe 1", hoje.isoformat())]
    bd = _bd_classificada(tmp_path, linhas)
    tx = ids_por_texto(bd)
    for t in ("Luanda 0", "Luanda 1", "Namibe 1"):
        bd.gravar_revisao(tx[t], "ana", "Desinformacao", 1, None)
    m = al.dados_mapa(bd, al.Periodo(hoje - timedelta(days=6), hoje))
    lua = next(l for l in m["provincias"] if l["codigo"] == "LUA")
    nam = next(l for l in m["provincias"] if l["codigo"] == "NAM")
    assert lua["mencoes"] == 10 and lua["valor"] == 2 and lua["taxa"] == pytest.approx(0.2)
    assert nam["valor"] == 1 and nam["taxa"] is None and not nam["suficiente"]   # menos de 5 publicações
    assert m["nacional"]["valor"] == 3 and m["sem_local"]["mencoes"] == 0


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("UAN_BD", str(tmp_path / "web.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", SEGREDO)
    monkeypatch.setenv("UAN_SMTP_SERVIDOR", "smtp.teste")
    monkeypatch.setenv("UAN_SMTP_REMETENTE", "alertas@uan.ao")
    monkeypatch.setenv("UAN_ENV", str(tmp_path / "nao-existe.env"))
    a = criar_app(Config(), clf=ClassificadorDemonstracao(), sincrono=True)
    a.state.smtp_testes = SMTPFalso
    bd = a.state.bd
    criar_utilizador(bd, "sup", "Supervisor", "supervisor", SENHA)
    criar_utilizador(bd, "ana", "Analista A", "analista", SENHA)
    return a


def entrar(app, utilizador) -> TestClient:
    c = TestClient(app)
    r = c.post("/entrar", data={"utilizador": utilizador, "senha": SENHA, "seguinte": "/"}, follow_redirects=False)
    assert r.status_code == 303
    return c


def csrf(resp) -> str:
    return re.search(r'name="csrf" value="([^"]+)"', resp.text).group(1)


def test_fluxo_web_alerta_mapa_relatorio(app, tmp_path):
    bd = app.state.bd
    hoje = al.hoje_luanda().isoformat()
    importar(bd, escrever_csv(tmp_path / "w.csv", [("Vamos todos à praça do Huambo amanhã, tragam tudo", hoje),
                                                   ("Bom dia Huambo", hoje)]), "YouTube", "api_oficial", SEGREDO)
    classificar_pendentes(bd, ClassificadorDemonstracao())
    sup = entrar(app, "sup")
    r = sup.get("/definicoes")
    assert sup.post("/definicoes/alertas", data={"csrf": csrf(r), "min_confirmacoes": 1, "janela_dias": 7, "min_casos": 1,
                                                  "factor": "1,5", "destinatarios": "chefe@uan.ao"},
                    follow_redirects=False).status_code == 303
    assert sup.post("/definicoes/alertas", data={"csrf": csrf(r), "destinatarios": "isto-nao"}).status_code == 400

    ana = entrar(app, "ana")
    idp = ids_por_texto(bd)["Vamos todos à praça do Huambo amanhã, tragam tudo"]
    f = ana.get("/fila")
    assert ana.post("/rever", data={"csrf": csrf(f), "id_pub": idp, "categoria": "Mobilizacao", "origem": "fila",
                                    "voltar": "/fila"}, follow_redirects=False).status_code == 303
    assert bd.consultar("SELECT COUNT(*) AS n FROM alertas WHERE tipo = 'confirmado'")[0]["n"] == 1
    assert len(SMTPFalso.enviadas) >= 1 and "tragam" not in SMTPFalso.enviadas[0].get_content()

    pag = ana.get("/alertas")
    assert pag.status_code == 200 and "Ameaça confirmada" in pag.text and "Huambo" in pag.text
    assert re.search(r'href="/alertas"[^>]*>\s*(<svg.*?</svg>)?<span>Alertas</span><span class="contador">', pag.text, re.S)
    ana.post("/alertas/vistos", data={"csrf": csrf(pag)})
    assert 'class="contador"' not in re.search(r'href="/alertas".*?</a>', ana.get("/alertas").text, re.S).group(0)

    m = ana.get("/mapa?dias=7")
    assert m.status_code == 200 and "<svg" in m.text and 'id="prov-HUA"' in m.text and "anterior a 2025" in m.text
    assert ana.get("/mapa?dias=7&modo=sinalizadas").status_code == 200

    rel = ana.get(f"/relatorio?de={hoje}&ate={hoje}")
    assert rel.status_code == 200 and "Relatório de alertas de ameaças" in rel.text and "tragam" in rel.text
    assert 'action="/relatorio/enviar"' not in rel.text   # só o supervisor envia
    c = ana.get(f"/relatorio.csv?de={hoje}&ate={hoje}")
    assert c.status_code == 200 and "Huambo" in c.text and "provincia" in c.text
    assert ana.post("/relatorio/enviar", data={"csrf": csrf(rel), "de": hoje, "ate": hoje}).status_code == 403

    rs = sup.get(f"/relatorio?de={hoje}&ate={hoje}")
    antes = len(SMTPFalso.enviadas)
    assert sup.post("/relatorio/enviar", data={"csrf": csrf(rs), "de": hoje, "ate": hoje},
                    follow_redirects=False).status_code == 303
    corpo = SMTPFalso.enviadas[antes].get_content()
    assert "Ameaças confirmadas: 1" in corpo and "tragam" not in corpo
    assert bd.consultar("SELECT COUNT(*) AS n FROM auditoria WHERE accao = 'relatorio_email'")[0]["n"] == 1


def test_falha_de_email_nao_impede_a_revisao(app, tmp_path):
    bd = app.state.bd
    bd.definir("alerta_destinatarios", "chefe@uan.ao", "teste")
    importar(bd, escrever_csv(tmp_path / "f.csv", [("Ataque em Cabinda", al.hoje_luanda().isoformat())]),
             "YouTube", "api_oficial", SEGREDO)
    classificar_pendentes(bd, ClassificadorDemonstracao())
    SMTPFalso.falhar = True
    ana = entrar(app, "ana")
    idp = next(iter(ids_por_texto(bd).values()))
    f = ana.get("/publicacao/" + idp)
    r = ana.post("/rever", data={"csrf": csrf(f), "id_pub": idp, "categoria": "Odio", "origem": "fila", "voltar": "/fila"},
                 follow_redirects=False)
    assert r.status_code == 303
    assert bd.consultar("SELECT COUNT(*) AS n FROM revisoes")[0]["n"] == 1
    assert bd.consultar("SELECT email_estado FROM alertas")[0]["email_estado"].startswith("falhou")
