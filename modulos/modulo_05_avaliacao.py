"""
Módulo 5 — Avaliação de Modelos (F1, Kappa, AUC-ROC, Matrizes de Confusão)
Dissertação UAN — Manuel Muinga 2026
Gera Figuras 4.1 e 4.2 da dissertação
"""
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    f1_score, cohen_kappa_score, roc_auc_score,
    confusion_matrix, classification_report,
    roc_curve, auc,
)

CATEGORIAS  = ["Normal","Desinformação","Discurso de Ódio","Mobilização Hostil"]
CATS_CURTAS = ["Normal","Desinform.","Ódio","Mobilização"]


def avaliar_modelo(y_real, y_pred, y_proba=None, nome="Modelo"):
    """Calcula todas as métricas da Tabela 4.1 da dissertação."""
    f1    = f1_score(y_real, y_pred, average="weighted", zero_division=0)
    kappa = cohen_kappa_score(y_real, y_pred)
    auc_v = roc_auc_score(y_real, y_proba, multi_class="ovr",
                           average="weighted") if y_proba is not None else None
    prec  = __import__("sklearn.metrics", fromlist=["precision_score"]).precision_score(
        y_real, y_pred, average="weighted", zero_division=0)
    rec   = __import__("sklearn.metrics", fromlist=["recall_score"]).recall_score(
        y_real, y_pred, average="weighted", zero_division=0)
    print(f"
=== {nome} ===")
    print(f"  F1-Score   : {f1:.3f}")
    print(f"  Precisão   : {prec:.3f}")
    print(f"  Recall     : {rec:.3f}")
    print(f"  Kappa (κ)  : {kappa:.3f}")
    if auc_v: print(f"  AUC-ROC    : {auc_v:.3f}")
    return {"nome":nome,"f1":f1,"precisao":prec,"recall":rec,"kappa":kappa,"auc_roc":auc_v}


def plotar_matrizes_confusao(modelos_preds, y_real, caminho="/content/graficos/figura_4_2.png"):
    """Gera Figura 4.2 — Matrizes de Confusão (4×4) de múltiplos modelos."""
    n    = len(modelos_preds)
    fig, axes = plt.subplots(1, n, figsize=(6*n, 5))
    if n == 1: axes = [axes]
    fig.suptitle("Figura 4.2 — Matrizes de Confusão
Corpus Angola OSINT 2024–2025",
                 fontsize=13, fontweight="bold")
    for ax, (nome, preds) in zip(axes, modelos_preds):
        cm = confusion_matrix(y_real, preds, labels=[0,1,2,3]).astype(float)
        for i in range(len(cm)):
            if cm[i].sum() > 0: cm[i] /= cm[i].sum()
        f1 = f1_score(y_real, preds, average="weighted", zero_division=0)
        sns.heatmap(cm, annot=True, fmt=".2f", cmap="Blues", ax=ax,
                    xticklabels=CATS_CURTAS, yticklabels=CATS_CURTAS, linewidths=0.5)
        ax.set_title(f"{nome}\nF1={f1:.2f}", fontsize=11, fontweight="bold")
        ax.set_ylabel("Real"); ax.set_xlabel("Previsto")
        ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    plt.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Figura 4.2 guardada: {caminho}")


def plotar_curvas_roc(modelos_proba, y_real, caminho="/content/graficos/figura_4_1.png"):
    """Gera Figura 4.1 — Curvas ROC comparativas dos 4 modelos."""
    from sklearn.preprocessing import label_binarize
    y_bin = label_binarize(y_real, classes=[0,1,2,3])
    plt.figure(figsize=(8, 6))
    cores = ["#E74C3C","#F39C12","#3498DB","#2ECC71"]
    for (nome, proba), cor in zip(modelos_proba, cores):
        fpr, tpr, _ = roc_curve(y_bin.ravel(),
                                  np.array(proba).ravel() if proba is not None
                                  else np.zeros_like(y_bin).ravel())
        auc_v = auc(fpr, tpr)
        plt.plot(fpr, tpr, color=cor, lw=2, label=f"{nome} (AUC={auc_v:.2f})")
    plt.plot([0,1],[0,1],"k--", lw=1)
    plt.xlabel("Taxa de Falsos Positivos"); plt.ylabel("Taxa de Verdadeiros Positivos")
    plt.title("Figura 4.1 — Curvas ROC Comparativas
Corpus Angola OSINT 2024–2025")
    plt.legend(loc="lower right"); plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(caminho, dpi=150, bbox_inches="tight")
    plt.show()
    print(f"Figura 4.1 guardada: {caminho}")
