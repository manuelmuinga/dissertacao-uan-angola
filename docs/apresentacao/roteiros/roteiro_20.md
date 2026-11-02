# Roteiro da defesa – 20 minutos

Nov 2, 2026 · @Erasmo Simão Sungandungue de Murta

## Como usar e mapa de tempos

A exposição tem 20 diapositivos e 20:00 exactos; a demonstração ocupa 4:00. Ensaie com o ficheiro *Apresentacao\_Defesa\_UAN\_20min\_com\_notas.pptx*, que traz os tempos e as notas do orador. Projecte na sala o *Apresentacao\_Defesa\_UAN\_20min\_sem\_notas.pptx*: é o mesmo conteúdo, sem os minutos na agenda nem na demonstração.

O texto da secção seguinte é um guia para dizer por palavras suas, não para ler. A coluna Relógio diz onde deve estar no fim de cada diapositivo; os quatro pontos de controlo estão a negrito.

| # | Diapositivo | Tempo | Relógio |
| --- | --- | --- | --- |
| 1 | Capa | 0:30 | 0:30 |
| 2 | Agenda | 0:30 | 1:00 |
| 3 | Contexto | 1:00 | 2:00 |
| 4 | Pergunta e hipóteses | 1:00 | 3:00 |
| 5 | Objectivos | 0:45 | 3:45 |
| 6 | Revisão da literatura | 1:15 | **5:00** |
| 7 | Desenho da investigação | 0:45 | 5:45 |
| 8 | Corpus angolano | 1:00 | 6:45 |
| 9 | Corpus híbrido e modelos | 1:00 | 7:45 |
| 10 | Comparação de modelos (H1) | 1:00 | 8:45 |
| 11 | Lacuna de domínio (H4) | 1:00 | **9:45** |
| 12 | Ordenação da fila | 0:50 | 10:35 |
| 13 | Tempo de processamento (H2) | 0:45 | 11:20 |
| 14 | Limitações | 0:55 | 12:15 |
| 15 | Arquitectura | 1:00 | **13:15** |
| 16 | Demonstração | 4:00 | **17:15** |
| 17 | Verificação das hipóteses | 0:55 | 18:10 |
| 18 | Conclusões e contributos | 0:45 | 18:55 |
| 19 | Recomendações | 0:50 | 19:45 |
| 20 | Encerramento | 0:15 | 20:00 |

Os diapositivos 21 a 23 (Reserva A, B e C) só se usam se a demonstração falhar ou numa pergunta.

## O que dizer, diapositivo a diapositivo

Fale devagar nos números e pare um segundo depois de cada um. Os números que não pode falhar são 0,807, 0,919, 0,533 e 0,6–0,7 s.

### 1. Capa · 0:30 · relógio 0:30

Senhor Presidente do Júri, senhores membros do Júri, senhor Orientador, senhor Co-orientador, caros colegas e convidados, bom dia. Apresento a dissertação “Monitoramento inteligente de ameaças em redes sociais em Angola para o apoio à defesa e segurança nacional”. A exposição dura vinte minutos e inclui uma demonstração do sistema.

### 2. Agenda · 0:30 · relógio 1:00

Divido a exposição em seis partes. Começo pelo problema e pela pergunta, passo pela literatura e pelo método, e chego aos resultados. A parte maior é a do sistema, que vou mostrar a funcionar. Termino com as hipóteses, as conclusões e as recomendações. No topo de cada diapositivo vêem em que parte estamos.

### 3. Contexto · 1:00 · relógio 2:00

Comecemos pela escala. Em Outubro de 2025, Angola tinha cerca de 17,6 milhões de utilizadores da Internet, quase 45% da população, e 5,5 milhões de identidades em redes sociais. O acesso faz-se sobretudo pelo telemóvel.

E o que se passa nas redes não fica nas redes. A campanha “2022 Vais Gostar” começou no Facebook, no WhatsApp e no TikTok e acabou em manifestações em várias províncias. Ao mesmo tempo, a desinformação ganhou ferramentas novas: deepfakes, bots, campanhas coordenadas.

Para quem trabalha em segurança, o obstáculo não é a falta de informação. É o excesso. Há muito mais publicações do que analistas, e as ferramentas comerciais foram feitas para outras línguas e outros orçamentos. Daqui sai a ideia do trabalho: um sistema que ajude o analista a decidir o que ler primeiro, sem decidir por ele.

### 4. Pergunta e hipóteses · 1:00 · relógio 3:00

A pergunta de partida é esta *(ler devagar)*: em que medida um sistema baseado em aprendizagem automática consegue apoiar, de forma fiável e juridicamente responsável, a triagem de publicações ameaçadoras em redes sociais angolanas?

