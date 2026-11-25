"""Testes da reconciliação (Parte 4, atividade 18).

Depois da carga, a reconciliação compara a origem (os brutos) com o destino (o banco):
- a contagem de pedidos únicos da origem com a contagem na tabela pedidos;
- a soma de valor_itens da origem com a soma no destino, com tolerância de 1 centavo.

Os valores esperados estão escritos à mão, com a conta ao lado. Os testes com banco usam as
fixtures de tests/conftest.py e são pulados sem PostgreSQL.
"""

from decimal import Decimal

import pytest

from etl.carga import carregar
from etl.extracao import ErroExtracao, ler_bruto
from etl.reconciliacao import comparar, resumir_destino, resumir_origem
from etl.transformacao import transformar

# Origem pequena, no formato dos brutos (como a API manda). O pedido 10 aparece duas vezes (A5).
CLIENTES_BRUTOS = [
    {
        "id": 1,
        "nome": "Ana Lima",
        "email": None,
        "cidade": "Porto Alegre",
        "estado": "rs",
        "cadastro_em": "2024-01-10",
    },
    {
        "id": 2,
        "nome": "Bruno Costa",
        "email": "bruno@exemplo.com",
        "cidade": "Campinas",
        "estado": "SP",
        "cadastro_em": "2025-06-01",
    },
]

PRODUTOS_BRUTOS = [
    {"produto_id": "1", "nome": "Alface crespa", "categoria": "folhas", "preco_base": "3.5"},
    {"produto_id": "2", "nome": "Tomate", "categoria": "legumes", "preco_base": "8.9"},
]

PEDIDO_10 = {
    "id": 10,
    "cliente_id": 1,
    "data_pedido": "2026-01-05",
    "status": "entregue",
    "valor_total": "7,00",
    "itens": [{"produto_id": 1, "quantidade": 2, "preco_unitario": 3.5}],
}  # itens: 2 x 3.50 = 7.00

PEDIDOS_BRUTOS = [
    PEDIDO_10,
    {
        "id": 11,
        "cliente_id": 2,
        "data_pedido": "31/01/2026",
        "status": "cancelado",
        "valor_total": 20.0,
        "itens": [
            {"produto_id": 1, "quantidade": 1, "preco_unitario": 3.5},
            {"produto_id": 2, "quantidade": 3, "preco_unitario": 8.9},
        ],
    },  # itens: 3.50 + 3 x 8.90 = 30.20 (divergente: o total diz 20.00)
    dict(PEDIDO_10),  # repetido, com o mesmo conteúdo: não pode entrar duas vezes na conta
    {
        "id": 12,
        "cliente_id": 1,
        "data_pedido": "01/02/2026",
        "status": "em_transporte",
        "valor_total": "12,35",
        "itens": [
            {"produto_id": 2, "quantidade": 1, "preco_unitario": 8.9},
            {"produto_id": 1, "quantidade": 1, "preco_unitario": 3.45},
        ],
    },  # itens: 8.90 + 3.45 = 12.35
]
# Conta à mão: 3 pedidos únicos (10, 11 e 12); soma = 7.00 + 30.20 + 12.35 = 49.55.


# --- origem (sem banco) ---


def test_origem_conta_os_pedidos_unicos_e_soma_os_itens_sem_repetir():
    resultado = resumir_origem(PEDIDOS_BRUTOS)

    # Contar os brutos daria 4 pedidos, e somar o repetido daria 56.55.
    assert resultado == {"pedidos": 3, "soma_valor_itens": Decimal("49.55")}


@pytest.mark.parametrize(
    ("itens", "soma"),
    [
        ([{"quantidade": 2, "preco_unitario": 3.5}], "7.00"),  # 7.0 sai com duas casas
        (
            [{"quantidade": 1, "preco_unitario": 0.1}, {"quantidade": 1, "preco_unitario": 0.2}],
            "0.30",  # em float, 0.1 + 0.2 = 0.30000000000000004
        ),
        # Meio centavo arredonda para cima. Decimal(2.675) direto do float é 2.67499999... e
        # daria 2.67: o preço precisa passar por str() antes.
        ([{"quantidade": 1, "preco_unitario": 2.675}], "2.68"),
        ([], "0.00"),  # pedido sem itens
    ],
)
def test_origem_soma_em_decimal_com_duas_casas(itens, soma):
    resultado = resumir_origem([{"id": 1, "itens": itens}])

    assert isinstance(resultado["soma_valor_itens"], Decimal)
    assert str(resultado["soma_valor_itens"]) == soma


def test_origem_sem_pedidos_tem_contagem_e_soma_zero():
    resultado = resumir_origem([])

    assert resultado == {"pedidos": 0, "soma_valor_itens": Decimal("0.00")}
    assert str(resultado["soma_valor_itens"]) == "0.00"


