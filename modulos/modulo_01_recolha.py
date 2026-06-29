"""
=============================================================================
MÓDULO 1 — Recolha de Dados em Redes Sociais
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola
=============================================================================
Descrição:
    Módulo de recolha de dados das principais plataformas sociais presentes
    em Angola (Twitter/X, Facebook, Telegram, Web) via APIs oficiais e
    crawlers. Os dados são armazenados em MongoDB para processamento posterior.
=============================================================================
"""

import os
import time
import logging
import pymongo
import tweepy
import requests
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from telegram import Bot
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ─── Configuração ─────────────────────────────────────────────────────────────
TWITTER_BEARER_TOKEN  = os.getenv("TWITTER_BEARER_TOKEN")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
MONGODB_URI           = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Palavras-chave de monitoramento (glossário dinâmico — Angola)
PALAVRAS_CHAVE_ANGOLA = [
    # Termos de segurança e política
    "manifestação angola", "protesto angola", "golpe angola",
    "MPLA", "UNITA", "João Lourenço", "segurança angola",
    # Termos de desinformação
    "fake news angola", "mentira angola", "boato angola",
    # Termos de ódio e conflito
    "guerra angola", "violência angola", "ataque angola",
    # Línguas nacionais (Kimbundu/Kikongo — expressões comuns)
    "kota yetu", "mukanda", "nzambi",
    # Calão urbano de Luanda
    "ki bué", "tó fix", "pesado demais angola",
]

# Províncias angolanas para geofiltro
PROVINCIAS_ANGOLA = [
    "Luanda", "Benguela", "Huambo", "Bié", "Malanje",
    "Huíla", "Cabinda", "Cunene", "Namibe", "Zaire",
    "Uíge", "Kwanza Norte", "Kwanza Sul", "Lunda Norte",
    "Lunda Sul", "Moxico", "Cuando Cubango", "Bengo",
]

# ─── Ligação MongoDB ──────────────────────────────────────────────────────────
def get_db():
    client = pymongo.MongoClient(MONGODB_URI)
    return client["dissertacao_angola"]["publicacoes_brutas"]

# ─── 1.1 Recolha Twitter/X ───────────────────────────────────────────────────
def coletar_twitter(palavras_chave: list, max_resultados: int = 500) -> list:
    """
    Recolhe tweets recentes com base em palavras-chave via Twitter/X API v2.
    
    Args:
        palavras_chave: Lista de termos de pesquisa.
        max_resultados: Número máximo de tweets a recolher.
    
    Returns:
        Lista de dicionários com dados dos tweets.
    """
    if not TWITTER_BEARER_TOKEN:
        logger.warning("TWITTER_BEARER_TOKEN não configurado.")
        return []
    
    cliente = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
    consulta = " OR ".join(f'"{p}"' for p in palavras_chave[:5]) + " lang:pt -is:retweet"
    publicacoes = []
    
    try:
        for tweet in tweepy.Paginator(
            cliente.search_recent_tweets,
            query=consulta,
            tweet_fields=["created_at", "geo", "public_metrics", "author_id", "lang"],
            max_results=100
        ).flatten(max_resultados):
            publicacoes.append({
                "id_externo":  str(tweet.id),
                "texto":       tweet.text,
                "data":        str(tweet.created_at),
                "plataforma":  "twitter",
                "metricas":    tweet.public_metrics,
                "recolhido_em": datetime.now(timezone.utc).isoformat(),
                "classificado": False,
            })
        logger.info(f"Twitter: {len(publicacoes)} publicações recolhidas.")
    except Exception as e:
        logger.error(f"Erro Twitter: {e}")
    
    return publicacoes


