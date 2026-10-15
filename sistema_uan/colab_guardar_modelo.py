# ===== Célula para o Colab: guardar o BERTimbau afinado no Google Drive =====
# Correr NA MESMA SESSÃO em que o treino terminou (os ficheiros em /content perdem-se ao fechar).
# Procura a pasta do modelo gravada pelo train_bertimbau.py; se o script tiver gravado
# apenas um state_dict (.pt), reconstrói o modelo e grava-o no formato Hugging Face.

import glob, os, shutil, json
from google.colab import drive

drive.mount('/content/drive')
DESTINO = '/content/drive/MyDrive/dissertacao_uan/bertimbau_uan_v13'
ROTULOS = ['Normal', 'Desinformacao', 'Odio', 'Mobilizacao']   # ordem do pipeline
BASE = 'neuralmind/bert-base-portuguese-cased'                 # alterar se treinou outro --model-name

candidatas = [os.path.dirname(p) for p in glob.glob('/content/**/config.json', recursive=True)
              if 'drive/' not in p and glob.glob(os.path.join(os.path.dirname(p), '*.safetensors')) +
                 glob.glob(os.path.join(os.path.dirname(p), 'pytorch_model.bin'))]
print('Pastas de modelo encontradas:', candidatas)

from transformers import AutoModelForSequenceClassification, AutoTokenizer
if candidatas:
    ORIGEM = sorted(candidatas, key=os.path.getmtime)[-1]          # a mais recente
    modelo = AutoModelForSequenceClassification.from_pretrained(ORIGEM)
    try:
        tok = AutoTokenizer.from_pretrained(ORIGEM)
    except Exception:
        tok = AutoTokenizer.from_pretrained(BASE)
else:
    import torch
    pts = sorted(glob.glob('/content/**/*.pt', recursive=True), key=os.path.getmtime)
    assert pts, 'Nenhum modelo encontrado em /content. O treino terminou nesta sessão?'
    print('A usar state_dict:', pts[-1])
    modelo = AutoModelForSequenceClassification.from_pretrained(BASE, num_labels=4)
    modelo.load_state_dict(torch.load(pts[-1], map_location='cpu'))
    tok = AutoTokenizer.from_pretrained(BASE)

modelo.config.id2label = dict(enumerate(ROTULOS))
modelo.config.label2id = {r: i for i, r in enumerate(ROTULOS)}
os.makedirs(DESTINO, exist_ok=True)
modelo.save_pretrained(DESTINO)
tok.save_pretrained(DESTINO)
print('Guardado em', DESTINO, '->', os.listdir(DESTINO))
# Atenção: confirme que a ordem ROTULOS é a mesma usada no treino (ver label_encoder/labels do test_metrics.json).
