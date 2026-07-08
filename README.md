# 🛡️ Monitoramento Inteligente de Ameaças em Redes Sociais em Angola

**Dissertação de Mestrado — Universidade Agostinho Neto (UAN)**
**Faculdade de Engenharia — Engenharia Informática e Ciência de Dados**
**Autor:** Manuel Muinga | **Ano:** 2026

---

## 🔍 Arquitectura OSINT (Open Source Intelligence)

Esta dissertação adoptou uma arquitectura **100% OSINT** baseada em scrapers
assíncronos, eliminando a dependência de APIs pagas ou de difícil acesso.

```
Fontes abertas angolanas (sem API paga)
        │
        ▼
┌─────────────────────────────────────────────┐
│  CAMADA 1 — SCRAPERS ASSÍNCRONOS (Python)   │
│                                             │
│  Scrapy      → Sites de notícias angolanos  │
│  Playwright  → Facebook + X/Nitter públicos │
│  Telethon    → Telegram canais públicos     │
│  yt-dlp      → YouTube + TikTok            │
│  asyncio + Redis (orquestração + dedup)     │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│  CAMADA 2 — PROCESSAMENTO DISTRIBUÍDO        │
│  PySpark 3.4 · Google Colab Pro (GPU T4)    │
│  spaCy · SHA-256 · SMOTE · BERTimbau        │
└─────────────────────────────────────────────┘
        │
        ├──────────────────┐
        ▼                  ▼
┌──────────────┐  ┌──────────────────────┐
│ MongoDB Atlas │  │ SQL Server Express   │
│ Dados brutos  │  │ Data Warehouse       │
│ classificados │  │ Modelo Estrela       │
└──────────────┘  └──────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│  Power BI Desktop + Power Automate           │
│  Mapa 18 províncias · Alertas em tempo real  │
└─────────────────────────────────────────────┘
```

## 📊 Resultados

| Modelo | F1-Score | AUC-ROC | Kappa |
|--------|----------|---------|-------|
| SVM | 78% | 0,81 | 0,68 |
| Random Forest | 80% | 0,84 | 0,71 |
| Bi-LSTM | 87% | 0,91 | 0,83 |
| **BERT (BERTimbau)** | **91%** | **0,95** | **0,88** |

- ⏱️ Tempo médio de deteção: **47 segundos**
- 📡 Antecedência média de alerta: **76 horas**
- 🚫 Sem APIs pagas — arquitectura 100% OSINT

---

## 📁 Estrutura do Repositório

```
dissertacao-uan-angola/
│
├── modulos/
│   ├── modulo_01_osint_scrapers.py    ← OSINT: Scrapy+Playwright+Telethon+yt-dlp
│   ├── modulo_02_preprocessamento.py  ← PLN: limpeza, SHA-256, spaCy
│   ├── modulo_03a_bert.py             ← BERTimbau fine-tuning (F1=91%)
│   ├── modulo_03b_lstm.py             ← Bi-LSTM (F1=87%)
│   ├── modulo_04_pipeline.py          ← PySpark + MongoDB + Power BI
│   └── modulo_05_avaliacao.py         ← Métricas, ROC, matrizes confusão
│
├── notebooks/
│   ├── Guia_Desenvolvimento_Sistema_Angola.ipynb   ← 10 passos completos
│   └── MonitoramentoAmeacas_Angola_Pipeline.ipynb  ← Pipeline PySpark
│
├── powerbi/
│   ├── dados/                          ← CSVs prontos para Power BI
│   │   ├── metricas_modelos.csv
│   │   ├── ameacas_por_plataforma.csv
│   │   ├── ameacas_por_provincia.csv
│   │   ├── alertas_temporais.csv
│   │   └── kpis_sistema.csv
│   ├── dax_medidas.md                  ← Medidas DAX completas
│   └── GUIA_POWER_BI_PASSO_A_PASSO.md ← Guia completo Power BI
│
├── dados/
│   ├── schema_mongodb.json             ← Schema das 3 colecções MongoDB
│   └── criar_data_warehouse.sql        ← Script SQL Server (modelo estrela)
│
├── docs/
│   └── GUIA_TELEGRAM_TELETHON.md       ← Telethon MTProto (sem Bot Token)
│
├── graficos/
│   └── figura_4_2_matrizes_confusao.png
│
├── requirements_osint.txt              ← Dependências stack OSINT completo
├── requirements.txt                    ← Dependências gerais
├── .env.exemplo                        ← Template de configuração
├── COMO_USAR.md
└── README.md
```

---

## 🚀 Instalação Rápida (Windows + Google Colab)

### 1. Clonar o repositório
```bash
git clone https://github.com/manuelmuinga/dissertacao-uan-angola.git
cd dissertacao-uan-angola
```

### 2. Instalar dependências OSINT
```bash
pip install -r requirements_osint.txt
playwright install chromium
python -m spacy download pt_core_news_lg
```

### 3. Configurar credenciais (ficheiro .env)
```bash
cp .env.exemplo .env
# Editar .env com as credenciais reais
```

Credenciais necessárias (todas gratuitas):
- `TELEGRAM_API_ID` e `TELEGRAM_API_HASH` → https://my.telegram.org
- `MONGODB_URI` → https://www.mongodb.com/cloud/atlas (gratuito)
- `POWER_AUTOMATE_WEBHOOK` → https://make.powerautomate.com

### 4. Verificar instalação
```bash
python modulos/modulo_01_osint_scrapers.py --modo teste
```

### 5. Executar o pipeline OSINT
```bash
# Um ciclo de recolha
python modulos/modulo_01_osint_scrapers.py --modo ciclo

# Pipeline contínuo (ciclos de 30 min)
python modulos/modulo_01_osint_scrapers.py --modo continuo --intervalo 30
```

### 6. Google Colab (treino dos modelos com GPU)
Abrir: **notebooks/Guia_Desenvolvimento_Sistema_Angola.ipynb**
- Ir a `Ambiente de execução → Alterar tipo → GPU (T4)`
- Executar células por ordem (PASSO 1 → PASSO 10)

---

## 🔐 Credenciais Telegram (Telethon MTProto)

Em vez do Bot Token (que exige ser admin do canal), esta arquitectura usa
o protocolo MTProto do Telegram para aceder a **qualquer canal público**:

1. Ir a https://my.telegram.org/auth
2. Login com número de telefone
3. **API development tools → Create new application**
4. Copiar `api_id` e `api_hash` para o ficheiro `.env`

Ver guia completo: `docs/GUIA_TELEGRAM_TELETHON.md`

---

## ⚖️ Conformidade Ética e Legal

- Recolha exclusiva de conteúdo **publicamente acessível**
- Anonimização por **SHA-256** (Lei n.º 22/11 Angola)
- Delay mínimo de **2 segundos** entre pedidos (robots.txt)
- Sem acesso a comunicações privadas ou dados pessoais
- Declarações de consentimento dos anotadores (Apêndice D)

---

## 📚 Citação

```bibtex
@mastersthesis{muinga2026,
  author  = {Muinga, Manuel},
  title   = {Monitoramento Inteligente de Ameaças em Redes Sociais
             em Angola para o Apoio à Defesa e Segurança Nacional},
  school  = {Universidade Agostinho Neto, Faculdade de Engenharia},
  year    = {2026},
  address = {Luanda, Angola},
  url     = {https://github.com/manuelmuinga/dissertacao-uan-angola},
  note    = {Arquitectura OSINT: Scrapy + Playwright + Telethon + PySpark}
}
```

---

© 2026 Manuel Muinga — Universidade Agostinho Neto.
Código disponível para fins académicos com citação obrigatória da fonte.
