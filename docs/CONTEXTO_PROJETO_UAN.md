# Contexto do projeto UAN — para continuar noutra conversa

> **Como usar:** abra uma conversa nova neste *Projeto* e escreva: *"Lê o CONTEXTO_PROJETO_UAN.md e continua daqui. Responde em português."* A nova conversa não vê os ficheiros de sessões anteriores: o que está no repositório GitHub pode ser clonado; o resto deve ser anexado.
> **Última actualização: 27/10/2026.** Dissertação revista (89 páginas, Capítulos 1–6), apresentação de 20 minutos actualizada, plano B da demonstração, errata-modelo e simulação da arguição prontos. **Defesa: 15 de Dezembro de 2026.**

## 1. Quem e o quê
- Utilizador: **Erasmo Murta**, a apoiar a dissertação de mestrado de **Manuel Gonga Muinga** — *"Monitoramento inteligente de ameaças em redes sociais em Angola para o apoio à defesa e segurança nacional"* (UAN, Faculdade de Engenharia, Mestrado em Engenharia e Ciência de Dados, 2026). Orientador: Prof. Doutor Joaquim Fortes; co-orientador: Prof. Doutor Judice Cumbunga.
- Responder sempre em **português europeu, grafia anterior ao AO** (actual, objectivo, acção). O utilizador usa **Windows (cmd)**: comandos numa linha, a começar por `python`.
- Seguir as **Normas da UAN para Teses e Dissertações** (não o Regulamento de trabalhos de fim do curso).
- PC do utilizador: Intel N100, 8 GB RAM. Repositório local: `C:\Users\Manue\OneDrive\Documentos\Dissertação\Trabalho_Disertação\Dissertacao\dissertacao-uan-angola`. GitHub: `manuelmuinga/dissertacao-uan-angola` (público), ramo de trabalho **`sistema-e-cap4`** (último commit de 27/10: `9763612`).
- O Google Drive ligado às conversas é o de **erasmomurta@gmail.com**, não o de manuelmuinga@gmail.com.

## 2. Regras permanentes (não negociáveis)
1. **Nunca fabricar dados de investigação** nem apresentá-los como reais; verificar toda a fonte nova (duplicados, κ, proveniência) antes de aceitar.
2. **Pseudonimização** dos autores à entrada (HMAC-SHA-256 com segredo fora do código). Nomes de pessoas privadas → descritores de papel. **Decisão de 27/10:** os cinco nomes próprios do lote temático mantêm-se como estão; a dissertação declara-o (Secções 3.2 e 4.5.1).
3. Dados enriquecidos (lote temático, léxico) **só no treino**, com `origem`; o modo de demonstração usa dados fictícios numa base separada.
4. Recolha: só **conteúdo público**; sem contornar protecções, sem conteúdo atrás de login; registar cada lote (plataforma, via, data, volume).
5. Reportar resultados tal como saem; escolher variantes pela **validação**; IC 95% sempre que possível.
6. **Alertas** nascem só de decisões humanas; nunca envio automático a terceiros; e-mails sem texto nem autor.
7. **Interface** sem bibliotecas externas; funciona sem Internet.
8. **Segurança:** nunca mostrar segredos (chave da API, `UAN_SEGREDO_HASH`); a chave `ghp_…` partilhada a 10/10 nunca foi usada e deve ser revogada.

## 3. Corpus (autoritativo: `corpus_ground_truth_com_texto_v13.csv`)
- 2 637 publicações: Normal 1 664, Mobilização 364, Desinformação 326, Ódio 283; cerca de 86% comentários do YouTube.
- `origem`: `ate_v11` 2 352 (1 978 YouTube sorteados; 374 manuais: 104 piloto original, 90 Facebook, 180 títulos de imprensa), `enriquecido_lexico` 91, `enriquecido_video_tema` 194 (só treino).
- Desacordos: prevalece a categoria mais grave; 297 ameaças (11,3%) vêm de um só voto.
- κ de Fleiss 0,718 [0,695; 0,741] em 2 443 itens (base 0,717); itens manuais com κ baixo (0,42 no piloto original, 0,28 nos títulos).
- Corpus híbrido: 26 859 registos (27 097 antes de retirar 238 duplicados): ToLD-BR 12 709, Fake.br 7 199, HateBR 4 378 (ofensivo → Ódio, limitação declarada), piloto 2 573. Divisão 70/15/15; teste 3 987 (355 angolanos).

