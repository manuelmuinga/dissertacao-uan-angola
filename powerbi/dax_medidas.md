# Medidas DAX — Dashboard Power BI
# Dissertação: Monitoramento Inteligente de Ameaças em redes sociais em Angola para a desefa nacional — UAN 2026
# Autor: Manuel Muinga
# GitHub: https://github.com/manuelmuinga/dissertacao-uan-angola

## Como usar
# 1. Abrir Power BI Desktop
# 2. Importar o ficheiro metricas_modelos.csv (em powerbi/dados/)
# 3. Conectar ao SQL Server (factos_ameacas + dimensões)
# 4. Criar as medidas abaixo em "Nova Medida"

---

## PÁGINA 1 — Centro de Comando

### Total de Ameaças Detetadas
```dax
Total_Ameacas =
CALCULATE(
    COUNT(factos_ameacas[id_externo]),
    NOT(factos_ameacas[categoria] = "Normal")
)
```

### Ameaças por Categoria (selecionada)
```dax
Ameacas_Categoria_Sel =
CALCULATE(
    COUNT(factos_ameacas[id_externo]),
    NOT(factos_ameacas[categoria] = "Normal"),
    ALLSELECTED(dim_categoria[categoria])
)
```

### Taxa de Deteção com >= 48 horas de Antecedência (H3)
```dax
Taxa_Antecipacao_48h =
DIVIDE(
    CALCULATE(
        COUNT(factos_ameacas[id_externo]),
        factos_ameacas[horas_antecedencia] >= 48
    ),
    CALCULATE(
        COUNT(factos_ameacas[id_externo]),
        NOT(factos_ameacas[categoria] = "Normal")
    ),
    0
)
```

### Nível de Confiança Médio (BERT)
```dax
Confianca_Media_BERT =
AVERAGE(factos_ameacas[confianca_bert])
```

### Alertas nas Últimas 24 Horas
```dax
Alertas_24h =
CALCULATE(
    COUNT(factos_ameacas[id_externo]),
    factos_ameacas[alerta_emitido] = 1,
    factos_ameacas[data_classificacao] >= NOW() - 1
)
```

### Tempo Médio de Deteção (segundos)
```dax
Tempo_Medio_Detecao_seg =
AVERAGE(factos_ameacas[segundos_para_detetar])
```

---

## PÁGINA 2 — Análise Histórica

### Evolução Semanal de Ameaças
```dax
Ameacas_Semana =
CALCULATE(
    COUNT(factos_ameacas[id_externo]),
    NOT(factos_ameacas[categoria] = "Normal"),
    DATESINPERIOD(dim_tempo[data], LASTDATE(dim_tempo[data]), -7, DAY)
)
```

### Variação vs. Semana Anterior (%)
```dax
Variacao_Semanal =
VAR SemanaAtual =
    CALCULATE(
        COUNT(factos_ameacas[id_externo]),
        NOT(factos_ameacas[categoria] = "Normal"),
        DATESINPERIOD(dim_tempo[data], LASTDATE(dim_tempo[data]), -7, DAY)
    )
VAR SemanaAnterior =
    CALCULATE(
        COUNT(factos_ameacas[id_externo]),
        NOT(factos_ameacas[categoria] = "Normal"),
        DATESINPERIOD(dim_tempo[data], LASTDATE(dim_tempo[data]) - 7, -7, DAY)
    )
RETURN
    DIVIDE(SemanaAtual - SemanaAnterior, SemanaAnterior, 0)
```

### Top Província com Mais Ameaças
```dax
Top_Provincia =
FIRSTNONBLANK(
    TOPN(1,
        SUMMARIZE(
            FILTER(factos_ameacas, factos_ameacas[categoria] <> "Normal"),
            dim_provincia[provincia],
            "Total", COUNT(factos_ameacas[id_externo])
        ),
        [Total], DESC
    ),
    dim_provincia[provincia]
)
```

---

## PÁGINA 3 — Relatório Executivo

### F1-Score BERT (KPI)
```dax
F1_BERT =
CALCULATE(
    AVERAGE(metricas_modelos[F1_Score]),
    metricas_modelos[Modelo] = "BERT (BERTimbau)"
)
```

### Taxa de Falsos Positivos
```dax
Taxa_Falsos_Positivos =
DIVIDE(
    CALCULATE(
        COUNT(factos_ameacas[id_externo]),
        factos_ameacas[alerta_emitido] = 1,
        factos_ameacas[categoria] = "Normal"
    ),
    CALCULATE(
        COUNT(factos_ameacas[id_externo]),
        factos_ameacas[alerta_emitido] = 1
    ),
    0
)
```

### Redução de Custo Estimada (USD)
```dax
Reducao_Custo_USD =
200000 - [Custo_Sistema_Anual]
-- Custo_Sistema_Anual é um parâmetro configurável (default: 146000)
```

---

## Configuração Power Automate (Alertas Automáticos)

### Fluxo de Alerta:
1. **Gatilho:** "Quando um alerta de dados é ativado no Power BI"
2. **Condição:** confianca_bert >= 0.75 AND categoria <> "Normal"
3. **Ação 1:** Enviar notificação push ao analista
4. **Ação 2:** Criar item na lista SharePoint (log de auditoria)
5. **Ação 3:** Enviar e-mail ao Gestor de Segurança (nível >= ALTO)

### Payload do webhook (do Módulo 4):
```json
{
  "timestamp": "2026-08-15T10:23:45Z",
  "tipo_alerta": "AMEACA_DETETADA",
  "nivel": "ALTO",
  "categoria": "Mobilização Hostil",
  "confianca": 0.89,
  "plataforma": "facebook",
  "provincia": "Luanda",
  "texto_resumo": "[texto anonimizado — 150 chars]"
}
```
