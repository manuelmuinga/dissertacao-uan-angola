# Sistema UAN: triagem de ameaças com revisão humana

Aplicação web do sistema descrito na dissertação *Monitoramento Inteligente de Ameaças em Redes Sociais em Angola*. O modelo BERTimbau afinado classifica publicações públicas em quatro categorias (`Normal`, `Desinformacao`, `Odio`, `Mobilizacao`) e **ordena uma fila de revisão**. O sistema **não toma decisões**: cada analista confirma ou corrige, e tudo fica registado na auditoria.

```
recolha integrada                         ficheiro (.csv/.jsonl)
 · YouTube Data API (vídeos, canais)       (Facebook e outras redes
 · sítios públicos e RSS (robots.txt)       com conta: exportação)
      │                                          │
      └──────► anonimização (Lei 22/11) + registo do lote ◄──┘
                         ▼
SQLite (dados\sistema.db) ──► classificar em segundo plano, gravando de 32 em 32 ──► fila por P(não Normal)
                                                                    │
                                    cada analista revê a sua fila (pode ser cega)
                                    amostra de controlo de itens Normal
                                                                    │
            ameaça confirmada ──► alertas (aplicação + e-mail) · mapa por província · relatório
                                                                    │
                       métricas: precisão@K, κ analista–sistema, κ entre analistas,
                       sensibilidade estimada, latência · exportação para re-treino
```

## 1. Instalação (Windows, cmd, na pasta `sistema_uan`)

```
python -m pip install -r requirements.txt
python -m pytest -q
```

Os testes (121) usam um classificador de demonstração e um BERT minúsculo criado no momento; não descarregam nada.

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
| `UAN_YOUTUBE_CHAVE` | (vazio) | Chave da YouTube Data API v3 para recolher comentários de vídeos e canais. Vazio = só fontes web |
| `UAN_RECOLHA_INTERVALO` | 3 | Segundos de espera entre pedidos ao mesmo sítio |
| `UAN_RECOLHA_MAX_PAGINAS` | 40 | Máximo de páginas visitadas por fonte em cada recolha |
| `UAN_SMTP_SERVIDOR` | (vazio) | Servidor de e-mail para os alertas (por exemplo, `smtp.instituicao.ao`). Vazio = alertas só na aplicação |
| `UAN_SMTP_PORTA` | 587 | 587 com STARTTLS; 465 com SSL |
| `UAN_SMTP_UTILIZADOR` / `UAN_SMTP_SENHA` | (vazio) | Conta de envio, se o servidor exigir autenticação |
| `UAN_SMTP_REMETENTE` | (vazio) | Endereço que aparece como remetente |
| `UAN_SMTP_TLS` | 1 | `0` só para servidores internos sem cifra |
| `UAN_URL_BASE` | http://127.0.0.1:8000 | Endereço do sistema, usado nas ligações dos e-mails |
| `UAN_RECOLHA_AGENTE` | SistemaUAN-Investigacao/1.0 (…) | Identificação enviada aos sítios (User-Agent) |

Uma variável definida com `set` no cmd prevalece sobre o ficheiro. O ficheiro é lido em cada arranque do servidor (também ao mudar de modo); depois de o alterar, reinicie. Se o Bloco de Notas o gravar como `uan.env.txt`, também é lido. Para confirmar o que o sistema lê, sem mostrar os valores: `python uan.py verificar-config`.

## 3. Arrancar

```
python uan.py servir
```

Abra **http://127.0.0.1:8000**. Na primeira vez, a aplicação pede para criar a conta do **supervisor**. O supervisor cria depois as contas dos analistas na página *Utilizadores* (também é possível pela linha de comandos: `python uan.py criar-utilizador ana --nome "Ana" --papel analista`).

**Demonstração.** Para apresentar o sistema (por exemplo, na defesa) sem tocar nos dados reais:

```
python uan.py servir --demonstracao
```

