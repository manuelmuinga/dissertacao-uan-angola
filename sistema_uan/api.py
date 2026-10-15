"""Serviço de inferência e integração (FastAPI).

Arranque (Windows, cmd):
    python -m uvicorn api:app --port 8000
Documentação interactiva: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel, Field

from sistema.base_dados import BaseDados
from sistema.classificador import carregar_classificador
from sistema.config import ROTULOS, obter_config
from sistema.servico import VIAS, classificar_pendentes, importar, metricas

cfg = obter_config()
bd = BaseDados(cfg.caminho_bd)
clf = carregar_classificador(cfg.caminho_modelo, max_length=cfg.max_length,
                             tamanho_lote=cfg.tamanho_lote, dispositivo=cfg.dispositivo)

app = FastAPI(title="Sistema UAN – triagem de ameaças", version="0.1.0",
              description="Classificação para apoio ao analista. Nenhuma decisão automática.")


class PedidoClassificar(BaseModel):
    textos: list[str] = Field(..., min_length=1, max_length=256)


class PedidoRevisao(BaseModel):
    id_pub: str
    analista: str = Field(..., min_length=2)
    categoria: str
    posicao_fila: int | None = None
    nota: str | None = None


@app.get("/saude")
def saude():
    return {"estado": "ok", "modelo": clf.nome, "versao": clf.versao,
            "aviso": "classificador de demonstração" if clf.nome == "DEMONSTRACAO" else None}


@app.post("/classificar")
def classificar(p: PedidoClassificar):
    """Classifica textos avulsos sem os gravar (útil para testes e integração)."""
    return [{"categoria": r.categoria, "confianca": round(r.confianca, 4), "probabilidades": r.probabilidades}
            for r in clf.classificar(p.textos)]


@app.post("/importar")
async def importar_ficheiro(ficheiro: UploadFile, plataforma: str, via: str, descricao: str | None = None):
    if via not in VIAS:
        raise HTTPException(422, f"via deve ser uma de {VIAS}")
    if not cfg.segredo_hash:
        raise HTTPException(500, "UAN_SEGREDO_HASH não definido.")
    sufixo = Path(ficheiro.filename or "x.csv").suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
        tmp.write(await ficheiro.read())
    try:
        info = importar(bd, Path(tmp.name), plataforma, via, cfg.segredo_hash, descricao, quem="api")
    finally:
        Path(tmp.name).unlink(missing_ok=True)  # o ficheiro bruto não fica guardado
    info.update(classificar_pendentes(bd, clf))
    return info


@app.post("/classificar-pendentes")
def classificar_todos():
    return classificar_pendentes(bd, clf)


@app.get("/fila")
def fila(limite: int = 50, categoria: str | None = None):
    if categoria and categoria not in ROTULOS:
        raise HTTPException(422, f"categoria deve ser uma de {ROTULOS}")
    return [{**dict(r), "probabilidades": json.loads(r["probabilidades"])} for r in bd.fila(limite, categoria)]


@app.post("/revisoes")
def rever(p: PedidoRevisao):
    if p.categoria not in ROTULOS:
        raise HTTPException(422, f"categoria deve ser uma de {ROTULOS}")
    try:
        bd.gravar_revisao(p.id_pub, p.analista, p.categoria, p.posicao_fila, p.nota)
    except KeyError as e:
        raise HTTPException(404, str(e))
    return {"estado": "gravada"}


@app.get("/metricas")
def obter_metricas():
    return metricas(bd)
