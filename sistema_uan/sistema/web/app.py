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
import logging
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ..base_dados import BaseDados
from ..classificador import Classificador, carregar_classificador
from ..config import NOMES_APRESENTACAO, PAPEIS, ROTULOS, Config, obter_config
from ..recolha import TIPOS as TIPOS_FONTE, ErroRecolha, adicionar_fonte, recolher_fonte
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


def criar_app(cfg: Config | None = None, clf: Classificador | None = None, sincrono: bool = False) -> FastAPI:
    """Cria a aplicação. `clf` e `sincrono` servem para os testes."""
    cfg = cfg or obter_config()
    bd = BaseDados(cfg.caminho_bd)
    estado: dict = {"clf": clf, "modelo": "pronto" if clf else "a carregar", "erro_modelo": None,
                    "progresso": None, "recolha": None}

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
    tpl.env.globals.update(ROTULOS=ROTULOS, NOMES=NOMES_APRESENTACAO, VIAS=VIAS, VIAS_NOMES=VIAS_NOMES, PAPEIS=PAPEIS)

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
        if request.url.path.startswith("/api"):
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
                "progresso": estado["progresso"], "recolha": estado["recolha"], "caminho": request.url.path}
        if s:
            base["n_fila_meus"] = bd.n_fila(s["utilizador"])
            base["n_amostra_meus"] = len(bd.fila_amostra(s["utilizador"], 10**6))
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
        return ir(destino_seguro(voltar), "revisao")

    @app.get("/publicacao/{id_pub}", response_class=HTMLResponse)
    def publicacao(request: Request, id_pub: str):
        s = sessao(request)
        p = bd.publicacao(id_pub)
        if p is None:
            raise HTTPException(404, "Publicação não encontrada.")
        it = _itens([p])[0]
        revs = bd.consultar("SELECT * FROM revisoes WHERE id_pub = ? ORDER BY revisto_em", (id_pub,))
        if s["papel"] != "supervisor":
            revs = [r for r in revs if r["analista"] == s["utilizador"]]
        return pagina(request, "publicacao.html", {"it": it, "revisoes": revs,
                                                   "cega": revisao_cega() and s["papel"] != "supervisor"})

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

    @app.get("/estado")
    def estado_json(request: Request):
        sessao(request)
        p = estado["progresso"]
        return {"modelo": estado["modelo"], "pendentes": bd.n_pendentes(),
                "classificacao": None if not p else {"feitos": p["feitos"], "total": p["total"]},
                "recolha": estado["recolha"]}

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
                                               "tem_youtube": bool(cfg.chave_youtube), "tem_segredo": bool(cfg.segredo_hash),
                                               "cfg": cfg})

    @app.post("/fontes/adicionar")
    def fontes_adicionar(request: Request, csrf: str = Form(""), tipo: str = Form(...), endereco: str = Form(...),
                         nome: str = Form(""), max_itens: int = Form(100)):
        s = sessao(request, "supervisor")
        verificar_csrf(s, csrf)
        try:
            adicionar_fonte(bd, tipo, endereco, nome, s["utilizador"], max_itens)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return ir("/fontes", "fonte")

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
        sessao(request, "supervisor")
        antigas = bd.consultar(
            """SELECT COUNT(*) AS n FROM publicacoes WHERE recolhido_em < ? AND id_pub NOT IN (SELECT id_pub FROM revisoes)""",
            ((datetime.now(timezone.utc) - timedelta(days=cfg.dias_conservacao)).isoformat(),))[0]["n"]
        return pagina(request, "definicoes.html", {"cega": revisao_cega(), "dias": cfg.dias_conservacao,
                                                   "antigas": antigas, "cfg": cfg,
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
        return {"estado": "gravada"}

    @app.get("/api/metricas")
    def api_metricas(request: Request):
        chave(request)
        return metricas(bd)

    app.state.bd = bd
    app.state.estado = estado
    return app
