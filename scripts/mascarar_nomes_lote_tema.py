"""Revisão de nomes de pessoas no lote temático de vídeos (origem = enriquecido_video_tema).

Regra (Secção 3.2 da dissertação): figuras políticas e históricas mantêm o nome;
comentadores de programas, activistas e outras pessoas passam a descritores.
Só altera os itens do lote temático; os restantes ficam iguais.

Uso (Windows, cmd, na pasta uan_pipeline):
python ..\\scripts\\mascarar_nomes_lote_tema.py data\\corpus_ground_truth_com_texto_v13.csv data\\corpus_ground_truth_com_texto_v13_nomes_revistos.csv

Gera também <saida>_relatorio.csv com o número de substituições por nome.
"""
import re
import sys
import collections
import pandas as pd

# (padrão, substituição, tipo). A ordem importa: nomes completos antes dos apelidos.
SUBSTITUICOES = [
    (r"\bOsvaldo\s+(?:Kaholo|Caholo|Caolo|Khaolo)\b", "[activista]", "activista"),
    (r"\bOsvaldo\b", "[activista]", "activista"),
    (r"\bM[áa]rio\s+Arag[ãa]o\b", "[comentador do programa]", "comentador"),
    (r"\bArag[ãa]o\b", "[comentador do programa]", "comentador"),
    (r"\bM\.A\b", "[comentador do programa]", "comentador"),
    (r"\bJoaquim\s+Jaime\b|\bO\.\s*Jaime\b", "[comentador do programa]", "comentador"),
    (r"\b(?:Dr\.?\s+|DR\s+)?Caba[çc]a\b", "[comentador do programa]", "comentador"),
    (r"\b(?:Dr\.?\s+)?Aniceto\b", "[comentador do programa]", "comentador"),
    (r"\bGama\b", "[comentador do programa]", "comentador"),
    (r"\bmoscalifa\b", "[comentador do programa]", "comentador"),
    (r"\bpakissi\b", "[comentador do programa]", "comentador"),
    (r"\bFrancisco\s+Teixeira\b", "[pessoa referida]", "outra pessoa"),
]
# Mantidos por serem figuras políticas ou históricas: Norberto Garcia, Savimbi,
# Rosa Coutinho, Venâncio, deputado Sapinhala (também escrito Sapinala).
MANTIDOS = ["Norberto Garcia", "Noberto", "Savimbi", "Rosa Coutinho", "Venâncio", "sapinhala"]


def main(entrada, saida):
    d = pd.read_csv(entrada)
    alvo = d["origem"] == "enriquecido_video_tema"
    contagem = collections.Counter()
    itens_alterados = 0

    def rever(texto):
        nonlocal itens_alterados
        novo = texto
        for padrao, sub, tipo in SUBSTITUICOES:
            novo, n = re.subn(padrao, sub, novo, flags=re.IGNORECASE)
            if n:
                contagem[(padrao, sub, tipo)] += n
        if novo != texto:
            itens_alterados += 1
        return novo

    d.loc[alvo, "texto"] = d.loc[alvo, "texto"].map(rever)
    d.to_csv(saida, index=False)

    rel = pd.DataFrame(
        [{"padrao": p, "substituicao": s, "tipo": t, "ocorrencias": n} for (p, s, t), n in contagem.items()]
    )
    rel.to_csv(saida.replace(".csv", "_relatorio.csv"), index=False)
    mantidos = {m: int(d.loc[alvo, "texto"].str.contains(m, case=False).sum()) for m in MANTIDOS}
    print(f"itens do lote temático: {int(alvo.sum())}")
    print(f"itens alterados: {itens_alterados}")
    print(f"substituições: {sum(contagem.values())}")
    print(f"nomes mantidos (itens): {mantidos}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
