"""Configuração central do sistema.

Os valores vêm de variáveis de ambiente. Para não ter de repetir `set` em cada
sessão do cmd, podem ficar no ficheiro `uan.env` na pasta do sistema (uma
linha `NOME=valor` por variável; ver `uan.env.exemplo`). Uma variável definida
no ambiente prevalece sobre o ficheiro. O `uan.env` não vai para o Git.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Rótulos exactamente como no pipeline de treino (sem acentos).
ROTULOS: tuple[str, ...] = ("Normal", "Desinformacao", "Odio", "Mobilizacao")

# Nomes para apresentação (o armazenamento usa sempre ROTULOS).
NOMES_APRESENTACAO = {
    "Normal": "Normal",
    "Desinformacao": "Desinformação",
    "Odio": "Discurso de Ódio",
    "Mobilizacao": "Mobilização Hostil",
}

PAPEIS: tuple[str, ...] = ("analista", "supervisor")


def carregar_env(caminho: Path | None = None) -> list[str]:
    """Lê `uan.env` e define as variáveis que ainda não existem no ambiente."""
    caminho = Path(caminho or os.getenv("UAN_ENV", RAIZ / "uan.env"))
    definidas = []
    if not caminho.exists():
        return definidas
    for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        nome, valor = (x.strip() for x in linha.split("=", 1))
        valor = valor.strip('"').strip("'")
        if nome and nome not in os.environ:
            os.environ[nome] = valor
            definidas.append(nome)
    return definidas


def _bool(nome: str, omissao: str = "0") -> bool:
    return os.getenv(nome, omissao).strip().lower() in ("1", "true", "sim", "yes")


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
    # Segredo para o pseudónimo dos autores. Sem ele, um hash SHA-256 simples de um
    # nome de utilizador pode ser revertido por dicionário. Defina-o fora do código.
    segredo_hash: str = field(default_factory=lambda: os.getenv("UAN_SEGREDO_HASH", ""))
    # Prazo de conservação dos textos (Lei n.º 22/11: conservação limitada à finalidade).
    dias_conservacao: int = field(default_factory=lambda: int(os.getenv("UAN_DIAS_CONSERVACAO", "180")))
    # Aplicação web
    chave_api: str = field(default_factory=lambda: os.getenv("UAN_CHAVE_API", ""))
    horas_sessao: int = field(default_factory=lambda: int(os.getenv("UAN_HORAS_SESSAO", "8")))
    cookie_seguro: bool = field(default_factory=lambda: _bool("UAN_COOKIE_SEGURO"))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("UAN_MAX_UPLOAD_MB", "20")))


def obter_config() -> Config:
    carregar_env()
    return Config()
