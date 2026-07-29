"""
importar_corpus_python.py
Importa corpus OSINT para MongoDB Atlas via Python (alternativa ao mongoimport)
Uso: python importar_corpus_python.py --uri mongodb+srv://...
"""
import pymongo, hashlib, re
from datetime import datetime, timezone

# Conexão local
MONGODB_URI = 'mongodb://localhost:27017'
print('✅ A usar MongoDB local.')

try:
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=8000)
    client.admin.command('ping')  # Testa a conexão
    db = client['dissertacao_angola']

    # Criação das coleções e índices
    for col_name, idxs in {
        'publicacoes_brutas':       ['id_externo','plataforma','recolhido_em'],
        'publicacoes_classificadas':['id_externo','categoria','alerta_emitido'],
        'logs_scrapers':            ['timestamp'],
    }.items():
        col = db[col_name]
        for idx in idxs:
            col.create_index(idx, unique=(idx=='id_externo'))

    client.close()
    print('✅ MongoDB local: 3 coleções + índices criados.')
except Exception as e:
    print(f'❌ Erro MongoDB local: {e}')

# ── Funções auxiliares ────────────────────────────────────────────────
PROVINCIAS = ['Luanda','Benguela','Huambo','Bié','Malanje','Huíla','Cabinda',
              'Cunene','Namibe','Zaire','Uíge','Kwanza Norte','Kwanza Sul',
              'Lunda Norte','Lunda Sul','Moxico','Cuando Cubango','Bengo']

def sha256(s):
    return hashlib.sha256(str(s).encode()).hexdigest()[:16]

def detectar_prov(t):
    return next((p for p in PROVINCIAS if p.lower() in t.lower()), 'Luanda')

def criar_pub(id_ext, texto, plataforma, url='', data=None, **extra):
    return {
        'id_externo': sha256(id_ext),
        'texto': texto.strip()[:3000],
        'plataforma': plataforma,
        'url_origem': url,
        'provincia': detectar_prov(texto),
        'data': data or datetime.now(timezone.utc).isoformat(),
        'recolhido_em': datetime.now(timezone.utc).isoformat(),
        'metodo': 'OSINT_scraper',
        'classificado': False,
        'preprocessado': False,
        **extra
    }

print('\n✅ PASSO 2 CONCLUÍDO (local)!')