Cria, na primeira vez, a base `dados\demonstracao.db` com cerca de 1 350 publicações **fictícias** em 16 semanas: conversas de três plataformas fictícias (vídeos, páginas e notícias) sobre transportes, água e luz, saúde, educação, economia, desporto e cultura, em 18 províncias, com registos formais e coloquiais, respostas entre utilizadores e casos de fronteira (convocatórias pacíficas e legais, críticas duras ao Governo). Episódios com princípio e fim (um boato de cólera em Benguela, uma paralisação com intimidação em Luanda, uma rivalidade na Huíla que acalma) dão forma ao mapa, às tendências e aos alertas. As sugestões vêm de um classificador **simulado**, que acerta e erra como um modelo real (erra mais na Desinformação), e há decisões de dois analistas. Quando o gerador muda de versão, a base de demonstração antiga é recriada sozinha. Todas as páginas mostram a faixa "Demonstração" e nenhum e-mail é enviado, mesmo com o servidor de e-mail configurado. Contas: `demo.supervisor`, `demo.analista` e `demo.revisor`, palavra-passe `demonstracao`. `--repor` apaga e recria os dados fictícios. A base real (`dados\sistema.db`) não é aberta.

**Trocar de modo sem fechar a janela.** Com o sistema aberto, um supervisor pode passar da demonstração para o sistema real (e ao contrário) no botão da faixa "Demonstração", em *Definições e aspecto → Modo do sistema* ou na paleta (`Ctrl`+`K`, "mudar"). O servidor reinicia na mesma janela com a outra base de dados e o navegador abre a página de entrada quando estiver pronto. As duas bases nunca se misturam e cada uma tem as suas contas.

**Esqueceu-se da palavra-passe?** Na página de entrada, *Esqueceu-se da palavra-passe?* abre três caminhos, todos sem e-mail nem serviços externos:

1. **Código de recuperação pessoal.** Cada pessoa gera o seu em *A minha conta → Código de recuperação* (confirma com a palavra-passe actual). O código tem 16 caracteres, aparece uma só vez, fica guardado só como hash e serve uma vez. Com ele, a pessoa muda a palavra-passe sozinha. As tentativas erradas contam para o mesmo bloqueio da entrada (5 falhas, 5 minutos).
2. **Pedido ao supervisor.** Quem não tem código envia um pedido. A resposta é sempre a mesma, exista ou não a conta. Os supervisores vêem os pedidos em *Utilizadores* (com contador no menu), confirmam a identidade da pessoa e geram uma **palavra-passe temporária**, mostrada uma só vez. Ao entrar com ela, a pessoa só pode ir a *A minha conta* até escolher uma palavra-passe sua. Uma palavra-passe que o supervisor escreva para outra conta também é temporária.
3. **Linha de comandos** (por exemplo, para o único supervisor), no computador do servidor: `python uan.py repor-senha supervisor`, que pede a nova palavra-passe, ou `python uan.py repor-senha supervisor --temporaria`, que mostra uma temporária. Os dois comandos desbloqueiam e reactivam a conta. Na base de demonstração, acrescente `--demonstracao`.

Todos os passos ficam na *Auditoria*.

**Fechar a janela termina a sessão.** Ao fechar o separador ou o navegador com o sistema aberto, o navegador pergunta se quer sair (a pergunta e o texto são do próprio navegador; aparece depois de ter usado a página, e também ao recarregar com F5). Se confirmar, o navegador avisa o servidor e, se nenhuma página do sistema voltar a abrir em 20 segundos, a sessão termina e fica na auditoria como `saida` com o motivo `janela_fechada`. Mudar de página e gravar formulários não perguntam nada. Com outro separador do sistema aberto, a sessão continua. O cookie da sessão também deixou de ter validade própria, por isso o navegador apaga-o ao fechar.

Por omissão o servidor só aceita ligações do próprio computador. Para outros computadores da rede local usarem o sistema: `python uan.py servir --anfitriao 0.0.0.0` (abra a porta 8000 na firewall do Windows só para a rede interna; para uso fora de um teste, coloque o serviço atrás de HTTPS e defina `UAN_COOKIE_SEGURO=1`).

## 4. Páginas

