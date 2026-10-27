"""McNemar (com correcção de continuidade) de cada variante do BERTimbau contra a referência, no conjunto de VALIDAÇÃO.

Critério da Secção 3.7: uma variante só substitui a referência se se distinguir dela na validação.
"""
import json
import numpy as np
from sklearn.metrics import f1_score
from statsmodels.stats.contingency_tables import mcnemar

R = "/home/claude/res/"
VAR = {"BERTimbau s43": "bert_s43", "BERTimbau s44": "bert_s44", "BERTimbau ensemble": "bertimbau_ensemble",
       "BERTimbau sem vídeo": "bert_sem_video", "BERTimbau w0,5": "bert_w05"}
ref = np.load(R + "bertimbau_ameacas/val_predictions.npz")
y, pr = ref["y_true"], ref["y_pred"]
out = {"referencia_f1_val": float(f1_score(y, pr, average="macro"))}
for nome, pasta in VAR.items():
    d = np.load(R + pasta + "/val_predictions.npz")
    assert (d["y_true"] == y).all()
    a, b = pr == y, d["y_pred"] == y
    t = [[int((a & b).sum()), int((a & ~b).sum())], [int((~a & b).sum()), int((~a & ~b).sum())]]
    r = mcnemar(t, exact=False, correction=True)
    out[nome] = {"f1_val": float(f1_score(y, d["y_pred"], average="macro")), "b01": t[0][1], "c10": t[1][0], "p": float(r.pvalue)}
json.dump(out, open("/home/claude/diss/numeros_validacao.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
