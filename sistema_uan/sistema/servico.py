"""Operações do sistema: importar, classificar, ordenar a fila e calcular métricas."""

from __future__ import annotations

import csv
import itertools
import json
import logging
import math
import random
import statistics
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable

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
             descricao: str | None = None, quem: str = "sistema", nome_ficheiro: str | None = None) -> dict:
    if via not in VIAS:
        raise ValueError(f"via deve ser uma de {VIAS}")
    brutos = ler_ficheiro(caminho)
    registos = preparar_registos(brutos, plataforma, segredo)
    id_lote = bd.criar_lote(plataforma, via, descricao, nome_ficheiro or Path(caminho).name, quem)
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


_TRAVA_CLASSIFICACAO = threading.Lock()


def classificar_pendentes(bd: BaseDados, clf: Classificador, limite: int = 1000, sublote: int | None = None,
                          progresso: Callable[[int, int], None] | None = None) -> dict:
    """Classifica as publicações pendentes e grava os resultados por sublote.

    Gravar a cada `sublote` itens (por omissão, o tamanho de lote do classificador)
    faz com que as primeiras publicações cheguem à fila sem esperar pelo lote
    inteiro. Assim, o tempo até à fila deixa de crescer com a dimensão do lote (H2).
    """
    if not _TRAVA_CLASSIFICACAO.acquire(blocking=False):
        return {"classificados": 0, "ocupado": True}
    try:
        pend = bd.pendentes(limite)
        if not pend:
            return {"classificados": 0}
        passo = max(1, sublote or getattr(clf, "tamanho_lote", 32) or 32)
        contagem: Counter = Counter()
        t_total = time.perf_counter()
        primeiro_s = None
        for i in range(0, len(pend), passo):
            parte = pend[i : i + passo]
            t0 = time.perf_counter()
            resultados = clf.classificar([p["texto"] for p in parte])
            dur_ms = (time.perf_counter() - t0) * 1000 / len(parte)
            quando = agora()
            bd.gravar_classificacoes([
                {
                    "id_pub": p["id_pub"], "modelo": clf.nome, "versao": clf.versao,
                    "probabilidades": json.dumps(r.probabilidades), "categoria": r.categoria,
                    "confianca": r.confianca, "prioridade": prioridade(r),
                    "classificado_em": quando, "duracao_ms": dur_ms,
                }
                for p, r in zip(parte, resultados)
            ])
            if primeiro_s is None:
                primeiro_s = time.perf_counter() - t_total
            contagem.update(r.categoria for r in resultados)
            if progresso:
                progresso(min(i + passo, len(pend)), len(pend))
        total_s = time.perf_counter() - t_total
        bd.auditar("sistema", "classificacao", {"n": len(pend), "modelo": clf.nome, "versao": clf.versao,
                                                "sublote": passo})
        return {"classificados": len(pend), "ms_por_item": round(total_s * 1000 / len(pend), 2),
                "segundos_ate_primeiro_sublote": round(primeiro_s, 3), "sublote": passo,
                "categorias": dict(contagem)}
    finally:
        _TRAVA_CLASSIFICACAO.release()


def classificacao_em_curso() -> bool:
    return _TRAVA_CLASSIFICACAO.locked()


