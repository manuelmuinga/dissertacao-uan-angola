"""Painel do analista (Streamlit).

Arranque (Windows, cmd):
    python -m streamlit run painel.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from sistema.base_dados import BaseDados
from sistema.classificador import carregar_classificador
from sistema.config import NOMES_APRESENTACAO, ROTULOS, obter_config
from sistema.servico import VIAS, classificar_pendentes, exportar_revisoes, importar, metricas

st.set_page_config(page_title="Triagem UAN", layout="wide")
cfg = obter_config()


@st.cache_resource
def recursos():
    bd = BaseDados(cfg.caminho_bd)
    kw = dict(max_length=cfg.max_length, tamanho_lote=cfg.tamanho_lote, dispositivo=cfg.dispositivo)
    clf = carregar_classificador(cfg.caminho_modelo, **kw)
    return bd, clf


bd, clf = recursos()

st.sidebar.title("Triagem de ameaças")
analista = st.sidebar.text_input("Analista (identificação para auditoria)", key="analista")
st.sidebar.caption(f"Modelo: **{clf.nome}** ({clf.versao})")
if clf.nome == "DEMONSTRACAO":
    st.sidebar.error("Classificador de DEMONSTRAÇÃO (palavras-chave). Defina UAN_MODELO com a pasta do BERTimbau.")
st.sidebar.info(
    "As classificações servem para **ordenar a revisão**. Nenhuma acção sobre pessoas "
    "pode basear-se apenas no sistema. Convocatórias pacíficas são exercício de direitos "
    "(arts. 40.º e 47.º da Constituição)."
)

aba_fila, aba_panorama, aba_metricas, aba_dados = st.tabs(["Fila de revisão", "Panorama", "Métricas", "Dados e lotes"])

# ------------------------------------------------------------------ fila
with aba_fila:
    c1, c2, c3 = st.columns([2, 1, 1])
    filtro = c1.selectbox("Categoria prevista", ["(todas as ameaças)"] + list(ROTULOS),
                          format_func=lambda x: NOMES_APRESENTACAO.get(x, x))
    n = c2.number_input("Itens", 5, 200, 20, step=5)
    if c3.button("Classificar pendentes"):
        st.success(classificar_pendentes(bd, clf))
    cat = None if filtro == "(todas as ameaças)" else filtro
    itens = bd.fila(int(n), cat)
    if not itens:
        st.info("Não há itens por rever com este filtro.")
    for pos, it in enumerate(itens, start=1):
        probs = json.loads(it["probabilidades"])
        with st.container(border=True):
            a, b = st.columns([3, 1])
            a.markdown(f"**#{pos}** · {it['plataforma']} · prioridade {it['prioridade']:.2f}"
                       + (f" · _{it['contexto']}_" if it["contexto"] else ""))
            a.write(it["texto"])
            b.markdown(f"**{NOMES_APRESENTACAO[it['categoria']]}** ({it['confianca']:.0%})")
            b.caption(" · ".join(f"{NOMES_APRESENTACAO[k][:6]} {v:.0%}" for k, v in probs.items()))
            escolha = b.selectbox("Decisão do analista", ROTULOS, index=ROTULOS.index(it["categoria"]),
                                  key=f"cat_{it['id_pub']}", format_func=NOMES_APRESENTACAO.get)
            nota = a.text_input("Nota (opcional)", key=f"nota_{it['id_pub']}")
            if b.button("Gravar revisão", key=f"g_{it['id_pub']}", disabled=not analista):
                bd.gravar_revisao(it["id_pub"], analista, escolha, pos, nota or None)
                st.rerun()
    if not analista:
        st.warning("Indique o nome do analista na barra lateral para gravar revisões.")

# ------------------------------------------------------------------ panorama
with aba_panorama:
    df = pd.DataFrame([dict(r) for r in bd.consultar(
        """SELECT p.plataforma, substr(COALESCE(p.data_publicacao, p.recolhido_em),1,10) AS dia, k.categoria,
                  r.categoria AS revista
           FROM classificacoes k JOIN publicacoes p ON p.id_pub = k.id_pub
           LEFT JOIN revisoes r ON r.id_pub = k.id_pub""")])
    if df.empty:
        st.info("Ainda não há publicações classificadas.")
    else:
        st.caption("Contagens das **previsões do modelo** (não confirmadas), salvo indicação em contrário. "
                   "Agregados por tema e plataforma; o painel não apresenta perfis de autores.")
        k = st.columns(4)
        for col, r in zip(k, ROTULOS):
            col.metric(NOMES_APRESENTACAO[r], int((df["categoria"] == r).sum()),
                       help=f"Confirmadas pelo analista: {int((df['revista'] == r).sum())}")
        st.subheader("Previsões por dia")
        tab = df.pivot_table(index="dia", columns="categoria", aggfunc="size", fill_value=0)
        tab = tab.reindex(columns=list(ROTULOS), fill_value=0)
        # cores fixas por categoria (Normal a cinzento, para não sugerir alarme)
        st.bar_chart(tab, color=["#b5b4ae", "#2a78d6", "#eb6834", "#6250d6"])
        st.subheader("Previsões por plataforma")
        st.dataframe(pd.crosstab(df["plataforma"], df["categoria"]), use_container_width=True)

# ------------------------------------------------------------------ métricas
with aba_metricas:
    m = metricas(bd)
    st.json(m)
    st.caption(
        "precisão@K: fracção de ameaças confirmadas entre os K itens revistos de maior prioridade. "
        "latencia_s: tempo entre a importação e a classificação de cada publicação (medida interna do sistema, "
        "para a H2; não inclui o tempo entre a publicação original e a recolha)."
    )

# ------------------------------------------------------------------ dados
with aba_dados:
    st.subheader("Importar lote")
    with st.form("importar"):
        f = st.file_uploader("Ficheiro (.csv, .jsonl, .json)", type=["csv", "jsonl", "json"])
        plataforma = st.text_input("Plataforma", "YouTube")
        via = st.selectbox("Via de recolha", VIAS)
        desc = st.text_input("Descrição do lote (ex.: comentários públicos, vídeos X–Y, data)")
        ok = st.form_submit_button("Importar e classificar", disabled=not analista)
    if ok and f is not None:
        if not cfg.segredo_hash:
            st.error("Defina UAN_SEGREDO_HASH antes de importar.")
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(f.name).suffix) as tmp:
                tmp.write(f.getvalue())
            try:
                info = importar(bd, Path(tmp.name), plataforma, via, cfg.segredo_hash, desc, quem=analista)
            finally:
                Path(tmp.name).unlink(missing_ok=True)
            info.update(classificar_pendentes(bd, clf))
            st.success(info)
    st.subheader("Lotes (proveniência)")
    st.dataframe(pd.DataFrame([dict(r) for r in bd.consultar("SELECT * FROM lotes ORDER BY id_lote DESC")]),
                 use_container_width=True)
    st.subheader("Exportar revisões para re-treino")
    if st.button("Gerar CSV", disabled=not analista):
        destino = Path(cfg.caminho_bd).parent / "revisoes_para_treino.csv"
        n = exportar_revisoes(bd, destino)
        st.download_button("Descarregar", destino.read_bytes(), destino.name, "text/csv")
        st.caption(f"{n} revisões. Origem 'revisao_sistema': usar só no treino, nunca no teste.")
