# ETL da Verdejar

Desafio do Bootcamp AI/R Fellowship (AI-Driven Data Engineering).

Este ETL leva os dados da Verdejar, uma loja fictícia de hortifrúti, para um banco PostgreSQL:

- os clientes e os pedidos vêm de uma API local paginada;
- os produtos vêm de um CSV.

No caminho, os dados são limpos e conferidos. Seis problemas de qualidade (A1 a A6) são tratados, e a carga é reconciliada.
Todos os dados são sintéticos.

## Requisitos

- Python 3.12+
- Docker (usado só para o PostgreSQL)
- Git

## Como rodar

```bash
# 1. ambiente Python
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
cp .env.example .env              # e troque a senha

# 2. API local (em outro terminal)
python insumos/api_verdejar.py --dados insumos/dados
curl http://127.0.0.1:8000/saude

# 3. PostgreSQL + esquema
docker run --name verdejar-pg -e POSTGRES_PASSWORD=<senha> -e POSTGRES_DB=verdejar -p 5433:5432 -d postgres:16
docker exec -i verdejar-pg psql -U postgres -d verdejar < insumos/schema.sql

# 4. ETL
python -m etl.main

# 5. testes
pytest -q
```

## Banco e biblioteca de conexão

- **Banco:** caminho B da errata v3, com o PostgreSQL 16 num contêiner Docker (`verdejar-pg`) na porta **5433**.
  A 5432 desta máquina já é usada por outro PostgreSQL, nativo. O contêiner já criado sobe de novo com
  `docker start verdejar-pg`.
- **Biblioteca:** [psycopg 3](https://www.psycopg.org/psycopg3/), instalada pelo `requirements.txt` (`psycopg[binary]`,
  que já traz a libpq, sem compilar nada). Ou, avulsa: `pip install "psycopg[binary]"`.
- **Por que o psycopg 3:** é o driver de PostgreSQL mais usado em Python e é mantido ativamente. Ele converte sozinho
  `Decimal`, `date`, `bool` e `None` para `NUMERIC`, `DATE`, `BOOLEAN` e `NULL`, e envia os parâmetros separados do texto do SQL.
- **Credenciais:** vêm das variáveis `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e `PGPASSWORD`, que o `python-dotenv` lê do `.env`
  (fora do git). A carga exige as cinco. Sem a `PGPORT`, por exemplo, ela iria para a 5432, que é o banco errado.

## Como funciona

`python -m etl.main` roda as quatro etapas em ordem. Cada uma imprime suas linhas de contadores (texto simples, uma
informação por linha). Se uma etapa falha, o ETL imprime `erro: <etapa>: <motivo>` na saída de erro e termina com código 1.

| Etapa | Arquivo | O que faz |
|---|---|---|
| Extração | `etl/extracao.py` | Percorre as páginas de `/clientes` e `/pedidos` e lê o `produtos.csv`. Grava tudo em `brutos/`, sem alterar nada. |
| Transformação | `etl/transformacao.py` | Lê os `brutos/` e trata A1 a A6 (regras em [`CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md)). |
| Carga | `etl/carga.py` | `TRUNCATE` e `INSERT` parametrizado das quatro tabelas, numa transação só (ver idempotência). |
| Reconciliação | `etl/reconciliacao.py` | Compara os `brutos/` com o banco: contagem de pedidos e soma de `valor_itens`. |

## Estratégia de idempotência

**Estratégia: limpar e recarregar tudo, numa transação só** (`etl/carga.py`, função `carregar`).

1. Abre uma transação.
2. `TRUNCATE itens_pedido, pedidos, clientes, produtos`, as quatro tabelas num só comando (assim o PostgreSQL aceita sem `CASCADE`).
3. Insere, nesta ordem, `produtos`, `clientes`, `pedidos` e `itens_pedido`: os pais antes dos filhos, por causa das
   chaves estrangeiras. Os INSERTs usam parâmetros `%(campo)s` com `executemany`, nunca texto concatenado com dados.
4. Faz o commit. Se qualquer passo falhar (por exemplo, um item com produto inexistente), a transação é desfeita, o banco
   continua com a carga anterior e o ETL termina com `erro: carga: tabela <nome>: <motivo>`.

