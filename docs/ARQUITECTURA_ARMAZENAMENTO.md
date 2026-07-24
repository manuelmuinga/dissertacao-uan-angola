# Arquitectura de Armazenamento — Dissertação UAN 2026

## Diagrama (conforme dissertação)

```
CAMADA 1 — INGESTÃO EM TEMPO REAL
Google Colab + PySpark Streaming
Kafka Producer → Kafka Consumer
         │
         ▼
CAMADA 2 — PROCESSAMENTO DIST.
PySpark (Spark Structured Streaming)
milhões pub./hora
Pré-processamento + BERT/LSTM
         │
    ┌────┴────────────────────────┐
    ▼                             ▼
MongoDB Atlas              SQL Server Express
Dados brutos               (Windows 11 local)
e classificados            Data Warehouse
                           Modelo Estrela
         │
         ▼
Power BI Dashboard + Power Automate
Alertas em tempo real
```

## MongoDB Atlas
- **Função:** dados brutos OSINT + dados classificados pelo BERT
- **Colecções:** `publicacoes_brutas`, `publicacoes_classificadas`, `logs_scrapers`
- **Acesso:** via `pymongo` + URI SRV

## SQL Server Express (Windows 11 — local)
- **Função:** Data Warehouse com modelo estrela para Power BI
- **Tabelas:** `factos_ameacas` + `dim_tempo` + `dim_categoria` + `dim_plataforma` + `dim_provincia`
- **Vista:** `vw_ameacas_completo` (usada directamente no Power BI)
- **Instalação:** https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads → Express
- **Script:** `dados/criar_data_warehouse.sql`
- **Ligação Power BI:** Obter Dados → SQL Server → `localhost\SQLEXPRESS` → `AmeacasAngola_DW`

## Ligar Power BI ao SQL Server Express (Windows 11)

1. Abrir **Power BI Desktop**
2. **Obter Dados → SQL Server**
3. Servidor: `localhost\SQLEXPRESS`
4. Base de dados: `AmeacasAngola_DW`
5. Seleccionar: `vw_ameacas_completo` (vista unificada)
6. **Carregar**
7. Criar medidas DAX (ver `powerbi/dax_medidas.md`)

## String de ligação Python (pyodbc)

```python
import pyodbc
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=AmeacasAngola_DW;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
```

*Dissertação UAN — Manuel Muinga 2026*
