# Arquitectura de Armazenamento

## MongoDB Atlas + SQL Server Express (Windows 11)

### MongoDB Atlas
- URI: `mongodb+srv://...` (.env)
- 3 colecções: brutas, classificadas, logs

### SQL Server Express (Windows 11 local)
- Instalação: Express (gratuito, até 10 GB)
- Script: `dados/criar_data_warehouse.sql`
- Ligação Power BI: `localhost\SQLEXPRESS` → `AmeacasAngola_DW` → `vw_ameacas_completo`

### Módulo Python
`modulos/modulo_armazenamento_dual.py`

*Dissertação UAN — Manuel Muinga 2026*