**Por que essa estratégia:** a extração traz sempre a origem inteira, então o banco deve ser um espelho dela. Limpar e
recarregar garante isso sem lógica extra. As alternativas eram piores aqui:

- `INSERT ... ON CONFLICT DO NOTHING` não duplica, mas não atualiza um pedido que mudou na origem.
- `ON CONFLICT DO UPDATE` atualiza, mas não remove o que sumiu da origem, como um item retirado de um pedido.

Com 5000 pedidos, recarregar tudo leva poucos segundos. A transação também impede que alguém veja as tabelas vazias ou pela metade.

**Prova:** a linha `carga:` mostra as contagens lidas do banco depois do commit (`SELECT COUNT(*)`), e não o que o ETL
acha que gravou. Duas execuções seguidas de `python -m etl.main`, já com a reconciliação, com código de saída 0 e saídas
idênticas (`diff` sem diferenças):

```text
extracao: clientes paginas=20 registros=1000
extracao: pedidos paginas=102 registros_brutos=5100
extracao: produtos registros=12
extracao: brutos salvos em brutos/ (clientes.json, pedidos.json, produtos.json)
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
carga: clientes=1000 produtos=12 pedidos=5000 itens=12455
reconciliacao: pedidos_origem=5000 pedidos_destino=5000 diferenca=0
reconciliacao: soma_valor_itens_origem=311228.75 soma_valor_itens_destino=311228.75 diferenca=0.00
divergentes: 238 pedidos com valor_total diferente da soma dos itens
```

```text
extracao: clientes paginas=20 registros=1000
extracao: pedidos paginas=102 registros_brutos=5100
extracao: produtos registros=12
extracao: brutos salvos em brutos/ (clientes.json, pedidos.json, produtos.json)
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
carga: clientes=1000 produtos=12 pedidos=5000 itens=12455
reconciliacao: pedidos_origem=5000 pedidos_destino=5000 diferenca=0
reconciliacao: soma_valor_itens_origem=311228.75 soma_valor_itens_destino=311228.75 diferenca=0.00
divergentes: 238 pedidos com valor_total diferente da soma dos itens
```

Os testes de `tests/test_carga.py` também cobrem isso: carregar duas vezes deixa as mesmas contagens, e uma carga com erro
desfaz tudo e mantém a anterior. Eles rodam num esquema temporário (`teste_etl`), sem tocar nas tabelas do ETL.

## Reconciliação

**O que compara** (`etl/reconciliacao.py`), logo depois do commit da carga:

| Item | Origem: `brutos/pedidos.json` | Destino: banco | Tolerância |
|---|---|---|---|
| Pedidos | ids distintos nos brutos | `COUNT(*) FROM pedidos` | nenhuma |
| `valor_itens` | soma de `quantidade × preco_unitario` dos itens de cada pedido único | `SUM(valor_itens) FROM pedidos` | 1 centavo |

- **A origem é calculada sem a transformação.** Ela sai direto dos brutos, sem `transformar` nem `calcular_valor_itens`.
  Por isso a reconciliação confere a transformação e a carga juntas: um pedido ou item perdido em qualquer uma delas
  aparece como diferença.
- Um pedido repetido entra uma vez só, pela primeira ocorrência (a regra da A5). O preço vem da API como float e passa por
  `str()` antes do `Decimal`, para não trazer o erro binário do float.
- **O destino é lido numa conexão nova**, depois do commit. Assim ele só enxerga o que de fato ficou gravado.
- As diferenças são origem menos destino: são positivas quando falta algo no destino. Se não conferir, o ETL imprime as
  duas linhas `reconciliacao:` (para mostrar onde está a diferença), depois `erro: reconciliacao: origem e destino nao
  conferem ...`, e termina com código 1.

Resultado da última execução: a diferença é zero nas duas comparações.

```text
reconciliacao: pedidos_origem=5000 pedidos_destino=5000 diferenca=0
reconciliacao: soma_valor_itens_origem=311228.75 soma_valor_itens_destino=311228.75 diferenca=0.00
```

## Testes

