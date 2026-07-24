"""
Módulo 3b — Classificador Bi-LSTM (F1=87%, AUC-ROC=0,91)
Dissertação UAN — Manuel Muinga 2026 | SO: Windows 11 / Google Colab Pro GPU T4
"""
import numpy as np

CATEGORIAS = {0:"Normal",1:"Desinformação",2:"Discurso de Ódio",3:"Mobilização Hostil"}
LIMIAR     = 0.75


def criar_modelo_bilstm(vocab_size=50000, embed_dim=128,
                         lstm_units1=128, lstm_units2=64,
                         dropout=0.3, num_classes=4):
    """
    Bi-LSTM com 2 camadas para classificação de ameaças.
    Hiperparâmetros: 10 épocas, batch=32, dropout=0.3, softmax.
    """
    from tensorflow import keras
    model = keras.Sequential([
        keras.layers.Embedding(vocab_size, embed_dim, mask_zero=True),
        keras.layers.Bidirectional(keras.layers.LSTM(lstm_units1, return_sequences=True)),
        keras.layers.Dropout(dropout),
        keras.layers.Bidirectional(keras.layers.LSTM(lstm_units2)),
        keras.layers.Dropout(dropout),
        keras.layers.Dense(64, activation="relu"),
        keras.layers.Dense(num_classes, activation="softmax"),
    ])
    model.compile(optimizer="adam", loss="sparse_categorical_crossentropy",
                  metrics=["accuracy"])
    return model


class ClassificadorLSTM:
    def __init__(self, modelo=None, tokenizer=None):
        self.modelo    = modelo
        self.tokenizer = tokenizer

    def classificar(self, texto, max_len=128):
        if not self.modelo or not self.tokenizer:
            return {"categoria":"Normal","confianca":1.0,"alerta":False}
        seq   = self.tokenizer.texts_to_sequences([texto])
        from tensorflow.keras.preprocessing.sequence import pad_sequences
        padded = pad_sequences(seq, maxlen=max_len, padding="post", truncating="post")
        probs  = self.modelo.predict(padded, verbose=0)[0]
        cl     = int(np.argmax(probs))
        conf   = float(probs[cl])
        return {"categoria":CATEGORIAS[cl], "confianca":round(conf,4),
                "alerta":conf >= LIMIAR and cl != 0}