def test_origem_usa_a_primeira_ocorrencia_do_pedido_repetido():
    # A regra da A5: fica a primeira ocorrência. Os dados reais repetem o mesmo conteúdo, mas
    # se o conteúdo mudasse, a origem tem que contar o mesmo pedido que foi carregado.
    pedidos = [
        {"id": 5, "itens": [{"quantidade": 1, "preco_unitario": 1.0}]},
        {"id": 5, "itens": [{"quantidade": 1, "preco_unitario": 99.0}]},
    ]

    assert resumir_origem(pedidos) == {"pedidos": 1, "soma_valor_itens": Decimal("1.00")}


# --- comparação (sem banco) ---

ORIGEM = {"pedidos": 3, "soma_valor_itens": Decimal("49.55")}


@pytest.mark.parametrize(
    ("pedidos_destino", "soma_destino", "diferenca_pedidos", "diferenca_soma", "confere"),
    [
        (3, "49.55", 0, "0.00", True),  # origem e destino iguais
        (3, "49.54", 0, "0.01", True),  # 1 centavo a menos: tolerado
        (3, "49.56", 0, "-0.01", True),  # 1 centavo a mais: tolerado
        (3, "49.53", 0, "0.02", False),  # mais de 1 centavo
        (3, "49.57", 0, "-0.02", False),
        (2, "49.55", 1, "0.00", False),  # faltou um pedido: nenhuma tolerância na contagem
        (4, "49.55", -1, "0.00", False),  # pedido a mais (por exemplo, um repetido)
    ],
)
def test_comparar_tolera_um_centavo_na_soma_e_nenhum_pedido_na_contagem(
    pedidos_destino, soma_destino, diferenca_pedidos, diferenca_soma, confere
):
    destino = {"pedidos": pedidos_destino, "soma_valor_itens": Decimal(soma_destino)}

    resultado = comparar(ORIGEM, destino)

    # As diferenças são origem menos destino: positiva quando falta algo no destino.
    assert resultado == {
        "pedidos_origem": 3,
        "pedidos_destino": pedidos_destino,
        "diferenca_pedidos": diferenca_pedidos,
        "soma_valor_itens_origem": Decimal("49.55"),
        "soma_valor_itens_destino": Decimal(soma_destino),
        "diferenca_soma": Decimal(diferenca_soma),
        "confere": confere,
    }
    assert str(resultado["diferenca_soma"]) == diferenca_soma  # sai como 0.00, não como 0


# --- depois da carga, no esquema temporário (fixture conexao) ---


def test_destino_vazio_tem_contagem_e_soma_zero(conexao):
    # Sem COALESCE, o SUM de uma tabela vazia viria NULL (None) e a comparação quebraria.
    assert resumir_destino(conexao) == {"pedidos": 0, "soma_valor_itens": Decimal("0.00")}


def test_reconciliacao_depois_da_carga_confere(conexao):
    dados, _ = transformar(CLIENTES_BRUTOS, PEDIDOS_BRUTOS, PRODUTOS_BRUTOS)
    carregar(conexao, dados)

    destino = resumir_destino(conexao)
    resultado = comparar(resumir_origem(PEDIDOS_BRUTOS), destino)

    assert destino == {"pedidos": 3, "soma_valor_itens": Decimal("49.55")}
    assert resultado["confere"] is True
    assert resultado["diferenca_pedidos"] == 0
    assert str(resultado["diferenca_soma"]) == "0.00"


def test_reconciliacao_acusa_pedido_que_nao_chegou_ao_destino(conexao):
    dados, _ = transformar(CLIENTES_BRUTOS, PEDIDOS_BRUTOS, PRODUTOS_BRUTOS)
    carregar(conexao, dados)
    # Simula uma carga incompleta: o pedido 12 (itens 12.35) some do destino.
    conexao.execute("DELETE FROM itens_pedido WHERE pedido_id = %s", (12,))
    conexao.execute("DELETE FROM pedidos WHERE id = %s", (12,))

    resultado = comparar(resumir_origem(PEDIDOS_BRUTOS), resumir_destino(conexao))

    assert resultado["confere"] is False
    assert resultado["pedidos_destino"] == 2
    assert resultado["diferenca_pedidos"] == 1
    assert resultado["diferenca_soma"] == Decimal("12.35")


# --- a última carga real do ETL (fixture destino_real, só leitura) ---


def test_reconciliacao_da_ultima_carga_do_etl(destino_real):
    try:
        pedidos_brutos = ler_bruto("pedidos")
    except ErroExtracao as erro:
        pytest.skip(f"sem os brutos da ultima extracao: {erro}")

    resultado = comparar(resumir_origem(pedidos_brutos), resumir_destino(destino_real))

    # 5000 pedidos únicos, como na linha "carga:" do exemplo de saída do enunciado (seção 4).
    assert resultado["pedidos_origem"] == 5000
    assert resultado["pedidos_destino"] == 5000
    assert abs(resultado["diferenca_soma"]) <= Decimal("0.01")
    assert resultado["confere"] is True
    # Terceira fonte, dentro do destino: a soma recalculada a partir da tabela itens_pedido.
    (soma_dos_itens,) = destino_real.execute(
        "SELECT SUM(quantidade * preco_unitario) FROM itens_pedido"
    ).fetchone()
    assert soma_dos_itens == resultado["soma_valor_itens_destino"]
