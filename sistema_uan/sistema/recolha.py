"""Recolha automática de conteúdo público.

Duas vias, ambas declaradas por lote:

- **YouTube Data API v3** (via `api_oficial`): comentários públicos de vídeos ou dos
  vídeos mais recentes de um canal. Precisa de uma chave da API (`UAN_YOUTUBE_CHAVE`).
- **Páginas web públicas** (via `scraping_publico`): páginas de notícias, comunicados
  e outros sítios abertos, e feeds RSS/Atom. Recolhe título e primeiros parágrafos
  (o mesmo formato «título + lead» das notícias do piloto).

Regras aplicadas na recolha web, para ficar dentro do que a metodologia permite:
- só `http`/`https`, sem cookies, sem sessão, sem JavaScript e sem preencher formulários;
- respeita o `robots.txt` de cada sítio e identifica-se com um agente próprio;
- pausa entre pedidos ao mesmo sítio e limite de páginas por recolha;
- páginas que pedem autenticação (401/403, formulários de palavra-passe) são ignoradas,
  nunca contornadas.

Comentários carregados por JavaScript (Disqus, Facebook e semelhantes) não são
recolhidos: exigiriam executar código da página ou usar sessões, o que fica fora
destas regras.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser

from .base_dados import BaseDados, agora
from .config import Config
from .servico import importar_registos

log = logging.getLogger(__name__)

TIPOS = {
    "youtube_video": "Vídeo do YouTube (comentários)",
    "youtube_canal": "Canal do YouTube (vídeos recentes)",
    "rss": "Feed RSS/Atom",
    "pagina": "Página web pública",
    "sitio": "Sítio web público (página inicial e ligações)",
}
TIPOS_YOUTUBE = ("youtube_video", "youtube_canal")
MAX_BYTES = 3 * 1024 * 1024
LEAD_CARACTERES = 700


class ErroRecolha(Exception):
    pass


# ----------------------------------------------------------------------------- HTTP
@dataclass
class Resposta:
    estado: int
    tipo: str
    corpo: bytes
    url: str

    def texto(self) -> str:
        m = re.search(r"charset=([\w-]+)", self.tipo or "", re.I)
        for cod in ([m.group(1)] if m else []) + ["utf-8", "latin-1"]:
            try:
                return self.corpo.decode(cod)
            except (LookupError, UnicodeDecodeError):
                continue
        return self.corpo.decode("utf-8", "replace")


class ClienteHTTP:
    """Cliente simples, sem cookies, com robots.txt e pausa por sítio."""

    def __init__(self, agente: str, intervalo_s: float = 3.0, timeout_s: float = 20.0):
        self.agente = agente
        self.intervalo_s = intervalo_s
        self.timeout_s = timeout_s
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._ultimo: dict[str, float] = {}

    def _pedido(self, url: str) -> Resposta:
        req = urllib.request.Request(url, headers={"User-Agent": self.agente, "Accept-Language": "pt,pt-AO;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                corpo = r.read(MAX_BYTES + 1)
                return Resposta(r.status, r.headers.get("Content-Type", ""), corpo[:MAX_BYTES], r.geturl())
        except urllib.error.HTTPError as e:
            return Resposta(e.code, e.headers.get("Content-Type", "") if e.headers else "", b"", url)

    def permitido(self, url: str) -> bool:
        p = urllib.parse.urlsplit(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self._pedido(base + "/robots.txt")
                if r.estado >= 400:
                    rp = None  # sem robots.txt: tudo permitido
                else:
                    rp.parse(r.texto().splitlines())
            except (urllib.error.URLError, OSError, ValueError):
                rp = None
            self._robots[base] = rp
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(self.agente, url)

    def obter(self, url: str, verificar_robots: bool = True) -> Resposta:
        p = urllib.parse.urlsplit(url)
        if p.scheme not in ("http", "https") or not p.netloc:
            raise ErroRecolha(f"Endereço inválido: {url}")
        if verificar_robots and not self.permitido(url):
            raise ErroRecolha(f"O robots.txt do sítio não permite recolher {url}")
        espera = self._ultimo.get(p.netloc, 0) + self.intervalo_s - time.monotonic()
        if espera > 0:
            time.sleep(espera)
        try:
            r = self._pedido(url)
        except (urllib.error.URLError, OSError) as e:
            raise ErroRecolha(f"Falha de ligação a {url}: {e}") from e
        finally:
            self._ultimo[p.netloc] = time.monotonic()
        if r.estado in (401, 403, 407):
            raise ErroRecolha(f"{url} exige autenticação ou recusou o acesso ({r.estado}); não é recolhido.")
        if r.estado >= 400:
            raise ErroRecolha(f"{url} respondeu com o código {r.estado}.")
        return r


# ----------------------------------------------------------------------------- HTML
class _Extractor(HTMLParser):
    IGNORAR = {"script", "style", "noscript", "nav", "footer", "aside", "form", "header", "svg", "iframe", "button"}
    BLOCOS = {"p", "h1", "h2", "h3", "li", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.titulo = ""
        self._em_titulo = False
        self.ignorar = 0
        self.dentro_artigo = 0
        self.blocos: list[tuple[str, str, bool]] = []  # (etiqueta, texto, dentro de <article>)
        self._bloco: list[str] | None = None
        self._etq = ""
        self.ligacoes: list[str] = []
        self.tem_senha = False
        self.datas: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k and a.get("content"):
                self.meta[k] = a["content"].strip()
        elif tag == "title":
            self._em_titulo = True
        elif tag == "a" and a.get("href"):
            self.ligacoes.append(a["href"])
        elif tag == "input" and (a.get("type") or "").lower() == "password":
            self.tem_senha = True
        elif tag == "time" and a.get("datetime"):
            self.datas.append(a["datetime"])
        if tag in self.IGNORAR:
            self.ignorar += 1
        if tag == "article":
            self.dentro_artigo += 1
        if tag in self.BLOCOS and not self.ignorar:
            self._bloco, self._etq = [], tag

    def handle_endtag(self, tag):
        if tag == "title":
            self._em_titulo = False
        if tag in self.IGNORAR and self.ignorar:
            self.ignorar -= 1
        if tag == "article" and self.dentro_artigo:
            self.dentro_artigo -= 1
        if tag == self._etq and self._bloco is not None:
            texto = re.sub(r"\s+", " ", "".join(self._bloco)).strip()
            if texto:
                self.blocos.append((self._etq, texto, self.dentro_artigo > 0))
            self._bloco = None

    def handle_data(self, data):
        if self._em_titulo:
            self.titulo += data
        if self._bloco is not None and not self.ignorar:
            self._bloco.append(data)


@dataclass
class Pagina:
    url: str
    titulo: str
    lead: str
    data: str | None
    ligacoes: list[str] = field(default_factory=list)
    requer_login: bool = False


def extrair_pagina(html: str, url: str) -> Pagina:
    ex = _Extractor()
    ex.feed(html)
    titulo = ex.meta.get("og:title") or ex.titulo or next((t for e, t, _ in ex.blocos if e == "h1"), "")
    titulo = re.sub(r"\s+", " ", titulo).strip()
    no_artigo = [t for e, t, art in ex.blocos if art and e in ("p", "blockquote")]
    paragrafos = no_artigo or [t for e, t, _ in ex.blocos if e == "p"]
    paragrafos = [p for p in paragrafos if len(p) >= 40]  # descarta legendas, botões e restos de menus
    lead = ""
    for p in paragrafos:
        if len(lead) >= LEAD_CARACTERES:
            break
        lead = (lead + " " + p).strip()
    if not lead:
        lead = ex.meta.get("og:description") or ex.meta.get("description") or ""
    if len(lead) > LEAD_CARACTERES + 300:
        lead = lead[: LEAD_CARACTERES + 300].rsplit(" ", 1)[0] + " (…)"
    data = ex.meta.get("article:published_time") or (ex.datas[0] if ex.datas else None)
    ligacoes = []
    for h in ex.ligacoes:
        absoluto = urllib.parse.urljoin(url, h.split("#")[0])
        if absoluto.startswith(("http://", "https://")):
            ligacoes.append(absoluto)
    return Pagina(url, titulo, lead, data, ligacoes, ex.tem_senha and not paragrafos)


def _limpar_html(texto: str) -> str:
    texto = re.sub(r"<[^>]+>", " ", texto or "")
    from html import unescape
    return re.sub(r"\s+", " ", unescape(texto)).strip()


def extrair_feed(xml: str) -> list[dict]:
    """Itens de um feed RSS 2.0 ou Atom: título, ligação, resumo e data."""
    try:
        raiz = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    except ET.ParseError as e:
        raise ErroRecolha(f"Feed inválido: {e}") from e
    itens = []
    for it in raiz.iter():
        nome = it.tag.split("}")[-1]
        if nome not in ("item", "entry"):
            continue
        campos = {c.tag.split("}")[-1]: c for c in it}
        ligacao = ""
        if "link" in campos:
            ligacao = campos["link"].get("href") or (campos["link"].text or "")
        resumo = ""
        for k in ("description", "summary", "content", "encoded"):
            if k in campos and (campos[k].text or "").strip():
                resumo = campos[k].text
                break
        data = next(((campos[k].text or "").strip() for k in ("pubDate", "published", "updated", "date") if k in campos), None)
        itens.append({"titulo": _limpar_html(campos["title"].text if "title" in campos else ""),
                      "ligacao": ligacao.strip(), "resumo": _limpar_html(resumo), "data": data,
                      "id": (campos["guid"].text if "guid" in campos else None) or (campos["id"].text if "id" in campos else None)})
    return itens


def _parece_artigo(url: str, base: str) -> bool:
    p = urllib.parse.urlsplit(url)
    if p.netloc != urllib.parse.urlsplit(base).netloc:
        return False
    caminho = p.path.lower()
    if re.search(r"\.(jpg|jpeg|png|gif|pdf|mp4|mp3|zip|css|js|svg|webp)$", caminho):
        return False
    if any(x in caminho for x in ("/tag/", "/categoria", "/category/", "/autor/", "/author/", "/login", "/conta",
                                  "/wp-admin", "/feed", "/search", "/pesquisa")):
        return False
    segmentos = [s for s in caminho.split("/") if s]
    return bool(segmentos) and (len(segmentos[-1]) >= 20 or bool(re.search(r"/20\d\d/", caminho)))


# ----------------------------------------------------------------------------- recolhedores
def _registo_web(pag: Pagina, nome_fonte: str) -> dict | None:
    texto = (pag.titulo + (" — " if pag.titulo and pag.lead else "") + pag.lead).strip()
    if len(texto) < 20:
        return None
    return {"id": pag.url, "texto": texto, "data": pag.data, "contexto": nome_fonte}


def recolher_web(fonte: dict, cliente: ClienteHTTP, max_paginas: int) -> tuple[list[dict], list[str]]:
    tipo, url, nome = fonte["tipo"], fonte["endereco"], fonte["nome"]
    limite = min(max_paginas, fonte.get("max_itens") or max_paginas)
    registos, avisos = [], []

    def pagina(u):
        r = cliente.obter(u)
        if "html" not in (r.tipo or "").lower() and r.tipo:
            raise ErroRecolha(f"{u} não é uma página HTML ({r.tipo}).")
        pag = extrair_pagina(r.texto(), r.url)
        if pag.requer_login:
            raise ErroRecolha(f"{u} pede autenticação; não é recolhida.")
        return pag

    if tipo == "pagina":
        reg = _registo_web(pagina(url), nome)
        if reg:
            registos.append(reg)
    elif tipo == "sitio":
        inicio = pagina(url)
        candidatos, vistos = [], set()
        for l in inicio.ligacoes:
            if l not in vistos and l != url and _parece_artigo(l, url):
                vistos.add(l)
                candidatos.append(l)
        for l in candidatos[:limite]:
            try:
                reg = _registo_web(pagina(l), nome)
                if reg:
                    registos.append(reg)
            except ErroRecolha as e:
                avisos.append(str(e))
    elif tipo == "rss":
        r = cliente.obter(url)
        for it in extrair_feed(r.texto())[:limite]:
            texto = it["titulo"]
            resumo = it["resumo"]
            if len(resumo) < 80 and it["ligacao"]:
                try:
                    resumo = pagina(it["ligacao"]).lead or resumo
                except ErroRecolha as e:
                    avisos.append(str(e))
            texto = (texto + (" — " if texto and resumo else "") + resumo[: LEAD_CARACTERES + 300]).strip()
            if len(texto) >= 20:
                registos.append({"id": it["id"] or it["ligacao"] or texto[:80], "texto": texto, "data": it["data"],
                                 "contexto": nome})
    else:
        raise ErroRecolha(f"Tipo de fonte web desconhecido: {tipo}")
    return registos, avisos


class ClienteYouTube:
    BASE = "https://www.googleapis.com/youtube/v3/"

    def __init__(self, chave: str, http: ClienteHTTP):
        if not chave:
            raise ErroRecolha("Defina UAN_YOUTUBE_CHAVE no ficheiro uan.env para recolher do YouTube.")
        self.chave, self.http = chave, http

    def _api(self, recurso: str, **params) -> dict:
        params["key"] = self.chave
        url = self.BASE + recurso + "?" + urllib.parse.urlencode(params)
        r = self.http.obter(url, verificar_robots=False)  # API oficial, não é uma página web
        return json.loads(r.texto())

    def videos_do_canal(self, canal: str, n: int) -> list[dict]:
        canal = canal.strip()
        if "youtube.com/" in canal:
            canal = canal.rstrip("/").split("/")[-1]
        params = {"forHandle": canal} if canal.startswith("@") else {"id": canal}
        dados = self._api("channels", part="contentDetails,snippet", **params)
        if not dados.get("items"):
            raise ErroRecolha(f"Canal não encontrado: {canal}")
        uploads = dados["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        itens = self._api("playlistItems", part="snippet", playlistId=uploads, maxResults=min(n, 50)).get("items", [])
        return [{"id": i["snippet"]["resourceId"]["videoId"], "titulo": i["snippet"]["title"]} for i in itens]

    def comentarios(self, video: str, titulo: str, n: int) -> list[dict]:
        if "watch?v=" in video:
            video = urllib.parse.parse_qs(urllib.parse.urlsplit(video).query)["v"][0]
        elif "youtu.be/" in video:
            video = video.rstrip("/").split("/")[-1]
        out, pagina = [], None
        while len(out) < n:
            params = dict(part="snippet,replies", videoId=video, maxResults=100, order="time", textFormat="plainText")
            if pagina:
                params["pageToken"] = pagina
            dados = self._api("commentThreads", **params)
            for th in dados.get("items", []):
                for c in [th["snippet"]["topLevelComment"]] + th.get("replies", {}).get("comments", []):
                    s = c["snippet"]
                    out.append({"id": c["id"], "texto": s.get("textOriginal") or s.get("textDisplay", ""),
                                "autor": s.get("authorDisplayName"), "data": s.get("publishedAt"), "contexto": titulo})
            pagina = dados.get("nextPageToken")
            if not pagina:
                break
        return out[:n]


def recolher_youtube(fonte: dict, yt: ClienteYouTube) -> tuple[list[dict], list[str]]:
    n = fonte.get("max_itens") or 300
    if fonte["tipo"] == "youtube_video":
        return yt.comentarios(fonte["endereco"], fonte["nome"], n), []
    registos, avisos = [], []
    videos = yt.videos_do_canal(fonte["endereco"], 10)
    por_video = max(20, n // max(1, len(videos)))
    for v in videos:
        try:
            registos += yt.comentarios(v["id"], v["titulo"], por_video)
        except ErroRecolha as e:  # comentários desactivados, por exemplo
            avisos.append(f"{v['titulo']}: {e}")
        if len(registos) >= n:
            break
    return registos[:n], avisos


# ----------------------------------------------------------------------------- gestão das fontes
def adicionar_fonte(bd: BaseDados, tipo: str, endereco: str, nome: str, quem: str, max_itens: int = 100,
                    plataforma: str | None = None) -> int:
    if tipo not in TIPOS:
        raise ValueError(f"Tipo deve ser um de {list(TIPOS)}")
    endereco = endereco.strip()
    if tipo not in TIPOS_YOUTUBE and not endereco.startswith(("http://", "https://")):
        raise ValueError("O endereço de uma fonte web tem de começar por http:// ou https://")
    if not plataforma:
        plataforma = "YouTube" if tipo in TIPOS_YOUTUBE else (urllib.parse.urlsplit(endereco).hostname or "web").removeprefix("www.")
    with bd.ligacao() as c:
        cur = c.execute(
            """INSERT INTO fontes(tipo, endereco, nome, plataforma, max_itens, activa, criada_em, criada_por)
               VALUES (?,?,?,?,?,1,?,?)""",
            (tipo, endereco, nome.strip() or endereco, plataforma, max(1, min(int(max_itens), 2000)), agora(), quem))
        id_fonte = int(cur.lastrowid)
    bd.auditar(quem, "fonte_adicionada", {"id_fonte": id_fonte, "tipo": tipo, "endereco": endereco})
    return id_fonte


def recolher_fonte(bd: BaseDados, cfg: Config, id_fonte: int, quem: str = "sistema",
                   http: ClienteHTTP | None = None) -> dict:
    linhas = bd.consultar("SELECT * FROM fontes WHERE id_fonte = ?", (id_fonte,))
    if not linhas:
        raise ErroRecolha(f"Fonte {id_fonte} não existe.")
    fonte = dict(linhas[0])
    if not cfg.segredo_hash:
        raise ErroRecolha("Defina UAN_SEGREDO_HASH antes de recolher: os autores são anonimizados à entrada.")
    http = http or ClienteHTTP(cfg.recolha_agente, cfg.recolha_intervalo_s)
    t0 = time.perf_counter()
    try:
        if fonte["tipo"] in TIPOS_YOUTUBE:
            registos, avisos = recolher_youtube(fonte, ClienteYouTube(cfg.chave_youtube, http))
            via = "api_oficial"
        else:
            registos, avisos = recolher_web(fonte, http, cfg.recolha_max_paginas)
            via = "scraping_publico"
        info = importar_registos(bd, registos, fonte["plataforma"], via, cfg.segredo_hash,
                                 f"recolha automática: {fonte['nome']} ({TIPOS[fonte['tipo']]})", quem,
                                 fonte["endereco"][:200], id_fonte=fonte["id_fonte"])
        estado = f"ok: {info['novos']} novas de {info['validos']} recolhidas" + (f"; {len(avisos)} avisos" if avisos else "")
        info.update(avisos=avisos[:20], segundos=round(time.perf_counter() - t0, 1))
    except ErroRecolha as e:
        estado, info = f"erro: {e}", {"erro": str(e)}
    with bd.ligacao() as c:
        c.execute("UPDATE fontes SET ultima_recolha = ?, ultimo_estado = ? WHERE id_fonte = ?",
                  (agora(), estado[:300], id_fonte))
    bd.auditar(quem, "recolha", {"id_fonte": id_fonte, "estado": estado[:200]})
    return {"id_fonte": id_fonte, "nome": fonte["nome"], "estado": estado, **info}


def recolher_todas(bd: BaseDados, cfg: Config, quem: str = "sistema", progresso=None) -> list[dict]:
    fontes = bd.consultar("SELECT id_fonte FROM fontes WHERE activa = 1 ORDER BY id_fonte")
    http = ClienteHTTP(cfg.recolha_agente, cfg.recolha_intervalo_s)
    out = []
    for i, f in enumerate(fontes):
        out.append(recolher_fonte(bd, cfg, f["id_fonte"], quem, http))
        if progresso:
            progresso(i + 1, len(fontes))
    return out
