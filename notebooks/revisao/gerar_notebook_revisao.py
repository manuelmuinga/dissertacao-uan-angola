"""Gera revisao_sementes_e_piloto.ipynb: sementes adicionais dos modelos de referência e análises do subconjunto angolano."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
py = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))

md("""
# Revisão da dissertação: sementes adicionais e análises do piloto angolano

Este notebook responde a duas críticas da leitura independente da dissertação.

**Parte A — sementes adicionais (ponto 10).** Os modelos de referência (Bi-LSTM, Floresta Aleatória e SVM) foram treinados com uma única semente. Aqui treinam-se também com as sementes 43 e 44, como já se fez com o BERTimbau, para ver se a conclusão «o Bi-LSTM não se distingue da Floresta Aleatória» se mantém.

**Parte B — análises do subconjunto angolano (ponto 2).** Com as previsões guardadas do BERTimbau de referência, calcula-se, só nas 355 publicações angolanas do teste:
1. o F1-macro de três classes refeito sem a Mobilização Hostil, com intervalo de confiança;
2. o desempenho por origem dos itens (comentários do YouTube sorteados, títulos de notícias e publicações recolhidas à mão);
3. o desempenho só nos comentários sorteados, sem os itens de recolha manual;
4. a precisão e a sensibilidade por categoria no piloto;
5. a calibração e a curva de esforço no piloto.

Nada aqui altera o modelo usado no sistema. Os resultados ficam em `MyDrive/dissertacao_uan/revisao/`.

**Antes de começar:** `Ambiente de execução → Alterar tipo de ambiente de execução → T4 GPU`. Demora cerca de 30 a 45 minutos (o Bi-LSTM usa a GPU; a Floresta Aleatória e o SVM correm no processador). Mantenha o separador aberto.
""")

md("## 0. GPU e Google Drive")
py("""
import subprocess, torch
assert torch.cuda.is_available(), "Sem GPU. Escolha 'T4 GPU' em Ambiente de execução → Alterar tipo de ambiente de execução."
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv"], capture_output=True, text=True).stdout)

from google.colab import drive
drive.mount("/content/drive")
import os
PASTA_DRIVE = "/content/drive/MyDrive/dissertacao_uan"
SAIDA = f"{PASTA_DRIVE}/revisao"
os.makedirs(SAIDA, exist_ok=True)
print("Resultados em:", SAIDA)
""")

md("""
## 1. Código, dados e previsões de referência (`uan_pipeline_revisao.zip`)

Carregue o ficheiro `uan_pipeline_revisao.zip` que acompanha este notebook (não o `uan_pipeline.zip` antigo). Fica guardada uma cópia no Drive para a próxima vez. O zip traz o código, o corpus angolano, a origem de cada item do piloto (`data/tipo_item_piloto.csv`) e as previsões de teste da corrida de referência (`resultados_referencia/`).
""")
py("""
import shutil, zipfile
ZIP_DRIVE = f"{PASTA_DRIVE}/uan_pipeline_revisao.zip"
os.chdir("/content")
if os.path.exists(ZIP_DRIVE):
    shutil.copy(ZIP_DRIVE, "uan_pipeline_revisao.zip"); print("Zip lido do Drive.")
else:
    from google.colab import files
    up = files.upload()                                   # escolha uan_pipeline_revisao.zip
    nome = [f for f in up if f.endswith(".zip")][0]
    if nome != "uan_pipeline_revisao.zip":
        os.replace(nome, "uan_pipeline_revisao.zip")
    shutil.copy("uan_pipeline_revisao.zip", ZIP_DRIVE); print("Cópia guardada no Drive.")
shutil.rmtree("/content/uan_pipeline", ignore_errors=True)
with zipfile.ZipFile("uan_pipeline_revisao.zip") as z:
    z.extractall("/content")
os.chdir("/content/uan_pipeline")
for f in ["data/corpus_ground_truth_com_texto_v13.csv", "data/tipo_item_piloto.csv", "resultados_referencia/bertimbau_ameacas_test.npz"]:
    assert os.path.exists(f), f"Falta {f} no zip."
print("Directório:", os.getcwd())
""")
py("""
!pip install -q -r requirements.txt
""")

md("## 2. Corpus híbrido v13 e divisão (mesmos comandos da corrida de referência)")
py("""
!python src/build_public_corpus.py \\
    --pilot-angolano data/corpus_ground_truth_com_texto_v13.csv \\
    --out data/corpus_hibrido_final.csv \\
    --report data/harmonizacao_relatorio.json
