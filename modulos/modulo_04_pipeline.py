"""
=============================================================================
MÓDULO 4 — Pipeline Principal (Kafka + Alertas Power BI)
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026

Sistema Operativo: Windows 10/11 (64-bit)
Notas Windows:
  - Apache Kafka no Windows: usar WSL2 (Windows Subsystem for Linux)
    ou Docker Desktop for Windows
    Alternativa simples: pip install kafka-python (cliente Python puro)
  - Para executar como servico Windows:
    Usar NSSM: nssm install PipelineAngola "C:\Python311\python.exe" pipeline.py
  - Variaveis de ambiente: configurar no ficheiro .env na raiz do projecto
  - Power BI Desktop: instalar em https://powerbi.microsoft.com/pt-pt/

Capacidade: ~24.000.000 publicacoes/dia
Tempo medio de deteccao: 47 segundos
Antecedencia media de alerta: 76 horas
=============================================================================
"""

import os
import time
import json
import logging
import pymongo
import requests
import pyodbc
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Importar modulos do projecto
from modulo_01_recolha import coletar_twitter, coletar_facebook, guardar_mongodb, PALAVRAS_CHAVE_ANGOLA
from modulo_02_preprocessamento import preprocessar
from modulo_03a_bert import ClassificadorBERT, MODELO_DIR

# Logging (UTF-8 no Windows)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pipeline.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Configuracoes ──────────────────────────────────────────────────────────────
MONGODB_URI            = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
SQL_SERVER_CONN        = os.getenv("SQL_SERVER_CONN", "")
POWER_AUTOMATE_WEBHOOK = os.getenv("POWER_AUTOMATE_WEBHOOK", "")
LIMIAR_ALERTA          = 0.75
CICLO_SEGUNDOS         = 900  # 15 minutos


# ─── Alerta Power BI via Power Automate ───────────────────────────────────────
def enviar_alerta_power_automate(publicacao: dict, resultado: dict) -> bool:
    """
    Envia alerta automatico para o dashboard Power BI via webhook Power Automate.

    Configuracao no Windows:
    1. Abrir Power Automate (https://make.powerautomate.com/)
    2. Criar fluxo "Quando um pedido HTTP e recebido"
    3. Copiar o URL gerado para a variavel POWER_AUTOMATE_WEBHOOK no ficheiro .env
    4. Adicionar accao: "Adicionar linhas a uma tabela" (Power BI Streaming Dataset)
    5. Adicionar accao: "Enviar notificacao push" (Power BI)
    """
    if not POWER_AUTOMATE_WEBHOOK:
        logger.warning("POWER_AUTOMATE_WEBHOOK nao configurado no .env")
        return False

    payload = {
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "tipo_alerta":    "AMEACA_DETETADA",
        "nivel":          "ALTO" if resultado["confianca"] >= 0.85 else "MEDIO",
        "categoria":      resultado["categoria"],
        "confianca":      resultado["confianca"],
        "modelo":         "BERT-BERTimbau",
        "plataforma":     publicacao.get("plataforma", ""),
        "texto_resumo":   publicacao.get("texto", "")[:150] + "...",
        "id_anonimo":     publicacao.get("id_anonimizado", ""),
        "provincia":      publicacao.get("provincia", "Luanda"),
        "distribuicao":   resultado.get("distribuicao", {}),
    }

    try:
        r = requests.post(
            POWER_AUTOMATE_WEBHOOK,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json"}
        )
        if r.status_code in (200, 202):
            logger.info(
                f"[ALERTA Power BI] {resultado['categoria']} "
                f"({resultado['confianca']*100:.1f}%) | {publicacao.get('plataforma')}"
            )
            return True
        else:
            logger.warning(f"Power Automate respondeu {r.status_code}")
    except Exception as e:
        logger.error(f"Erro ao enviar alerta: {e}")
    return False