# ---------------------------- amostra de controlo ----------------------------
def gerar_amostra_controlo(bd: BaseDados, n: int, quem: str, semente: int | None = None,
                           id_lote: int | None = None) -> dict:
    """Sorteia `n` itens classificados como Normal para estimar a sensibilidade.

    A fila só mostra o que o modelo sinalizou. Sem rever uma amostra aleatória do
    que ficou de fora, não é possível estimar quantas ameaças o sistema deixa passar.
    """
    filtro, params = "", []
    if id_lote:
        filtro, params = "AND p.id_lote = ?", [id_lote]
    cand = [r["id_pub"] for r in bd.consultar(
        f"""SELECT k.id_pub FROM classificacoes k JOIN publicacoes p ON p.id_pub = k.id_pub
            WHERE k.categoria = 'Normal' AND k.id_pub NOT IN (SELECT id_pub FROM amostra_controlo) {filtro}
            ORDER BY k.id_pub""", tuple(params))]
    semente = semente if semente is not None else random.SystemRandom().randrange(1, 10**6)
    escolha = random.Random(semente).sample(cand, min(n, len(cand)))
    id_amostra = (bd.consultar("SELECT COALESCE(MAX(id_amostra), 0) AS m FROM amostra_controlo")[0]["m"] or 0) + 1
    quando = agora()
    with bd.ligacao() as c:
        c.executemany("INSERT INTO amostra_controlo(id_pub, id_amostra, ordem, criada_em, criada_por) VALUES (?,?,?,?,?)",
                      [(x, id_amostra, i, quando, quem) for i, x in enumerate(escolha, 1)])
    info = {"id_amostra": id_amostra, "n": len(escolha), "candidatos": len(cand), "semente": semente, "id_lote": id_lote}
    bd.auditar(quem, "amostra_controlo", info)
    return info