Para a tornar verificável, formulei quatro hipóteses, cada uma com um critério fixado antes de ver os resultados. A H1 diz que os modelos profundos superam os clássicos em pelo menos cinco pontos de F1-macro, com significância estatística. A H2, que cada publicação é processada em menos de sessenta segundos. A H3, que o sistema detecta padrões de risco com 48 horas de antecedência. A H4, que o desempenho cai pelo menos cinco pontos quando o texto é angolano. Esta última é a que mais me interessava, e já vão perceber porquê.

### 5. Objectivos · 0:45 · relógio 3:45

O objectivo geral é desenvolver e avaliar um sistema de apoio à triagem que junte um classificador adaptado ao português, revisão humana obrigatória e protecção de dados desde a concepção. Desdobra-se em cinco objectivos específicos. A comparação de algoritmos, o OE2, é testada pela H1. A perda em conteúdo angolano, o OE3, pela H4. O protótipo, o OE4, pela H2 e pela H3. O corpus e o quadro ético e legal não têm hipótese: um é construção de dados, o outro é normativo.

### 6. Revisão da literatura · 1:15 · relógio 5:00

A literatura deixou-me quatro constatações. Primeira: os sistemas internacionais existem, como o programa MediFor da DARPA ou as plataformas da Palantir, mas não foram feitos para o português de Angola, ou criam dependência de fornecedores externos.

Segunda: os recursos de processamento de linguagem natural em português são brasileiros. O BERTimbau, o ToLD-BR, o HateBR e o Fake.br vêm todos do Brasil, e a desinformação anotada que existe são notícias completas, não comentários.

Terceira: os classificadores de conteúdo nocivo perdem desempenho fora do domínio em que foram treinados, e tendem a aprender atalhos em vez do fenómeno. Quarta: pôr um humano no circuito não chega, porque quem revê sugestões de uma máquina tende a confiar nelas de mais. Isso pede revisão cega e amostras de controlo.

Juntas, dão a lacuna *(apontar a linha a vermelho)*: ninguém mediu o desempenho destes modelos em conteúdo angolano, nem existe um sistema de triagem desenhado à medida das suas limitações.

### 7. Desenho da investigação · 0:45 · relógio 5:45

O trabalho segue um paradigma pragmático e aplicado, com abordagem quantitativa, em três fases: primeiro os dados, depois os modelos, por fim o sistema. A H1 e a H4 testam-se com métricas e testes estatísticos; a H2 e a H3, com o sistema a funcionar. As revisões feitas no sistema podem voltar ao treino, o que fecha o ciclo.

### 8. Corpus angolano · 1:00 · relógio 6:45

O corpus angolano tem 2 637 publicações públicas. Cerca de 86% são comentários do YouTube, recolhidos pela interface oficial; o resto foi copiado à mão de páginas públicas. Os autores são pseudonimizados antes de qualquer gravação.

Três anotadores classificaram cada publicação em quatro categorias. O acordo entre eles, pelo κ de Fleiss, foi de 0,718, o que se considera substancial. Quando discordavam, prevaleceu a categoria mais grave: numa triagem, é preferível rever um falso alarme a perder uma ameaça.

Guardem um pormenor: a Mobilização Hostil só existe neste corpus. Nenhum dos corpora públicos a tem.

### 9. Corpus híbrido e modelos · 1:00 · relógio 7:45

Sozinho, o piloto é pequeno para treinar modelos profundos. Juntei-o a três corpora brasileiros, o ToLD-BR, o Fake.br e o HateBR, num total de 26 859 registos depois de deduplicar, com divisão estratificada de 70, 15 e 15 por cento.

Comparei quatro modelos de três gerações: SVM e Floresta Aleatória sobre TF-IDF, um Bi-LSTM e o BERTimbau. O protocolo ficou fixado antes de olhar para o teste: F1-macro com intervalos de confiança por bootstrap, e McNemar com correcção de Bonferroni.

Há um pormenor que condiciona tudo o resto: 91% do teste é brasileiro. Um bom número global diz pouco sobre Angola, e é por isso que a H4 separa os dois domínios.

### 10. Comparação de modelos (H1) · 1:00 · relógio 8:45

O BERTimbau obteve um F1-macro de **0,807**, com intervalo de confiança entre 0,774 e 0,838, que não se sobrepõe ao de nenhum dos outros. A vantagem é de 15 a 17 pontos, e o McNemar dá p inferior a 10 elevado a menos 47 nos três pares. Com três sementes, a média é 0,797.

Mas a H1 falava de modelos profundos, no plural, e o Bi-LSTM não se distingue da Floresta Aleatória: em três sementes, nunca a supera. A H1 fica parcialmente confirmada. O que distingue o BERTimbau é provavelmente o pré-treino, embora o desenho não o isole.

### 11. Lacuna de domínio (H4) · 1:00 · relógio 9:45

