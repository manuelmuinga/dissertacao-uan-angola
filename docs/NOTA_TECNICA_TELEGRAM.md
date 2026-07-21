# NOTA TÉCNICA — Actualização da Arquitectura OSINT (Julho 2026)

## Alteração: Telegram MTProto → t.me/s/ Preview

### Contexto
O módulo Telethon MTProto, anteriormente documentado na secção 3.4
da dissertação, passou a exigir subscrição paga pelo Telegram em 2025.
Esta alteração foi implementada antes da submissão final.

### Solução adoptada
O sistema passa a usar o endpoint público `t.me/s/{canal}` do Telegram,
que expõe todos os canais públicos em formato HTML sem autenticação.

### Impacto na dissertação
A Tabela 3.2 (Fontes OSINT Monitoradas) é actualizada conforme abaixo.
O resto da dissertação não é afectado — a arquitectura OSINT permanece
100% gratuita e sem dependência de APIs pagas ou subscrições.

### Tabela 3.2 actualizada

| Plataforma | Ferramenta OSINT | Método | Custo |
|---|---|---|---|
| Sites de notícias | Scrapy + aiohttp | HTTP assíncrono + BeautifulSoup | Gratuito |
| Facebook (páginas públicas) | Playwright + Chromium | Browser headless stealth | Gratuito |
| X/Twitter (perfis públicos) | Playwright + Nitter | Espelho open-source | Gratuito |
| Telegram (canais públicos) | aiohttp + BeautifulSoup | t.me/s/ preview HTML | Gratuito |
| YouTube / TikTok | yt-dlp | Metadados + transcrições | Gratuito |

### Comparação Telethon vs. t.me/s/

| | Telethon MTProto | t.me/s/ Preview (actual) |
|---|---|---|
| Custo | ❌ Pago desde 2025 | ✅ Gratuito |
| Conta Telegram | ❌ Obrigatória | ✅ Não necessária |
| Canais públicos | ✅ Sim | ✅ Sim |
| Histórico completo | ✅ Sim | ⚠️ Paginado (~200 msgs) |
| Sustentabilidade | ❌ Dependente de subscrição | ✅ Totalmente sustentável |

*Dissertação UAN — Manuel Muinga 2026*