Rodam com `pytest -q` na raiz do projeto. Os valores esperados estão escritos à mão, com a conta ao lado, e nunca são
calculados pela função testada.

| Arquivo | O que cobre | Banco |
|---|---|---|
| `tests/test_transformacao.py` | A1 a A6 (tabela abaixo), registros completos, contadores e erros com o registro identificado | não usa |
| `tests/test_extracao.py` | paginação, erros de rede, de HTTP e do CSV, brutos, e a saída do `main` no formato da seção 4 | não usa |
| `tests/test_carga.py` | variáveis de conexão, idempotência, rollback e SQL parametrizado (nome com apóstrofo e `DROP TABLE` gravados como dado) | `teste_etl` |
| `tests/test_reconciliacao.py` | origem (repetidos, `Decimal`), tolerância de 1 centavo, reconciliação depois da carga, pedido faltando e a última carga real | `teste_etl` e `public` |
| `tests/test_consultas.py` | as consultas do `consultas_validacao.sql`, com dados escritos à mão e na última carga real | `teste_etl` e `public` |

**Um teste por armadilha** (em `tests/test_transformacao.py`):

| Armadilha | Testes |
|---|---|
| A1 e-mail ausente | `test_a1_email_nulo_continua_nulo_e_o_cliente_e_mantido`, `test_a1_email_em_branco_vira_nulo`, `test_a1_email_preenchido_sai_sem_espacos_nas_pontas`, `test_a1_nao_altera_o_registro_recebido` |
| A2 sigla do estado | `test_a2_estado_sai_em_maiusculas`, `test_a2_estado_que_nao_e_sigla_de_duas_letras_vira_erro` |
| A3 data em dois formatos | `test_a3_converte_os_dois_formatos_para_date`, `test_a3_data_fora_dos_dois_formatos_vira_erro` |
| A4 valor com vírgula | `test_a4_converte_para_decimal_com_duas_casas`, `test_a4_arredonda_meio_centavo_para_cima_sem_erro_de_float`, `test_a4_valor_que_nao_e_numero_vira_erro` |
| A5 pedido repetido | `test_a5_remove_repetidos_pelo_id_mantendo_a_primeira_ocorrencia`, `test_a5_sem_repetidos_devolve_a_mesma_sequencia` |
| A6 divergência | `test_a6_soma_os_itens_e_marca_divergencia_acima_de_um_centavo`, `test_a6_nao_altera_o_pedido_recebido` |

**Testes com banco:** usam as fixtures de `tests/conftest.py`.

- `conexao`: cria um esquema temporário (`teste_etl`) com o `schema.sql`, e o apaga no fim. As tabelas do ETL não são tocadas.
- `destino_real`: lê as tabelas do ETL (esquema `public`) numa sessão só de leitura (`default_transaction_read_only`), em
  que qualquer `INSERT`, `DELETE` ou `TRUNCATE` é recusado. Pula o teste se a tabela `pedidos` estiver vazia, ou seja, se o
  ETL ainda não rodou.

Sem o PostgreSQL no ar, os testes com banco aparecem como `skipped`, e os demais rodam normalmente.

## Resultados das consultas de validação

As consultas estão em [`consultas_validacao.sql`](consultas_validacao.sql). Os resultados abaixo são da última carga,
obtidos com o comando abaixo (o `psql` de dentro do contêiner não pede senha):

```bash
docker exec -i verdejar-pg psql -U postgres -d verdejar < consultas_validacao.sql
```

O `tests/test_consultas.py` roda essas mesmas consultas, lidas do arquivo: primeiro num esquema temporário, com dados
escritos à mão e resultado esperado calculado à mão; depois na última carga real, só para leitura.

### (a) Total de vendas por mês

Entram todos os pedidos da tabela, de qualquer status, para que a soma dos meses possa ser comparada com a soma geral.
Há duas colunas de valor: `valor_total`, o valor informado no pedido, e `valor_itens`, a soma dos itens (A6), que é o
mesmo valor conferido pela reconciliação.

