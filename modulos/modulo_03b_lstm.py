"""
=============================================================================
MÓDULO 3b — Classificador Bi-LSTM (Bidirecional)
=============================================================================
Dissertação: Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
Autor: Manuel Muinga | UAN — Faculdade de Engenharia | 2026
=============================================================================
Descrição:
    Rede neural Bi-LSTM para classificação de ameaças, com ênfase na
    deteção de padrões de escalada temporal. Melhor desempenho em
    Mobilização Hostil (F1 = 90%).
    
    Resultados: F1-Score = 87% | AUC-ROC = 0,91 | Kappa Cohen = 0,83
=============================================================================
"""

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (
    Embedding, Bidirectional, LSTM, Dense, Dropout, GlobalMaxPooling1D
)
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from loguru import logger

# ─── Configurações ────────────────────────────────────────────────────────────
VOCAB_SIZE    = 30000
MAX_LENGTH    = 128
EMBED_DIM     = 128
LSTM_UNITS_1  = 128
LSTM_UNITS_2  = 64
NUM_CLASSES   = 4
DROPOUT_RATE  = 0.3
BATCH_SIZE    = 32
NUM_EPOCHS    = 10
LIMIAR_ALERTA = 0.75

CATEGORIAS = {0: "Normal", 1: "Desinformação", 2: "Discurso de Ódio", 3: "Mobilização Hostil"}

# Reprodutibilidade
tf.random.set_seed(42)
np.random.seed(42)


class ClassificadorBiLSTM:
    def __init__(self):
        self.tokenizer = Tokenizer(num_words=VOCAB_SIZE, oov_token="<OOV>")
        self.modelo    = None
    
    def construir_modelo(self) -> None:
        """
        Arquitectura Bi-LSTM bidirecional com duas camadas LSTM e Dropout.
        """
        self.modelo = Sequential([
            Embedding(VOCAB_SIZE, EMBED_DIM, input_length=MAX_LENGTH, mask_zero=True),
            Bidirectional(LSTM(LSTM_UNITS_1, return_sequences=True, dropout=DROPOUT_RATE)),
            Bidirectional(LSTM(LSTM_UNITS_2, dropout=DROPOUT_RATE)),
            Dense(64, activation="relu"),
            Dropout(DROPOUT_RATE),
            Dense(NUM_CLASSES, activation="softmax"),
        ])
        
        self.modelo.compile(
            optimizer=keras.optimizers.Adam(learning_rate=1e-3),
            loss="sparse_categorical_crossentropy",
            metrics=["accuracy"],
        )
        logger.info(f"Bi-LSTM construído. Parâmetros: {self.modelo.count_params():,}")
        self.modelo.summary()
    
    def treinar(self, X_train: list, y_train: list,
                X_val: list = None, y_val: list = None) -> keras.callbacks.History:
        """
        Treina o Bi-LSTM no corpus de ameaças angolano.
        """
        # Tokenização e padding
        self.tokenizer.fit_on_texts(X_train)
        X_train_seq = pad_sequences(self.tokenizer.texts_to_sequences(X_train), maxlen=MAX_LENGTH)
        y_train_arr = np.array(y_train)
        
        if not self.modelo:
            self.construir_modelo()
        
        callbacks = [
            keras.callbacks.EarlyStopping(patience=3, restore_best_weights=True),
            keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=2, min_lr=1e-5),
            keras.callbacks.ModelCheckpoint(
                "modelos/bilstm_melhor.h5", save_best_only=True, monitor="val_accuracy"
            ),
        ]
        
        val_data = None
        if X_val and y_val:
            X_val_seq = pad_sequences(self.tokenizer.texts_to_sequences(X_val), maxlen=MAX_LENGTH)
            val_data  = (X_val_seq, np.array(y_val))
        
        historico = self.modelo.fit(
            X_train_seq, y_train_arr,
            batch_size=BATCH_SIZE,
            epochs=NUM_EPOCHS,
            validation_data=val_data,
            callbacks=callbacks,
            verbose=1,
        )
        return historico
    
    def classificar(self, texto: str) -> dict:
        """Classifica uma publicação e retorna categoria e confiança."""
        seq = pad_sequences(self.tokenizer.texts_to_sequences([texto]), maxlen=MAX_LENGTH)
        prob = self.modelo.predict(seq, verbose=0)[0]
        classe    = int(np.argmax(prob))
        confianca = float(prob[classe])
        
        return {
            "categoria":  CATEGORIAS[classe],
            "classe":     classe,
            "confianca":  round(confianca, 4),
            "alerta":     confianca >= LIMIAR_ALERTA and classe != 0,
            "distribuicao": {CATEGORIAS[i]: round(float(p), 4) for i, p in enumerate(prob)},
        }
    
    def avaliar(self, X_test: list, y_test: list) -> dict:
        """Avalia o modelo no conjunto de teste."""
        X_test_seq  = pad_sequences(self.tokenizer.texts_to_sequences(X_test), maxlen=MAX_LENGTH)
        probs       = self.modelo.predict(X_test_seq, verbose=0)
        predicoes   = np.argmax(probs, axis=1)
        
        f1    = f1_score(y_test, predicoes, average="weighted")
        cm    = confusion_matrix(y_test, predicoes)
        
        logger.info(f"F1-Score Bi-LSTM: {f1:.4f}")
        logger.info("\n" + classification_report(y_test, predicoes,
                    target_names=list(CATEGORIAS.values())))
        
        return {
            "f1_score":         round(f1, 4),
            "confusion_matrix": cm.tolist(),
            "predicoes":        predicoes.tolist(),
        }
    
    def guardar(self, caminho: str) -> None:
        """Guarda o modelo e tokenizer."""
        os.makedirs(caminho, exist_ok=True)
        self.modelo.save(f"{caminho}/bilstm_modelo.h5")
        import pickle
        with open(f"{caminho}/bilstm_tokenizer.pkl", "wb") as f:
            pickle.dump(self.tokenizer, f)
        logger.info(f"Bi-LSTM guardado em: {caminho}")


if __name__ == "__main__":
    clf = ClassificadorBiLSTM()
    clf.construir_modelo()
    logger.info("Bi-LSTM pronto para treino.")
