# Guia Power BI — SQL Server Express (Windows 11)

## Passo 1 — Instalar SQL Server Express
1. https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads → **Express**
2. Instalar SSMS: https://aka.ms/ssmsfullsetup
3. Abrir SSMS → `localhost\SQLEXPRESS`
4. Executar: `dados/criar_data_warehouse.sql`

## Passo 2 — Instalar ODBC Driver 18
https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server

## Passo 3 — Ligar Power BI
1. Power BI Desktop → **Obter Dados → SQL Server**
2. Servidor: `localhost\SQLEXPRESS`
3. Base de dados: `AmeacasAngola_DW`
4. Seleccionar: `vw_ameacas_completo`
5. **Carregar**

## Passo 4 — Alternativa: importar CSVs
Se o SQL Server não estiver disponível, importar directamente:
- `powerbi/dados/metricas_modelos.csv`
- `powerbi/dados/ameacas_por_plataforma.csv`
- `powerbi/dados/ameacas_por_provincia.csv`
- `powerbi/dados/alertas_temporais.csv`
- `powerbi/dados/kpis_sistema.csv`

## Passo 5 — Criar medidas DAX
Ver `powerbi/dax_medidas.md`

## Passo 6 — 3 Páginas do Dashboard
- **Pág. 1 — Centro de Comando:** mapa 18 províncias + alertas tempo real
- **Pág. 2 — Análise Histórica:** séries temporais por plataforma
- **Pág. 3 — Comparação Modelos:** Tabela 4.1 dissertação

*Dissertação UAN — Manuel Muinga 2026*
