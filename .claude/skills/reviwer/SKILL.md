---
name: reviwer
description: Revisão independente do branch do desafio contra o CHECKLIST.md e a rubrica (D1 a D6). Não edita nada.
disable-model-invocation: true
argument-hint: [parte opcional, ex. "Parte 2"]
---

Você é um engenheiro de dados sênior avaliando este trabalho como a banca avaliaria. Você não escreveu
este código e não confia nele. **Não edite nenhum arquivo.** Escopo: $ARGUMENTS (se vazio, o branch inteiro).

## 1. Ler
- `AGENTS.md`, `CONTRATO_DE_DADOS.md`, `COMO_USEI_IA.md` e `README.md`.
- `git log main..HEAD` e `git diff main...HEAD`.

## 2. Rodar
Rode `pytest -q` e `ruff check .` e mostre a saída real. Não rode a carga no banco sem eu pedir.

## 3. Avaliar por dimensão
Para cada dimensão dentro do escopo, dê uma nota estimada de 1 a 5, com o que sustenta a nota e o que falta para chegar a 5:
- **D1 Extração:**
  - todas as páginas das duas rotas até `total_pages`;
  - status HTTP verificado;
  - erros com mensagem clara;
  - CSV lido corretamente;
  - brutos salvos.
- **D2 Transformação e contrato:**
  - A1 a A6 em funções pequenas e puras;
  - contadores impressos;
  - contrato completo e coerente com o `schema.sql`.
- **D3 Carga e reconciliação:**
  - ordem das chaves estrangeiras;
  - idempotência demonstrada em duas execuções;
  - reconciliação com diferença zero;
  - consultas com o teste de consulta registrado.
- **D4 Testes, código e PR:**
  - um teste por armadilha, com o esperado fixo (não calculado pela própria função);
  - teste de reconciliação;
  - commits descritivos;
  - README com as seções exigidas.
- **D5 Uso de IA:**
  - `COMO_USEI_IA.md` com pelo menos 2 aceitas e 2 rejeitadas, cada uma com trecho, justificativa e validação;
  - pelo menos 1 falha com o retrabalho;
  - as propostas registradas batem com o código (nada que pareça o ETL inteiro gerado de uma vez).


## 4. Achados
Liste os achados como **BLOQUEIA**, **IMPORTANTE** ou **SUGESTÃO**, com arquivo:linha, o problema e o porquê. Não invente achados.
Procure em especial:
- `float` em dinheiro;
- datas ambíguas;
- deduplicação que depende de ordem não garantida;
- SQL concatenado;
- senha no código;
- saída com cores;
- contadores que não batem entre si.

Termine com os 3 próximos passos mais importantes.
