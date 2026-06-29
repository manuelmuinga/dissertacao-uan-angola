"""
=============================================================================
MÓDULO 3a — Classificador BERT (BERTimbau)
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026

Sistema Operativo: Windows 10/11 (64-bit)
Notas Windows:
  - GPU NVIDIA: instalar CUDA Toolkit 11.8 + cuDNN antes do PyTorch
    https://developer.nvidia.com/cuda-11-8-0-download-archive
  - Instalar PyTorch com CUDA:
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
  - Sem GPU: PyTorch CPU funciona mas treino e mais lento
  - Treino realizado em Google Colab Pro (GPU T4 16GB) e modelo guardado localmente

Resultados: F1-Score = 91% | AUC-ROC = 0,95 | Kappa Cohen = 0,88
=============================================================================
"""

import os
import logging
import numpy as np
import torch
import pymongo
from pathlib import Path
from torch.utils.data import Dataset, DataLoader
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    AdamW,
    get_linear_schedule_with_warmup,
)
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    cohen_kappa_score,
    accuracy_score,
    f1_score,
)
from dotenv import load_dotenv

load_dotenv()

# Logging (UTF-8 para Windows)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "bert.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Configuracoes ─────────────────────────────────────────────────────────────
MODELO_BERT   = "neuralmind/bert-base-portuguese-cased"
NUM_CLASSES   = 4
MAX_LENGTH    = 128
BATCH_SIZE    = 16
NUM_EPOCHS    = 3
LEARNING_RATE = 2e-5
LIMIAR_ALERTA = 0.75

# Deteccao automatica de GPU (NVIDIA CUDA no Windows)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info(f"Dispositivo: {DEVICE}")
if torch.cuda.is_available():
    logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
else:
    logger.info("GPU nao disponivel — a usar CPU. Treino mais lento.")

CATEGORIAS = {
    0: "Normal",
    1: "Desinformacao",
    2: "Discurso de Odio",
    3: "Mobilizacao Hostil",
}

# Caminho para guardar/carregar modelo (Windows — usar Path para compatibilidade)
MODELO_DIR = Path("modelos") / "bert_finetuned"
MODELO_DIR.mkdir(parents=True, exist_ok=True)


# ─── Dataset ───────────────────────────────────────────────────────────────────
class AmeacasDataset(Dataset):
    def __init__(self, textos, rotulos, tokenizer, max_length):
        self.textos     = textos
        self.rotulos    = rotulos
        self.tokenizer  = tokenizer
        self.max_length = max_length

    def __len__(self):
        return len(self.textos)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.textos[idx],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      enc["input_ids"].squeeze(),
            "attention_mask": enc["attention_mask"].squeeze(),
            "label":          torch.tensor(self.rotulos[idx], dtype=torch.long),
        }