```text
   mes   | pedidos | valor_total | valor_itens 
---------+---------+-------------+-------------
 2026-01 |     488 |    30449.02 |    30355.02
 2026-02 |     536 |    33923.86 |    33855.86
 2026-03 |     487 |    30678.70 |    30617.70
 2026-04 |     521 |    31253.96 |    31170.96
 2026-05 |     512 |    30890.02 |    30777.02
 2026-06 |     523 |    31627.73 |    31557.73
 2026-07 |     519 |    32796.17 |    32685.17
 2026-08 |     458 |    29328.04 |    29260.04
 2026-09 |     476 |    29995.71 |    29909.71
 2026-10 |     480 |    31104.54 |    31039.54
(10 rows)
```

**Teste de consulta:** a soma dos meses é igual à soma geral da tabela, nas três colunas. O `valor_itens` geral
(311228.75) também é o valor da linha `reconciliacao:` do ETL.

```text
     conta      | pedidos | valor_total | valor_itens 
----------------+---------+-------------+-------------
 soma dos meses |    5000 |   312047.75 |   311228.75
 soma geral     |    5000 |   312047.75 |   311228.75
(2 rows)
```

### (b) Quantidade de pedidos por estado

O estado é o do cliente que fez o pedido. A soma dá os 5000 pedidos, e as siglas estão todas em maiúsculas (A2).

```text
 estado | pedidos 
--------+---------
 RS     |    1543
 SC     |    1127
 PR     |     974
 SP     |     880
 MG     |     476
(5 rows)
```

### (c) Pedidos divergentes

São 238 pedidos com `divergente = TRUE`, o mesmo número da linha `divergentes:` do ETL. Abaixo estão as 10 primeiras
das 238 linhas (`diferenca = valor_total - valor_itens`):

```text
  id  | cliente_id | data_pedido |    status     | valor_total | valor_itens | diferenca 
------+------------+-------------+---------------+-------------+-------------+-----------
    1 |        303 | 2026-02-19  | entregue      |      125.84 |      130.84 |     -5.00
   51 |         23 | 2026-04-27  | cancelado     |       26.58 |       23.58 |      3.00
   71 |        962 | 2026-05-27  | cancelado     |      144.35 |      134.35 |     10.00
   81 |        198 | 2026-09-05  | entregue      |       -1.84 |        3.16 |     -5.00
  106 |        973 | 2026-05-02  | em_transporte |       47.78 |       44.78 |      3.00
  176 |        286 | 2026-03-20  | em_transporte |      137.69 |      134.69 |      3.00
  186 |        306 | 2026-09-16  | em_transporte |      143.51 |      133.51 |     10.00
  289 |        779 | 2026-04-12  | cancelado     |       79.40 |       76.40 |      3.00
  303 |        344 | 2026-06-28  | em_transporte |      120.25 |      110.25 |     10.00
  326 |        547 | 2026-02-18  | entregue      |       10.58 |        7.58 |      3.00
```

Resumo por diferença (soma: 88 + 87 + 63 = 238). A origem só tem três deslocamentos (+3.00, +10.00 e −5.00). O pedido 81,
com `valor_total` de −1.84, é um desses casos: os itens somam 3.16, e o total veio 5.00 abaixo.

```text
 diferenca | pedidos 
-----------+---------
      3.00 |      88
     10.00 |      87
     -5.00 |      63
(3 rows)
```

## Saída do pytest

`pytest -q` com o PostgreSQL e a última carga do ETL disponíveis, sem nenhum teste pulado:

```text
$ pytest -q
........................................................................ [ 56%]
.......................................................                  [100%]
127 passed in 4.95s
```

## Uso de IA no desenvolvimento do projeto

Registro completo em [`COMO_USEI_IA.md`](COMO_USEI_IA.md).

---

## Fluxo de trabalho 

- Eu escrevo o ETL. O agente do Claude Code é um **Par com escopo limitado** (regras em `AGENTS.md`).
- `/data-engineer <pedido>`: o agente propõe **uma** função ou um teste, explica linha por linha e só aplica com o meu OK.
- `/reviwer`: numa **sessão nova**, o agente revisa o branch e a rubrica (D1–D6), sem editar nada.
- Os commits são sempre meus. As permissões do agente bloqueiam `git commit` e `git push`.

