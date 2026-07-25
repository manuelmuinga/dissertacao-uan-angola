# Guia Completo Power BI — Dissertação UAN 2026

## Arquitectura de dados

```
SQL Server Express (Windows 11 local)
└── AmeacasAngola_DW
    ├── factos_ameacas          ← tabela central (modelo estrela)
    ├── dim_categoria           ← Normal | Desinformacao | Odio | Mobilizacao
    ├── dim_plataforma          ← facebook | twitter | telegram | web | youtube
    ├── dim_provincia           ← 18 provincias angolanas + GPS
    ├── dim_tempo               ← ano, mes, dia, hora, semana
    └── vw_ameacas_completo     ← vista unificada (usar no Power BI)

MongoDB Atlas
└── dissertacao_angola
    ├── publicacoes_brutas      ← dados OSINT brutos
    ├── publicacoes_classificadas ← resultados BERT
    └── logs_scrapers           ← métricas de cada ciclo
```

---

## PASSO 1 — Instalar SQL Server Express (Windows 11)

1. **Descarregar:** https://www.microsoft.com/pt-pt/sql-server/sql-server-downloads
   → Escolher **Express** (gratuito, até 10 GB)

2. **Instalar SSMS:** https://aka.ms/ssmsfullsetup

3. **Ligar ao SSMS:**
   - Servidor: `localhost\SQLEXPRESS`
   - Autenticação: Windows Authentication

4. **Executar script:** abrir `dados/criar_data_warehouse.sql` → F5

5. **Verificar:**
   ```sql
   USE AmeacasAngola_DW;
   SELECT COUNT(*) FROM dim_provincia;  -- deve retornar 18
   SELECT * FROM vw_ameacas_completo;   -- vista de teste
   ```

---

## PASSO 2 — Instalar ODBC Driver 18

**Necessário para:** Power BI + Python (pyodbc)

https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server

Verificar instalação:
```python
import pyodbc
print([x for x in pyodbc.drivers() if 'SQL Server' in x])
# Deve aparecer: ['ODBC Driver 18 for SQL Server']
```

---

## PASSO 3 — Ligar Power BI ao SQL Server Express

1. Abrir **Power BI Desktop**
2. **Obter Dados → SQL Server**
3. Preencher:
   - **Servidor:** `localhost\SQLEXPRESS`
   - **Base de dados:** `AmeacasAngola_DW`
   - **Modo:** Importar
4. Seleccionar: `vw_ameacas_completo`
5. **Carregar**

---

## PASSO 4 — Alternativa: importar CSVs directamente

Se o SQL Server não estiver disponível, usar os CSVs da pasta `powerbi/dados/`:

| Ficheiro | Conteúdo | Usar para |
|----------|----------|-----------|
| `metricas_modelos.csv` | Tabela 4.1 completa | Página 3 — Comparação de Modelos |
| `ameacas_por_plataforma.csv` | Corpus Tabela 3.1 | Gráfico barras plataformas |
| `ameacas_por_provincia.csv` | 18 províncias + GPS | Mapa coroplético |
| `alertas_temporais.csv` | Jan 2024–Ago 2025 | Séries temporais |
| `kpis_sistema.csv` | Todos os KPIs | Cartões e medidas |

Importar: **Obter Dados → Texto/CSV** → seleccionar ficheiro

---

## PASSO 5 — Criar as Medidas DAX

Ver ficheiro `powerbi/dax_medidas.md` para todas as medidas organizadas por:
- KPIs principais
- Hipótese H1 (modelos IA)
- Hipótese H2 (tempo de deteção)
- Hipótese H3 (antecedência alertas)
- Análise por categoria e plataforma
- Análise temporal

---

## PASSO 6 — Construir as 3 Páginas do Dashboard

### 📍 Página 1 — Centro de Comando
**Visuais:**
- **Mapa preenchido** (Azure Maps) → Localização: `Provincia`, Valores: `Total_Ameacas`
- **4 Cartões KPI:** F1=91% | Tempo=47s | Antecedência=76h | Total Alertas
- **Gráfico barras** → X: `Categoria`, Y: COUNT
- **Tabela alertas** → filtro: `Alerta_Emitido = 1`, ordenar por `Data` desc
- **Segmentador** → `Plataforma` e `Período`

### 📈 Página 2 — Análise Histórica
**Visuais:**
- **Gráfico linhas** → X: `Data`, Y: `Alertas_Mes` (por categoria)
- **Barras empilhadas** → X: `Provincia`, Y: ameaças por categoria
- **Gráfico dispersão** → X: `Horas_Antecedencia`, Y: `Confianca_BERT`
- **Segmentador ano/mês**

### 🤖 Página 3 — Comparação de Modelos (Tabela 4.1)
**Visuais:**
- **Barras agrupadas** → Modelo vs. F1 / AUC-ROC / Kappa
- **Tabela** com Precisão, Recall, F1, AUC-ROC, Kappa (todos os 4 modelos)
- **Gráfico radar** → métricas por modelo

---

## PASSO 7 — Configurar alertas via Power Automate

1. Ir a https://make.powerautomate.com
2. **Criar → Fluxo automatizado → Quando um pedido HTTP é recebido**
3. Colar schema JSON:
```json
{
  "type": "object",
  "properties": {
    "timestamp":  {"type": "string"},
    "categoria":  {"type": "string"},
    "confianca":  {"type": "number"},
    "plataforma": {"type": "string"},
    "provincia":  {"type": "string"}
  }
}
```
4. Adicionar acção: **Power BI → Adicionar linhas a um dataset de transmissão**
5. Guardar → copiar URL do webhook → `.env` como `POWER_AUTOMATE_WEBHOOK`

---

## Ligação Python → SQL Server (Windows 11)

```python
import pyodbc

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=AmeacasAngola_DW;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM factos_ameacas")
print(f"Total factos: {cursor.fetchone()[0]}")
conn.close()
```

---

*Dissertação UAN — Manuel Muinga 2026 | github.com/manuelmuinga/dissertacao-uan-angola*