| Página | Quem | Para quê |
|---|---|---|
| Panorama | todos | Contagens por categoria, dia, plataforma e lote; nunca por autor |
| Fila de revisão | todos | Itens sinalizados por prioridade, com lugares e dados anonimizados realçados no texto. Decisão com os botões ou as teclas `1`–`4`, sem recarregar a página; `U` desfaz durante 5 segundos (o e-mail de um alerta só sai 8 segundos depois, para o desfazer o poder anular); `D` abre o detalhe num painel lateral; `J`/`K` mudam de item; `N` nota; `?` mostra todos os atalhos (`G` + `F`/`A`/`M`/`R`/`P`/`O` para navegar) |
| Amostra de controlo | todos | Itens que o modelo classificou como Normal, sorteados, sempre sem a sugestão do modelo |
| Fontes e recolha | supervisor | Registar fontes públicas (vídeo ou canal do YouTube, feed RSS, página ou sítio de notícias) e recolher novos dados; cada recolha cria um lote |
| Alertas | todos | Ameaças confirmadas e tendências; contador de alertas por ver no menu e no sino do topo (últimos 5); um alerta novo aparece em tempo real, sem recarregar |
| Mapa | todos | 18 províncias (divisão anterior a 2025): taxa de ameaças confirmadas (ou sinalizadas) e variação face ao período anterior. Cartão com os números ao passar o rato; clique destaca a linha da tabela; ▶ reproduz a evolução semana a semana; linhas de tendência por província; descarregar em SVG ou PNG |
| Relatório | todos (enviar por e-mail: supervisor) | Relatório de alertas de ameaças do período escolhido: indicadores com tendência, mapa, categorias, alertas e ameaças confirmadas; tabelas ordenáveis; imprimir/PDF, CSV, e-mail |
| Sobre o modelo | todos | Ficha do modelo: versão, data de treino, F1 por categoria, desempenho em conteúdo angolano, limitações e o acordo real entre analistas e modelo nesta instalação |
| Lotes | todos (importar: supervisor) | Importar ficheiros, ver a proveniência e classificar pendentes |
| Métricas | supervisor | Precisão@K, κ analista–sistema, κ entre analistas, sensibilidade com IC 95%, latência; exportar revisões e JSON |
| Utilizadores | supervisor | Criar, desactivar, redefinir palavra-passe |
| Auditoria | supervisor | Entradas, importações, classificações, revisões, exportações e alterações |
| Definições e aspecto | todos (o resto: supervisor) | **Aspecto**, por conta: tema (automático, claro, escuro), cor principal (azul, verde, vinho, petróleo, grafite), menu lateral (escuro, da cor principal, claro), tamanho da letra (pequena, normal, grande, muito grande; amplia toda a interface), densidade (compacta, normal, confortável), cores do mapa, cantos e animações, com efeito imediato. **Supervisor**: modo do sistema (real ou demonstração), revisão cega, regras e destinatários dos alertas, limpeza de conservação, cópia de segurança |

No topo de cada página: **Procurar** (`Ctrl`+`K`) abre uma paleta para ir a qualquer página ou acção (por exemplo, "rel 7" → relatório dos últimos 7 dias); o **sino** mostra os últimos alertas; o botão de **tema** alterna entre automático (segue o sistema), escuro e claro. Na primeira entrada, uma **visita guiada** percorre todo o sistema, página a página (14 passos para analistas, 18 para supervisores, com as páginas de supervisão), com barra de progresso, setas do teclado e `Esc` para sair; pode repeti-la em *Visita guiada*, no fundo do menu. No mapa, ao passar o rato numa província aparece só o cartão do sistema, sem a dica do navegador. As tabelas do mapa e do relatório ordenam-se clicando no cabeçalho.

Tudo funciona sem Internet: a interface não usa bibliotecas, tipos de letra nem ícones externos, e a política de segurança (CSP) só permite recursos do próprio servidor.

A ficha do modelo é lida de `ficha_modelo.json` na pasta do modelo (`UAN_MODELO`), se existir; caso contrário, usa a ficha de referência em `sistema\ficha_modelo.json`. Ao treinar um modelo novo, copie e actualize essa ficha para a pasta do modelo.

A API JSON está em `/api` (documentação em `/api/docs`), com o cabeçalho `X-Chave-API`.

## 5. Recolha de novos dados

Além da importação de ficheiros, o sistema recolhe ele próprio do YouTube e de sítios web públicos. Pode acrescentar **várias fontes de uma vez**: cole os endereços, um por linha, e o tipo de cada um é detectado automaticamente (a página mostra-o antes de gravar). Uma linha de texto livre passa a ser uma pesquisa no YouTube; linhas repetidas ou já registadas são ignoradas.

**Recolha automática.** Em *Fontes e recolha → Recolha automática*, o supervisor escolhe a frequência (de 15 em 15 minutos até uma vez por dia). Enquanto o servidor estiver a correr, o sistema percorre sozinho todas as fontes activas: vídeos novos dos canais, listas e pesquisas, comentários novos nos vídeos, artigos novos dos feeds e das páginas. Só entra o que ainda não existe na base de dados. Cada volta fica registada como lotes e na auditoria (`recolha_automatica`), e as publicações novas são classificadas e vão para a fila. A página mostra a última e a próxima volta e uma estimativa da quota diária do YouTube, com um aviso quando a frequência a pode esgotar (cada pesquisa gasta cerca de 110 unidades por volta; o limite habitual é 10 000 por dia). Na demonstração não há recolha. Com o servidor fechado, use o Agendador de Tarefas do Windows com `python uan.py recolher`.

