"""
=============================================================================
MÓDULO — Scraper Telegram via t.me/s/ (Sem API, Sem Subscrição, Sem Login)
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola

PROBLEMA ANTERIOR:
  - Telethon MTProto exige subscrição paga desde 2025
  - Bot Token exige ser administrador do canal

SOLUÇÃO OSINT (100% gratuita, sem conta, sem subscrição):
  - O Telegram expõe TODOS os canais públicos em:
    https://t.me/s/{username}
  - Esta página é HTML puro renderizado pelo servidor do Telegram
  - Não requer: API key · token · número de telefone · conta · subscrição
  - É a mesma página que o Google usa para indexar canais do Telegram
  - Técnica: aiohttp + BeautifulSoup (parsing HTML assíncrono)

SO: Windows 10/11 (64-bit) | Google Colab Pro
Instalação: pip install aiohttp beautifulsoup4 lxml
=============================================================================
"""

import asyncio
import hashlib
import re
import time
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiohttp
import pymongo
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

load_dotenv()

# ─── Logging (UTF-8 para Windows) ────────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "telegram_osint.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("TelegramOSINT")

# ─── Configuração ─────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DELAY_ENTRE_PEDIDOS = 2.5   # segundos entre pedidos (evitar bloqueio)
MAX_MENSAGENS_POR_CANAL = 200
MAX_PAGINAS_POR_CANAL   = 10  # cada página tem ~20 mensagens

# URL base para preview pública do Telegram (sem autenticação)
TELEGRAM_PREVIEW_URL = "https://t.me/s/{canal}"

# User-Agents rotativos (simular navegadores reais)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
]

# Canais públicos angolanos no Telegram
CANAIS_TELEGRAM_ANGOLA = [
    "angola_noticias",
    "luanda_hoje",
    "angola_actualidade",
    "angola_seguranca",
    "angola_politica",
    "verangola",
    "rna_angola",
    "jornaldeangola",
    "expansao_angola",
]

PROVINCIAS_ANGOLA = [
    "Luanda", "Benguela", "Huambo", "Bié", "Malanje",
    "Huíla", "Cabinda", "Cunene", "Namibe", "Zaire",
    "Uíge", "Kwanza Norte", "Kwanza Sul", "Lunda Norte",
    "Lunda Sul", "Moxico", "Cuando Cubango", "Bengo",
]


# ─── Utilitários ─────────────────────────────────────────────────────────────
def sha256(s: str) -> str:
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()[:16]


def detectar_provincia(texto: str) -> str:
    t = texto.lower()
    return next((p for p in PROVINCIAS_ANGOLA if p.lower() in t), "Luanda")


