"""Modo de demonstração: base de dados separada, com dados FICTÍCIOS, para apresentações e para a defesa.

    python uan.py servir --demonstracao

- usa sempre outra base de dados (dados/demonstracao.db), nunca a base real;
- os textos são inventados (ver demonstracao_dados.py): conversas fictícias com temas, lugares,
  registos e episódios; nenhum vem de redes sociais;
- as sugestões vêm de um classificador SIMULADO, que acerta e erra como um modelo real
  (erra mais na Desinformação e confunde protesto legal com mobilização), não do BERTimbau;
- nenhum e-mail sai do sistema: o servidor de e-mail é ignorado neste modo;
- todas as páginas mostram a faixa "Demonstração".

Contas criadas: demo.supervisor, demo.analista e demo.revisor, palavra-passe "demonstracao".
"""

from __future__ import annotations

import random
from datetime import timedelta
from pathlib import Path

from . import alertas as al
from .base_dados import BaseDados
from .classificador import Classificador, ClassificadorDemonstracao, Resultado
from .config import ROTULOS
from .servico import classificar_pendentes, importar_registos, preparar_registos
from .utilizadores import criar_utilizador
from .demonstracao_dados import PLATAFORMAS, gerar

SENHA = "demonstracao"
CONTAS = (("demo.supervisor", "Supervisor (demonstração)", "supervisor"),
          ("demo.analista", "Analista (demonstração)", "analista"),
          ("demo.revisor", "Segundo analista (demonstração)", "analista"))
SEGREDO = "demonstracao-sem-dados-reais"
VERSAO_DADOS = "3"  # mudar quando o gerador mudar: a base de demonstração antiga é recriada


def precisa_recriar(caminho: Path) -> bool:
    """True se a base de demonstração existe mas foi criada por uma versão anterior do gerador."""
    import sqlite3
    if not Path(caminho).exists():
        return False
    c = None
    try:
        # «with sqlite3.connect» não fecha a ligação; no Windows o ficheiro ficaria bloqueado e não se podia apagar
        c = sqlite3.connect(caminho)
        v = c.execute("SELECT valor FROM definicoes WHERE chave = 'demonstracao_versao'").fetchone()
    except sqlite3.Error:
        return True
    finally:
        if c is not None:
            c.close()
    return not v or v[0] != VERSAO_DADOS

# Taxa de acerto do classificador simulado por categoria (próxima do que o modelo faz em conteúdo
# angolano, um pouco melhor para a demonstração ter uma fila útil).
ACERTO_SIMULADO = {"Normal": 0.93, "Desinformacao": 0.6, "Odio": 0.7, "Mobilizacao": 0.72}


class ClassificadorSimulado(Classificador):
    """Sugestões fictícias: conhece a categoria pretendida de cada texto gerado e erra de propósito.

    Textos que não conhece (por exemplo, importados depois) vão para o classificador de palavras-chave.
    """

    nome = "SIMULADO"
    versao = "demonstracao-2"

    def __init__(self, pretendidas: dict[str, str], semente: int = 5):
        self.pretendidas, self.semente = pretendidas, semente
        self._reserva = ClassificadorDemonstracao()

    def _um(self, texto: str) -> Resultado:
        real = self.pretendidas[texto]
        rnd = random.Random(f"{self.semente}:{texto}")
        ameacas = [c for c in ROTULOS if c != "Normal"]
        if rnd.random() < ACERTO_SIMULADO[real]:
            prevista = real
        elif real == "Normal":
            prevista = rnd.choice(ameacas)
        else:
            prevista = "Normal" if rnd.random() < 0.7 else rnd.choice([c for c in ameacas if c != real])
        p = rnd.uniform(0.46, 0.93)
        resto = [rnd.random() + (0.6 if c == real and c != prevista else 0) for c in ROTULOS if c != prevista]
        soma = sum(resto)
        outras = iter(r / soma * (1 - p) for r in resto)
        return Resultado({c: (p if c == prevista else next(outras)) for c in ROTULOS})

    def classificar(self, textos: list[str]) -> list[Resultado]:
        desconhecidos = [t for t in textos if t not in self.pretendidas]
        reserva = dict(zip(desconhecidos, self._reserva.classificar(desconhecidos))) if desconhecidos else {}
        return [self._um(t) if t in self.pretendidas else reserva[t] for t in textos]


