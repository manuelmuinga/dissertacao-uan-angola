# Medidas DAX — Dashboard Power BI
## Dissertação UAN — Manuel Muinga 2026
## Ligação: localhost\SQLEXPRESS → AmeacasAngola_DW → vw_ameacas_completo

---

## 📊 KPIs Principais (cartões do dashboard)

```dax
-- Total de Publicações do Corpus
Total_Corpus = SUM(kpis_sistema[Valor])
-- ou directamente:
Total_Corpus = 85420

-- Total de Ameaças Detectadas
Total_Ameacas =
CALCULATE(
    COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[categoria] <> "Normal"
)

-- Taxa de Ameaças (%)
Taxa_Ameacas =
DIVIDE([Total_Ameacas], COUNT(vw_ameacas_completo[id_facto]), 0) * 100

-- F1-Score BERT (Tabela 4.1)
F1_BERT =
CALCULATE(
    AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)"
)

-- AUC-ROC BERT
AUC_ROC_BERT =
CALCULATE(
    AVERAGE(metricas_modelos[AUC_ROC]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)"
)

-- Kappa de Cohen (corpus)
Kappa_Corpus = 0.78
```

---

## ⏱️ Hipótese H2 — Tempo de Deteção

```dax
-- Tempo Médio de Deteção (segundos)
Tempo_Medio_Detecao =
AVERAGE(vw_ameacas_completo[segundos_detecao])

-- Tempo Médio de Deteção (minutos)
Tempo_Medio_Min =
DIVIDE([Tempo_Medio_Detecao], 60, 0)

-- Redução vs. Monitoramento Manual (H2)
-- Manual = 24h = 86400 segundos
Reducao_Tempo_H2 =
VAR manual_seg = 86400
VAR sistema_seg = [Tempo_Medio_Detecao]
RETURN DIVIDE(manual_seg - sistema_seg, manual_seg, 0) * 100
-- Resultado esperado: 99.9%

-- Verificação H2 (redução > 90%)
Verifica_H2 =
IF([Reducao_Tempo_H2] >= 90, "✅ H2 Confirmada", "❌ H2 Não confirmada")
```

---

## 🕐 Hipótese H3 — Antecedência dos Alertas

```dax
-- Antecedência Média (horas)
Antecedencia_Media =
CALCULATE(
    AVERAGE(alertas_temporais[Horas_Antecedencia]),
    alertas_temporais[Alerta_Emitido] = 1
)

-- Taxa de Alertas com >= 48h de antecedência (H3)
Taxa_Antecedencia_48h =
DIVIDE(
    CALCULATE(
        COUNT(alertas_temporais[Data]),
        alertas_temporais[Horas_Antecedencia] >= 48,
        alertas_temporais[Alerta_Emitido] = 1
    ),
    CALCULATE(
        COUNT(alertas_temporais[Data]),
        alertas_temporais[Alerta_Emitido] = 1
    ), 0
) * 100

-- Verificação H3 (antecedência >= 48h)
Verifica_H3 =
IF([Antecedencia_Media] >= 48, "✅ H3 Confirmada", "❌ H3 Não confirmada")
```

---

## 🤖 Hipótese H1 — Modelos de IA

```dax
-- Diferença F1 BERT vs. SVM (H1)
Delta_F1_BERT_SVM =
VAR f1_bert = CALCULATE(AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)")
VAR f1_svm  = CALCULATE(AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "SVM")
RETURN (f1_bert - f1_svm) * 100
-- Resultado esperado: 13 pp

-- Verificação H1 (BERT > modelos clássicos)
Verifica_H1 =
IF([Delta_F1_BERT_SVM] > 0, "✅ H1 Confirmada", "❌ H1 Não confirmada")

-- Melhor Modelo
Melhor_Modelo =
CALCULATE(
    FIRSTNONBLANK(metricas_modelos[Modelo], 1),
    TOPN(1, metricas_modelos, metricas_modelos[F1_Score], DESC)
)
```

---

## 🗺️ Mapa e Províncias

