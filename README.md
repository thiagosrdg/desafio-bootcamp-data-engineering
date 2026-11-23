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

## Biblioteca de conexão

_Qual biblioteca foi usada, por quê e como instalar._

## Como funciona

_Extração → brutos → transformação (A1–A6) → carga → reconciliação._

## Estratégia de idempotência

_Qual estratégia foi escolhida, por quê, e a saída de duas execuções seguidas com as mesmas contagens._

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

