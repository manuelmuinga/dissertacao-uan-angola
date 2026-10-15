"""Anonimização aplicada ANTES de qualquer gravação (Lei n.º 22/11).

Princípios aplicados:
- minimização: guarda-se apenas o texto (mascarado) e metadados não identificativos;
- o autor é substituído por um pseudónimo HMAC-SHA-256 com segredo, que permite
  contar publicações do mesmo pseudónimo sem conhecer a identidade;
- menções, URLs, e-mails e números de telefone no texto são mascarados.

Nomes de pessoas privadas escritos em texto livre não são detectáveis com
fiabilidade por regras; ficam a cargo da revisão humana (ver README).
"""

from __future__ import annotations

import hashlib
import hmac
import re

_PADROES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE), "[URL]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[EMAIL]"),
    # Telefones: +244 9xx xxx xxx, 9xxxxxxxx e variantes com espaços/hífenes.
    (re.compile(r"(?<!\w)(?:\+?244[\s-]?)?9\d{2}[\s-]?\d{3}[\s-]?\d{3}(?!\w)"), "[TELEFONE]"),
    (re.compile(r"(?<!\w)@[\w.]{2,}"), "@[UTILIZADOR]"),
]


def mascarar_texto(texto: str) -> str:
    """Substitui identificadores directos no texto por marcadores."""
    if not texto:
        return ""
    for padrao, marcador in _PADROES:
        texto = padrao.sub(marcador, texto)
    return re.sub(r"\s+", " ", texto).strip()


def pseudonimo_autor(autor: str | None, segredo: str) -> str | None:
    """Pseudónimo irreversível do autor (HMAC-SHA-256, 16 hex)."""
    if not autor:
        return None
    if not segredo:
        raise ValueError(
            "Defina UAN_SEGREDO_HASH: sem segredo, o hash de um nome de utilizador "
            "pode ser revertido por dicionário."
        )
    digest = hmac.new(segredo.encode("utf-8"), autor.strip().lower().encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()[:16]


def id_publicacao(plataforma: str, id_externo: str | None, texto: str) -> str:
    """Identificador estável da publicação, usado para evitar duplicados."""
    base = f"{plataforma}|{id_externo}" if id_externo else f"{plataforma}|{texto}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]
