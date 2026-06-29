# Monitoramento Inteligente de Ameacas em Redes Sociais em Angola

**Dissertacao de Mestrado — Universidade Agostinho Neto (UAN)**
**Faculdade de Engenharia — Engenharia Informatica e Ciencia de Dados**
**Autor:** Manuel Muinga | **Ano:** 2026

---

## Resultados Principais

| Modelo | Precisao | Recall | F1-Score | AUC-ROC |
|--------|----------|--------|----------|---------|
| Random Forest | 82% | 79% | 80% | 0,84 |
| SVM | 80% | 77% | 78% | 0,81 |
| Bi-LSTM | 86% | 88% | **87%** | 0,91 |
| **BERT (BERTimbau)** | **90%** | **92%** | **91%** | **0,95** |

- Tempo medio de deteccao: **47 segundos** (vs. 24-72h manual)
- Antecedencia media de alerta: **76 horas**
- Dashboard Power BI com alertas automaticos via Power Automate

---

## Sistema Operativo e Requisitos

**Windows 10/11 (64-bit)**

| Componente | Especificacao |
|---|---|
| SO | Windows 10/11 (64-bit) |
| Python | 3.11 (https://www.python.org/downloads/) |
| GPU (opcional) | NVIDIA com CUDA 11.8 (treino mais rapido) |
| MongoDB | MongoDB Community Server 7.0 (Windows Service) |
| SQL Server | SQL Server Express 2022 (gratuito) |
| Power BI | Power BI Desktop (https://powerbi.microsoft.com/pt-pt/) |
| Kafka | WSL2 + Ubuntu ou Docker Desktop for Windows |

---

## Estrutura do Repositorio

```
dissertacao-uan-angola/
|
|-- modulos/
|   |-- modulo_01_recolha.py           # Recolha via APIs
|   |-- modulo_02_preprocessamento.py  # Pre-processamento + SHA-256
|   |-- modulo_03a_bert.py             # Classificador BERTimbau
|   |-- modulo_03b_lstm.py             # Classificador Bi-LSTM
|   |-- modulo_04_pipeline.py          # Pipeline principal + Power BI
|   `-- modulo_05_avaliacao.py         # Metricas + curvas ROC
|
|-- powerbi/
|   |-- dax_medidas.md                 # Medidas DAX para Power BI
|   `-- power_automate_flow.md         # Configuracao alertas automaticos
|
|-- dados/
|   `-- schema_mongodb.json            # Schema MongoDB
|
|-- logs/                              # Criada automaticamente
|-- modelos/                           # Modelos treinados (criada automaticamente)
|-- requirements.txt
|-- .env.exemplo
`-- README.md
```

---

## Instalacao no Windows

### 1. Instalar Python 3.11
Descarregar de https://www.python.org/downloads/
Marcar a opcao **"Add Python to PATH"** durante a instalacao.

### 2. Clonar o repositorio
```cmd
git clone https://github.com/manuelmuinga/dissertacao-uan-angola.git
cd dissertacao-uan-angola
```

### 3. Instalar dependencias
```cmd
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
```

### 4. Instalar PyTorch (CPU — sem GPU)
```cmd
pip install torch torchvision torchaudio
```

### 4b. Instalar PyTorch com GPU NVIDIA (opcional)
```cmd
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```
Requer: CUDA Toolkit 11.8 — https://developer.nvidia.com/cuda-11-8-0-download-archive

### 5. Configurar variaveis de ambiente
Criar ficheiro `.env` na raiz do projecto:
```
TWITTER_BEARER_TOKEN=seu_token_aqui
FACEBOOK_ACCESS_TOKEN=seu_token_aqui
TELEGRAM_BOT_TOKEN=seu_token_aqui
MONGODB_URI=mongodb://localhost:27017
POWER_AUTOMATE_WEBHOOK=https://prod-xx.westeurope.logic.azure.com/...
SQL_SERVER_CONN=DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost;DATABASE=AmeacasAngola_DW;Trusted_Connection=yes;
```

### 6. Iniciar MongoDB no Windows
```cmd
net start MongoDB
```
Ou: Servicos do Windows (services.msc) > MongoDB Server > Iniciar

### 7. Executar o pipeline
```cmd
python modulos/modulo_04_pipeline.py
```

### 8. Executar em segundo plano (sem janela CMD)
```cmd
pythonw modulos/modulo_04_pipeline.py
```

### 9. Instalar como Servico Windows (NSSM)
Descarregar NSSM de https://nssm.cc/download
```cmd
nssm install PipelineAngola "C:\Python311\python.exe" "C:\projecto\modulos\modulo_04_pipeline.py"
nssm start PipelineAngola
```

---

## Configuracao do Dashboard Power BI

1. Instalar Power BI Desktop: https://powerbi.microsoft.com/pt-pt/
2. Ligar ao SQL Server local (factos_ameacas + dimensoes)
3. Importar o ficheiro `powerbi/dax_medidas.md` e criar as medidas
4. Configurar Power Automate para alertas automaticos
5. Publicar no Power BI Service para acesso via browser/telemovel

---

## Arquitetura do Sistema (Windows)

```
Redes Sociais (Facebook, Twitter/X, Telegram, Web)
        |
        v
[Modulo 1: Recolha via APIs] -- Windows Service (NSSM)
        |
        v
[Modulo 2: Pre-processamento + SHA-256] -- Python 3.11
        |
        v
[Modulo 3: Classificacao BERT / Bi-LSTM] -- PyTorch / TensorFlow
        |  (confianca > 0,75)
        v
[Kafka (WSL2/Docker) + Spark] -- Pipeline em Tempo Real
        |
        |---> MongoDB 7.0 (Windows Service)
        |---> SQL Server Express 2022 (Data Warehouse)
        `---> Power BI Desktop + Power Automate (Alertas)
```

---

## Citacao

```bibtex
@mastersthesis{muinga2026,
  author  = {Muinga, Manuel},
  title   = {Monitoramento Inteligente de Ameacas em Redes Sociais em Angola
             para o Apoio a Defesa e Seguranca Nacional},
  school  = {Universidade Agostinho Neto, Faculdade de Engenharia},
  year    = {2026},
  address = {Luanda, Angola},
  url     = {https://github.com/manuelmuinga/dissertacao-uan-angola}
}
```

---

## Licenca

(c) 2026 Manuel Muinga -- Universidade Agostinho Neto.
Codigo disponivel para fins academicos com citacao obrigatoria da fonte.