!python src/split_and_balance.py --in data/corpus_hibrido_final.csv \\
    --out-dir data/splits --strat-col categoria_final \\
    --train-only-origem enriquecido_lexico enriquecido_video_tema
""")
py("""
import json, hashlib, numpy as np, pandas as pd
LABELS = ["Normal", "Desinformacao", "Odio", "Mobilizacao"]
L2I = {l: i for i, l in enumerate(LABELS)}
rel = json.load(open("data/harmonizacao_relatorio.json", encoding="utf-8"))
print("Total:", rel["total_apos_dedup"], "| por fonte:", rel["por_fonte"])

test = pd.read_csv("data/splits/test.csv")
ref = np.load("resultados_referencia/bertimbau_ameacas_test.npz")
y_csv = test["categoria_final"].map(L2I).astype(int).values
IGUAL = len(y_csv) == len(ref["y_true"]) and (y_csv == ref["y_true"]).all()
h = hashlib.md5(",".join(map(str, y_csv.tolist())).encode()).hexdigest()
print(f"Teste: n={len(y_csv)}; impressão digital {h}")
print("✅ Teste idêntico ao da corrida de referência." if IGUAL and h == "a827ac39358164b48589291ade21bf33" else
      "⚠️ O teste NÃO coincide com o da referência. Pare aqui e envie esta saída: os resultados não seriam comparáveis.")
assert IGUAL, "Divisão diferente da referência."
""")

md("""
## Parte A — Sementes adicionais dos modelos de referência

Mesmos comandos e valores por omissão da corrida de referência; só muda a semente. A semente 42 é repetida no Bi-LSTM para confirmar que o resultado de referência se reproduz neste ambiente.
""")
py("""
import time
CORRIDAS = [("bilstm", 42), ("bilstm", 43), ("bilstm", 44), ("rf", 43), ("rf", 44), ("svm", 43), ("svm", 44)]
for modelo, s in CORRIDAS:
    out = f"models/{modelo}_s{s}"
    if os.path.exists(f"{out}/test_predictions.npz"):
        print("já existe:", out); continue
    t0 = time.time()
    if modelo == "bilstm":
        !python src/train_bilstm.py --train data/splits/train.csv --val data/splits/val.csv --test data/splits/test.csv --out-dir {out} --seed {s}
    else:
        !python src/train_baseline.py --model {modelo} --train data/splits/train.csv --val data/splits/val.csv --test data/splits/test.csv --out-dir {out} --seed {s}
    print(f"{modelo} s{s}: {time.time()-t0:.0f} s")
    shutil.copytree(out, f"{SAIDA}/{modelo}_s{s}", dirs_exist_ok=True)
""")
py("""
from sklearn.metrics import f1_score
from statsmodels.stats.contingency_tables import mcnemar

def f1m(y, p): return f1_score(y, p, average="macro", labels=[0, 1, 2, 3], zero_division=0)
def mcn(y, a, b):
    ca, cb = a == y, b == y
    t = [[int((ca & cb).sum()), int((ca & ~cb).sum())], [int((~ca & cb).sum()), int((~ca & ~cb).sum())]]
    return mcnemar(t, exact=False, correction=True).pvalue

REF = {"bilstm": "resultados_referencia/bilstm_ameacas_test.npz", "rf": "resultados_referencia/baseline_rf_test.npz",
       "svm": "resultados_referencia/baseline_svm_test.npz"}
y = ref["y_true"]
prev = {m: {42: np.load(f)["y_pred"]} for m, f in REF.items()}
for modelo, s in CORRIDAS:
    if s != 42:
        prev[modelo][s] = np.load(f"models/{modelo}_s{s}/test_predictions.npz")["y_pred"]
rep42 = np.load("models/bilstm_s42/test_predictions.npz")["y_pred"]
print(f"Reprodução do Bi-LSTM s42: F1-macro {f1m(y, rep42):.4f} (referência {f1m(y, prev['bilstm'][42]):.4f}); "
      f"previsões iguais em {(rep42 == prev['bilstm'][42]).mean():.1%} dos itens")

RES_A = {"f1_macro": {}, "media": {}, "dp": {}}
print("\\nF1-macro no teste por semente")
for m in ["bilstm", "rf", "svm"]:
    v = {s: f1m(y, p) for s, p in sorted(prev[m].items())}
    RES_A["f1_macro"][m] = v; RES_A["media"][m] = float(np.mean(list(v.values()))); RES_A["dp"][m] = float(np.std(list(v.values()), ddof=1))
    print(f"  {m:<7}", "  ".join(f"s{s}: {x:.3f}" for s, x in v.items()), f"| média {RES_A['media'][m]:.3f} ± {RES_A['dp'][m]:.3f}")