```dax
-- Ameaças por Província (mapa coroplético)
Ameacas_Provincia =
CALCULATE(
    COUNT(ameacas_por_provincia[Provincia]),
    ameacas_por_provincia[Total_Ameacas] > 0
)

-- Província com mais ameaças
Provincia_Top =
CALCULATE(
    FIRSTNONBLANK(ameacas_por_provincia[Provincia], 1),
    TOPN(1, ameacas_por_provincia, ameacas_por_provincia[Total_Ameacas], DESC)
)

-- Nível de Risco por Província (semáforo)
Nivel_Risco_Provincia =
VAR ameacas = SELECTEDVALUE(ameacas_por_provincia[Total_Ameacas])
VAR total   = SELECTEDVALUE(ameacas_por_provincia[Total_Publicacoes])
VAR taxa    = DIVIDE(ameacas, total, 0)
RETURN
    IF(taxa >= 0.40, "🔴 ALTO",
    IF(taxa >= 0.25, "🟡 MÉDIO", "🟢 BAIXO"))
```

---

## 📈 Análise Temporal

```dax
-- Alertas por Mês
Alertas_Mes =
CALCULATE(
    COUNT(alertas_temporais[Data]),
    alertas_temporais[Alerta_Emitido] = 1
)

-- Tendência (crescimento mês a mês)
Tendencia_Alertas =
VAR atual = [Alertas_Mes]
VAR anterior = CALCULATE([Alertas_Mes],
    DATEADD(alertas_temporais[Data], -1, MONTH))
RETURN DIVIDE(atual - anterior, anterior, 0) * 100

-- Total Alertas Emitidos
Total_Alertas =
CALCULATE(
    COUNT(alertas_temporais[Data]),
    alertas_temporais[Alerta_Emitido] = 1
)

-- Taxa de Confirmação de Alertas
Taxa_Confirmacao =
DIVIDE(
    CALCULATE(COUNT(alertas_temporais[Data]),
        alertas_temporais[Verificado_Real] = 1),
    [Total_Alertas], 0
) * 100
```

---

## 📋 Por Categoria e Plataforma

```dax
-- Por Categoria
Ameacas_Desinformacao =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Desinformacao")

Ameacas_Odio =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Discurso de Odio")

Ameacas_Mobilizacao =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Mobilizacao Hostil")

-- Por Plataforma
Ameacas_Facebook =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[plataforma] = "facebook")

Ameacas_Telegram =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[plataforma] = "telegram")

Ameacas_Twitter =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[plataforma] = "twitter")

-- Confiança Média BERT (apenas ameaças)
Confianca_Media =
CALCULATE(
    AVERAGE(vw_ameacas_completo[confianca]),
    vw_ameacas_completo[categoria] <> "Normal"
)
```

---

## 🏗️ Estrutura do Dashboard (3 páginas)

### Página 1 — Centro de Comando
| Visual | Campos | Filtros |
|--------|--------|---------|
| Mapa coroplético | Província, Total_Ameacas | Data, Categoria |
| Cartões KPI | F1=91%, Tempo=47s, Antecedência=76h, Alertas | — |
| Gráfico barras | Categoria, COUNT | Plataforma |
| Tabela alertas | Data, Categoria, Confiança, Província | Alerta_Emitido=1 |
| Medidor risco | Taxa_Ameacas | Tempo real |

### Página 2 — Análise Histórica
| Visual | Campos | Filtros |
|--------|--------|---------|
| Gráfico linhas | Data, Alertas_Mes | Categoria |
| Barras empilhadas | Província, Categorias | Data |
| Dispersão | Horas_Antecedencia, Confiança | Plataforma |
| Segmentação | Ano, Mês | — |

### Página 3 — Comparação de Modelos (Tabela 4.1)
| Visual | Campos | Filtros |
|--------|--------|---------|
| Barras agrupadas | Modelo, F1, AUC-ROC, Kappa | — |
| Tabela | Modelo, Precisão, Recall, F1, AUC-ROC, Kappa | — |
| Gráfico radar | Modelos vs. métricas | — |

---

## 🔗 Ligação Power BI ao SQL Server Express (Windows 11)

```
1. Power BI Desktop → Obter Dados → SQL Server
2. Servidor:      localhost\SQLEXPRESS
3. Base de dados: AmeacasAngola_DW
4. Autenticação:  Windows (Trusted Connection)
5. Tabela:        vw_ameacas_completo
```

*Dissertação UAN — Manuel Muinga 2026*