| Tipo de fonte | Endereço | Como recolhe |
|---|---|---|
| `youtube_video` | ligação de um vídeo | Comentários e respostas pela YouTube Data API v3 (`UAN_YOUTUBE_CHAVE`) |
| `youtube_canal` | `https://www.youtube.com/@canal` | Vídeos mais recentes do canal e os respectivos comentários, pela API |
| `youtube_lista` | `https://www.youtube.com/playlist?list=PL…` | Vídeos da lista de reprodução e os seus comentários |
| `youtube_pesquisa` | termos de pesquisa (ex.: `greve professores Huambo`) | Vídeos mais recentes com esses termos (região Angola, português) e os seus comentários; gasta mais quota da API |
| `rss` | endereço do feed RSS/Atom | Título e resumo de cada entrada; se o resumo for curto, lê o início do artigo |
| `pagina` | ligação de um artigo | Título, data e primeiros parágrafos do artigo |
| `sitio` | página inicial ou secção de um jornal | Segue as ligações para artigos do mesmo sítio e lê cada um |

Na página **Fontes e recolha** (ou `python uan.py fonte-adicionar --endereco https://exemplo.ao/feed "greve professores" @canal`) regista as fontes; o botão **Recolher** (ou `python uan.py recolher`) recolhe todas as fontes activas, grava um lote por fonte e classifica a seguir. `python uan.py fontes` lista as fontes e o estado da última recolha. Para recolha periódica, agende `python uan.py recolher` no Agendador de Tarefas do Windows.

Regras que o código aplica e que não devem ser contornadas:

- Só conteúdo **público**. Páginas com formulário de palavra-passe, respostas 401/403 e endereços proibidos pelo `robots.txt` são ignorados.
- Sem contornar protecções: não há rotação de IP, identidades falsas nem resolução de captchas; o sistema identifica-se com `UAN_RECOLHA_AGENTE` e espera `UAN_RECOLHA_INTERVALO` segundos entre pedidos ao mesmo sítio.
- Redes que exigem conta (Facebook, Instagram, X, TikTok) não são recolhidas automaticamente; o seu conteúdo público entra por importação de ficheiro, de acordo com os termos de cada plataforma.
- Os textos passam pela mesma anonimização da importação (telefones, e-mails, @menções, pseudónimo do autor) antes de serem gravados.

## 6. Alertas, mapa e relatório

**Alertas.** Nascem só de decisões humanas:

- *Ameaça confirmada*: quando o número de analistas definido em *Definições* (1 por omissão) escolhe uma categoria de ameaça e há mais decisões de ameaça do que de Normal.
- *Tendência*: quando as ameaças confirmadas numa província (ou no país) na última janela (7 dias) chegam ao mínimo de casos (5) e crescem pelo menos 50% face à janela anterior, **e** o seu peso no total de publicações recolhidas também sobe. Assim, recolher mais, por si só, não gera alertas.

Os alertas aparecem na página *Alertas* e, com o e-mail configurado (`UAN_SMTP_*` no `uan.env` e destinatários em *Definições*), são enviados por e-mail. O e-mail **não** leva o texto da publicação nem o pseudónimo do autor: só categoria, província, data e ligação. Nunca há envio automático para terceiros. Se o servidor de e-mail falhar, o alerta fica na aplicação com o estado "falhou".

**Província.** É o lugar **mencionado** no texto ou no título (lista de topónimos: províncias, capitais e municípios), não a localização de quem escreveu. Só ao nível da província; publicações sem lugar contam como "sem localização". O mapa usa as 18 províncias com os limites de 2011 a 2024 (geoBoundaries, domínio público), anteriores à divisão que entrou em vigor em Janeiro de 2025; ver `scripts/preparar_mapa_angola.py`.

**Mapa.** A cor é a taxa de ameaças confirmadas sobre as publicações que mencionam a província; abaixo do mínimo de casos, a taxa não é calculada (tracejado). As setas ▲/▼ mostram a variação face ao período anterior com a mesma duração. Pode mudar para "sinalizadas pelo modelo", com aviso.

