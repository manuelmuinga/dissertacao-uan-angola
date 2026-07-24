"""
=============================================================================
MÓDULO — Camada de Armazenamento Dual
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026

Arquitectura de armazenamento (conforme diagrama da dissertação):
  ┌─────────────────────────────────────────────────────────────┐
  │           CAMADA 3 — ARMAZENAMENTO HÍBRIDO                  │
  │                                                             │
  │  MongoDB Atlas          │  SQL Server Express               │
  │  (dados brutos e        │  (Data Warehouse — modelo         │
  │   classificados)        │   estrela — Windows 11 local)     │
  │  3 colecções            │  factos_ameacas + 4 dimensões     │
  └─────────────────────────────────────────────────────────────┘

SO: Windows 11 (64-bit) — SQL Server Express instalado localmente
Instalação:
  pip install pymongo[srv] pyodbc dnspython
  # SQL Server Express: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads
  # ODBC Driver 18:   https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server
=============================================================================
"""

import os
import logging
from datetime import datetime, timezone

import pymongo
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("ArmazenamentoDual")

# ─── Configuração ─────────────────────────────────────────────────────────────
MONGODB_URI   = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# SQL Server Express local no Windows 11 (não Azure)
SQL_SERVER_CONN = os.getenv(
    "SQL_SERVER_CONN",
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"       # instância local Windows 11
    "DATABASE=AmeacasAngola_DW;"
    "Trusted_Connection=yes;"              # autenticação Windows
    "TrustServerCertificate=yes;"
)


# ═══════════════════════════════════════════════════════════════════════════════
# MONGODB ATLAS — dados brutos e classificados
# ═══════════════════════════════════════════════════════════════════════════════
class MongoDBStorage:
    """
    Camada de persistência MongoDB Atlas.
    Guarda dados brutos OSINT e resultados da classificação BERT.
    """

    def __init__(self, uri: str = None):
        self.uri = uri or MONGODB_URI
        self._client = None

    def _get_client(self):
        if not self._client:
            self._client = pymongo.MongoClient(
                self.uri, serverSelectionTimeoutMS=8000)
        return self._client

    def guardar_brutos(self, publicacoes: list) -> int:
        """Guarda publicações brutas OSINT (antes do processamento PLN)."""
        if not publicacoes:
            return 0
        try:
            col = self._get_client()["dissertacao_angola"]["publicacoes_brutas"]
            inseridos = sum(
                1 for p in publicacoes
                if col.update_one(
                    {"id_externo": p["id_externo"]},
                    {"$setOnInsert": p},
                    upsert=True
                ).upserted_id
            )
            logger.info(f"MongoDB [brutas]: {inseridos}/{len(publicacoes)} inseridas")
            return inseridos
        except Exception as e:
            logger.error(f"MongoDB erro [brutas]: {e}")
            return 0

    def guardar_classificadas(self, publicacoes: list) -> int:
        """Guarda publicações após classificação pelo BERT."""
        if not publicacoes:
            return 0
        try:
            col = self._get_client()["dissertacao_angola"]["publicacoes_classificadas"]
            inseridos = sum(
                1 for p in publicacoes
                if col.update_one(
                    {"id_externo": p["id_externo"]},
                    {"$set": p},
                    upsert=True
                ).upserted_id
            )
            logger.info(f"MongoDB [classificadas]: {inseridos}/{len(publicacoes)} inseridas")
            return inseridos
        except Exception as e:
            logger.error(f"MongoDB erro [classificadas]: {e}")
            return 0

    def registar_log_scraper(self, plataforma: str, total: int,
                              inseridos: int, duracao: float, erro: str = None):
        """Regista métricas de cada ciclo de recolha OSINT."""
        try:
            col = self._get_client()["dissertacao_angola"]["logs_scrapers"]
            col.insert_one({
                "timestamp":      datetime.now(timezone.utc).isoformat(),
                "plataforma":     plataforma,
                "total_recolhido": total,
                "inseridos":      inseridos,
                "duracao_seg":    duracao,
                "erro":           erro,
            })
        except Exception as e:
            logger.error(f"MongoDB erro [logs]: {e}")

    def consultar_ameacas(self, categoria=None, provincia=None, limite=100):
        """Consulta publicações classificadas com filtros opcionais."""
        try:
            col   = self._get_client()["dissertacao_angola"]["publicacoes_classificadas"]
            filtro = {"categoria": {"$ne": "Normal"}}
            if categoria: filtro["categoria"] = categoria
            if provincia: filtro["provincia"] = provincia
            return list(col.find(filtro).sort("classificado_em", -1).limit(limite))
        except Exception as e:
            logger.error(f"MongoDB erro [consulta]: {e}")
            return []

    def fechar(self):
        if self._client:
            self._client.close()
            self._client = None


