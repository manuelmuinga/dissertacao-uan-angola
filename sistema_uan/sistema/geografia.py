"""Localização das publicações por província (18 províncias, divisão anterior a 2025).

O sistema não conhece a localização de quem escreve: os comentários e as páginas
públicas não a trazem. O que se detecta é o LUGAR MENCIONADO no texto ou no
contexto (por exemplo, o título do vídeo), comparando-o com uma lista de
topónimos: nomes das províncias, capitais e municípios mais citados.

Regras:
- só ao nível da província; nada abaixo disso é guardado;
- os nomes com outro significado comum em português (Belas, Cela, Marimba...) ficam
  de fora para evitar falsos positivos;
- "Kwanza"/"Cuanza" sozinho é a moeda ou o rio; só conta com "Norte" ou "Sul";
- "Lunda" sozinho é ambíguo; só conta com "Norte" ou "Sul";
- os topónimos mais longos são procurados primeiro e retirados do texto, para que
  "Icolo e Bengo" (Luanda) não conte também como Bengo e "Cuito Cuanavale"
  (Cuando Cubango) não conte como Cuito (Bié).
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

PROVINCIAS: dict[str, str] = {
    "BGO": "Bengo", "BGU": "Benguela", "BIE": "Bié", "CAB": "Cabinda", "CCU": "Cuando Cubango",
    "CNO": "Cuanza Norte", "CUS": "Cuanza Sul", "CNN": "Cunene", "HUA": "Huambo", "HUI": "Huíla",
    "LUA": "Luanda", "LNO": "Lunda Norte", "LSU": "Lunda Sul", "MAL": "Malanje", "MOX": "Moxico",
    "NAM": "Namibe", "UIG": "Uíge", "ZAI": "Zaire",
}

# Topónimos já normalizados (minúsculas, sem acentos, hífenes e apóstrofos como espaço).
TOPONIMOS: dict[str, tuple[str, ...]] = {
    "BGO": ("bengo", "caxito", "dande", "ambriz", "nambuangongo", "dembos", "pango aluquem", "bula atumba"),
    "BGU": ("benguela", "lobito", "catumbela", "baia farta", "cubal", "ganda", "balombo", "bocoio", "chongoroi",
            "caimbambo"),
    "BIE": ("bie", "kuito", "cuito", "andulo", "camacupa", "chinguar", "catabola", "chitembo", "nharea", "cunhinga"),
    "CAB": ("cabinda", "buco zau", "cacongo", "landana"),
    "CCU": ("cuando cubango", "kuando kubango", "menongue", "cuito cuanavale", "mavinga", "calai", "dirico",
            "rivungo", "cuchi", "cuangar", "nancova"),
    "CNO": ("cuanza norte", "kwanza norte", "kuanza norte", "ndalatando", "n dalatando", "cazengo", "golungo alto",
            "cambambe", "dondo", "lucala", "samba caju", "ambaca", "banga", "quiculungo"),
    "CUS": ("cuanza sul", "kwanza sul", "kuanza sul", "sumbe", "porto amboim", "gabela", "waku kungo", "wako kungo",
            "quibala", "libolo", "calulo", "ebo", "mussende", "cassongue", "quilenda"),
    "CNN": ("cunene", "kunene", "ondjiva", "onjiva", "cahama", "curoca", "ombadja", "xangongo", "namacunde",
            "cuvelai"),
    "HUA": ("huambo", "caala", "bailundo", "londuimbali", "longonjo", "ekunha", "mungo", "catchiungo",
            "tchicala tcholoanga", "tchindjenje", "ucuma"),
    "HUI": ("huila", "lubango", "matala", "chibia", "quipungo", "caluquembe", "caconda", "chipindo", "humpata",
            "cacula", "gambos", "kuvango", "quilengues", "chicomba", "tundavala"),
    "LUA": ("luanda", "cacuaco", "cazenga", "viana", "talatona", "kilamba", "kilamba kiaxi", "sambizanga",
            "maianga", "ingombota", "ingombotas", "icolo e bengo", "quicama", "kissama", "camama", "zango", "cassequel",
            "hoji ya henda", "mutamba", "ilha de luanda"),
    "LNO": ("lunda norte", "dundo", "chitato", "lucapa", "cambulo", "caungula", "xa muteba", "capenda camulemba",
            "cuilo", "lubalo", "cuango"),
    "LSU": ("lunda sul", "saurimo", "cacolo", "muconda"),
    "MAL": ("malanje", "malange", "cacuso", "calandula", "kalandula", "cangandala", "massango", "quela",
            "cunda dia baze", "luquembo", "mucari", "quirima", "caombo", "kiwaba nzoji", "pungo andongo"),
    "MOX": ("moxico", "luena", "luau", "cazombo", "camanongue", "luacano", "lumbala nguimbo", "alto zambeze",
            "cameia", "luchazes", "leua"),
    "NAM": ("namibe", "mocamedes", "tombwa", "tombua", "bibala", "camucuio", "virei"),
    "UIG": ("uige", "negage", "maquela do zombo", "sanza pombo", "quimbele", "quitexe", "mucaba", "damba",
            "alto cauale", "ambuila", "buengas", "milunga", "puri"),
    "ZAI": ("zaire", "mbanza kongo", "mbanza congo", "soyo", "nzeto", "n zeto", "noqui", "tomboco", "cuimba"),
}

SEM_LOCAL = "SEM"


def normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = re.sub(r"[\-'’`´_/]", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def _padroes() -> list[tuple[re.Pattern, str]]:
    pares = [(nome, cod) for cod, nomes in TOPONIMOS.items() for nome in nomes]
    pares.sort(key=lambda p: -len(p[0]))  # mais longos primeiro
    return [(re.compile(rf"(?<![a-z0-9]){re.escape(n)}(?![a-z0-9])"), cod) for n, cod in pares]


def detectar_provincias(*textos: str | None) -> list[str]:
    """Códigos das províncias mencionadas (ordenados), ou lista vazia."""
    t = " " + " ".join(normalizar(x) for x in textos if x) + " "
    encontradas: set[str] = set()
    for padrao, cod in _padroes():
        if padrao.search(t):
            encontradas.add(cod)
            t = padrao.sub(" ", t)
    return sorted(encontradas)


@lru_cache(maxsize=1)
def mapa() -> dict:
    """Contornos das 18 províncias já projectados para SVG (ver scripts/preparar_mapa_angola.py)."""
    return json.loads((Path(__file__).resolve().parent / "geo" / "angola_provincias.json").read_text(encoding="utf-8"))
