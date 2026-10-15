"""Armazenamento em SQLite (um único ficheiro, sem servidor).

Tabelas:
- lotes: proveniência de cada recolha (plataforma, via, data, volume), exigida
  pela metodologia para declarar as vias de recolha.
- publicacoes: texto já anonimizado e metadados mínimos.
- classificacoes: saída do modelo, com marcas de tempo para medir a latência (H2).
- revisoes: decisão de cada analista sobre cada publicação (uma linha por par
  publicação–analista, para permitir medir o acordo entre analistas).
- amostra_controlo: itens classificados como Normal sorteados para estimar a
  sensibilidade (o que a fila não mostra).
- fontes: canais, vídeos, feeds e sítios públicos de onde o sistema recolhe.
- pub_provincias: províncias MENCIONADAS em cada publicação (não a localização do autor).
- alertas e alertas_vistos: alertas confirmados e de tendência, e quem já os viu.
- utilizadores e sessoes: acesso à aplicação web.
- definicoes: opções do supervisor (por exemplo, revisão cega).
- auditoria: registo de acções (quem fez o quê e quando).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from .geografia import detectar_provincias

GEO_VERSAO = "1"  # aumentar quando a lista de topónimos mudar, para reindexar

ESQUEMA = """
CREATE TABLE IF NOT EXISTS lotes (
    id_lote        INTEGER PRIMARY KEY AUTOINCREMENT,
    plataforma     TEXT NOT NULL,
    via            TEXT NOT NULL,          -- api_oficial | manual | scraping_publico | doacao | dataset_terceiros
    descricao      TEXT,
    ficheiro       TEXT,
    importado_em   TEXT NOT NULL,
    n_recebidos    INTEGER NOT NULL DEFAULT 0,
    n_novos        INTEGER NOT NULL DEFAULT 0,
    importado_por  TEXT,
    id_fonte       INTEGER REFERENCES fontes(id_fonte) ON DELETE SET NULL
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
    id_pub         TEXT NOT NULL REFERENCES publicacoes(id_pub) ON DELETE CASCADE,
    analista       TEXT NOT NULL,
    categoria      TEXT NOT NULL,
    concorda       INTEGER NOT NULL,       -- 1 se igual à categoria do modelo
    posicao_fila   INTEGER,                -- posição na fila quando foi revista
    nota           TEXT,
    revisto_em     TEXT NOT NULL,
    origem_fila    TEXT NOT NULL DEFAULT 'fila',   -- fila | amostra | api
    cega           INTEGER NOT NULL DEFAULT 0,     -- 1 se a sugestão do modelo estava escondida
    PRIMARY KEY (id_pub, analista)
);
CREATE TABLE IF NOT EXISTS amostra_controlo (
    id_pub      TEXT PRIMARY KEY REFERENCES publicacoes(id_pub) ON DELETE CASCADE,
    id_amostra  INTEGER NOT NULL,
    ordem       INTEGER NOT NULL,
    criada_em   TEXT NOT NULL,
    criada_por  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS utilizadores (
    utilizador     TEXT PRIMARY KEY,
    nome           TEXT NOT NULL,
    papel          TEXT NOT NULL,          -- analista | supervisor
    hash_senha     TEXT NOT NULL,
    activo         INTEGER NOT NULL DEFAULT 1,
    criado_em      TEXT NOT NULL,
    ultimo_acesso  TEXT,
    falhas         INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate  TEXT
);
CREATE TABLE IF NOT EXISTS sessoes (
    token_hash  TEXT PRIMARY KEY,
    utilizador  TEXT NOT NULL REFERENCES utilizadores(utilizador) ON DELETE CASCADE,
    csrf        TEXT NOT NULL,
    criada_em   TEXT NOT NULL,
    expira_em   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fontes (
    id_fonte       INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo           TEXT NOT NULL,          -- youtube_video | youtube_canal | rss | pagina | sitio
    endereco       TEXT NOT NULL,
    nome           TEXT NOT NULL,
    plataforma     TEXT NOT NULL,
    max_itens      INTEGER NOT NULL DEFAULT 100,
    activa         INTEGER NOT NULL DEFAULT 1,
    criada_em      TEXT NOT NULL,
    criada_por     TEXT NOT NULL,
    ultima_recolha TEXT,
    ultimo_estado  TEXT
);
CREATE TABLE IF NOT EXISTS pub_provincias (
    id_pub     TEXT NOT NULL REFERENCES publicacoes(id_pub) ON DELETE CASCADE,
    provincia  TEXT NOT NULL,              -- código de 3 letras (18 províncias, divisão anterior a 2025)
    PRIMARY KEY (id_pub, provincia)
);
CREATE TABLE IF NOT EXISTS alertas (
    id_alerta    INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo         TEXT NOT NULL,            -- confirmado | tendencia
    chave        TEXT NOT NULL UNIQUE,     -- evita alertas repetidos
    criado_em    TEXT NOT NULL,
    titulo       TEXT NOT NULL,
    categoria    TEXT,
    provincia    TEXT,                     -- código, NAC (nacional) ou NULL
    id_pub       TEXT REFERENCES publicacoes(id_pub) ON DELETE SET NULL,
    detalhe      TEXT,                     -- JSON
    email_estado TEXT NOT NULL DEFAULT 'nao_enviado',
    email_em     TEXT
);
CREATE TABLE IF NOT EXISTS alertas_vistos (
    id_alerta   INTEGER NOT NULL REFERENCES alertas(id_alerta) ON DELETE CASCADE,
    utilizador  TEXT NOT NULL,
    visto_em    TEXT NOT NULL,
    PRIMARY KEY (id_alerta, utilizador)
);
CREATE TABLE IF NOT EXISTS definicoes (
    chave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    quando     TEXT NOT NULL,
    quem       TEXT NOT NULL,
    accao      TEXT NOT NULL,
    detalhe    TEXT
);
CREATE INDEX IF NOT EXISTS ix_class_prior ON classificacoes(prioridade DESC);
CREATE INDEX IF NOT EXISTS ix_class_cat ON classificacoes(categoria);
CREATE INDEX IF NOT EXISTS ix_pub_lote ON publicacoes(id_lote);
CREATE INDEX IF NOT EXISTS ix_rev_analista ON revisoes(analista);
CREATE INDEX IF NOT EXISTS ix_pubprov_prov ON pub_provincias(provincia);
CREATE INDEX IF NOT EXISTS ix_alertas_criado ON alertas(criado_em DESC);
"""


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _colunas(c: sqlite3.Connection, tabela: str) -> list[str]:
    return [r[1] for r in c.execute(f"PRAGMA table_info({tabela})")]


def _migrar(c: sqlite3.Connection) -> None:
    """Actualiza bases de dados criadas pela versão 0.1 do protótipo."""
    if "origem_fila" not in _colunas(c, "revisoes"):
        # 0.1: uma revisão por publicação (id_pub PRIMARY KEY). Passa a uma por analista.
        c.executescript("""
            ALTER TABLE revisoes RENAME TO revisoes_v01;
            CREATE TABLE revisoes (
                id_pub TEXT NOT NULL REFERENCES publicacoes(id_pub) ON DELETE CASCADE,
                analista TEXT NOT NULL, categoria TEXT NOT NULL, concorda INTEGER NOT NULL,
                posicao_fila INTEGER, nota TEXT, revisto_em TEXT NOT NULL,
                origem_fila TEXT NOT NULL DEFAULT 'fila', cega INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (id_pub, analista));
            INSERT INTO revisoes(id_pub, analista, categoria, concorda, posicao_fila, nota, revisto_em)
                SELECT id_pub, analista, categoria, concorda, posicao_fila, nota, revisto_em FROM revisoes_v01;
            DROP TABLE revisoes_v01;
            CREATE INDEX IF NOT EXISTS ix_rev_analista ON revisoes(analista);
        """)
    if "importado_por" not in _colunas(c, "lotes"):
        c.execute("ALTER TABLE lotes ADD COLUMN importado_por TEXT")
    if "id_fonte" not in _colunas(c, "lotes"):
        c.execute("ALTER TABLE lotes ADD COLUMN id_fonte INTEGER REFERENCES fontes(id_fonte) ON DELETE SET NULL")


class BaseDados:
    def __init__(self, caminho: Path | str):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self.ligacao() as c:
            # Tabelas antigas primeiro (CREATE IF NOT EXISTS não altera as existentes), depois a migração.
            c.executescript(ESQUEMA.split("CREATE INDEX IF NOT EXISTS ix_rev_analista")[0])
            _migrar(c)
            c.executescript(ESQUEMA)
            # Bases criadas antes da localização: indexa uma vez as publicações existentes.
            versao = c.execute("SELECT valor FROM definicoes WHERE chave = 'geo_versao'").fetchone()
            if versao is None or versao["valor"] != GEO_VERSAO:
                c.execute("DELETE FROM pub_provincias")
                linhas = c.execute("SELECT id_pub, texto, contexto FROM publicacoes").fetchall()
                c.executemany("INSERT OR IGNORE INTO pub_provincias(id_pub, provincia) VALUES (?,?)",
                              [(r["id_pub"], p) for r in linhas for p in detectar_provincias(r["texto"], r["contexto"])])
                c.execute("INSERT OR REPLACE INTO definicoes(chave, valor) VALUES ('geo_versao', ?)", (GEO_VERSAO,))

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

    # ---------------- auditoria e definições ----------------
    def auditar(self, quem: str, accao: str, detalhe: dict | str | None = None) -> None:
        det = json.dumps(detalhe, ensure_ascii=False) if isinstance(detalhe, dict) else detalhe
        with self.ligacao() as c:
            c.execute("INSERT INTO auditoria(quando, quem, accao, detalhe) VALUES (?,?,?,?)", (agora(), quem, accao, det))

    def definicao(self, chave: str, omissao: str = "") -> str:
        r = self.consultar("SELECT valor FROM definicoes WHERE chave = ?", (chave,))
        return r[0]["valor"] if r else omissao

    def definir(self, chave: str, valor: str, quem: str) -> None:
        with self.ligacao() as c:
            c.execute("INSERT OR REPLACE INTO definicoes(chave, valor) VALUES (?,?)", (chave, valor))
        self.auditar(quem, "definicao", {"chave": chave, "valor": valor})

    # ---------------- lotes e publicações ----------------
    def criar_lote(self, plataforma: str, via: str, descricao: str | None, ficheiro: str | None,
                   quem: str | None = None, id_fonte: int | None = None) -> int:
        with self.ligacao() as c:
            cur = c.execute(
                "INSERT INTO lotes(plataforma, via, descricao, ficheiro, importado_em, importado_por, id_fonte) "
                "VALUES (?,?,?,?,?,?,?)",
                (plataforma, via, descricao, ficheiro, agora(), quem, id_fonte),
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
            c.executemany("INSERT OR IGNORE INTO pub_provincias(id_pub, provincia) VALUES (?,?)",
                          [(r["id_pub"], p) for r in registos for p in detectar_provincias(r["texto"], r.get("contexto"))])
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

    def n_pendentes(self) -> int:
        return self.consultar(
            """SELECT COUNT(*) AS n FROM publicacoes p LEFT JOIN classificacoes k ON k.id_pub = p.id_pub
               WHERE k.id_pub IS NULL""")[0]["n"]

    def gravar_classificacoes(self, linhas: list[dict]) -> None:
        with self.ligacao() as c:
            c.executemany(
                """INSERT OR REPLACE INTO classificacoes
                   (id_pub, modelo, versao, probabilidades, categoria, confianca, prioridade, classificado_em, duracao_ms)
                   VALUES (:id_pub, :modelo, :versao, :probabilidades, :categoria, :confianca, :prioridade, :classificado_em, :duracao_ms)""",
                linhas,
            )

    # ---------------- fila e revisões ----------------
    def fila(self, limite: int = 50, categoria: str | None = None, incluir_normais: bool = False,
             analista: str | None = None, plataforma: str | None = None, id_lote: int | None = None,
             deslocamento: int = 0) -> list[sqlite3.Row]:
        """Itens classificados e ainda não revistos, por prioridade decrescente.

        Com `analista`, mostra o que ESSE analista ainda não reviu (dois analistas
        revêem os mesmos itens de forma independente). Sem `analista`, mostra o que
        ninguém reviu.
        """
        params: list = []
        if analista:
            filtros = ["NOT EXISTS (SELECT 1 FROM revisoes r WHERE r.id_pub = k.id_pub AND r.analista = ?)"]
            params.append(analista)
        else:
            filtros = ["NOT EXISTS (SELECT 1 FROM revisoes r WHERE r.id_pub = k.id_pub)"]
        if categoria:
            filtros.append("k.categoria = ?")
            params.append(categoria)
        elif not incluir_normais:
            filtros.append("k.categoria != 'Normal'")
        if plataforma:
            filtros.append("p.plataforma = ?")
            params.append(plataforma)
        if id_lote:
            filtros.append("p.id_lote = ?")
            params.append(id_lote)
        params += [limite, deslocamento]
        sql = f"""SELECT p.id_pub, p.id_lote, p.plataforma, p.texto, p.contexto, p.data_publicacao, k.categoria,
                         k.confianca, k.prioridade, k.probabilidades, k.modelo, k.versao
                  FROM classificacoes k JOIN publicacoes p ON p.id_pub = k.id_pub
                  WHERE {' AND '.join(filtros)}
                  ORDER BY k.prioridade DESC, p.id_pub LIMIT ? OFFSET ?"""
        with self.ligacao() as c:
            return c.execute(sql, params).fetchall()

    def n_fila(self, analista: str | None = None) -> int:
        cond = ("NOT EXISTS (SELECT 1 FROM revisoes r WHERE r.id_pub = k.id_pub AND r.analista = ?)"
                if analista else "NOT EXISTS (SELECT 1 FROM revisoes r WHERE r.id_pub = k.id_pub)")
        return self.consultar(f"SELECT COUNT(*) AS n FROM classificacoes k WHERE k.categoria != 'Normal' AND {cond}",
                              (analista,) if analista else ())[0]["n"]

    def gravar_revisao(self, id_pub: str, analista: str, categoria: str, posicao: int | None, nota: str | None,
                       origem: str = "fila", cega: bool = False) -> None:
        with self.ligacao() as c:
            k = c.execute("SELECT categoria FROM classificacoes WHERE id_pub = ?", (id_pub,)).fetchone()
            if k is None:
                raise KeyError(f"Publicação {id_pub} sem classificação.")
            c.execute(
                """INSERT OR REPLACE INTO revisoes
                   (id_pub, analista, categoria, concorda, posicao_fila, nota, revisto_em, origem_fila, cega)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (id_pub, analista, categoria, int(categoria == k["categoria"]), posicao, nota, agora(), origem, int(cega)),
            )
        self.auditar(analista, "revisao", {"id_pub": id_pub, "categoria": categoria, "origem": origem})

    def apagar_revisao(self, id_pub: str, analista: str, max_segundos: int = 120) -> bool:
        """Desfaz a decisão recente de um analista (só a sua e só nos últimos `max_segundos`)."""
        limite = (datetime.now(timezone.utc) - timedelta(seconds=max_segundos)).isoformat(timespec="milliseconds")
        with self.ligacao() as c:
            n = c.execute("DELETE FROM revisoes WHERE id_pub = ? AND analista = ? AND revisto_em >= ?",
                          (id_pub, analista, limite)).rowcount
        if n:
            self.auditar(analista, "revisao_desfeita", {"id_pub": id_pub})
        return bool(n)

    # ---------------- amostra de controlo ----------------
    def fila_amostra(self, analista: str, limite: int = 50) -> list[sqlite3.Row]:
        with self.ligacao() as c:
            return c.execute(
                """SELECT p.id_pub, p.id_lote, p.plataforma, p.texto, p.contexto, p.data_publicacao, k.categoria,
                          k.confianca, k.prioridade, k.probabilidades, k.modelo, k.versao, a.ordem
                   FROM amostra_controlo a JOIN publicacoes p ON p.id_pub = a.id_pub
                   JOIN classificacoes k ON k.id_pub = a.id_pub
                   WHERE NOT EXISTS (SELECT 1 FROM revisoes r WHERE r.id_pub = a.id_pub AND r.analista = ?)
                   ORDER BY a.id_amostra, a.ordem LIMIT ?""",
                (analista, limite),
            ).fetchall()

    # ---------------- consultas gerais ----------------
    def consultar(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.ligacao() as c:
            return c.execute(sql, params).fetchall()

    def publicacao(self, id_pub: str) -> sqlite3.Row | None:
        r = self.consultar(
            """SELECT p.*, k.categoria, k.confianca, k.prioridade, k.probabilidades, k.modelo, k.versao, k.classificado_em
               FROM publicacoes p LEFT JOIN classificacoes k ON k.id_pub = p.id_pub WHERE p.id_pub = ?""",
            (id_pub,))
        return r[0] if r else None

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

    def copia_seguranca(self, destino: Path, quem: str = "sistema") -> Path:
        """Cópia consistente da base de dados (API de backup do SQLite)."""
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        with self.ligacao() as c:
            alvo = sqlite3.connect(destino)
            try:
                c.backup(alvo)
            finally:
                alvo.close()
        self.auditar(quem, "copia_seguranca", {"ficheiro": destino.name})
        return destino