# ─── 1.2 Recolha Facebook (Graph API) ────────────────────────────────────────
def coletar_facebook(paginas: list, max_posts: int = 100) -> list:
    """
    Recolhe publicações públicas de páginas Facebook via Graph API.
    
    Args:
        paginas: Lista de IDs ou nomes de páginas públicas.
        max_posts: Número máximo de posts por página.
    
    Returns:
        Lista de dicionários com dados dos posts.
    """
    if not FACEBOOK_ACCESS_TOKEN:
        logger.warning("FACEBOOK_ACCESS_TOKEN não configurado.")
        return []
    
    publicacoes = []
    base_url = "https://graph.facebook.com/v18.0"
    
    for pagina in paginas:
        try:
            url = f"{base_url}/{pagina}/posts"
            params = {
                "access_token": FACEBOOK_ACCESS_TOKEN,
                "fields": "id,message,created_time,story,shares,reactions.summary(true)",
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
    
    logger.info(f"Facebook: {len(publicacoes)} publicações recolhidas.")
    return publicacoes


# ─── 1.3 Recolha Telegram (canais públicos) ───────────────────────────────────
def coletar_telegram(canais: list, limite: int = 100) -> list:
    """
    Recolhe mensagens de canais públicos do Telegram via Bot API.
    
    Args:
        canais: Lista de usernames de canais públicos (ex: ["@canalAngola"]).
        limite: Número máximo de mensagens por canal.
    
    Returns:
        Lista de dicionários com dados das mensagens.
    """
    publicacoes = []
    
    for canal in canais:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            # Nota: para canais públicos use a API de forwarding ou a Bot API
            # O código completo com MTProto está no apêndice do repositório
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


# ─── 1.4 Crawler Web (blogues e sites angolanos) ─────────────────────────────
def crawl_web(urls: list) -> list:
    """
    Extrai texto de artigos de blogues e sites de notícias angolanos.
    
    Args:
        urls: Lista de URLs a processar.
    
    Returns:
        Lista de dicionários com dados dos artigos.
    """
    publicacoes = []
    headers = {"User-Agent": "Mozilla/5.0 (UAN Research Bot 2026)"}
    
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            # Extrai parágrafos principais
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
        time.sleep(1)  # respeitar robots.txt
    
    logger.info(f"Web: {len(publicacoes)} artigos recolhidos.")
    return publicacoes


# ─── 1.5 Armazenamento em MongoDB ────────────────────────────────────────────
def guardar_mongodb(publicacoes: list) -> int:
    """
    Insere publicações na coleção MongoDB, evitando duplicatas por id_externo.
    
    Returns:
        Número de documentos inseridos.
    """
    if not publicacoes:
        return 0
    
    colecao = get_db()
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


# ─── 1.6 Pipeline de Recolha Completo ────────────────────────────────────────
def pipeline_recolha(ciclo_minutos: int = 15) -> None:
    """
    Executa o pipeline de recolha em ciclos contínuos.
    
    Args:
        ciclo_minutos: Intervalo em minutos entre ciclos de recolha.
    """
    # Páginas Facebook angolanas de interesse público
    PAGINAS_FB = ["VerAngola", "JornalDeAngola.ao", "RNAangola"]
    
    # Canais Telegram públicos angolanos
    CANAIS_TG = ["@angola_news", "@luanda_hoje"]
    
    # Sites angolanos de referência
    URLS_WEB = [
        "https://www.angop.ao/",
        "https://www.verangola.net/va/",
    ]
    
    logger.info(f"Pipeline de recolha iniciado. Ciclo: {ciclo_minutos} minutos.")
    
    while True:
        try:
            total = 0
            total += guardar_mongodb(coletar_twitter(PALAVRAS_CHAVE_ANGOLA))
            total += guardar_mongodb(coletar_facebook(PAGINAS_FB))
            total += guardar_mongodb(coletar_telegram(CANAIS_TG))
            total += guardar_mongodb(crawl_web(URLS_WEB))
            logger.info(f"Ciclo concluído: {total} novas publicações guardadas.")
        except Exception as e:
            logger.error(f"Erro no ciclo de recolha: {e}")
        
        time.sleep(ciclo_minutos * 60)


if __name__ == "__main__":
    pipeline_recolha(ciclo_minutos=15)
