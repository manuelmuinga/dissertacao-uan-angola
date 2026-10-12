# Sistema UAN: triagem de ameaças com revisão humana

Aplicação web do sistema descrito na dissertação *Monitoramento Inteligente de Ameaças em Redes Sociais em Angola*. O modelo BERTimbau afinado classifica publicações públicas em quatro categorias (`Normal`, `Desinformacao`, `Odio`, `Mobilizacao`) e **ordena uma fila de revisão**. O sistema **não toma decisões**: cada analista confirma ou corrige, e tudo fica registado na auditoria.

```
ficheiro de recolha (.csv/.jsonl)
      │  importar (página Lotes): anonimização (Lei 22/11) + registo do lote
      ▼
SQLite ──► classificar em segundo plano, gravando de 32 em 32 ──► fila por P(não Normal)
                                                                    │
                                    cada analista revê a sua fila (pode ser cega)
                                    amostra de controlo de itens Normal
                                                                    │
                       métricas: precisão@K, κ analista–sistema, κ entre analistas,
                       sensibilidade estimada, latência · exportação para re-treino
```

## 1. Instalação (Windows, cmd, na pasta `sistema_uan`)

```
python -m pip install -r requirements.txt
python -m pytest -q
```

Os testes (31) usam um classificador de demonstração e um BERT minúsculo criado no momento; não descarregam nada.

## 2. Configuração: ficheiro `uan.env`

Copie `uan.env.exemplo` para `uan.env` e preencha. O `uan.env` não vai para o Git.

| Variável | Por omissão | Significado |
|---|---|---|
| `UAN_MODELO` | (vazio) | Pasta do modelo. Vazio = classificador de **demonstração** (palavras-chave, não é um modelo) |
| `UAN_SEGREDO_HASH` | (vazio) | Segredo do pseudónimo dos autores. Obrigatório para importar. Não o mude depois de importar dados |
| `UAN_CHAVE_API` | (vazio) | Chave da API JSON em `/api`. Vazio = API desactivada |
| `UAN_BD` | `dados\sistema.db` | Ficheiro da base de dados |
| `UAN_MAX_LENGTH` | 256 | Igual ao `--max-length` do treino |
| `UAN_LOTE` | 32 | Tamanho do lote de inferência e do sublote de gravação |
| `UAN_DISPOSITIVO` | auto | `cpu`, `cuda` ou `auto` |
| `UAN_DIAS_CONSERVACAO` | 180 | Prazo de conservação das publicações não revistas |
| `UAN_HORAS_SESSAO` | 8 | Duração da sessão na aplicação web |
| `UAN_MAX_UPLOAD_MB` | 20 | Tamanho máximo do ficheiro importado |
| `UAN_COOKIE_SEGURO` | 0 | `1` quando o site for servido por HTTPS |

Uma variável definida com `set` no cmd prevalece sobre o ficheiro.

## 3. Arrancar

```
python uan.py servir
```

Abra **http://127.0.0.1:8000**. Na primeira vez, a aplicação pede para criar a conta do **supervisor**. O supervisor cria depois as contas dos analistas na página *Utilizadores* (também é possível pela linha de comandos: `python uan.py criar-utilizador ana --nome "Ana" --papel analista`).

Por omissão o servidor só aceita ligações do próprio computador. Para outros computadores da rede local usarem o sistema: `python uan.py servir --anfitriao 0.0.0.0` (abra a porta 8000 na firewall do Windows só para a rede interna; para uso fora de um teste, coloque o serviço atrás de HTTPS e defina `UAN_COOKIE_SEGURO=1`).

## 4. Páginas

| Página | Quem | Para quê |
|---|---|---|
| Panorama | todos | Contagens por categoria, dia, plataforma e lote; nunca por autor |
| Fila de revisão | todos | Itens sinalizados por prioridade; decisão com os botões ou as teclas `1`–`4`, `J`/`K` para mudar de item, `N` para nota |
| Amostra de controlo | todos | Itens que o modelo classificou como Normal, sorteados, sempre sem a sugestão do modelo |
| Lotes | todos (importar: supervisor) | Importar ficheiros, ver a proveniência e classificar pendentes |
| Métricas | supervisor | Precisão@K, κ analista–sistema, κ entre analistas, sensibilidade com IC 95%, latência; exportar revisões e JSON |
| Utilizadores | supervisor | Criar, desactivar, redefinir palavra-passe |
| Auditoria | supervisor | Entradas, importações, classificações, revisões, exportações e alterações |
| Definições | supervisor | Revisão cega, limpeza de conservação, cópia de segurança |

