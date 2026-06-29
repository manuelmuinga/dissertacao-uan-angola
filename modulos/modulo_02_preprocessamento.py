"""
=============================================================================
MÓDULO 2 — Pré-processamento e Anonimização
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
=============================================================================
Descrição:
    Módulo de limpeza textual, normalização, tokenização, lematização e
    anonimização SHA-256 dos identificadores, em conformidade com a
    Lei n.º 22/11 de Proteção de Dados Pessoais de Angola.
=============================================================================
"""

import re
import hashlib
import unicodedata
import spacy
import pymongo
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from loguru import logger
from dotenv import load_dotenv
import os

load_dotenv()
nlp = spacy.load("pt_core_news_lg")

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# ─── Stopwords angolanas adicionais ──────────────────────────────────────────
STOPWORDS_ANGOLA = {
    "né", "tá", "lá", "né", "pra", "pro", "dum", "duma",
    "ki", "ke", "kk", "kkk", "haha", "lol", "omg",
    "angola", "luanda", "angolano", "angolana",  # demasiado genérico
}

# ─── Normalizações do português angolano ─────────────────────────────────────
NORMALIZACOES = {
    "ki bué":  "muito",
    "tó fix":  "tudo bem",
    "pesado":  "grave",
    "ganda":   "grande",
    "bué":     "muito",
    "manga":   "muito",
    "leke":    "pequeno",
    "duzar":   "dormir",
    "kandengue": "criança",
}


def anonimizar_sha256(identificador: str) -> str:
    """
    Anonimiza um identificador (user ID, username) por hash SHA-256.
    Cumpre a Lei n.º 22/11 de Proteção de Dados Pessoais de Angola.
    """
    return hashlib.sha256(str(identificador).encode("utf-8")).hexdigest()[:16]


def limpar_texto(texto: str) -> str:
    """
    Remove URLs, menções, hashtags, emojis e normaliza espaços.
    """
    texto = re.sub(r"http\S+|www\.\S+", "", texto)        # URLs
    texto = re.sub(r"@[\w]+", "", texto)                    # Menções
    texto = re.sub(r"#[\w]+", "", texto)                    # Hashtags
    texto = re.sub(r"[^\w\s\u00C0-\u024F]", " ", texto) # Emojis/símbolos
    texto = re.sub(r"\s+", " ", texto).strip()              # Espaços múltiplos
    return texto


def normalizar_angola(texto: str) -> str:
    """
    Aplica normalizações específicas do português angolano (calão, gíria).
    """
    texto = texto.lower()
    for expressao, normalizado in NORMALIZACOES.items():
        texto = texto.replace(expressao, normalizado)
    return texto


def tokenizar_lematizar(texto: str) -> str:
    """
    Tokeniza e lematiza o texto usando spaCy (pt_core_news_lg),
    removendo stopwords e pontuação.
    """
    doc = nlp(texto)
    tokens = [
        token.lemma_.lower()
        for token in doc
        if not token.is_stop
        and not token.is_punct
        and len(token.text) > 2
        and token.lemma_.lower() not in STOPWORDS_ANGOLA
    ]
    return " ".join(tokens)


def preprocessar(texto: str, id_utilizador: str = None) -> dict:
    """
    Pipeline completo de pré-processamento para uma publicação.
    
    Args:
        texto: Texto bruto da publicação.
        id_utilizador: Identificador do utilizador (anonimizado).
    
    Returns:
        Dicionário com texto processado e metadados.
    """
    texto_limpo    = limpar_texto(texto)
    texto_angola   = normalizar_angola(texto_limpo)
    texto_final    = tokenizar_lematizar(texto_angola)
    id_anonimo     = anonimizar_sha256(id_utilizador) if id_utilizador else None
    
    return {
        "texto_original":    texto,
        "texto_processado":  texto_final,
        "id_anonimizado":    id_anonimo,
        "num_tokens":        len(texto_final.split()),
        "preprocessado":     True,
    }


def remover_duplicatas(textos: list, limiar: float = 0.95) -> list:
    """
    Remove textos quasi-duplicados com similaridade cosseno > limiar.
    
    Args:
        textos: Lista de textos a filtrar.
        limiar: Limiar de similaridade (0–1).
    
    Returns:
        Lista de textos sem duplicatas.
    """
    if len(textos) < 2:
        return textos
    
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(textos)
    unicos = [0]
    
    for i in range(1, len(textos)):
        sim = cosine_similarity(tfidf_matrix[i], tfidf_matrix[unicos])
        if sim.max() < limiar:
            unicos.append(i)
    
    logger.info(f"Duplicatas removidas: {len(textos) - len(unicos)} ({len(unicos)} únicos)")
    return [textos[i] for i in unicos]


def processar_corpus_mongodb() -> pd.DataFrame:
    """
    Processa todas as publicações não processadas no MongoDB.
    
    Returns:
        DataFrame com publicações processadas.
    """
    client  = pymongo.MongoClient(MONGODB_URI)
    db      = client["dissertacao_angola"]
    brutas  = db["publicacoes_brutas"]
    proc    = db["publicacoes_processadas"]
    
    publicacoes = list(brutas.find({"preprocessado": {"$ne": True}}))
    logger.info(f"A processar {len(publicacoes)} publicações...")
    
    resultados = []
    for pub in publicacoes:
        resultado = preprocessar(pub.get("texto", ""), pub.get("id_externo"))
        resultado.update({
            "id_externo":  pub["id_externo"],
            "plataforma":  pub.get("plataforma"),
            "data":        pub.get("data"),
            "recolhido_em": pub.get("recolhido_em"),
            "classificado": False,
        })
        proc.update_one(
            {"id_externo": pub["id_externo"]},
            {"$set": resultado},
            upsert=True
        )
        brutas.update_one({"_id": pub["_id"]}, {"$set": {"preprocessado": True}})
        resultados.append(resultado)
    
    logger.info(f"Processamento concluído: {len(resultados)} publicações.")
    return pd.DataFrame(resultados)


if __name__ == "__main__":
    df = processar_corpus_mongodb()
    print(df[["id_externo", "plataforma", "num_tokens"]].head(10))