def criar_publicacao(id_ext, texto, url="", data=None, vistas=0, canal=""):
    return {
        "id_externo":    sha256(id_ext),
        "texto":         texto.strip()[:3000],
        "plataforma":    "telegram",
        "url_origem":    url,
        "canal":         canal,
        "provincia":     detectar_provincia(texto),
        "data":          data or datetime.now(timezone.utc).isoformat(),
        "recolhido_em":  datetime.now(timezone.utc).isoformat(),
        "vistas":        vistas,
        "metodo":        "OSINT_tme_preview",
        "classificado":  False,
        "preprocessado": False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCRAPER PRINCIPAL — t.me/s/ (preview pública do Telegram)
# ═══════════════════════════════════════════════════════════════════════════════
class TelegramScraperOSINT:
    """
    Scraper OSINT para canais públicos do Telegram via t.me/s/.

    Como funciona:
    1. Acede a https://t.me/s/{canal} — página HTML pública do Telegram
    2. Analisa o HTML com BeautifulSoup para extrair mensagens
    3. Navega para páginas anteriores via parâmetro ?before={id}
    4. Sem API, sem token, sem conta, sem subscrição

    Limitações:
    - Apenas canais PÚBLICOS com preview web activada
    - Máximo ~100 mensagens por página
    - Sem acesso a grupos privados ou mensagens privadas
    - Algumas imagens/vídeos podem não estar acessíveis

    Vantagem para OSINT académico:
    - 100% gratuito e sustentável
    - Sem dependência de credenciais que podem ser revogadas
    - Respeita os termos do Telegram para conteúdo público
    - Replicável por qualquer investigador sem registo prévio
    """

    def __init__(self):
        self.session = None

    async def _criar_sessao(self) -> aiohttp.ClientSession:
        """Cria uma sessão HTTP assíncrona com cabeçalhos de navegador."""
        headers = {
            "User-Agent":      random.choice(USER_AGENTS),
            "Accept":          "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection":      "keep-alive",
            "DNT":             "1",
        }
        return aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
            connector=aiohttp.TCPConnector(ssl=False),
        )

    def _extrair_mensagens_html(self, html: str, canal: str) -> list:
        """
        Analisa o HTML da página t.me/s/{canal} e extrai as mensagens.

        Estrutura HTML do Telegram (t.me/s/):
          <div class="tgme_widget_message_wrap">
            <div class="tgme_widget_message" data-post="{canal}/{id}">
              <div class="tgme_widget_message_text">Texto da mensagem</div>
              <time datetime="2025-08-01T10:00:00+00:00">...</time>
              <span class="tgme_widget_message_views">1.2K</span>
            </div>
          </div>
        """
        soup = BeautifulSoup(html, "lxml")
        mensagens = []

        # Cada mensagem está num bloco .tgme_widget_message_wrap
        blocos = soup.select(".tgme_widget_message_wrap")

        for bloco in blocos:
            try:
                # ID da mensagem (formato: canal/123)
                msg_div = bloco.select_one(".tgme_widget_message[data-post]")
                if not msg_div:
                    continue
                data_post = msg_div.get("data-post", "")
                msg_id    = data_post.replace("/", "_")

                # Texto da mensagem
                texto_el = bloco.select_one(".tgme_widget_message_text")
                if not texto_el:
                    # Tentar outros selectores (mensagens com apenas imagem, etc.)
                    texto_el = bloco.select_one(".tgme_widget_message_caption")
                texto = texto_el.get_text(separator=" ", strip=True) if texto_el else ""

                # Ignorar mensagens sem texto suficiente
                if len(texto) < 10:
                    continue

                # Data da mensagem
                time_el = bloco.select_one("time[datetime]")
                data_str = time_el.get("datetime") if time_el else None

                # URL da mensagem
                url_el = bloco.select_one("a.tgme_widget_message_date")
                url = url_el.get("href", "") if url_el else f"https://t.me/{canal}"

                # Número de visualizações
                vistas_el = bloco.select_one(".tgme_widget_message_views")
                vistas_str = vistas_el.get_text(strip=True) if vistas_el else "0"
                # Converter "1.2K" → 1200, "5.3M" → 5300000
                vistas = self._converter_vistas(vistas_str)

                pub = criar_publicacao(
                    id_ext=f"tg_{canal}_{msg_id}",
                    texto=texto,
                    url=url,
                    data=data_str,
                    vistas=vistas,
                    canal=canal,
                )
                mensagens.append(pub)

            except Exception as e:
                logger.debug(f"Erro a extrair mensagem: {e}")
                continue

        return mensagens

    def _converter_vistas(self, vistas_str: str) -> int:
        """Converte '1.2K' → 1200, '5.3M' → 5300000, '123' → 123."""
        try:
            v = vistas_str.strip().upper().replace(",", ".")
            if "K" in v:
                return int(float(v.replace("K", "")) * 1000)
            elif "M" in v:
                return int(float(v.replace("M", "")) * 1000000)
            else:
                return int(v) if v.isdigit() else 0
        except Exception:
            return 0

    def _obter_id_mais_antigo(self, html: str) -> Optional[int]:
        """
        Extrai o ID da mensagem mais antiga da página,
        para navegação para páginas anteriores (?before={id}).
        """
        soup = BeautifulSoup(html, "lxml")
        blocos = soup.select(".tgme_widget_message[data-post]")
        if not blocos:
            return None
        # O primeiro bloco tem a mensagem mais antiga da página
        data_post = blocos[0].get("data-post", "")
        partes = data_post.split("/")
        try:
            return int(partes[-1])
        except (ValueError, IndexError):
            return None

    async def raspar_canal(self, canal: str) -> list:
        """
        Raspa todas as mensagens públicas de um canal do Telegram.

        Navegação paginada:
          1ª página: https://t.me/s/{canal}
          2ª página: https://t.me/s/{canal}?before={id_mais_antigo}
          ... e assim sucessivamente

        Args:
            canal: Username do canal (sem @), ex: 'angola_noticias'

        Returns:
            Lista de publicações no formato padronizado.
        """
        todas_mensagens = []
        url_base = TELEGRAM_PREVIEW_URL.format(canal=canal)
        url_actual = url_base
        pagina = 0

        async with await self._criar_sessao() as session:
            while pagina < MAX_PAGINAS_POR_CANAL:
                pagina += 1
                logger.info(f"  Telegram @{canal}: página {pagina}...")

                try:
                    async with session.get(url_actual) as resp:
                        if resp.status == 404:
                            logger.warning(f"  @{canal}: canal não encontrado (404)")
                            break
                        if resp.status != 200:
                            logger.warning(f"  @{canal}: HTTP {resp.status}")
                            break

                        html = await resp.text(encoding="utf-8", errors="ignore")

                    # Extrair mensagens desta página
                    mensagens_pagina = self._extrair_mensagens_html(html, canal)

                    if not mensagens_pagina:
                        logger.info(f"  @{canal}: sem mais mensagens na página {pagina}")
                        break

                    todas_mensagens.extend(mensagens_pagina)
                    logger.info(
                        f"  @{canal}: {len(mensagens_pagina)} msgs na pág. {pagina} "
                        f"(total: {len(todas_mensagens)})"
                    )

                    # Verificar se atingimos o limite
                    if len(todas_mensagens) >= MAX_MENSAGENS_POR_CANAL:
                        break

                    # Obter ID mais antigo para navegar para a página anterior
                    id_mais_antigo = self._obter_id_mais_antigo(html)
                    if not id_mais_antigo or id_mais_antigo <= 1:
                        break

                    # URL da próxima página (mensagens mais antigas)
                    url_actual = f"{url_base}?before={id_mais_antigo}"

                    # Delay entre pedidos (respeitar rate limiting do Telegram)
                    await asyncio.sleep(DELAY_ENTRE_PEDIDOS)

                except aiohttp.ClientError as e:
                    logger.error(f"  @{canal} erro de rede: {e}")
                    break
                except asyncio.TimeoutError:
                    logger.error(f"  @{canal}: timeout na página {pagina}")
                    break
                except Exception as e:
                    logger.error(f"  @{canal} erro inesperado: {e}")
                    break

        logger.info(f"  @{canal}: {len(todas_mensagens)} mensagens recolhidas (total)")
        return todas_mensagens

    async def raspar_todos_canais(self, canais: list = None) -> list:
        """
        Raspa todos os canais angolanos configurados.
        Execução sequencial para respeitar os rate limits do Telegram.
        """
        if canais is None:
            canais = CANAIS_TELEGRAM_ANGOLA

        todas = []
        for canal in canais:
            mensagens = await self.raspar_canal(canal)
            todas.extend(mensagens)
            # Pausa entre canais
            await asyncio.sleep(DELAY_ENTRE_PEDIDOS * 2)

        return todas

    async def testar_canal(self, canal: str) -> dict:
        """
        Testa se um canal é acessível via t.me/s/.
        Útil para verificar antes de executar a recolha completa.
        """
        url = TELEGRAM_PREVIEW_URL.format(canal=canal)
        async with await self._criar_sessao() as session:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return {"canal": canal, "acessivel": False, "estado": resp.status}
                    html = await resp.text()
                    msgs = self._extrair_mensagens_html(html, canal)
                    soup = BeautifulSoup(html, "lxml")
                    titulo_el = soup.select_one(".tgme_page_title span")
                    titulo = titulo_el.get_text(strip=True) if titulo_el else canal
                    subs_el = soup.select_one(".tgme_page_extra")
                    subs = subs_el.get_text(strip=True) if subs_el else "?"
                    return {
                        "canal":         canal,
                        "acessivel":     True,
                        "titulo":        titulo,
                        "subscritores":  subs,
                        "msgs_na_pagina": len(msgs),
                        "url":           url,
                    }
            except Exception as e:
                return {"canal": canal, "acessivel": False, "erro": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# GUARDAR NO MONGODB
# ═══════════════════════════════════════════════════════════════════════════════
def guardar_mongodb(publicacoes: list, uri: str = None) -> int:
    """Guarda publicações no MongoDB Atlas, ignorando duplicatas."""
    uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    if not publicacoes:
        return 0
    try:
        client  = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
        colecao = client["dissertacao_angola"]["publicacoes_brutas"]
        inseridos = 0
        for pub in publicacoes:
            r = colecao.update_one(
                {"id_externo": pub["id_externo"]},
                {"$setOnInsert": pub},
                upsert=True,
            )
            if r.upserted_id:
                inseridos += 1
        client.close()
        logger.info(f"MongoDB: {inseridos} novas publicações inseridas.")
        return inseridos
    except Exception as e:
        logger.error(f"MongoDB erro: {e}")
        return 0


# ═══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════
async def main():
    scraper = TelegramScraperOSINT()

    print("=" * 60)
    print("SCRAPER TELEGRAM OSINT — t.me/s/ (sem API, sem subscrição)")
    print("Dissertação UAN — Manuel Muinga 2026")
    print("=" * 60)

    # 1. Testar acessibilidade dos canais
    print("\n[1/3] A testar acessibilidade dos canais...")
    canais_acessiveis = []
    for canal in CANAIS_TELEGRAM_ANGOLA[:5]:  # testar primeiros 5
        resultado = await scraper.testar_canal(canal)
        estado = "✅" if resultado["acessivel"] else "❌"
        print(f"  {estado} @{canal}: {resultado.get('titulo', '?')} "
              f"({resultado.get('subscritores', '?')}) — "
              f"{resultado.get('msgs_na_pagina', 0)} msgs visíveis")
        if resultado["acessivel"]:
            canais_acessiveis.append(canal)
        await asyncio.sleep(1)

    print(f"\n  {len(canais_acessiveis)}/{len(CANAIS_TELEGRAM_ANGOLA[:5])} "
          f"canais acessíveis via t.me/s/")

    # 2. Recolher mensagens
    print("\n[2/3] A recolher mensagens dos canais acessíveis...")
    if canais_acessiveis:
        publicacoes = await scraper.raspar_todos_canais(canais_acessiveis)
    else:
        print("  ⚠️  Nenhum canal acessível. A usar canais de demonstração...")
        publicacoes = await scraper.raspar_todos_canais(["telegram", "durov"])

    # 3. Guardar MongoDB
    print(f"\n[3/3] A guardar {len(publicacoes)} publicações no MongoDB...")
    inseridas = guardar_mongodb(publicacoes)

    print("\n" + "=" * 60)
    print(f"✅ CONCLUÍDO:")
    print(f"   Mensagens recolhidas : {len(publicacoes)}")
    print(f"   Inseridas MongoDB    : {inseridas}")
    print(f"   Método               : t.me/s/ (OSINT, sem API)")
    print(f"   Custo                : 0 USD")
    print("=" * 60)

    # Mostrar exemplos
    if publicacoes:
        print("\n📋 Exemplos recolhidos:")
        for p in publicacoes[:3]:
            print(f"  Canal  : @{p['canal']}")
            print(f"  Texto  : {p['texto'][:80]}...")
            print(f"  Vistas : {p['vistas']:,}")
            print(f"  Prov.  : {p['provincia']}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
