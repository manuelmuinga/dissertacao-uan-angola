# Arquitectura de Armazenamento — Dissertação UAN 2026

## Duas bases de dados (conforme diagrama)

### MongoDB Atlas — dados brutos e classificados
- URI: `mongodb+srv://...` (Colab Secrets / .env)
- Colecções: `publicacoes_brutas`, `publicacoes_classificadas`, `logs_scrapers`
- Acesso Python: `pymongo`

### SQL Server Express — Data Warehouse (Windows 11 local)
- Instalação: https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads → Express
- Script: `dados/criar_data_warehouse.sql`
- String de ligação:
  ```
  SERVER=localhost\SQLEXPRESS;DATABASE=AmeacasAngola_DW;Trusted_Connection=yes
  ```
- Vista Power BI: `vw_ameacas_completo`

## Módulo de escrita dual
`modulos/modulo_armazenamento_dual.py` escreve em ambas automaticamente.

*Dissertação UAN — Manuel Muinga 2026*
