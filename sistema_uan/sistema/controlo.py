"""Controlo do servidor em execução: permite trocar entre o modo real e o de demonstração sem fechar a janela.

`python uan.py servir` arranca o servidor num ciclo. Quando um supervisor pede a troca na aplicação,
`pedir_troca` regista o modo pedido e manda o servidor terminar de forma ordenada; o ciclo em uan.py
arranca-o de novo com a outra base de dados. Sem esse ciclo (testes, uvicorn arrancado à mão),
a troca não está disponível.
"""

from __future__ import annotations

import threading

servidor = None            # uvicorn.Server em execução, definido por uan.py
pedido: str | None = None  # "demonstracao" ou "real"
MODOS = ("demonstracao", "real")


def disponivel() -> bool:
    return servidor is not None


def pedir_troca(modo: str, atraso_s: float = 0.4) -> bool:
    """Pede a troca de modo; o servidor pára depois de responder ao pedido em curso."""
    global pedido
    if modo not in MODOS or servidor is None:
        return False
    pedido = modo
    alvo = servidor
    threading.Timer(atraso_s, lambda: setattr(alvo, "should_exit", True)).start()
    return True
