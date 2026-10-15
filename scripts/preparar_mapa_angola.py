"""Prepara o mapa das 18 províncias de Angola para a aplicação web (SVG, sem Internet).

Fonte: geoBoundaries gbOpen, AGO ADM1 (ano 2021, fonte U.S. Census Bureau, domínio público),
https://github.com/wmgeolab/geoBoundaries (releaseData/gbOpen/AGO/ADM1/geoBoundaries-AGO-ADM1_simplified.geojson).
Representa as 18 províncias com os limites de 2011 a 2024 (Luanda já com Icolo e
Bengo e Quiçama), anteriores à divisão político-administrativa que entrou em vigor
em Janeiro de 2025; é a divisão usada pelo sistema.

Uso:
    python scripts/preparar_mapa_angola.py geoBoundaries-AGO-ADM1_simplified.geojson
Escreve sistema_uan/sistema/geo/angola_provincias.json (caminhos SVG já projectados).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

LARGURA = 560.0     # largura útil do desenho, em unidades SVG
MARGEM = 20.0
TOLERANCIA = 0.025  # graus; simplificação Ramer–Douglas–Peucker
DESTINO = Path(__file__).resolve().parents[1] / "sistema_uan" / "sistema" / "geo" / "angola_provincias.json"

CODIGOS = {  # ISO 3166-2 → código curto usado no sistema
    "AO-BGO": "BGO", "AO-BGU": "BGU", "AO-BIE": "BIE", "AO-CAB": "CAB", "AO-CCU": "CCU", "AO-CNO": "CNO",
    "AO-CUS": "CUS", "AO-CNN": "CNN", "AO-HUA": "HUA", "AO-HUI": "HUI", "AO-LUA": "LUA", "AO-LNO": "LNO",
    "AO-LSU": "LSU", "AO-MAL": "MAL", "AO-MOX": "MOX", "AO-NAM": "NAM", "AO-UIG": "UIG", "AO-ZAI": "ZAI",
}


def _rdp(pts: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    if len(pts) < 3:
        return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    dx, dy = x2 - x1, y2 - y1
    norma = math.hypot(dx, dy) or 1e-12
    dmax, idx = 0.0, 0
    for i in range(1, len(pts) - 1):
        x0, y0 = pts[i]
        d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norma
        if d > dmax:
            dmax, idx = d, i
    if dmax <= tol:
        return [pts[0], pts[-1]]
    return _rdp(pts[: idx + 1], tol)[:-1] + _rdp(pts[idx:], tol)


def _area_centroide(anel: list[tuple[float, float]]) -> tuple[float, float, float]:
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(anel, anel[1:] + anel[:1]):
        f = x0 * y1 - x1 * y0
        a += f
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    a *= 0.5
    if abs(a) < 1e-12:
        xs, ys = zip(*anel)
        return 0.0, sum(xs) / len(xs), sum(ys) / len(ys)
    return abs(a), cx / (6 * a), cy / (6 * a)


def main(origem: str) -> None:
    dados = json.loads(Path(origem).read_text(encoding="utf-8"))
    feats = [f for f in dados["features"] if f["properties"].get("shapeGroup", f["properties"].get("adm0_a3")) == "AGO"]
    if len(feats) != 18:
        raise SystemExit(f"Esperavam-se 18 províncias, encontradas {len(feats)}.")
    poligonos = {}
    for f in feats:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        pr = f["properties"]
        iso, nome = pr.get("shapeISO", pr.get("iso_3166_2")), pr.get("shapeName", pr.get("name"))
        poligonos[CODIGOS[iso]] = (nome, [p[0] for p in polys])
    lons = [x for _, ps in poligonos.values() for p in ps for x, _ in p]
    lats = [y for _, ps in poligonos.values() for p in ps for _, y in p]
    lat0 = math.radians((min(lats) + max(lats)) / 2)
    k = LARGURA / ((max(lons) - min(lons)) * math.cos(lat0))
    proj = lambda lon, lat: (MARGEM + (lon - min(lons)) * math.cos(lat0) * k, MARGEM + (max(lats) - lat) * k)
    altura = 2 * MARGEM + (max(lats) - min(lats)) * k
    saida = {"fonte": "geoBoundaries gbOpen AGO ADM1 2021 (U.S. Census Bureau, domínio público); 18 províncias, divisão anterior a 2025",
             "largura": round(LARGURA + 2 * MARGEM), "altura": round(altura), "provincias": {}}
    for cod, (nome, aneis) in sorted(poligonos.items()):
        partes, melhor = [], (0.0, 0.0, 0.0)
        for anel in aneis:
            pts = [tuple(p) for p in anel]
            meio = len(pts) // 2  # anel fechado: simplifica as duas metades em separado
            simpl = _rdp(pts[: meio + 1], TOLERANCIA)[:-1] + _rdp(pts[meio:], TOLERANCIA)
            if len(simpl) < 4:
                continue
            xy = [proj(lon, lat) for lon, lat in simpl[:-1]]
            partes.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in xy) + "Z")
            ac = _area_centroide(xy)
            if ac[0] > melhor[0]:
                melhor = ac
        saida["provincias"][cod] = {"nome": nome, "d": "".join(partes),
                                    "cx": round(melhor[1], 1), "cy": round(melhor[2], 1)}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{DESTINO} ({DESTINO.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