print(f"  BERTimbau (já publicado): média 0,797 ± 0,011")

print("\\nBi-LSTM vs. Floresta Aleatória, semente a semente")
RES_A["bilstm_vs_rf"] = {}
for s in (42, 43, 44):
    d = f1m(y, prev["bilstm"][s]) - f1m(y, prev["rf"][s]); p = mcn(y, prev["bilstm"][s], prev["rf"][s])
    RES_A["bilstm_vs_rf"][s] = {"df1_pp": 100 * d, "p_mcnemar": p}
    print(f"  s{s}: ΔF1 = {100*d:+.1f} p.p.; McNemar p = {p:.3f}")
print("\\nBERTimbau (s42) vs. cada modelo de referência, em todas as sementes")
RES_A["bert_vs"] = {}
for m in ["bilstm", "rf", "svm"]:
    ds = [100 * (f1m(y, ref["y_pred"]) - f1m(y, p)) for p in prev[m].values()]
    ps = [mcn(y, ref["y_pred"], p) for p in prev[m].values()]
    RES_A["bert_vs"][m] = {"df1_pp_min": min(ds), "df1_pp_max": max(ds), "p_max": max(ps)}
    print(f"  {m:<7} ΔF1 entre {min(ds):.1f} e {max(ds):.1f} p.p.; maior p = {max(ps):.1e}")
""")

md("""
## Parte B — Análises do subconjunto angolano (BERTimbau de referência)

Usa as previsões guardadas da corrida de referência (semente 42), as mesmas do Capítulo 4.
""")
py("""
from sklearn.metrics import precision_recall_fscore_support, cohen_kappa_score
tipos = pd.read_csv("data/tipo_item_piloto.csv")
test["tipo"] = test["texto"].map(dict(zip(tipos["texto"], tipos["tipo"])))
piloto = (test["fonte"] == "Piloto_Angola").values
print("Itens do piloto no teste:", piloto.sum(), "| por origem:", test.loc[piloto, "tipo"].value_counts(dropna=False).to_dict())
assert test.loc[piloto, "tipo"].notna().all(), "Há itens do piloto sem origem identificada."

