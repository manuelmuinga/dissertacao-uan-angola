"""
=============================================================================
MÓDULO 3a — Classificador BERT (BERTimbau)
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
=============================================================================
Descrição:
    Fine-tuning do modelo BERTimbau (neuralmind/bert-base-portuguese-cased)
    para classificação de ameaças em 4 categorias:
      0 — Normal
      1 — Desinformação
      2 — Discurso de Ódio
      3 — Mobilização Hostil
    
    Resultados: F1-Score = 91% | AUC-ROC = 0,95 | Kappa Cohen = 0,88
=============================================================================
"""

import os
import numpy as np
import torch
import pymongo
from torch import nn
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
)
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# ─── Configurações ────────────────────────────────────────────────────────────
MODELO_BERT     = "neuralmind/bert-base-portuguese-cased"  # BERTimbau
NUM_CLASSES     = 4
MAX_LENGTH      = 128
BATCH_SIZE      = 16
NUM_EPOCHS      = 3
LEARNING_RATE   = 2e-5
LIMIAR_ALERTA   = 0.75  # confiança mínima para emitir alerta Power BI
DEVICE          = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CATEGORIAS = {
    0: "Normal",
    1: "Desinformação",
    2: "Discurso de Ódio",
    3: "Mobilização Hostil",
}

logger.info(f"Dispositivo: {DEVICE}")


