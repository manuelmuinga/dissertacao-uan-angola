# 🛡️ Monitoramento Inteligente de Ameaças em Redes Sociais em Angola

**Dissertação de Mestrado — Universidade Agostinho Neto (UAN)**  
**Faculdade de Engenharia — Engenharia Informática e Ciência de Dados**  
**Autor:** Manuel Muinga | **Ano:** 2026 | **SO:** Windows 11 (64-bit)

---

## 📐 Arquitectura do Sistema

```
CAMADA 1 — INGESTÃO EM TEMPO REAL
Google Colab + PySpark Streaming
Kafka Producer → Kafka Consumer
         │
         ▼
CAMADA 2 — PROCESSAMENTO DISTRIBUÍDO
PySpark (Spark Structured Streaming)
~1.000.000 pub./hora | PLN + BERT/LSTM
         │
    ┌────┴──────────────────────┐
    ▼                           ▼
MongoDB Atlas            SQL Server Express
Dados brutos e           Windows 11 (local)
classificados            Data Warehouse
3 colecções              Modelo Estrela
         │
         ▼
Power BI Dashboard + Power Automate
Alertas em tempo real
```

## 🔍 Fontes OSINT — 85.420 Publicações (Jan 2024 – Ago 2025)

| Plataforma | Fontes | Total | Ferramenta OSINT | Custo |
|------------|--------|-------|-----------------|-------|
| Facebook | 12 páginas públicas angolanas | 35.876 | Playwright + Chromium | 0 USD |
| Twitter/X | 15 perfis via Nitter | 23.918 | Playwright + Nitter | 0 USD |
| Telegram | 18 canais via t.me/s/ | 15.376 | aiohttp + BeautifulSoup | 0 USD |
| Web/Blogues | 8 sites + YouTube | 10.250 | aiohttp + yt-dlp | 0 USD |
| **TOTAL** | | **85.420** | | **0 USD** |

> ⚠️ O corpus de 85.420 publicações foi acumulado em **20 meses** de recolha contínua  
> (ciclos de 15 minutos). Uma única execução recolhe as publicações actuais de cada fonte.  
> Para acumular: `python modulos/modulo_01_osint_scrapers.py --modo continuo --intervalo 15`

## 📊 Resultados dos Modelos

| Modelo | F1-Score | AUC-ROC | Kappa |
|--------|----------|---------|-------|
| SVM | 78% | 0,81 | 0,68 |
| Random Forest | 80% | 0,84 | 0,71 |
| Bi-LSTM | 87% | 0,91 | 0,83 |
| **BERT (BERTimbau)** | **91%** | **0,95** | **0,88** |

**Tempo médio de deteção:** 47 s | **Antecedência:** 76 h | **Redução vs. manual:** 99,9%

---

## 📁 Estrutura do Repositório

```
dissertacao-uan-angola/
├── README.md
├── .gitignore
├── .env.exemplo                         ← Credenciais (template)
├── requirements_osint.txt               ← Todas as dependências
│
├── modulos/
│   ├── modulo_01_osint_scrapers.py      ← Pipeline OSINT (orquestrador)
│   ├── modulo_telegram_osint.py         ← Telegram t.me/s/ (sem API)
│   ├── modulo_02_preprocessamento.py    ← PLN + SHA-256 (Lei 22/11)
│   ├── modulo_03a_bert.py               ← BERTimbau fine-tuning (F1=91%)
│   ├── modulo_03b_lstm.py               ← Bi-LSTM (F1=87%)
│   ├── modulo_04_pipeline.py            ← PySpark Structured Streaming
│   ├── modulo_05_avaliacao.py           ← F1, Kappa, ROC, matrizes
│   └── modulo_armazenamento_dual.py     ← MongoDB Atlas + SQL Server Express
│
├── notebooks/
│   ├── Guia_Desenvolvimento_Sistema_Angola.ipynb   ← 13 passos completos
│   └── MonitoramentoAmeacas_Angola_Pipeline.ipynb  ← Pipeline PySpark
│
├── dados/
│   ├── schema_mongodb.json              ← Schema das 3 colecções
│   └── criar_data_warehouse.sql         ← SQL Server Express Windows 11
│
├── powerbi/
│   ├── dados/
│   │   ├── metricas_modelos.csv         ← BERT 91%, Bi-LSTM 87%...
│   │   ├── ameacas_por_plataforma.csv   ← Distribuição por plataforma
│   │   ├── ameacas_por_provincia.csv    ← 18 províncias + GPS
│   │   ├── alertas_temporais.csv        ← Histórico de alertas
│   │   └── kpis_sistema.csv             ← KPIs estratégicos
│   ├── dax_medidas.md                   ← Medidas DAX
│   └── GUIA_POWER_BI.md                 ← Ligação SQL Server + Power BI
│
└── docs/
    ├── GUIA_TELEGRAM_OSINT.md           ← Scraper t.me/s/ sem API
    ├── ARQUITECTURA_ARMAZENAMENTO.md    ← MongoDB + SQL Server
    └── NOTA_TECNICA_TELEGRAM.md         ← Nota substituição Telethon
```

---

## 🚀 Instalação (Windows 11)

```bash
# 1. Clonar
git clone https://github.com/manuelmuinga/dissertacao-uan-angola.git
cd dissertacao-uan-angola

# 2. Dependências
pip install -r requirements_osint.txt
playwright install chromium
python -m spacy download pt_core_news_lg

# 3. Configurar bases de dados
#    MongoDB Atlas: https://www.mongodb.com/cloud/atlas/register
#    SQL Server Express: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads
#    Executar: dados/criar_data_warehouse.sql no SSMS

# 4. Variáveis de ambiente
cp .env.exemplo .env   # editar com credenciais reais

# 5. Verificar
python modulos/modulo_01_osint_scrapers.py --modo teste

# 6. Executar pipeline (ciclo único)
python modulos/modulo_01_osint_scrapers.py --modo ciclo

# 7. Modo contínuo (acumula corpus como na dissertação)
python modulos/modulo_01_osint_scrapers.py --modo continuo --intervalo 15
```

## 🔗 Ligação Power BI ao SQL Server Express (Windows 11)

1. Power BI Desktop → **Obter Dados → SQL Server**
2. Servidor: `localhost\SQLEXPRESS`
3. Base de dados: `AmeacasAngola_DW`
4. Vista: `vw_ameacas_completo`
5. Importar medidas DAX de `powerbi/dax_medidas.md`

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

© 2026 Manuel Muinga — Universidade Agostinho Neto. Uso académico com citação obrigatória.