yp, pp = ref["y_true"], ref["y_pred"]
S = ref["y_score"].astype(float); P = S / S.sum(1, keepdims=True)
rng = np.random.default_rng(0)
def boot(f, idx, n=2000):
    v = [f(rng.choice(idx, len(idx), replace=True)) for _ in range(n)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
RES_B = {}

# 1. F1-macro de três classes sem a Mobilização Hostil (itens de Mobilização excluídos; prever Mobilização conta como erro)
def f1_3(ix): return f1_score(yp[ix], pp[ix], average="macro", labels=[0, 1, 2], zero_division=0)
ip = np.where(piloto & (yp != 3))[0]; iq = np.where(~piloto)[0]
d_boot = [f1_3(rng.choice(iq, len(iq))) - f1_3(rng.choice(ip, len(ip))) for _ in range(2000)]
RES_B["f1_3classes"] = {"piloto": f1_3(ip), "piloto_ic": boot(f1_3, ip), "publico": f1_3(iq), "publico_ic": boot(f1_3, iq),
                        "delta_pp": 100 * (f1_3(iq) - f1_3(ip)), "delta_ic_pp": [100 * float(np.percentile(d_boot, 2.5)), 100 * float(np.percentile(d_boot, 97.5))],
                        "n_piloto_sem_mob": int(len(ip))}
r = RES_B["f1_3classes"]
print(f"\\n1. F1-macro 3 classes: piloto {r['piloto']:.3f} {np.round(r['piloto_ic'],3)} vs público {r['publico']:.3f}; "
      f"Δ = {r['delta_pp']:.1f} p.p. [IC {r['delta_ic_pp'][0]:.1f}; {r['delta_ic_pp'][1]:.1f}]")

# 2. Por origem dos itens do piloto
print("\\n2. Por origem (piloto):")
RES_B["por_origem"] = {}
for t, g in test[piloto].groupby("tipo"):
    ix = g.index.values; labs = sorted(set(yp[ix]))
    RES_B["por_origem"][t] = {"n": int(len(ix)), "f1_macro": float(f1_score(yp[ix], pp[ix], average="macro", labels=labs, zero_division=0)),
                              "exactidao": float((yp[ix] == pp[ix]).mean()), "dist": {LABELS[c]: int((yp[ix] == c).sum()) for c in range(4)}}
    x = RES_B["por_origem"][t]; print(f"  {t:<24} n={x['n']:>3}  F1-macro {x['f1_macro']:.3f}  exactidão {x['exactidao']:.3f}  {x['dist']}")
iy = np.where(piloto & (test["tipo"] == "youtube_aleatorio").values)[0]
def f1r(ix): return f1_score(yp[ix], pp[ix], average="macro", labels=sorted(set(yp[iy])), zero_division=0)

# 3. Só os comentários do YouTube sorteados
RES_B["so_youtube"] = {"n": int(len(iy)), "f1_macro": f1r(iy), "ic": boot(f1r, iy), "kappa": float(cohen_kappa_score(yp[iy], pp[iy]))}
r = RES_B["so_youtube"]; print(f"\\n3. Só comentários sorteados: n={r['n']}, F1-macro {r['f1_macro']:.3f} {np.round(r['ic'],3)}, κ {r['kappa']:.3f}")

# 4. Precisão e sensibilidade por categoria no piloto
ipi = np.where(piloto)[0]
pr, rc, f1, sup = precision_recall_fscore_support(yp[ipi], pp[ipi], labels=[0, 1, 2, 3], zero_division=0)
RES_B["por_categoria_piloto"] = {LABELS[c]: {"precisao": float(pr[c]), "sensibilidade": float(rc[c]), "f1": float(f1[c]), "n": int(sup[c])} for c in range(4)}
print("\\n4. Por categoria no piloto:")
for c in range(4): print(f"  {LABELS[c]:<14} precisão {pr[c]:.3f}  sensibilidade {rc[c]:.3f}  F1 {f1[c]:.3f}  n={sup[c]}")

# 5. Calibração e curva de esforço no piloto
conf = P[ipi].max(1); acc = (P[ipi].argmax(1) == yp[ipi])
bins = np.linspace(0, 1, 16); ece = sum(((conf > a) & (conf <= b)).sum() / len(ipi) * abs(acc[(conf > a) & (conf <= b)].mean() - conf[(conf > a) & (conf <= b)].mean())
                                        for a, b in zip(bins[:-1], bins[1:]) if ((conf > a) & (conf <= b)).sum())
am = (yp[ipi] != 0).astype(int); prio = 1 - P[ipi, 0]; ordem = np.argsort(-prio, kind="stable"); cum = np.cumsum(am[ordem]); tot = am.sum()
esf = {str(a): float((np.argmax(cum >= a * tot) + 1) / len(ipi)) for a in (0.8, 0.9, 0.95)}
prevN = P[ipi].argmax(1) == 0
RES_B["calibracao_piloto"] = {"ece": float(ece), "conf_media": float(conf.mean()), "exactidao": float(acc.mean()),
                              "prevalencia_ameaca": float(am.mean()), "fracao_fila_para": esf,
                              "ameacas_entre_normais": int(am[prevN].sum()), "fracao_ameacas_entre_normais": float(am[prevN].sum() / tot)}
r = RES_B["calibracao_piloto"]
print(f"\\n5. Calibração no piloto: ECE {r['ece']:.3f}; confiança média {r['conf_media']:.3f} vs exactidão {r['exactidao']:.3f}")
print(f"   Ameaças no piloto: {r['prevalencia_ameaca']:.1%}; fila revista para encontrar 80/90/95%: "
      + ", ".join(f"{100*v:.0f}%" for v in esf.values()) + f"; ameaças entre os Normais: {r['ameacas_entre_normais']} ({r['fracao_ameacas_entre_normais']:.1%})")
""")

md("## 3. Guardar e enviar os resultados")
py("""
json.dump({"parte_A": RES_A, "parte_B": RES_B}, open(f"{SAIDA}/resultados_revisao.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
print(open(f"{SAIDA}/resultados_revisao.json", encoding="utf-8").read())
print("\\nGuardado em", f"{SAIDA}/resultados_revisao.json", "— envie este ficheiro (ou cole esta saída) para incorporar na dissertação.")
""")

nb["cells"] = C
nb["metadata"] = {"accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []},
                  "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}}
nbf.write(nb, "/tmp/claude-0/-home-claude/5b17b837-1394-5bd2-9329-77b405cf46e3/scratchpad/nb_revisao/revisao_sementes_e_piloto.ipynb")
print("ok")
