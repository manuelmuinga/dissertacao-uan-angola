#!/bin/sh
# Gera as quatro versões da apresentação (20 e 15 minutos, com e sem notas).
set -e; cd "$(dirname "$0")"
V=/root/.claude/skills/synced/c839fb96-0e54-447b-bc7f-f0f3174d226d_45b15fb7-6316-4503-930d-730f8784abae/pptx/scripts/office/validate.py
for D in 20 15; do for N in 1 0; do
  DUR=$D NOTAS=$N node gerar.js | tail -3
  F=Apresentacao_Defesa_UAN_${D}min_$([ $N = 1 ] && echo com_notas || echo sem_notas).pptx
  if [ $D = 20 ]; then I=1,3,6,7,10,15,17,20; else I=1,3,5,6,9,14,16,19; fi
  python3 transicoes.py $F $I && python3 $V $F | tail -1
done; done
