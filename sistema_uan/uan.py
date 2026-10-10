"""Linha de comandos do sistema.

Exemplos (Windows, cmd):
    python uan.py importar dados\\comentarios.csv --plataforma YouTube --via api_oficial --descricao "lote 12"
    python uan.py classificar
    python uan.py fila --n 20
    python uan.py metricas
    python uan.py exportar dados\\revisoes_para_treino.csv
    python uan.py limpar --dias 180
    python uan.py medir-latencia dados\\comentarios.csv --repeticoes 3
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import tempfile
import time
from pathlib import Path

from sistema.base_dados import BaseDados
from sistema.classificador import carregar_classificador
from sistema.config import ROTULOS, obter_config
from sistema.servico import VIAS, classificar_pendentes, exportar_revisoes, importar, metricas


def _clf(cfg):
    return carregar_classificador(cfg.caminho_modelo, max_length=cfg.max_length,
                                  tamanho_lote=cfg.tamanho_lote, dispositivo=cfg.dispositivo)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="uan")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("importar"); p.add_argument("ficheiro"); p.add_argument("--plataforma", required=True)
    p.add_argument("--via", required=True, choices=VIAS); p.add_argument("--descricao")
    sub.add_parser("classificar")
    p = sub.add_parser("fila"); p.add_argument("--n", type=int, default=20); p.add_argument("--categoria", choices=ROTULOS)
    sub.add_parser("metricas")
    p = sub.add_parser("exportar"); p.add_argument("destino")
    p = sub.add_parser("limpar"); p.add_argument("--dias", type=int)
    p = sub.add_parser("medir-latencia", help="Mede importação+classificação numa BD temporária (H2)")
    p.add_argument("ficheiro"); p.add_argument("--repeticoes", type=int, default=3); p.add_argument("--plataforma", default="teste")
    a = ap.parse_args(argv)

    cfg = obter_config()
    bd = BaseDados(cfg.caminho_bd)
    if a.cmd == "importar":
        print(json.dumps(importar(bd, Path(a.ficheiro), a.plataforma, a.via, cfg.segredo_hash, a.descricao), ensure_ascii=False))
    elif a.cmd == "classificar":
        print(json.dumps(classificar_pendentes(bd, _clf(cfg), limite=10**9), ensure_ascii=False))
    elif a.cmd == "fila":
        for i, r in enumerate(bd.fila(a.n, a.categoria), 1):
            print(f"{i:>3}. [{r['categoria']:<13} {r['confianca']:.2f} | prior. {r['prioridade']:.2f}] {r['texto'][:110]}")
    elif a.cmd == "metricas":
        print(json.dumps(metricas(bd), ensure_ascii=False, indent=1))
    elif a.cmd == "exportar":
        print(f"{exportar_revisoes(bd, Path(a.destino))} revisões exportadas para {a.destino}")
    elif a.cmd == "limpar":
        print(f"{bd.apagar_antigos(a.dias or cfg.dias_conservacao)} publicações apagadas")
    elif a.cmd == "medir-latencia":
        clf = _clf(cfg)
        tempos, n = [], 0
        for _ in range(a.repeticoes):
            with tempfile.TemporaryDirectory() as d:
                bdt = BaseDados(Path(d) / "t.db")
                t0 = time.perf_counter()
                info = importar(bdt, Path(a.ficheiro), a.plataforma, "manual", cfg.segredo_hash or "medicao", "medição de latência")
                classificar_pendentes(bdt, clf, limite=10**9)
                tempos.append(time.perf_counter() - t0); n = info["novos"]
        print(json.dumps({"modelo": clf.nome, "itens": n, "repeticoes": a.repeticoes,
                          "segundos_total_mediana": round(statistics.median(tempos), 3),
                          "ms_por_item_mediana": round(1000 * statistics.median(tempos) / max(n, 1), 2)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
