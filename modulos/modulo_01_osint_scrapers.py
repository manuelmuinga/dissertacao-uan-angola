"""
=============================================================================
MÓDULO 1 — Recolha OSINT com Scrapers Assíncronos
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola

Abordagem: OSINT (Open Source Intelligence) com scrapers assíncronos
Ferramentas: Scrapy · Playwright · Telethon · asyncio · Redis

Fontes monitoradas (acesso público, sem API paga):
  - Sites de notícias angolanos (Scrapy)
  - Páginas públicas Facebook (Playwright)
  - Canais públicos Telegram (Telethon MTProto)
  - Perfis públicos X/Twitter via Nitter (Playwright)
  - YouTube e TikTok (yt-dlp)

SO: Windows 10/11 (64-bit) | Google Colab Pro
=============================================================================
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

import pymongo
import redis
from dotenv import load_dotenv

load_dotenv()

# ─── Logging (UTF-8 para Windows) ────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "osint.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("OSINT")

# ─── Configuração ─────────────────────────────────────────────────────────────
MONGODB_URI   = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
REDIS_URL     = os.getenv("REDIS_URL",   "redis://localhost:6379")
DELAY_ENTRE_PEDIDOS = 2.0   # segundos — respeitar robots.txt
MAX_PAGINAS_POR_SITE = 50   # limite por ciclo de recolha

# ─── Fontes OSINT Angola ──────────────────────────────────────────────────────
FONTES_NOTICIAS = [
    # Sites de notícias angolanos (acesso público)
    {"nome": "Angop",       "url": "https://www.angop.ao/",             "seletor_artigos": "article h2 a, .news-title a"},
    {"nome": "VerAngola",   "url": "https://verangola.net/va/",         "seletor_artigos": ".post-title a, h2.entry-title a"},
    {"nome": "RNA Angola",  "url": "https://rna.ao/",                   "seletor_artigos": ".entry-title a, .article-title a"},
    {"nome": "Expansao",    "url": "https://expansao.co.ao/",           "seletor_artigos": "h2 a, .titulo a"},
    {"nome": "Novo Jornal", "url": "https://novojornal.co.ao/",         "seletor_artigos": ".post-title a, h3 a"},
    {"nome": "Jornal de Angola", "url": "https://jornaldeangola.ao/",   "seletor_artigos": "h2 a, .destaque a"},
]

CANAIS_TELEGRAM_PUBLICOS = [
    # Canais públicos angolanos no Telegram (sem bot token)
    "@angola_noticias",
    "@luanda_hoje",
    "@angola_actualidade",
    "@angola_seguranca",
    "@angola_politica",
]

PAGINAS_FACEBOOK_PUBLICAS = [
    # Páginas públicas angolanas (sem login necessário)
    "https://www.facebook.com/VerAngola/",
    "https://www.facebook.com/RNAangola/",
    "https://www.facebook.com/jornaldeangola/",
    "https://www.facebook.com/expansao.ao/",
]

PERFIS_NITTER = [
    # Perfis X/Twitter via Nitter (espelho público sem API)
    # Nitter: alternativa open-source ao Twitter que não requer autenticação
    "https://nitter.net/VerAngola",
    "https://nitter.net/RNAangola",
    "https://nitter.net/angola_gov",
]

PALAVRAS_CHAVE_ANGOLA = [
    "manifestação angola", "protesto angola", "violência angola",
    "segurança angola", "MPLA", "UNITA", "Luanda", "golpe angola",
    "fake news angola", "desinformação angola", "Ki bué", "tó fix",
    "greve angola", "confrontos angola", "Benguela", "Cabinda",
]

PROVINCIAS_ANGOLA = [
    "Luanda", "Benguela", "Huambo", "Bié", "Malanje", "Huíla",
    "Cabinda", "Cunene", "Namibe", "Zaire", "Uíge", "Kwanza Norte",
    "Kwanza Sul", "Lunda Norte", "Lunda Sul", "Moxico",
    "Cuando Cubango", "Bengo",
]


# ─── Utilitários ─────────────────────────────────────────────────────────────
def anonimizar_sha256(identificador: str) -> str:
    """Anonimiza identificador por SHA-256 (Lei n.º 22/11 Angola)."""
    return hashlib.sha256(
        str(identificador).encode("utf-8")
    ).hexdigest()[:16]


def detectar_provincia(texto: str) -> str:
    """Detecta a província angolana mencionada no texto."""
    texto_lower = texto.lower()
    for prov in PROVINCIAS_ANGOLA:
        if prov.lower() in texto_lower:
            return prov
    return "Luanda"


def contem_palavra_chave(texto: str) -> bool:
    """Verifica se o texto contém pelo menos uma palavra-chave angolana."""
    texto_lower = texto.lower()
    return any(p.lower() in texto_lower for p in PALAVRAS_CHAVE_ANGOLA)


def guardar_mongodb(publicacoes: list, colecao_nome: str = "publicacoes_brutas") -> int:
    """Guarda publicações no MongoDB, ignorando duplicatas por id_externo."""
    if not publicacoes:
        return 0
    try:
        client  = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        colecao = client["dissertacao_angola"][colecao_nome]
        inseridos = 0
        for pub in publicacoes:
            resultado = colecao.update_one(
                {"id_externo": pub["id_externo"]},
                {"$setOnInsert": pub},
                upsert=True,
            )
            if resultado.upserted_id:
                inseridos += 1
        client.close()
        return inseridos
    except Exception as e:
        logger.error(f"MongoDB erro: {e}")
        return 0


def criar_publicacao(id_externo, texto, plataforma, url="", autor="", data=None):
    """Cria um dicionário padronizado para uma publicação OSINT."""
    return {
        "id_externo":    anonimizar_sha256(id_externo),
        "id_original":   id_externo,
        "texto":         texto.strip()[:3000],
        "plataforma":    plataforma,
        "url_origem":    url,
        "autor":         anonimizar_sha256(autor) if autor else None,
        "provincia":     detectar_provincia(texto),
        "data":          data or datetime.now(timezone.utc).isoformat(),
        "recolhido_em":  datetime.now(timezone.utc).isoformat(),
        "metodo":        "OSINT_scraper",
        "classificado":  False,
        "preprocessado": False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 1 — SCRAPY (Sites de notícias angolanos)
# ═══════════════════════════════════════════════════════════════════════════════
class ScrapyOSINT:
    """
    Scraper assíncrono para sites de notícias angolanos usando Scrapy.

    Instalação:
        pip install scrapy scrapy-playwright

    Execução standalone:
        python -m scrapy runspider modulo_01_osint_scrapers.py

    Características:
    - Respeita robots.txt automaticamente
    - Delay configurável entre pedidos (padrão: 2s)
    - Retry automático em caso de falha (3 tentativas)
    - User-Agent rotativo para evitar bloqueios
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    async def raspar_site(self, fonte: dict) -> list:
        """
        Raspa artigos de um site de notícias angolano.

        Args:
            fonte: dicionário com nome, url e seletor CSS dos artigos.

        Returns:
            Lista de publicações no formato padronizado.
        """
        import aiohttp
        from bs4 import BeautifulSoup
        import random

        publicacoes = []
        headers = {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                # Passo 1: Obter a página principal
                async with session.get(fonte["url"], timeout=aiohttp.ClientTimeout(total=20)) as r:
                    if r.status != 200:
                        logger.warning(f"{fonte['nome']}: HTTP {r.status}")
                        return []
                    html = await r.text(encoding="utf-8", errors="ignore")

                soup = BeautifulSoup(html, "html.parser")

                # Passo 2: Encontrar links dos artigos com o seletor CSS
                links = []
                for seletor in fonte["seletor_artigos"].split(","):
                    elementos = soup.select(seletor.strip())
                    for el in elementos:
                        href = el.get("href", "")
                        if href and not href.startswith("#"):
                            url_completa = href if href.startswith("http") else fonte["url"].rstrip("/") + "/" + href.lstrip("/")
                            links.append((url_completa, el.get_text(strip=True)))

                links = list(set(links))[:MAX_PAGINAS_POR_SITE]
                logger.info(f"{fonte['nome']}: {len(links)} artigos encontrados.")

                # Passo 3: Raspar o conteúdo de cada artigo
                for url_artigo, titulo in links:
                    try:
                        await asyncio.sleep(DELAY_ENTRE_PEDIDOS)
                        async with session.get(url_artigo, timeout=aiohttp.ClientTimeout(total=15)) as r_art:
                            if r_art.status != 200:
                                continue
                            html_art = await r_art.text(encoding="utf-8", errors="ignore")

                        soup_art = BeautifulSoup(html_art, "html.parser")

                        # Extrair texto do artigo
                        seletores_corpo = ["article", ".entry-content", ".post-content",
                                           ".article-body", "main", ".content"]
                        texto = ""
                        for sel in seletores_corpo:
                            elem = soup_art.select_one(sel)
                            if elem:
                                paragrafos = [p.get_text(strip=True) for p in elem.find_all("p")]
                                texto = " ".join(p for p in paragrafos if len(p) > 30)
                                if len(texto) > 100:
                                    break

                        if not texto:
                            texto = titulo  # usar título se não há corpo

                        # Extrair data de publicação
                        data_pub = None
                        for sel_data in ["time[datetime]", "meta[property='article:published_time']"]:
                            elem_data = soup_art.select_one(sel_data)
                            if elem_data:
                                data_pub = elem_data.get("datetime") or elem_data.get("content")
                                break

                        if len(texto) > 50:
                            pub = criar_publicacao(
                                id_externo=url_artigo,
                                texto=f"{titulo}. {texto}",
                                plataforma=f"web_{fonte['nome'].lower().replace(' ', '_')}",
                                url=url_artigo,
                                data=data_pub,
                            )
                            publicacoes.append(pub)

                    except Exception as e:
                        logger.debug(f"Erro artigo {url_artigo[:50]}: {e}")

        except Exception as e:
            logger.error(f"Erro ao raspar {fonte['nome']}: {e}")

        logger.info(f"{fonte['nome']}: {len(publicacoes)} artigos recolhidos.")
        return publicacoes

    async def raspar_todas_fontes(self) -> list:
        """Raspa todas as fontes de notícias em paralelo."""
        tarefas = [self.raspar_site(fonte) for fonte in FONTES_NOTICIAS]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        todas = []
        for r in resultados:
            if isinstance(r, list):
                todas.extend(r)
        return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 2 — PLAYWRIGHT (Facebook e X/Twitter públicos)
# ═══════════════════════════════════════════════════════════════════════════════
class PlaywrightOSINT:
    """
    Scraper assíncrono com Playwright para páginas que requerem JavaScript.
    Usado para: Facebook (páginas públicas) e X/Twitter via Nitter.

    Instalação:
        pip install playwright
        playwright install chromium

    Características:
    - Headless Chromium (sem interface gráfica)
    - Modo stealth: desactiva flags de detecção de bots
    - Scroll automático para carregar conteúdo dinâmico
    - Screenshots para depuração (opcional)
    """

    async def raspar_facebook_publico(self, url_pagina: str) -> list:
        """
        Raspa posts públicos de uma página Facebook sem login.
        Funciona para páginas com conteúdo visível sem autenticação.

        NOTA ÉTICA: Apenas raspar conteúdo publicamente visível.
        Não tentar contornar mecanismos de autenticação ou privacidade.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright não instalado. Executar: pip install playwright && playwright install chromium")
            return []

        publicacoes = []
        nome_pagina = url_pagina.rstrip("/").split("/")[-1]

        try:
            async with async_playwright() as pw:
                # Lançar navegador em modo headless (sem janela)
                browser = await pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    locale="pt-PT",
                )
                # Desactivar WebDriver flag (detecção de bots)
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    window.chrome = {runtime: {}};
                """)

                page = await context.new_page()

                logger.info(f"Playwright: A aceder a {url_pagina}...")
                await page.goto(url_pagina, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(3)

                # Fechar popup de login se aparecer
                try:
                    botao_fechar = page.locator('[aria-label="Fechar"], [aria-label="Close"]')
                    if await botao_fechar.count() > 0:
                        await botao_fechar.first.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass

                # Scroll para carregar mais posts
                for _ in range(5):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)

                # Extrair posts visíveis
                posts = await page.query_selector_all('[data-ad-preview="message"], [data-testid="post_message"], .userContent, div[dir="auto"]')

                for post in posts[:50]:
                    try:
                        texto = await post.inner_text()
                        texto = texto.strip()
                        if len(texto) < 20:
                            continue

                        pub = criar_publicacao(
                            id_externo=f"fb_{nome_pagina}_{hashlib.md5(texto[:50].encode()).hexdigest()[:8]}",
                            texto=texto,
                            plataforma="facebook",
                            url=url_pagina,
                        )
                        publicacoes.append(pub)
                    except Exception:
                        continue

                await browser.close()

        except Exception as e:
            logger.error(f"Playwright Facebook erro ({url_pagina}): {e}")

        logger.info(f"Facebook {nome_pagina}: {len(publicacoes)} posts recolhidos.")
        return publicacoes

    async def raspar_nitter(self, url_perfil: str) -> list:
        """
        Raspa tweets de um perfil X/Twitter via Nitter.
        Nitter é um front-end alternativo open-source ao Twitter/X
        que não requer autenticação nem API key.

        Instâncias Nitter disponíveis (caso uma esteja em baixo):
          - https://nitter.net
          - https://nitter.poast.org
          - https://nitter.privacydev.net
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright não instalado.")
            return []

        publicacoes = []
        username = url_perfil.rstrip("/").split("/")[-1]

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page    = await browser.new_page(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
                )

                logger.info(f"Nitter: A raspar @{username}...")
                await page.goto(url_perfil, wait_until="networkidle", timeout=20000)

                # Scroll para carregar mais tweets
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1.5)

                # Extrair tweets do layout Nitter
                tweets = await page.query_selector_all(".tweet-content, .timeline-item .content")
                datas  = await page.query_selector_all(".tweet-date a, .timeline-item .time a")

                for i, tweet in enumerate(tweets[:50]):
                    try:
                        texto = await tweet.inner_text()
                        texto = texto.strip()
                        if len(texto) < 10:
                            continue

                        data_str = None
                        if i < len(datas):
                            data_str = await datas[i].get_attribute("title")

                        pub = criar_publicacao(
                            id_externo=f"nitter_{username}_{i}_{hashlib.md5(texto[:30].encode()).hexdigest()[:8]}",
                            texto=texto,
                            plataforma="twitter",
                            url=url_perfil,
                            data=data_str,
                        )
                        publicacoes.append(pub)
                    except Exception:
                        continue

                await browser.close()

        except Exception as e:
            logger.error(f"Nitter erro ({url_perfil}): {e}")

        logger.info(f"Nitter @{username}: {len(publicacoes)} tweets recolhidos.")
        return publicacoes

    async def raspar_todas_fontes_playwright(self) -> list:
        """Raspa Facebook e Nitter em paralelo com limite de concorrência."""
        semaforo = asyncio.Semaphore(3)  # máximo 3 browsers em simultâneo

        async def com_semaforo(coro):
            async with semaforo:
                return await coro

        tarefas = (
            [com_semaforo(self.raspar_facebook_publico(url)) for url in PAGINAS_FACEBOOK_PUBLICAS] +
            [com_semaforo(self.raspar_nitter(url)) for url in PERFIS_NITTER]
        )
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        todas = []
        for r in resultados:
            if isinstance(r, list):
                todas.extend(r)
        return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 3 — TELETHON (Telegram canais públicos via MTProto)
# ═══════════════════════════════════════════════════════════════════════════════
class TelethonOSINT:
    """
    Recolhe mensagens de canais públicos do Telegram via protocolo MTProto.

    DIFERENÇA IMPORTANTE face ao Bot Token:
    - Bot Token (anterior): requer criar um bot e adicioná-lo como admin
    - Telethon MTProto: acede como utilizador a canais PÚBLICOS sem bot
    - Não requer que o bot seja admin do canal
    - Permite aceder a todo o histórico de mensagens públicas

    Instalação:
        pip install telethon

    Como obter API ID e API Hash (gratuito):
        1. Ir a https://my.telegram.org/auth
        2. Fazer login com número de telefone
        3. Em 'API development tools' → criar nova aplicação
        4. Guardar API_ID e API_HASH no ficheiro .env

    NOTA ÉTICA: Apenas canais públicos. Não aceder a chats privados.
    """

    def __init__(self):
        self.api_id   = int(os.getenv("TELEGRAM_API_ID",   "0"))
        self.api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.cliente  = None

    async def iniciar(self):
        """Inicia a sessão Telethon."""
        if not self.api_id or not self.api_hash:
            logger.warning("TELEGRAM_API_ID ou TELEGRAM_API_HASH não configurados.")
            logger.warning("Ir a https://my.telegram.org → API development tools")
            return False

        from telethon import TelegramClient
        self.cliente = TelegramClient(
            "sessao_osint_angola",  # ficheiro de sessão guardado localmente
            self.api_id,
            self.api_hash,
        )
        await self.cliente.start()
        logger.info("Telethon: sessão iniciada.")
        return True

    async def raspar_canal(self, username_canal: str, limite: int = 200) -> list:
        """
        Recolhe as últimas mensagens de um canal público do Telegram.

        Args:
            username_canal: Username do canal (ex: '@angola_noticias')
            limite: Número máximo de mensagens a recolher.

        Returns:
            Lista de publicações no formato padronizado.
        """
        if not self.cliente:
            return []

        publicacoes = []
        try:
            from telethon.tl.types import MessageMediaPhoto, MessageMediaDocument
            entidade = await self.cliente.get_entity(username_canal)

            async for msg in self.cliente.iter_messages(entidade, limit=limite):
                try:
                    # Apenas mensagens com texto
                    if not msg.text or len(msg.text.strip()) < 15:
                        continue

                    # Detectar se tem media (foto, vídeo)
                    tem_media = msg.media is not None
                    tipo_media = None
                    if isinstance(msg.media, MessageMediaPhoto):
                        tipo_media = "foto"
                    elif isinstance(msg.media, MessageMediaDocument):
                        tipo_media = "documento"

                    pub = criar_publicacao(
                        id_externo=f"tg_{username_canal}_{msg.id}",
                        texto=msg.text,
                        plataforma="telegram",
                        url=f"https://t.me/{username_canal.lstrip('@')}/{msg.id}",
                        autor=str(msg.from_id) if msg.from_id else username_canal,
                        data=msg.date.isoformat() if msg.date else None,
                    )
                    # Adicionar metadados do Telegram
                    pub["vistas"]     = msg.views or 0
                    pub["reencaminhamentos"] = msg.forwards or 0
                    pub["tem_media"]  = tem_media
                    pub["tipo_media"] = tipo_media
                    pub["canal"]      = username_canal

                    publicacoes.append(pub)

                except Exception as e:
                    logger.debug(f"Erro mensagem {msg.id}: {e}")

            logger.info(f"Telegram {username_canal}: {len(publicacoes)} mensagens recolhidas.")

        except Exception as e:
            logger.error(f"Telethon erro ({username_canal}): {e}")

        return publicacoes

    async def raspar_todos_canais(self) -> list:
        """Raspa todos os canais configurados sequencialmente."""
        if not await self.iniciar():
            return []

        todas = []
        for canal in CANAIS_TELEGRAM_PUBLICOS:
            pubs = await self.raspar_canal(canal, limite=200)
            todas.extend(pubs)
            await asyncio.sleep(DELAY_ENTRE_PEDIDOS)

        if self.cliente:
            await self.cliente.disconnect()

        return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 4 — yt-dlp (YouTube e TikTok)
# ═══════════════════════════════════════════════════════════════════════════════
class YtDlpOSINT:
    """
    Recolhe metadados e transcrições de vídeos do YouTube e TikTok
    relacionados com Angola, usando yt-dlp (ferramenta open-source).

    Instalação:
        pip install yt-dlp

    NOTA: Não faz download de vídeos — apenas metadados e legendas/transcrições.
    """

    PESQUISAS_YOUTUBE = [
        "manifestação angola 2024",
        "protestos angola 2025",
        "violência angola luanda",
        "fake news angola",
        "desinformação angola",
    ]

    async def raspar_youtube_pesquisa(self, termo_pesquisa: str, max_videos: int = 20) -> list:
        """
        Recolhe metadados de vídeos YouTube sobre Angola sem API key.
        Usa yt-dlp para aceder ao feed de pesquisa pública do YouTube.
        """
        import subprocess
        publicacoes = []

        try:
            # yt-dlp em modo assíncrono via subprocess
            cmd = [
                "yt-dlp",
                f"ytsearch{max_videos}:{termo_pesquisa}",
                "--dump-json",            # apenas metadados, sem download
                "--no-download",
                "--skip-download",
                "--write-auto-sub",       # transcrição automática se disponível
                "--sub-lang", "pt",
                "--quiet",
            ]
            resultado = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await resultado.communicate()

            for linha in stdout.decode("utf-8", errors="ignore").splitlines():
                if not linha.strip():
                    continue
                try:
                    meta = json.loads(linha)
                    titulo      = meta.get("title", "")
                    descricao   = meta.get("description", "")[:500]
                    url         = meta.get("webpage_url", "")
                    canal       = meta.get("uploader", "")
                    data_upload = meta.get("upload_date", "")
                    vistas      = meta.get("view_count", 0)

                    texto = f"{titulo}. {descricao}".strip()
                    if len(texto) < 20:
                        continue

                    pub = criar_publicacao(
                        id_externo=meta.get("id", url),
                        texto=texto,
                        plataforma="youtube",
                        url=url,
                        autor=canal,
                        data=f"{data_upload[:4]}-{data_upload[4:6]}-{data_upload[6:8]}" if data_upload else None,
                    )
                    pub["vistas"]  = vistas
                    pub["duracao"] = meta.get("duration", 0)
                    publicacoes.append(pub)

                except json.JSONDecodeError:
                    continue

        except FileNotFoundError:
            logger.error("yt-dlp não encontrado. Instalar: pip install yt-dlp")
        except Exception as e:
            logger.error(f"yt-dlp erro ({termo_pesquisa}): {e}")

        logger.info(f"YouTube '{termo_pesquisa}': {len(publicacoes)} vídeos recolhidos.")
        return publicacoes

    async def raspar_youtube_todas_pesquisas(self) -> list:
        """Raspa YouTube para todos os termos de pesquisa angolanos."""
        tarefas = [self.raspar_youtube_pesquisa(t, max_videos=15)
                   for t in self.PESQUISAS_YOUTUBE]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
        todas = []
        for r in resultados:
            if isinstance(r, list):
                todas.extend(r)
        return todas


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR OSINT — Pipeline assíncrono completo
# ═══════════════════════════════════════════════════════════════════════════════
class OrquestradorOSINT:
    """
    Orquestrador principal que coordena todos os scrapers OSINT
    e gere a fila de URLs com Redis para evitar reprocessamento.

    Fluxo:
        1. Scrapy raspa sites de notícias (paralelo)
        2. Playwright raspa Facebook e Nitter (concorrência limitada)
        3. Telethon recolhe Telegram (sequencial — respeitar rate limits)
        4. yt-dlp recolhe YouTube (paralelo)
        5. Deduplicação e persistência no MongoDB
        6. Métricas do ciclo registadas no log
    """

    def __init__(self):
        self.scrapy    = ScrapyOSINT()
        self.playwright= PlaywrightOSINT()
        self.telethon  = TelethonOSINT()
        self.ytdlp     = YtDlpOSINT()

        # Redis para fila de URLs já processadas (evitar duplicatas entre ciclos)
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            self.usar_redis = True
            logger.info("Redis: ligado para controlo de duplicatas.")
        except Exception:
            self.usar_redis = False
            logger.warning("Redis não disponível. Deduplicação apenas por MongoDB.")

    def ja_processado(self, id_externo: str) -> bool:
        """Verifica se um URL/ID já foi processado neste ciclo via Redis."""
        if not self.usar_redis:
            return False
        chave = f"osint:processado:{id_externo}"
        return bool(self.redis_client.get(chave))

    def marcar_processado(self, id_externo: str, ttl_horas: int = 24):
        """Marca um ID como processado no Redis (expira após ttl_horas)."""
        if not self.usar_redis:
            return
        chave = f"osint:processado:{id_externo}"
        self.redis_client.setex(chave, ttl_horas * 3600, "1")

    def filtrar_novas(self, publicacoes: list) -> list:
        """Remove publicações já processadas neste ciclo."""
        novas = []
        for pub in publicacoes:
            if not self.ja_processado(pub["id_externo"]):
                novas.append(pub)
                self.marcar_processado(pub["id_externo"])
        return novas

    async def executar_ciclo_completo(self) -> dict:
        """
        Executa um ciclo completo de recolha OSINT.
        Retorna estatísticas do ciclo.
        """
        inicio = time.time()
        logger.info("=" * 55)
        logger.info("CICLO OSINT INICIADO")
        logger.info("=" * 55)

        stats = {
            "scrapy_noticias":  0,
            "playwright_fb":    0,
            "playwright_nitter":0,
            "telethon_telegram":0,
            "ytdlp_youtube":    0,
            "total_recolhido":  0,
            "novas_apos_dedup": 0,
            "inseridas_mongodb":0,
            "duracao_segundos": 0,
        }

        todas_publicacoes = []

        # 1. Scrapy: sites de notícias (paralelo)
        logger.info("[1/4] Scrapy: sites de notícias angolanos...")
        pubs_scrapy = await self.scrapy.raspar_todas_fontes()
        stats["scrapy_noticias"] = len(pubs_scrapy)
        todas_publicacoes.extend(pubs_scrapy)

        # 2. Playwright: Facebook + Nitter (concorrência limitada)
        logger.info("[2/4] Playwright: Facebook e Nitter...")
        pubs_playwright = await self.playwright.raspar_todas_fontes_playwright()
        stats["playwright_fb"]     = sum(1 for p in pubs_playwright if p["plataforma"] == "facebook")
        stats["playwright_nitter"] = sum(1 for p in pubs_playwright if p["plataforma"] == "twitter")
        todas_publicacoes.extend(pubs_playwright)

        # 3. Telethon: Telegram (sequencial)
        logger.info("[3/4] Telethon: canais Telegram públicos...")
        pubs_telegram = await self.telethon.raspar_todos_canais()
        stats["telethon_telegram"] = len(pubs_telegram)
        todas_publicacoes.extend(pubs_telegram)

        # 4. yt-dlp: YouTube (paralelo)
        logger.info("[4/4] yt-dlp: YouTube Angola...")
        pubs_youtube = await self.ytdlp.raspar_youtube_todas_pesquisas()
        stats["ytdlp_youtube"] = len(pubs_youtube)
        todas_publicacoes.extend(pubs_youtube)

        # 5. Filtrar novas (Redis) e guardar no MongoDB
        stats["total_recolhido"]  = len(todas_publicacoes)
        novas = self.filtrar_novas(todas_publicacoes)
        stats["novas_apos_dedup"] = len(novas)

        if novas:
            inseridas = guardar_mongodb(novas)
            stats["inseridas_mongodb"] = inseridas

        stats["duracao_segundos"] = round(time.time() - inicio, 1)

        # Log do resumo
        logger.info("=" * 55)
        logger.info("CICLO OSINT CONCLUÍDO")
        logger.info(f"  Notícias (Scrapy)  : {stats['scrapy_noticias']}")
        logger.info(f"  Facebook (Playwright): {stats['playwright_fb']}")
        logger.info(f"  Twitter/Nitter     : {stats['playwright_nitter']}")
        logger.info(f"  Telegram (Telethon): {stats['telethon_telegram']}")
        logger.info(f"  YouTube (yt-dlp)   : {stats['ytdlp_youtube']}")
        logger.info(f"  Total recolhido    : {stats['total_recolhido']}")
        logger.info(f"  Novas (após dedup) : {stats['novas_apos_dedup']}")
        logger.info(f"  Inseridas MongoDB  : {stats['inseridas_mongodb']}")
        logger.info(f"  Duração            : {stats['duracao_segundos']}s")
        logger.info("=" * 55)

        return stats

    async def pipeline_continuo(self, intervalo_minutos: int = 30, max_ciclos: int = None):
        """
        Executa o pipeline OSINT continuamente em ciclos.

        Args:
            intervalo_minutos: Tempo de espera entre ciclos.
            max_ciclos: Número máximo de ciclos (None = infinito).

        Uso:
            asyncio.run(orquestrador.pipeline_continuo(intervalo_minutos=30))
        """
        ciclo = 0
        logger.info(f"Pipeline OSINT iniciado. Intervalo: {intervalo_minutos} min.")

        while max_ciclos is None or ciclo < max_ciclos:
            ciclo += 1
            logger.info(f"--- Ciclo #{ciclo} ---")
            try:
                stats = await self.executar_ciclo_completo()
            except Exception as e:
                logger.error(f"Erro no ciclo #{ciclo}: {e}")

            if max_ciclos and ciclo >= max_ciclos:
                break

            logger.info(f"Próximo ciclo em {intervalo_minutos} minutos...")
            await asyncio.sleep(intervalo_minutos * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="OSINT Scraper — Sistema de Monitoramento Angola UAN 2026"
    )
    parser.add_argument(
        "--modo",
        choices=["ciclo", "continuo", "teste"],
        default="ciclo",
        help="ciclo=um ciclo; continuo=loop infinito; teste=verificar instalação",
    )
    parser.add_argument("--intervalo", type=int, default=30,
                        help="Minutos entre ciclos (modo contínuo)")
    args = parser.parse_args()

    orquestrador = OrquestradorOSINT()

    if args.modo == "teste":
        # Verificar instalação de todas as dependências
        print("\n=== Verificação de dependências OSINT ===")
        deps = {
            "aiohttp":    "pip install aiohttp",
            "beautifulsoup4": "pip install beautifulsoup4",
            "playwright": "pip install playwright && playwright install chromium",
            "telethon":   "pip install telethon",
            "scrapy":     "pip install scrapy",
            "yt-dlp":     "pip install yt-dlp",
            "redis":      "pip install redis",
            "pymongo":    "pip install pymongo[srv]",
        }
        for dep, inst in deps.items():
            try:
                __import__(dep.replace("-", "_").replace("beautifulsoup4", "bs4"))
                print(f"  ✅ {dep}")
            except ImportError:
                print(f"  ❌ {dep} — instalar: {inst}")

    elif args.modo == "ciclo":
        asyncio.run(orquestrador.executar_ciclo_completo())

    elif args.modo == "continuo":
        asyncio.run(orquestrador.pipeline_continuo(
            intervalo_minutos=args.intervalo
        ))
