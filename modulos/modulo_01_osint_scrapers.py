"""
=============================================================================
MÓDULO 1 — Recolha OSINT com Scrapers Assíncronos (v2 — Julho 2026)
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola

Arquitectura OSINT 100% gratuita (sem APIs pagas, sem subscrições):
  ┌─────────────────────────────────────────────────────────┐
  │  Plataforma        │ Ferramenta         │ Custo         │
  ├─────────────────────────────────────────────────────────┤
  │  Sites de notícias │ Scrapy + aiohttp   │ Gratuito      │
  │  Facebook público  │ Playwright         │ Gratuito      │
  │  X/Twitter público │ Playwright + Nitter│ Gratuito      │
  │  Telegram público  │ t.me/s/ scraper    │ Gratuito      │
  │  YouTube / TikTok  │ yt-dlp             │ Gratuito      │
  └─────────────────────────────────────────────────────────┘

NOTA v2: O Telethon MTProto foi substituído pelo scraper t.me/s/
porque o Telegram passou a exigir subscrição paga em 2025.
O endpoint t.me/s/ é público, sem autenticação, e 100% gratuito.

SO: Windows 10/11 | Google Colab Pro | Python 3.11
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

import aiohttp
import pymongo
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

# ─── Logging UTF-8 ────────────────────────────────────────────────────────────
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
MONGODB_URI          = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DELAY_PEDIDOS        = 2.0
MAX_ARTIGOS_POR_SITE = 30
MAX_MSGS_TELEGRAM    = 200

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]

FONTES_NOTICIAS = [
    {"nome": "Angop",        "url": "https://www.angop.ao/",
     "seletores": ["article h2 a", ".news-title a", ".destaque a"]},
    {"nome": "VerAngola",    "url": "https://verangola.net/va/",
     "seletores": [".post-title a", "h2.entry-title a"]},
    {"nome": "RNA Angola",   "url": "https://rna.ao/",
     "seletores": [".entry-title a", ".article-title a"]},
    {"nome": "Expansao",     "url": "https://expansao.co.ao/",
     "seletores": ["h2 a", ".titulo a"]},
    {"nome": "Novo Jornal",  "url": "https://novojornal.co.ao/",
     "seletores": [".post-title a", "h3 a"]},
    {"nome": "Jornal Angola","url": "https://jornaldeangola.ao/",
     "seletores": ["h2 a", ".destaque a"]},
]

PAGINAS_FACEBOOK = [
    "https://www.facebook.com/VerAngola/",
    "https://www.facebook.com/RNAangola/",
    "https://www.facebook.com/jornaldeangola/",
    "https://www.facebook.com/expansao.ao/",
]

PERFIS_NITTER = [
    "https://nitter.poast.org/VerAngola",
    "https://nitter.poast.org/RNAangola",
    "https://nitter.poast.org/angola_gov",
]

# ─── Canais Telegram públicos angolanos (acesso via t.me/s/) ─────────────────
CANAIS_TELEGRAM = [
    "angola_noticias",
    "luanda_hoje",
    "angola_actualidade",
    "angola_seguranca",
    "angola_politica",
    "verangola",
    "rna_angola",
]

PESQUISAS_YOUTUBE = [
    "manifestação angola 2025",
    "protestos angola luanda 2025",
    "violência angola 2025",
    "fake news angola",
    "desinformação angola",
]

PROVINCIAS = [
    "Luanda","Benguela","Huambo","Bié","Malanje","Huíla",
    "Cabinda","Cunene","Namibe","Zaire","Uíge","Kwanza Norte",
    "Kwanza Sul","Lunda Norte","Lunda Sul","Moxico","Cuando Cubango","Bengo",
]

NORMALIZACOES = {
    "ki bué":"muito","ki bue":"muito","bué":"muito","tó fix":"tudo bem",
    "ganda":"grande","kandengue":"crianca","kota":"pessoa",
    "manga":"muito","leke":"pequeno","zungu":"rumor",
}


# ─── Utilitários ──────────────────────────────────────────────────────────────
def sha256(s): return hashlib.sha256(str(s).encode()).hexdigest()[:16]
def detectar_prov(t): return next((p for p in PROVINCIAS if p.lower() in t.lower()), "Luanda")

def criar_pub(id_ext, texto, plataforma, url="", data=None, **extra):
    pub = {
        "id_externo":    sha256(id_ext),
        "texto":         texto.strip()[:3000],
        "plataforma":    plataforma,
        "url_origem":    url,
        "provincia":     detectar_prov(texto),
        "data":          data or datetime.now(timezone.utc).isoformat(),
        "recolhido_em":  datetime.now(timezone.utc).isoformat(),
        "metodo":        "OSINT_scraper",
        "classificado":  False,
        "preprocessado": False,
    }
    pub.update(extra)
    return pub

def guardar_mongodb(publicacoes, colecao="publicacoes_brutas"):
    if not publicacoes: return 0
    try:
        client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
        col    = client["dissertacao_angola"][colecao]
        n = sum(1 for p in publicacoes
                if col.update_one({"id_externo": p["id_externo"]},
                                  {"$setOnInsert": p}, upsert=True).upserted_id)
        client.close()
        return n
    except Exception as e:
        logger.error(f"MongoDB: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 1 — SCRAPY/AIOHTTP (Sites de notícias)
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_site_noticias(fonte, session):
    """Raspa artigos de um site de notícias angolano com aiohttp."""
    publicacoes = []
    headers = {"User-Agent": random.choice(USER_AGENTS),
               "Accept-Language": "pt-PT,pt;q=0.9"}
    try:
        async with session.get(fonte["url"], timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200: return []
            html = await r.text(encoding="utf-8", errors="ignore")

        soup  = BeautifulSoup(html, "lxml")
        links = set()
        for sel in fonte["seletores"]:
            for el in soup.select(sel):
                href = el.get("href", "")
                if href and not href.startswith("#"):
                    url_full = href if href.startswith("http")                                else fonte["url"].rstrip("/")+"/"+href.lstrip("/")
                    links.add((url_full, el.get_text(strip=True)))

        for url_art, titulo in list(links)[:MAX_ARTIGOS_POR_SITE]:
            await asyncio.sleep(DELAY_PEDIDOS)
            try:
                async with session.get(url_art, timeout=aiohttp.ClientTimeout(total=15)) as r2:
                    if r2.status != 200: continue
                    html2 = await r2.text(encoding="utf-8", errors="ignore")
                soup2 = BeautifulSoup(html2, "lxml")
                texto = ""
                for sel in ["article","main",".entry-content",".post-content"]:
                    el = soup2.select_one(sel)
                    if el:
                        pars = [p.get_text(strip=True) for p in el.find_all("p") if len(p.get_text())>30]
                        texto = " ".join(pars)
                        if len(texto)>80: break
                if len(texto)>50:
                    publicacoes.append(criar_pub(url_art, f"{titulo}. {texto}",
                                                  f"web_{fonte['nome'].lower()}", url_art))
            except Exception: continue

        logger.info(f"  {fonte['nome']}: {len(publicacoes)} artigos")
    except Exception as e:
        logger.error(f"  {fonte['nome']} erro: {e}")
    return publicacoes

async def raspar_todas_noticias():
    async with aiohttp.ClientSession() as session:
        res = await asyncio.gather(*[raspar_site_noticias(f, session) for f in FONTES_NOTICIAS],
                                   return_exceptions=True)
    return [p for r in res if isinstance(r, list) for p in r]


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 2 — PLAYWRIGHT (Facebook + Nitter)
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_playwright(url, tipo):
    """Raspa página com Playwright Chromium headless."""
    publicacoes = []
    nome = url.rstrip("/").split("/")[-1]
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=True,
                args=["--no-sandbox","--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"]
            )
            ctx  = await browser.new_context(
                user_agent=random.choice(USER_AGENTS), locale="pt-PT")
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Fechar popup de login (Facebook)
            for sel in ["[aria-label=\"Fechar\"]","[aria-label=\"Close\"]"]:
                try:
                    el = page.locator(sel)
                    if await el.count()>0: await el.first.click(); await asyncio.sleep(1)
                except: pass

            for _ in range(4):
                await page.evaluate("window.scrollTo(0,document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Extrair texto
            seletores = {
                "facebook": ["[data-ad-preview=\"message\"]","[data-testid=\"post_message\"]","div[dir=\"auto\"]"],
                "nitter":   [".tweet-content",".timeline-item .content"]
            }
            for sel in seletores.get(tipo, [".content"]):
                elementos = await page.query_selector_all(sel)
                for el in elementos[:50]:
                    txt = (await el.inner_text()).strip()
                    if len(txt)>20:
                        publicacoes.append(criar_pub(
                            f"{tipo}_{nome}_{hashlib.md5(txt[:40].encode()).hexdigest()[:8]}",
                            txt, tipo, url))
                if publicacoes: break

            await browser.close()
    except ImportError:
        logger.error("Playwright não instalado: pip install playwright && playwright install chromium")
    except Exception as e:
        logger.error(f"  Playwright {nome} erro: {e}")
    logger.info(f"  Playwright {nome}: {len(publicacoes)} posts")
    return publicacoes

async def raspar_todas_playwright():
    sem = asyncio.Semaphore(2)
    async def com_sem(url, tipo):
        async with sem: return await raspar_playwright(url, tipo)
    res = await asyncio.gather(
        *[com_sem(u,"facebook") for u in PAGINAS_FACEBOOK],
        *[com_sem(u,"nitter")   for u in PERFIS_NITTER],
        return_exceptions=True
    )
    return [p for r in res if isinstance(r, list) for p in r]


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 3 — TELEGRAM via t.me/s/ (SEM API, SEM SUBSCRIÇÃO)
# ═══════════════════════════════════════════════════════════════════════════════
def _converter_vistas(s):
    try:
        s = s.strip().upper().replace(",",".")
        if "K" in s: return int(float(s.replace("K",""))*1000)
        if "M" in s: return int(float(s.replace("M",""))*1_000_000)
        return int(s) if s.isdigit() else 0
    except: return 0

async def raspar_telegram_canal(canal, session):
    """
    Raspa mensagens de um canal público do Telegram via t.me/s/.

    MÉTODO: O Telegram expõe todos os canais públicos em
    https://t.me/s/{canal} — HTML público sem autenticação.

    NAVEGAÇÃO PAGINADA:
    - Página 1: https://t.me/s/{canal}
    - Página N: https://t.me/s/{canal}?before={id_mais_antigo}

    SEM CUSTO · SEM CONTA · SEM API · SEM SUBSCRIÇÃO
    """
    publicacoes = []
    url_base    = f"https://t.me/s/{canal}"
    url_actual  = url_base
    pagina      = 0

    while pagina < 10 and len(publicacoes) < MAX_MSGS_TELEGRAM:
        pagina += 1
        try:
            async with session.get(url_actual,
                                   timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 404:
                    logger.warning(f"  @{canal}: não encontrado (404)")
                    break
                if resp.status != 200:
                    logger.warning(f"  @{canal}: HTTP {resp.status}")
                    break
                html = await resp.text(encoding="utf-8", errors="ignore")

            soup   = BeautifulSoup(html, "lxml")
            blocos = soup.select(".tgme_widget_message_wrap")
            if not blocos: break

            msgs_pag = []
            for bloco in blocos:
                try:
                    msg_div  = bloco.select_one(".tgme_widget_message[data-post]")
                    if not msg_div: continue
                    data_post = msg_div.get("data-post","")
                    msg_id    = data_post.replace("/","_")

                    texto_el  = bloco.select_one(".tgme_widget_message_text") or                                 bloco.select_one(".tgme_widget_message_caption")
                    texto = texto_el.get_text(separator=" ",strip=True) if texto_el else ""
                    if len(texto)<10: continue

                    time_el  = bloco.select_one("time[datetime]")
                    data_str = time_el.get("datetime") if time_el else None

                    url_el   = bloco.select_one("a.tgme_widget_message_date")
                    url_msg  = url_el.get("href","") if url_el else f"https://t.me/{canal}"

                    vistas_el = bloco.select_one(".tgme_widget_message_views")
                    vistas    = _converter_vistas(vistas_el.get_text(strip=True)) if vistas_el else 0

                    msgs_pag.append(criar_pub(
                        f"tg_{canal}_{msg_id}", texto, "telegram",
                        url_msg, data_str, canal=canal, vistas=vistas))
                except Exception: continue

            publicacoes.extend(msgs_pag)
            logger.info(f"  @{canal} pág.{pagina}: {len(msgs_pag)} msgs (total {len(publicacoes)})")

            # ID mais antigo para próxima página
            ids = [int(b.select_one(".tgme_widget_message[data-post]")
                       .get("data-post","0").split("/")[-1])
                   for b in blocos
                   if b.select_one(".tgme_widget_message[data-post]")]
            if not ids or min(ids)<=1: break
            url_actual = f"{url_base}?before={min(ids)}"
            await asyncio.sleep(DELAY_PEDIDOS)

        except Exception as e:
            logger.error(f"  @{canal} pág.{pagina} erro: {e}")
            break

    logger.info(f"  @{canal}: {len(publicacoes)} mensagens no total")
    return publicacoes

async def raspar_todos_telegram():
    """Raspa todos os canais Telegram via t.me/s/ (sem API, sem subscrição)."""
    headers = {"User-Agent": random.choice(USER_AGENTS),
               "Accept-Language": "pt-PT,pt;q=0.9"}
    async with aiohttp.ClientSession(headers=headers) as session:
        todas = []
        for canal in CANAIS_TELEGRAM:
            pubs = await raspar_telegram_canal(canal, session)
            todas.extend(pubs)
            await asyncio.sleep(DELAY_PEDIDOS*2)  # pausa entre canais
    return todas


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER 4 — yt-dlp (YouTube + TikTok)
# ═══════════════════════════════════════════════════════════════════════════════
async def raspar_youtube(termo, max_videos=15):
    """Recolhe metadados YouTube via yt-dlp sem API key."""
    publicacoes = []
    try:
        cmd = ["yt-dlp", f"ytsearch{max_videos}:{termo}",
               "--dump-json","--no-download","--skip-download","--quiet","--no-warnings"]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        for linha in stdout.decode("utf-8", errors="ignore").splitlines():
            if not linha.strip(): continue
            try:
                m    = json.loads(linha)
                txt  = f"{m.get('title','')}. {m.get('description','')[:400]}".strip()
                if len(txt)<15: continue
                d    = m.get("upload_date","")
                data = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d)==8 else None
                pub  = criar_pub(m.get("id",txt), txt, "youtube",
                                 m.get("webpage_url",""), data,
                                 vistas=m.get("view_count",0),
                                 canal_yt=m.get("uploader",""))
                publicacoes.append(pub)
            except json.JSONDecodeError: continue
    except FileNotFoundError:
        logger.error("yt-dlp não encontrado: pip install yt-dlp")
    except Exception as e:
        logger.error(f"yt-dlp erro: {e}")
    return publicacoes

async def raspar_todo_youtube():
    res = await asyncio.gather(*[raspar_youtube(t) for t in PESQUISAS_YOUTUBE],
                               return_exceptions=True)
    return [p for r in res if isinstance(r, list) for p in r]


# ═══════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR OSINT — Pipeline completo
# ═══════════════════════════════════════════════════════════════════════════════
async def pipeline_osint_completo():
    """
    Executa um ciclo completo de recolha OSINT.

    Stack 100% gratuito:
      Scrapy/aiohttp → Sites de notícias
      Playwright     → Facebook + X/Nitter
      t.me/s/        → Telegram canais públicos (SEM API)
      yt-dlp         → YouTube + TikTok
    """
    inicio = time.time()
    logger.info("="*60)
    logger.info("PIPELINE OSINT — UAN 2026 — Manuel Muinga")
    logger.info("="*60)

    # 1. Sites de notícias
    logger.info("[1/4] Scrapy: sites de notícias angolanos...")
    pubs_noticias  = await raspar_todas_noticias()

    # 2. Facebook + Nitter
    logger.info("[2/4] Playwright: Facebook + Nitter...")
    pubs_playwright = await raspar_todas_playwright()

    # 3. Telegram via t.me/s/ (SEM API, SEM SUBSCRIÇÃO)
    logger.info("[3/4] t.me/s/: Telegram canais públicos (sem API)...")
    pubs_telegram   = await raspar_todos_telegram()

    # 4. YouTube
    logger.info("[4/4] yt-dlp: YouTube Angola...")
    pubs_youtube    = await raspar_todo_youtube()

    # Agregar e deduplicar
    todas = pubs_noticias + pubs_playwright + pubs_telegram + pubs_youtube
    ids_vistos = set()
    unicas = []
    for p in todas:
        if p["id_externo"] not in ids_vistos:
            ids_vistos.add(p["id_externo"])
            unicas.append(p)

    # Guardar MongoDB
    inseridas = guardar_mongodb(unicas)

    logger.info("="*60)
    logger.info(f"  Notícias (Scrapy)  : {len(pubs_noticias)}")
    logger.info(f"  Facebook + Nitter  : {len(pubs_playwright)}")
    logger.info(f"  Telegram (t.me/s/) : {len(pubs_telegram)}")
    logger.info(f"  YouTube (yt-dlp)   : {len(pubs_youtube)}")
    logger.info(f"  Total recolhido    : {len(todas)}")
    logger.info(f"  Únicas (após dedup): {len(unicas)}")
    logger.info(f"  Inseridas MongoDB  : {inseridas}")
    logger.info(f"  Duração            : {time.time()-inicio:.1f}s")
    logger.info("="*60)

    return {"total": len(todas), "unicas": len(unicas), "inseridas": inseridas}


if __name__ == "__main__":
    asyncio.run(pipeline_osint_completo())
