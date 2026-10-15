"""Modo de demonstração: base de dados separada, com dados FICTÍCIOS, para apresentações e para a defesa.

    python uan.py servir --demonstracao

- usa sempre outra base de dados (dados/demonstracao.db), nunca a base real;
- os textos são inventados a partir de modelos de frase e lugares; nenhum vem de redes sociais;
- usa o classificador de demonstração (palavras-chave), não o BERTimbau;
- nenhum e-mail sai do sistema: o servidor de e-mail é ignorado neste modo;
- todas as páginas mostram a faixa "Demonstração".

Contas criadas: demo.supervisor e demo.analista, palavra-passe "demonstracao".
"""

from __future__ import annotations

import random
from datetime import timedelta
from pathlib import Path

from . import alertas as al
from .base_dados import BaseDados
from .classificador import ClassificadorDemonstracao
from .servico import classificar_pendentes, importar_registos, preparar_registos
from .utilizadores import criar_utilizador

SENHA = "demonstracao"
CONTAS = (("demo.supervisor", "Supervisor (demonstração)", "supervisor"),
          ("demo.analista", "Analista (demonstração)", "analista"),
          ("demo.revisor", "Segundo analista (demonstração)", "analista"))
SEGREDO = "demonstracao-sem-dados-reais"

# Lugares por província (pesos aproximados ao volume de conversa); None = sem lugar mencionado.
LUGARES = {
    "Luanda": 30, "Cacuaco": 5, "Viana": 6, "Benguela": 10, "Lobito": 6, "Huambo": 8, "Lubango": 7, "Cabinda": 6,
    "Malanje": 4, "Uíge": 4, "Saurimo": 2, "Dundo": 2, "Luena": 2, "Menongue": 2, "Ondjiva": 2, "Namibe": 3,
    "Soyo": 2, "Sumbe": 2, "N'dalatando": 2, "Kuito": 3, "Caxito": 2,
}
FRASES = {
    "Mobilizacao": [
        "Vamos todos amanhã às 9h à praça de {p}, tragam tudo e quem não aparecer é traidor",
        "Vamos todos para a rua em {p}, tragam paus e pedras, amanhã às 10h",
        "Quem não aparecer amanhã às 8h no largo de {p} vai ver, vamos todos fechar a estrada",
    ],
    "Odio": [
        "Esses de {p} não merecem estar aqui, são todos iguais, fora daqui",
        "São todos uns ladrões os de {p}, não merecem nada, fora daqui com eles",
        "Gente de {p} não merecem respeito, são todos iguais",
    ],
    "Desinformacao": [
        "URGENTE: fonte interna diz que em {p} a água foi envenenada, partilha antes que apaguem",
        "Estão a esconder a verdade sobre {p}: fonte interna confirma que os números são falsos",
        "Partilha antes que apaguem! Em {p} estão a esconder o surto, urgente",
    ],
    "Normal": [
        "Hoje o trânsito em {p} estava bom, finalmente chegaram as obras",
        "Alguém sabe se a farmácia de {p} abre ao domingo?",
        "Bom jogo ontem em {p}, parabéns à equipa",
        "A feira de {p} tinha muita fruta boa esta semana",
        "O mercado de {p} está mais caro, mas ainda se compra",
        "Parabéns aos estudantes de {p} pela formatura",
        "Choveu bastante hoje em {p}, cuidado nas estradas",
        "Que saudades do funge da minha avó",
        "Alguém recomenda um bom mecânico?",
        "Excelente reportagem, obrigado pela informação",
    ],
}


def _sortear(rnd: random.Random, pesos: dict) -> str:
    return rnd.choices(list(pesos), weights=list(pesos.values()))[0]


def gerar_registos(hoje, semanas: int = 16, semente: int = 7) -> list[tuple[dict, str]]:
    """(registo bruto, categoria pretendida). Crescimento recente em Benguela e Luanda, descida na Huíla."""
    rnd = random.Random(semente)
    out = []
    n = 0
    for s in range(semanas):
        recente = semanas - s  # 1 = última semana
        for _ in range(rnd.randint(55, 85) + 3 * s):
            dia = hoje - timedelta(days=(semanas - 1 - s) * 7 + rnd.randint(0, 6))
            lugar = _sortear(rnd, LUGARES) if rnd.random() > 0.18 else None
            p_ameaca = 0.22
            if lugar in ("Benguela", "Lobito") and recente <= 3:
                p_ameaca = 0.55
            elif lugar in ("Luanda", "Viana", "Cacuaco") and recente <= 2:
                p_ameaca = 0.4
            elif lugar == "Lubango" and recente <= 4:
                p_ameaca = 0.08
            cat = "Normal"
            if rnd.random() < p_ameaca:
                cat = _sortear(rnd, {"Mobilizacao": 3, "Odio": 3, "Desinformacao": 4})
            frases = FRASES[cat]
            texto = rnd.choice([f for f in frases if ("{p}" in f) == bool(lugar)] or frases)
            texto = texto.format(p=lugar or "aqui")
            n += 1
            out.append(({"id": f"demo-{n:05d}", "authorDisplayName": f"@exemplo{rnd.randint(1, 400)}",
                         "textDisplay": f"{texto} [{n}]", "publishedAt": dia.isoformat(),
                         "contexto": "Vídeo fictício de demonstração"}, cat))
    return out


def povoar(bd: BaseDados, hoje=None) -> dict:
    """Preenche uma base de dados VAZIA com dados fictícios. Não toca numa base que já tenha publicações."""
    if bd.consultar("SELECT COUNT(*) AS n FROM publicacoes")[0]["n"]:
        return {"criada": False}
    hoje = hoje or al.hoje_luanda()
    rnd = random.Random(11)
    for u, nome, papel in CONTAS:
        if not bd.consultar("SELECT 1 FROM utilizadores WHERE utilizador = ?", (u,)):
            criar_utilizador(bd, u, nome, papel, SENHA, quem="demonstracao")
    regs = gerar_registos(hoje)
    brutos, plataforma = [r for r, _ in regs], "YouTube (fictício)"
    pretendida = {p["id_pub"]: c for p, (_, c) in zip(preparar_registos(brutos, plataforma, SEGREDO), regs)}
    importar_registos(bd, brutos, plataforma, "manual", SEGREDO, "Dados fictícios do modo de demonstração",
                      quem="demonstracao")
    classificar_pendentes(bd, ClassificadorDemonstracao(), limite=10**9)
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
    bd.auditar("demonstracao", "demonstracao_criada", {"publicacoes": len(regs), "revistas": revistas,
                                                       "alertas_tendencia": len(tend)})
    return {"criada": True, "publicacoes": len(regs), "revistas": revistas, "alertas_tendencia": len(tend)}


def caminho_bd(pasta_dados: Path) -> Path:
    return pasta_dados / "demonstracao.db"
