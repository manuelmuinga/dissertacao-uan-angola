#!/bin/bash
# =============================================================
# importar_corpus_mongodb.sh
# Importa o corpus OSINT da dissertação UAN 2026 para MongoDB
# =============================================================
# Requisitos:
#   pip install pymongo[srv]
#   mongoimport (incluído no MongoDB Database Tools)
#
# Uso:
#   chmod +x importar_corpus_mongodb.sh
#   ./importar_corpus_mongodb.sh mongodb+srv://user:pass@cluster.mongodb.net/dissertacao_angola
# =============================================================

MONGODB_URI="${1:-mongodb://localhost:27017/dissertacao_angola}"
DB="dissertacao_angola"
COL="publicacoes_brutas"

echo "=================================================="
echo "Importação do Corpus OSINT — Dissertação UAN 2026"
echo "URI: $MONGODB_URI"
echo "=================================================="

for plat in facebook twitter telegram web; do
    ficheiro="corpus_${plat}.jsonl.gz"
    if [ -f "$ficheiro" ]; then
        echo -n "  A importar $ficheiro..."
        # Descomprimir e importar
        zcat "$ficheiro" | mongoimport \
            --uri "$MONGODB_URI" \
            --collection "$COL" \
            --mode upsert \
            --upsertFields id_externo \
            --numInsertionWorkers 4
        echo " ✓"
    else
        echo "  AVISO: $ficheiro não encontrado"
    fi
done

echo ""
echo "Importação concluída!"
echo "Total esperado: 85.420 publicações"
echo "Verificar: mongo $DB --eval \"db.$COL.countDocuments()\""
