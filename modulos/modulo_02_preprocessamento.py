"""
=============================================================================
MÓDULO 2 — Pré-processamento e Anonimização
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026

Sistema Operativo: Windows 10/11 (64-bit)
Notas Windows:
  - Instalar spaCy: pip install spacy
  - Descarregar modelo: python -m spacy download pt_core_news_lg
  - Encoding: todos os ficheiros guardados em UTF-8
=============================================================================
"""

import re
import hashlib
import logging
import pymongo
import pandas as pd
import os
from pathlib import Path
from datetime import datetime, timezone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

# Logging com encoding UTF-8 (necessário no Windows para caracteres angolanos)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "preprocessamento.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

# Importar spaCy (verificar instalação no Windows)
try:
    import spacy
    nlp = spacy.load("pt_core_news_lg")
    logger.info("spaCy carregado: pt_core_news_lg")
except OSError:
    logger.error("Modelo spaCy nao encontrado.")
    logger.error("Execute: python -m spacy download pt_core_news_lg")
    raise

# ─── Stopwords e normalizações angolanas ──────────────────────────────────────
STOPWORDS_ANGOLA = {
    "ne", "ta", "la", "pra", "pro", "dum", "duma",
    "ki", "ke", "kk", "kkk", "haha", "lol", "omg",
}

NORMALIZACOES = {
    "ki bue":    "muito",
    "to fix":    "tudo bem",
    "pesado":    "grave",
    "ganda":     "grande",
    "bue":       "muito",
    "manga":     "muito",
    "leke":      "pequeno",
    "kandengue": "crianca",
}


def anonimizar_sha256(identificador: str) -> str:
    """
    Anonimiza identificador por hash SHA-256.
    Cumpre a Lei n.o 22/11 de Protecao de Dados Pessoais de Angola.
    """
    return hashlib.sha256(str(identificador).encode("utf-8")).hexdigest()[:16]


def limpar_texto(texto: str) -> str:
    """Remove URLs, mencoes, hashtags, emojis e normaliza espacos."""
    texto = re.sub(r"http\S+|www\.\S+", "", texto)
    texto = re.sub(r"@[\w]+", "", texto)
    texto = re.sub(r"#[\w]+", "", texto)
    # Remover emojis e caracteres nao-latinos (manter letras angolanas)
    texto = re.sub(r"[^\w\sÀ-ɏ]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def normalizar_angola(texto: str) -> str:
    """Aplica normalizacoes do portugues angolano."""
    texto = texto.lower()
    for expressao, normalizado in NORMALIZACOES.items():
        texto = texto.replace(expressao, normalizado)
    return texto


def tokenizar_lematizar(texto: str) -> str:
    """Tokeniza e lematiza com spaCy, removendo stopwords."""
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
    """Pipeline completo de pre-processamento para uma publicacao."""
    texto_limpo   = limpar_texto(texto)
    texto_angola  = normalizar_angola(texto_limpo)
    texto_final   = tokenizar_lematizar(texto_angola)
    id_anonimo    = anonimizar_sha256(id_utilizador) if id_utilizador else None

    return {
        "texto_original":   texto,
        "texto_processado": texto_final,
        "id_anonimizado":   id_anonimo,
        "num_tokens":       len(texto_final.split()),
        "preprocessado":    True,
    }


def remover_duplicatas(textos: list, limiar: float = 0.95) -> list:
    """Remove textos quasi-duplicados com similaridade cosseno > limiar."""
    if len(textos) < 2:
        return textos
    vectorizer   = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(textos)
    unicos = [0]
    for i in range(1, len(textos)):
        sim = cosine_similarity(tfidf_matrix[i], tfidf_matrix[unicos])
        if sim.max() < limiar:
            unicos.append(i)
    logger.info(f"Duplicatas removidas: {len(textos) - len(unicos)} ({len(unicos)} unicos)")
    return [textos[i] for i in unicos]


def processar_corpus_mongodb() -> pd.DataFrame:
    """Processa todas as publicacoes nao processadas no MongoDB."""
    client  = pymongo.MongoClient(MONGODB_URI)
    db      = client["dissertacao_angola"]
    brutas  = db["publicacoes_brutas"]
    proc    = db["publicacoes_processadas"]

    publicacoes = list(brutas.find({"preprocessado": {"$ne": True}}))
    logger.info(f"A processar {len(publicacoes)} publicacoes...")

    resultados = []
    for pub in publicacoes:
        resultado = preprocessar(pub.get("texto", ""), pub.get("id_externo"))
        resultado.update({
            "id_externo":   pub["id_externo"],
            "plataforma":   pub.get("plataforma"),
            "data":         pub.get("data"),
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

    logger.info(f"Processamento concluido: {len(resultados)} publicacoes.")
    return pd.DataFrame(resultados)


if __name__ == "__main__":
    # Teste rapido no Windows
    exemplo = "Manifestacao marcada para amanha em Luanda! Partilha este video!"
    resultado = preprocessar(exemplo, "user_12345")
    print(f"Original:   {resultado['texto_original']}")
    print(f"Processado: {resultado['texto_processado']}")
    print(f"ID anonimo: {resultado['id_anonimizado']}")
    print(f"Tokens:     {resultado['num_tokens']}")
