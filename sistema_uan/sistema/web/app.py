"""Aplicação web do sistema UAN (FastAPI + modelos Jinja2, sem compilação nem Node).

Arranque (Windows, cmd, na pasta sistema_uan):
    python uan.py servir
Depois, abrir http://127.0.0.1:8000 no navegador.

Páginas para analistas e supervisores, com sessão e papéis; API JSON em /api,
protegida por chave (cabeçalho X-Chave-API). Nenhuma decisão é automática: o
sistema ordena a revisão e regista o que o analista decide.
"""

from __future__ import annotations

import hmac
import html
import io
import json
import os
import logging
import re
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from pydantic import BaseModel, Field

from .. import alertas as al
from ..base_dados import BaseDados
from ..classificador import Classificador, ClassificadorDemonstracao, carregar_classificador
from ..geografia import PROVINCIAS, localizar_toponimos, mapa as mapa_geo
from ..config import NOMES_APRESENTACAO, PAPEIS, ROTULOS, Config, obter_config
from ..recolha import TIPOS as TIPOS_FONTE, ErroRecolha, adicionar_fonte, adicionar_fontes, recolher_fonte
from ..servico import (VIAS, classificacao_em_curso, classificar_pendentes, exportar_revisoes,
                       gerar_amostra_controlo, importar, metricas, panorama)
from ..utilizadores import (ErroAutenticacao, autenticar, criar_sessao, criar_utilizador, definir_activo,
                            mudar_senha, obter_sessao, terminar_sessao)

log = logging.getLogger(__name__)
PASTA = Path(__file__).resolve().parent
COOKIE = "uan_sessao"
LUANDA = timezone(timedelta(hours=1))  # Angola: UTC+1, sem hora de Verão
POR_PAGINA = 20

AVISOS = {
    "revisao": ("ok", "Decisão gravada."),
    "importado": ("ok", "Lote importado. A classificação corre em segundo plano."),
    "classificar": ("ok", "Classificação iniciada em segundo plano."),
    "ocupado": ("aviso", "Já há uma classificação em curso."),
    "amostra": ("ok", "Amostra de controlo criada."),
    "senha": ("ok", "Palavra-passe alterada."),
    "utilizador": ("ok", "Utilizador criado."),
    "estado": ("ok", "Estado do utilizador actualizado."),
    "definicoes": ("ok", "Definições gravadas."),
    "limpeza": ("ok", "Limpeza de conservação concluída."),
    "copia": ("ok", "Cópia de segurança criada na pasta dados\\copias."),
    "saiu": ("ok", "Sessão terminada."),
    "fonte": ("ok", "Fonte acrescentada."),
    "fonte_estado": ("ok", "Estado da fonte actualizado."),
    "fonte_apagada": ("ok", "Fonte apagada. Os lotes já recolhidos mantêm-se."),
    "recolha": ("ok", "Recolha iniciada em segundo plano. As publicações novas são classificadas no fim."),
    "recolha_ocupada": ("aviso", "Já há uma recolha em curso."),
    "alertas_vistos": ("ok", "Alertas marcados como vistos."),
    "alertas_def": ("ok", "Definições dos alertas gravadas."),
    "email_teste": ("ok", "E-mail de teste enviado. Confirme a caixa de entrada dos destinatários."),
    "relatorio_enviado": ("ok", "Relatório enviado por e-mail aos destinatários definidos."),
    "desfeita": ("ok", "Decisão desfeita. O item voltou à fila."),
    "aspecto": ("ok", "Aspecto gravado."),
}
VIAS_NOMES = {
    "api_oficial": "API oficial da plataforma",
    "manual": "Recolha manual",
    "scraping_publico": "Página pública, sem login",
    "doacao": "Exportação ou doação",
    "dataset_terceiros": "Conjunto de dados de terceiros",
}


class PedidoClassificar(BaseModel):
    textos: list[str] = Field(..., min_length=1, max_length=256)

class PedidoRevisao(BaseModel):
    id_pub: str
    analista: str = Field(..., min_length=2, max_length=40)
    categoria: str
    posicao_fila: int | None = None
    nota: str | None = Field(None, max_length=500)


class PrecisaEntrar(Exception):
    def __init__(self, seguinte: str = "/"):
        self.seguinte = seguinte


class SemPermissao(Exception):
    pass


def _hora(iso: str | None, so_data: bool = False) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return str(iso)[:16]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(LUANDA)
    return dt.strftime("%d/%m/%Y") if so_data else dt.strftime("%d/%m/%Y %H:%M")


def _num(x, casas: int = 0) -> str:
    if x is None:
        return "—"
    s = f"{x:,.{casas}f}"
    return s.replace(",", " ").replace(".", ",")


def _pct(x, casas: int = 0) -> str:
    return "—" if x is None else _num(100 * x, casas) + "%"


_MASCARA = re.compile(r"@?\[(?:URL|EMAIL|TELEFONE|UTILIZADOR)\]")
ATRASO_EMAIL_S = 8  # tempo para o analista desfazer antes de o e-mail do alerta sair


def realcar(texto: str | None) -> Markup:
    """Texto da publicação com os lugares e as máscaras realçados (tudo o resto é escapado)."""
    if not texto:
        return Markup("")
    marcas = [(a, b, "lugar", PROVINCIAS.get(c, c)) for a, b, c in localizar_toponimos(texto)]
    marcas += [(m.start(), m.end(), "mascara", "Dado retirado na anonimização") for m in _MASCARA.finditer(texto)]
    marcas.sort()
    out, pos = [], 0
    for a, b, tipo, titulo in marcas:
        if a < pos:
            continue
        out.append(escape(texto[pos:a]))
        out.append(Markup('<mark class="{}" title="{}">{}</mark>').format(tipo, titulo, texto[a:b]))
        pos = b
    out.append(escape(texto[pos:]))
    return Markup("").join(out)


# Aspecto da interface, escolhido por cada utilizador em Definições (guardado no servidor).
ASPECTO: dict[str, tuple[str, dict[str, str]]] = {
    "tema": ("auto", {"auto": "Automático (segue o sistema)", "claro": "Claro", "escuro": "Escuro"}),
    "cor": ("azul", {"azul": "Azul institucional", "verde": "Verde", "vinho": "Vinho", "petroleo": "Petróleo",
                     "grafite": "Grafite"}),
    "menu": ("escuro", {"escuro": "Escuro", "cor": "Da cor principal", "claro": "Claro"}),
    "cantos": ("arredondados", {"arredondados": "Arredondados", "rectos": "Rectos"}),
    "letra": ("normal", {"pequena": "Pequena", "normal": "Normal", "grande": "Grande", "muito-grande": "Muito grande"}),
    "densidade": ("normal", {"compacta": "Compacta", "normal": "Normal", "confortavel": "Confortável"}),
    "movimento": ("normal", {"normal": "Normais", "reduzido": "Reduzidas (sem animações)"}),
    "mapa": ("vermelho", {"vermelho": "Vermelho", "laranja": "Laranja", "roxo": "Roxo", "azul": "Azul", "verde": "Verde"}),
}
PALETAS_MAPA = {"vermelho": ("#f6efe6", "#a3261a"), "laranja": ("#fbf2e4", "#b4530b"), "roxo": ("#f3eff9", "#4b2a8a"),
                "azul": ("#eef3f8", "#143a5e"), "verde": ("#eef5ef", "#1d5c45")}


def _misturar(a: str, b: str, t: float) -> str:
    ca, cb = (tuple(int(x[i:i + 2], 16) for i in (1, 3, 5)) for x in (a, b))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))


