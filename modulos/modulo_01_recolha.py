"""
=============================================================================
MÓDULO 1 — Recolha de Dados em Redes Sociais
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola

Sistema Operativo: Windows 10/11 (64-bit)
Python: 3.11 (recomendado via Anaconda ou Python.org)
Execução: python modulo_01_recolha.py
=============================================================================
"""

import os
import time
import json
import logging
import pymongo
import tweepy
import requests
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Carregar variáveis de ambiente do ficheiro .env
# No Windows: criar ficheiro .env na raiz do projecto com as chaves API
load_dotenv()

# ─── Logging (compatível com Windows — sem caracteres especiais no path) ───────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "recolha.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Configuração (variáveis de ambiente — ficheiro .env) ─────────────────────
TWITTER_BEARER_TOKEN  = os.getenv("TWITTER_BEARER_TOKEN", "")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN", "")
MONGODB_URI           = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Palavras-chave de monitoramento (glossário dinâmico — Angola)
PALAVRAS_CHAVE_ANGOLA = [
    "manifestação angola", "protesto angola", "golpe angola",
    "MPLA", "UNITA", "João Lourenço", "segurança angola",
    "fake news angola", "mentira angola", "boato angola",
    "guerra angola", "violência angola", "ataque angola",
    "ki bué", "tó fix", "pesado demais angola",
    "kota yetu", "mukanda", "nzambi",
]

PROVINCIAS_ANGOLA = [
    "Luanda", "Benguela", "Huambo", "Bié", "Malanje",
    "Huíla", "Cabinda", "Cunene", "Namibe", "Zaire",
    "Uíge", "Kwanza Norte", "Kwanza Sul", "Lunda Norte",
    "Lunda Sul", "Moxico", "Cuando Cubango", "Bengo",
]

# ─── Ligação MongoDB ──────────────────────────────────────────────────────────
def get_colecao():
    """
    Retorna a coleção MongoDB.
    No Windows: garantir que o serviço MongoDB está em execução:
      Serviços > MongoDB Server > Iniciar
      ou: net start MongoDB (Linha de Comandos como Administrador)
    """
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    return client["dissertacao_angola"]["publicacoes_brutas"]


# ─── 1.1 Recolha Twitter/X ───────────────────────────────────────────────────
def coletar_twitter(palavras_chave: list, max_resultados: int = 500) -> list:
    """Recolhe tweets recentes com base em palavras-chave via Twitter/X API v2."""
    if not TWITTER_BEARER_TOKEN:
        logger.warning("TWITTER_BEARER_TOKEN nao configurado no ficheiro .env")
        return []

    cliente = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
    consulta = " OR ".join(f'"{p}"' for p in palavras_chave[:5]) + " lang:pt -is:retweet"
    publicacoes = []

    try:
        for tweet in tweepy.Paginator(
            cliente.search_recent_tweets,
            query=consulta,
            tweet_fields=["created_at", "geo", "public_metrics", "author_id"],
            max_results=100
        ).flatten(max_resultados):
            publicacoes.append({
                "id_externo":   str(tweet.id),
                "texto":        tweet.text,
                "data":         str(tweet.created_at),
                "plataforma":   "twitter",
                "metricas":     tweet.public_metrics,
                "recolhido_em": datetime.now(timezone.utc).isoformat(),
                "classificado": False,
            })
        logger.info(f"Twitter: {len(publicacoes)} publicacoes recolhidas.")
    except Exception as e:
        logger.error(f"Erro Twitter: {e}")

    return publicacoes


# ─── 1.2 Recolha Facebook (Graph API) ────────────────────────────────────────
def coletar_facebook(paginas: list, max_posts: int = 100) -> list:
    """Recolhe publicações públicas de páginas Facebook via Graph API."""
    if not FACEBOOK_ACCESS_TOKEN:
        logger.warning("FACEBOOK_ACCESS_TOKEN nao configurado no ficheiro .env")
        return []

    publicacoes = []
    base_url = "https://graph.facebook.com/v18.0"

    for pagina in paginas:
        try:
            url = f"{base_url}/{pagina}/posts"
            params = {
                "access_token": FACEBOOK_ACCESS_TOKEN,
                "fields": "id,message,created_time,shares,reactions.summary(true)",
                "limit": max_posts,
            }
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                for post in r.json().get("data", []):
                    if post.get("message"):
                        publicacoes.append({
                            "id_externo":   post["id"],
                            "texto":        post["message"],
                            "data":         post.get("created_time", ""),
                            "plataforma":   "facebook",
                            "pagina":       pagina,
                            "reacoes":      post.get("reactions", {}).get("summary", {}).get("total_count", 0),
                            "recolhido_em": datetime.now(timezone.utc).isoformat(),
                            "classificado": False,
                        })
        except Exception as e:
            logger.error(f"Erro Facebook ({pagina}): {e}")

    logger.info(f"Facebook: {len(publicacoes)} publicacoes recolhidas.")
    return publicacoes


