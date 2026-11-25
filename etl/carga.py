"""Carga (Parte 3).

Responsabilidades:
- conectar ao PostgreSQL com as credenciais de variáveis de ambiente (nunca no código);
- carregar na ordem das chaves estrangeiras: produtos, clientes, pedidos, itens_pedido;
- garantir idempotência: cada execução substitui o conteúdo das quatro tabelas, numa transação só;
- usar consultas parametrizadas.

Estratégia de idempotência (detalhada no README): TRUNCATE das quatro tabelas e INSERT de tudo,
dentro de uma única transação. Rodar duas vezes com os mesmos brutos deixa o banco igual. Se algo
falhar no meio, a transação é desfeita e o banco continua com o conteúdo da execução anterior.
"""

import os
from collections.abc import Mapping

import psycopg

TIMEOUT_SEGUNDOS = 10

# Variável de ambiente (carregada do .env pelo main) -> parâmetro de conexão do psycopg.
VARIAVEIS_CONEXAO = {
    "PGHOST": "host",
    "PGPORT": "port",
    "PGDATABASE": "dbname",
    "PGUSER": "user",
    "PGPASSWORD": "password",
}

# Pais antes dos filhos: itens_pedido aponta para pedidos e produtos; pedidos aponta para clientes.
ORDEM_CARGA = ("produtos", "clientes", "pedidos", "itens_pedido")

# Limpa as quatro tabelas de uma vez. Como todas as tabelas ligadas por chave estrangeira estão na
# lista, o PostgreSQL aceita sem CASCADE.
SQL_LIMPAR = "TRUNCATE itens_pedido, pedidos, clientes, produtos"

# Cada %(campo)s é um parâmetro: o psycopg envia os valores separados do texto do SQL, e o banco
# nunca interpreta um dado como comando. Os nomes são as chaves dos dicionários da transformação.
SQL_INSERIR = {
    "produtos": (
        "INSERT INTO produtos (produto_id, nome, categoria, preco_base) "
        "VALUES (%(produto_id)s, %(nome)s, %(categoria)s, %(preco_base)s)"
    ),
    "clientes": (
        "INSERT INTO clientes (id, nome, email, cidade, estado, cadastro_em) "
        "VALUES (%(id)s, %(nome)s, %(email)s, %(cidade)s, %(estado)s, %(cadastro_em)s)"
    ),
    "pedidos": (
        "INSERT INTO pedidos "
        "(id, cliente_id, data_pedido, status, valor_total, valor_itens, divergente) "
        "VALUES (%(id)s, %(cliente_id)s, %(data_pedido)s, %(status)s, "
        "%(valor_total)s, %(valor_itens)s, %(divergente)s)"
    ),
    "itens_pedido": (
        "INSERT INTO itens_pedido (pedido_id, linha, produto_id, quantidade, preco_unitario) "
        "VALUES (%(pedido_id)s, %(linha)s, %(produto_id)s, %(quantidade)s, %(preco_unitario)s)"
    ),
}

SQL_CONTAR = (
    "SELECT (SELECT COUNT(*) FROM clientes), (SELECT COUNT(*) FROM produtos), "
    "(SELECT COUNT(*) FROM pedidos), (SELECT COUNT(*) FROM itens_pedido)"
)


class ErroCarga(Exception):
    """Falha prevista na carga, com uma mensagem clara (e sem a senha) para quem roda o ETL."""


def resumir(erro: psycopg.Error) -> str:
    """Mensagem do psycopg numa linha só: a principal e, se o servidor mandou, o detalhe.

    Exemplo: 'insert or update on table "itens_pedido" violates foreign key constraint ...
    (Key (produto_id)=(99) is not present in table "produtos".)'
    """
    principal = erro.diag.message_primary or str(erro).partition("\n")[0]
    detalhe = erro.diag.message_detail
    return f"{principal} ({detalhe})" if detalhe else principal


def parametros_conexao(ambiente: Mapping[str, str]) -> dict[str, str]:
    """Monta os parâmetros de conexão a partir das variáveis de ambiente PG*.

    Exige as cinco: sem PGPORT, por exemplo, o psycopg usaria a 5432, que nesta máquina é outro
    banco. A mensagem de erro cita só os nomes das variáveis que faltam, nunca os valores.
    """
    faltando = [nome for nome in VARIAVEIS_CONEXAO if not ambiente.get(nome)]
    if faltando:
        raise ErroCarga(f"faltam as variaveis de ambiente {faltando} (veja o .env.example)")
    return {parametro: ambiente[nome] for nome, parametro in VARIAVEIS_CONEXAO.items()}


def conectar(ambiente: Mapping[str, str] = os.environ) -> psycopg.Connection:
    """Abre a conexão em autocommit: as transações são abertas de forma explícita, onde importam."""
    parametros = parametros_conexao(ambiente)
    try:
        return psycopg.connect(**parametros, autocommit=True, connect_timeout=TIMEOUT_SEGUNDOS)
    except psycopg.OperationalError as erro:
        raise ErroCarga(
            f"sem conexao com o PostgreSQL em {parametros['host']}:{parametros['port']}/"
            f"{parametros['dbname']}: {resumir(erro)}. O banco esta rodando? "
            "(docker start verdejar-pg)"
        ) from None


def carregar(conexao: psycopg.Connection, dados: Mapping[str, list[dict]]) -> None:
    """Substitui o conteúdo das quatro tabelas pelas linhas de `dados`, numa transação só.

    `dados` é o que a transformação devolve: uma lista de dicionários por tabela. Se qualquer passo
    falhar, a transação é desfeita (nada do que foi limpo ou inserido fica valendo) e a função
    levanta ErroCarga dizendo em que etapa parou.
    """
    etapa = "limpeza das tabelas"
    try:
        with conexao.transaction(), conexao.cursor() as cursor:
            cursor.execute(SQL_LIMPAR)
            for tabela in ORDEM_CARGA:
                etapa = f"tabela {tabela}"
                cursor.executemany(SQL_INSERIR[tabela], dados[tabela])
    except psycopg.Error as erro:
        raise ErroCarga(f"{etapa}: {resumir(erro)}") from None


def contar_linhas(conexao: psycopg.Connection) -> dict[str, int]:
    """Conta as linhas de cada tabela, lidas do banco (e não do que o ETL acha que gravou)."""
    try:
        with conexao.cursor() as cursor:
            cursor.execute(SQL_CONTAR)
            clientes, produtos, pedidos, itens = cursor.fetchone()
    except psycopg.Error as erro:
        raise ErroCarga(f"contagem das tabelas: {resumir(erro)}") from None
    return {"clientes": clientes, "produtos": produtos, "pedidos": pedidos, "itens_pedido": itens}


def executar_carga(dados: Mapping[str, list[dict]]) -> dict[str, int]:
    """Conecta, carrega e devolve as contagens de cada tabela, lidas depois do commit."""
    with conectar() as conexao:
        carregar(conexao, dados)
        return contar_linhas(conexao)