def gerar_registos(hoje, semanas: int = 16, semente: int = 7) -> list[tuple[dict, str]]:
    """(registo bruto, categoria pretendida); compatível com versões anteriores."""
    return [(r, c) for r, c, _ in gerar(hoje, semanas, semente)]


def povoar(bd: BaseDados, hoje=None) -> dict:
    """Preenche uma base de dados VAZIA com dados fictícios. Não toca numa base que já tenha publicações."""
    if bd.consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"]:
        return {"criada": False}
    hoje = hoje or al.hoje_luanda()
    rnd = random.Random(11)
    for u, nome, papel in CONTAS:
        if not bd.consultar("SELECT 1 FROM utilizadores WHERE utilizador = ?", (u,)):
            criar_utilizador(bd, u, nome, papel, SENHA, quem="demonstracao")
    regs = gerar(hoje)
    # um lote por plataforma e por mês, como numa recolha regular
    grupos: dict[tuple[str, str], list[tuple[dict, str]]] = {}
    for r, c, plat in regs:
        bloco = r["publishedAt"][:7]
        grupos.setdefault((plat, bloco), []).append((r, c))
    pretendida: dict[str, str] = {}
    por_texto: dict[str, str] = {}
    for (plat, bloco), itens in sorted(grupos.items(), key=lambda x: (x[0][1], x[0][0])):
        brutos = [r for r, _ in itens]
        for prep, (_, c) in zip(preparar_registos(brutos, plat, SEGREDO), itens):
            pretendida[prep["id_pub"]] = c
            por_texto[prep["texto"]] = c
        importar_registos(bd, brutos, plat, PLATAFORMAS[plat][0], SEGREDO,
                          f"Dados fictícios · {plat} · {bloco}", quem="demonstracao")
    classificar_pendentes(bd, ClassificadorSimulado(por_texto), limite=10**9)
    linhas = bd.consultar("""SELECT p.id_pub, k.categoria, substr(COALESCE(p.data_publicacao, p.recolhido_em), 1, 10) AS dia
                             FROM publicacoes p JOIN classificacoes k ON k.id_pub = p.id_pub ORDER BY k.prioridade DESC""")
    revistas = 0
    for i, l in enumerate(linhas):
        real = pretendida.get(l["id_pub"], "Normal")
        if l["categoria"] == "Normal" and rnd.random() > 0.04:
            continue  # a fila mostra primeiro o que o modelo sinaliza; poucos Normais são vistos
        if rnd.random() > 0.8:
            continue  # parte da fila ainda por rever
        decisao = real if rnd.random() < 0.88 else "Normal"
        bd.gravar_revisao(l["id_pub"], "demo.analista", decisao, i + 1, None)
        if rnd.random() < 0.3:  # segundo analista em parte dos itens, para haver Kappa entre analistas
            bd.gravar_revisao(l["id_pub"], "demo.revisor", decisao if rnd.random() < 0.85 else real, i + 1, None)
        novo = al.alerta_confirmado(bd, l["id_pub"])
        if novo:  # o alerta fica datado do dia da publicação, como se tivesse sido revista nesse dia
            with bd.ligacao() as c:
                c.execute("UPDATE alertas SET criado_em = ?, email_estado = 'demonstracao' WHERE id_alerta = ?",
                          (f"{l['dia']}T{rnd.randint(8, 17):02d}:{rnd.randint(0, 59):02d}:00+00:00", novo))
        revistas += 1
    tend = al.verificar_tendencias(bd, hoje)
    limite = (hoje - timedelta(days=2)).isoformat()
    with bd.ligacao() as c:
        c.execute("UPDATE alertas SET email_estado = 'demonstracao'")
        for u, _, _ in CONTAS:  # os alertas antigos já foram vistos; ficam por ver os dos últimos dias
            c.execute("""INSERT OR IGNORE INTO alertas_vistos(id_alerta, utilizador, visto_em)
                         SELECT id_alerta, ?, criado_em FROM alertas WHERE substr(criado_em, 1, 10) < ?""", (u, limite))
    bd.definir("demonstracao", "1", "demonstracao")
    bd.definir("demonstracao_versao", VERSAO_DADOS, "demonstracao")
    bd.auditar("demonstracao", "demonstracao_criada", {"publicacoes": len(regs), "revistas": revistas,
                                                       "alertas_tendencia": len(tend)})
    return {"criada": True, "publicacoes": len(regs), "revistas": revistas, "alertas_tendencia": len(tend)}


def caminho_bd(pasta_dados: Path) -> Path:
    return pasta_dados / "demonstracao.db"
