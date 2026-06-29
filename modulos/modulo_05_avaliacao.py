"""
=============================================================================
MÓDULO 5 — Avaliação de Modelos e Visualização de Resultados
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
=============================================================================
Descrição:
    Módulo de avaliação comparativa dos quatro modelos (SVM, Random Forest,
    Bi-LSTM, BERT), gerando:
    - Matrizes de confusão (4×4)
    - Curvas ROC comparativas
    - Relatório de métricas (F1, AUC-ROC, Kappa de Cohen)
    - Exportação para Power BI (CSV)
=============================================================================
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve, auc, cohen_kappa_score, f1_score
)
from sklearn.svm import SVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from loguru import logger

CATEGORIAS = ["Normal", "Desinformação", "Discurso de Ódio", "Mobilização Hostil"]
CORES_MODELOS = {
    "SVM":            "#E74C3C",
    "Random Forest":  "#F39C12",
    "Bi-LSTM":        "#2ECC71",
    "BERT (BERTimbau)": "#3498DB",
}


def treinar_baseline(X_train: list, y_train: list) -> dict:
    """Treina os modelos baseline (SVM e Random Forest) com TF-IDF."""
    modelos = {
        "SVM": Pipeline([
            ("tfidf", TfidfVectorizer(max_features=20000, ngram_range=(1,2))),
            ("clf",   SVC(kernel="rbf", C=10, probability=True, random_state=42)),
        ]),
        "Random Forest": Pipeline([
            ("tfidf", TfidfVectorizer(max_features=20000, ngram_range=(1,2))),
            ("clf",   RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)),
        ]),
    }
    for nome, modelo in modelos.items():
        modelo.fit(X_train, y_train)
        logger.info(f"{nome} treinado.")
    return modelos


def plotar_matrizes_confusao(resultados: dict, caminho: str = "graficos/") -> None:
    """
    Gera matrizes de confusão (4×4) para cada modelo — Figura 4.2 da dissertação.
    """
    os.makedirs(caminho, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for i, (nome, dados) in enumerate(resultados.items()):
        cm = confusion_matrix(dados["y_true"], dados["y_pred"])
        cm_norm = cm.astype("float") / cm.sum(axis=1)[:, np.newaxis]
        
        sns.heatmap(
            cm_norm, annot=True, fmt=".2f", cmap="Blues",
            xticklabels=CATEGORIAS, yticklabels=CATEGORIAS,
            ax=axes[i], linewidths=0.5, cbar_kws={"shrink": 0.8}
        )
        axes[i].set_title(f"{nome}\nF1={dados['f1']:.2f} | AUC={dados.get('auc',0):.2f}",
                          fontsize=12, fontweight="bold")
        axes[i].set_ylabel("Real", fontsize=10)
        axes[i].set_xlabel("Previsto", fontsize=10)
        axes[i].tick_params(axis="x", rotation=30)
    
    plt.suptitle("Figura 4.2 — Matrizes de Confusão (4×4)\nCorpus Angola — Jan 2024 a Ago 2025",
                 fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    plt.savefig(f"{caminho}figura_4_2_matrizes_confusao.png", dpi=150, bbox_inches="tight")
    logger.info(f"Matrizes de confusão guardadas: {caminho}figura_4_2_matrizes_confusao.png")
    plt.close()


def plotar_curvas_roc(resultados: dict, caminho: str = "graficos/") -> None:
    """
    Gera curvas ROC comparativas dos quatro modelos — Figura 4.1 da dissertação.
    """
    os.makedirs(caminho, exist_ok=True)
    plt.figure(figsize=(10, 8))
    
    for nome, dados in resultados.items():
        if "y_prob" in dados and dados["y_prob"] is not None:
            # Curva ROC macro-average
            fpr_list, tpr_list = [], []
            for classe in range(4):
                y_bin = (np.array(dados["y_true"]) == classe).astype(int)
                fpr, tpr, _ = roc_curve(y_bin, np.array(dados["y_prob"])[:, classe])
                fpr_list.append(fpr)
                tpr_list.append(tpr)
            
            # Interpolação macro
            all_fpr = np.unique(np.concatenate(fpr_list))
            mean_tpr = np.zeros_like(all_fpr)
            for j in range(4):
                mean_tpr += np.interp(all_fpr, fpr_list[j], tpr_list[j])
            mean_tpr /= 4
            auc_score = auc(all_fpr, mean_tpr)
            
            plt.plot(all_fpr, mean_tpr,
                     color=CORES_MODELOS.get(nome, "gray"),
                     lw=2.5,
                     label=f"{nome} (AUC = {auc_score:.2f})")
    
    plt.plot([0, 1], [0, 1], "k--", lw=1.5, label="Classificador Aleatório (AUC = 0,50)")
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Taxa de Falsos Positivos (FPR)", fontsize=12)
    plt.ylabel("Taxa de Verdadeiros Positivos (TPR)", fontsize=12)
    plt.title("Figura 4.1 — Curvas ROC Comparativas dos Quatro Modelos\n"
              "Corpus Angola — Jan 2024 a Ago 2025", fontsize=13, fontweight="bold")
    plt.legend(loc="lower right", fontsize=11)
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{caminho}figura_4_1_curvas_roc.png", dpi=150, bbox_inches="tight")
    logger.info(f"Curvas ROC guardadas: {caminho}figura_4_1_curvas_roc.png")
    plt.close()


def exportar_powerbi(resultados: dict, caminho: str = "powerbi/dados/") -> None:
    """
    Exporta métricas dos modelos para CSV — importação no Power BI Desktop.
    """
    os.makedirs(caminho, exist_ok=True)
    
    # Tabela de métricas por modelo
    metricas = []
    for nome, dados in resultados.items():
        metricas.append({
            "Modelo":     nome,
            "F1_Score":   dados.get("f1", 0),
            "AUC_ROC":    dados.get("auc", 0),
            "Kappa":      dados.get("kappa", 0),
            "Precisao":   dados.get("precisao", 0),
            "Recall":     dados.get("recall", 0),
        })
    
    df_metricas = pd.DataFrame(metricas)
    df_metricas.to_csv(f"{caminho}metricas_modelos.csv", index=False, encoding="utf-8-sig")
    logger.info(f"Métricas exportadas para Power BI: {caminho}metricas_modelos.csv")
    print("\n=== Tabela 4.1 — Resultados dos Modelos ===")
    print(df_metricas.to_string(index=False))


if __name__ == "__main__":
    logger.info("Módulo de avaliação pronto. Execute após treino dos modelos.")
    logger.info("Saída: graficos/figura_4_1_curvas_roc.png")
    logger.info("Saída: graficos/figura_4_2_matrizes_confusao.png")
    logger.info("Saída: powerbi/dados/metricas_modelos.csv")