# ---------------------------- métricas ----------------------------
def _kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n**2
    return None if pe == 1 else (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(max(0.0, centro - meia), 3), round(min(1.0, centro + meia), 3)


def _bloco_revisoes(rev: list, ks: tuple[int, ...]) -> dict:
    out: dict = {"n_revistas": len(rev)}
    if not rev:
        return out
    ameaca = [x["analista_cat"] != "Normal" for x in rev]
    out["precisao_at_k"] = {k: round(sum(ameaca[:k]) / min(k, len(ameaca)), 3) for k in ks if len(ameaca) >= k}
    s, a = [x["sistema"] for x in rev], [x["analista_cat"] for x in rev]
    out["concordancia"] = round(sum(x == y for x, y in zip(s, a)) / len(rev), 3)
    k = _kappa(s, a)
    out["kappa_analista_sistema"] = None if k is None else round(k, 3)
    out["por_categoria"] = {
        c: {"previstas": s.count(c), "confirmadas": sum(1 for x, y in zip(s, a) if x == c and y == c)}
        for c in ROTULOS
    }
    return out


def metricas(bd: BaseDados, ks: tuple[int, ...] = (10, 25, 50, 100)) -> dict:
    """Métricas operacionais a partir das revisões humanas.

    - precisão@K: entre os K itens de maior prioridade já revistos, fracção que o
      analista confirmou como ameaça (qualquer categoria diferente de Normal);
    - concordância e Kappa analista–sistema (global e por analista);
    - Kappa entre analistas nos itens revistos por mais de um;
    - amostra de controlo: fracção de itens classificados como Normal que o
      analista considerou ameaça (estimativa das ameaças que a fila não mostra);
    - latência recolha→classificação (mediana e P95), para a H2.
    """
    rev = bd.consultar(
        """SELECT r.id_pub, r.analista, k.categoria AS sistema, r.categoria AS analista_cat, k.prioridade, r.origem_fila
           FROM revisoes r JOIN classificacoes k ON k.id_pub = r.id_pub ORDER BY k.prioridade DESC, r.id_pub"""
    )
    da_fila = [x for x in rev if x["origem_fila"] != "amostra"]
    out = _bloco_revisoes(da_fila, ks)
    out["por_analista"] = {
        a: _bloco_revisoes([x for x in da_fila if x["analista"] == a], ks)
        for a in sorted({x["analista"] for x in da_fila})
    }
    # acordo entre analistas
    por_item: dict = defaultdict(dict)
    for x in rev:
        por_item[x["id_pub"]][x["analista"]] = x["analista_cat"]
    pares = []
    for a, b in itertools.combinations(sorted({x["analista"] for x in rev}), 2):
        comuns = [d for d in por_item.values() if a in d and b in d]
        if comuns:
            k = _kappa([d[a] for d in comuns], [d[b] for d in comuns])
            pares.append({"analistas": [a, b], "n_comuns": len(comuns),
                          "concordancia": round(sum(d[a] == d[b] for d in comuns) / len(comuns), 3),
                          "kappa": None if k is None else round(k, 3)})
    out["entre_analistas"] = pares
    # amostra de controlo (sensibilidade)
    am = [x for x in rev if x["origem_fila"] == "amostra"]
    if am:
        por_a = {}
        for a in sorted({x["analista"] for x in am}):
            xs = [x for x in am if x["analista"] == a]
            fn = sum(x["analista_cat"] != "Normal" for x in xs)
            por_a[a] = {"revistos": len(xs), "ameacas_nao_sinalizadas": fn,
                        "taxa": round(fn / len(xs), 3), "ic95": wilson(fn, len(xs))}
        out["amostra_controlo"] = por_a
    out["n_amostra_controlo"] = bd.consultar("SELECT COUNT(*) AS n FROM amostra_controlo")[0]["n"]
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


def panorama(bd: BaseDados, dias: int = 14) -> dict:
    """Agregados para o painel. Só contagens por categoria, dia, plataforma e lote; nunca por autor."""
    q = bd.consultar
    out = {
        "publicacoes": q("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"],
        "classificadas": q("SELECT COUNT(*) AS n FROM classificacoes")[0]["n"],
        "pendentes": bd.n_pendentes(),
        "revistas": q("SELECT COUNT(DISTINCT id_pub) AS n FROM revisoes")[0]["n"],
        "por_categoria": {c: 0 for c in ROTULOS},
        "por_plataforma": [dict(r) for r in q(
            """SELECT p.plataforma, COUNT(*) AS total, SUM(k.categoria != 'Normal') AS sinalizadas
               FROM publicacoes p JOIN classificacoes k ON k.id_pub = p.id_pub GROUP BY p.plataforma ORDER BY total DESC""")],
        "por_dia": [dict(r) for r in q(
            """SELECT substr(COALESCE(p.data_publicacao, p.recolhido_em), 1, 10) AS dia, k.categoria, COUNT(*) AS n
               FROM publicacoes p JOIN classificacoes k ON k.id_pub = p.id_pub
               WHERE substr(COALESCE(p.data_publicacao, p.recolhido_em), 1, 10) >= date('now', ?)
               GROUP BY dia, k.categoria ORDER BY dia""", (f"-{dias} days",))],
        "decisoes": {c: 0 for c in ROTULOS},
    }
    for r in q("SELECT categoria, COUNT(*) AS n FROM classificacoes GROUP BY categoria"):
        out["por_categoria"][r["categoria"]] = r["n"]
    for r in q("SELECT categoria, COUNT(*) AS n FROM revisoes GROUP BY categoria"):
        out["decisoes"][r["categoria"]] = r["n"]
    return out


def exportar_revisoes(bd: BaseDados, destino: Path, quem: str = "sistema") -> int:
    """Exporta as revisões no formato do corpus de treino (id_hash, texto, categoria_final, origem).

    Uma linha por publicação. Quando vários analistas reviram o mesmo item e
    discordaram, o item não é exportado (fica para decisão do supervisor).
    """
    linhas = bd.consultar(
        """SELECT p.id_pub, p.texto, p.plataforma, r.categoria, r.analista
           FROM revisoes r JOIN publicacoes p ON p.id_pub = r.id_pub ORDER BY p.id_pub, r.analista"""
    )
    por_item: dict = defaultdict(list)
    for l in linhas:
        por_item[l["id_pub"]].append(l)
    destino = Path(destino)
    n = discordantes = 0
    with destino.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id_hash", "texto", "categoria_final", "origem", "plataforma", "analistas"])
        for id_pub, rs in por_item.items():
            cats = {r["categoria"] for r in rs}
            if len(cats) > 1:
                discordantes += 1
                continue
            # origem própria: rótulos de analistas sobre itens escolhidos pela fila do modelo; não equivalem
            # à anotação aleatória por 3 anotadores e não devem entrar no conjunto de teste.
            w.writerow([id_pub, rs[0]["texto"], cats.pop(), "revisao_sistema", rs[0]["plataforma"],
                        "|".join(r["analista"] for r in rs)])
            n += 1
    bd.auditar(quem, "exportacao_revisoes", {"n": n, "discordantes_excluidos": discordantes, "ficheiro": destino.name})
    return n
