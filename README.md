# ETL - Desafio Final do Bootcamp Data Engineering da AI/R Compass

ETL da Verdejar, uma loja fictícia de hortifrúti. Os clientes e os pedidos vêm de uma API local paginada, e os produtos,
de um CSV. Tudo vai para um PostgreSQL, com seis problemas de qualidade (A1 a A6) tratados e a carga reconciliada.
Os dados são sintéticos.

## Requisitos

- Python 3.12+
- Docker (usado para o PostgreSQL)
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

- **Banco:** caminho B da errata v3, com o PostgreSQL 16 no contêiner Docker `verdejar-pg`, na porta **5433**. Para subir
  o contêiner de novo: `docker start verdejar-pg`.
- **Biblioteca:** [psycopg 3](https://www.psycopg.org/psycopg3/) (`psycopg[binary]`, no `requirements.txt`). Converte
  `Decimal`, `date`, `bool` e `None` para os tipos do PostgreSQL e envia os parâmetros separados do texto do SQL.
- **Credenciais:** variáveis `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER` e `PGPASSWORD`, lidas do `.env` (fora do git)
  pelo `python-dotenv`.

## Como funciona

`python -m etl.main` roda as etapas abaixo, em ordem, e imprime os contadores de cada uma. Se uma etapa falha, o ETL
imprime `erro: <etapa>: <motivo>` e termina com código 1.

| Etapa | Arquivo | O que faz |
|---|---|---|
| Extração | `etl/extracao.py` | Lê todas as páginas de `/clientes` e `/pedidos` e o `produtos.csv`, e grava tudo em `brutos/` sem alterar nada. |
| Transformação | `etl/transformacao.py` | Lê `brutos/` e trata A1 a A6 (regras em [`CONTRATO_DE_DADOS.md`](CONTRATO_DE_DADOS.md)). |
| Carga | `etl/carga.py` | Recarrega as quatro tabelas numa transação só (ver idempotência). |
| Reconciliação | `etl/reconciliacao.py` | Compara `brutos/` com o banco: contagem de pedidos e soma de `valor_itens`. |

## Estratégia de idempotência

**Limpar e recarregar tudo, numa transação só** (função `carregar`, em `etl/carga.py`):

1. `TRUNCATE` das quatro tabelas, num só comando.
2. `INSERT` em `produtos`, `clientes`, `pedidos` e `itens_pedido`, nessa ordem (os pais antes dos filhos), com
   parâmetros `%(campo)s`.
3. Commit. Se algo falhar, a transação é desfeita e o banco continua com a carga anterior.

**Por que essa estratégia:** a extração traz sempre a origem inteira, então o banco deve ser um espelho dela. Limpar e
recarregar garante isso sem lógica extra.

**Prova:** duas execuções seguidas de `python -m etl.main` terminaram com código 0 e saídas idênticas (`diff` sem
diferenças). As contagens da linha `carga:` são lidas do banco depois do commit.

1ª execução:

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

2ª execução:

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

## Reconciliação

Roda logo depois do commit da carga (`etl/reconciliacao.py`):

| Item | Origem (`brutos/pedidos.json`) | Destino (banco) | Tolerância |
|---|---|---|---|
| Pedidos | ids distintos | `COUNT(*) FROM pedidos` | nenhuma |
| `valor_itens` | soma de `quantidade × preco_unitario` dos itens dos pedidos únicos | `SUM(valor_itens) FROM pedidos` | 1 centavo |

- A origem é calculada direto dos brutos, sem as funções da transformação. Assim, um pedido perdido na transformação ou
  na carga aparece como diferença.
- O destino é lido numa conexão nova, depois do commit, e por isso só conta o que ficou gravado.
- Se não conferir, o ETL imprime as diferenças e termina com código 1. Na última execução, as duas diferenças foram zero
  (saída acima).

## Testes

Rodam com `pytest -q` na raiz. Os valores esperados são escritos à mão, nunca calculados pela função testada.

| Arquivo | O que cobre |
|---|---|
| `tests/test_transformacao.py` | A1 a A6, com testes próprios para cada armadilha (prefixos `test_a1_` a `test_a6_`) |
| `tests/test_extracao.py` | paginação, erros da API e do CSV, brutos e a saída do `main` |
| `tests/test_carga.py` | idempotência, rollback e SQL parametrizado |
| `tests/test_reconciliacao.py` | origem, tolerância de 1 centavo e a reconciliação depois da carga |
| `tests/test_consultas.py` | as consultas de `consultas_validacao.sql`, com dados escritos à mão e na última carga |

Os testes com banco usam um esquema temporário (`teste_etl`), apagado no fim, ou leem a última carga numa sessão só de
leitura. Sem o PostgreSQL no ar, eles aparecem como `skipped`.

## Resultados das consultas de validação

As consultas estão em [`consultas_validacao.sql`](consultas_validacao.sql). Os resultados abaixo são da última carga,
obtidos com:

```bash
docker exec -i verdejar-pg psql -U postgres -d verdejar < consultas_validacao.sql
```

### (a) Total de vendas por mês

Entram todos os pedidos, de qualquer status. `valor_total` é o valor informado no pedido; `valor_itens` é a soma dos
itens (A6).

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

**Teste de consulta:** a soma dos meses é igual à soma geral da tabela, nas três colunas.

```text
     conta      | pedidos | valor_total | valor_itens
----------------+---------+-------------+-------------
 soma dos meses |    5000 |   312047.75 |   311228.75
 soma geral     |    5000 |   312047.75 |   311228.75
(2 rows)
```

### (b) Quantidade de pedidos por estado

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

São 238 pedidos, o mesmo número da linha `divergentes:` do ETL. Abaixo estão as 5 primeiras linhas
(`diferenca = valor_total - valor_itens`):

```text
  id  | cliente_id | data_pedido |    status     | valor_total | valor_itens | diferenca
------+------------+-------------+---------------+-------------+-------------+-----------
    1 |        303 | 2026-02-19  | entregue      |      125.84 |      130.84 |     -5.00
   51 |         23 | 2026-04-27  | cancelado     |       26.58 |       23.58 |      3.00
   71 |        962 | 2026-05-27  | cancelado     |      144.35 |      134.35 |     10.00
   81 |        198 | 2026-09-05  | entregue      |       -1.84 |        3.16 |     -5.00
  106 |        973 | 2026-05-02  | em_transporte |       47.78 |       44.78 |      3.00
```

Resumo por diferença: a origem só tem três deslocamentos.

```text
 diferenca | pedidos
-----------+---------
      3.00 |      88
     10.00 |      87
     -5.00 |      63
(3 rows)
```

## Saída do pytest

Com o PostgreSQL e a última carga disponíveis:

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

- O agente do Claude Code é um **Par com escopo limitado** (regras em `AGENTS.md`).
- `/data-engineer <pedido>`: o agente propõe **uma** função ou um teste, explica linha por linha e só aplica com o meu OK.
- `/reviwer`: numa **sessão nova**, o agente revisa o branch e a rubrica (D1–D6), sem editar nada.
- Os commits são sempre meus. As permissões do agente bloqueiam `git commit` e `git push`.
