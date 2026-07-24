# Medidas DAX — Power BI
## Dissertação UAN — Manuel Muinga 2026
## Ligação: localhost\SQLEXPRESS → AmeacasAngola_DW → vw_ameacas_completo

```dax
-- KPI: F1-Score BERT (Tabela 4.1)
F1_BERT = CALCULATE(AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)")

-- KPI: Total de Ameaças
Total_Ameacas = CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[categoria] <> "Normal")

-- KPI: Tempo Médio de Deteção (H2)
Tempo_Medio_Detecao = AVERAGE(vw_ameacas_completo[segundos_detecao])

-- KPI: Antecedência Média (H3)
Antecedencia_Media = AVERAGE(vw_ameacas_completo[horas_antecedencia])

-- KPI: Verificação H3 (>= 48h)
Taxa_H3 = DIVIDE(
    CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
        vw_ameacas_completo[horas_antecedencia] >= 48,
        vw_ameacas_completo[alerta_emitido] = 1),
    CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
        vw_ameacas_completo[alerta_emitido] = 1), 0)

-- KPI: Redução vs. Manual (H2)
Reducao_Tempo = VAR m = 86400 VAR s = [Tempo_Medio_Detecao]
    RETURN DIVIDE(m - s, m, 0) * 100

-- KPI: Total Alertas
Total_Alertas = CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[alerta_emitido] = 1)

-- Mapa: Ameaças por Província
Ameacas_Provincia = CALCULATE(COUNT(vw_ameacas_completo[id_facto]),
    vw_ameacas_completo[categoria] <> "Normal")

-- Nível de Risco (semáforo)
Nivel_Risco = VAR p = DIVIDE([Total_Ameacas],
    COUNT(vw_ameacas_completo[id_facto]), 0)
    RETURN IF(p >= 0.4, "ALTO 🔴", IF(p >= 0.2, "MÉDIO 🟡", "BAIXO 🟢"))

-- Por categoria
Ameacas_Desinformacao = CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Desinformacao")
Ameacas_Odio = CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Discurso de Odio")
Ameacas_Mobilizacao = CALCULATE([Total_Ameacas],
    vw_ameacas_completo[categoria] = "Mobilizacao Hostil")
```
