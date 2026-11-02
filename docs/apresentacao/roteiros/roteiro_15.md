# Roteiro da defesa – 15 minutos

Nov 2, 2026 · @Erasmo Simão Sungandungue de Murta

## Como usar e mapa de tempos

A exposição tem 19 diapositivos e 15:00 exactos; a demonstração ocupa 3:15. Em relação à versão de 20 minutos, sai o diapositivo dos objectivos e todos os outros encurtam. Ensaie com *Apresentacao\_Defesa\_UAN\_15min\_com\_notas.pptx* e projecte *Apresentacao\_Defesa\_UAN\_15min\_sem\_notas.pptx*.

O texto da secção seguinte é um guia para dizer por palavras suas. A coluna Relógio diz onde deve estar no fim de cada diapositivo; os quatro pontos de controlo estão a negrito.

| # | Diapositivo | Tempo | Relógio |
| --- | --- | --- | --- |
| 1 | Capa | 0:20 | 0:20 |
| 2 | Agenda | 0:25 | 0:45 |
| 3 | Contexto | 0:50 | 1:35 |
| 4 | Pergunta e hipóteses | 0:50 | 2:25 |
| 5 | Revisão da literatura | 0:55 | **3:20** |
| 6 | Desenho da investigação | 0:30 | 3:50 |
| 7 | Corpus angolano | 0:45 | 4:35 |
| 8 | Corpus híbrido e modelos | 0:45 | 5:20 |
| 9 | Comparação de modelos (H1) | 0:50 | 6:10 |
| 10 | Lacuna de domínio (H4) | 0:55 | **7:05** |
| 11 | Ordenação da fila | 0:40 | 7:45 |
| 12 | Tempo de processamento (H2) | 0:35 | 8:20 |
| 13 | Limitações | 0:45 | 9:05 |
| 14 | Arquitectura | 0:40 | **9:45** |
| 15 | Demonstração | 3:15 | **13:00** |
| 16 | Verificação das hipóteses | 0:40 | 13:40 |
| 17 | Conclusões e contributos | 0:30 | 14:10 |
| 18 | Recomendações | 0:35 | 14:45 |
| 19 | Encerramento | 0:15 | 15:00 |

Os diapositivos 20 a 22 (Reserva A, B e C) só se usam se a demonstração falhar ou numa pergunta. Se o Júri perguntar pelos objectivos, estão na Secção 1.4: o OE2 é testado pela H1, o OE3 pela H4 e o OE4 pela H2 e pela H3.

## O que dizer, diapositivo a diapositivo

Em 15 minutos não há tempo para explicar o que está no ecrã: diga a conclusão de cada diapositivo e deixe o Júri ler o resto. Os números que não pode falhar são 0,807, 0,919, 0,533 e 0,6–0,7 s.

### 1. Capa · 0:20 · relógio 0:20

Senhor Presidente do Júri, senhores membros do Júri, senhor Orientador, senhor Co-orientador, caros colegas e convidados, bom dia. Apresento a minha dissertação de mestrado. São quinze minutos, com uma demonstração do sistema.

### 2. Agenda · 0:25 · relógio 0:45

Seis partes: o problema, a literatura, o método, os resultados, o sistema e as conclusões. A maior é a do sistema, que vou mostrar a funcionar.

### 3. Contexto · 0:50 · relógio 1:35

Angola tinha, em Outubro de 2025, cerca de 17,6 milhões de utilizadores da Internet e 5,5 milhões de identidades em redes sociais. E o que nasce na rede pode chegar à rua: a campanha “2022 Vais Gostar” começou nas redes e acabou em manifestações em várias províncias.

O obstáculo para a segurança não é a falta de informação, é o excesso. Há mais publicações do que analistas, e as ferramentas comerciais não conhecem o português de Angola. Proponho um sistema que ajude o analista a decidir o que ler primeiro, sem decidir por ele.

### 4. Pergunta e hipóteses · 0:50 · relógio 2:25

A pergunta de partida é esta *(ler devagar)*: em que medida um sistema baseado em aprendizagem automática consegue apoiar, de forma fiável e juridicamente responsável, a triagem de publicações ameaçadoras em redes sociais angolanas?

