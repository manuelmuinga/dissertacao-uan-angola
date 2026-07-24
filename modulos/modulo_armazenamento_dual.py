"""
Módulo de Armazenamento Dual — MongoDB Atlas + SQL Server Express (Windows 11)
Dissertação UAN — Manuel Muinga 2026
"""
import os, logging
from datetime import datetime, timezone
import pymongo
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger("ArmazenamentoDual")
MONGODB_URI     = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
SQL_SERVER_CONN = os.getenv("SQL_SERVER_CONN",
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=AmeacasAngola_DW;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;")


class MongoDBStorage:
    """MongoDB Atlas — dados brutos OSINT e resultados BERT."""
    def __init__(self, uri=None):
        self.uri = uri or MONGODB_URI
        self._client = None

    def _col(self, nome):
        if not self._client:
            self._client = pymongo.MongoClient(self.uri, serverSelectionTimeoutMS=8000)
        return self._client["dissertacao_angola"][nome]

    def guardar_brutos(self, pubs):
        if not pubs: return 0
        col = self._col("publicacoes_brutas")
        n = sum(1 for p in pubs if col.update_one(
            {"id_externo": p["id_externo"]}, {"$setOnInsert": p}, upsert=True).upserted_id)
        logger.info(f"MongoDB [brutas]: {n}/{len(pubs)} inseridas")
        return n

    def guardar_classificadas(self, pubs):
        if not pubs: return 0
        col = self._col("publicacoes_classificadas")
        n = sum(1 for p in pubs if col.update_one(
            {"id_externo": p["id_externo"]}, {"$set": p}, upsert=True).upserted_id)
        logger.info(f"MongoDB [classificadas]: {n}/{len(pubs)} inseridas")
        return n

    def fechar(self):
        if self._client: self._client.close(); self._client = None


class SQLServerStorage:
    """
    SQL Server Express instalado localmente no Windows 11.
    Instalar: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads (Express)
    Script:   dados/criar_data_warehouse.sql
    ODBC:     https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server
    Ligacao Power BI: localhost\SQLEXPRESS -> AmeacasAngola_DW -> vw_ameacas_completo
    """
    def __init__(self, conn_str=None):
        self.conn_str = conn_str or SQL_SERVER_CONN
        self._ok = None

    def disponivel(self):
        if self._ok is not None: return self._ok
        try:
            import pyodbc
            c = pyodbc.connect(self.conn_str, timeout=5); c.close()
            self._ok = True
            logger.info("SQL Server Express: disponivel (Windows 11 local)")
        except ImportError:
            logger.warning("pyodbc nao instalado: pip install pyodbc"); self._ok = False
        except Exception as e:
            logger.warning(f"SQL Server nao disponivel: {e}"); self._ok = False
        return self._ok

    def inserir_batch(self, pubs):
        if not self.disponivel(): return 0
        try:
            import pyodbc
            conn   = pyodbc.connect(self.conn_str)
            cursor = conn.cursor()
            n = 0
            for p in pubs:
                try:
                    cursor.execute(
                        "SELECT 1 FROM factos_ameacas WHERE id_externo=?",
                        p.get("id_externo",""))
                    if cursor.fetchone(): continue
                    cursor.execute("""
                        INSERT INTO factos_ameacas
                        (id_externo,id_anonimizado,texto_resumo,categoria,
                         confianca,alerta_emitido,plataforma,provincia,
                         data_publicacao,data_classificacao,modelo_ia)
                        VALUES (?,?,?,?,?,?,?,?,?,GETDATE(),?)
                    """,
                        p.get("id_externo",""), p.get("id_anonimizado",""),
                        str(p.get("texto_processado",""))[:200],
                        p.get("categoria","Normal"),
                        float(p.get("confianca_bert",0)),
                        1 if p.get("alerta_emitido") else 0,
                        p.get("plataforma",""), p.get("provincia","Luanda"),
                        p.get("data",""), "BERT-BERTimbau")
                    n += 1
                except Exception: continue
            conn.commit(); conn.close()
            logger.info(f"SQL Server DW: {n}/{len(pubs)} inseridos")
            return n
        except Exception as e:
            logger.error(f"SQL Server erro: {e}"); return 0


class ArmazenamentoDual:
    """Fachada — escreve em MongoDB Atlas e SQL Server Express (Windows 11)."""
    def __init__(self):
        self.mongo = MongoDBStorage()
        self.sql   = SQLServerStorage()

    def guardar(self, brutos, classificadas):
        stats = {
            "mongo_brutos":       self.mongo.guardar_brutos(brutos),
            "mongo_classificadas":self.mongo.guardar_classificadas(classificadas),
            "sql_dw":             self.sql.inserir_batch(
                [p for p in classificadas if p.get("categoria") != "Normal"])
        }
        return stats

    def fechar(self): self.mongo.fechar()
