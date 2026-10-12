"""Configuração central do sistema.

Todos os valores podem ser alterados por variáveis de ambiente, para que o
mesmo código corra no portátil do investigador, no Colab ou num servidor.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Rótulos exactamente como no pipeline de treino (sem acentos).
ROTULOS: tuple[str, ...] = ("Normal", "Desinformacao", "Odio", "Mobilizacao")

# Nomes para apresentação no painel (o armazenamento usa sempre ROTULOS).
NOMES_APRESENTACAO = {
    "Normal": "Normal",
    "Desinformacao": "Desinformação",
    "Odio": "Discurso de Ódio",
    "Mobilizacao": "Mobilização Hostil",
}


@dataclass(frozen=True)
class Config:
    caminho_bd: Path = field(
        default_factory=lambda: Path(os.getenv("UAN_BD", RAIZ / "dados" / "sistema.db"))
    )
    # Pasta com o modelo guardado (formato Hugging Face: config.json + pesos + tokenizer).
    caminho_modelo: Path | None = field(
        default_factory=lambda: Path(p) if (p := os.getenv("UAN_MODELO")) else None
    )
    max_length: int = field(default_factory=lambda: int(os.getenv("UAN_MAX_LENGTH", "256")))
    tamanho_lote: int = field(default_factory=lambda: int(os.getenv("UAN_LOTE", "32")))
    dispositivo: str = field(default_factory=lambda: os.getenv("UAN_DISPOSITIVO", "auto"))
    # Segredo para o hash dos autores. Sem ele, um hash SHA-256 simples de um
    # nome de utilizador pode ser revertido por dicionário. Defina-o fora do código.
    segredo_hash: str = field(default_factory=lambda: os.getenv("UAN_SEGREDO_HASH", ""))
    # Prazo de conservação dos textos (Lei n.º 22/11: conservação limitada à finalidade).
    dias_conservacao: int = field(default_factory=lambda: int(os.getenv("UAN_DIAS_CONSERVACAO", "180")))


def obter_config() -> Config:
    return Config()
