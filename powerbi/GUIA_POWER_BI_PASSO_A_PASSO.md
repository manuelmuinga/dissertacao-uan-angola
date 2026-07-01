# 📊 Guia Completo — Dashboard Power BI
## Dissertação UAN — Monitoramento de Ameaças em Angola 2026
### Autor: Manuel Muinga

---

## Ficheiros de dados disponíveis

| Ficheiro | Descrição | Linhas |
|----------|-----------|--------|
| `metricas_modelos.csv` | Desempenho dos 4 modelos de ML | 4 |
| `ameacas_por_plataforma.csv` | Distribuição de ameaças por plataforma | 5 |
| `ameacas_por_provincia.csv` | Mapa das 18 províncias angolanas | 18 |
| `alertas_temporais.csv` | Histórico de alertas (série temporal) | 17 |
| `kpis_sistema.csv` | KPIs estratégicos do sistema | 13 |

---

## PASSO 1 — Abrir o Power BI Desktop

1. Descarregar Power BI Desktop em https://powerbi.microsoft.com/pt-pt/
2. Instalar e abrir o programa
3. Verás a janela de boas-vindas — fechar o painel inicial

---

## PASSO 2 — Importar metricas_modelos.csv

### Opção A: Descarregar do GitHub (recomendado)

1. Ir a:
   https://github.com/manuelmuinga/dissertacao-uan-angola/tree/main/powerbi/dados

2. Clicar em `metricas_modelos.csv`

3. Clicar no botão **"Download raw file"** (ícone de seta para baixo)

4. Guardar em `C:\dissertacao\powerbi\dados\metricas_modelos.csv`

### Opção B: Importar directamente no Power BI

1. No Power BI Desktop, clicar em **Obter Dados** (no menu inicial)
   
   OU no menu superior: **Base → Obter Dados → Texto/CSV**

2. Navegar até ao ficheiro `metricas_modelos.csv` e clicar em **Abrir**

3. Na janela de pré-visualização verificar:
   - **Delimitador:** Vírgula
   - **Detecção do tipo de dados:** Com base nas primeiras 200 linhas
   - Os dados devem mostrar 4 linhas (um por modelo)

4. Clicar em **Carregar** (ou **Transformar Dados** para editar primeiro)

### O que verás após importar:

| Modelo | Precisao | Recall | F1_Score | AUC_ROC | Kappa |
|--------|----------|--------|----------|---------|-------|
| Random Forest | 0.82 | 0.79 | 0.80 | 0.84 | 0.71 |
| SVM | 0.80 | 0.77 | 0.78 | 0.81 | 0.68 |
| Bi-LSTM | 0.86 | 0.88 | 0.87 | 0.91 | 0.83 |
| BERT (BERTimbau) | 0.90 | 0.92 | 0.91 | 0.95 | 0.88 |

---

## PASSO 3 — Importar os outros ficheiros CSV

Repetir o PASSO 2 para cada ficheiro:

| Ordem | Ficheiro | Para que serve |
|-------|----------|----------------|
| 2 | `ameacas_por_plataforma.csv` | Gráfico de barras por plataforma |
| 3 | `ameacas_por_provincia.csv` | Mapa coroplético das províncias |
| 4 | `alertas_temporais.csv` | Gráfico de série temporal |
| 5 | `kpis_sistema.csv` | Cartões KPI do relatório executivo |

---

## PASSO 4 — Criar as Medidas DAX

Após importar todos os CSVs, criar as medidas DAX.

No painel direito **Dados**, clicar com o botão direito em
`metricas_modelos` → **Nova Medida**

### Medida 1 — F1-Score BERT (KPI principal)
```dax
F1_BERT =
CALCULATE(
    AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)"
)
```

### Medida 2 — Total de Ameaças
```dax
Total_Ameacas =
CALCULATE(
    SUM(kpis_sistema[Valor]),
    kpis_sistema[Metrica] = "Total_Ameacas"
)
```

### Medida 3 — Tempo Médio de Deteção (segundos)
```dax
Tempo_Medio_Detecao_seg =
CALCULATE(
    AVERAGE(alertas_temporais[Segundos_Detecao]),
    alertas_temporais[Alerta] = 1
)
```

### Medida 4 — Taxa de Deteção com >= 48h de Antecedência (H3)
```dax
Taxa_Antecipacao_48h =
DIVIDE(
    CALCULATE(
        COUNT(alertas_temporais[Alerta]),
        alertas_temporais[Horas_Antecedencia] >= 48,
        alertas_temporais[Alerta] = 1
    ),
    CALCULATE(
        COUNT(alertas_temporais[Alerta]),
        alertas_temporais[Alerta] = 1
    ),
    0
)
```

### Medida 5 — Melhor Modelo por F1
```dax
Melhor_Modelo =
FIRSTNONBLANK(
    TOPN(1,
        metricas_modelos,
        metricas_modelos[F1_Score], DESC
    ),
    metricas_modelos[Modelo]
)
```

