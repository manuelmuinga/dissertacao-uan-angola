# Como obter API ID e API Hash do Telegram (Telethon MTProto)

## Porquê Telethon em vez do Bot Token?

| Característica | Bot Token | Telethon MTProto |
|---|---|---|
| Acesso a canais | Só se o bot for admin | Qualquer canal público |
| Histórico de mensagens | Apenas novas | Histórico completo |
| Necessidade de admin | Sim | Não |
| Complexidade | Baixa | Média |
| Adequação ao OSINT | Limitada | ✅ Ideal |

---

## Passo a passo para obter API ID e API Hash

### 1. Aceder ao portal de developers Telegram
Ir a: **https://my.telegram.org/auth**

### 2. Fazer login com o número de telefone
- Introduzir o número no formato internacional: `+244 9XX XXX XXX`
- Telegram envia um código de verificação para a app Telegram
- Introduzir o código recebido

### 3. Criar uma aplicação
- Clicar em **API development tools**
- Clicar em **Create new application**
- Preencher os campos:
  - App title: `MonitoramentoAngola`
  - Short name: `angola_osint`
  - Platform: **Desktop**
  - Description: `OSINT research tool for master thesis at UAN Angola`

### 4. Copiar as credenciais
Após criar, aparecem:
```
App api_id:   12345678          ← este é o API_ID
App api_hash: abc123def456...   ← este é o API_HASH
```

### 5. Guardar no ficheiro .env
```
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abc123def456...
```

### 6. Primeira execução — autenticação
Na primeira vez que o Telethon for executado, pede autenticação:
```
python modulo_01_osint_scrapers.py --modo ciclo
```
Vai aparecer:
```
Please enter your phone (or bot token): +244 9XX XXX XXX
Please enter the code you received: 12345
```
Após autenticação, é criado o ficheiro `sessao_osint_angola.session`
que guarda a sessão para execuções futuras (não é necessário autenticar de novo).

### 7. Verificar que funciona
```python
from telethon import TelegramClient

async def teste():
    client = TelegramClient('teste', API_ID, API_HASH)
    await client.start()
    canal = await client.get_entity('@angola_noticias')
    print(f"Canal: {canal.title} — {canal.participants_count} membros")
    await client.disconnect()

import asyncio
asyncio.run(teste())
```

---

## Nota legal e ética
- O Telethon acede ao Telegram como utilizador registado, tal como a app oficial
- Apenas recolher mensagens de canais **públicos** (sem privacidade de membros)
- Em conformidade com os Termos de Serviço do Telegram para investigação académica
- Todos os identificadores de utilizadores são anonimizados por SHA-256 (Lei 22/11 Angola)

---

*Dissertação UAN — Manuel Muinga 2026 | github.com/manuelmuinga/dissertacao-uan-angola*