## 4. Resultados (todos na dissertação)
| Modelo | F1-macro (teste) | Média de 3 sementes |
|---|---|---|
| BERTimbau s42 | 0,807 [0,774; 0,838] | 0,797 ± 0,011 |
| Floresta Aleatória | 0,659 | 0,652 ± 0,009 |
| Bi-LSTM | 0,660 | 0,645 ± 0,016 |
| SVM | 0,633 | 0,631 ± 0,001 |
- H1 parcialmente confirmada (BERTimbau +14,6 a +17,4 p.p., p < 10^-47; o Bi-LSTM nunca supera a Floresta; nas sementes 43 e 44 fica abaixo dela, p < 10^-4).
- H4 confirmada com reservas: piloto 0,533 contra 0,919 (−38,6 p.p.). Sem Mobilização: 0,545 [0,474; 0,613], Δ 37,3 [30,6; 44,7]. Só YouTube sorteado (n = 289): 0,535 [0,457; 0,603], κ 0,443. Desinformação 0,99 → 0,24, com duas explicações que os dados não separam (estilo do Fake.br; etiquetas mais amplas no piloto); OE3 parcialmente cumprido.
- Calibração no piloto: ECE 0,160; confiança 0,85 contra exactidão 0,69. Esforço: 25% da ordenação encontra 80% das ameaças no teste, 49% no piloto; 28,7% das ameaças angolanas ficam entre os Normais (11,8% no teste). A fila por omissão tem 1 147 itens (28,8%) com 88,2% das ameaças.
- H2 confirmada com condições: 0,6–0,7 s por publicação (N100, sem GPU); primeiras na fila em 36 s; todas em < 60 s até 64 por recolha. H3 não testada (protocolo esboçado).
- Modelo do sistema (novo treino de 12/10): F1-macro 0,808 [0,773; 0,839]; McNemar p = 0,41; 97,4% de previsões iguais.
- Resultados do caderno de revisão: `resultados/revisao/resultados_revisao.json`.

## 5. Dissertação (estado de 27/10)
- `docs/Dissertacao_UAN.docx` e `.pdf` no ramo: **89 páginas** (xiii + 64 + glossário G1 + apêndices A–F). Gerada por um *builder* Node (`build.js`, `cap1–6.js`, `pos.js`, `construir.sh`) que **não persiste** entre sessões.
- Estrutura conforme às Normas: Capítulo 5 – Conclusões e **Capítulo 6 – Recomendações** (separados); capa em Arial 14 com orientadores; glossário paginado G1; subsecções a 13 pt; Resumo e Abstract com 243 e 248 palavras.
- Referências: 67, todas citadas e todas na lista. Verificadas nas fontes: Cintra (2025, p. 101), Elias (2019, p. 85), Sette Câmara (2016, pp. 202–209), Hassane (2021, pp. 37–38, revista confirmada), Kemp (2025), Sambaca & Pessoa (2026, *Revista Tópicos* 4(29)), Marcon (2019, pp. 191–208), Palantir Technologies (2024, ficha G-Cloud 14). Fortuna et al. (2021): citado só pelo que diz o resumo; os dois PDF enviados eram de outros artigos.
- Apêndice F.4 / Tabela F.2: requisitos RF1–RF17 ligados aos 121 testes automáticos.

## 6. Defesa (15/12/2026)
- Apresentação de 20 minutos: `docs/Apresentacao_Defesa_UAN.pptx` (20 diapositivos + 3 de reserva); gerador em `docs/apresentacao/gerar.js` + `transicoes.py`.
- Claude Docs: **Roteiro e preparação da defesa** (roteiro falado, demonstração de 4:00, plano B, plano semanal, checklist); **Simulação da arguição** (47 perguntas com resposta e página); **Errata da dissertação — modelo**.
- Plano B da demonstração: `docs/apresentacao/demo_reserva/` (vídeo de 3:24 legendado, capturas, script de gravação). Arranque: `sistema_uan\arrancar_demonstracao.bat`. Entrar como **demo.supervisor** (o analista não vê Fontes) e saltar a visita guiada antes da sessão.

## 7. Sistema web (`sistema_uan\`)
- `python uan.py servir` → http://127.0.0.1:8000; demonstração: `python uan.py servir --demonstracao` (contas demo.supervisor / demo.analista / demo.revisor, senha `demonstracao`; recolha automática desligada; sem e-mails).
- FastAPI + Jinja2, SQLite, 17 requisitos, **121 testes** (`python -m pytest -q`). Ficha do modelo em `sistema/ficha_modelo.json` (texto da Desinformação suavizado a 27/10).

## 8. Pendências (do lado do utilizador)
1. Aprovação do orientador para as mudanças de fundo (Capítulo 6 separado, OE3 parcialmente cumprido, nomes mantidos no lote temático).
2. **Autorização institucional** (elemento obrigatório pelas Normas) e ficha catalográfica com a biblioteca.
3. Abrir o .docx no Word e actualizar os campos (F9); verificação de plágio; leitura do Abstract por um falante nativo, se possível.
4. Imprimir e entregar seis exemplares em capa dura branca; errata real (a partir do modelo) entregue ao júri antes da prova.
5. Ensaios com cronómetro e com a simulação da arguição; testar a demonstração no N100 sem Wi-Fi.
6. Rever e fazer *merge* do PR #1; revogar a chave `ghp_…`; rodar a chave do YouTube.
7. Depois da defesa: página «Aprovação do Júri» a seguir à folha de rosto; versão definitiva sem errata.
