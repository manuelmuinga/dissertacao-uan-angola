"""Operações do sistema: importar, classificar, ordenar a fila e calcular métricas."""

from __future__ import annotations

import csv
import json
import logging
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from .anonimizacao import id_publicacao, mascarar_texto, pseudonimo_autor
from .base_dados import BaseDados, agora
from .classificador import Classificador, Resultado
from .config import ROTULOS

log = logging.getLogger(__name__)

VIAS = ("api_oficial", "manual", "scraping_publico", "doacao", "dataset_terceiros")

# Nomes de colunas aceites nos ficheiros de entrada (os scripts de recolha usam variantes).
_COL_TEXTO = ("texto", "text", "comentario", "textDisplay", "textOriginal", "mensagem")
_COL_AUTOR = ("autor", "author", "authorDisplayName", "utilizador", "username")
_COL_ID = ("id", "id_comentario", "comment_id", "id_externo")
_COL_DATA = ("data", "data_publicacao", "publishedAt", "date")
_COL_CONTEXTO = ("contexto", "video_titulo", "titulo_video", "canal", "channel")


def _campo(reg: dict, nomes: tuple[str, ...]) -> str | None:
    for n in nomes:
        v = reg.get(n)
        if v not in (None, ""):
            return str(v)
    return None


def ler_ficheiro(caminho: Path) -> list[dict]:
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".jsonl":
        with caminho.open(encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]
    if caminho.suffix.lower() == ".json":
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        return dados if isinstance(dados, list) else dados.get("registos", [])
    with caminho.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def preparar_registos(brutos: list[dict], plataforma: str, segredo: str) -> list[dict]:
    """Anonimiza e normaliza os registos. Os dados brutos nunca são gravados."""
    out = []
    recolhido = agora()
    for r in brutos:
        texto = _campo(r, _COL_TEXTO)
        if not texto or len(texto.strip()) < 3:
            continue
        texto_m = mascarar_texto(texto)
        out.append({
            "id_pub": id_publicacao(plataforma, _campo(r, _COL_ID), texto_m),
            "plataforma": plataforma,
            "autor_pseudo": pseudonimo_autor(_campo(r, _COL_AUTOR), segredo),
            "texto": texto_m,
            "data_publicacao": _campo(r, _COL_DATA),
            "recolhido_em": recolhido,
            "contexto": _campo(r, _COL_CONTEXTO),
        })
    return out


def importar(bd: BaseDados, caminho: Path, plataforma: str, via: str, segredo: str,
             descricao: str | None = None, quem: str = "sistema") -> dict:
    if via not in VIAS:
        raise ValueError(f"via deve ser uma de {VIAS}")
    brutos = ler_ficheiro(caminho)
    registos = preparar_registos(brutos, plataforma, segredo)
    id_lote = bd.criar_lote(plataforma, via, descricao, Path(caminho).name)
    novos = bd.inserir_publicacoes(id_lote, registos)
    info = {"id_lote": id_lote, "lidos": len(brutos), "validos": len(registos), "novos": novos}
    bd.auditar(quem, "importacao", {**info, "plataforma": plataforma, "via": via})
    log.info("Lote %s: %s", id_lote, info)
    return info


def prioridade(res: Resultado) -> float:
    """Prioridade na fila = probabilidade de NÃO ser Normal.

    Ordena pela suspeita global e não pela categoria prevista, para que um item
    com 45% Mobilizacao e 50% Normal (previsto Normal) também suba na fila.
    """
    return 1.0 - res.probabilidades.get("Normal", 0.0)


