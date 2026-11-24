"""Testes da carga (Parte 3).

Os dois primeiros não usam banco. Os demais rodam no PostgreSQL do .env, mas num esquema temporário
(teste_carga), criado e apagado pelo próprio teste: as tabelas do ETL, no esquema public, não são
tocadas. Sem banco disponível, esses testes são pulados e aparecem como "skipped" na saída do
pytest. Os valores esperados estão escritos à mão.
"""

import os
from datetime import date
from decimal import Decimal

import pytest
from dotenv import dotenv_values

from etl.carga import ErroCarga, carregar, conectar, contar_linhas, parametros_conexao
from etl.extracao import RAIZ

AMBIENTE = {
    "PGHOST": "localhost",
    "PGPORT": "5433",
    "PGDATABASE": "verdejar",
    "PGUSER": "postgres",
    "PGPASSWORD": "senha_de_teste",
}


# --- sem banco ---


def test_parametros_conexao_le_as_cinco_variaveis():
    assert parametros_conexao(AMBIENTE) == {
        "host": "localhost",
        "port": "5433",
        "dbname": "verdejar",
        "user": "postgres",
        "password": "senha_de_teste",
    }


def test_parametros_conexao_sem_variavel_vira_erro_que_nao_mostra_a_senha():
    ambiente = {**AMBIENTE, "PGPORT": ""}  # vazia conta como ausente
    del ambiente["PGUSER"]

    with pytest.raises(ErroCarga) as erro:
        parametros_conexao(ambiente)

    assert "faltam as variaveis de ambiente ['PGPORT', 'PGUSER']" in str(erro.value)
    assert "senha_de_teste" not in str(erro.value)


# --- com banco, num esquema temporário ---


@pytest.fixture
def conexao():
    """Conexão com search_path no esquema teste_carga, com as tabelas do schema.sql vazias."""
    # O .env vai para um dicionário, e não para o os.environ: o load_dotenv deixaria as variáveis
    # PG* valendo para os testes seguintes, e um teste do main gravaria dados falsos no banco real.
    ambiente = {**dotenv_values(RAIZ / ".env"), **os.environ}  # o ambiente vence, como no main
    try:
        conexao = conectar(ambiente)
    except ErroCarga as erro:
        pytest.skip(f"PostgreSQL indisponivel: {erro}")
    with conexao:
        conexao.execute("DROP SCHEMA IF EXISTS teste_carga CASCADE")  # sobra de teste interrompido
        conexao.execute("CREATE SCHEMA teste_carga")
        conexao.execute("SET search_path TO teste_carga")
        # Trava de segurança: o TRUNCATE da carga nunca pode cair nas tabelas reais (public).
        assert conexao.execute("SELECT current_schema()").fetchone() == ("teste_carga",)
        conexao.execute((RAIZ / "insumos" / "schema.sql").read_text(encoding="utf-8"))
        try:
            yield conexao
        finally:
            conexao.execute("DROP SCHEMA teste_carga CASCADE")


def dados_pequenos() -> dict[str, list[dict]]:
    """Linhas no formato que a transformação devolve: 2 produtos, 2 clientes, 2 pedidos, 3 itens."""
    return {
        "produtos": [
            {
                "produto_id": 1,
                "nome": "Alface",
                "categoria": "folhas",
                "preco_base": Decimal("3.50"),
            },
            {
                "produto_id": 2,
                "nome": "Tomate",
                "categoria": "legumes",
                "preco_base": Decimal("8.90"),
            },
        ],
        "clientes": [
            {
                "id": 10,
                "nome": "Joana D'Arc",  # o apóstrofo quebraria um SQL montado com texto
                "email": None,
                "cidade": "Porto Alegre",
                "estado": "RS",
                "cadastro_em": date(2025, 1, 31),
            },
            {
                "id": 11,
                "nome": "Robert'); DROP TABLE clientes; --",  # vira dado, nunca comando
                "email": "rob@exemplo.com",
                "cidade": "Curitiba",
                "estado": "PR",
                "cadastro_em": date(2025, 2, 1),
            },
        ],
        "pedidos": [
            {
                "id": 100,
                "cliente_id": 10,
                "data_pedido": date(2026, 2, 19),
                "status": "entregue",
                "valor_total": Decimal("20.90"),
                "valor_itens": Decimal("15.90"),
                "divergente": True,
            },
            {
                "id": 101,
                "cliente_id": 11,
                "data_pedido": date(2026, 3, 5),
                "status": "cancelado",
                "valor_total": Decimal("8.90"),
                "valor_itens": Decimal("8.90"),
                "divergente": False,
            },
        ],
        "itens_pedido": [
            {
                "pedido_id": 100,
                "linha": 1,
                "produto_id": 1,
                "quantidade": 2,
                "preco_unitario": Decimal("3.50"),
            },
            {
                "pedido_id": 100,
                "linha": 2,
                "produto_id": 2,
                "quantidade": 1,
                "preco_unitario": Decimal("8.90"),
            },
            {
                "pedido_id": 101,
                "linha": 1,
                "produto_id": 2,
                "quantidade": 1,
                "preco_unitario": Decimal("8.90"),
            },
        ],
    }


def test_carga_duas_vezes_seguidas_deixa_as_mesmas_contagens(conexao):
    esperado = {"clientes": 2, "produtos": 2, "pedidos": 2, "itens_pedido": 3}

    carregar(conexao, dados_pequenos())
    assert contar_linhas(conexao) == esperado

    carregar(conexao, dados_pequenos())
    assert contar_linhas(conexao) == esperado  # a segunda carga não duplica nada


def test_carga_grava_os_valores_como_vieram(conexao):
    carregar(conexao, dados_pequenos())

    clientes = conexao.execute(
        "SELECT id, nome, email, estado, cadastro_em FROM clientes ORDER BY id"
    ).fetchall()
    pedido = conexao.execute(
        "SELECT data_pedido, valor_total, valor_itens, divergente FROM pedidos WHERE id = %s",
        (100,),
    ).fetchone()

    assert clientes == [
        (10, "Joana D'Arc", None, "RS", date(2025, 1, 31)),
        (11, "Robert'); DROP TABLE clientes; --", "rob@exemplo.com", "PR", date(2025, 2, 1)),
    ]
    assert pedido == (date(2026, 2, 19), Decimal("20.90"), Decimal("15.90"), True)


def test_carga_com_erro_desfaz_tudo_e_mantem_a_carga_anterior(conexao):
    carregar(conexao, dados_pequenos())
    com_erro = dados_pequenos()
    com_erro["clientes"].append(
        {
            "id": 12,
            "nome": "Bia",
            "email": None,
            "cidade": "Pelotas",
            "estado": "RS",
            "cadastro_em": date(2025, 3, 1),
        }
    )
    com_erro["itens_pedido"].append(  # produto 99 não existe: viola a chave estrangeira
        {
            "pedido_id": 101,
            "linha": 2,
            "produto_id": 99,
            "quantidade": 1,
            "preco_unitario": Decimal("1.00"),
        }
    )

    with pytest.raises(ErroCarga, match=r"tabela itens_pedido: .*\(produto_id\)=\(99\)"):
        carregar(conexao, com_erro)

    # Sem a transação, o TRUNCATE e a cliente 12 teriam ficado gravados: seriam 3 clientes.
    assert contar_linhas(conexao) == {"clientes": 2, "produtos": 2, "pedidos": 2, "itens_pedido": 3}
