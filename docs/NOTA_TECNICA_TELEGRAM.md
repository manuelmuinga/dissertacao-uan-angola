# Nota Técnica — Substituição Telethon → t.me/s/

## Contexto
O Telethon MTProto passou a exigir subscrição paga pelo Telegram em 2025.

## Solução adoptada
Scraper `t.me/s/{canal}` — endpoint HTML público do Telegram.

| | Telethon (anterior) | t.me/s/ (actual) |
|---|---|---|
| Custo | ❌ Pago desde 2025 | ✅ Gratuito |
| Conta Telegram | ❌ Obrigatória | ✅ Não necessária |
| Canais públicos | ✅ | ✅ |
| Canais privados | ✅ | ❌ |

## Impacto na secção 3.4 da dissertação
A Tabela 3.2 foi actualizada: Telegram usa `aiohttp + BeautifulSoup` via `t.me/s/`.
A arquitectura OSINT permanece 100% gratuita.

## Código
Ver `modulos/modulo_telegram_osint.py`

*Dissertação UAN — Manuel Muinga 2026*