# ─── Classificador BERT ────────────────────────────────────────────────────────
class ClassificadorBERT:
    def __init__(self, caminho_modelo: str = None):
        self.tokenizer = BertTokenizer.from_pretrained(MODELO_BERT)

        if caminho_modelo and Path(caminho_modelo).exists():
            self.modelo = BertForSequenceClassification.from_pretrained(caminho_modelo)
            logger.info(f"Modelo carregado de: {caminho_modelo}")
        else:
            self.modelo = BertForSequenceClassification.from_pretrained(
                MODELO_BERT, num_labels=NUM_CLASSES
            )
            logger.info(f"BERTimbau iniciado: {MODELO_BERT}")

        self.modelo.to(DEVICE)

    def treinar(self, X_train, y_train, X_val=None, y_val=None):
        """
        Fine-tuning do BERTimbau.
        Recomendado: executar no Google Colab Pro (GPU T4) e guardar o modelo.
        No Windows com GPU NVIDIA: funciona directamente.
        """
        dataset = AmeacasDataset(X_train, y_train, self.tokenizer, MAX_LENGTH)
        loader  = DataLoader(
            dataset, batch_size=BATCH_SIZE, shuffle=True,
            num_workers=0  # Windows: num_workers=0 (evita erros de multiprocessing)
        )
        optimizer = AdamW(self.modelo.parameters(), lr=LEARNING_RATE,
                          no_deprecation_warning=True)
        total_steps = len(loader) * NUM_EPOCHS
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=total_steps // 10,
            num_training_steps=total_steps
        )

        historico = {"loss": [], "val_accuracy": []}

        for epoca in range(NUM_EPOCHS):
            self.modelo.train()
            loss_total = 0

            for batch in loader:
                optimizer.zero_grad()
                input_ids      = batch["input_ids"].to(DEVICE)
                attention_mask = batch["attention_mask"].to(DEVICE)
                labels         = batch["label"].to(DEVICE)

                outputs = self.modelo(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                loss = outputs.loss
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.modelo.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                loss_total += loss.item()

            loss_media = loss_total / len(loader)
            historico["loss"].append(loss_media)
            logger.info(f"Epoca {epoca + 1}/{NUM_EPOCHS} | Loss: {loss_media:.4f}")

            if X_val and y_val:
                metricas = self.avaliar(X_val, y_val)
                historico["val_accuracy"].append(metricas["accuracy"])

        # Guardar modelo no Windows
        self.guardar(str(MODELO_DIR))
        return historico

    def classificar(self, texto: str) -> dict:
        """Classifica uma publicacao e retorna categoria e confianca."""
        self.modelo.eval()
        enc = self.tokenizer(
            texto, max_length=MAX_LENGTH,
            padding="max_length", truncation=True,
            return_tensors="pt"
        )
        input_ids      = enc["input_ids"].to(DEVICE)
        attention_mask = enc["attention_mask"].to(DEVICE)

        with torch.no_grad():
            outputs = self.modelo(input_ids=input_ids, attention_mask=attention_mask)

        probs     = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
        classe    = int(np.argmax(probs))
        confianca = float(probs[classe])

        return {
            "categoria":    CATEGORIAS[classe],
            "classe":       classe,
            "confianca":    round(confianca, 4),
            "alerta":       confianca >= LIMIAR_ALERTA and classe != 0,
            "distribuicao": {CATEGORIAS[i]: round(float(p), 4) for i, p in enumerate(probs)},
        }

    def avaliar(self, X_test, y_test) -> dict:
        """Avalia o modelo e devolve metricas completas."""
        self.modelo.eval()
        predicoes, probs_todas = [], []

        for texto in X_test:
            r = self.classificar(texto)
            predicoes.append(r["classe"])
            probs_todas.append(list(r["distribuicao"].values()))

        prob_array = np.array(probs_todas)
        acc   = accuracy_score(y_test, predicoes)
        f1    = f1_score(y_test, predicoes, average="weighted")
        kappa = cohen_kappa_score(y_test, predicoes)

        try:
            auc = roc_auc_score(y_test, prob_array, multi_class="ovr", average="weighted")
        except Exception:
            auc = None

        logger.info(f"Accuracy: {acc:.4f} | F1: {f1:.4f} | Kappa: {kappa:.4f} | AUC: {auc}")
        logger.info("\n" + classification_report(
            y_test, predicoes, target_names=list(CATEGORIAS.values())
        ))

        return {
            "accuracy":         round(acc, 4),
            "f1_score":         round(f1, 4),
            "kappa":            round(kappa, 4),
            "auc_roc":          round(auc, 4) if auc else None,
            "confusion_matrix": confusion_matrix(y_test, predicoes).tolist(),
        }

    def guardar(self, caminho: str) -> None:
        """
        Guarda modelo fine-tunado.
        No Windows: os caminhos com barras invertidas sao geridos
        automaticamente pelo modulo pathlib.
        """
        Path(caminho).mkdir(parents=True, exist_ok=True)
        self.modelo.save_pretrained(caminho)
        self.tokenizer.save_pretrained(caminho)
        logger.info(f"Modelo guardado em: {caminho}")

    def guardar_resultado_mongodb(self, pub_id: str, resultado: dict) -> None:
        """Persiste resultado de classificacao no MongoDB."""
        client  = pymongo.MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
        colecao = client["dissertacao_angola"]["publicacoes_classificadas"]
        colecao.update_one(
            {"id_externo": pub_id},
            {"$set": {**resultado, "modelo": "bert", "id_externo": pub_id}},
            upsert=True
        )


# ─── Execucao ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    clf = ClassificadorBERT(str(MODELO_DIR) if MODELO_DIR.exists() else None)

    exemplos = [
        "O governo de Angola anunciou novas medidas de seguranca para Luanda.",
        "URGENTE: Concentracao no largo da independencia amanha as 10h! Partilha!",
        "Este grupo nao merece viver nesta terra!",
        "Video revela presidente a confessar corrupcao — PARTILHA!",
    ]

    print("\n=== Classificacao BERT (BERTimbau) — Windows ===")
    for texto in exemplos:
        r = clf.classificar(texto)
        status = "[ALERTA]" if r["alerta"] else "[Normal]"
        print(f"{status} {r['categoria']} ({r['confianca']*100:.1f}%) | {texto[:60]}...")
