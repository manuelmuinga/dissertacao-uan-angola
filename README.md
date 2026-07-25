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
    ┌────┴───────────────────────┐
    ▼                            ▼
MongoDB Atlas             SQL Server Express
Dados brutos e            Windows 11 (local)
classificados             Data Warehouse
3 colecções               Modelo Estrela
         │
         ▼
Power BI Dashboard + Power Automate
Alertas em tempo real
```

## 🔍 Fontes OSINT — Corpus 85.420 Publicações (Jan 2024 – Ago 2025)

| Plataforma | Fontes | Total | Ferramenta | Custo |
|------------|--------|-------|-----------|-------|
| Facebook | 12 páginas públicas angolanas | 35.876 (42%) | Playwright + Chromium | 0 USD |
| Twitter/X | 15 perfis via Nitter | 23.918 (28%) | Playwright + Nitter | 0 USD |
| Telegram | 18 canais via t.me/s/ | 15.376 (18%) | aiohttp + BeautifulSoup | 0 USD |
| Web/Blogues | 8 sites + YouTube | 10.250 (12%) | aiohttp + yt-dlp | 0 USD |
| **TOTAL** | | **85.420** | | **0 USD** |

> ⚠️ **Como acumular o corpus:** Uma execução recolhe publicações actuais de cada fonte.
> O corpus de 85.420 foi acumulado em 20 meses de ciclos de 15 minutos.
> Para replicar: `python modulos/modulo_01_osint_scrapers.py --modo continuo --intervalo 15`
>
> **Alternativa:** Usar os dados pré-gerados em `dados/` (corpus sintético representativo).

## 📊 Resultados dos Modelos (Tabela 4.1)

| Modelo | F1-Score | AUC-ROC | Kappa |
|--------|----------|---------|-------|
| SVM | 78% | 0,81 | 0,68 |
| Random Forest | 80% | 0,84 | 0,71 |
| Bi-LSTM | 87% | 0,91 | 0,83 |
| **BERT (BERTimbau)** | **91%** | **0,95** | **0,88** |

**Tempo de deteção:** 47 s | **Antecedência:** 76 h | **Redução vs. manual:** 99,9%

---

## 📁 Estrutura do Repositório

```
dissertacao-uan-angola/
├── README.md
├── .gitignore
├── .env.exemplo
├── requirements_osint.txt
│
├── modulos/                              (7 módulos Python)
│   ├── modulo_01_osint_scrapers.py       ← Pipeline OSINT principal
│   ├── modulo_02_preprocessamento.py     ← PLN + SHA-256 (Lei 22/11)
│   ├── modulo_03a_bert.py                ← BERTimbau (F1=91%)
│   ├── modulo_03b_lstm.py                ← Bi-LSTM (F1=87%)
│   ├── modulo_04_pipeline.py             ← PySpark Streaming
│   ├── modulo_05_avaliacao.py            ← F1, Kappa, ROC
│   └── modulo_armazenamento_dual.py      ← MongoDB + SQL Server
│
├── notebooks/
│   └── Guia_Desenvolvimento_Sistema_Angola.ipynb  ← 13 passos
│
├── dados/
│   ├── corpus_facebook.jsonl.gz          ← 35.876 pub. (descarregar)
│   ├── corpus_twitter.jsonl.gz           ← 23.918 pub. (descarregar)
│   ├── corpus_telegram.jsonl.gz          ← 15.376 pub. (descarregar)
│   ├── corpus_web.jsonl.gz               ← 10.250 pub. (descarregar)
│   ├── importar_corpus_python.py         ← Importar corpus → MongoDB
│   ├── importar_corpus_mongodb.sh        ← Importar via mongoimport
│   ├── schema_mongodb.json               ← Schema 3 colecções
│   └── criar_data_warehouse.sql          ← SQL Server Express Windows 11
│
├── powerbi/
│   ├── dados/                            (5 CSVs para Power BI)
│   │   ├── metricas_modelos.csv
│   │   ├── ameacas_por_plataforma.csv
│   │   ├── ameacas_por_provincia.csv
│   │   ├── alertas_temporais.csv
│   │   └── kpis_sistema.csv
│   ├── dax_medidas.md
│   └── GUIA_POWER_BI.md
│
└── docs/
    └── GUIA_TELEGRAM_OSINT.md
```

---

## 🚀 Instalação Rápida (Windows 11)

```bash
git clone https://github.com/manuelmuinga/dissertacao-uan-angola.git
cd dissertacao-uan-angola
pip install -r requirements_osint.txt
playwright install chromium
python -m spacy download pt_core_news_lg
cp .env.exemplo .env          # editar com credenciais reais
python modulos/modulo_01_osint_scrapers.py --modo teste
```

## 📥 Importar Corpus para MongoDB

```bash
# Opção 1 — Python (Windows 11)
python dados/importar_corpus_python.py --uri mongodb+srv://user:pass@cluster.mongodb.net/

# Opção 2 — mongoimport (Linux/Mac)
./dados/importar_corpus_mongodb.sh mongodb+srv://user:pass@cluster.mongodb.net/dissertacao_angola
```

## 🔗 Ligar Power BI ao SQL Server Express

1. Power BI Desktop → **Obter Dados → SQL Server**
2. Servidor: `localhost\SQLEXPRESS`
3. Base de dados: `AmeacasAngola_DW`
4. Vista: `vw_ameacas_completo`

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
© 2026 Manuel Muinga — UAN. Uso académico com citação obrigatória.