# ─── 1.3 Recolha Telegram ─────────────────────────────────────────────────────
def coletar_telegram(canais: list, limite: int = 100) -> list:
    """Recolhe mensagens de canais públicos do Telegram via Bot API."""
    publicacoes = []

    for canal in canais:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                for update in r.json().get("result", [])[:limite]:
                    msg = update.get("channel_post", {})
                    if msg.get("text"):
                        publicacoes.append({
                            "id_externo":   str(msg.get("message_id", "")),
                            "texto":        msg["text"],
                            "data":         str(datetime.fromtimestamp(msg.get("date", 0))),
                            "plataforma":   "telegram",
                            "canal":        canal,
                            "recolhido_em": datetime.now(timezone.utc).isoformat(),
                            "classificado": False,
                        })
        except Exception as e:
            logger.error(f"Erro Telegram ({canal}): {e}")

    logger.info(f"Telegram: {len(publicacoes)} mensagens recolhidas.")
    return publicacoes


# ─── 1.4 Crawler Web ──────────────────────────────────────────────────────────
def crawl_web(urls: list) -> list:
    """Extrai texto de artigos de blogues e sites de notícias angolanos."""
    publicacoes = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) UAN-Research-Bot/2026"}

    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.encoding = "utf-8"
            soup = BeautifulSoup(r.text, "html.parser")
            paragrafos = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text()) > 80]
            texto = " ".join(paragrafos[:10])
            if texto:
                publicacoes.append({
                    "id_externo":   url,
                    "texto":        texto[:2000],
                    "data":         datetime.now(timezone.utc).isoformat(),
                    "plataforma":   "web",
                    "url":          url,
                    "recolhido_em": datetime.now(timezone.utc).isoformat(),
                    "classificado": False,
                })
        except Exception as e:
            logger.error(f"Erro Web ({url}): {e}")
        time.sleep(1)

    logger.info(f"Web: {len(publicacoes)} artigos recolhidos.")
    return publicacoes


# ─── 1.5 Armazenamento em MongoDB ────────────────────────────────────────────
def guardar_mongodb(publicacoes: list) -> int:
    """Insere publicações no MongoDB, evitando duplicatas por id_externo."""
    if not publicacoes:
        return 0
    colecao = get_colecao()
    inseridos = 0
    for pub in publicacoes:
        resultado = colecao.update_one(
            {"id_externo": pub["id_externo"]},
            {"$setOnInsert": pub},
            upsert=True
        )
        if resultado.upserted_id:
            inseridos += 1
    logger.info(f"MongoDB: {inseridos} novos documentos inseridos.")
    return inseridos


# ─── 1.6 Pipeline Principal ───────────────────────────────────────────────────
def pipeline_recolha(ciclo_minutos: int = 15) -> None:
    """
    Executa o pipeline de recolha em ciclos contínuos.

    No Windows, para executar em segundo plano:
      pythonw modulo_01_recolha.py
    Ou como serviço Windows (usar NSSM — Non-Sucking Service Manager):
      nssm install MonitoramentoAngola python modulo_01_recolha.py
    """
    PAGINAS_FB = ["VerAngola", "JornalDeAngola.ao", "RNAangola"]
    CANAIS_TG  = ["@angola_news", "@luanda_hoje"]
    URLS_WEB   = [
        "https://www.angop.ao/",
        "https://www.verangola.net/va/",
    ]

    logger.info("Pipeline de recolha iniciado. SO: Windows 10/11")
    logger.info(f"Ciclo: {ciclo_minutos} minutos | MongoDB: {MONGODB_URI}")

    ciclo = 0
    while True:
        ciclo += 1
        logger.info(f"--- Ciclo #{ciclo} ---")
        try:
            total = 0
            total += guardar_mongodb(coletar_twitter(PALAVRAS_CHAVE_ANGOLA))
            total += guardar_mongodb(coletar_facebook(PAGINAS_FB))
            total += guardar_mongodb(coletar_telegram(CANAIS_TG))
            total += guardar_mongodb(crawl_web(URLS_WEB))
            logger.info(f"Ciclo #{ciclo} concluido: {total} novas publicacoes.")
        except Exception as e:
            logger.error(f"Erro no ciclo #{ciclo}: {e}")
        time.sleep(ciclo_minutos * 60)


if __name__ == "__main__":
    pipeline_recolha(ciclo_minutos=15)