# ═══════════════════════════════════════════════════════════════════════════════
# SQL SERVER EXPRESS (Windows 11 local) — Data Warehouse modelo estrela
# ═══════════════════════════════════════════════════════════════════════════════
class SQLServerStorage:
    """
    Camada de persistência SQL Server Express (Windows 11 local).
    Implementa o modelo estrela para análise no Power BI.

    Pré-requisitos (Windows 11):
    1. SQL Server Express instalado (localhost\SQLEXPRESS)
    2. Script dados/criar_data_warehouse.sql executado no SSMS
    3. ODBC Driver 18 instalado
    4. pyodbc: pip install pyodbc

    String de ligação (.env):
    SQL_SERVER_CONN=DRIVER={ODBC Driver 18 for SQL Server};
                    SERVER=localhost\SQLEXPRESS;
                    DATABASE=AmeacasAngola_DW;
                    Trusted_Connection=yes;
                    TrustServerCertificate=yes;
    """

    def __init__(self, conn_str: str = None):
        self.conn_str = conn_str or SQL_SERVER_CONN
        self._disponivel = None

    def verificar_disponibilidade(self) -> bool:
        """Verifica se o SQL Server Express está disponível."""
        if self._disponivel is not None:
            return self._disponivel
        try:
            import pyodbc
            conn = pyodbc.connect(self.conn_str, timeout=5)
            conn.close()
            self._disponivel = True
            logger.info("SQL Server Express: disponível (Windows 11 local)")
        except ImportError:
            logger.warning("pyodbc não instalado: pip install pyodbc")
            self._disponivel = False
        except Exception as e:
            logger.warning(f"SQL Server Express não disponível: {e}")
            logger.warning("Verificar: SQL Server Express instalado? SSMS configurado?")
            self._disponivel = False
        return self._disponivel

    def _obter_ou_criar_dimensao(self, cursor, tabela, campo, valor):
        """Obtém ou cria um registo numa tabela de dimensão."""
        cursor.execute(f"SELECT id_{campo.split('_')[1] if '_' in campo else campo} FROM {tabela} WHERE {campo} = ?", valor)
        row = cursor.fetchone()
        if row:
            return row[0]
        # Inserir novo registo na dimensão
        cursor.execute(f"INSERT INTO {tabela} ({campo}) OUTPUT INSERTED.id_{campo.split('_')[1] if '_' in campo else campo} VALUES (?)", valor)
        return cursor.fetchone()[0]

    def _obter_id_tempo(self, cursor, data_str: str) -> int:
        """Obtém ou cria registo na dimensão tempo."""
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(data_str.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(timezone.utc)

        cursor.execute("SELECT id_tempo FROM dim_tempo WHERE data = ?", dt.date())
        row = cursor.fetchone()
        if row:
            return row[0]

        dias_semana = ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]
        cursor.execute("""
            INSERT INTO dim_tempo (data, ano, mes, dia, hora, dia_semana, trimestre, semana_ano)
            OUTPUT INSERTED.id_tempo
            VALUES (?,?,?,?,?,?,?,?)
        """, dt.date(), dt.year, dt.month, dt.day, dt.hour,
             dias_semana[dt.weekday()], (dt.month - 1) // 3 + 1, dt.isocalendar()[1])
        return cursor.fetchone()[0]

    def _obter_id_categoria(self, cursor, categoria: str) -> int:
        cursor.execute("SELECT id_categoria FROM dim_categoria WHERE categoria = ?", categoria)
        row = cursor.fetchone()
        return row[0] if row else None

    def _obter_id_plataforma(self, cursor, plataforma: str) -> int:
        cursor.execute("SELECT id_plataforma FROM dim_plataforma WHERE plataforma = ?", plataforma)
        row = cursor.fetchone()
        return row[0] if row else None

    def _obter_id_provincia(self, cursor, provincia: str) -> int:
        cursor.execute("SELECT id_provincia FROM dim_provincia WHERE provincia = ?", provincia)
        row = cursor.fetchone()
        return row[0] if row else None

    def inserir_facto(self, pub: dict) -> bool:
        """
        Insere uma publicação classificada na tabela de factos.
        Resolve as chaves estrangeiras para as dimensões automaticamente.
        """
        if not self.verificar_disponibilidade():
            return False
        try:
            import pyodbc
            conn   = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()

            # Verificar se já existe
            cursor.execute("SELECT 1 FROM factos_ameacas WHERE id_externo = ?",
                           pub.get("id_externo", ""))
            if cursor.fetchone():
                conn.close()
                return False  # já existe — não duplicar

            # Resolver dimensões
            id_cat  = self._obter_id_categoria(cursor, pub.get("categoria", "Normal"))
            id_plat = self._obter_id_plataforma(cursor, pub.get("plataforma", ""))
            id_prov = self._obter_id_provincia(cursor, pub.get("provincia", "Luanda"))
            id_temp = self._obter_id_tempo(cursor, pub.get("data", ""))

            # Inserir facto
            cursor.execute("""
                INSERT INTO factos_ameacas (
                    id_categoria, id_plataforma, id_provincia, id_tempo,
                    id_externo, id_anonimizado, texto_resumo,
                    categoria, confianca, alerta_emitido,
                    plataforma, provincia, data_publicacao,
                    data_classificacao, modelo_ia,
                    segundos_detecao, horas_antecedencia
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,GETDATE(),?,?,?)
            """,
                id_cat, id_plat, id_prov, id_temp,
                pub.get("id_externo", ""),
                pub.get("id_anonimizado", ""),
                str(pub.get("texto_processado", ""))[:200],
                pub.get("categoria", "Normal"),
                float(pub.get("confianca_bert", 0)),
                1 if pub.get("alerta_emitido") else 0,
                pub.get("plataforma", ""),
                pub.get("provincia", "Luanda"),
                pub.get("data", ""),
                "BERT-BERTimbau",
                pub.get("segundos_detecao"),
                pub.get("horas_antecedencia"),
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"SQL Server erro: {e}")
            return False

    def inserir_batch(self, publicacoes: list) -> int:
        """Insere um batch de publicações classificadas no Data Warehouse."""
        if not self.verificar_disponibilidade():
            logger.warning("SQL Server não disponível — a saltar escrita DW")
            return 0
        inseridos = sum(1 for p in publicacoes if self.inserir_facto(p))
        logger.info(f"SQL Server DW: {inseridos}/{len(publicacoes)} inseridos")
        return inseridos


# ═══════════════════════════════════════════════════════════════════════════════
# FACHADA — Armazenamento Dual (MongoDB + SQL Server)
# ═══════════════════════════════════════════════════════════════════════════════
class ArmazenamentoDual:
    """
    Fachada que coordena as escritas para ambas as bases de dados.

    Fluxo:
        publicações brutas  → MongoDB [publicacoes_brutas]
        publicações classif → MongoDB [publicacoes_classificadas]
                           → SQL Server [factos_ameacas] (modelo estrela)

    O SQL Server é opcional — se não estiver disponível no Windows 11,
    o sistema continua a funcionar apenas com MongoDB.
    """

    def __init__(self):
        self.mongo = MongoDBStorage()
        self.sql   = SQLServerStorage()

    def guardar_pipeline_completo(self, publicacoes_brutas: list,
                                   publicacoes_classificadas: list) -> dict:
        """
        Guarda o resultado completo de um ciclo OSINT nas duas bases de dados.

        Args:
            publicacoes_brutas:       saída dos scrapers OSINT
            publicacoes_classificadas: saída do classificador BERT

        Returns:
            dict com estatísticas de inserção
        """
        stats = {
            "mongo_brutas":        0,
            "mongo_classificadas": 0,
            "sql_dw":              0,
            "sql_disponivel":      False,
        }

        # 1. MongoDB — dados brutos
        stats["mongo_brutas"] = self.mongo.guardar_brutos(publicacoes_brutas)

        # 2. MongoDB — dados classificados
        stats["mongo_classificadas"] = self.mongo.guardar_classificadas(
            publicacoes_classificadas)

        # 3. SQL Server — Data Warehouse (apenas ameaças, não "Normal")
        ameacas = [p for p in publicacoes_classificadas
                   if p.get("categoria") != "Normal"]
        if self.sql.verificar_disponibilidade():
            stats["sql_disponivel"] = True
            stats["sql_dw"] = self.sql.inserir_batch(ameacas)
        else:
            logger.info(
                "SQL Server Express não disponível. "
                "Instalar em: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads"
            )

        logger.info(
            f"Armazenamento dual: "
            f"MongoDB brutos={stats['mongo_brutas']} | "
            f"MongoDB classif={stats['mongo_classificadas']} | "
            f"SQL DW={stats['sql_dw']}"
        )
        return stats

    def fechar(self):
        self.mongo.fechar()
