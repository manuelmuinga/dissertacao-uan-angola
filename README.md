# 🔍 Monitoramento Inteligente de Ameaças em Redes Sociais em Angola

**Dissertação de Mestrado — Universidade Agostinho Neto (UAN)**  
**Faculdade de Engenharia — Engenharia Informática e Ciência de Dados**  
**Autor:** Manuel Muinga | **Ano:** 2026

---

## 📌 Descrição

Sistema de monitoramento inteligente baseado em **Inteligência Artificial** e **Big Data** para deteção, classificação e antecipação de ameaças em redes sociais no contexto angolano, com visualização em tempo real via **dashboard Power BI**.

### Resultados Principais
| Modelo | Precisão | Recall | F1-Score | AUC-ROC |
|--------|----------|--------|----------|---------|
| Random Forest | 82% | 79% | 80% | 0,84 |
| SVM | 80% | 77% | 78% | 0,81 |
| Bi-LSTM | 86% | 88% | **87%** | 0,91 |
| **BERT (BERTimbau)** | **90%** | **92%** | **91%** | **0,95** |

- ⏱️ Tempo médio de deteção: **47 segundos** (vs. 24–72h manual)
- 📡 Antecedência média de alerta: **76 horas**
- 📊 Dashboard Power BI com alertas automáticos via Power Automate

---

## 📁 Estrutura do Repositório

```
dissertacao-uan-angola/
│
├── modulos/
│   ├── modulo_01_recolha.py          # Recolha via APIs (Twitter/X, Facebook, Telegram)
│   ├── modulo_02_preprocessamento.py  # Limpeza, lematização, anonimização SHA-256
│   ├── modulo_03a_bert.py             # Classificador BERTimbau (PyTorch)
│   ├── modulo_03b_lstm.py             # Classificador Bi-LSTM (TensorFlow/Keras)
│   ├── modulo_04_pipeline.py          # Pipeline principal (Kafka + Spark + alertas)
│   └── modulo_05_avaliacao.py         # Métricas, matrizes de confusão, curvas ROC
│
├── powerbi/
│   ├── dax_medidas.md                 # Medidas DAX para o dashboard Power BI
│   └── power_automate_flow.md         # Documentação do fluxo de alertas automáticos
│
├── dados/
│   └── schema_mongodb.json            # Schema da base de dados MongoDB
│
├── requirements.txt                   # Dependências Python
└── README.md
```

---

## 🚀 Instalação e Configuração

### 1. Clonar o repositório
```bash
git clone https://github.com/manuelmuinga/dissertacao-uan-angola.git
cd dissertacao-uan-angola
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
```

### 3. Configurar variáveis de ambiente
```bash
export TWITTER_BEARER_TOKEN="seu_token_aqui"
export FACEBOOK_ACCESS_TOKEN="seu_token_aqui"
export TELEGRAM_BOT_TOKEN="seu_token_aqui"
export MONGODB_URI="mongodb://localhost:27017"
```

### 4. Executar o pipeline
```bash
python modulos/modulo_04_pipeline.py
```

---

## 📐 Arquitetura do Sistema

```
Redes Sociais (Facebook, Twitter/X, Telegram, Web)
        │
        ▼
[Módulo 1: Recolha via APIs + Crawlers]
        │
        ▼
[Módulo 2: Pré-processamento + Anonimização SHA-256]
        │
        ▼
[Módulo 3: Classificação BERT / Bi-LSTM]
        │ (confiança > 0,75)
        ▼
[Apache Kafka + Spark — Pipeline em Tempo Real]
        │
        ├──▶ MongoDB (dados brutos e classificados)
        ├──▶ SQL Server / Data Warehouse (modelo estrela)
        └──▶ Power BI Dashboard + Power Automate (alertas)
```

---

## ⚖️ Conformidade Ética

- Recolha exclusiva de dados **publicamente disponíveis** via APIs oficiais
- Anonimização de identificadores por **hash SHA-256** (Lei n.º 22/11 — Angola)
- Sem acesso a comunicações privadas encriptadas
- Declaração de ausência de conflitos de interesse

---

## 📚 Citação

```bibtex
@mastersthesis{muinga2026,
  author  = {Muinga, Manuel},
  title   = {Monitoramento Inteligente de Ameaças em Redes Sociais em Angola
             para o Apoio à Defesa e Segurança Nacional},
  school  = {Universidade Agostinho Neto, Faculdade de Engenharia},
  year    = {2026},
  address = {Luanda, Angola},
  url     = {https://github.com/manuelmuinga/dissertacao-uan-angola}
}
```

---

## 📄 Licença

© 2026 Manuel Muinga — Universidade Agostinho Neto. Todos os direitos reservados.  
Código disponível para fins académicos com citação obrigatória da fonte.
