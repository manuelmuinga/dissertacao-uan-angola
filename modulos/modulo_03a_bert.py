"""
Módulo 3a — Classificador BERTimbau (F1=91%, AUC-ROC=0,95)
Dissertação UAN — Manuel Muinga 2026 | SO: Windows 11 / Google Colab Pro GPU T4
"""
import torch
import numpy as np
from transformers import BertTokenizer, BertForSequenceClassification

MODELO_BERT = "neuralmind/bert-base-portuguese-cased"
CATEGORIAS  = {0:"Normal",1:"Desinformação",2:"Discurso de Ódio",3:"Mobilização Hostil"}
LIMIAR      = 0.75
DEVICE      = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class ClassificadorBERT:
    """
    BERTimbau com fine-tuning para detecção de ameaças em português angolano.
    Hiperparâmetros: 3 épocas, lr=2e-5, batch=16, max_len=128, GPU T4.
    """
    def __init__(self, caminho_modelo=None):
        src = caminho_modelo or MODELO_BERT
        self.tokenizer = BertTokenizer.from_pretrained(src)
        self.modelo    = BertForSequenceClassification.from_pretrained(
            src, num_labels=4).to(DEVICE)
        self.modelo.eval()

    def classificar(self, texto):
        if not texto or len(texto.strip()) < 3:
            return {"categoria":"Normal","confianca":1.0,"alerta":False}
        enc = self.tokenizer(texto, max_length=128, padding="max_length",
                             truncation=True, return_tensors="pt")
        with torch.no_grad():
            out = self.modelo(
                input_ids=enc["input_ids"].to(DEVICE),
                attention_mask=enc["attention_mask"].to(DEVICE))
        probs = torch.softmax(out.logits, dim=-1).cpu().numpy()[0]
        cl    = int(np.argmax(probs))
        conf  = float(probs[cl])
        return {"categoria":CATEGORIAS[cl], "confianca":round(conf,4),
                "alerta":conf >= LIMIAR and cl != 0,
                "distribuicao":{CATEGORIAS[i]:round(float(p),4) for i,p in enumerate(probs)}}

    def classificar_batch(self, textos):
        return [self.classificar(t) for t in textos]

    def guardar(self, caminho):
        self.modelo.save_pretrained(caminho)
        self.tokenizer.save_pretrained(caminho)
        print(f"Modelo guardado em: {caminho}")