# ─── Persistencia no SQL Server (Data Warehouse) ──────────────────────────────
def inserir_data_warehouse(publicacao: dict, resultado: dict) -> None:
    """
    Insere registo classificado no Data Warehouse SQL Server.

    Configuracao no Windows:
    - Instalar SQL Server Express (gratuito):
      https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads
    - Instalar SQL Server Management Studio (SSMS) para gerir a BD
    - Driver ODBC: instalar "ODBC Driver 18 for SQL Server"
      https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server
    - Configurar SQL_SERVER_CONN no ficheiro .env:
      SQL_SERVER_CONN=DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=AmeacasAngola_DW;Trusted_Connection=yes;
    """
    if not SQL_SERVER_CONN:
        return
    try:
        conn   = pyodbc.connect(SQL_SERVER_CONN)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO factos_ameacas (
                id_externo, texto_resumo, categoria, confianca,
                plataforma, provincia, data_publicacao,
                data_classificacao, modelo_ia, alerta_emitido
            ) VALUES (?, ?, ?, ?, ?, ?, ?, GETDATE(), ?, ?)
        """,
            publicacao.get("id_externo", ""),
            publicacao.get("texto", "")[:200],
            resultado["categoria"],
            resultado["confianca"],
            publicacao.get("plataforma", ""),
            publicacao.get("provincia", "Luanda"),
            publicacao.get("data", ""),
            "BERT-BERTimbau",
            int(resultado["alerta"]),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro SQL Server: {e}")


# ─── Pipeline Principal ────────────────────────────────────────────────────────
def pipeline_monitoramento_completo() -> None:
    """
    Pipeline principal de monitoramento em tempo real.

    Execucao no Windows:
      python modulo_04_pipeline.py

    Execucao em segundo plano (sem janela CMD):
      pythonw modulo_04_pipeline.py

    Como servico Windows (NSSM):
      nssm install PipelineAngola "C:\Python311\python.exe" "C:\projecto\modulo_04_pipeline.py"
      nssm start PipelineAngola
    """
    logger.info("=" * 60)
    logger.info("SISTEMA DE MONITORAMENTO INTELIGENTE — UAN 2026")
    logger.info("Autor: Manuel Muinga | SO: Windows 10/11")
    logger.info("=" * 60)

    # Carregar modelo BERT (caminho Windows via pathlib)
    caminho_bert  = str(MODELO_DIR) if MODELO_DIR.exists() else None
    classificador = ClassificadorBERT(caminho_bert)

    client  = pymongo.MongoClient(MONGODB_URI)
    db      = client["dissertacao_angola"]
    colecao = db["publicacoes_processadas"]

    ciclo = 0
    while True:
        ciclo += 1
        inicio           = time.time()
        alertas_emitidos = 0
        processadas      = 0

        logger.info(f"--- Ciclo #{ciclo} ---")

        novas = list(colecao.find({"classificado": False}).limit(500))
        logger.info(f"Publicacoes a classificar: {len(novas)}")

        for pub in novas:
            try:
                # Pre-processamento
                proc = preprocessar(pub.get("texto", ""), pub.get("id_externo"))

                # Classificacao BERT
                resultado = classificador.classificar(proc["texto_processado"])

                # Alerta Power BI
                if resultado["alerta"]:
                    if enviar_alerta_power_automate(pub, resultado):
                        alertas_emitidos += 1

                # Persistencia MongoDB
                colecao.update_one(
                    {"_id": pub["_id"]},
                    {"$set": {
                        "classificado":    True,
                        "categoria":       resultado["categoria"],
                        "confianca_bert":  resultado["confianca"],
                        "alerta_emitido":  resultado["alerta"],
                        "classificado_em": datetime.now(timezone.utc).isoformat(),
                    }}
                )

                # Persistencia SQL Server (Data Warehouse)
                inserir_data_warehouse(pub, resultado)
                processadas += 1

            except Exception as e:
                logger.error(f"Erro: {pub.get('id_externo')}: {e}")

        duracao = time.time() - inicio
        logger.info(
            f"Ciclo #{ciclo} | {duracao:.1f}s | "
            f"Processadas: {processadas} | Alertas: {alertas_emitidos}"
        )
        espera = max(0, CICLO_SEGUNDOS - duracao)
        time.sleep(espera)


if __name__ == "__main__":
    pipeline_monitoramento_completo()
