# Scraper Telegram OSINT — t.me/s/ (Sem API, Sem Subscrição)

## O que mudou

O Telethon MTProto passou a exigir subscrição paga em 2025.
Esta solução usa o endpoint público `t.me/s/` do Telegram — **100% gratuita**.

## Comparação das abordagens

| Característica | Telethon MTProto (anterior) | t.me/s/ OSINT (actual) |
|---|---|---|
| Custo | ❌ Subscrição paga (2025) | ✅ Gratuito |
| Conta Telegram | ❌ Necessária | ✅ Não necessária |
| API ID / Hash | ❌ Necessários | ✅ Não necessários |
| Número de telefone | ❌ Necessário | ✅ Não necessário |
| Canais públicos | ✅ Sim | ✅ Sim |
| Canais privados | ✅ Sim (com conta) | ❌ Não |
| Histórico completo | ✅ Sim | ⚠️ ~100 msgs/página (paginado) |
| Instalação | `pip install telethon` | `pip install aiohttp beautifulsoup4 lxml` |

## Como funciona

O Telegram expõe todos os canais públicos numa página HTML pública:

```
https://t.me/s/{username_do_canal}
```

Esta página é renderizada pelo servidor do Telegram (sem JavaScript),
tornando-a trivial de raspar com `aiohttp` + `BeautifulSoup`.

Exemplo:
```
https://t.me/s/angola_noticias
https://t.me/s/verangola
```

## Instalação

```bash
pip install aiohttp beautifulsoup4 lxml pymongo python-dotenv
```

## Execução

```bash
# Testar canais e recolher mensagens
python modulos/modulo_telegram_osint.py

# Em Google Colab:
import asyncio
from modulo_telegram_osint import TelegramScraperOSINT, guardar_mongodb

scraper = TelegramScraperOSINT()
# Testar um canal
resultado = await scraper.testar_canal('angola_noticias')
print(resultado)

# Recolher mensagens
publicacoes = await scraper.raspar_todos_canais()
print(f'{len(publicacoes)} mensagens recolhidas')
```

## Navegação paginada

Para obter mais de 20 mensagens por canal, o scraper navega
automaticamente para páginas anteriores usando o parâmetro `?before={id}`:

```
Página 1: https://t.me/s/angola_noticias
Página 2: https://t.me/s/angola_noticias?before=450
Página 3: https://t.me/s/angola_noticias?before=430
...
```

## Limitações

- Apenas canais **públicos** com preview web activada
- Sem acesso a reacções (renderizadas client-side)
- Alguns canais podem ter o preview desactivado pelo administrador
- Imagens/vídeos disponíveis como URLs CDN (expiram ao fim de algum tempo)

## Conformidade ética e legal

- Recolha exclusiva de conteúdo **publicamente acessível** (Lei n.º 22/11 Angola)
- Anonimização de identificadores por **SHA-256**
- Delay mínimo de **2,5 segundos** entre pedidos
- Sem acesso a mensagens privadas ou dados de utilizadores

---
*Dissertação UAN — Manuel Muinga 2026 | github.com/manuelmuinga/dissertacao-uan-angola*
