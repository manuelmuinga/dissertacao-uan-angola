"""Classificadores.

`ClassificadorBERTimbau` carrega o modelo afinado no Colab (pasta no formato
Hugging Face). `ClassificadorDemonstracao` serve apenas para testar o sistema
sem pesos: devolve probabilidades por palavras-chave e está marcado como tal
em todas as classificações que produz. Nunca usar os seus resultados como
resultados de investigação.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from .config import ROTULOS

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Resultado:
    probabilidades: dict[str, float]

    @property
    def categoria(self) -> str:
        return max(self.probabilidades, key=self.probabilidades.get)

    @property
    def confianca(self) -> float:
        return self.probabilidades[self.categoria]


class Classificador(ABC):
    nome: str
    versao: str

    @abstractmethod
    def classificar(self, textos: list[str]) -> list[Resultado]:
        """Classifica uma lista de textos e devolve um resultado por texto."""


class ClassificadorBERTimbau(Classificador):
    def __init__(self, pasta: Path, max_length: int = 128, tamanho_lote: int = 32, dispositivo: str = "auto"):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        pasta = Path(pasta)
        if not (pasta / "config.json").exists():
            raise FileNotFoundError(
                f"{pasta} não contém config.json. Guarde o modelo no Colab com "
                "model.save_pretrained(pasta) e tokenizer.save_pretrained(pasta)."
            )
        self._torch = torch
        self.dispositivo = ("cuda" if torch.cuda.is_available() else "cpu") if dispositivo == "auto" else dispositivo
        self.tokenizer = AutoTokenizer.from_pretrained(pasta)
        self.modelo = AutoModelForSequenceClassification.from_pretrained(pasta).to(self.dispositivo).eval()
        self.max_length = max_length
        self.tamanho_lote = tamanho_lote
        self.rotulos = self._ordem_rotulos()
        self.nome = "BERTimbau"
        self.versao = pasta.name
        log.info("Modelo carregado de %s em %s; rótulos %s", pasta, self.dispositivo, self.rotulos)

    def _ordem_rotulos(self) -> list[str]:
        """Usa id2label do modelo se for coerente com o pipeline; senão a ordem do treino."""
        id2label = getattr(self.modelo.config, "id2label", {}) or {}
        nomes = [id2label.get(i, id2label.get(str(i), "")) for i in range(len(ROTULOS))]
        if sorted(nomes) == sorted(ROTULOS):
            return nomes
        if self.modelo.config.num_labels != len(ROTULOS):
            raise ValueError(f"O modelo tem {self.modelo.config.num_labels} saídas; esperavam-se {len(ROTULOS)}.")
        log.warning("id2label genérico (%s); a assumir a ordem do pipeline %s", nomes, ROTULOS)
        return list(ROTULOS)

    def classificar(self, textos: list[str]) -> list[Resultado]:
        torch = self._torch
        resultados: list[Resultado] = []
        for i in range(0, len(textos), self.tamanho_lote):
            lote = textos[i : i + self.tamanho_lote]
            enc = self.tokenizer(lote, truncation=True, max_length=self.max_length, padding=True, return_tensors="pt")
            enc = {k: v.to(self.dispositivo) for k, v in enc.items()}
            with torch.no_grad():
                probs = torch.softmax(self.modelo(**enc).logits, dim=-1).cpu().tolist()
            resultados.extend(Resultado(dict(zip(self.rotulos, map(float, p)))) for p in probs)
        return resultados


class ClassificadorDemonstracao(Classificador):
    """Classificador de palavras-chave para testes e demonstrações. NÃO é um modelo."""

    nome = "DEMONSTRACAO"
    versao = "palavras-chave-0"
    _PISTAS = {
        "Desinformacao": ("partilha antes que apaguem", "estão a esconder", "fonte interna", "urgente"),
        "Odio": ("não merecem", "são todos", "fora daqui", "raça"),
        "Mobilizacao": ("vamos todos", "amanhã às", "quem não aparecer", "tragam"),
    }

    def classificar(self, textos: list[str]) -> list[Resultado]:
        out = []
        for t in textos:
            t = t.lower()
            pont = {r: 0.1 for r in ROTULOS}
            pont["Normal"] = 1.0
            for rotulo, pistas in self._PISTAS.items():
                pont[rotulo] += sum(1.5 for p in pistas if p in t)
            total = sum(pont.values())
            out.append(Resultado({r: v / total for r, v in pont.items()}))
        return out


def carregar_classificador(caminho_modelo: Path | None, **kw) -> Classificador:
    if caminho_modelo is None:
        log.warning("UAN_MODELO não definido: a usar o classificador de DEMONSTRAÇÃO (não é um modelo).")
        return ClassificadorDemonstracao()
    return ClassificadorBERTimbau(caminho_modelo, **kw)