**Relatório.** Escolha o período (datas ou 7/30/90 dias). Imprima ou guarde em PDF pelo navegador, descarregue o CSV ou (supervisor) envie o resumo por e-mail. Pela linha de comandos: `python uan.py relatorio --dias 30 --csv dados\relatorio.csv`.

## 7. Avaliação com analistas (Secção 3.9 da dissertação)

1. Importe um lote **novo**, nunca usado no treino.
2. Em *Definições*, active a **revisão cega**, para a sugestão do modelo não influenciar a decisão.
3. Em *Amostra de controlo*, sorteie 50 itens Normal (anote a semente).
4. Cada analista revê, sem falar com os outros, os primeiros 50 itens da sua fila e a amostra.
5. Em *Métricas*, descarregue o JSON. Tem a precisão@K, o κ analista–sistema, o κ entre analistas e a taxa de ameaças na amostra (com IC 95%), que estima o que a fila deixa passar.

## 8. Medir a H2 (latência)

```
python uan.py medir-latencia dados\lote_latencia.csv --repeticoes 3
```

Mede importação + anonimização + classificação numa base temporária. A classificação grava de 32 em 32 publicações, por isso o resultado inclui também o tempo até ao primeiro sublote chegar à fila. Nenhuma das medidas inclui o tempo entre a publicação original e a recolha.

## 9. Linha de comandos

```
python uan.py importar dados\comentarios.csv --plataforma YouTube --via api_oficial --descricao "lote 12"
python uan.py fonte-adicionar --endereco https://exemplo.ao/feed https://www.youtube.com/@canal "greve professores"
python uan.py recolher
python uan.py classificar
python uan.py alertas
python uan.py relatorio --de 2026-10-01 --ate 2026-10-31 --csv dados\relatorio.csv --email
python uan.py fila --n 20
python uan.py metricas
python uan.py exportar dados\revisoes_para_treino.csv
python uan.py limpar --dias 180
python uan.py copia
python uan.py repor-senha supervisor            (esqueceu a palavra-passe; --temporaria gera uma)
```

Útil para tarefas agendadas no Agendador de Tarefas do Windows (por exemplo, `limpar` e `copia` uma vez por dia).

## 10. Protecção de dados e uso responsável

- **Minimização.** O ficheiro importado é apagado logo a seguir à leitura. Só ficam o texto mascarado, a plataforma, a data, o contexto público e um pseudónimo do autor.
- **Pseudónimo com segredo.** HMAC-SHA-256 com `UAN_SEGREDO_HASH`, para não ser revertido por dicionário.
- **Nomes em texto livre** não são detectados automaticamente. O analista sinaliza-os na nota; os textos exportados são revistos antes de saírem do projecto.
- **Acesso.** Contas individuais, palavras-passe com PBKDF2-SHA-256, bloqueio após 5 tentativas falhadas, sessões no servidor, protecção CSRF em todos os formulários, cabeçalhos de segurança (CSP, X-Frame-Options).
- **Conservação limitada** e **cópias de segurança** em *Definições* ou pela linha de comandos.
- **Auditoria** de todas as acções relevantes.
- **Sem perfis de autores.** Não há vistas nem pesquisas por autor.
- **Revisão humana obrigatória.** Uma convocatória para manifestação pacífica é exercício de direitos (arts. 40.º e 47.º da Constituição). No teste, a precisão do modelo em `Mobilizacao` foi cerca de 0,51 e, em conteúdo angolano, o F1-macro foi cerca de 0,53.

## 11. Re-treino com as revisões

*Métricas → Exportar revisões para treino* (ou `python uan.py exportar`) gera um CSV com `origem = revisao_sistema`, uma linha por publicação; os itens em que os analistas discordaram ficam de fora. Estes rótulos vêm de itens **escolhidos pelo modelo**, por isso entram só no treino (`split_and_balance.py --train-only-origem revisao_sistema`) e nunca no teste.

## 12. Guardar o modelo no Colab

No fim da sessão de treino, corra a célula de `colab_guardar_modelo.py`. A pasta gravada no Drive (com `config.json`, pesos e tokenizer) é a que se indica em `UAN_MODELO`.

## 13. Actualizar de uma versão anterior

A base de dados da versão 0.1 é actualizada automaticamente no primeiro arranque: as revisões existentes passam a ter `origem_fila = fila`. O painel Streamlit (`painel.py`) foi substituído pela aplicação web; `python -m uvicorn api:app` continua a funcionar e arranca a aplicação completa.