Quatro hipóteses, cada uma com critério fixado antes dos resultados: a H1 compara algoritmos, a H2 mede o tempo, a H3 a antecedência, e a H4 a queda de desempenho em texto angolano. É a H4 que vai pesar mais.

### 5. Revisão da literatura · 0:55 · relógio 3:20

A literatura deixa quatro constatações. Os sistemas internacionais não servem Angola ou criam dependência de fornecedores. Os recursos de linguagem em português são brasileiros. Os classificadores perdem desempenho fora do domínio de treino. E rever não basta, porque quem revê sugestões de uma máquina tende a confiar de mais.

Daí a lacuna *(apontar a linha a vermelho)*: ninguém mediu estes modelos em conteúdo angolano, nem desenhou um sistema à medida das suas limitações.

### 6. Desenho da investigação · 0:30 · relógio 3:50

Paradigma pragmático, abordagem quantitativa e três fases: dados, modelos e sistema.

### 7. Corpus angolano · 0:45 · relógio 4:35

O corpus angolano tem 2 637 publicações públicas, 86% delas comentários do YouTube recolhidos pela interface oficial, com autores pseudonimizados. Três anotadores, κ de Fleiss de 0,718, acordo substancial. No desacordo, prevalece a categoria mais grave. E a Mobilização Hostil só existe aqui.

### 8. Corpus híbrido e modelos · 0:45 · relógio 5:20

Juntei o piloto a três corpora brasileiros: 26 859 registos. Comparei quatro modelos, de SVM a BERTimbau, com um protocolo fixado antes de ver o teste. Atenção: 91% do teste é brasileiro, e é por isso que a H4 separa os dois domínios.

### 9. Comparação de modelos (H1) · 0:50 · relógio 6:10

O BERTimbau obteve **0,807** de F1-macro e supera os outros em 15 a 17 pontos, com p inferior a 10 elevado a menos 47. Mas o Bi-LSTM, em três sementes, nunca supera a Floresta Aleatória. Por isso a H1, que falava de modelos profundos no plural, fica parcialmente confirmada.

### 10. Lacuna de domínio (H4) · 0:55 · relógio 7:05

Este é o resultado central. No corpus público o F1-macro é **0,919**; no piloto angolano é **0,533**. A diferença resiste aos controlos: sem Mobilização Hostil são 37,3 pontos, e só com YouTube sorteado o F1 é 0,535.

A maior queda é na Desinformação, de 0,99 para 0,24, com duas explicações que os dados não separam: o estilo das notícias do Fake.br ou etiquetas mais amplas no piloto. Para Angola, a estimativa realista é 0,53.

### 11. Ordenação da fila · 0:40 · relógio 7:45

No teste, rever 25% da ordenação encontra 80% das ameaças; no piloto, são precisos 49%. A ordem segue a confiança, não a gravidade. E 28,7% das ameaças angolanas ficam entre os Normais, o que justifica a amostra de controlo.

### 12. Tempo de processamento (H2) · 0:35 · relógio 8:20

Sem GPU, cada publicação leva **0,6 a 0,7 segundos**, e as primeiras chegam à fila em 36 segundos. H2 confirmada com condições. A H3 não foi testada: falta um corpus datado.

### 13. Limitações · 0:45 · relógio 9:05

Três limitações pesam mais: o piloto é pequeno, com 355 itens de teste; o teste é sobretudo brasileiro; e o uso real com analistas não foi medido. As outras estão no ecrã.

### 14. Arquitectura · 0:40 · relógio 9:45

Um modelo com 0,53 em Angola não pode decidir; pode ordenar. Um único servidor, software livre, sem serviços externos. Pseudonimização à entrada, nenhum perfil de pessoas, decisão sempre humana e tudo registado. Passo ao navegador.

### 15. Demonstração · 3:15 · relógio 13:00

Seguir o guião da secção seguinte.

### 16. Verificação das hipóteses · 0:40 · relógio 13:40

H1 parcialmente confirmada, H2 confirmada com condições, H3 não testada, H4 confirmada com reservas. Não demonstrei que a fila poupa tempo a analistas reais, nem que o sistema antecipa acontecimentos.

### 17. Conclusões e contributos · 0:30 · relógio 14:10

Só o BERTimbau serve como classificador principal; em Angola vale 0,53; e o sistema é viável com software livre. Numa frase: o modelo ordena o trabalho, o analista decide.

