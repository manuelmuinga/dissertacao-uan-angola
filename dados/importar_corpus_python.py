"""
importar_corpus_python.py
Importa corpus OSINT para MongoDB Atlas via Python (alternativa ao mongoimport)
Uso: python importar_corpus_python.py --uri mongodb+srv://...
"""
import gzip, json, pymongo, argparse, os
from pathlib import Path

def importar(uri="mongodb://localhost:27017"):
    client  = pymongo.MongoClient(uri, serverSelectionTimeoutMS=10000)
    client.admin.command("ping")
    col     = client["dissertacao_angola"]["publicacoes_brutas"]
    col.create_index("id_externo", unique=True)
    print(f"MongoDB ligado: {uri[:40]}...")

    total = 0
    for plat in ["facebook","twitter","telegram","web"]:
        fich = Path(__file__).parent / f"corpus_{plat}.jsonl.gz"
        if not fich.exists():
            print(f"  AVISO: {fich.name} não encontrado"); continue
        batch, inseridos = [], 0
        with gzip.open(fich, "rt", encoding="utf-8") as f:
            for linha in f:
                if not linha.strip(): continue
                batch.append(json.loads(linha))
                if len(batch) >= 500:
                    for pub in batch:
                        try:
                            col.update_one({"id_externo":pub["id_externo"]},
                                           {"$setOnInsert":pub}, upsert=True)
                            inseridos += 1
                        except Exception: pass
                    batch = []
        for pub in batch:
            try:
                col.update_one({"id_externo":pub["id_externo"]},
                               {"$setOnInsert":pub}, upsert=True)
                inseridos += 1
            except Exception: pass
        print(f"  [{plat}]: {inseridos:,} inseridas")
        total += inseridos

    print(f"\nTotal inserido: {total:,} publicações")
    print(f"Total MongoDB:  {col.count_documents({}):,} publicações")
    client.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uri", default="mongodb://localhost:27017",
                        help="URI MongoDB Atlas ou local")
    args = parser.parse_args()
    importar(args.uri)