A API JSON está em `/api` (documentação em `/api/docs`), com o cabeçalho `X-Chave-API`.

## 5. Avaliação com analistas (Secção 3.9 da dissertação)

1. Importe um lote **novo**, nunca usado no treino.
2. Em *Definições*, active a **revisão cega**, para a sugestão do modelo não influenciar a decisão.
3. Em *Amostra de controlo*, sorteie 50 itens Normal (anote a semente).
4. Cada analista revê, sem falar com os outros, os primeiros 50 itens da sua fila e a amostra.
5. Em *Métricas*, descarregue o JSON. Tem a precisão@K, o κ analista–sistema, o κ entre analistas e a taxa de ameaças na amostra (com IC 95%), que estima o que a fila deixa passar.

## 6. Medir a H2 (latência)

```
python uan.py medir-latencia dados\lote_latencia.csv --repeticoes 3
```

Mede importação + anonimização + classificação numa base temporária. A classificação grava de 32 em 32 publicações, por isso o resultado inclui também o tempo até ao primeiro sublote chegar à fila. Nenhuma das medidas inclui o tempo entre a publicação original e a recolha.

## 7. Linha de comandos

```
python uan.py importar dados\comentarios.csv --plataforma YouTube --via api_oficial --descricao "lote 12"
python uan.py classificar
python uan.py fila --n 20
python uan.py metricas
python uan.py exportar dados\revisoes_para_treino.csv
python uan.py limpar --dias 180
python uan.py copia
```

Útil para tarefas agendadas no Agendador de Tarefas do Windows (por exemplo, `limpar` e `copia` uma vez por dia).

## 8. Protecção de dados e uso responsável

- **Minimização.** O ficheiro importado é apagado logo a seguir à leitura. Só ficam o texto mascarado, a plataforma, a data, o contexto público e um pseudónimo do autor.
- **Pseudónimo com segredo.** HMAC-SHA-256 com `UAN_SEGREDO_HASH`, para não ser revertido por dicionário.
- **Nomes em texto livre** não são detectados automaticamente. O analista sinaliza-os na nota; os textos exportados são revistos antes de saírem do projecto.
- **Acesso.** Contas individuais, palavras-passe com PBKDF2-SHA-256, bloqueio após 5 tentativas falhadas, sessões no servidor, protecção CSRF em todos os formulários, cabeçalhos de segurança (CSP, X-Frame-Options).
- **Conservação limitada** e **cópias de segurança** em *Definições* ou pela linha de comandos.
- **Auditoria** de todas as acções relevantes.
- **Sem perfis de autores.** Não há vistas nem pesquisas por autor.
- **Revisão humana obrigatória.** Uma convocatória para manifestação pacífica é exercício de direitos (arts. 40.º e 47.º da Constituição). No teste, a precisão do modelo em `Mobilizacao` foi cerca de 0,51 e, em conteúdo angolano, o F1-macro foi cerca de 0,53.

## 9. Re-treino com as revisões

*Métricas → Exportar revisões para treino* (ou `python uan.py exportar`) gera um CSV com `origem = revisao_sistema`, uma linha por publicação; os itens em que os analistas discordaram ficam de fora. Estes rótulos vêm de itens **escolhidos pelo modelo**, por isso entram só no treino (`split_and_balance.py --train-only-origem revisao_sistema`) e nunca no teste.

## 10. Guardar o modelo no Colab

No fim da sessão de treino, corra a célula de `colab_guardar_modelo.py`. A pasta gravada no Drive (com `config.json`, pesos e tokenizer) é a que se indica em `UAN_MODELO`.

## 11. Actualizar de uma versão anterior

A base de dados da versão 0.1 é actualizada automaticamente no primeiro arranque: as revisões existentes passam a ter `origem_fila = fila`. O painel Streamlit (`painel.py`) foi substituído pela aplicação web; `python -m uvicorn api:app` continua a funcionar e arranca a aplicação completa.
