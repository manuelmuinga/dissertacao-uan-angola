"""Armazenamento em SQLite (um único ficheiro, sem servidor).

Tabelas:
- lotes: proveniência de cada recolha (plataforma, via, data, volume) — exigido
  pela metodologia para declarar as vias de recolha.
- publicacoes: texto já anonimizado e metadados mínimos.
- classificacoes: saída do modelo, com marcas de tempo para medir a latência (H2).
- revisoes: decisão do analista; servem de novos rótulos para re-treino.
- auditoria: registo de acções (quem fez o quê e quando).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

ESQUEMA = """
CREATE TABLE IF NOT EXISTS lotes (
    id_lote        INTEGER PRIMARY KEY AUTOINCREMENT,
    plataforma     TEXT NOT NULL,
    via            TEXT NOT NULL,          -- api_oficial | manual | scraping_publico | doacao | dataset_terceiros
    descricao      TEXT,
    ficheiro       TEXT,
    importado_em   TEXT NOT NULL,
    n_recebidos    INTEGER NOT NULL DEFAULT 0,
    n_novos        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS publicacoes (
    id_pub          TEXT PRIMARY KEY,
    id_lote         INTEGER REFERENCES lotes(id_lote),
    plataforma      TEXT NOT NULL,
    autor_pseudo    TEXT,
    texto           TEXT NOT NULL,
    data_publicacao TEXT,
    recolhido_em    TEXT NOT NULL,
    contexto        TEXT                    -- ex.: título do vídeo ou canal público
);
CREATE TABLE IF NOT EXISTS classificacoes (
    id_pub         TEXT PRIMARY KEY REFERENCES publicacoes(id_pub) ON DELETE CASCADE,
    modelo         TEXT NOT NULL,
    versao         TEXT NOT NULL,
    probabilidades TEXT NOT NULL,           -- JSON {rotulo: prob}
    categoria      TEXT NOT NULL,
    confianca      REAL NOT NULL,
    prioridade     REAL NOT NULL,
    classificado_em TEXT NOT NULL,
    duracao_ms     REAL NOT NULL           -- tempo de inferência atribuído a este item
);
CREATE TABLE IF NOT EXISTS revisoes (
    id_pub         TEXT PRIMARY KEY REFERENCES publicacoes(id_pub) ON DELETE CASCADE,
    analista       TEXT NOT NULL,
    categoria      TEXT NOT NULL,
    concorda       INTEGER NOT NULL,       -- 1 se igual à categoria do modelo
    posicao_fila   INTEGER,                -- posição na fila quando foi revista (para precisão@K)
    nota           TEXT,
    revisto_em     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    quando     TEXT NOT NULL,
    quem       TEXT NOT NULL,
    accao      TEXT NOT NULL,
    detalhe    TEXT
);
CREATE INDEX IF NOT EXISTS ix_class_prior ON classificacoes(prioridade DESC);
CREATE INDEX IF NOT EXISTS ix_pub_lote ON publicacoes(id_lote);
"""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class BaseDados:
    def __init__(self, caminho: Path | str):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.ligacao() as c:
            c.executescript(ESQUEMA)

    @contextmanager
    def ligacao(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.caminho, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("PRAGMA journal_mode = WAL")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    # ---------------- auditoria ----------------
    def auditar(self, quem: str, accao: str, detalhe: dict | str | None = None) -> None:
        det = json.dumps(detalhe, ensure_ascii=False) if isinstance(detalhe, dict) else detalhe
        with self.ligacao() as c:
            c.execute("INSERT INTO auditoria(quando, quem, accao, detalhe) VALUES (?,?,?,?)", (agora(), quem, accao, det))

    # ---------------- lotes e publicações ----------------
    def criar_lote(self, plataforma: str, via: str, descricao: str | None, ficheiro: str | None) -> int:
        with self.ligacao() as c:
            cur = c.execute(
                "INSERT INTO lotes(plataforma, via, descricao, ficheiro, importado_em) VALUES (?,?,?,?,?)",
                (plataforma, via, descricao, ficheiro, agora()),
            )
            return int(cur.lastrowid)

    def inserir_publicacoes(self, id_lote: int, registos: list[dict]) -> int:
        """Insere publicações novas; ignora duplicados. Devolve o número de novas."""
        with self.ligacao() as c:
            antes = c.total_changes
            c.executemany(
                """INSERT OR IGNORE INTO publicacoes
                   (id_pub, id_lote, plataforma, autor_pseudo, texto, data_publicacao, recolhido_em, contexto)
                   VALUES (:id_pub, :id_lote, :plataforma, :autor_pseudo, :texto, :data_publicacao, :recolhido_em, :contexto)""",
                [{**r, "id_lote": id_lote} for r in registos],
            )
            novos = c.total_changes - antes
            c.execute("UPDATE lotes SET n_recebidos = ?, n_novos = ? WHERE id_lote = ?", (len(registos), novos, id_lote))
            return novos

    def pendentes(self, limite: int = 1000) -> list[sqlite3.Row]:
        with self.ligacao() as c:
            return c.execute(
                """SELECT p.id_pub, p.texto FROM publicacoes p
                   LEFT JOIN classificacoes k ON k.id_pub = p.id_pub
                   WHERE k.id_pub IS NULL ORDER BY p.recolhido_em LIMIT ?""",
                (limite,),
            ).fetchall()

    def gravar_classificacoes(self, linhas: list[dict]) -> None:
        with self.ligacao() as c:
            c.executemany(
                """INSERT OR REPLACE INTO classificacoes
                   (id_pub, modelo, versao, probabilidades, categoria, confianca, prioridade, classificado_em, duracao_ms)
                   VALUES (:id_pub, :modelo, :versao, :probabilidades, :categoria, :confianca, :prioridade, :classificado_em, :duracao_ms)""",
                linhas,
            )

    # ---------------- fila e revisões ----------------
    def fila(self, limite: int = 50, categoria: str | None = None, incluir_normais: bool = False) -> list[sqlite3.Row]:
        filtros = ["r.id_pub IS NULL"]
        params: list = []
        if categoria:
            filtros.append("k.categoria = ?")
            params.append(categoria)
        elif not incluir_normais:
            filtros.append("k.categoria != 'Normal'")
        params.append(limite)
        sql = f"""SELECT p.id_pub, p.plataforma, p.texto, p.contexto, p.data_publicacao, k.categoria, k.confianca,
                         k.prioridade, k.probabilidades, k.modelo, k.versao
                  FROM classificacoes k JOIN publicacoes p ON p.id_pub = k.id_pub
                  LEFT JOIN revisoes r ON r.id_pub = k.id_pub
                  WHERE {' AND '.join(filtros)}
                  ORDER BY k.prioridade DESC LIMIT ?"""
        with self.ligacao() as c:
            return c.execute(sql, params).fetchall()

    def gravar_revisao(self, id_pub: str, analista: str, categoria: str, posicao: int | None, nota: str | None) -> None:
        with self.ligacao() as c:
            k = c.execute("SELECT categoria FROM classificacoes WHERE id_pub = ?", (id_pub,)).fetchone()
            if k is None:
                raise KeyError(f"Publicação {id_pub} sem classificação.")
            c.execute(
                """INSERT OR REPLACE INTO revisoes(id_pub, analista, categoria, concorda, posicao_fila, nota, revisto_em)
                   VALUES (?,?,?,?,?,?,?)""",
                (id_pub, analista, categoria, int(categoria == k["categoria"]), posicao, nota, agora()),
            )
        self.auditar(analista, "revisao", {"id_pub": id_pub, "categoria": categoria})

    # ---------------- consultas para o painel e métricas ----------------
    def consultar(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.ligacao() as c:
            return c.execute(sql, params).fetchall()

    def apagar_antigos(self, dias: int, quem: str = "sistema") -> int:
        """Remove publicações não revistas com mais de `dias` dias (minimização, Lei 22/11)."""
        limite = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        with self.ligacao() as c:
            cur = c.execute(
                """DELETE FROM publicacoes WHERE recolhido_em < ?
                   AND id_pub NOT IN (SELECT id_pub FROM revisoes)""",
                (limite,),
            )
            n = cur.rowcount
        self.auditar(quem, "limpeza_conservacao", {"dias": dias, "apagadas": n})
        return n
