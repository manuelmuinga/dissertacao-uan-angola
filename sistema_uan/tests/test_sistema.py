"""Testes do sistema. Correr com: python -m pytest -q"""

from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sistema.anonimizacao import mascarar_texto, pseudonimo_autor  # noqa: E402
from sistema.base_dados import BaseDados  # noqa: E402
from sistema.classificador import ClassificadorDemonstracao, Resultado, carregar_classificador  # noqa: E402
from sistema.config import ROTULOS  # noqa: E402
from sistema.servico import _kappa, classificar_pendentes, exportar_revisoes, importar, metricas, prioridade  # noqa: E402

SEGREDO = "segredo-de-teste"
EXEMPLOS = [
    {"id": "c1", "autor": "Joao Silva", "texto": "Bom dia, o jogo de ontem foi bom", "data": "2026-09-01"},
    {"id": "c2", "autor": "@maria", "texto": "URGENTE partilha antes que apaguem, estão a esconder tudo", "data": "2026-09-01"},
    {"id": "c3", "autor": "anon", "texto": "Vamos todos amanhã às 8h, quem não aparecer é traidor, tragam tudo", "data": "2026-09-02"},
    {"id": "c4", "autor": "x", "texto": "Esses não merecem estar aqui, são todos iguais", "data": "2026-09-02"},
    {"id": "c4", "autor": "x", "texto": "Esses não merecem estar aqui, são todos iguais", "data": "2026-09-02"},  # duplicado
    {"id": "c5", "autor": "y", "texto": "ok"},  # demasiado curto? (3 caracteres mínimos -> 'ok' é ignorado)
]


@pytest.fixture()
def csv_exemplo(tmp_path: Path) -> Path:
    p = tmp_path / "lote.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "autor", "texto", "data"])
        w.writeheader()
        for e in EXEMPLOS:
            w.writerow({k: e.get(k, "") for k in w.fieldnames})
    return p


@pytest.fixture()
def bd(tmp_path: Path) -> BaseDados:
    return BaseDados(tmp_path / "t.db")


# ---------------- anonimização ----------------
def test_mascara_identificadores():
    t = mascarar_texto("Liga 923 456 789 ou +244 912345678, escreve a ana@mail.ao, vê https://x.co/a e fala com @kota_99")
    assert "923" not in t and "912345678" not in t and "ana@" not in t and "https" not in t and "kota_99" not in t
    assert t.count("[TELEFONE]") == 2 and "[EMAIL]" in t and "[URL]" in t and "@[UTILIZADOR]" in t


def test_pseudonimo_estavel_e_exige_segredo():
    assert pseudonimo_autor("Maria", SEGREDO) == pseudonimo_autor(" maria ", SEGREDO)
    assert pseudonimo_autor("Maria", SEGREDO) != pseudonimo_autor("Maria", "outro")
    assert pseudonimo_autor(None, SEGREDO) is None
    with pytest.raises(ValueError):
        pseudonimo_autor("Maria", "")


# ---------------- importação ----------------
def test_importar_anonimiza_e_deduplica(bd, csv_exemplo):
    info = importar(bd, csv_exemplo, "YouTube", "api_oficial", SEGREDO, "teste")
    assert info["lidos"] == 6 and info["validos"] == 5 and info["novos"] == 4
    linhas = bd.consultar("SELECT autor_pseudo, texto FROM publicacoes")
    assert all("Joao" not in (l["autor_pseudo"] or "") for l in linhas)
    assert all("@maria" not in l["texto"] for l in linhas)
    lote = bd.consultar("SELECT * FROM lotes")[0]
    assert lote["via"] == "api_oficial" and lote["n_novos"] == 4
    # reimportar o mesmo ficheiro não cria duplicados
    assert importar(bd, csv_exemplo, "YouTube", "api_oficial", SEGREDO)["novos"] == 0


def test_via_invalida(bd, csv_exemplo):
    with pytest.raises(ValueError):
        importar(bd, csv_exemplo, "YouTube", "login_falso", SEGREDO)


# ---------------- classificação e fila ----------------
def test_prioridade_usa_probabilidade_de_nao_normal():
    r = Resultado({"Normal": 0.5, "Desinformacao": 0.02, "Odio": 0.03, "Mobilizacao": 0.45})
    assert r.categoria == "Normal" and prioridade(r) == pytest.approx(0.5)


def test_fluxo_completo(bd, csv_exemplo, tmp_path):
    importar(bd, csv_exemplo, "YouTube", "api_oficial", SEGREDO)
    out = classificar_pendentes(bd, ClassificadorDemonstracao())
    assert out["classificados"] == 4
    assert classificar_pendentes(bd, ClassificadorDemonstracao())["classificados"] == 0
    fila = bd.fila(10)
    assert [r["categoria"] for r in fila] and all(r["categoria"] != "Normal" for r in fila)
    assert [r["prioridade"] for r in fila] == sorted([r["prioridade"] for r in fila], reverse=True)
    # revisão: o analista confirma a primeira e corrige a segunda para Normal
    bd.gravar_revisao(fila[0]["id_pub"], "analista1", fila[0]["categoria"], 1, None)
    bd.gravar_revisao(fila[1]["id_pub"], "analista1", "Normal", 2, "convocatória pacífica")
    assert len(bd.fila(10)) == len(fila) - 2
    m = metricas(bd, ks=(1, 2))
    assert m["n_revistas"] == 2 and m["precisao_at_k"] == {1: 1.0, 2: 0.5}
    assert m["concordancia"] == 0.5 and m["latencia_s"]["n"] == 4
    n = exportar_revisoes(bd, tmp_path / "rev.csv")
    linhas = list(csv.DictReader((tmp_path / "rev.csv").open(encoding="utf-8")))
    assert n == 2 and {l["origem"] for l in linhas} == {"revisao_sistema"}
    assert {l["categoria_final"] for l in linhas} <= set(ROTULOS)
    accoes = {r["accao"] for r in bd.consultar("SELECT accao FROM auditoria")}
    assert {"importacao", "classificacao", "revisao", "exportacao_revisoes"} <= accoes