### 18. Recomendações · 0:35 · relógio 14:45

Antes de qualquer uso institucional: avaliar a fila com analistas, obter parecer jurídico e ampliar o corpus angolano. Depois, o trabalho futuro que está à direita. O investimento que mais rende são dados angolanos anotados.

### 19. Encerramento · 0:15 · relógio 15:00

Agradeço a atenção do Júri e fico à disposição para as perguntas.

## Demonstração ao vivo (3:15)

A demonstração corre no modo de demonstração: base separada, dados fictícios, classificador simulado. Diga-o logo ao entrar.

| Passo | Tempo | O que fazer | O que dizer |
| --- | --- | --- | --- |
| Entrada | 0:10 | Alt+Tab para o navegador, já com sessão aberta como demo.supervisor | “Modo de demonstração: dados fictícios e classificador simulado.” |
| 1. Panorama | 0:20 | Mostrar os totais | “O que foi recolhido e o que o modelo sinalizou.” |
| 2. Fila e amostra de controlo | 0:50 | Decidir uma publicação com uma tecla de 1 a 4; desfazer com U; abrir a amostra de controlo | “Decido com o teclado e posso desfazer. Na revisão cega, a sugestão só aparece depois. Aqui revejo uma amostra do que o modelo achou normal.” |
| 3. Alertas e mapa | 0:45 | Abrir o sino; passar o cursor por uma província | “Os alertas nascem só de decisões humanas. O mapa usa o lugar mencionado, não o paradeiro de quem escreve.” |
| 4. Sobre o modelo | 0:25 | Abrir a página Sobre o modelo | “O analista vê o 0,53 de Angola.” |
| 5. Lotes e contas | 0:30 | Abrir Lotes; depois Sair e “Esqueceu-se da palavra-passe?” | “Cada recolha fica registada como lote. O acesso recupera-se sem correio electrónico.” |
| Regresso | 0:15 | Alt+Tab para o PowerPoint, diapositivo 16 | “Volto às hipóteses.” |

**Plano B.** Se o servidor não arrancar, não tente reparar à frente do Júri. Salte para os diapositivos de reserva A, B e C e comente-os em 2:00; ganha 1:15. O vídeo de reserva dura 3:24 e passa do tempo: só o use se puder cortá-lo antes do fim.

## Se o tempo apertar

Confira o relógio nos quatro pontos de controlo: 3:20, 7:05, 9:45 e 13:00. A versão de 15 minutos já vem enxuta, por isso a margem é pequena: estes cortes poupam até 1:35.

| Ordem | Onde | O que cortar | Poupa |
| --- | --- | --- | --- |
| 1 | 15. Demonstração | Saltar o passo 5, Lotes e contas | 0:30 |
| 2 | 5. Literatura | Dizer só a lacuna, a vermelho | 0:25 |
| 3 | 3. Contexto | Dizer os dois números e a ideia central, sem o exemplo de 2022 | 0:15 |
| 4 | 17. Conclusões | Dizer só a frase final | 0:15 |
| 5 | 12. H2 | Dizer só o 0,6–0,7 s e a H3 não testada | 0:10 |

Nunca corte o diapositivo 10 (H4) nem o 16 (hipóteses).

## Antes da sessão

**Na véspera**

- [ ] Ensaiar duas vezes com cronómetro, usando a versão com notas
- [ ] Copiar para uma pen e para o portátil: a versão sem notas, a versão com notas e o PDF da dissertação
- [ ] Imprimir este roteiro ou tê-lo no telemóvel

**Uma hora antes, na sala**

- [ ] Ligar o portátil ao projector e confirmar o cabo HDMI, o adaptador e o carregador
- [ ] Abrir a versão sem notas no ecrã do projector; se houver vista do orador, abrir a versão com notas no portátil
- [ ] Arrancar o servidor com *arrancar\_demonstracao.bat* e confirmar http://127.0.0.1:8000
- [ ] Entrar como demo.supervisor e carregar em Saltar na visita guiada
- [ ] Testar o Alt+Tab entre o PowerPoint e o navegador
- [ ] Desligar notificações, actualizações automáticas e protecção de ecrã
- [ ] Ter água e um relógio visível
