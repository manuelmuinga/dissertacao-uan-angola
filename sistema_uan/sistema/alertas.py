"""Alertas, mapa por província e relatório de alertas de ameaças.

Princípios (Secção 3.8 da dissertação):
- nenhum alerta sai do sistema sem decisão humana: o alerta CONFIRMADO nasce da
  revisão de um analista; o alerta de TENDÊNCIA conta só ameaças confirmadas;
- os alertas vão para a aplicação e, se configurado, por e-mail para os
  destinatários definidos pelo supervisor; nunca para terceiros automaticamente;
- os e-mails não levam o texto da publicação nem o pseudónimo do autor, só a
  categoria, a província mencionada, a data e a ligação para o sistema;
- a província é o lugar MENCIONADO, não a localização de quem escreveu;
- no mapa, a concentração é uma taxa (ameaças ÷ publicações que mencionam a
  província), para não confundir mais conversa com mais ameaça;
- na tendência, o peso das ameaças é medido sobre o total de publicações recolhidas
  em cada janela, para que um aumento da recolha, por si só, não gere alertas.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import smtplib
import ssl
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Callable

from .base_dados import BaseDados, agora
from .config import NOMES_APRESENTACAO, ROTULOS, Config
from .geografia import PROVINCIAS, SEM_LOCAL

log = logging.getLogger(__name__)

NACIONAL = "NAC"
DATA_PUB = "substr(COALESCE(p.data_publicacao, p.recolhido_em), 1, 10)"
LUANDA = timezone(timedelta(hours=1))

DEFINICOES = {  # chave: (omissão, descrição)
    "alerta_min_confirmacoes": ("1", "Analistas que têm de confirmar uma ameaça para gerar o alerta"),
    "alerta_janela_dias": ("7", "Dias de cada janela na comparação de tendência"),
    "alerta_min_casos": ("5", "Mínimo de ameaças confirmadas na janela para haver alerta de tendência"),
    "alerta_factor": ("1.5", "Crescimento mínimo face à janela anterior (1,5 = +50%)"),
    "alerta_destinatarios": ("", "E-mails que recebem os alertas, separados por vírgulas"),
}
_EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")


# ---------------------------------------------------------------- definições
def ler_definicoes(bd: BaseDados) -> dict:
    d = {k: bd.definicao(k, v[0]) for k, v in DEFINICOES.items()}
    return {
        "min_confirmacoes": max(1, int(d["alerta_min_confirmacoes"] or 1)),
        "janela_dias": max(1, int(d["alerta_janela_dias"] or 7)),
        "min_casos": max(1, int(d["alerta_min_casos"] or 5)),
        "factor": max(1.0, float(str(d["alerta_factor"] or "1.5").replace(",", "."))),
        "destinatarios": [e for e in (x.strip() for x in d["alerta_destinatarios"].split(",")) if e],
    }


def validar_destinatarios(texto: str) -> list[str]:
    emails = [e.strip() for e in re.split(r"[,;\s]+", texto or "") if e.strip()]
    maus = [e for e in emails if not _EMAIL.match(e)]
    if maus:
        raise ValueError(f"Endereço de e-mail inválido: {', '.join(maus)}")
    if len(emails) > 20:
        raise ValueError("No máximo 20 destinatários.")
    return emails


# ---------------------------------------------------------------- período
@dataclass(frozen=True)
class Periodo:
    inicio: date
    fim: date

    @property
    def dias(self) -> int:
        return (self.fim - self.inicio).days + 1

    @property
    def anterior(self) -> "Periodo":
        return Periodo(self.inicio - timedelta(days=self.dias), self.inicio - timedelta(days=1))

    def rotulo(self) -> str:
        return f"{self.inicio:%d/%m/%Y} a {self.fim:%d/%m/%Y}"


def hoje_luanda() -> date:
    return datetime.now(LUANDA).date()


def periodo(de: str | None = None, ate: str | None = None, dias: int | str | None = None) -> Periodo:
    """Período escolhido pelo utilizador. Sem datas, os últimos `dias` (30 por omissão)."""
    def ler(x):
        try:
            return date.fromisoformat(x) if x else None
        except ValueError:
            return None
    fim = ler(ate) or hoje_luanda()
    inicio = ler(de)
    if inicio is None:
        n = int(dias) if str(dias or "").isdigit() and int(dias) > 0 else 30
        inicio = fim - timedelta(days=min(n, 3660) - 1)
    if inicio > fim:
        inicio, fim = fim, inicio
    if (fim - inicio).days > 3660:
        inicio = fim - timedelta(days=3660)
    return Periodo(inicio, fim)


# ---------------------------------------------------------------- confirmação
def _confirmadas(bd: BaseDados, minc: int, ids: list[str] | None = None) -> dict[str, str]:
    """{id_pub: categoria} das publicações confirmadas como ameaça pelos analistas.

    Confirmada = pelo menos `minc` analistas escolheram uma categoria de ameaça e
    há mais decisões de ameaça do que de Normal. A categoria é a mais escolhida.
    """
    filtro, params = "", ()
    if ids is not None:
        if not ids:
            return {}
        filtro = f"WHERE id_pub IN ({','.join('?' * len(ids))})"
        params = tuple(ids)
    linhas = bd.consultar(f"SELECT id_pub, categoria FROM revisoes {filtro}", params)
    por: dict[str, list[str]] = defaultdict(list)
    for l in linhas:
        por[l["id_pub"]].append(l["categoria"])
    out = {}
    for idp, cats in por.items():
        ameacas = [c for c in cats if c != "Normal"]
        if len(ameacas) >= minc and len(ameacas) > len(cats) - len(ameacas):
            out[idp] = Counter(ameacas).most_common(1)[0][0]
    return out


def _provincias_de(bd: BaseDados, ids: list[str]) -> dict[str, list[str]]:
    if not ids:
        return {}
    out: dict[str, list[str]] = defaultdict(list)
    for i in range(0, len(ids), 900):
        parte = ids[i:i + 900]
        for r in bd.consultar(f"SELECT id_pub, provincia FROM pub_provincias WHERE id_pub IN ({','.join('?' * len(parte))})",
                              tuple(parte)):
            out[r["id_pub"]].append(r["provincia"])
    return out


def nomes_provincias(codigos: list[str] | None) -> str:
    return ", ".join(PROVINCIAS.get(c, c) for c in codigos) if codigos else "sem localização"


# ---------------------------------------------------------------- criação de alertas
def _criar(bd: BaseDados, tipo: str, chave: str, titulo: str, categoria: str | None, provincia: str | None,
           id_pub: str | None, detalhe: dict) -> int | None:
    with bd.ligacao() as c:
        cur = c.execute(
            """INSERT OR IGNORE INTO alertas(tipo, chave, criado_em, titulo, categoria, provincia, id_pub, detalhe)
               VALUES (?,?,?,?,?,?,?,?)""",
            (tipo, chave, agora(), titulo, categoria, provincia, id_pub, json.dumps(detalhe, ensure_ascii=False)))
        novo = int(cur.lastrowid) if cur.rowcount else None
    if novo:
        bd.auditar("sistema", "alerta", {"id_alerta": novo, "tipo": tipo, "provincia": provincia, "categoria": categoria})
    return novo


def alerta_confirmado(bd: BaseDados, id_pub: str) -> int | None:
    """Cria o alerta de ameaça confirmada, se a publicação acabou de ser confirmada."""
    defs = ler_definicoes(bd)
    conf = _confirmadas(bd, defs["min_confirmacoes"], [id_pub])
    if id_pub not in conf:
        return None
    cat = conf[id_pub]
    provs = _provincias_de(bd, [id_pub]).get(id_pub, [])
    p = bd.consultar(f"SELECT {DATA_PUB} AS dia, p.plataforma FROM publicacoes p WHERE p.id_pub = ?", (id_pub,))
    n = bd.consultar("SELECT COUNT(*) AS n FROM revisoes WHERE id_pub = ? AND categoria != 'Normal'", (id_pub,))[0]["n"]
    titulo = f"Ameaça confirmada: {NOMES_APRESENTACAO.get(cat, cat)} · {nomes_provincias(provs)}"
    return _criar(bd, "confirmado", f"confirmado:{id_pub}", titulo, cat, provs[0] if len(provs) == 1 else None, id_pub,
                  {"provincias": provs, "dia_publicacao": p[0]["dia"] if p else None,
                   "plataforma": p[0]["plataforma"] if p else None, "analistas_confirmaram": n})


def _contagens(bd: BaseDados, per: Periodo, modo: str = "confirmadas", minc: int = 1,
               categoria: str | None = None) -> dict:
    """Por província: publicações que a mencionam e ameaças (confirmadas ou sinalizadas) no período."""
    linhas = bd.consultar(
        f"""SELECT p.id_pub, k.categoria AS cat_modelo FROM publicacoes p
            LEFT JOIN classificacoes k ON k.id_pub = p.id_pub
            WHERE {DATA_PUB} BETWEEN ? AND ?""", (per.inicio.isoformat(), per.fim.isoformat()))
    ids = [l["id_pub"] for l in linhas]
    provs = _provincias_de(bd, ids)
    if modo == "sinalizadas":
        ameaca = {l["id_pub"]: l["cat_modelo"] for l in linhas if l["cat_modelo"] and l["cat_modelo"] != "Normal"}
    else:
        ameaca = _confirmadas(bd, minc, ids)
    if categoria:
        ameaca = {k: v for k, v in ameaca.items() if v == categoria}
    mencoes, valores = Counter(), Counter()
    por_cat: dict[str, Counter] = defaultdict(Counter)
    for idp in ids:
        ps = provs.get(idp) or [SEM_LOCAL]
        for pr in ps:
            mencoes[pr] += 1
            if idp in ameaca:
                valores[pr] += 1
                por_cat[pr][ameaca[idp]] += 1
        mencoes[NACIONAL] += 1
        if idp in ameaca:
            valores[NACIONAL] += 1
            por_cat[NACIONAL][ameaca[idp]] += 1
    return {"mencoes": mencoes, "valores": valores, "por_categoria": por_cat, "ameacas": ameaca, "provs": provs,
            "total": len(ids)}


def verificar_tendencias(bd: BaseDados, hoje: date | None = None) -> list[int]:
    """Alerta quando as ameaças confirmadas numa província (ou no país) crescem face à janela anterior.

    Condições: pelo menos `min_casos` ameaças confirmadas na janela actual, crescimento de
    pelo menos `factor` vezes face à janela anterior e peso no total recolhido também a subir
    (ameaças da zona ÷ publicações recolhidas na janela), para que mais recolha, por si só,
    não pareça mais ameaça.
    """
    defs = ler_definicoes(bd)
    fim = hoje or hoje_luanda()
    actual = Periodo(fim - timedelta(days=defs["janela_dias"] - 1), fim)
    a = _contagens(bd, actual, "confirmadas", defs["min_confirmacoes"])
    b = _contagens(bd, actual.anterior, "confirmadas", defs["min_confirmacoes"])
    novos = []
    for pr in [*PROVINCIAS, NACIONAL]:
        va, vb = a["valores"][pr], b["valores"][pr]
        ma, mb = a["mencoes"][pr], b["mencoes"][pr]
        if va < defs["min_casos"] or va < defs["factor"] * max(vb, 1):
            continue
        pa = va / a["total"] if a["total"] else 0.0
        pb = vb / b["total"] if b["total"] else 0.0
        if pa <= pb:
            continue
        ta, tb = va / ma if ma else 0.0, (vb / mb if mb else 0.0)
        nome = "todo o país" if pr == NACIONAL else PROVINCIAS[pr]
        cats = dict(a["por_categoria"][pr].most_common())
        titulo = f"Tendência: ameaças confirmadas a subir em {nome} ({vb} → {va} em {defs['janela_dias']} dias)"
        idn = _criar(bd, "tendencia", f"tendencia:{pr}:{fim.isoformat()}:{defs['janela_dias']}", titulo,
                     max(cats, key=cats.get) if cats else None, pr, None,
                     {"janela": actual.rotulo(), "anterior": actual.anterior.rotulo(), "confirmadas": va,
                      "confirmadas_antes": vb, "mencoes": ma, "mencoes_antes": mb, "taxa": round(ta, 4),
                      "taxa_antes": round(tb, 4), "recolhidas": a["total"], "recolhidas_antes": b["total"],
                      "peso": round(pa, 4), "peso_antes": round(pb, 4), "por_categoria": cats})
        if idn:
            novos.append(idn)
    return novos


# ---------------------------------------------------------------- e-mail
def enviar_email(cfg: Config, destinos: list[str], assunto: str, corpo: str,
                 fabrica_smtp: Callable | None = None) -> None:
    if not cfg.email_configurado:
        raise RuntimeError("E-mail não configurado (UAN_SMTP_SERVIDOR e UAN_SMTP_REMETENTE no uan.env).")
    if not destinos:
        raise RuntimeError("Sem destinatários definidos em Definições.")
    msg = EmailMessage()
    msg["From"] = cfg.smtp_remetente or cfg.smtp_utilizador
    msg["To"] = ", ".join(destinos)
    msg["Subject"] = assunto
    msg.set_content(corpo)
    if fabrica_smtp is None:
        fabrica_smtp = smtplib.SMTP_SSL if cfg.smtp_porta == 465 else smtplib.SMTP
    with fabrica_smtp(cfg.smtp_servidor, cfg.smtp_porta, timeout=30) as s:
        if cfg.smtp_tls and cfg.smtp_porta != 465 and hasattr(s, "starttls"):
            s.starttls(context=ssl.create_default_context())
        if cfg.smtp_utilizador:
            s.login(cfg.smtp_utilizador, cfg.smtp_senha)
        s.send_message(msg)


def corpo_alerta(a, cfg: Config) -> tuple[str, str]:
    det = json.loads(a["detalhe"] or "{}")
    linhas = [a["titulo"], ""]
    if a["tipo"] == "confirmado":
        linhas += [f"Categoria confirmada: {NOMES_APRESENTACAO.get(a['categoria'], a['categoria'])}",
                   f"Província mencionada: {nomes_provincias(det.get('provincias'))}",
                   f"Data da publicação: {det.get('dia_publicacao') or '—'}",
                   f"Plataforma: {det.get('plataforma') or '—'}",
                   f"Analistas que confirmaram: {det.get('analistas_confirmaram')}",
                   "", f"Ver no sistema: {cfg.url_base}/publicacao/{a['id_pub']}"]
    else:
        linhas += [f"Janela: {det.get('janela')} (anterior: {det.get('anterior')})",
                   f"Ameaças confirmadas: {det.get('confirmadas_antes')} → {det.get('confirmadas')}",
                   f"Publicações recolhidas em cada janela: {det.get('recolhidas_antes')} → {det.get('recolhidas')}",
                   f"Peso das ameaças da zona no total recolhido: {100 * det.get('peso_antes', 0):.1f}% → "
                   f"{100 * det.get('peso', 0):.1f}%",
                   "", f"Ver no mapa: {cfg.url_base}/mapa"]
    linhas += ["", "Este e-mail não contém o texto das publicações nem dados dos autores.",
               "A província é o lugar mencionado na publicação, não a localização de quem a escreveu.",
               "Uma convocatória pacífica é exercício de direitos (arts. 40.º e 47.º da Constituição)."]
    return f"[Sistema UAN] {a['titulo']}", "\n".join(linhas)


def notificar(bd: BaseDados, cfg: Config, ids: list[int], sincrono: bool = False,
              fabrica_smtp: Callable | None = None) -> None:
    """Envia por e-mail os alertas novos; regista o resultado no próprio alerta e na auditoria."""
    if not ids:
        return
    destinos = ler_definicoes(bd)["destinatarios"]

    def tarefa():
        for ida in ids:
            a = bd.consultar("SELECT * FROM alertas WHERE id_alerta = ?", (ida,))
            if not a:
                continue
            a = a[0]
            if not cfg.email_configurado or not destinos:
                estado = "nao_configurado"
            else:
                try:
                    assunto, corpo = corpo_alerta(a, cfg)
                    enviar_email(cfg, destinos, assunto, corpo, fabrica_smtp)
                    estado = "enviado"
                except Exception as e:  # o alerta fica na aplicação mesmo que o e-mail falhe
                    log.exception("Falha ao enviar o alerta %s", ida)
                    estado = f"falhou: {str(e)[:150]}"
            with bd.ligacao() as c:
                c.execute("UPDATE alertas SET email_estado = ?, email_em = ? WHERE id_alerta = ?", (estado, agora(), ida))
            if estado != "nao_configurado":
                bd.auditar("sistema", "alerta_email", {"id_alerta": ida, "estado": estado, "destinatarios": len(destinos)})

    if sincrono:
        tarefa()
    else:
        threading.Thread(target=tarefa, name="alertas-email", daemon=True).start()


def apos_revisao(bd: BaseDados, cfg: Config, id_pub: str, sincrono: bool = False,
                 fabrica_smtp: Callable | None = None) -> list[int]:
    """Chamado depois de cada decisão: alerta confirmado e verificação de tendência."""
    novos = [i for i in [alerta_confirmado(bd, id_pub)] if i]
    novos += verificar_tendencias(bd)
    notificar(bd, cfg, novos, sincrono=sincrono, fabrica_smtp=fabrica_smtp)
    return novos


# ---------------------------------------------------------------- mapa e relatório
def dados_mapa(bd: BaseDados, per: Periodo, modo: str = "confirmadas", categoria: str | None = None) -> dict:
    defs = ler_definicoes(bd)
    modo = modo if modo in ("confirmadas", "sinalizadas") else "confirmadas"
    a = _contagens(bd, per, modo, defs["min_confirmacoes"], categoria)
    b = _contagens(bd, per.anterior, modo, defs["min_confirmacoes"], categoria)
    linhas = []
    for cod, nome in PROVINCIAS.items():
        ma, va, mb, vb = a["mencoes"][cod], a["valores"][cod], b["mencoes"][cod], b["valores"][cod]
        suficiente = ma >= defs["min_casos"]
        linhas.append({"codigo": cod, "nome": nome, "mencoes": ma, "valor": va, "taxa": va / ma if suficiente else None,
                       "mencoes_antes": mb, "valor_antes": vb, "taxa_antes": vb / mb if mb >= defs["min_casos"] else None,
                       "variacao": va - vb, "suficiente": suficiente,
                       "categorias": dict(a["por_categoria"][cod].most_common())})
    taxas = [l["taxa"] for l in linhas if l["taxa"] is not None]
    return {"periodo": per, "anterior": per.anterior, "modo": modo, "categoria": categoria, "provincias": linhas,
            "max_taxa": max(taxas) if taxas else 0.0, "min_casos": defs["min_casos"],
            "nacional": {"mencoes": a["total"], "valor": a["valores"][NACIONAL], "valor_antes": b["valores"][NACIONAL],
                         "categorias": dict(a["por_categoria"][NACIONAL].most_common())},
            "sem_local": {"mencoes": a["mencoes"][SEM_LOCAL], "valor": a["valores"][SEM_LOCAL]}}


def relatorio(bd: BaseDados, per: Periodo) -> dict:
    """Relatório de alertas de ameaças no período escolhido (confirmadas pelos analistas)."""
    defs = ler_definicoes(bd)
    mapa_c = dados_mapa(bd, per, "confirmadas")
    sinal = _contagens(bd, per, "sinalizadas", defs["min_confirmacoes"])
    conf = _contagens(bd, per, "confirmadas", defs["min_confirmacoes"])
    alertas = bd.consultar(
        """SELECT * FROM alertas WHERE substr(criado_em, 1, 10) BETWEEN ? AND ? ORDER BY criado_em DESC""",
        (per.inicio.isoformat(), per.fim.isoformat()))
    ids = list(conf["ameacas"])
    detalhes = {}
    for i in range(0, len(ids), 900):
        parte = ids[i:i + 900]
        for r in bd.consultar(
                f"""SELECT p.id_pub, {DATA_PUB} AS dia, p.plataforma, p.texto, p.contexto FROM publicacoes p
                    WHERE p.id_pub IN ({','.join('?' * len(parte))})""", tuple(parte)):
            detalhes[r["id_pub"]] = r
    ameacas = sorted(({"id_pub": i, "categoria": c, "dia": detalhes[i]["dia"], "plataforma": detalhes[i]["plataforma"],
                       "provincias": conf["provs"].get(i, []), "excerto": (detalhes[i]["texto"] or "")[:240]}
                      for i, c in conf["ameacas"].items() if i in detalhes), key=lambda x: (x["dia"] or ""), reverse=True)
    por_categoria = [{"categoria": c, "sinalizadas": Counter(sinal["ameacas"].values())[c],
                      "confirmadas": Counter(conf["ameacas"].values())[c]} for c in ROTULOS if c != "Normal"]
    revistas = bd.consultar(
        f"""SELECT COUNT(DISTINCT r.id_pub) AS n FROM revisoes r JOIN publicacoes p ON p.id_pub = r.id_pub
            WHERE {DATA_PUB} BETWEEN ? AND ?""", (per.inicio.isoformat(), per.fim.isoformat()))[0]["n"]
    return {"periodo": per, "gerado_em": agora(), "mapa": mapa_c, "alertas": alertas, "ameacas": ameacas,
            "por_categoria": por_categoria,
            "kpi": {"publicacoes": conf["total"], "sinalizadas": len(sinal["ameacas"]), "revistas": revistas,
                    "confirmadas": len(conf["ameacas"]), "alertas": len(alertas),
                    "confirmadas_antes": mapa_c["nacional"]["valor_antes"]}}


def relatorio_csv(rel: dict) -> str:
    f = io.StringIO()
    w = csv.writer(f)
    per = rel["periodo"]
    w.writerow(["Relatório de alertas de ameaças", per.rotulo()])
    w.writerow([])
    w.writerow(["provincia", "publicacoes_que_mencionam", "ameacas_confirmadas", "taxa", "confirmadas_periodo_anterior",
                "variacao"])
    for l in rel["mapa"]["provincias"]:
        w.writerow([l["nome"], l["mencoes"], l["valor"], "" if l["taxa"] is None else f"{l['taxa']:.4f}",
                    l["valor_antes"], l["variacao"]])
    w.writerow(["Sem localização", rel["mapa"]["sem_local"]["mencoes"], rel["mapa"]["sem_local"]["valor"], "", "", ""])
    w.writerow([])
    w.writerow(["categoria", "sinalizadas_pelo_modelo", "confirmadas_pelos_analistas"])
    for c in rel["por_categoria"]:
        w.writerow([NOMES_APRESENTACAO[c["categoria"]], c["sinalizadas"], c["confirmadas"]])
    w.writerow([])
    w.writerow(["alerta", "tipo", "criado_em", "provincia", "categoria"])
    for a in rel["alertas"]:
        w.writerow([a["titulo"], a["tipo"], a["criado_em"], PROVINCIAS.get(a["provincia"] or "", a["provincia"] or ""),
                    NOMES_APRESENTACAO.get(a["categoria"] or "", "")])
    return f.getvalue()


def corpo_relatorio(rel: dict, cfg: Config) -> tuple[str, str]:
    per, k = rel["periodo"], rel["kpi"]
    linhas = [f"Relatório de alertas de ameaças · {per.rotulo()}", "",
              f"Publicações no período: {k['publicacoes']}",
              f"Sinalizadas pelo modelo: {k['sinalizadas']}",
              f"Revistas por analistas: {k['revistas']}",
              f"Ameaças confirmadas: {k['confirmadas']} (período anterior: {k['confirmadas_antes']})",
              f"Alertas gerados: {k['alertas']}", "", "Ameaças confirmadas por categoria:"]
    linhas += [f"  {NOMES_APRESENTACAO[c['categoria']]}: {c['confirmadas']}" for c in rel["por_categoria"]]
    linhas += ["", "Províncias com mais ameaças confirmadas (lugar mencionado):"]
    top = sorted((l for l in rel["mapa"]["provincias"] if l["valor"]), key=lambda l: -l["valor"])[:8]
    linhas += [f"  {l['nome']}: {l['valor']} ({'+' if l['variacao'] >= 0 else ''}{l['variacao']} face ao período anterior)"
               for l in top] or ["  nenhuma"]
    linhas += ["", f"Relatório completo: {cfg.url_base}/relatorio?de={per.inicio}&ate={per.fim}", "",
               "Este e-mail não contém o texto das publicações nem dados dos autores."]
    return f"[Sistema UAN] Relatório de alertas de ameaças · {per.rotulo()}", "\n".join(linhas)
