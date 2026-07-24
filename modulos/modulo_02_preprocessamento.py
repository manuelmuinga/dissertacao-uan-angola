"""
Módulo 2 — Pré-processamento PLN + Anonimização SHA-256
Dissertação UAN — Manuel Muinga 2026 | SO: Windows 11
"""
import re, hashlib
import spacy

nlp = spacy.load("pt_core_news_lg")

NORMALIZACOES_ANGOLA = {
    "ki bué":"muito","ki bue":"muito","bué":"muito","bue":"muito",
    "tó fix":"tudo bem","to fix":"tudo bem","ganda":"grande",
    "kandengue":"crianca","kota":"pessoa","zungu":"rumor",
    "manga":"muito","leke":"pequeno","duzar":"dormir","muamba":"mercadoria",
}
STOPWORDS_ANGOLA = {"ne","né","ta","tá","la","lá","ki","ke","kk","kkk"}

def anonimizar_sha256(s):
    """Anonimiza identificador por SHA-256 (Lei n.º 22/11 Angola)."""
    return hashlib.sha256(str(s).encode("utf-8")).hexdigest()[:16]

def limpar_texto(t):
    if not t: return ""
    t = re.sub(r"http\S+|www\.\S+", "", t)
    t = re.sub(r"@[\w]+", "", t)
    t = re.sub(r"#[\w]+", "", t)
    t = re.sub(r"[^\w\s\u00C0-\u024F]", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()

def normalizar_angola(t):
    for k, v in NORMALIZACOES_ANGOLA.items():
        t = t.replace(k, v)
    return t

def tokenizar_lematizar(t):
    doc = nlp(t)
    return " ".join(
        tk.lemma_.lower() for tk in doc
        if not tk.is_stop and not tk.is_punct
        and len(tk.text) > 2
        and tk.lemma_.lower() not in STOPWORDS_ANGOLA
    )

def preprocessar(texto, id_utilizador=None):
    """Pipeline completo: limpeza → normalização angolana → lematização spaCy."""
    t1 = limpar_texto(texto)
    t2 = normalizar_angola(t1)
    t3 = tokenizar_lematizar(t2)
    return {
        "texto_original":    texto,
        "texto_processado":  t3,
        "num_tokens":        len(t3.split()),
        "id_anonimizado":    anonimizar_sha256(id_utilizador) if id_utilizador else None,
    }
