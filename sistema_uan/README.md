# Sistema UAN: triagem de ameaças com revisão humana (protótipo)

Protótipo do sistema descrito na dissertação *Monitoramento Inteligente de Ameaças em Redes Sociais em Angola*. O modelo BERTimbau afinado classifica publicações públicas em quatro categorias (`Normal`, `Desinformacao`, `Odio`, `Mobilizacao`) e **ordena uma fila de revisão** para o analista. O sistema **não toma decisões**. Cada classificação é uma sugestão que o analista confirma ou corrige, e as correcções podem ser exportadas para voltar a treinar o modelo.

```
ficheiro de recolha (.csv/.jsonl)
      │  importar: anonimização (Lei 22/11) + registo do lote (plataforma, via, data, volume)
      ▼
SQLite ──► classificar (BERTimbau, em lote) ──► fila ordenada por P(não Normal)
                                                      │
                                     analista confirma / corrige (auditado)
                                                      │
                               métricas (precisão@K, κ analista–sistema, latência)
                               exportação de revisões para re-treino
```

| Ficheiro | Função |
|---|---|
| `sistema/anonimizacao.py` | Mascara URLs, e-mails, telefones e @menções; pseudónimo HMAC-SHA-256 do autor |
| `sistema/classificador.py` | Carrega o BERTimbau guardado; classificador de demonstração para testes |
| `sistema/base_dados.py` | Esquema SQLite: lotes, publicações, classificações, revisões, auditoria |
| `sistema/servico.py` | Importação, classificação, prioridade, métricas, exportação |
| `uan.py` | Linha de comandos |
| `api.py` | Serviço FastAPI (integração com outros componentes) |
| `painel.py` | Painel Streamlit do analista |
| `tests/` | 13 testes (anonimização, fluxo completo, modelo BERT real em miniatura, API) |

## 1. Instalação (Windows, cmd)

```
python -m pip install -r requirements.txt
```

## 2. Guardar o modelo no Colab (uma vez)

O notebook não descarrega os pesos. No **fim da sessão de treino**, na mesma sessão do Colab, correr a célula de `colab_guardar_modelo.py`. A célula grava o modelo no formato Hugging Face no Google Drive. Depois descarregue a pasta `bertimbau_uan_v13` do Drive para o PC, por exemplo para `C:\modelos\bertimbau_uan_v13`.

A pasta tem de conter `config.json`, os pesos (`model.safetensors` ou `pytorch_model.bin`) e os ficheiros do tokenizer.

## 3. Configuração (variáveis de ambiente)

```
set UAN_MODELO=C:\modelos\bertimbau_uan_v13
set UAN_SEGREDO_HASH=uma-frase-secreta-longa-que-nao-vai-para-o-git
```

| Variável | Por omissão | Significado |
|---|---|---|
| `UAN_MODELO` | (vazio) | Pasta do modelo. Vazio = classificador de **demonstração** (palavras-chave, não é um modelo) |
| `UAN_SEGREDO_HASH` | (vazio) | Segredo do pseudónimo dos autores. Obrigatório para importar |
| `UAN_BD` | `dados\sistema.db` | Ficheiro da base de dados |
| `UAN_MAX_LENGTH` | 128 | Igual ao `--max-length` do treino |
| `UAN_LOTE` | 32 | Tamanho do lote de inferência |
| `UAN_DISPOSITIVO` | auto | `cpu`, `cuda` ou `auto` |
| `UAN_DIAS_CONSERVACAO` | 180 | Prazo para `uan.py limpar` |

## 4. Utilização

```
python uan.py importar dados\comentarios_lote12.csv --plataforma YouTube --via api_oficial --descricao "comentários públicos, 12 vídeos, 2026-10-10"
python uan.py classificar
python uan.py fila --n 20
python -m streamlit run painel.py
python -m uvicorn api:app --port 8000
python uan.py metricas
python uan.py exportar dados\revisoes_para_treino.csv
python uan.py limpar --dias 180
```

Vias de recolha aceites (`--via`): `api_oficial`, `manual`, `scraping_publico`, `doacao`, `dataset_terceiros`. Ficam registadas por lote para a secção de metodologia.

Colunas reconhecidas nos ficheiros: texto (`texto`, `text`, `textDisplay`, `textOriginal`, `comentario`), autor (`autor`, `author`, `authorDisplayName`), id (`id`, `comment_id`), data (`data`, `publishedAt`) e contexto (`video_titulo`, `canal`). O resultado do `scrape_youtube_canais.py` pode ser importado directamente.

## 5. Medir a H2 (latência) e avaliar o sistema

```
python uan.py medir-latencia dados\comentarios_lote12.csv --repeticoes 5
```

Este comando mede **importação + anonimização + classificação** numa base temporária e reporta a mediana por lote e por item. A métrica `latencia_s` em `uan.py metricas` mede o tempo entre a importação e a classificação de cada publicação (mediana e P95). Nenhuma das duas inclui o tempo entre a publicação original e a recolha, que depende da frequência de recolha. Na dissertação, reporte esse tempo separadamente (Secção 4.7).

Para avaliar o sistema com um analista:
1. Importe um lote **novo**, nunca usado no treino, e classifique-o.
2. O analista revê a fila por ordem.
3. `python uan.py metricas` devolve a **precisão@K** (fracção de ameaças confirmadas nos K primeiros), a concordância e o **κ analista–sistema**.

Para medir a sensibilidade, é preciso rever também uma **amostra aleatória** de itens classificados como Normal. A fila só mostra o que o modelo sinalizou.

## 6. Protecção de dados e uso responsável

- **Minimização.** O ficheiro bruto não é guardado. Só ficam o texto mascarado, a plataforma, a data, o contexto público e um pseudónimo do autor.
- **Pseudónimo com segredo.** Um SHA-256 simples de um nome de utilizador pode ser revertido por dicionário. Por isso usa-se HMAC com `UAN_SEGREDO_HASH`. Guarde o segredo fora do repositório.
- **Nomes em texto livre** (por exemplo, pessoas privadas mencionadas num comentário) não são detectados automaticamente. O analista deve sinalizá-los na nota, e os textos exportados devem ser revistos antes de saírem do projecto.
- **Conservação limitada.** `uan.py limpar` apaga as publicações não revistas mais antigas do que o prazo. As revistas ficam como base de re-treino.
- **Auditoria.** Importações, classificações, revisões, exportações e limpezas ficam na tabela `auditoria`.
- **Sem perfis de autores.** O painel mostra agregados por categoria, dia e plataforma. Não há vistas por autor.
- **Revisão humana obrigatória.** Uma convocatória para manifestação pacífica é exercício de direitos (arts. 40.º e 47.º da Constituição). No teste, a precisão do modelo em `Mobilizacao` foi cerca de 0,51 e, em conteúdo angolano, o F1-macro foi cerca de 0,53.
- **Vias de recolha.** Só conteúdo público, sem contornar protecções técnicas nem aceder a conteúdo atrás de login. Os termos de uso das plataformas devem ser declarados na metodologia e confirmados com o orientador.

## 7. Re-treino com as revisões

`uan.py exportar` gera um CSV com `origem = revisao_sistema`. Estes rótulos vêm de **um** analista e de itens **escolhidos pelo modelo**, por isso não equivalem à anotação aleatória por três anotadores. Use-os apenas no treino (`split_and_balance.py --train-only-origem revisao_sistema`) e nunca no teste.

## 8. Testes

```
python -m pytest -q
```
