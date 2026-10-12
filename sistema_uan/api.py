"""Compatibilidade com a versão 0.1: `python -m uvicorn api:app` arranca a aplicação web completa.

A forma recomendada é `python uan.py servir`. A API JSON está em /api (ver /api/docs).
"""

from sistema.web.app import criar_app

app = criar_app()