def test_revisao_de_item_inexistente(bd):
    with pytest.raises(KeyError):
        bd.gravar_revisao("nao-existe", "a", "Normal", None, None)


def test_kappa():
    assert _kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert _kappa([], []) is None
    assert _kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]) == pytest.approx(0.0)


def test_limpeza_mantem_revistas(bd, csv_exemplo):
    importar(bd, csv_exemplo, "YouTube", "manual", SEGREDO)
    classificar_pendentes(bd, ClassificadorDemonstracao())
    alvo = bd.fila(1)[0]["id_pub"]
    bd.gravar_revisao(alvo, "a", "Odio", 1, None)
    bd.consultar("SELECT 1")
    with bd.ligacao() as c:
        c.execute("UPDATE publicacoes SET recolhido_em = '2000-01-01T00:00:00+00:00'")
    assert bd.apagar_antigos(30) == 3
    assert [r["id_pub"] for r in bd.consultar("SELECT id_pub FROM publicacoes")] == [alvo]


# ---------------- modelo real (BERT minúsculo, sem descarregar nada) ----------------
def _bert_minusculo(pasta: Path, id2label: dict | None) -> Path:
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + "o a de que vamos todos amanhã fora daqui bom dia".split()
    (pasta / "vocab.txt").write_text("\n".join(vocab), encoding="utf-8")
    tok = transformers.BertTokenizerFast(vocab_file=str(pasta / "vocab.txt"), do_lower_case=True)
    cfg = transformers.BertConfig(vocab_size=len(vocab), hidden_size=16, num_hidden_layers=1, num_attention_heads=2,
                                  intermediate_size=32, num_labels=4, id2label=id2label,
                                  label2id={v: k for k, v in id2label.items()} if id2label else None)
    torch.manual_seed(0)
    transformers.BertForSequenceClassification(cfg).save_pretrained(pasta)
    tok.save_pretrained(pasta)
    return pasta


@pytest.mark.parametrize("id2label", [dict(enumerate(["Normal", "Desinformacao", "Odio", "Mobilizacao"])), None])
def test_carrega_bertimbau_guardado(tmp_path, id2label):
    pasta = _bert_minusculo(tmp_path, id2label)
    clf = carregar_classificador(pasta, max_length=32, tamanho_lote=2, dispositivo="cpu")
    assert clf.nome == "BERTimbau" and clf.rotulos == list(ROTULOS)
    res = clf.classificar(["bom dia", "vamos todos amanhã", "fora daqui"])
    assert len(res) == 3
    for r in res:
        assert set(r.probabilidades) == set(ROTULOS)
        assert sum(r.probabilidades.values()) == pytest.approx(1.0, abs=1e-5)


def test_pasta_sem_modelo(tmp_path):
    pytest.importorskip("transformers")
    with pytest.raises(FileNotFoundError):
        carregar_classificador(tmp_path)


# ---------------- API ----------------
def test_api(tmp_path, monkeypatch, csv_exemplo):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("UAN_BD", str(tmp_path / "api.db"))
    monkeypatch.setenv("UAN_SEGREDO_HASH", SEGREDO)
    monkeypatch.delenv("UAN_MODELO", raising=False)
    sys.modules.pop("api", None)
    api = importlib.import_module("api")
    cli = TestClient(api.app)
    assert cli.get("/saude").json()["modelo"] == "DEMONSTRACAO"
    r = cli.post("/classificar", json={"textos": ["vamos todos amanhã às 8h, tragam tudo"]}).json()
    assert r[0]["categoria"] == "Mobilizacao"
    with csv_exemplo.open("rb") as f:
        info = cli.post("/importar", params={"plataforma": "YouTube", "via": "api_oficial"},
                        files={"ficheiro": ("lote.csv", f, "text/csv")}).json()
    assert info["novos"] == 4 and info["classificados"] == 4
    fila = cli.get("/fila").json()
    assert fila and isinstance(fila[0]["probabilidades"], dict)
    assert cli.post("/revisoes", json={"id_pub": fila[0]["id_pub"], "analista": "an", "categoria": "Xpto"}).status_code == 422
    assert cli.post("/revisoes", json={"id_pub": fila[0]["id_pub"], "analista": "an", "categoria": "Odio"}).status_code == 200
    assert cli.post("/importar", params={"plataforma": "YouTube", "via": "captcha"},
                    files={"ficheiro": ("l.csv", b"texto\nola mundo", "text/csv")}).status_code == 422
    assert cli.get("/metricas").json()["n_revistas"] == 1
