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

_Extração → brutos → transformação (A1–A6) → carga → reconciliação._

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
acha que gravou. Duas execuções seguidas de `python -m etl.main`, com saídas idênticas (`diff` sem diferenças):

```text
extracao: clientes paginas=20 registros=1000
extracao: pedidos paginas=102 registros_brutos=5100
extracao: produtos registros=12
extracao: brutos salvos em brutos/ (clientes.json, pedidos.json, produtos.json)
transformacao: pedidos_unicos=5000 repetidos_descartados=100
transformacao: emails_nulos=81 estados_padronizados=151 datas_convertidas=1037 valores_convertidos=1255
carga: clientes=1000 produtos=12 pedidos=5000 itens=12455
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
divergentes: 238 pedidos com valor_total diferente da soma dos itens
```

Os testes de `tests/test_carga.py` também cobrem isso: carregar duas vezes deixa as mesmas contagens, e uma carga com erro
desfaz tudo e mantém a anterior. Eles rodam num esquema temporário (`teste_carga`), sem tocar nas tabelas do ETL.

## Resultados das consultas de validação

_Resultados de `consultas_validacao.sql`: (a) vendas por mês e o teste de consulta, (b) pedidos por estado, (c) divergentes._

## Saída do pytest

```text
(colar aqui)
```

## Uso de IA no desenvolvimento do projeto

Registro completo em [`COMO_USEI_IA.md`](COMO_USEI_IA.md).

---

## Fluxo de trabalho 

- Eu escrevo o ETL. O agente do Claude Code é um **Par com escopo limitado** (regras em `AGENTS.md`).
- `/data-engineer <pedido>`: o agente propõe **uma** função ou um teste, explica linha por linha e só aplica com o meu OK.
- `/revisar`: numa **sessão nova**, o agente revisa o branch e a rubrica (D1–D6), sem editar nada.
- Os commits são sempre meus. As permissões do agente bloqueiam `git commit` e `git push`.