def classificar_pendentes(bd: BaseDados, clf: Classificador, limite: int = 1000) -> dict:
    pend = bd.pendentes(limite)
    if not pend:
        return {"classificados": 0}
    t0 = time.perf_counter()
    resultados = clf.classificar([p["texto"] for p in pend])
    dur_ms = (time.perf_counter() - t0) * 1000 / len(pend)
    quando = agora()
    bd.gravar_classificacoes([
        {
            "id_pub": p["id_pub"], "modelo": clf.nome, "versao": clf.versao,
            "probabilidades": json.dumps(r.probabilidades), "categoria": r.categoria,
            "confianca": r.confianca, "prioridade": prioridade(r),
            "classificado_em": quando, "duracao_ms": dur_ms,
        }
        for p, r in zip(pend, resultados)
    ])
    bd.auditar("sistema", "classificacao", {"n": len(pend), "modelo": clf.nome, "versao": clf.versao})
    return {"classificados": len(pend), "ms_por_item": round(dur_ms, 2),
            "categorias": dict(Counter(r.categoria for r in resultados))}


# ---------------------------- métricas ----------------------------
def _kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    return None if pe == 1 else (po - pe) / (1 - pe)


def metricas(bd: BaseDados, ks: tuple[int, ...] = (10, 25, 50, 100)) -> dict:
    """Métricas operacionais a partir das revisões humanas.

    - precisão@K: entre os K itens de maior prioridade já revistos, fracção que o
      analista confirmou como ameaça (qualquer categoria diferente de Normal);
    - concordância e Kappa analista–sistema;
    - latência recolha→classificação (mediana e P95), para a H2.
    """
    rev = bd.consultar(
        """SELECT k.categoria AS sistema, r.categoria AS analista, k.prioridade
           FROM revisoes r JOIN classificacoes k ON k.id_pub = r.id_pub ORDER BY k.prioridade DESC"""
    )
    out: dict = {"n_revistas": len(rev)}
    if rev:
        ameaca = [x["analista"] != "Normal" for x in rev]
        out["precisao_at_k"] = {k: round(sum(ameaca[:k]) / min(k, len(ameaca)), 3) for k in ks if len(ameaca) >= k}
        s, a = [x["sistema"] for x in rev], [x["analista"] for x in rev]
        out["concordancia"] = round(sum(x == y for x, y in zip(s, a)) / len(rev), 3)
        k = _kappa(s, a)
        out["kappa_analista_sistema"] = None if k is None else round(k, 3)
        out["por_categoria"] = {
            c: {"previstas": s.count(c), "confirmadas": sum(1 for x, y in zip(s, a) if x == c and y == c)}
            for c in ROTULOS
        }
    lat = bd.consultar(
        """SELECT p.recolhido_em, k.classificado_em FROM classificacoes k JOIN publicacoes p ON p.id_pub = k.id_pub"""
    )
    seg = [
        (datetime.fromisoformat(x["classificado_em"]) - datetime.fromisoformat(x["recolhido_em"])).total_seconds()
        for x in lat
    ]
    if seg:
        seg.sort()
        out["latencia_s"] = {
            "n": len(seg), "mediana": round(statistics.median(seg), 3),
            "p95": round(seg[min(len(seg) - 1, int(0.95 * len(seg)))], 3), "max": round(seg[-1], 3),
        }
    inf = bd.consultar("SELECT AVG(duracao_ms) AS m FROM classificacoes")
    if inf and inf[0]["m"] is not None:
        out["inferencia_ms_por_item"] = round(inf[0]["m"], 2)
    return out


def exportar_revisoes(bd: BaseDados, destino: Path) -> int:
    """Exporta as revisões no formato do corpus de treino (id_hash, texto, categoria_final, origem)."""
    linhas = bd.consultar(
        """SELECT p.id_pub AS id_hash, p.texto, r.categoria AS categoria_final, p.plataforma, r.analista
           FROM revisoes r JOIN publicacoes p ON p.id_pub = r.id_pub"""
    )
    destino = Path(destino)
    with destino.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_hash", "texto", "categoria_final", "origem", "plataforma", "analista"])
        for l in linhas:
            # origem própria: rótulos de UM analista, ordenados pela fila do modelo — não equivalem
            # à anotação aleatória por 3 anotadores e não devem entrar no conjunto de teste.
            w.writerow([l["id_hash"], l["texto"], l["categoria_final"], "revisao_sistema", l["plataforma"], l["analista"]])
    bd.auditar("sistema", "exportacao_revisoes", {"n": len(linhas), "ficheiro": destino.name})
    return len(linhas)