### Medida 6 — Redução vs. Manual (%)
```dax
Reducao_Tempo_Pct =
VAR TempoSistema = [Tempo_Medio_Detecao_seg]
VAR TempoManual  = 86400  -- 24 horas em segundos
RETURN
    DIVIDE(TempoManual - TempoSistema, TempoManual, 0) * 100
```

### Medida 7 — Total de Alertas Power BI
```dax
Total_Alertas_PowerBI =
CALCULATE(
    COUNT(alertas_temporais[Alerta]),
    alertas_temporais[Alerta] = 1
)
```

### Medida 8 — Ameaças por Província (para mapa)
```dax
Ameacas_Provincia =
SUM(ameacas_por_provincia[Total_Ameacas])
```

---

## PASSO 5 — Construir as 3 páginas do dashboard

### Página 1 — Centro de Comando

**Adicionar visuais:**

1. **Cartão (Card)** — arrastar `F1_BERT` → formatar como percentagem
2. **Cartão** — arrastar `Tempo_Medio_Detecao_seg` → título "Tempo de Deteção (s)"
3. **Cartão** — arrastar `Total_Alertas_PowerBI` → título "Alertas Emitidos"
4. **Cartão** — arrastar `Taxa_Antecipacao_48h` → "H3: Antecedência ≥ 48h"
5. **Gráfico de barras** — eixo X: `Plataforma`, eixo Y: `Total_Ameacas`
   → Usar tabela `ameacas_por_plataforma`
6. **Mapa preenchido (Choropleth)** → localização: `Provincia`, valores: `Ameacas_Provincia`
   → Usar tabela `ameacas_por_provincia` (latitude + longitude já incluídos)
7. **Segmentação (Slicer)** → campo `Categoria` para filtrar o dashboard

### Página 2 — Análise Histórica

1. **Gráfico de linhas** — eixo X: `Data`, eixo Y: `COUNT(alertas_temporais[Alerta])`
   → Série: `Plataforma` → mostra evolução temporal por plataforma
2. **Gráfico de barras empilhadas** — X: `Provincia`, Y: `Total_Ameacas`, legenda: `Categoria`
3. **Tabela** — colunas: Data, Hora, Plataforma, Categoria, Confianca, Provincia
   → Filtrado por `Alerta = 1`

### Página 3 — Comparação de Modelos (Tabela 4.1 da dissertação)

1. **Gráfico de barras agrupadas** — X: `Modelo`, Y: `F1_Score`, `AUC_ROC`
   → Usar tabela `metricas_modelos`
2. **Gráfico de radar** — categorias: Precisao, Recall, F1_Score, AUC_ROC, Kappa
   → Série: `Modelo` (compara os 4 modelos visualmente)
3. **Tabela** — todos os campos de `metricas_modelos`
   → Formatar percentagens com 1 casa decimal
4. **Cartão** — `Melhor_Modelo` → destaca "BERT (BERTimbau)"

---

## PASSO 6 — Configurar Power Automate para alertas

1. Ir a https://make.powerautomate.com/
2. **Criar fluxo** → "Fluxo de nuvem automatizado"
3. **Gatilho:** "Quando um alerta de dados é ativado (Power BI)"
4. Seleccionar o workspace e o relatório
5. Adicionar acção: **"Enviar uma notificação push"**
6. Configurar: Título = `[categoria] detetado`, Mensagem = `Confiança: [confianca]`

---

## PASSO 7 — Publicar no Power BI Service

1. No Power BI Desktop: **Ficheiro → Publicar → Publicar no Power BI**
2. Seleccionar workspace "Dissertação UAN Angola"
3. Após publicar, aceder em https://app.powerbi.com
4. Partilhar o link do dashboard com o orientador

---

## Ligação ao SQL Server (opcional — dados em tempo real)

Se tiveres o SQL Server Express configurado com o pipeline PySpark em execução:

1. Power BI Desktop → **Obter Dados → SQL Server**
2. Servidor: `localhost\SQLEXPRESS`
3. Base de dados: `AmeacasAngola_DW`
4. Seleccionar tabelas: `factos_ameacas`, `dim_categoria`, `dim_provincia`, `dim_plataforma`
5. Clicar em **Carregar**
6. O dashboard actualiza automaticamente em tempo real conforme o pipeline classifica novas publicações

---

## Resolução de problemas comuns

| Problema | Solução |
|----------|---------|
| "Não foi possível encontrar o ficheiro CSV" | Verificar se o caminho está correcto. Usar barra `/` em vez de `\` |
| Mapa não mostra as províncias | Verificar se o campo `Provincia` está definido como **Categoria de Dados: Estado/Província** |
| Medida DAX dá erro | Verificar se o nome da tabela corresponde exactamente ao importado |
| Gráfico de radar não aparece | Instalar visual: **...→ Obter mais elementos visuais → Radar Chart** |

---

*Dissertação UAN — Manuel Muinga 2026 | github.com/manuelmuinga/dissertacao-uan-angola*
