# Scraper Telegram via t.me/s/ — Sem API, Sem Subscrição

## Contexto
O Telethon MTProto passou a ser **pago** em 2025.
Esta solução usa `https://t.me/s/{canal}` — HTML público do Telegram.

| | Telethon (anterior) | t.me/s/ (actual) |
|---|---|---|
| Custo | ❌ Pago 2025 | ✅ Gratuito |
| Conta Telegram | ❌ Obrigatória | ✅ Não necessária |
| Canais públicos | ✅ | ✅ |
| Histórico | ✅ Completo | ⚠️ Paginado |

## Como funciona
```python
import aiohttp
from bs4 import BeautifulSoup

async def raspar_canal(canal):
    url = f"https://t.me/s/{canal}"
    async with aiohttp.ClientSession() as s:
        async with s.get(url) as r:
            html = await r.text()
    soup = BeautifulSoup(html, "lxml")
    msgs = soup.select(".tgme_widget_message_text")
    return [m.get_text() for m in msgs]

# Paginação: ?before={id_mais_antigo}
```

## Canais angolanos do corpus (18)
angola24horas, angolaclareza, angolainformacao, verangola, rnaangola,
jornaldeangola, expansaoangola, novojornal_ao, angola_politica,
angola_seguranca, angola_actualidade, luanda_hoje, angola_noticias,
angola_livre, benguela_noticias, cabinda_actualidade, huambo_info, angola_diaspora

## Instalação
```bash
pip install aiohttp beautifulsoup4 lxml
```

*Dissertação UAN — Manuel Muinga 2026*