Este é o resultado central do trabalho. No corpus público, o BERTimbau tem F1-macro de **0,919**. No piloto angolano, cai para **0,533**. São 38,6 pontos, muito acima dos cinco que a H4 exigia.

Testei duas objecções. Sem a Mobilização Hostil, que só existe no piloto, a diferença mantém-se em 37,3 pontos, com intervalo de 30,6 a 44,7. E só com os comentários do YouTube sorteados, sem os itens que eu próprio escolhi, o F1 é 0,535.

A queda maior está na Desinformação, de 0,99 para 0,24. Há duas explicações que os dados não separam: o modelo pode ter aprendido o estilo das notícias do Fake.br em vez do fenómeno, ou as etiquetas do piloto são mais amplas. Seja qual for, a estimativa realista para Angola é 0,53, e é esse o número que o sistema mostra ao analista.

### 12. Ordenação da fila · 0:50 · relógio 10:35

Como o sistema usa as probabilidades para ordenar a fila, medi também o esforço de revisão. No teste completo, rever um quarto da ordenação encontra 80% das ameaças. No piloto angolano é preciso rever 49%.

Deixo dois avisos. A ordem segue a confiança do modelo, não a gravidade: a Mobilização Hostil fica, em mediana, na posição 927. E 28,7% das ameaças angolanas ficam entre os itens que o modelo considera normais, contra 11,8% no teste completo. É isto que justifica a amostra de controlo, que vão ver na demonstração.

### 13. Tempo de processamento (H2) · 0:45 · relógio 11:20

Medi o protótipo num computador modesto, um Intel N100 com 8 GB de RAM e sem GPU, com 198 comentários reais e três repetições. Cada publicação leva **0,6 a 0,7 segundos** a ser importada, pseudonimizada, classificada e gravada.

Com a gravação por sublotes, as primeiras chegam à fila em 36 segundos, e todas em menos de um minuto em recolhas até cerca de 64 publicações. A H2 fica confirmada nessas condições. A H3 não pôde ser testada: exigia um corpus datado em torno de eventos documentados, que não tive.

### 14. Limitações · 0:55 · relógio 12:15

Antes do sistema, digo o que estes resultados não permitem afirmar. O piloto é pequeno: 355 itens de teste, e só 47 de Mobilização Hostil, com um intervalo de F1 entre 0,42 e 0,66. O teste é dominado pelo Brasil. A única desinformação pública disponível são notícias.

Não consegui separar língua, plataforma, registo e etiquetas, porque variam todos ao mesmo tempo. A utilidade da fila com analistas reais e a antecipação ficaram por medir. E o protótipo segue boas práticas de segurança, mas não teve auditoria independente.

### 15. Arquitectura · 1:00 · relógio 13:15

Foram estes resultados que ditaram o desenho. Um modelo com 0,53 em Angola não pode decidir; pode ordenar. A arquitectura é leve: um único servidor, software livre, sem bibliotecas nem serviços externos, e funciona sem Internet.

As salvaguardas estão no próprio código. Os autores são pseudonimizados à entrada, e telefones, endereços e menções são mascarados. Não há perfis de pessoas, só publicações e agregados por categoria, período e província. A decisão é sempre humana, e tudo fica registado para auditoria. Há 121 testes automáticos, todos aprovados. Passo agora ao navegador.

### 16. Demonstração · 4:00 · relógio 17:15

Seguir o guião da secção seguinte.

### 17. Verificação das hipóteses · 0:55 · relógio 18:10

Volto às hipóteses. A H1 fica parcialmente confirmada: o BERTimbau supera os clássicos com folga, o Bi-LSTM não. A H2 confirma-se, nas condições que referi. A H3 não foi testada. A H4 confirma-se com reservas: a queda é grande e resiste aos controlos, mas o piloto é pequeno e as causas não estão separadas.

Quero ser claro sobre o que não demonstrei: que a fila poupa tempo a analistas reais, e que o sistema antecipa acontecimentos.

### 18. Conclusões e contributos · 0:45 · relógio 18:55

Tiro três conclusões. Só o BERTimbau serve como classificador principal. O desempenho não se transfere intacto para Angola, onde a estimativa realista é 0,53. E um sistema de triagem com revisão humana, auditável e de baixo custo é viável com software livre.

Os contributos estão à direita: o primeiro corpus angolano anotado nestas categorias, a medida da lacuna de domínio, uma avaliação que inclui calibração e esforço de revisão, e um protótipo aberto. Numa frase: o modelo ordena o trabalho; o analista decide.

### 19. Recomendações · 0:50 · relógio 19:45

As três primeiras recomendações são condições para qualquer uso institucional: avaliar a fila com analistas reais, obter parecer jurídico à luz da Lei n.º 22/11, e ampliar o corpus angolano, medindo sempre em Angola.

