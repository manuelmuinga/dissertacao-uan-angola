# 🛡️ Monitoramento Inteligente de Ameaças em Redes Sociais em Angola

**Dissertação de Mestrado — Universidade Agostinho Neto (UAN)**
**Faculdade de Engenharia — Engenharia Informática e Ciência de Dados**
**Autor:** Manuel Muinga | **Ano:** 2026

---

## 📐 Arquitectura do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│  CAMADA 1 — INGESTÃO EM TEMPO REAL                          │
│  Google Colab + PySpark Streaming                           │
│  Kafka Producer → Kafka Consumer                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  CAMADA 2 — PROCESSAMENTO DISTRIBUÍDO                        │
│  PySpark (Spark Structured Streaming)                       │
│  ~1.000.000 pub./hora | Pré-processamento + BERT/LSTM       │
└──────────────┬───────────────────────────┬──────────────────┘
               │                           │
┌──────────────▼──────────┐   ┌────────────▼────────────────┐
│  MongoDB Atlas           │   │  SQL Server Express         │
│  Dados brutos e          │   │  (Windows 11 — local)       │
│  classificados           │   │  Data Warehouse             │
│  3 colecções             │   │  Modelo Estrela             │
└──────────────┬───────────┘   └────────────┬────────────────┘
               └──────────┬─────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│  Power BI Dashboard + Power Automate                        │
│  Mapa 18 províncias · Alertas em tempo real                 │
└─────────────────────────────────────────────────────────────┘
```

## 🔍 Fontes OSINT (100% Gratuitas — Sem APIs Pagas)

| Plataforma | Ferramenta | Método | Custo |
|------------|-----------|--------|-------|
| Sites de notícias angolanos | `aiohttp` + `BeautifulSoup` | HTTP assíncrono | 0 USD |
| Facebook (páginas públicas) | `Playwright` + Chromium | Browser headless | 0 USD |
| X/Twitter (perfis públicos) | `Playwright` + Nitter | Espelho open-source | 0 USD |
| Telegram (canais públicos) | `t.me/s/` scraper | HTML público | 0 USD |
| YouTube / TikTok | `yt-dlp` | Metadados + transcrições | 0 USD |

> ⚠️ **Telegram:** O Telethon MTProto passou a ser pago em 2025.
> Esta arquitectura usa `https://t.me/s/{canal}` — HTML público sem autenticação.

## 📊 Resultados

| Modelo | F1-Score | AUC-ROC | Kappa |
|--------|----------|---------|-------|
| SVM | 78% | 0,81 | 0,68 |
| Random Forest | 80% | 0,84 | 0,71 |
| Bi-LSTM | 87% | 0,91 | 0,83 |
| **BERT (BERTimbau)** | **91%** | **0,95** | **0,88** |

**Tempo de deteção:** 47 s · **Antecedência:** 76 h · **Corpus:** 85.420 pub.

---

## 📁 Estrutura do Repositório

```
dissertacao-uan-angola/
├── README.md
├── .gitignore
├── .env.exemplo
├── requirements_osint.txt
│
├── modulos/
│   ├── modulo_01_osint_scrapers.py      ← Pipeline OSINT principal (orquestrador)
│   ├── modulo_telegram_osint.py         ← Scraper Telegram t.me/s/ (sem API)
│   ├── modulo_02_preprocessamento.py    ← PLN + SHA-256 (Lei 22/11)
│   ├── modulo_03a_bert.py               ← BERTimbau fine-tuning (F1=91%)
│   ├── modulo_03b_lstm.py               ← Bi-LSTM (F1=87%)
│   ├── modulo_04_pipeline.py            ← PySpark Structured Streaming
│   ├── modulo_05_avaliacao.py           ← Métricas, ROC, matrizes confusão
│   └── modulo_armazenamento_dual.py     ← MongoDB Atlas + SQL Server Express
│
├── notebooks/
│   ├── Guia_Desenvolvimento_Sistema_Angola.ipynb   ← 13 passos completos
│   └── MonitoramentoAmeacas_Angola_Pipeline.ipynb  ← Pipeline PySpark
│
├── dados/
│   ├── schema_mongodb.json              ← Schema das 3 colecções MongoDB
│   └── criar_data_warehouse.sql         ← SQL Server Express Windows 11
│
├── powerbi/
│   ├── dados/
│   │   ├── metricas_modelos.csv         ← BERT 91%, Bi-LSTM 87%, RF 80%, SVM 78%
│   │   ├── ameacas_por_plataforma.csv   ← Distribuição por plataforma
│   │   ├── ameacas_por_provincia.csv    ← 18 províncias com GPS
│   │   ├── alertas_temporais.csv        ← Histórico de alertas
│   │   └── kpis_sistema.csv             ← KPIs estratégicos
│   ├── dax_medidas.md                   ← Medidas DAX para Power BI
│   └── GUIA_POWER_BI.md                 ← Ligação SQL Server + Power BI
│
└── docs/
    ├── GUIA_TELEGRAM_OSINT.md           ← Scraper t.me/s/ sem API
    ├── ARQUITECTURA_ARMAZENAMENTO.md    ← MongoDB + SQL Server
    └── NOTA_TECNICA_TELEGRAM.md         ← Nota técnica (secção 3.4)
```

---

## 🚀 Instalação Rápida (Windows 11)

### 1. Clonar o repositório
```bash
git clone https://github.com/manuelmuinga/dissertacao-uan-angola.git
cd dissertacao-uan-angola
```

### 2. Instalar dependências
```bash
pip install -r requirements_osint.txt
playwright install chromium
python -m spacy download pt_core_news_lg
```

### 3. Configurar bases de dados

**MongoDB Atlas** (gratuito — 512 MB):
- https://www.mongodb.com/cloud/atlas/register → Free (M0)
- Copiar URI para `.env`

**SQL Server Express** (gratuito — Windows 11 local):
- https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads → Express
- Instalar SSMS: https://aka.ms/ssmsfullsetup
- Executar: `dados/criar_data_warehouse.sql` no SSMS

### 4. Configurar variáveis de ambiente
```bash
cp .env.exemplo .env
# Editar .env com as credenciais reais
```

### 5. Verificar instalação
```bash
python modulos/modulo_01_osint_scrapers.py --modo teste
```

### 6. Executar pipeline OSINT
```bash
# Um ciclo de recolha
python modulos/modulo_01_osint_scrapers.py --modo ciclo

# Pipeline contínuo (ciclos de 30 min)
python modulos/modulo_01_osint_scrapers.py --modo continuo --intervalo 30
```

### 7. Ligar Power BI ao SQL Server Express
1. Power BI Desktop → **Obter Dados → SQL Server**
2. Servidor: `localhost\SQLEXPRESS`
3. Base de dados: `AmeacasAngola_DW`
4. Seleccionar vista: `vw_ameacas_completo`
5. Importar medidas DAX de `powerbi/dax_medidas.md`

### 8. Google Colab (treino com GPU T4)
- Abrir: `notebooks/Guia_Desenvolvimento_Sistema_Angola.ipynb`
- Mudar runtime: **Ambiente de execução → T4 GPU**
- Executar os 13 passos por ordem

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
  url     = {https://github.com/manuelmuinga/dissertacao-uan-angola}
}
```

© 2026 Manuel Muinga — Universidade Agostinho Neto.
