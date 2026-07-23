# Medidas DAX — Dashboard Power BI
## Dissertação UAN — Manuel Muinga 2026

### KPIs Principais

```dax
-- F1-Score BERT (Tabela 4.1)
F1_Score_BERT =
CALCULATE(
    AVERAGE(metricas_modelos[f1]),
    metricas_modelos[Modelo] = "BERT"
)

-- Total de Ameaças Detectadas
Total_Ameacas =
CALCULATE(
    COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[categoria] <> "Normal"
)

-- Tempo Médio de Deteção (segundos)
Tempo_Medio_Detecao =
AVERAGE(vw_ameacas_completo[segundos_detecao])

-- Antecedência Média (horas) — Hipótese H3
Antecedencia_Media =
AVERAGE(vw_ameacas_completo[horas_antecedencia])

-- Verificação H3: % alertas com >= 48h antecedência
Taxa_Antecedencia_48h =
DIVIDE(
    CALCULATE(
        COUNT(vw_ameacas_completo[id_facto]),
        vw_ameacas_completo[horas_antecedencia] >= 48,
        vw_ameacas_completo[alerta_emitido] = 1
    ),
    CALCULATE(
        COUNT(vw_ameacas_completo[id_facto]),
        vw_ameacas_completo[alerta_emitido] = 1
    ), 0
)

-- Redução vs. Monitoramento Manual (%) — Hipótese H2
Reducao_Tempo =
VAR Manual_seg = 86400
VAR Sistema_seg = [Tempo_Medio_Detecao]
RETURN DIVIDE(Manual_seg - Sistema_seg, Manual_seg, 0) * 100

-- Total de Alertas Power BI
Total_Alertas =
CALCULATE(
    COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[alerta_emitido] = 1
)

-- Ameaças por Provincia (para mapa)
Ameacas_Provincia =
CALCULATE(
    COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[categoria] <> "Normal"
)

-- Confiança Média BERT
Confianca_Media_BERT =
CALCULATE(
    AVERAGE(vw_ameacas_completo[confianca]),
    vw_ameacas_completo[categoria] <> "Normal"
)

-- Nível de Risco (semáforo)
Nivel_Risco =
VAR pct = DIVIDE([Total_Ameacas],
                 COUNT(vw_ameacas_completo[id_facto]), 0)
RETURN
    IF(pct >= 0.4, "ALTO 🔴",
    IF(pct >= 0.2, "MÉDIO 🟡", "BAIXO 🟢"))
```

### Medidas para gráficos

```dax
-- Ameaças por Categoria (gráfico de barras)
Ameacas_Desinformacao =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Desinformacao")

Ameacas_Odio =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Discurso de Odio")

Ameacas_Mobilizacao =
CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Mobilizacao Hostil")

-- Evolução temporal (gráfico de linhas)
Alertas_Diarios =
CALCULATE(
    [Total_Alertas],
    USERELATIONSHIP(vw_ameacas_completo[data_classificacao],
                    dim_tempo[data])
)
```
