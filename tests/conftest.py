"""Fixtures dos testes que usam o PostgreSQL (carga, reconciliação e consultas de validação).

As credenciais vêm do .env e das variáveis de ambiente. Sem banco disponível, os testes que usam
estas fixtures são pulados e aparecem como "skipped" na saída do pytest.
"""

import os

import psycopg
import pytest
from dotenv import dotenv_values

from etl.carga import ErroCarga, conectar
from etl.extracao import RAIZ


def conectar_ou_pular() -> psycopg.Connection:
    """Conecta ao PostgreSQL do .env ou pula o teste, se o banco não estiver disponível."""
    # O .env vai para um dicionário, e não para o os.environ: o load_dotenv deixaria as variáveis
    # PG* valendo para os testes seguintes, e um teste do main gravaria dados falsos no banco real.
    ambiente = {**dotenv_values(RAIZ / ".env"), **os.environ}  # o ambiente vence, como no main
    try:
        return conectar(ambiente)
    except ErroCarga as erro:
        pytest.skip(f"PostgreSQL indisponivel: {erro}")


@pytest.fixture
def conexao():
    """Conexão com search_path no esquema temporário teste_etl, com as tabelas do schema.sql vazias.

    O esquema é criado e apagado pelo próprio teste: as tabelas do ETL, no esquema public, não são
    tocadas.
    """
    conexao = conectar_ou_pular()
    with conexao:
        conexao.execute("DROP SCHEMA IF EXISTS teste_etl CASCADE")  # sobra de teste interrompido
        conexao.execute("CREATE SCHEMA teste_etl")
        conexao.execute("SET search_path TO teste_etl")
        # Trava de segurança: o TRUNCATE da carga nunca pode cair nas tabelas reais (public).
        assert conexao.execute("SELECT current_schema()").fetchone() == ("teste_etl",)
        conexao.execute((RAIZ / "insumos" / "schema.sql").read_text(encoding="utf-8"))
        try:
            yield conexao
        finally:
            conexao.execute("DROP SCHEMA teste_etl CASCADE")


@pytest.fixture
def destino_real():
    """Conexão só de leitura com as tabelas do ETL (esquema public), para conferir a última carga.

    Pula o teste se o banco estiver fora do ar ou se a tabela pedidos estiver vazia (o ETL ainda
    não rodou). A sessão fica em modo só leitura: qualquer INSERT, DELETE ou TRUNCATE é recusado.
    """
    conexao = conectar_ou_pular()
    with conexao:
        conexao.execute("SET default_transaction_read_only = on")
        conexao.execute("SET search_path TO public")
        try:
            vazia = conexao.execute("SELECT COUNT(*) FROM pedidos").fetchone() == (0,)
        except psycopg.Error as erro:
            pytest.skip(f"tabelas do ETL indisponiveis: {erro}")
        if vazia:
            pytest.skip("a tabela pedidos esta vazia: rode python -m etl.main antes")
        yield conexao