def _ficha_modelo(cfg: Config) -> dict:
    """Ficha do modelo: a da pasta do modelo, se existir (ficha_modelo.json), senão a de referência do sistema."""
    candidatos = []
    if cfg.caminho_modelo:
        candidatos.append(Path(cfg.caminho_modelo) / "ficha_modelo.json")
    candidatos.append(PASTA.parent / "ficha_modelo.json")
    for c in candidatos:
        try:
            if c.is_file():
                return {**json.loads(c.read_text(encoding="utf-8")), "origem_ficha": str(c.name if c.parent == PASTA.parent else c)}
        except (OSError, ValueError):
            log.warning("Ficha do modelo ilegível: %s", c)
    return {}


def linha_tendencia(valores, largura: int = 96, altura: int = 24, rotulo: str = "") -> Markup:
    """Pequena linha de tendência (sparkline) em SVG, desenhada no servidor: sem JavaScript nem bibliotecas."""
    v = [float(x or 0) for x in (valores or [])]
    if len(v) < 2:
        return Markup("")
    topo = max(v) or 1.0
    m = 2.5
    pts = [(m + i * (largura - 2 * m) / (len(v) - 1), altura - m - (x / topo) * (altura - 2 * m)) for i, x in enumerate(v)]
    d = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(pts))
    area = f"{d} L{pts[-1][0]:.1f},{altura - m:.1f} L{pts[0][0]:.1f},{altura - m:.1f} Z"
    ult = pts[-1]
    tendencia = "sobe" if v[-1] > v[-2] else ("desce" if v[-1] < v[-2] else "igual")
    desc = rotulo or "Evolução"
    texto = f"{desc}: " + ", ".join(f"{int(x)}" for x in v)
    return Markup(
        f'<svg class="linha-tendencia {tendencia}" viewBox="0 0 {largura} {altura}" width="{largura}" height="{altura}" '
        f'role="img" aria-label="{escape(texto)}"><title>{escape(texto)}</title>'
        f'<path class="area" d="{area}"></path><path class="traco" d="{d}"></path>'
        f'<circle cx="{ult[0]:.1f}" cy="{ult[1]:.1f}" r="2.4"></circle></svg>')


