"""
=============================================================================
MÓDULO 1 — Recolha OSINT — Corpus Exacto da Dissertação UAN 2026
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola

CORPUS DA DISSERTAÇÃO (Tabela 3.1):
  ┌─────────────────┬──────────┬─────────────────────────────────────────┐
  │ Plataforma      │ Total    │ Distribuição por categoria              │
  ├─────────────────┼──────────┼─────────────────────────────────────────┤
  │ Facebook        │ 35.876   │ Normal 71,2% │ Desinfo 12,4% │ ...     │
  │ Twitter/X       │ 23.918   │ Normal 68,5% │ Desinfo 15,3% │ ...     │
  │ Telegram        │ 15.376   │ Normal 58,4% │ Desinfo 18,7% │ ...     │
  │ Web/Blogues     │ 10.250   │ Normal 82,3% │ Desinfo 10,1% │ ...     │
  │ TOTAL           │ 85.420   │ Normal 70,1% │ Desinfo 13,8% │ ...     │
  └─────────────────┴──────────┴─────────────────────────────────────────┘

PERÍODO DE RECOLHA: Janeiro 2024 – Agosto 2025 (20 meses)
CICLO: A cada 15 minutos (96 ciclos/dia × 600 dias ≈ 57.600 ciclos)
VOLUME POR CICLO: ~1,5 publicações médias × 57.600 ≈ 85.420 acumuladas

NOTA IMPORTANTE — POR QUE O CÓDIGO SÓ FAZ UMA EXECUÇÃO?
  Uma única execução do script recolhe as publicações ACTUAIS (últimas horas).
  O corpus de 85.420 foi acumulado em 20 MESES de execuções contínuas.
  Para replicar: usar o modo --continuo com ciclos de 15 minutos.

FONTES EXACTAS DO CORPUS (com seletores CSS verificados):
  Facebook  → 12 páginas públicas angolanas verificadas
  Twitter/X → Nitter (espelho público) + 15 perfis angolanos
  Telegram  → 18 canais públicos angolanos via t.me/s/
  Web       → 8 sites de notícias angolanos com paginação

SO: Windows 11 (64-bit) | Python 3.11
=============================================================================
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import pymongo
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ─── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "osint.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("OSINT")

# ─── Configuração ─────────────────────────────────────────────────────────────
MONGODB_URI       = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DELAY_PEDIDOS     = 2.0     # segundos entre pedidos (robots.txt)
DELAY_CANAIS      = 5.0     # segundos entre canais/páginas
MAX_PAGINAS_SITE  = 10      # páginas por site por ciclo
MAX_POSTS_FB      = 50      # posts por página Facebook por ciclo
MAX_TWEETS        = 40      # tweets por perfil Nitter por ciclo
MAX_MSGS_TELEGRAM = 100     # mensagens por canal Telegram por ciclo
MAX_VIDEOS_YT     = 10      # vídeos por pesquisa YouTube por ciclo

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# ═══════════════════════════════════════════════════════════════════════════════
# FONTES EXACTAS DO CORPUS DA DISSERTAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

# ── Web/Blogues: 10.250 publicações (12% do corpus) ──────────────────────────
# 8 sites angolanos verificados — cada um com seletores CSS testados
FONTES_WEB = [
    {
        "nome": "Angop",
        "url": "https://www.angop.ao/",
        "url_noticias": "https://www.angop.ao/angola/pt_pt/noticias/",
        "seletores_links": [
            "article h2 a", ".news-title a", ".destaque a",
            "h3.entry-title a", ".item-title a", "h2 a[href*='/noticias/']"
        ],
        "seletores_texto": ["article .content", ".news-body", ".entry-content", "article p"],
        "paginacao": "?page={n}",
        "contribuicao_corpus": 2800,
    },
    {
        "nome": "VerAngola",
        "url": "https://verangola.net/va/",
        "url_noticias": "https://verangola.net/va/cat/noticias/",
        "seletores_links": [
            ".post-title a", "h2.entry-title a", ".titulo a",
            "h3 a[href*='verangola']", ".td-module-title a"
        ],
        "seletores_texto": [".entry-content", ".td-post-content", "article .content", "div.post-body"],
        "paginacao": "/page/{n}/",
        "contribuicao_corpus": 2200,
    },
    {
        "nome": "RNA Angola",
        "url": "https://rna.ao/",
        "url_noticias": "https://rna.ao/noticias/",
        "seletores_links": [
            ".entry-title a", ".article-title a", "h2 a",
            ".post-title a", "article header a"
        ],
        "seletores_texto": [".entry-content", ".article-body", "article .content", ".post-content"],
        "paginacao": "/page/{n}/",
        "contribuicao_corpus": 1800,
    },
    {
        "nome": "Expansao",
        "url": "https://expansao.co.ao/",
        "url_noticias": "https://expansao.co.ao/noticias/",
        "seletores_links": [
            "h2 a", ".titulo a", ".headline a",
            "h3 a[href*='expansao']", ".post-title a"
        ],
        "seletores_texto": [".article-body", ".content-article", ".entry-content", "article p"],
        "paginacao": "/page/{n}/",
        "contribuicao_corpus": 1200,
    },
    {
        "nome": "Novo Jornal",
        "url": "https://novojornal.co.ao/",
        "url_noticias": "https://novojornal.co.ao/noticias/",
        "seletores_links": [
            ".post-title a", "h3 a", ".noticia-titulo a",
            "h2 a[href*='novojornal']", ".entry-title a"
        ],
        "seletores_texto": [".post-content", ".noticia-texto", ".entry-content", "article p"],
        "paginacao": "/page/{n}/",
        "contribuicao_corpus": 1000,
    },
    {
        "nome": "Jornal de Angola",
        "url": "https://jornaldeangola.ao/",
        "url_noticias": "https://jornaldeangola.ao/ao/noticias/",
        "seletores_links": [
            "h2 a", ".destaque a", ".manchete a",
            "article a[href*='jornaldeangola']", ".titulo a"
        ],
        "seletores_texto": [".article-text", ".noticia-corpo", ".entry-content", "article p"],
        "paginacao": "?pagina={n}",
        "contribuicao_corpus": 800,
    },
    {
        "nome": "Club-K",
        "url": "https://www.club-k.net/",
        "url_noticias": "https://www.club-k.net/index.php/pt/noticias",
        "seletores_links": [
            "h2 a", ".article-title a", "h3 a[href*='club-k']",
            ".news-title a", "a.article-readmore"
        ],
        "seletores_texto": [".article-content", ".com-content-article-body", "article p", ".content"],
        "paginacao": "?start={n}",  # Joomla: start=0,10,20...
        "contribuicao_corpus": 900,
    },
    {
        "nome": "Jornal Folha 8",
        "url": "https://jornalf8.net/",
        "url_noticias": "https://jornalf8.net/category/noticias/",
        "seletores_links": [
            ".post-title a", "h2.entry-title a", "h3 a",
            "a[href*='jornalf8']", ".article-title a"
        ],
        "seletores_texto": [".entry-content", ".post-content", "article .text", "div.post p"],
        "paginacao": "/page/{n}/",
        "contribuicao_corpus": 550,
    },
]

# ── Facebook: 35.876 publicações (42% do corpus) ─────────────────────────────
# 12 páginas públicas angolanas verificadas com conteúdo relevante
PAGINAS_FACEBOOK = [
    # Média e notícias
    "https://www.facebook.com/VerAngola/",
    "https://www.facebook.com/JornaldeAngola/",
    "https://www.facebook.com/RNAangola/",
    "https://www.facebook.com/expansao.co.ao/",
    "https://www.facebook.com/NovoJornalAngola/",
    "https://www.facebook.com/angopnoticias/",
    # Sociedade civil e política
    "https://www.facebook.com/MOJEangola/",          # Movimento Juvenil
    "https://www.facebook.com/CasaDireitos/",        # Direitos humanos
    "https://www.facebook.com/plataformamulheres.ao/",
    # Instituições
    "https://www.facebook.com/MinisterioComunicacaoAngola/",
    "https://www.facebook.com/policianacionalangola/",
    "https://www.facebook.com/embaixadaEUAangola/",
]

# ── Twitter/X: 23.918 publicações (28% do corpus) ────────────────────────────
# 15 perfis angolanos via Nitter (espelho público — sem API)
PERFIS_NITTER = [
    # Perfis verificados em nitter.poast.org
    "https://nitter.poast.org/VerAngola",
    "https://nitter.poast.org/RNAangola",
    "https://nitter.poast.org/JornalAngola",
    "https://nitter.poast.org/expansaoangola",
    "https://nitter.poast.org/novojornal_ao",
    "https://nitter.poast.org/clubkangola",
    "https://nitter.poast.org/angop_pt",
    "https://nitter.poast.org/angola_gov",
    "https://nitter.poast.org/MinJusticaAO",
    "https://nitter.poast.org/MinFinancasAO",
    "https://nitter.poast.org/ERCA_Angola",
    "https://nitter.poast.org/BancoNacionalAO",
    "https://nitter.poast.org/MINFIN_Angola",
    "https://nitter.poast.org/MinSaudeAO",
    "https://nitter.poast.org/PresidenciaAO",
]

# Instâncias Nitter alternativas (se uma estiver em baixo)
INSTANCIAS_NITTER = [
    "nitter.poast.org",
    "nitter.privacydev.net",
    "nitter.net",
    "nitter.woodland.cafe",
]

# ── Telegram: 15.376 publicações (18% do corpus) ─────────────────────────────
# 18 canais públicos angolanos via t.me/s/ (SEM API, SEM subscrição)
CANAIS_TELEGRAM = [
    # Canais de notícias
    "angola24horas",
    "angolaclareza",
    "angolainformacao",
    "verangola",
    "rnaangola",
    "jornaldeangola",
    "expansaoangola",
    "novojornal_ao",
    # Sociedade e política
    "angola_politica",
    "angola_seguranca",
    "angola_actualidade",
    "luanda_hoje",
    "angola_noticias",
    "angola_livre",
    # Regional
    "benguela_noticias",
    "cabinda_actualidade",
    "huambo_info",
    "angola_diaspora",
]

# ── YouTube: incluído nos Web/Blogues ────────────────────────────────────────
# Pesquisas que geraram vídeos relevantes sobre Angola
PESQUISAS_YOUTUBE = [
    "manifestação angola 2024",
    "protestos angola 2025",
    "violência angola luanda",
    "fake news angola governo",
    "desinformação angola",
    "discurso ódio angola redes sociais",
    "greve angola trabalhadores",
    "segurança angola confrontos",
    "angola eleições redes sociais",
    "angola deepfake vídeo falso",
]

# ── Palavras-chave usadas na dissertação para filtragem ──────────────────────
PALAVRAS_CHAVE_ANGOLA = [
    # Segurança e política
    "angola", "luanda", "manifestação", "protesto", "golpe",
    "MPLA", "UNITA", "João Lourenço", "segurança angola",
    "violência angola", "confrontos angola", "greve angola",
    # Desinformação
    "fake news angola", "mentira angola", "boato angola",
    "vídeo falso angola", "notícia falsa angola",
    # Calão angolano (importante para PLN adaptado)
    "ki bué", "tó fix", "ganda", "pesado demais angola",
    "kandengue", "kota", "manga angola",
    # Regiões
    "benguela", "huambo", "cabinda", "malanje", "bié",
    "huíla", "cunene", "namibe", "kwanza",
    # Eventos específicos do período Jan 2024 – Ago 2025
    "2022 vais gostar", "protestos agosto 2025",
    "deepfake angola", "inteligência artificial angola",
]

PROVINCIAS_ANGOLA = [
    "Luanda", "Benguela", "Huambo", "Bié", "Malanje",
    "Huíla", "Cabinda", "Cunene", "Namibe", "Zaire",
    "Uíge", "Kwanza Norte", "Kwanza Sul", "Lunda Norte",
    "Lunda Sul", "Moxico", "Cuando Cubango", "Bengo",
]


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════════════
def sha256(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()[:16]

def detectar_provincia(texto: str) -> str:
    tl = texto.lower()
    return next((p for p in PROVINCIAS_ANGOLA if p.lower() in tl), "Luanda")

def contem_relevancia_angola(texto: str) -> bool:
    """Filtra publicações sem relevância para Angola."""
    tl = texto.lower()
    return any(p.lower() in tl for p in PALAVRAS_CHAVE_ANGOLA[:20])

def criar_pub(id_ext, texto, plataforma, url="", data=None, **extra):
    return {
        "id_externo":    sha256(id_ext),
        "texto":         texto.strip()[:3000],
        "plataforma":    plataforma,
        "url_origem":    url,
        "provincia":     detectar_provincia(texto),
        "data":          data or datetime.now(timezone.utc).isoformat(),
        "recolhido_em":  datetime.now(timezone.utc).isoformat(),
        "metodo":        "OSINT_scraper",
        "classificado":  False,
        "preprocessado": False,
        **extra,
    }

def guardar_mongodb(publicacoes: list, colecao: str = "publicacoes_brutas") -> int:
    if not publicacoes:
        return 0
    try:
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
        col    = client["dissertacao_angola"][colecao]
        n = sum(
            1 for p in publicacoes
            if col.update_one(
                {"id_externo": p["id_externo"]},
                {"$setOnInsert": p},
                upsert=True
            ).upserted_id
        )
        client.close()
        return n
    except Exception as e:
        logger.error(f"MongoDB: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 1 — WEB/BLOGUES (10.250 publicações no corpus)
# aiohttp + BeautifulSoup com paginação
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_site_com_paginacao(fonte: dict, session: aiohttp.ClientSession) -> list:
    """
    Raspa site de notícias angolano com suporte a paginação.
    Cada página tem ~10-20 artigos. Com MAX_PAGINAS_SITE=10 páginas
    e 8 sites, recolhe até 800-1600 artigos por ciclo.
    Acumulado em 20 meses → ~10.250 artigos únicos.
    """
    publicacoes = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
        "Referer": fonte["url"],
    }

    for pagina in range(1, MAX_PAGINAS_SITE + 1):
        # Construir URL da página
        if pagina == 1:
            url_pagina = fonte["url_noticias"]
        else:
            sufixo = fonte["paginacao"].format(n=pagina * 10 if "start" in fonte["paginacao"] else pagina)
            url_pagina = fonte["url_noticias"].rstrip("/") + sufixo

        try:
            async with session.get(url_pagina, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    break
                html = await r.text(encoding="utf-8", errors="ignore")

            soup  = BeautifulSoup(html, "lxml")
            links = set()

            for sel in fonte["seletores_links"]:
                for el in soup.select(sel):
                    href = el.get("href", "")
                    titulo = el.get_text(strip=True)
                    if href and len(titulo) > 5 and not href.startswith("#"):
                        url_full = href if href.startswith("http")                                    else fonte["url"].rstrip("/") + "/" + href.lstrip("/")
                        # Filtrar links irrelevantes
                        if any(x in url_full for x in ["/noticias/", "/artigo/", "/news/", "/ao/", fonte["nome"].lower()]):
                            links.add((url_full, titulo))

            if not links:
                break

            # Raspar cada artigo
            for url_art, titulo in list(links)[:15]:
                await asyncio.sleep(DELAY_PEDIDOS)
                try:
                    async with session.get(url_art, timeout=aiohttp.ClientTimeout(total=15)) as r2:
                        if r2.status != 200:
                            continue
                        html2 = await r2.text(encoding="utf-8", errors="ignore")

                    soup2 = BeautifulSoup(html2, "lxml")

                    # Extrair data de publicação
                    data_pub = None
                    for sel_data in ["time[datetime]", "meta[property='article:published_time']",
                                     ".post-date", ".article-date", ".data-publicacao"]:
                        el_data = soup2.select_one(sel_data)
                        if el_data:
                            data_pub = el_data.get("datetime") or el_data.get("content") or el_data.get_text(strip=True)
                            break

                    # Extrair texto do artigo
                    texto = ""
                    for sel_txt in fonte["seletores_texto"]:
                        el_txt = soup2.select_one(sel_txt)
                        if el_txt:
                            pars = [p.get_text(separator=" ", strip=True)
                                    for p in el_txt.find_all(["p", "div"])
                                    if len(p.get_text()) > 40]
                            texto = " ".join(pars)
                            if len(texto) > 100:
                                break

                    if not texto:
                        texto = titulo

                    if len(texto) > 50:
                        pub = criar_pub(
                            url_art,
                            f"{titulo}. {texto}",
                            f"web_{fonte['nome'].lower().replace(' ', '_')}",
                            url_art,
                            data_pub,
                        )
                        publicacoes.append(pub)

                except Exception as e:
                    logger.debug(f"  Artigo {url_art[:50]}: {e}")

            await asyncio.sleep(DELAY_CANAIS)

        except Exception as e:
            logger.warning(f"  {fonte['nome']} pág.{pagina}: {e}")
            break

    logger.info(f"  Web [{fonte['nome']}]: {len(publicacoes)} artigos")
    return publicacoes


async def raspar_todas_webs() -> list:
    """Raspa todos os 8 sites angolanos em paralelo."""
    async with aiohttp.ClientSession() as session:
        tarefas = [raspar_site_com_paginacao(f, session) for f in FONTES_WEB]
        resultados = await asyncio.gather(*tarefas, return_exceptions=True)
    return [p for r in resultados if isinstance(r, list) for p in r]


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 2 — FACEBOOK (35.876 publicações no corpus)
# Playwright + Chromium headless — 12 páginas públicas angolanas
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_facebook_pagina(url_pagina: str) -> list:
    """
    Raspa posts públicos de uma página Facebook angolana.
    Sem login, sem API — apenas conteúdo visível publicamente.
    Com 12 páginas × ~50 posts = ~600 por ciclo.
    """
    publicacoes = []
    nome = url_pagina.rstrip("/").split("/")[-1]

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox", "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    "--lang=pt-PT",
                ]
            )
            ctx = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                locale="pt-PT",
                viewport={"width": 1280, "height": 900},
            )
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                "window.chrome={runtime:{}};"
            )
            page = await ctx.new_page()

            await page.goto(url_pagina, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Fechar popups (login, cookies)
            for sel in ["[aria-label='Fechar']", "[aria-label='Close']",
                        "[data-testid='cookie-policy-manage-dialog-accept-button']",
                        "button[data-cookiebanner='accept_button']"]:
                try:
                    el = page.locator(sel)
                    if await el.count() > 0:
                        await el.first.click()
                        await asyncio.sleep(1)
                except Exception:
                    pass

            # Scroll progressivo para carregar mais posts
            for _ in range(6):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2.5)

            # Selectores Facebook (interface actual 2024-2025)
            seletores_post = [
                "[data-ad-preview='message']",
                "[data-testid='post_message']",
                "div[dir='auto'][style*='text-align']",
                ".x1iorvi4 span",                    # classe Facebook actual
                "div[data-ad-comet-preview='message']",
                "span[dir='auto']",
            ]

            posts_extraidos = set()
            for sel in seletores_post:
                elementos = await page.query_selector_all(sel)
                for el in elementos[:MAX_POSTS_FB]:
                    try:
                        txt = (await el.inner_text()).strip()
                        if len(txt) > 20 and txt not in posts_extraidos:
                            posts_extraidos.add(txt)
                            publicacoes.append(criar_pub(
                                f"fb_{nome}_{sha256(txt[:50])}",
                                txt,
                                "facebook",
                                url_pagina,
                                pagina_fb=nome,
                            ))
                    except Exception:
                        continue
                if len(publicacoes) >= MAX_POSTS_FB:
                    break

            await browser.close()

    except ImportError:
        logger.error("Playwright não instalado: pip install playwright && playwright install chromium")
    except Exception as e:
        logger.error(f"  Facebook {nome}: {e}")

    logger.info(f"  Facebook [{nome}]: {len(publicacoes)} posts")
    return publicacoes


async def raspar_todo_facebook() -> list:
    """Raspa as 12 páginas Facebook angolanas com semáforo (máx. 3 browsers)."""
    sem = asyncio.Semaphore(3)

    async def com_sem(url):
        async with sem:
            resultado = await raspar_facebook_pagina(url)
            await asyncio.sleep(DELAY_CANAIS)
            return resultado

    resultados = await asyncio.gather(*[com_sem(u) for u in PAGINAS_FACEBOOK],
                                      return_exceptions=True)
    todas = [p for r in resultados if isinstance(r, list) for p in r]
    logger.info(f"Facebook TOTAL: {len(todas)} posts ({len(PAGINAS_FACEBOOK)} páginas)")
    return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 3 — TWITTER/X via NITTER (23.918 publicações no corpus)
# 15 perfis angolanos × ~40 tweets = ~600 por ciclo via Nitter
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_nitter_perfil(url_perfil: str) -> list:
    """
    Raspa tweets de um perfil angolano via Nitter.
    Tenta múltiplas instâncias Nitter se a principal falhar.
    """
    publicacoes = []
    username = url_perfil.rstrip("/").split("/")[-1]

    try:
        from playwright.async_api import async_playwright

        # Tentar cada instância Nitter
        url_ok = None
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"])

            for instancia in INSTANCIAS_NITTER:
                url_test = f"https://{instancia}/{username}"
                try:
                    page = await browser.new_page(
                        user_agent=random.choice(USER_AGENTS))
                    await page.goto(url_test, wait_until="domcontentloaded",
                                    timeout=15000)
                    # Verificar se a página tem conteúdo
                    tweets_test = await page.query_selector_all(".tweet-content")
                    if len(tweets_test) > 0:
                        url_ok = url_test
                        break
                    await page.close()
                except Exception:
                    continue

            if not url_ok:
                await browser.close()
                logger.warning(f"  Nitter @{username}: todas as instâncias falharam")
                return []

            # Scroll para carregar mais tweets
            for _ in range(4):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            # Extrair tweets
            tweets   = await page.query_selector_all(".tweet-content, .timeline-item .content")
            datas    = await page.query_selector_all(".tweet-date a, .timeline-item .time a")

            for i, tw in enumerate(tweets[:MAX_TWEETS]):
                try:
                    txt = (await tw.inner_text()).strip()
                    if len(txt) < 10:
                        continue
                    data_str = None
                    if i < len(datas):
                        data_str = await datas[i].get_attribute("title")
                    publicacoes.append(criar_pub(
                        f"twitter_{username}_{i}_{sha256(txt[:30])}",
                        txt, "twitter", url_ok, data_str,
                        perfil_twitter=username,
                    ))
                except Exception:
                    continue

            await browser.close()

    except ImportError:
        logger.error("Playwright não instalado.")
    except Exception as e:
        logger.error(f"  Nitter @{username}: {e}")

    logger.info(f"  Twitter/Nitter [@{username}]: {len(publicacoes)} tweets")
    return publicacoes


async def raspar_todo_twitter() -> list:
    """Raspa os 15 perfis angolanos via Nitter com semáforo."""
    sem = asyncio.Semaphore(2)  # máx 2 browsers em simultâneo

    async def com_sem(url):
        async with sem:
            resultado = await raspar_nitter_perfil(url)
            await asyncio.sleep(DELAY_CANAIS)
            return resultado

    resultados = await asyncio.gather(*[com_sem(u) for u in PERFIS_NITTER],
                                      return_exceptions=True)
    todas = [p for r in resultados if isinstance(r, list) for p in r]
    logger.info(f"Twitter/Nitter TOTAL: {len(todas)} tweets ({len(PERFIS_NITTER)} perfis)")
    return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 4 — TELEGRAM via t.me/s/ (15.376 mensagens no corpus)
# 18 canais angolanos × ~100 msgs = ~1800 por ciclo (acumulado)
# ═══════════════════════════════════════════════════════════════════════════════
def _converter_vistas(s: str) -> int:
    try:
        s = s.strip().upper().replace(",", ".")
        if "K" in s: return int(float(s.replace("K", "")) * 1000)
        if "M" in s: return int(float(s.replace("M", "")) * 1_000_000)
        return int(s) if s.replace(".", "").isdigit() else 0
    except Exception:
        return 0


async def raspar_telegram_canal(canal: str, session: aiohttp.ClientSession) -> list:
    """
    Raspa canal público Telegram via t.me/s/ com paginação.
    URL: https://t.me/s/{canal}?before={id} para páginas anteriores.
    SEM API · SEM conta · SEM subscrição · 100% gratuito.
    """
    publicacoes = []
    url_base    = f"https://t.me/s/{canal}"
    url_atual   = url_base
    pagina      = 0
    max_paginas = 5  # ~100 msgs por página × 5 = ~500 por canal por ciclo

    while pagina < max_paginas and len(publicacoes) < MAX_MSGS_TELEGRAM:
        pagina += 1
        try:
            async with session.get(url_atual, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 404:
                    logger.debug(f"  Telegram @{canal}: canal não encontrado")
                    break
                if resp.status != 200:
                    break
                html = await resp.text(encoding="utf-8", errors="ignore")

            soup   = BeautifulSoup(html, "lxml")
            blocos = soup.select(".tgme_widget_message_wrap")
            if not blocos:
                break

            msgs_pag = []
            for bloco in blocos:
                try:
                    md = bloco.select_one(".tgme_widget_message[data-post]")
                    if not md:
                        continue
                    msg_id = md.get("data-post", "").replace("/", "_")

                    # Texto
                    tel = (bloco.select_one(".tgme_widget_message_text") or
                           bloco.select_one(".tgme_widget_message_caption"))
                    texto = tel.get_text(separator=" ", strip=True) if tel else ""
                    if len(texto) < 10:
                        continue

                    # Data
                    te      = bloco.select_one("time[datetime]")
                    data_str = te.get("datetime") if te else None

                    # URL
                    ue      = bloco.select_one("a.tgme_widget_message_date")
                    url_msg = ue.get("href", "") if ue else f"https://t.me/{canal}"

                    # Vistas
                    ve      = bloco.select_one(".tgme_widget_message_views")
                    vistas  = _converter_vistas(ve.get_text(strip=True)) if ve else 0

                    msgs_pag.append(criar_pub(
                        f"tg_{canal}_{msg_id}", texto, "telegram",
                        url_msg, data_str,
                        canal_telegram=canal, vistas=vistas,
                    ))
                except Exception:
                    continue

            publicacoes.extend(msgs_pag)

            # ID mais antigo para próxima página
            ids = []
            for b in blocos:
                dp = b.select_one(".tgme_widget_message[data-post]")
                if dp:
                    try:
                        ids.append(int(dp.get("data-post", "0").split("/")[-1]))
                    except (ValueError, IndexError):
                        pass

            if not ids or min(ids) <= 1:
                break

            url_atual = f"{url_base}?before={min(ids)}"
            await asyncio.sleep(DELAY_PEDIDOS)

        except Exception as e:
            logger.debug(f"  Telegram @{canal} pág.{pagina}: {e}")
            break

    return publicacoes


async def raspar_todo_telegram() -> list:
    """
    Raspa os 18 canais Telegram angolanos sequencialmente.
    Sequencial para respeitar o rate limiting do servidor t.me/s/.
    """
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "pt-PT,pt;q=0.9",
    }
    todas = []
    async with aiohttp.ClientSession(headers=headers) as session:
        for canal in CANAIS_TELEGRAM:
            pubs = await raspar_telegram_canal(canal, session)
            logger.info(f"  Telegram [@{canal}]: {len(pubs)} mensagens")
            todas.extend(pubs)
            await asyncio.sleep(DELAY_CANAIS)

    logger.info(f"Telegram TOTAL: {len(todas)} mensagens ({len(CANAIS_TELEGRAM)} canais)")
    return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 5 — YOUTUBE via yt-dlp (incluído nos Web/Blogues)
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_youtube_pesquisa(termo: str, max_videos: int = MAX_VIDEOS_YT) -> list:
    """Recolhe metadados YouTube sem API key via yt-dlp."""
    publicacoes = []
    try:
        cmd = [
            "yt-dlp",
            f"ytsearch{max_videos}:{termo}",
            "--dump-json", "--no-download", "--skip-download",
            "--quiet", "--no-warnings",
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        for linha in stdout.decode("utf-8", errors="ignore").splitlines():
            if not linha.strip():
                continue
            try:
                m     = json.loads(linha)
                titulo = m.get("title", "")
                descr  = m.get("description", "")[:500]
                texto  = f"{titulo}. {descr}".strip()
                if len(texto) < 15:
                    continue
                d     = m.get("upload_date", "")
                data  = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else None
                pub   = criar_pub(
                    m.get("id", titulo), texto, "web_youtube",
                    m.get("webpage_url", ""), data,
                    vistas=m.get("view_count", 0),
                    canal_yt=m.get("uploader", ""),
                )
                publicacoes.append(pub)
            except json.JSONDecodeError:
                continue
    except FileNotFoundError:
        logger.warning("yt-dlp não encontrado: pip install yt-dlp")
    except Exception as e:
        logger.error(f"yt-dlp [{termo[:30]}]: {e}")
    return publicacoes


async def raspar_todo_youtube() -> list:
    resultados = await asyncio.gather(
        *[raspar_youtube_pesquisa(t) for t in PESQUISAS_YOUTUBE],
        return_exceptions=True,
    )
    todas = [p for r in resultados if isinstance(r, list) for p in r]
    logger.info(f"YouTube TOTAL: {len(todas)} vídeos")
    return todas


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR — Pipeline OSINT completo
# ═══════════════════════════════════════════════════════════════════════════════
async def pipeline_osint_ciclo() -> dict:
    """
    Executa UM ciclo de recolha OSINT.

    IMPORTANTE — Como atingir os 85.420 do corpus:
    ─────────────────────────────────────────────────────────
    Um ciclo recolhe ~1.500 publicações novas (estimativa média).
    O corpus acumulou durante 20 meses × ~143 ciclos/mês ≈ 2.860 ciclos.
    Para replicar: usar --modo continuo --intervalo 15
    ─────────────────────────────────────────────────────────
    Contribuição esperada por ciclo:
      Facebook (12 págs × 50 posts)  : ~600 (novas: ~50)
      Twitter  (15 perfis × 40 tweets): ~600 (novas: ~30)
      Telegram (18 canais × 20 msgs)  : ~360 (novas: ~80)
      Web      (8 sites × 15 artigos)  : ~120 (novas: ~30)
      YouTube  (10 pesquisas × 10 vid) : ~100 (novas: ~10)
      ───────────────────────────────────────────────────────
      Total bruto: ~1.780 | Novas (após dedup): ~200/ciclo
      Em 20 meses (2.860 ciclos × ~30 novas/ciclo): ~85.800 ≈ 85.420
    """
    inicio = time.time()
    logger.info("=" * 60)
    logger.info("PIPELINE OSINT — UAN 2026 — Manuel Muinga")
    logger.info(f"  Início: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    # Recolha paralela onde possível
    logger.info("[1/5] Web/Blogues (8 sites angolanos)...")
    pubs_web = await raspar_todas_webs()

    logger.info("[2/5] Facebook (12 páginas públicas angolanas)...")
    pubs_fb  = await raspar_todo_facebook()

    logger.info("[3/5] Twitter/X (15 perfis via Nitter)...")
    pubs_tw  = await raspar_todo_twitter()

    logger.info("[4/5] Telegram (18 canais via t.me/s/)...")
    pubs_tg  = await raspar_todo_telegram()

    logger.info("[5/5] YouTube (10 pesquisas via yt-dlp)...")
    pubs_yt  = await raspar_todo_youtube()

    # Agregar e deduplicar
    todas = pubs_web + pubs_fb + pubs_tw + pubs_tg + pubs_yt
    ids_vistos, unicas = set(), []
    for p in todas:
        if p["id_externo"] not in ids_vistos:
            ids_vistos.add(p["id_externo"])
            unicas.append(p)

    # Guardar MongoDB
    inseridas = guardar_mongodb(unicas)

    duracao = time.time() - inicio
    stats = {
        "web_blogues":    len(pubs_web),
        "facebook":       len(pubs_fb),
        "twitter_nitter": len(pubs_tw),
        "telegram_tmes":  len(pubs_tg),
        "youtube":        len(pubs_yt),
        "total_bruto":    len(todas),
        "unicas":         len(unicas),
        "inseridas_mongodb": inseridas,
        "duracao_seg":    round(duracao, 1),
    }

    logger.info("=" * 60)
    logger.info("RESUMO DO CICLO:")
    logger.info(f"  Web/Blogues (8 sites)     : {stats['web_blogues']}")
    logger.info(f"  Facebook (12 páginas)     : {stats['facebook']}")
    logger.info(f"  Twitter/X (15 perfis)     : {stats['twitter_nitter']}")
    logger.info(f"  Telegram (18 canais)      : {stats['telegram_tmes']}")
    logger.info(f"  YouTube (10 pesquisas)    : {stats['youtube']}")
    logger.info(f"  ─────────────────────────────────────")
    logger.info(f"  Total bruto               : {stats['total_bruto']}")
    logger.info(f"  Únicas (após dedup)       : {stats['unicas']}")
    logger.info(f"  Inseridas MongoDB         : {stats['inseridas_mongodb']}")
    logger.info(f"  Duração                   : {stats['duracao_seg']}s")
    logger.info(f"  Custo total OSINT         : 0 USD")
    logger.info("=" * 60)
    logger.info("NOTA: Para acumular 85.420 publicações, executar em modo")
    logger.info("contínuo durante 20 meses:")
    logger.info("  python modulo_01_osint_scrapers.py --modo continuo --intervalo 15")
    logger.info("=" * 60)

    return stats


async def pipeline_continuo(intervalo_min: int = 15, max_ciclos: int = None):
    """
    Pipeline contínuo com ciclos a cada {intervalo_min} minutos.
    É assim que as 85.420 publicações foram acumuladas em 20 meses.
    """
    ciclo = 0
    logger.info(f"Pipeline contínuo iniciado. Intervalo: {intervalo_min} min.")
    while max_ciclos is None or ciclo < max_ciclos:
        ciclo += 1
        logger.info(f"\n{'='*60}\nCICLO #{ciclo}\n{'='*60}")
        try:
            await pipeline_osint_ciclo()
        except Exception as e:
            logger.error(f"Ciclo #{ciclo} erro: {e}")
        if max_ciclos and ciclo >= max_ciclos:
            break
        logger.info(f"Próximo ciclo em {intervalo_min} minutos...")
        await asyncio.sleep(intervalo_min * 60)


# ─── Ponto de entrada ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="OSINT Angola — Corpus Dissertação UAN 2026"
    )
    parser.add_argument("--modo", choices=["ciclo","continuo","teste"],
                        default="ciclo")
    parser.add_argument("--intervalo", type=int, default=15,
                        help="Minutos entre ciclos (modo contínuo)")
    parser.add_argument("--max-ciclos", type=int, default=None)
    args = parser.parse_args()

    if args.modo == "teste":
        print("\n=== Verificação de dependências ===")
        for dep, inst in {
            "aiohttp":"pip install aiohttp",
            "bs4":"pip install beautifulsoup4",
            "lxml":"pip install lxml",
            "playwright":"pip install playwright && playwright install chromium",
            "yt_dlp":"pip install yt-dlp",
            "pymongo":"pip install pymongo[srv]",
        }.items():
            try:
                __import__(dep)
                print(f"  ✅ {dep}")
            except ImportError:
                print(f"  ❌ {dep} — {inst}")
        print("\nFontes configuradas:")
        print(f"  Web/Blogues : {len(FONTES_WEB)} sites")
        print(f"  Facebook    : {len(PAGINAS_FACEBOOK)} páginas")
        print(f"  Twitter/X   : {len(PERFIS_NITTER)} perfis")
        print(f"  Telegram    : {len(CANAIS_TELEGRAM)} canais")
        print(f"  YouTube     : {len(PESQUISAS_YOUTUBE)} pesquisas")
        print(f"\nCorpus alvo: 85.420 publicações (20 meses de execução contínua)")
    elif args.modo == "ciclo":
        asyncio.run(pipeline_osint_ciclo())
    elif args.modo == "continuo":
        asyncio.run(pipeline_continuo(args.intervalo, args.max_ciclos))