As outras três são trabalho futuro: substituir a fonte de desinformação por publicações curtas, de preferência angolanas; adaptar o modelo ao domínio; e ordenar a fila pela gravidade. Se tivesse de escolher um só investimento, seriam dados angolanos anotados.

### 20. Encerramento · 0:15 · relógio 20:00

Agradeço a atenção do Júri e fico à disposição para as perguntas e os comentários.

## Demonstração ao vivo (4:00)

A demonstração corre no modo de demonstração: base separada, dados fictícios, classificador simulado. Diga-o logo ao entrar, para que ninguém tome os números do ecrã por resultados.

| Passo | Tempo | O que fazer | O que dizer |
| --- | --- | --- | --- |
| Entrada | 0:10 | Alt+Tab para o navegador, já com sessão aberta como demo.supervisor | “Estou no modo de demonstração: dados fictícios e classificador simulado.” |
| 1. Panorama | 0:25 | Mostrar os totais e as categorias | “O que foi recolhido e o que o modelo sinalizou, por categoria e província.” |
| 2. Fila e amostra de controlo | 1:00 | Abrir uma publicação; decidir com uma tecla de 1 a 4; desfazer com U; abrir a amostra de controlo | “Cada publicação traz a categoria prevista, as probabilidades e o lugar realçado. Decido com o teclado e posso desfazer. Na revisão cega, a sugestão só aparece depois de eu decidir. Aqui revejo uma amostra do que o modelo achou normal: é assim que se estimam as ameaças que escapam.” |
| 3. Alertas e mapa | 1:00 | Abrir o sino; no mapa, passar o cursor por uma província; reproduzir semana a semana | “Os alertas nascem só de decisões humanas. O mapa usa o lugar mencionado na publicação, não o paradeiro de quem escreve.” |
| 4. Sobre o modelo | 0:30 | Abrir a página Sobre o modelo | “O analista vê o desempenho em Angola, 0,53, e não só o número global.” |
| 5. Lotes e contas | 0:40 | Abrir Lotes; depois Sair e a ligação “Esqueceu-se da palavra-passe?” | “Cada recolha fica registada como lote, com origem e data. O acesso recupera-se com código, sem correio electrónico.” |
| Regresso | 0:15 | Alt+Tab para o PowerPoint, diapositivo 17 | “Volto às hipóteses.” |

**Plano B.** Se o servidor não arrancar ou o navegador bloquear, não tente reparar à frente do Júri. Diga “passo à gravação” e mostre o vídeo de reserva (*demo\_sistema\_uan\_reserva.mp4*, 3:24). Sem vídeo, salte para os diapositivos de reserva A, B e C e comente-os em 2:30; ganha 1:30, que pode dar às hipóteses.

## Se o tempo apertar

Confira o relógio nos quatro pontos de controlo: 5:00, 9:45, 13:15 e 17:15. Se estiver atrasado, corte por esta ordem, que poupa até 2:20 sem tocar no resultado central nem na demonstração da fila.

| Ordem | Onde | O que cortar | Poupa |
| --- | --- | --- | --- |
| 1 | 5. Objectivos | Dizer só o objectivo geral; os específicos ficam no ecrã | 0:30 |
| 2 | 14. Limitações | Dizer as três maiores: piloto pequeno, teste brasileiro, uso real por medir | 0:25 |
| 3 | 16. Demonstração | Saltar o passo 5, Lotes e contas | 0:40 |
| 4 | 19. Recomendações | Ler só os títulos das três primeiras e a frase final | 0:25 |
| 5 | 6. Literatura | Dizer só a lacuna, a vermelho | 0:20 |

Nunca corte o diapositivo 11 (H4) nem o 17 (hipóteses): são os que o Júri vai discutir.

## Antes da sessão

**Na véspera**

- [ ] Ensaiar duas vezes com cronómetro, usando a versão com notas
- [ ] Copiar para uma pen e para o portátil: a versão sem notas, a versão com notas, o PDF da dissertação e o vídeo de reserva
- [ ] Imprimir este roteiro ou tê-lo no telemóvel

**Uma hora antes, na sala**

- [ ] Ligar o portátil ao projector e confirmar o cabo HDMI, o adaptador e o carregador
- [ ] Abrir a versão sem notas no ecrã do projector; se houver vista do orador, abrir a versão com notas no portátil
- [ ] Arrancar o servidor com *arrancar\_demonstracao.bat* e confirmar http://127.0.0.1:8000
- [ ] Entrar como demo.supervisor e carregar em Saltar na visita guiada
- [ ] Testar o Alt+Tab entre o PowerPoint e o navegador
- [ ] Desligar notificações, actualizações automáticas e protecção de ecrã
- [ ] Ter água e um relógio visível