def criar_app(cfg: Config | None = None, clf: Classificador | None = None, sincrono: bool = False) -> FastAPI:
    """Cria a aplicação. `clf` e `sincrono` servem para os testes."""
    cfg = cfg or obter_config()
    if cfg.demonstracao and clf is None:  # a demonstração nunca carrega o modelo real
        from ..demonstracao import ClassificadorSimulado
        clf = ClassificadorSimulado({})
    bd = BaseDados(cfg.caminho_bd)
    if cfg.demonstracao:
        from ..demonstracao import povoar
        povoar(bd)
    estado: dict = {"clf": clf, "modelo": "pronto" if clf else "a carregar", "erro_modelo": None,
                    "progresso": None, "recolha": None}

    smtp_testes = None  # os testes substituem o servidor de e-mail

    def _carregar():
        try:
            estado["clf"] = carregar_classificador(cfg.caminho_modelo, max_length=cfg.max_length,
                                                   tamanho_lote=cfg.tamanho_lote, dispositivo=cfg.dispositivo)
            estado["modelo"] = "pronto"
        except Exception as e:  # o site continua a funcionar e mostra o erro
            log.exception("Falha ao carregar o modelo")
            estado["modelo"], estado["erro_modelo"] = "erro", str(e)

    carregador = None
    if clf is None:
        carregador = threading.Thread(target=_carregar, name="carregar-modelo", daemon=True)
        carregador.start()

    def _obter_clf() -> Classificador:
        if carregador is not None:
            carregador.join()
        if estado["clf"] is None:
            raise RuntimeError(f"Modelo indisponível: {estado['erro_modelo']}")
        return estado["clf"]

    def _classificar_fundo(quem: str) -> bool:
        if classificacao_em_curso():
            return False

        def tarefa():
            try:
                c = _obter_clf()
                estado["progresso"] = {"feitos": 0, "total": bd.n_pendentes(), "inicio": datetime.now(timezone.utc)}

                def prog(f, t):
                    estado["progresso"] = {**estado["progresso"], "feitos": f, "total": t}

                classificar_pendentes(bd, c, limite=10**9, progresso=prog)
            except Exception:
                log.exception("Falha na classificação")
                bd.auditar(quem, "classificacao_falhada", None)
            finally:
                estado["progresso"] = None

        if sincrono:
            tarefa()
        else:
            threading.Thread(target=tarefa, name="classificar", daemon=True).start()
        return True

    app = FastAPI(title="Sistema UAN – triagem de ameaças", version="1.0.0",
                  description="Ordena a revisão humana de publicações públicas. Nenhuma decisão automática.",
                  docs_url="/api/docs", redoc_url=None, openapi_url="/api/openapi.json")
    app.mount("/estatico", StaticFiles(directory=PASTA / "estatico"), name="estatico")
    tpl = Jinja2Templates(directory=PASTA / "modelos")
    tpl.env.filters.update(hora=_hora, num=_num, pct=_pct)
    tpl.env.globals.update(ROTULOS=ROTULOS, NOMES=NOMES_APRESENTACAO, VIAS=VIAS, VIAS_NOMES=VIAS_NOMES, PAPEIS=PAPEIS,
                           PROVINCIAS=PROVINCIAS, nomes_provincias=al.nomes_provincias)
    tpl.env.filters["json"] = lambda x: json.loads(x or "{}")
    tpl.env.filters["realcar"] = realcar
    tpl.env.globals["linha_tendencia"] = linha_tendencia
    import hashlib
    tpl.env.globals["v_estatico"] = hashlib.sha1(b"".join(
        (PASTA / "estatico" / f).read_bytes() for f in ("app.js", "estilo.css"))).hexdigest()[:10]

    @app.middleware("http")
    async def cabecalhos(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "same-origin"
        if not request.url.path.startswith("/api/docs"):
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "form-action 'self'; frame-ancestors 'none'")
        if request.url.path not in ("/estatico",) and not request.url.path.startswith("/estatico/"):
            resp.headers["Cache-Control"] = "no-store"
        else:  # o navegador confirma sempre se o ficheiro mudou (evita JavaScript antigo depois de actualizar)
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    @app.exception_handler(PrecisaEntrar)
    async def _entrar(request: Request, exc: PrecisaEntrar):
        return RedirectResponse(f"/entrar?seguinte={quote(exc.seguinte)}", status_code=303)

    @app.exception_handler(SemPermissao)
    async def _proibido(request: Request, exc: SemPermissao):
        return pagina(request, "erro.html", {"titulo": "Sem permissão",
                                              "mensagem": "Esta página é reservada a supervisores."}, 403)

    @app.exception_handler(HTTPException)
    async def _erro_http(request: Request, exc: HTTPException):
        if request.url.path.startswith("/api") or request.headers.get("X-Pedido") == "fetch":
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        s = obter_sessao(bd, request.cookies.get(COOKIE))
        if s is None:
            return HTMLResponse(f"<p>{exc.status_code}: {html.escape(str(exc.detail))}</p><p><a href='/'>Voltar</a></p>",
                                status_code=exc.status_code)
        request.state.sessao = s
        return pagina(request, "erro.html", {"titulo": "Não foi possível concluir", "mensagem": str(exc.detail)},
                      exc.status_code)

    # ------------------------------------------------------------------ auxiliares
    def sessao(request: Request, papel: str | None = None) -> dict:
        s = obter_sessao(bd, request.cookies.get(COOKIE))
        if s is None:
            seguinte = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            raise PrecisaEntrar(seguinte)
        request.state.sessao = s
        if papel and s["papel"] != papel:
            raise SemPermissao()
        return s

    def verificar_csrf(s: dict, token: str) -> None:
        if not token or not hmac.compare_digest(token, s["csrf"]):
            raise HTTPException(400, "Formulário expirado. Volte à página e tente de novo.")

    def pagina(request: Request, nome: str, ctx: dict | None = None, codigo: int = 200) -> HTMLResponse:
        s = getattr(request.state, "sessao", None)
        aviso = AVISOS.get(request.query_params.get("aviso", ""))
        base = {"request": request, "sessao": s, "aviso": aviso, "erro": None,
                "modelo_estado": estado["modelo"], "erro_modelo": estado["erro_modelo"],
                "modelo_nome": estado["clf"].nome if estado["clf"] else None,
                "modelo_versao": estado["clf"].versao if estado["clf"] else None,
                "progresso": estado["progresso"], "recolha": estado["recolha"], "caminho": request.url.path,
                "cega_activa": revisao_cega(), "demonstracao": cfg.demonstracao,
                "troca_disponivel": _troca_disponivel(),
                "tema": request.cookies.get("uan_tema") if request.cookies.get("uan_tema") in ("claro", "escuro") else "",
                "aspecto": ler_aspecto(None), "ASPECTO": ASPECTO, "PALETAS_MAPA": PALETAS_MAPA}
        if cfg.demonstracao:
            from ..demonstracao import CONTAS, SENHA
            base["contas_demo"] = [u for u, _, _ in CONTAS]
            base["senha_demo"] = SENHA
        if s:
            base["aspecto"] = ler_aspecto(s["utilizador"])
            base["tema"] = "" if base["aspecto"]["tema"] == "auto" else base["aspecto"]["tema"]
            base["visita_pendente"] = bd.definicao(f"visita_vista:{s['utilizador']}", "0") != "1"
            base["n_fila_meus"] = bd.n_fila(s["utilizador"])
            base["n_amostra_meus"] = len(bd.fila_amostra(s["utilizador"], 10**6))
            base["n_alertas_novos"] = bd.consultar(
                """SELECT COUNT(*) AS n FROM alertas a WHERE NOT EXISTS
                   (SELECT 1 FROM alertas_vistos v WHERE v.id_alerta = a.id_alerta AND v.utilizador = ?)""",
                (s["utilizador"],))[0]["n"]
        base.update(ctx or {})
        return tpl.TemplateResponse(request, nome, base, status_code=codigo)

    def ir(caminho: str, aviso: str | None = None) -> RedirectResponse:
        if aviso:
            caminho += ("&" if "?" in caminho else "?") + f"aviso={aviso}"
        return RedirectResponse(caminho, status_code=303)

    def destino_seguro(url: str | None) -> str:
        # Evita redireccionamentos para fora do site.
        if not url or not url.startswith("/") or url.startswith("//"):
            return "/"
        return url

    def ler_aspecto(utilizador: str | None) -> dict:
        out = {k: v[0] for k, v in ASPECTO.items()}
        if utilizador:
            try:
                guardado = json.loads(bd.definicao(f"aspecto:{utilizador}", "{}") or "{}")
            except ValueError:
                guardado = {}
            out.update({k: v for k, v in guardado.items() if k in ASPECTO and v in ASPECTO[k][1]})
        return out

    def _troca_disponivel() -> bool:
        from .. import controlo
        return controlo.disponivel()

    def revisao_cega() -> bool:
        return bd.definicao("revisao_cega", "0") == "1"

    def sem_utilizadores() -> bool:
        return bd.consultar("SELECT COUNT(*) AS n FROM utilizadores")[0]["n"] == 0

    # ------------------------------------------------------------------ entrada e configuração inicial
    @app.get("/entrar", response_class=HTMLResponse)
    def entrar_form(request: Request, seguinte: str = "/"):
        if sem_utilizadores():
            return ir("/configurar")
        return pagina(request, "entrar.html", {"seguinte": destino_seguro(seguinte)})

    @app.post("/entrar")
    def entrar(request: Request, utilizador: str = Form(""), senha: str = Form(""), seguinte: str = Form("/")):
        try:
            u = autenticar(bd, utilizador, senha)
        except ErroAutenticacao as e:
            return pagina(request, "entrar.html", {"seguinte": destino_seguro(seguinte), "erro": str(e),
                                                   "utilizador": utilizador}, 401)
        token = criar_sessao(bd, u["utilizador"], cfg.horas_sessao)
        resp = ir(destino_seguro(seguinte))
        resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=cfg.cookie_seguro,
                        max_age=cfg.horas_sessao * 3600, path="/")
        return resp

    @app.post("/sair")
    def sair(request: Request, csrf: str = Form("")):
        s = sessao(request)
        verificar_csrf(s, csrf)
        terminar_sessao(bd, request.cookies.get(COOKIE))
        bd.auditar(s["utilizador"], "saida", None)
        resp = ir("/entrar", "saiu")
        resp.delete_cookie(COOKIE, path="/")
        return resp

    @app.get("/configurar", response_class=HTMLResponse)
    def configurar_form(request: Request):
        if not sem_utilizadores():
            return ir("/entrar")
        return pagina(request, "configurar.html")

    @app.post("/configurar")
    def configurar(request: Request, utilizador: str = Form(""), nome: str = Form(""), senha: str = Form(""),
                   senha2: str = Form("")):
        if not sem_utilizadores():
            return ir("/entrar")
        try:
            if senha != senha2:
                raise ValueError("As duas palavras-passe não coincidem.")
            criar_utilizador(bd, utilizador, nome, "supervisor", senha, quem="configuracao_inicial")
        except ValueError as e:
            return pagina(request, "configurar.html", {"erro": str(e), "utilizador": utilizador, "nome": nome}, 400)
        return ir("/entrar")

    # ------------------------------------------------------------------ panorama
    @app.get("/", response_class=HTMLResponse)
    def inicio(request: Request):
        s = sessao(request)
        pan = panorama(bd)
        dias = sorted({r["dia"] for r in pan["por_dia"]})
        serie = {d: {c: 0 for c in ROTULOS} for d in dias}
        for r in pan["por_dia"]:
            serie[r["dia"]][r["categoria"]] = r["n"]
        hoje = datetime.now(LUANDA).date().isoformat()
        minhas = bd.consultar(
            """SELECT COUNT(*) AS total, SUM(substr(revisto_em,1,10) = ?) AS hoje
               FROM revisoes WHERE analista = ?""", (hoje, s["utilizador"]))[0]
        lotes = bd.consultar("SELECT * FROM lotes ORDER BY id_lote DESC LIMIT 5")
        return pagina(request, "panorama.html", {"pan": pan, "serie": serie, "minhas": minhas, "lotes": lotes})

    # ------------------------------------------------------------------ fila e amostra
    def _itens(rows) -> list[dict]:
        out = []
        for r in rows:
            d = dict(r)
            d["probs"] = json.loads(d["probabilidades"]) if d.get("probabilidades") else {}
            out.append(d)
        return out

    @app.get("/fila", response_class=HTMLResponse)
    def fila(request: Request, categoria: str = "", plataforma: str = "", lote: str = "", pagina_n: int = 1):
        s = sessao(request)
        cat = categoria if categoria in ROTULOS else None
        id_lote = int(lote) if lote.isdigit() else None
        pagina_n = max(1, pagina_n)
        desloc = (pagina_n - 1) * POR_PAGINA
        rows = bd.fila(POR_PAGINA + 1, cat, analista=s["utilizador"], plataforma=plataforma or None,
                       id_lote=id_lote, deslocamento=desloc)
        itens = _itens(rows[:POR_PAGINA])
        for i, it in enumerate(itens):
            it["posicao"] = desloc + i + 1
        plataformas = [r["plataforma"] for r in bd.consultar("SELECT DISTINCT plataforma FROM publicacoes ORDER BY 1")]
        lotes = bd.consultar("SELECT id_lote, plataforma, descricao FROM lotes ORDER BY id_lote DESC")
        filtros = {"categoria": categoria, "plataforma": plataforma, "lote": lote}
        voltar = "/fila?" + urlencode({k: v for k, v in {**filtros, "pagina_n": pagina_n}.items() if v})
        return pagina(request, "fila.html", {
            "itens": itens, "modo": "fila", "cega": revisao_cega(), "filtros": filtros, "plataformas": plataformas,
            "lotes_opcoes": lotes, "pagina_n": pagina_n, "ha_mais": len(rows) > POR_PAGINA, "voltar": voltar,
            "qs": lambda **kw: urlencode({k: v for k, v in {**filtros, **kw}.items() if v})})

    @app.get("/amostra", response_class=HTMLResponse)
    def amostra(request: Request):
        s = sessao(request)
        itens = _itens(bd.fila_amostra(s["utilizador"], POR_PAGINA))
        for i, it in enumerate(itens):
            it["posicao"] = None
        resumo = bd.consultar(
            """SELECT a.id_amostra, MIN(a.criada_em) AS criada_em, MIN(a.criada_por) AS criada_por, COUNT(*) AS n
               FROM amostra_controlo a GROUP BY a.id_amostra ORDER BY a.id_amostra DESC""")
        lotes = bd.consultar("SELECT id_lote, plataforma, descricao FROM lotes ORDER BY id_lote DESC")
        normais = bd.consultar(
            """SELECT COUNT(*) AS n FROM classificacoes WHERE categoria='Normal'
               AND id_pub NOT IN (SELECT id_pub FROM amostra_controlo)""")[0]["n"]
        return pagina(request, "fila.html", {"itens": itens, "modo": "amostra", "cega": True, "voltar": "/amostra",
                                             "amostras": resumo, "lotes_opcoes": lotes, "normais_livres": normais})

    @app.post("/amostra/gerar")
    def amostra_gerar(request: Request, csrf: str = Form(""), n: int = Form(50), lote: str = Form(""),
                      semente: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        gerar_amostra_controlo(bd, max(1, min(n, 1000)), s["utilizador"],
                               semente=int(semente) if semente.strip().isdigit() else None,
                               id_lote=int(lote) if lote.isdigit() else None)
        return ir("/amostra", "amostra")

    def pedido_fetch(request: Request) -> bool:
        return request.headers.get("X-Pedido") == "fetch"

    @app.post("/rever")
    def rever(request: Request, csrf: str = Form(""), id_pub: str = Form(...), categoria: str = Form(...),
              nota: str = Form(""), origem: str = Form("fila"), posicao: str = Form(""), voltar: str = Form("/fila")):
        s = sessao(request)
        verificar_csrf(s, csrf)
        if categoria not in ROTULOS or origem not in ("fila", "amostra"):
            raise HTTPException(422, "Decisão inválida.")
        try:
            bd.gravar_revisao(id_pub, s["utilizador"], categoria, int(posicao) if posicao.isdigit() else None,
                              nota.strip()[:500] or None, origem=origem, cega=origem == "amostra" or revisao_cega())
        except KeyError:
            raise HTTPException(404, "Publicação não encontrada.")
        novos = _depois_de_rever(id_pub)
        if pedido_fetch(request):
            return {"ok": True, "id_pub": id_pub, "categoria": categoria, "nome": NOMES_APRESENTACAO[categoria],
                    "n_fila": bd.n_fila(s["utilizador"]), "n_amostra": len(bd.fila_amostra(s["utilizador"], 10**6)),
                    "alertas_novos": len(novos)}
        return ir(destino_seguro(voltar), "revisao")

    @app.post("/rever/desfazer")
    def rever_desfazer(request: Request, csrf: str = Form(""), id_pub: str = Form(...), voltar: str = Form("/fila")):
        s = sessao(request)
        verificar_csrf(s, csrf)
        if not bd.apagar_revisao(id_pub, s["utilizador"]):
            raise HTTPException(409, "Já não é possível desfazer esta decisão.")
        anulado = al.apos_desfazer(bd, id_pub)
        if pedido_fetch(request):
            return {"ok": True, "id_pub": id_pub, "alerta_anulado": anulado,
                    "n_fila": bd.n_fila(s["utilizador"]), "n_amostra": len(bd.fila_amostra(s["utilizador"], 10**6))}
        return ir(destino_seguro(voltar), "desfeita")

    @app.get("/publicacao/{id_pub}", response_class=HTMLResponse)
    def publicacao(request: Request, id_pub: str, parcial: int = 0):
        s = sessao(request)
        p = bd.publicacao(id_pub)
        if p is None:
            raise HTTPException(404, "Publicação não encontrada.")
        it = _itens([p])[0]
        revs = bd.consultar("SELECT * FROM revisoes WHERE id_pub = ? ORDER BY revisto_em", (id_pub,))
        if s["papel"] != "supervisor":
            revs = [r for r in revs if r["analista"] == s["utilizador"]]
        ctx = {"it": it, "revisoes": revs, "cega": revisao_cega() and s["papel"] != "supervisor"}
        if parcial:  # painel lateral da fila: só o corpo, sem menu
            return pagina(request, "_publicacao_corpo.html", ctx)
        return pagina(request, "publicacao.html", ctx)

    # ------------------------------------------------------------------ lotes
    @app.get("/lotes", response_class=HTMLResponse)
    def lotes(request: Request):
        sessao(request)
        rows = bd.consultar(
            """SELECT l.*,
                      (SELECT COUNT(*) FROM publicacoes p WHERE p.id_lote = l.id_lote) AS guardadas,
                      (SELECT COUNT(*) FROM publicacoes p JOIN classificacoes k ON k.id_pub = p.id_pub
                        WHERE p.id_lote = l.id_lote) AS classificadas,
                      (SELECT COUNT(*) FROM publicacoes p JOIN classificacoes k ON k.id_pub = p.id_pub
                        WHERE p.id_lote = l.id_lote AND k.categoria != 'Normal') AS sinalizadas,
                      (SELECT COUNT(DISTINCT r.id_pub) FROM publicacoes p JOIN revisoes r ON r.id_pub = p.id_pub
                        WHERE p.id_lote = l.id_lote) AS revistas
               FROM lotes l ORDER BY l.id_lote DESC""")
        return pagina(request, "lotes.html", {"lotes": rows, "pendentes": bd.n_pendentes(),
                                              "tem_segredo": bool(cfg.segredo_hash), "max_mb": cfg.max_upload_mb})

    @app.post("/lotes/importar")
    async def lotes_importar(request: Request, ficheiro: UploadFile, csrf: str = Form(""), plataforma: str = Form(...),
                             via: str = Form(...), descricao: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        if via not in VIAS:
            raise HTTPException(422, "Via de recolha inválida.")
        if not cfg.segredo_hash:
            raise HTTPException(500, "Defina UAN_SEGREDO_HASH no ficheiro uan.env antes de importar.")
        sufixo = Path(ficheiro.filename or "x.csv").suffix.lower()
        if sufixo not in (".csv", ".jsonl", ".json"):
            raise HTTPException(422, "Formato aceite: .csv, .jsonl ou .json.")
        limite = cfg.max_upload_mb * 1024 * 1024
        dados = await ficheiro.read(limite + 1)
        if len(dados) > limite:
            raise HTTPException(413, f"Ficheiro maior do que {cfg.max_upload_mb} MB.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
            tmp.write(dados)
        try:
            importar(bd, Path(tmp.name), plataforma.strip()[:40] or "desconhecida", via, cfg.segredo_hash,
                     descricao.strip()[:300] or None, quem=s["utilizador"], nome_ficheiro=Path(ficheiro.filename or "").name)
        except (ValueError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise HTTPException(422, f"Não foi possível ler o ficheiro: {e}")
        finally:
            Path(tmp.name).unlink(missing_ok=True)  # o ficheiro bruto nunca fica guardado
        _classificar_fundo(s["utilizador"])
        return ir("/lotes", "importado")

    @app.post("/classificar")
    def classificar(request: Request, csrf: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        return ir("/lotes", "classificar" if _classificar_fundo(s["utilizador"]) else "ocupado")

    def _alertas_por_ver(utilizador: str, limite: int = 5) -> tuple[int, list[dict]]:
        n = bd.consultar(
            """SELECT COUNT(*) AS n FROM alertas a WHERE NOT EXISTS
               (SELECT 1 FROM alertas_vistos v WHERE v.id_alerta = a.id_alerta AND v.utilizador = ?)""",
            (utilizador,))[0]["n"]
        rows = bd.consultar(
            """SELECT a.id_alerta, a.tipo, a.titulo, a.criado_em, a.id_pub,
                      EXISTS(SELECT 1 FROM alertas_vistos v WHERE v.id_alerta = a.id_alerta AND v.utilizador = ?) AS visto
               FROM alertas a ORDER BY a.id_alerta DESC LIMIT ?""", (utilizador, limite))
        return n, [{"id": r["id_alerta"], "tipo": r["tipo"], "titulo": r["titulo"], "quando": _hora(r["criado_em"]),
                    "ligacao": f"/publicacao/{r['id_pub']}" if r["id_pub"] else "/alertas", "visto": bool(r["visto"])}
                   for r in rows]

    @app.get("/estado")
    def estado_json(request: Request):
        s = sessao(request)
        p = estado["progresso"]
        n_alertas, recentes = _alertas_por_ver(s["utilizador"], 1)
        return {"modelo": estado["modelo"], "pendentes": bd.n_pendentes(),
                "classificacao": None if not p else {"feitos": p["feitos"], "total": p["total"]},
                "recolha": estado["recolha"], "alertas_por_ver": n_alertas,
                "modo": "demonstracao" if cfg.demonstracao else "real",
                "ultimo_alerta": recentes[0] if recentes else None, "fila": bd.n_fila(s["utilizador"])}

    @app.get("/alertas/recentes")
    def alertas_recentes(request: Request):
        """Últimos 5 alertas, para o sino no topo da página."""
        s = sessao(request)
        n, recentes = _alertas_por_ver(s["utilizador"], 5)
        return {"por_ver": n, "alertas": recentes}

    @app.get("/modelo", response_class=HTMLResponse)
    def sobre_o_modelo(request: Request):
        sessao(request)
        ficha = _ficha_modelo(cfg)
        m = metricas(bd)
        return pagina(request, "modelo.html", {"ficha": ficha, "m": m,
                                               "a_usar_demo": (estado["clf"] is not None and estado["clf"].nome in ("DEMONSTRACAO", "SIMULADO"))})

    @app.post("/aspecto")
    async def gravar_aspecto(request: Request):
        """Grava as escolhas de aspecto do utilizador (todas ou só algumas, como o botão do tema)."""
        s = sessao(request)
        form = await request.form()
        verificar_csrf(s, str(form.get("csrf", "")))
        actual = ler_aspecto(s["utilizador"])
        repor = form.get("repor") == "1"
        if repor:
            actual = {k: v[0] for k, v in ASPECTO.items()}
        for k, (_, opcoes) in ([] if repor else ASPECTO.items()):
            v = str(form.get(k, ""))
            if v:
                if v not in opcoes:
                    raise HTTPException(400, f"Valor inválido para {k}.")
                actual[k] = v
        bd.definir(f"aspecto:{s['utilizador']}", json.dumps(actual), s["utilizador"])
        if request.headers.get("X-Pedido") == "fetch":
            resp = JSONResponse({"ok": True, "aspecto": actual})
        else:
            resp = ir("/definicoes", "aspecto")
        # o ecrã de entrada (sem sessão) usa o tema do último utilizador neste navegador
        if actual["tema"] == "auto":
            resp.delete_cookie("uan_tema", path="/")
        else:
            resp.set_cookie("uan_tema", actual["tema"], max_age=31536000, path="/", samesite="lax")
        return resp

    # ------------------------------------------------------------------ modo do sistema
    @app.get("/sistema/estado")
    def sistema_estado():
        """Usado pelo ecrã de espera durante a troca de modo (sem dados, sem sessão)."""
        return {"modo": "demonstracao" if cfg.demonstracao else "real", "pronto": True}

    @app.post("/sistema/modo")
    def sistema_modo(request: Request, csrf: str = Form(""), modo: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        from .. import controlo
        actual = "demonstracao" if cfg.demonstracao else "real"
        if modo not in controlo.MODOS or modo == actual:
            raise HTTPException(400, "Modo inválido ou já em uso.")
        if not controlo.disponivel():
            raise HTTPException(409, "A troca de modo só funciona quando o sistema é arrancado com «python uan.py servir». "
                                     "Pare o servidor e arranque de novo" + (" sem" if modo == "real" else " com") +
                                     " a opção --demonstracao.")
        bd.auditar(s["utilizador"], "troca_de_modo", {"de": actual, "para": modo})
        controlo.pedir_troca(modo)
        if request.headers.get("X-Pedido") == "fetch":
            return {"ok": True, "modo": modo}
        return pagina(request, "trocar_modo.html", {"modo_novo": modo})

    @app.post("/visita/vista")
    def visita_vista(request: Request, csrf: str = Form("")):
        s = sessao(request)
        verificar_csrf(s, csrf)
        bd.definir(f"visita_vista:{s['utilizador']}", "1", s["utilizador"])
        return {"ok": True}

    # ------------------------------------------------------------------ fontes e recolha
    def _recolher_fundo(ids: list[int], quem: str) -> bool:
        if estado["recolha"]:
            return False
        estado["recolha"] = {"feitas": 0, "total": len(ids), "fonte": ""}

        def tarefa():
            try:
                from ..recolha import ClienteHTTP
                http = ClienteHTTP(cfg.recolha_agente, cfg.recolha_intervalo_s)
                for i, idf in enumerate(ids):
                    nome = bd.consultar("SELECT nome FROM fontes WHERE id_fonte = ?", (idf,))
                    estado["recolha"] = {"feitas": i, "total": len(ids), "fonte": nome[0]["nome"] if nome else ""}
                    try:
                        recolher_fonte(bd, cfg, idf, quem, http)
                    except ErroRecolha:
                        log.exception("Recolha falhada na fonte %s", idf)
            finally:
                estado["recolha"] = None
            _classificar_fundo(quem)

        if sincrono:
            tarefa()
        else:
            threading.Thread(target=tarefa, name="recolha", daemon=True).start()
        return True

    @app.get("/fontes", response_class=HTMLResponse)
    def fontes(request: Request):
        sessao(request, "supervisor")
        rows = bd.consultar("""SELECT f.*, (SELECT COUNT(*) FROM lotes l WHERE l.ficheiro = substr(f.endereco, 1, 200)
                                AND l.descricao LIKE 'recolha automática%') AS recolhas
                               FROM fontes f ORDER BY f.activa DESC, f.id_fonte""")
        return pagina(request, "fontes.html", {"fontes": rows, "TIPOS_FONTE": TIPOS_FONTE,
                                               "resultado": request.query_params.get("resultado", "")[:400],
                                               "tem_youtube": bool(cfg.chave_youtube), "tem_segredo": bool(cfg.segredo_hash),
                                               "cfg": cfg})

    @app.post("/fontes/adicionar")
    def fontes_adicionar(request: Request, csrf: str = Form(""), tipo: str = Form("auto"), endereco: str = Form(""),
                         enderecos: str = Form(""), nome: str = Form(""), max_itens: int = Form(100)):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        texto = "\n".join(x for x in (enderecos, endereco) if x.strip())
        if not texto.strip():
            raise HTTPException(400, "Indique pelo menos um endereço, identificador ou termo de pesquisa.")
        if tipo != "auto" and tipo not in TIPOS_FONTE:
            raise HTTPException(400, "Tipo de fonte desconhecido.")
        try:
            r = adicionar_fontes(bd, texto, s["utilizador"], tipo, nome, max_itens)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not r["criadas"] and r["erros"] and not r["repetidas"]:
            raise HTTPException(400, "Nenhuma fonte acrescentada. " + "; ".join(f"{l}: {m}" for l, m in r["erros"][:5]))
        partes = [f"{len(r['criadas'])} fonte(s) acrescentada(s)"]
        if r["repetidas"]:
            partes.append(f"{len(r['repetidas'])} já existia(m)")
        if r["erros"]:
            partes.append(f"{len(r['erros'])} com erro: " + "; ".join(f"{l[:40]} ({m})" for l, m in r["erros"][:3]))
        return ir("/fontes?" + urlencode({"resultado": ". ".join(partes) + "."}))

    @app.post("/fontes/detectar")
    def fontes_detectar(request: Request, csrf: str = Form(""), enderecos: str = Form("")):
        """Pré-visualização: o tipo que cada linha vai ter, antes de gravar."""
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        from ..recolha import detectar_tipo, normalizar_endereco
        existentes = {(r["tipo"], r["endereco"]) for r in bd.consultar("SELECT tipo, endereco FROM fontes")}
        out = []
        for l in [x.strip() for x in enderecos.splitlines() if x.strip() and not x.strip().startswith("#")][:100]:
            t = detectar_tipo(l)
            e = normalizar_endereco(t, l)
            out.append({"linha": l[:200], "tipo": t, "tipo_nome": TIPOS_FONTE[t], "endereco": e[:200],
                        "repetida": (t, e) in existentes})
        return {"linhas": out}

    @app.post("/fontes/{id_fonte}/estado")
    def fontes_estado(request: Request, id_fonte: int, csrf: str = Form(""), activa: str = Form("0")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        with bd.ligacao() as c:
            c.execute("UPDATE fontes SET activa = ? WHERE id_fonte = ?", (1 if activa == "1" else 0, id_fonte))
        bd.auditar(s["utilizador"], "fonte_estado", {"id_fonte": id_fonte, "activa": activa == "1"})
        return ir("/fontes", "fonte_estado")

    @app.post("/fontes/{id_fonte}/apagar")
    def fontes_apagar(request: Request, id_fonte: int, csrf: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        with bd.ligacao() as c:
            c.execute("DELETE FROM fontes WHERE id_fonte = ?", (id_fonte,))
        bd.auditar(s["utilizador"], "fonte_apagada", {"id_fonte": id_fonte})
        return ir("/fontes", "fonte_apagada")

    @app.post("/fontes/recolher")
    def fontes_recolher(request: Request, csrf: str = Form(""), id_fonte: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        if not cfg.segredo_hash:
            raise HTTPException(500, "Defina UAN_SEGREDO_HASH no ficheiro uan.env antes de recolher.")
        if id_fonte.isdigit():
            ids = [int(id_fonte)]
        else:
            ids = [r["id_fonte"] for r in bd.consultar("SELECT id_fonte FROM fontes WHERE activa = 1 ORDER BY id_fonte")]
        if not ids:
            raise HTTPException(400, "Não há fontes activas.")
        return ir("/fontes", "recolha" if _recolher_fundo(ids, s["utilizador"]) else "recolha_ocupada")

    # ------------------------------------------------------------------ alertas, mapa e relatório
    def _depois_de_rever(id_pub: str) -> list[int]:
        try:
            return al.apos_revisao(bd, cfg, id_pub, sincrono=sincrono, fabrica_smtp=app.state.smtp_testes,
                                   atraso_s=ATRASO_EMAIL_S)
        except Exception:  # um erro nos alertas nunca impede a gravação da decisão
            log.exception("Falha ao gerar alertas para %s", id_pub)
            return []

    @app.get("/alertas", response_class=HTMLResponse)
    def ver_alertas(request: Request, tipo: str = "", pagina_n: int = 1):
        s = sessao(request)
        pagina_n = max(1, pagina_n)
        filtro, params = ("WHERE a.tipo = ?", (tipo,)) if tipo in ("confirmado", "tendencia") else ("", ())
        rows = bd.consultar(
            f"""SELECT a.*, EXISTS(SELECT 1 FROM alertas_vistos v WHERE v.id_alerta = a.id_alerta AND v.utilizador = ?)
                       AS visto FROM alertas a {filtro} ORDER BY a.id_alerta DESC LIMIT ? OFFSET ?""",
            (s["utilizador"], *params, 51, (pagina_n - 1) * 50))
        defs = al.ler_definicoes(bd)
        return pagina(request, "alertas.html", {"alertas": rows[:50], "ha_mais": len(rows) > 50, "pagina_n": pagina_n,
                                                "tipo": tipo, "defs": defs, "email_ok": cfg.email_configurado})

    @app.post("/alertas/vistos")
    def alertas_vistos(request: Request, csrf: str = Form("")):
        s = sessao(request)
        verificar_csrf(s, csrf)
        with bd.ligacao() as c:
            c.execute("""INSERT OR IGNORE INTO alertas_vistos(id_alerta, utilizador, visto_em)
                         SELECT id_alerta, ?, ? FROM alertas""", (s["utilizador"], datetime.now(timezone.utc).isoformat()))
        return ir("/alertas", "alertas_vistos")

    def _cor(taxa: float | None, maximo: float, suficiente: bool, mencoes: int, paleta: str = "vermelho") -> str:
        if not mencoes:
            return "#eceee9"
        if not suficiente or taxa is None:
            return "url(#insuficiente)"
        a, b = PALETAS_MAPA.get(paleta, PALETAS_MAPA["vermelho"])
        t = 0.0 if maximo <= 0 else min(1.0, taxa / maximo)
        return _misturar(a, b, 0.12 + 0.88 * t) if taxa > 0 else a

    def _preparar_mapa(d: dict, geo: dict, paleta: str = "vermelho") -> None:
        a, b = PALETAS_MAPA.get(paleta, PALETAS_MAPA["vermelho"])
        d["escala"] = (a, _misturar(a, b, 0.45), b)
        for l in d["provincias"]:
            g = geo["provincias"][l["codigo"]]
            l.update(d_svg=g["d"], cx=g["cx"], cy=g["cy"],
                     cor=_cor(l["taxa"], d["max_taxa"], l["suficiente"], l["mencoes"], paleta))

    def _dados_mapa(de, ate, dias, modo, categoria, paleta="vermelho"):
        per = al.periodo(de, ate, dias)
        cat = categoria if categoria in ROTULOS and categoria != "Normal" else None
        d = al.dados_mapa(bd, per, modo, cat)
        geo = mapa_geo()
        _preparar_mapa(d, geo, paleta)
        return per, cat, d, geo

    @app.get("/mapa", response_class=HTMLResponse)
    def ver_mapa(request: Request, de: str = "", ate: str = "", dias: str = "", modo: str = "confirmadas",
                 categoria: str = ""):
        s = sessao(request)
        per, cat, d, geo = _dados_mapa(de, ate, dias, modo, categoria, ler_aspecto(s["utilizador"])["mapa"])
        serie = al.serie(bd, per, d["modo"], cat)
        return pagina(request, "mapa.html", {"m": d, "geo": geo, "per": per, "modo": d["modo"], "categoria": cat or "",
                                             "fonte_geo": geo["fonte"], "serie": serie})

    @app.get("/mapa.svg")
    def mapa_svg_exportar(request: Request, de: str = "", ate: str = "", dias: str = "", modo: str = "confirmadas",
                          categoria: str = ""):
        """Mapa autónomo, com título, período, legenda e fonte, para descarregar (SVG) ou converter em PNG."""
        s = sessao(request)
        per, cat, d, geo = _dados_mapa(de, ate, dias, modo, categoria, ler_aspecto(s["utilizador"])["mapa"])
        bd.auditar(s["utilizador"], "exportacao_mapa", {"periodo": per.rotulo(), "modo": d["modo"]})
        corpo = tpl.env.get_template("mapa_exportar.svg").render(
            m=d, geo=geo, per=per, categoria=NOMES_APRESENTACAO.get(cat, "") if cat else "",
            gerado=_hora(datetime.now(timezone.utc).isoformat()))
        return Response(corpo, media_type="image/svg+xml; charset=utf-8", headers={
            "Content-Disposition": f"inline; filename=mapa_{d['modo']}_{per.inicio}_{per.fim}.svg"})

    @app.get("/relatorio", response_class=HTMLResponse)
    def ver_relatorio(request: Request, de: str = "", ate: str = "", dias: str = ""):
        s = sessao(request)
        per = al.periodo(de, ate, dias)
        rel = al.relatorio(bd, per)
        geo = mapa_geo()
        _preparar_mapa(rel["mapa"], geo, ler_aspecto(s["utilizador"])["mapa"])
        bd.auditar(s["utilizador"], "relatorio", {"periodo": per.rotulo()})
        return pagina(request, "relatorio.html", {"rel": rel, "per": per, "geo": geo, "m": rel["mapa"],
                                                  "serie": al.serie(bd, per, "confirmadas"),
                                                  "serie_sinal": al.serie(bd, per, "sinalizadas"),
                                                  "email_ok": cfg.email_configurado,
                                                  "destinatarios": al.ler_definicoes(bd)["destinatarios"]})

    @app.get("/relatorio.csv")
    def relatorio_csv(request: Request, de: str = "", ate: str = "", dias: str = ""):
        s = sessao(request)
        per = al.periodo(de, ate, dias)
        bd.auditar(s["utilizador"], "exportacao_relatorio", {"periodo": per.rotulo()})
        corpo = "\ufeff" + al.relatorio_csv(al.relatorio(bd, per))
        return Response(corpo, media_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": f"attachment; filename=relatorio_alertas_{per.inicio}_{per.fim}.csv"})

    @app.post("/relatorio/enviar")
    def relatorio_enviar(request: Request, csrf: str = Form(""), de: str = Form(""), ate: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        per = al.periodo(de, ate)
        assunto, corpo = al.corpo_relatorio(al.relatorio(bd, per), cfg)
        try:
            al.enviar_email(cfg, al.ler_definicoes(bd)["destinatarios"], assunto, corpo, app.state.smtp_testes)
        except Exception as e:
            raise HTTPException(502, f"O e-mail não foi enviado: {e}")
        bd.auditar(s["utilizador"], "relatorio_email", {"periodo": per.rotulo()})
        return ir(f"/relatorio?de={per.inicio}&ate={per.fim}", "relatorio_enviado")

    @app.post("/definicoes/alertas")
    def definicoes_alertas(request: Request, csrf: str = Form(""), min_confirmacoes: int = Form(1),
                           janela_dias: int = Form(7), min_casos: int = Form(5), factor: str = Form("1.5"),
                           destinatarios: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        try:
            emails = al.validar_destinatarios(destinatarios)
            f = float(factor.replace(",", "."))
            if not (1 <= min_confirmacoes <= 5 and 1 <= janela_dias <= 90 and 1 <= min_casos <= 1000 and 1.0 <= f <= 10):
                raise ValueError("Valores fora dos limites.")
        except ValueError as e:
            raise HTTPException(400, str(e))
        for k, v in (("alerta_min_confirmacoes", min_confirmacoes), ("alerta_janela_dias", janela_dias),
                     ("alerta_min_casos", min_casos), ("alerta_factor", f), ("alerta_destinatarios", ",".join(emails))):
            bd.definir(k, str(v), s["utilizador"])
        return ir("/definicoes", "alertas_def")

    @app.post("/definicoes/email-teste")
    def definicoes_email_teste(request: Request, csrf: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        try:
            al.enviar_email(cfg, al.ler_definicoes(bd)["destinatarios"], "[Sistema UAN] E-mail de teste",
                            "Se recebeu esta mensagem, os alertas por e-mail do Sistema UAN estão configurados.",
                            app.state.smtp_testes)
        except Exception as e:
            raise HTTPException(502, f"O e-mail não foi enviado: {e}")
        bd.auditar(s["utilizador"], "email_teste", None)
        return ir("/definicoes", "email_teste")

    # ------------------------------------------------------------------ métricas
    @app.get("/metricas", response_class=HTMLResponse)
    def ver_metricas(request: Request):
        sessao(request, "supervisor")
        return pagina(request, "metricas.html", {"m": metricas(bd)})

    @app.get("/metricas/metricas.json")
    def metricas_json(request: Request):
        s = sessao(request, "supervisor")
        bd.auditar(s["utilizador"], "exportacao_metricas", None)
        corpo = json.dumps(metricas(bd), ensure_ascii=False, indent=1)
        return Response(corpo, media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=metricas_sistema_uan.json"})

    @app.get("/metricas/revisoes.csv")
    def revisoes_csv(request: Request):
        s = sessao(request, "supervisor")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "revisoes.csv"
            exportar_revisoes(bd, p, quem=s["utilizador"])
            corpo = p.read_bytes()
        return StreamingResponse(io.BytesIO(corpo), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=revisoes_para_treino.csv"})

    # ------------------------------------------------------------------ auditoria
    @app.get("/auditoria", response_class=HTMLResponse)
    def auditoria(request: Request, pagina_n: int = 1, quem: str = "", accao: str = ""):
        sessao(request, "supervisor")
        pagina_n = max(1, pagina_n)
        filtros, params = [], []
        if quem:
            filtros.append("quem = ?"); params.append(quem)
        if accao:
            filtros.append("accao = ?"); params.append(accao)
        where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
        rows = bd.consultar(f"SELECT * FROM auditoria {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                            tuple(params) + (51, (pagina_n - 1) * 50))
        accoes = [r["accao"] for r in bd.consultar("SELECT DISTINCT accao FROM auditoria ORDER BY 1")]
        pessoas = [r["quem"] for r in bd.consultar("SELECT DISTINCT quem FROM auditoria ORDER BY 1")]
        return pagina(request, "auditoria.html", {"linhas": rows[:50], "ha_mais": len(rows) > 50, "pagina_n": pagina_n,
                                                  "accoes": accoes, "pessoas": pessoas, "f_quem": quem, "f_accao": accao})

    # ------------------------------------------------------------------ utilizadores
    @app.get("/utilizadores", response_class=HTMLResponse)
    def utilizadores(request: Request):
        sessao(request, "supervisor")
        rows = bd.consultar(
            """SELECT u.utilizador, u.nome, u.papel, u.activo, u.criado_em, u.ultimo_acesso,
                      (SELECT COUNT(*) FROM revisoes r WHERE r.analista = u.utilizador) AS revisoes
               FROM utilizadores u ORDER BY u.activo DESC, u.papel DESC, u.utilizador""")
        return pagina(request, "utilizadores.html", {"utilizadores": rows})

    @app.post("/utilizadores/criar")
    def utilizadores_criar(request: Request, csrf: str = Form(""), utilizador: str = Form(""), nome: str = Form(""),
                           papel: str = Form("analista"), senha: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        try:
            criar_utilizador(bd, utilizador, nome, papel, senha, quem=s["utilizador"])
        except ValueError as e:
            rows = bd.consultar("""SELECT u.*, (SELECT COUNT(*) FROM revisoes r WHERE r.analista = u.utilizador) AS revisoes
                                   FROM utilizadores u ORDER BY u.activo DESC, u.papel DESC, u.utilizador""")
            return pagina(request, "utilizadores.html", {"utilizadores": rows, "erro": str(e),
                                                         "form": {"utilizador": utilizador, "nome": nome, "papel": papel}}, 400)
        return ir("/utilizadores", "utilizador")

    @app.post("/utilizadores/{utilizador}/estado")
    def utilizadores_estado(request: Request, utilizador: str, csrf: str = Form(""), activo: str = Form("0")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        try:
            definir_activo(bd, utilizador, activo == "1", s["utilizador"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        return ir("/utilizadores", "estado")

    @app.post("/utilizadores/{utilizador}/senha")
    def utilizadores_senha(request: Request, utilizador: str, csrf: str = Form(""), senha: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        try:
            mudar_senha(bd, utilizador, senha, s["utilizador"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        return ir("/utilizadores", "senha")

    @app.get("/conta", response_class=HTMLResponse)
    def conta(request: Request):
        sessao(request)
        return pagina(request, "conta.html")

    @app.post("/conta/senha")
    def conta_senha(request: Request, csrf: str = Form(""), actual: str = Form(""), senha: str = Form(""),
                    senha2: str = Form("")):
        s = sessao(request)
        verificar_csrf(s, csrf)
        try:
            autenticar(bd, s["utilizador"], actual)
            if senha != senha2:
                raise ValueError("As duas palavras-passe novas não coincidem.")
            mudar_senha(bd, s["utilizador"], senha, s["utilizador"])
        except (ErroAutenticacao, ValueError) as e:
            return pagina(request, "conta.html", {"erro": str(e)}, 400)
        resp = ir("/entrar", "senha")
        resp.delete_cookie(COOKIE, path="/")
        return resp

    # ------------------------------------------------------------------ definições
    @app.get("/definicoes", response_class=HTMLResponse)
    def definicoes(request: Request):
        s = sessao(request)
        if s["papel"] != "supervisor":
            return pagina(request, "definicoes.html", {"so_aspecto": True})
        antigas = bd.consultar(
            """SELECT COUNT(*) AS n FROM publicacoes WHERE recolhido_em < ? AND id_pub NOT IN (SELECT id_pub FROM revisoes)""",
            ((datetime.now(timezone.utc) - timedelta(days=cfg.dias_conservacao)).isoformat(),))[0]["n"]
        return pagina(request, "definicoes.html", {"cega": revisao_cega(), "dias": cfg.dias_conservacao,
                                                   "antigas": antigas, "cfg": cfg, "defs": al.ler_definicoes(bd),
                                                   "api_activa": bool(cfg.chave_api)})

    @app.post("/definicoes")
    def definicoes_gravar(request: Request, csrf: str = Form(""), cega: str = Form("0")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        bd.definir("revisao_cega", "1" if cega == "1" else "0", s["utilizador"])
        return ir("/definicoes", "definicoes")

    @app.post("/definicoes/limpar")
    def definicoes_limpar(request: Request, csrf: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        bd.apagar_antigos(cfg.dias_conservacao, quem=s["utilizador"])
        return ir("/definicoes", "limpeza")

    @app.post("/definicoes/copia")
    def definicoes_copia(request: Request, csrf: str = Form("")):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        nome = datetime.now(LUANDA).strftime("sistema_%Y%m%d_%H%M%S.db")
        bd.copia_seguranca(Path(cfg.caminho_bd).parent / "copias" / nome, quem=s["utilizador"])
        return ir("/definicoes", "copia")

    # ------------------------------------------------------------------ API JSON (integração)
    def chave(request: Request) -> None:
        recebida = request.headers.get("X-Chave-API", "")
        if not cfg.chave_api:
            raise HTTPException(403, "API desactivada: defina UAN_CHAVE_API no ficheiro uan.env.")
        if not hmac.compare_digest(recebida, cfg.chave_api):
            raise HTTPException(401, "Chave de API inválida.")

    @app.get("/api/saude")
    def api_saude():
        c = estado["clf"]
        return {"estado": "ok", "modelo_estado": estado["modelo"], "modelo": c.nome if c else None,
                "versao": c.versao if c else None,
                "aviso": "classificador de demonstração" if c and c.nome == "DEMONSTRACAO" else None}

    @app.post("/api/classificar")
    def api_classificar(request: Request, p: PedidoClassificar):
        chave(request)
        return [{"categoria": r.categoria, "confianca": round(r.confianca, 4), "probabilidades": r.probabilidades}
                for r in _obter_clf().classificar(p.textos)]

    @app.post("/api/importar")
    async def api_importar(request: Request, ficheiro: UploadFile, plataforma: str, via: str, descricao: str | None = None):
        chave(request)
        if via not in VIAS:
            raise HTTPException(422, f"via deve ser uma de {VIAS}")
        if not cfg.segredo_hash:
            raise HTTPException(500, "UAN_SEGREDO_HASH não definido.")
        sufixo = Path(ficheiro.filename or "x.csv").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=sufixo) as tmp:
            tmp.write(await ficheiro.read())
        try:
            info = importar(bd, Path(tmp.name), plataforma, via, cfg.segredo_hash, descricao, quem="api",
                            nome_ficheiro=Path(ficheiro.filename or "").name)
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        info.update(classificar_pendentes(bd, _obter_clf(), limite=10**9))
        return info

    @app.get("/api/fila")
    def api_fila(request: Request, limite: int = 50, categoria: str | None = None):
        chave(request)
        if categoria and categoria not in ROTULOS:
            raise HTTPException(422, f"categoria deve ser uma de {ROTULOS}")
        return [{**dict(r), "probabilidades": json.loads(r["probabilidades"])}
                for r in bd.fila(min(limite, 500), categoria)]

    @app.post("/api/revisoes")
    def api_rever(request: Request, p: PedidoRevisao):
        chave(request)
        if p.categoria not in ROTULOS:
            raise HTTPException(422, f"categoria deve ser uma de {ROTULOS}")
        try:
            bd.gravar_revisao(p.id_pub, p.analista, p.categoria, p.posicao_fila, p.nota, origem="api")
        except KeyError as e:
            raise HTTPException(404, str(e))
        return {"estado": "gravada", "alertas_novos": _depois_de_rever(p.id_pub)}

    @app.get("/api/alertas")
    def api_alertas(request: Request, limite: int = 50):
        chave(request)
        return [{**dict(a), "detalhe": json.loads(a["detalhe"] or "{}")}
                for a in bd.consultar("SELECT * FROM alertas ORDER BY id_alerta DESC LIMIT ?", (min(limite, 500),))]

    @app.get("/api/mapa")
    def api_mapa(request: Request, de: str = "", ate: str = "", dias: str = "", modo: str = "confirmadas"):
        chave(request)
        d = al.dados_mapa(bd, al.periodo(de, ate, dias), modo)
        return {**d, "periodo": d["periodo"].rotulo(), "anterior": d["anterior"].rotulo()}

    @app.get("/api/metricas")
    def api_metricas(request: Request):
        chave(request)
        return metricas(bd)

    def _pronto():  # só aparece quando o servidor já aceita ligações
        endereco = os.getenv("UAN_ENDERECO_SERVIDOR")
        if endereco:
            print(f"PRONTO: abra {endereco} no navegador  (Ctrl+C para parar)", flush=True)

    app.router.on_startup.append(_pronto)
    app.state.bd = bd
    app.state.estado = estado
    app.state.smtp_testes = smtp_testes
    return app
