# Guia Power BI — Ligação ao SQL Server Express (Windows 11)

## Arquitectura de dados

```
SQL Server Express (Windows 11 local)
└── AmeacasAngola_DW
    ├── factos_ameacas         ← tabela central
    ├── dim_categoria          ← dimensão categoria
    ├── dim_plataforma         ← dimensão plataforma OSINT
    ├── dim_provincia          ← 18 províncias angolanas + GPS
    ├── dim_tempo              ← dimensão tempo
    └── vw_ameacas_completo    ← vista unificada (usar no Power BI)
```

## Passo 1 — Instalar SQL Server Express (Windows 11)

1. Descarregar: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads
2. Escolher **Express** (gratuito, até 10 GB)
3. Instalar com autenticação Windows (mais simples)
4. Instalar SSMS: https://aka.ms/ssmsfullsetup
5. Abrir SSMS → ligar a `localhost\SQLEXPRESS`
6. Executar o script `dados/criar_data_warehouse.sql`

## Passo 2 — Instalar ODBC Driver 18 (Windows 11)

Necessário para Power BI e Python (pyodbc):
- https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server

## Passo 3 — Ligar Power BI ao SQL Server Express

1. Abrir **Power BI Desktop**
2. Clicar em **Obter Dados → SQL Server**
3. Preencher:
   - **Servidor:** `localhost\SQLEXPRESS`
   - **Base de dados:** `AmeacasAngola_DW`
   - **Modo de conectividade:** Importar
4. Seleccionar a vista: **`vw_ameacas_completo`**
5. Clicar em **Carregar**

## Passo 4 — Criar as Medidas DAX

Ver ficheiro `powerbi/dax_medidas.md` para todas as medidas.

Medidas principais:
```dax
-- F1-Score BERT
F1_BERT = CALCULATE(
    AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)"
)

-- Total de Ameaças
Total_Ameacas = CALCULATE(
    COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[categoria] <> "Normal"
)

-- Taxa de Antecedência >= 48h (Hipótese H3)
Taxa_H3 = DIVIDE(
    CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
              vw_ameacas_completo[horas_antecedencia] >= 48),
    CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
              vw_ameacas_completo[alerta_emitido] = 1), 0
)
```

## Passo 5 — Construir as 3 páginas do dashboard

### Página 1 — Centro de Comando
- **Mapa preenchido** → localização: `provincia`, valores: `Total_Ameacas`
- **Gráfico de barras** → X: `categoria`, Y: `COUNT(id_facto)`
- **Cartões KPI:** F1=91%, Tempo=47s, Antecedência=76h
- **Tabela** → últimas publicações com `alerta_emitido = 1`

### Página 2 — Análise Histórica
- **Gráfico de linhas** → X: `data_classificacao`, Y: alertas por dia
- **Gráfico de barras empilhadas** → X: `provincia`, Y: ameaças por categoria

### Página 3 — Comparação de Modelos (Tabela 4.1)
- **Gráfico de barras agrupadas** → modelos vs. F1-Score / AUC-ROC
- Usar ficheiro `powerbi/dados/metricas_modelos.csv`

## Passo 6 — Actualização automática

O SQL Server Express é alimentado em tempo real pelo módulo:
`modulos/modulo_armazenamento_dual.py`

Para actualizar o Power BI:
**Base de Dados → Actualizar** (manual)
ou configurar actualização agendada no Power BI Service.

---
*Dissertação UAN — Manuel Muinga 2026*