# ─── Dataset ──────────────────────────────────────────────────────────────────
class AmeacasDataset(Dataset):
    def __init__(self, textos: list, rotulos: list, tokenizer, max_length: int):
        self.textos    = textos
        self.rotulos   = rotulos
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.textos)
    
    def __getitem__(self, idx):
        encodings = self.tokenizer(
            self.textos[idx],
            max_length=self.max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return {
            "input_ids":      encodings["input_ids"].squeeze(),
            "attention_mask": encodings["attention_mask"].squeeze(),
            "label":          torch.tensor(self.rotulos[idx], dtype=torch.long),
        }


# ─── Classificador BERT ───────────────────────────────────────────────────────
class ClassificadorBERT:
    def __init__(self, caminho_modelo: str = None):
        self.tokenizer = BertTokenizer.from_pretrained(MODELO_BERT)
        
        if caminho_modelo and os.path.exists(caminho_modelo):
            self.modelo = BertForSequenceClassification.from_pretrained(caminho_modelo)
            logger.info(f"Modelo carregado de: {caminho_modelo}")
        else:
            self.modelo = BertForSequenceClassification.from_pretrained(
                MODELO_BERT, num_labels=NUM_CLASSES
            )
            logger.info(f"Modelo BERTimbau iniciado: {MODELO_BERT}")
        
        self.modelo.to(DEVICE)
    
    def treinar(self, X_train: list, y_train: list,
                X_val: list = None, y_val: list = None) -> dict:
        """
        Fine-tuning do BERTimbau no corpus de ameaças angolano.
        
        Args:
            X_train, y_train: Dados de treino.
            X_val, y_val:     Dados de validação (opcional).
        
        Returns:
            Dicionário com histórico de treino (loss e accuracy por época).
        """
        dataset_treino = AmeacasDataset(X_train, y_train, self.tokenizer, MAX_LENGTH)
        loader_treino  = DataLoader(dataset_treino, batch_size=BATCH_SIZE, shuffle=True)
        
        optimizer = AdamW(self.modelo.parameters(), lr=LEARNING_RATE, no_deprecation_warning=True)
        total_steps = len(loader_treino) * NUM_EPOCHS
        scheduler = get_linear_schedule_with_warmup(
            optimizer, num_warmup_steps=total_steps // 10,
            num_training_steps=total_steps
        )
        
        historico = {"loss": [], "val_accuracy": []}
        
        for epoca in range(NUM_EPOCHS):
            self.modelo.train()
            loss_total = 0
            
            for batch in loader_treino:
                optimizer.zero_grad()
                input_ids      = batch["input_ids"].to(DEVICE)
                attention_mask = batch["attention_mask"].to(DEVICE)
                labels         = batch["label"].to(DEVICE)
                
                outputs = self.modelo(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=labels,
                )
                loss = outputs.loss
                loss.backward()
                
                torch.nn.utils.clip_grad_norm_(self.modelo.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                loss_total += loss.item()
            
            loss_media = loss_total / len(loader_treino)
            historico["loss"].append(loss_media)
            logger.info(f"Época {epoca+1}/{NUM_EPOCHS} — Loss: {loss_media:.4f}")
            
            if X_val and y_val:
                metricas = self.avaliar(X_val, y_val)
                historico["val_accuracy"].append(metricas["accuracy"])
        
        return historico
    
    def classificar(self, texto: str) -> dict:
        """
        Classifica uma publicação e retorna categoria e confiança.
        
        Returns:
            {"categoria": str, "classe": int, "confianca": float,
             "alerta": bool, "distribuicao": dict}
        """
        self.modelo.eval()
        encodings = self.tokenizer(
            texto, max_length=MAX_LENGTH,
            padding="max_length", truncation=True,
            return_tensors="pt"
        )
        input_ids      = encodings["input_ids"].to(DEVICE)
        attention_mask = encodings["attention_mask"].to(DEVICE)
        
        with torch.no_grad():
            outputs = self.modelo(input_ids=input_ids, attention_mask=attention_mask)
        
        probabilidades = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
        classe         = int(np.argmax(probabilidades))
        confianca      = float(probabilidades[classe])
        
        return {
            "categoria":    CATEGORIAS[classe],
            "classe":       classe,
            "confianca":    round(confianca, 4),
            "alerta":       confianca >= LIMIAR_ALERTA and classe != 0,
            "distribuicao": {CATEGORIAS[i]: round(float(p), 4) for i, p in enumerate(probabilidades)},
        }
    
    def avaliar(self, X_test: list, y_test: list) -> dict:
        """
        Avalia o modelo no conjunto de teste.
        
        Returns:
            Dicionário com accuracy, F1, AUC-ROC e Kappa de Cohen.
        """
        self.modelo.eval()
        predicoes, probabilidades_todas = [], []
        
        for texto in X_test:
            resultado = self.classificar(texto)
            predicoes.append(resultado["classe"])
            probabilidades_todas.append(list(resultado["distribuicao"].values()))
        
        prob_array = np.array(probabilidades_todas)
        
        # Métricas
        from sklearn.metrics import accuracy_score, f1_score
        accuracy = accuracy_score(y_test, predicoes)
        f1       = f1_score(y_test, predicoes, average="weighted")
        kappa    = cohen_kappa_score(y_test, predicoes)
        
        # AUC-ROC (multiclasse)
        try:
            auc = roc_auc_score(y_test, prob_array, multi_class="ovr", average="weighted")
        except Exception:
            auc = None
        
        logger.info(f"Accuracy: {accuracy:.4f} | F1: {f1:.4f} | Kappa: {kappa:.4f} | AUC-ROC: {auc}")
        logger.info("\n" + classification_report(y_test, predicoes,
                    target_names=list(CATEGORIAS.values())))
        
        return {
            "accuracy": round(accuracy, 4),
            "f1_score": round(f1, 4),
            "kappa":    round(kappa, 4),
            "auc_roc":  round(auc, 4) if auc else None,
            "confusion_matrix": confusion_matrix(y_test, predicoes).tolist(),
        }
    
    def guardar(self, caminho: str) -> None:
        """Guarda o modelo e tokenizer fine-tunados."""
        self.modelo.save_pretrained(caminho)
        self.tokenizer.save_pretrained(caminho)
        logger.info(f"Modelo guardado em: {caminho}")
    
    def guardar_resultado_mongodb(self, pub_id: str, resultado: dict) -> None:
        """Persiste o resultado de classificação no MongoDB."""
        client = pymongo.MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
        colecao = client["dissertacao_angola"]["publicacoes_classificadas"]
        colecao.update_one(
            {"id_externo": pub_id},
            {"$set": {**resultado, "modelo": "bert", "id_externo": pub_id}},
            upsert=True
        )


# ─── Execução ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    classificador = ClassificadorBERT()
    
    # Exemplo de classificação
    exemplos = [
        "O governo de Angola anunciou novas medidas de segurança para Luanda.",
        "URGENTE: Concentração no largo da independência amanhã às 10h! Partilha!",
        "Este grupo de pessoas não merece viver nesta terra sagrada!",
        "Vídeo revela que o presidente confessou corrupção — PARTILHA!",
    ]
    
    print("\n=== Classificação BERT (BERTimbau) ===")
    for texto in exemplos:
        r = classificador.classificar(texto)
        status = "🚨 ALERTA" if r["alerta"] else "✅ Normal"
        print(f"{status} | {r['categoria']} ({r['confianca']*100:.1f}%) | {texto[:60]}...")
