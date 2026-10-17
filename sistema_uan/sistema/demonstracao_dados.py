"""Gerador dos dados FICTÍCIOS do modo de demonstração.

Os textos não vêm de nenhuma rede social: são compostos a partir de uma pequena
gramática (abertura, assunto, pormenor, fecho) com vocabulário de cada tema, registos
diferentes (formal, coloquial, com calão urbano) e comprimentos variados. As publicações
organizam-se como numa recolha real:

- cada publicação pertence a uma CONVERSA (um vídeo, uma publicação de página ou uma
  notícia fictícia) com tema, lugar e data;
- há conversa de fundo todas as semanas, em todo o país, sobretudo Normal;
- há EPISÓDIOS com princípio e fim, que fazem crescer uma categoria num lugar
  (por exemplo, um boato de cólera em Benguela nas últimas semanas), para que o mapa,
  as tendências e os alertas tenham alguma coisa para mostrar;
- há casos de fronteira de propósito: convocatórias pacíficas e legais (Normal),
  críticas duras ao Governo (Normal), ironia, perguntas sobre boatos.

Nada aqui descreve pessoas ou acontecimentos reais. Os nomes de canais, páginas e
autores são inventados e marcados como fictícios.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

# --------------------------------------------------------------------------- lugares
# cidade -> bairros ou localidades que o sistema reconhece (ou não) como da mesma província
LUGARES: dict[str, tuple[int, tuple[str, ...]]] = {
    "Luanda": (30, ("Cazenga", "Viana", "Kilamba", "Sambizanga", "Cacuaco", "Talatona", "Maianga", "Zango", "Camama")),
    "Benguela": (9, ("Lobito", "Catumbela", "Baía Farta", "Cubal")),
    "Huambo": (8, ("Caála", "Bailundo", "Longonjo")),
    "Lubango": (7, ("Matala", "Chibia", "Humpata")),
    "Cabinda": (5, ("Cacongo", "Buco Zau")),
    "Malanje": (4, ("Cacuso", "Calandula")),
    "Uíge": (4, ("Negage", "Quitexe")),
    "Saurimo": (2, ("Cacolo",)),
    "Dundo": (2, ("Lucapa", "Chitato")),
    "Luena": (2, ("Cazombo",)),
    "Menongue": (2, ("Cuito Cuanavale",)),
    "Ondjiva": (2, ("Xangongo",)),
    "Namibe": (3, ("Tômbwa", "Bibala")),
    "Soyo": (2, ("Nzeto",)),
    "Sumbe": (2, ("Gabela", "Porto Amboim")),
    "N'dalatando": (2, ("Dondo",)),
    "Kuito": (3, ("Andulo", "Camacupa")),
    "Caxito": (2, ("Ambriz",)),
}

PLATAFORMAS = {  # nome -> (via, peso, canais/páginas fictícios)
    "YouTube (fictício)": ("api_oficial", 6, ("Canal Kianda Notícias", "Debate Aberto TV", "Mwangolé Directo",
                                              "Canal Bairro a Bairro", "Ngola Desporto")),
    "Facebook (fictício)": ("doacao", 3, ("Página Somos {cidade}", "Grupo público Vendas e Avisos {cidade}",
                                          "Página Notícias de {cidade}")),
    "Portal de notícias (fictício)": ("scraping_publico", 1, ("Jornal Palanca", "Diário da Kianda", "Semanário Mulemba")),
}

# --------------------------------------------------------------------------- temas
# Cada tema: títulos de conversa e o vocabulário que os comentários usam.
TEMAS: dict[str, dict] = {
    "transporte": {
        "titulos": ("Taxistas discutem novo preço da corrida em {cidade}", "Candongueiros: o que muda com as novas paragens em {cidade}",
                    "Estrada nacional entre {cidade} e {bairro} continua cortada"),
        "assunto": ("o preço do táxi", "a estrada para {bairro}", "a paragem nova do {bairro}", "o combustível"),
        "factos": ("o táxi já subiu duas vezes este ano", "ninguém explicou as paragens novas aos passageiros",
                   "a estrada para {bairro} está cheia de buracos desde as chuvas", "perdemos duas horas por dia no trânsito",
                   "os candongueiros cobram o que querem à noite", "a ponte do {bairro} continua sem obras",
                   "os autocarros públicos passam de hora a hora", "o combustível faltou outra vez nas bombas"),
    },
    "agua_luz": {
        "titulos": ("Falta de água no {bairro}: moradores sem resposta", "Cortes de energia em {cidade} esta semana",
                    "Empresa de águas promete normalizar abastecimento em {cidade}"),
        "assunto": ("a água no {bairro}", "a luz", "o abastecimento", "os cortes de energia"),
        "factos": ("a água faltou três dias seguidos no {bairro}", "compramos bidões a preço de ouro",
                   "a luz vai e vem e a geladeira já estragou", "as crianças vão à escola sem tomar banho",
                   "o camião-cisterna só aparece à noite", "a factura da luz veio mais cara com menos horas de energia",
                   "o gerador do prédio trabalha mais do que a rede"),
    },
    "saude": {
        "titulos": ("Hospital de {cidade} recebe novos equipamentos", "Casos de diarreia no {bairro}: o que se sabe",
                    "Campanha de vacinação chega a {cidade}"),
        "assunto": ("o hospital", "a campanha de vacinação", "os casos de diarreia", "a farmácia do {bairro}"),
        "factos": ("a fila do hospital começa às 5h da manhã", "falta paracetamol no posto do {bairro}",
                   "+o atendimento no banco de urgência melhorou, verdade seja dita", "ninguém informou os horários da vacinação",
                   "+a enfermeira do {bairro} atende com paciência", "a ambulância demorou mais de uma hora",
                   "o centro de saúde novo ainda não abriu"),
    },
    "educacao": {
        "titulos": ("Propinas: estudantes de {cidade} pedem explicações", "Início do ano lectivo em {cidade}",
                    "Professores de {cidade} reclamam salários em atraso"),
        "assunto": ("as propinas", "o ano lectivo", "a escola do {bairro}", "os exames"),
        "factos": ("as propinas aumentaram sem aviso", "as salas têm mais de oitenta alunos",
                   "os professores estão sem receber há três meses", "faltam carteiras e livros na escola do {bairro}",
                   "a universidade ainda não publicou o calendário", "os miúdos estudam debaixo da árvore",
                   "+a directora da escola do {bairro} explicou tudo na reunião de pais"),
    },
    "economia": {
        "titulos": ("Preço do pão e do óleo volta a subir em {cidade}", "Zungueiras de {cidade} queixam-se de fiscalização",
                    "Kwanza: o que esperar este mês"),
        "assunto": ("o preço da cesta básica", "a fiscalização no mercado", "o câmbio", "o mercado do {bairro}"),
        "factos": ("o salário acaba na primeira semana", "a fiscalização levou a mercadoria das zungueiras",
                   "o pão já custa o dobro do ano passado", "o mercado do {bairro} está vazio desde as obras",
                   "o kumbu não chega para o mês", "o óleo subiu outra vez na cantina do {bairro}",
                   "+a feira de sábado ajudou os pequenos vendedores"),
    },
    "desporto": {
        "lazer": True,
        "titulos": ("Girabola: resumo da jornada", "Equipa de {cidade} sobe na tabela", "Selecção: lista de convocados"),
        "assunto": ("o jogo de ontem", "o treinador", "a arbitragem", "a nossa equipa"),
        "factos": ("+merecíamos ganhar o jogo de ontem", "o árbitro estragou a segunda parte", "+o miúdo da frente joga bué",
                   "faltou atitude depois do intervalo", "+o estádio de {cidade} estava cheio", "o treinador mexeu tarde na equipa",
                   "+a equipa de {cidade} está a jogar o melhor futebol do campeonato"),
    },
    "cultura": {
        "lazer": True,
        "titulos": ("Festival de música em {cidade} este fim de semana", "Carnaval: grupos de {cidade} preparam desfile",
                    "Feira do livro chega a {cidade}"),
        "assunto": ("o festival", "o desfile", "a feira do livro", "o concerto no {bairro}"),
        "factos": ("+o festival estava bué organizado", "+os bilhetes esgotaram cedo", "faltou segurança à saída do concerto",
                   "+o grupo do {bairro} vai desfilar este ano", "+a feira do livro trouxe autores angolanos novos",
                   "+o semba ao vivo foi o melhor da noite"),
    },
}

ABERTURAS_COLOQUIAIS = ("Ya,", "Mano,", "Kota,", "Epá,", "Olha,", "Ihh,", "Bom dia a todos.", "Sinceramente,", "Eish,", "")
FECHOS_COLOQUIAIS = ("", "", " Deus nos ajude.", " É só isso.", " Ninguém merece.", " Vamos ver.", " 🙏", " 😡", " 😂", " Força!")


@dataclass(frozen=True)
class Episodio:
    categoria: str
    cidade: str
    tema: str
    semanas: tuple[int, int]   # (início, fim) contadas a partir do fim; 1 = última semana
    intensidade: float          # fracção das publicações da conversa que são desta categoria
    peso: float                 # quantas conversas extra por semana


# Episódios fictícios: dão forma ao mapa e às tendências (crescimento recente em Benguela e
# Luanda, descida na Huíla, picos curtos noutras províncias).
EPISODIOS = (
    Episodio("Desinformacao", "Benguela", "saude", (3, 1), 0.55, 3.0),       # boato de cólera, recente
    Episodio("Mobilizacao", "Luanda", "transporte", (2, 1), 0.45, 4.0),      # paralisação com intimidação
    Episodio("Odio", "Luanda", "economia", (6, 4), 0.35, 2.0),               # zungueiras e fiscalização
    Episodio("Odio", "Lubango", "desporto", (12, 8), 0.40, 2.0),             # rivalidade que acalma
    Episodio("Desinformacao", "Cabinda", "economia", (9, 7), 0.45, 1.5),     # boato sobre o kwanza
    Episodio("Mobilizacao", "Huambo", "educacao", (5, 4), 0.30, 1.5),        # propinas
    Episodio("Desinformacao", "Malanje", "agua_luz", (14, 13), 0.40, 1.0),
)


# --------------------------------------------------------------------------- composição
def _lugar(rnd: random.Random, cidade: str) -> tuple[str, str]:
    bairro = rnd.choice(LUGARES[cidade][1])
    return cidade, bairro


def _sem_lugar(texto: str, cidade: str, bairro: str) -> str:
    """Retira os nomes de lugar de um texto já composto (muitos comentários não dizem onde)."""
    import re as _re
    b = _re.escape(bairro)
    texto = _re.sub(rf"\b(em|no|na) {b}\b", "no bairro", texto)
    texto = _re.sub(rf"\b(No|Na) {b}\b", "No bairro", texto)
    texto = _re.sub(rf"\b(do|da) {b}\b", "do bairro", texto)
    texto = _re.sub(rf"\bpara {b}\b", "para o bairro", texto)
    texto = texto.replace(bairro, "o bairro")
    c = _re.escape(cidade)
    texto = _re.sub(rf"\baqui em {c}\b", "aqui", texto)
    texto = _re.sub(rf"\bem {c}\b", "aqui", texto)
    texto = _re.sub(rf"\bde {c}\b", "daqui", texto)
    texto = texto.replace("Malta daqui", "Malta").replace(cidade, "a cidade")
    return _maiuscula(texto)


def _maiuscula(t: str) -> str:
    import re as _re
    t = t.strip()
    t = _re.sub(r"([.!?] )([a-zà-ú])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t[:1].upper() + t[1:]


def _fmt(t: str, cidade: str, bairro: str) -> str:
    return t.replace("{cidade}", cidade).replace("{bairro}", bairro)


def _normal(rnd, tema, cidade, bairro) -> str:
    v = TEMAS[tema]
    a = _fmt(rnd.choice(v["assunto"]), cidade, bairro)
    maus = [_fmt(x, cidade, bairro) for x in v["factos"] if not x.startswith("+")]
    bons = [_fmt(x[1:], cidade, bairro) for x in v["factos"] if x.startswith("+")] or maus
    f, f2 = rnd.sample(maus, 2) if len(maus) > 1 else (maus[0], maus[0])
    b = rnd.choice(bons)
    comuns = [
        lambda: f"{rnd.choice(ABERTURAS_COLOQUIAIS)} aqui em {cidade} {rnd.choice((f, b))}.{rnd.choice(FECHOS_COLOQUIAIS)}",
        lambda: f"Alguém sabe o que se passa com {a}? Ouvi dizer que {rnd.choice((f, b))}.",
        lambda: f"Obrigado pela informação. Moro em {cidade} e confirmo que {rnd.choice((f, b))}.",
        lambda: f"Kkkk {a} 😂 só em {cidade} mesmo.",
        lambda: f"{_maiuscula(b)}. Gostei muito.",
        lambda: f"No {bairro} também se fala disso: {rnd.choice((f, b))}.",
    ]
    civicas = [
        lambda: f"Concordo com a reportagem: {f}. As autoridades de {cidade} têm de responder.",
        lambda: f"No {bairro} é igual, {f}. Mas pelo menos agora há informação.",
        lambda: f"É verdade que {f}, mas também é verdade que {b}.",
        lambda: f"O Governo prometeu e não cumpriu: {f}. Isto tem de mudar nas próximas eleições.",
        lambda: f"Há quem diga que a situação d{'a' if a.startswith('a ') else 'o'}{'s' if a.split(' ')[0] in ('os', 'as') else ''} {a.split(' ', 1)[1]} vai piorar. Alguém tem fonte oficial? Não partilhem sem confirmar.",
        lambda: f"Bom trabalho da administração de {cidade}: {b}.",
        lambda: f"{_maiuscula(f)}. {_maiuscula(f2)}. Quem manda devia vir ver.",
        lambda: f"Manifestação pacífica e comunicada ao Governo Provincial: sábado às 10h no largo do {bairro}, "
                f"sobre {a}. Levem água e cartazes, sem confusão.",
        lambda: f"Vamos todos assinar a petição sobre {a}. É o nosso direito, de forma ordeira.",
        lambda: f"Reunião de moradores no {bairro} na quinta às 18h para falar sobre {a}. Tragam ideias.",
    ]
    formas = comuns + ([] if v.get("lazer") else civicas * 2)
    return _maiuscula(rnd.choice(formas)())


def _desinformacao_base(rnd, tema, cidade, bairro) -> str:
    urg = rnd.choice(("URGENTE:", "ATENÇÃO!!!", "Partilhem antes que apaguem:", "Ninguém está a falar disto:", "Áudio que está a circular:"))
    fonte = rnd.choice(("um primo meu que trabalha no hospital", "fonte interna do ministério", "um amigo da polícia",
                        "um documento que vazou", "uma enfermeira que não quer ser identificada"))
    alegacoes = {
        "saude": (f"há cólera em {cidade} e estão a esconder os mortos", f"a água do {bairro} foi envenenada de propósito",
                  "a vacina da campanha deixa as crianças estéreis"),
        "economia": ("os bancos vão fechar na segunda e ninguém vai conseguir levantar o kumbu",
                     "o kwanza vai ser trocado por notas novas e as antigas deixam de valer amanhã",
                     f"o Governo vai proibir a venda na rua em {cidade} a partir de segunda"),
        "agua_luz": (f"vão cortar a água em {cidade} durante um mês inteiro", f"a luz no {bairro} foi cortada para castigar os moradores"),
        "transporte": (f"a estrada de {cidade} vai ser fechada para sempre", "o combustível vai custar o triplo a partir de amanhã"),
        "educacao": (f"as escolas de {cidade} vão fechar o ano todo", "os exames foram anulados e ninguém passa de classe"),
        "desporto": ("o campeonato foi comprado e os resultados já estão decididos",),
        "cultura": (f"o festival de {cidade} foi cancelado por causa de uma doença",),
    }[tema]
    al_ = rnd.choice(alegacoes)
    formas = [
        lambda: f"{urg} {fonte} confirmou que {al_}. Partilhem com a família!",
        lambda: f"{urg} {al_}. Quem avisa amigo é. A televisão não vai mostrar.",
        lambda: f"Segundo {fonte}, {al_}. Estão a esconder a verdade, passem a mensagem.",
        lambda: f"{_maiuscula(al_)}!!! Vi com os meus olhos no {bairro}. Estão a esconder.",
    ]
    return _maiuscula(rnd.choice(formas)())


def _odio(rnd, tema, cidade, bairro) -> str:
    alvo = rnd.choice(("esses de fora", "os estrangeiros que vêm para cá", "esses vendedores do mercado",
                       "os do bairro ao lado", "esses adeptos", "os taxistas", "essa gente que chegou agora",
                       "os do outro lado do rio"))
    juizo = rnd.choice(("não prestam", "são todos ladrões", "não merecem viver aqui", "são uma praga",
                        "deviam ser corridos daqui", "são todos iguais, nenhum presta", "só trazem problemas",
                        "não são gente de confiança"))
    culpa = _fmt(rnd.choice([x.lstrip("+") for x in TEMAS[tema]["factos"] if not x.startswith("+")] or ["tudo piorou"]),
                 cidade, bairro)
    formas = [
        lambda: f"{_maiuscula(alvo)} {juizo}. {cidade} era melhor antes deles.",
        lambda: f"O problema de {cidade} são {alvo}, {juizo}.",
        lambda: f"Já disse e repito: {alvo} {juizo}. Fora daqui!",
        lambda: f"No {bairro} toda a gente sabe que {alvo} {juizo}.",
        lambda: f"{_maiuscula(culpa)} e a culpa é d{'os' if alvo.startswith(('os', 'esses')) else 'a'} {alvo.split(' ', 1)[1]}. {_maiuscula(juizo)}.",
        lambda: f"Enquanto {alvo} andarem por aqui, {culpa}. {_maiuscula(juizo)}, ponto final.",
    ]
    return _maiuscula(rnd.choice(formas)())


def _mobilizacao(rnd, tema, cidade, bairro) -> str:
    dia = rnd.choice(("amanhã", "segunda-feira", "na sexta", "este sábado", "depois do jogo", "na quarta"))
    hora = rnd.choice(("às 6h", "às 7h", "às 8h", "de madrugada", "às 5h30", "logo cedo"))
    accao = rnd.choice((f"fechar a estrada do {bairro}", f"parar {cidade} inteira", "bloquear a entrada do mercado",
                        "não deixar nenhum carro passar", "queimar pneus na avenida", "fechar as lojas à força",
                        f"cercar a administração do {bairro}", "parar os candongueiros que forem trabalhar"))
    ameaca = rnd.choice(("quem abrir a loja vai ver", "quem não aparecer é traidor", "quem for trabalhar vai arrepender-se",
                         "não queremos conversa, é para partir tudo se for preciso", "ninguém sai de casa sem a nossa ordem",
                         "quem furar a paragem leva"))
    a = _fmt(rnd.choice(TEMAS[tema]["assunto"]), cidade, bairro)
    motivo = rnd.choice(("", "", f" por causa d{'a' if a.startswith('a ') else 'o'}{'s' if a.split(' ')[0] in ('os', 'as') else ''} {a.split(' ', 1)[1]}"))
    formas = [
        lambda: f"Vamos todos {dia} {hora} {accao}{motivo}. {_maiuscula(ameaca)}.",
        lambda: f"Malta de {cidade}: {dia} {hora} é para {accao}{motivo}. {_maiuscula(ameaca)}!",
        lambda: f"Chega de conversa{motivo}. {_maiuscula(dia)} {hora}, todos no {bairro} para {accao}. {_maiuscula(ameaca)}.",
        lambda: f"Passem a palavra: {dia} {accao}. {_maiuscula(ameaca)}. Tragam todos os vizinhos.",
        lambda: f"Já falámos com os outros bairros: {dia} {hora} vamos {accao}. {_maiuscula(ameaca)}.",
    ]
    return _maiuscula(rnd.choice(formas)())


def _desinformacao(rnd, tema, cidade, bairro) -> str:
    return _desinformacao_base(rnd, tema, cidade, bairro)


COMPOR = {"Normal": _normal, "Desinformacao": _desinformacao, "Odio": _odio, "Mobilizacao": _mobilizacao}


def _artigo(rnd, tema, cidade, bairro, titulo) -> str:
    """Título e primeira frase de uma notícia fictícia (como na recolha de páginas web)."""
    f = _fmt(rnd.choice(TEMAS[tema]["factos"]).lstrip("+"), cidade, bairro)
    return (f"{titulo}. Moradores de {cidade} relatam que {f}. A administração local diz que está a acompanhar "
            f"a situação e promete novidades nas próximas semanas.")


# --------------------------------------------------------------------------- geração
def gerar(hoje: date, semanas: int = 16, semente: int = 7) -> list[tuple[dict, str, str]]:
    """Lista de (registo bruto, categoria pretendida, plataforma), reprodutível pela semente."""
    rnd = random.Random(semente)
    cidades = list(LUGARES)
    pesos = [LUGARES[c][0] for c in cidades]
    temas = list(TEMAS)
    plats = list(PLATAFORMAS)
    pesos_plat = [PLATAFORMAS[p][1] for p in plats]
    autores = {p: [f"@{nome}{i}" for i in range(1, 160) for nome in ("kianda", "mwangole", "kamba", "zungueira", "kota", "ngueve")]
               for p in plats}
    out: list[tuple[dict, str, str]] = []
    n = 0

    def conversa(semana: int, cidade: str, tema: str, plataforma: str, n_pubs: int, cat_ep: str | None, intens: float):
        nonlocal n
        cidade_, bairro = _lugar(rnd, cidade)
        recente = semanas - semana
        inicio = hoje - timedelta(days=(recente - 1) * 7 + 6)
        dia0 = inicio + timedelta(days=rnd.randint(0, 6))
        canal = rnd.choice(PLATAFORMAS[plataforma][2]).replace("{cidade}", cidade_)
        titulo = _fmt(rnd.choice(TEMAS[tema]["titulos"]), cidade_, bairro)
        contexto = f"{canal} · {titulo}"
        if plataforma == "Portal de notícias (fictício)":
            n += 1
            out.append(({"id": f"demo-{n:05d}", "authorDisplayName": canal, "textDisplay": _artigo(rnd, tema, cidade_, bairro, titulo),
                         "publishedAt": dia0.isoformat(), "contexto": canal}, "Normal", plataforma))
            return
        for _ in range(n_pubs):
            if cat_ep and rnd.random() < intens:
                cat = cat_ep
            else:
                r = rnd.random()
                cat = "Normal" if r < 0.86 else rnd.choice(("Desinformacao", "Odio", "Mobilizacao"))
            # nem todas as publicações repetem o lugar: muitas só se percebem pelo título da conversa
            texto = COMPOR[cat](rnd, tema, cidade_, bairro)
            if rnd.random() < 0.3:
                texto = _sem_lugar(texto, cidade_, bairro)
            if rnd.random() < 0.12:
                texto = f"{rnd.choice(autores[plataforma])} {texto}"  # resposta a outro comentário
            dia = dia0 + timedelta(days=rnd.choice((0, 0, 0, 1, 1, 2)))
            if dia > hoje:
                dia = hoje
            n += 1
            out.append(({"id": f"demo-{n:05d}", "authorDisplayName": rnd.choice(autores[plataforma]), "textDisplay": texto,
                         "publishedAt": f"{dia.isoformat()}T{rnd.randint(6, 23):02d}:{rnd.randint(0, 59):02d}:00Z",
                         "contexto": contexto if rnd.random() < 0.85 else canal}, cat, plataforma))

    for semana in range(semanas):
        recente = semanas - semana
        # conversa de fundo: cresce um pouco ao longo do tempo (mais recolha)
        for _ in range(rnd.randint(9, 13) + semana // 3):
            conversa(semana, rnd.choices(cidades, pesos)[0], rnd.choice(temas), rnd.choices(plats, pesos_plat)[0],
                     rnd.randint(3, 8), None, 0)
        for ep in EPISODIOS:
            fim, ini = ep.semanas[1], ep.semanas[0]
            if fim <= recente <= ini:
                for _ in range(int(ep.peso) + (1 if rnd.random() < ep.peso % 1 else 0)):
                    conversa(semana, ep.cidade, ep.tema, rnd.choice(("YouTube (fictício)", "Facebook (fictício)")),
                             rnd.randint(4, 9), ep.categoria, ep.intensidade)
    return out
