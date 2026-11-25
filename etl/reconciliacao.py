"""Reconciliação (Parte 4).

Prova que a carga está completa e correta, comparando a origem com o destino:
- pedidos: a quantidade de pedidos únicos nos brutos e a quantidade de linhas na tabela pedidos;
- valor_itens: a soma de quantidade x preco_unitario dos itens nos brutos e a soma de
  pedidos.valor_itens no banco, com tolerância de 1 centavo.

O lado da origem é calculado direto dos brutos, sem usar as funções da transformação. Assim a
reconciliação confere a transformação e a carga juntas: um pedido ou item perdido em qualquer uma
das duas aparece como diferença. O lado do destino é lido numa conexão nova, depois do commit da
carga, e por isso só enxerga o que de fato ficou gravado.
"""

from collections.abc import Mapping
from decimal import ROUND_HALF_UP, Decimal

import psycopg

from etl.carga import conectar, resumir

CENTAVO = Decimal("0.01")
TOLERANCIA_SOMA = CENTAVO  # a contagem de pedidos não tem tolerância: precisa bater exatamente

# COALESCE: numa tabela vazia o SUM é NULL, e a soma tem que sair como 0.00.
SQL_DESTINO = "SELECT COUNT(*), COALESCE(SUM(valor_itens), 0.00) FROM pedidos"


class ErroReconciliacao(Exception):
    """Falha ao ler o destino para a reconciliação, com uma mensagem clara."""


def resumir_origem(pedidos_brutos: list[dict]) -> dict:
    """Conta os pedidos únicos dos brutos e soma quantidade x preco_unitario dos itens deles.

    Um pedido repetido entra uma vez só, pela primeira ocorrência (a mesma regra da A5). O preço
    vem da API como float: passa por str() antes do Decimal, para não trazer o erro binário do
    float (Decimal(0.1) é 0.1000000000000000055...). A soma sai com duas casas.
    """
    primeiros: dict = {}
    for pedido in pedidos_brutos:
        primeiros.setdefault(pedido["id"], pedido)  # só grava o id na primeira vez que aparece
    soma = sum(
        (
            item["quantidade"] * Decimal(str(item["preco_unitario"]))
            for pedido in primeiros.values()
            for item in pedido["itens"]
        ),
        Decimal("0"),
    )
    return {
        "pedidos": len(primeiros),
        "soma_valor_itens": soma.quantize(CENTAVO, rounding=ROUND_HALF_UP),
    }


def resumir_destino(conexao: psycopg.Connection) -> dict:
    """Conta as linhas da tabela pedidos e soma valor_itens, lidos do banco."""
    try:
        with conexao.cursor() as cursor:
            cursor.execute(SQL_DESTINO)
            pedidos, soma = cursor.fetchone()
    except psycopg.Error as erro:
        raise ErroReconciliacao(f"leitura do destino: {resumir(erro)}") from None
    return {"pedidos": pedidos, "soma_valor_itens": soma}


def comparar(origem: Mapping, destino: Mapping) -> dict:
    """Compara os resumos da origem e do destino. As diferenças são origem menos destino.

    confere é True quando a contagem de pedidos é igual e a soma difere no máximo 1 centavo.
    """
    diferenca_pedidos = origem["pedidos"] - destino["pedidos"]
    diferenca_soma = origem["soma_valor_itens"] - destino["soma_valor_itens"]
    return {
        "pedidos_origem": origem["pedidos"],
        "pedidos_destino": destino["pedidos"],
        "diferenca_pedidos": diferenca_pedidos,
        "soma_valor_itens_origem": origem["soma_valor_itens"],
        "soma_valor_itens_destino": destino["soma_valor_itens"],
        "diferenca_soma": diferenca_soma,
        "confere": diferenca_pedidos == 0 and abs(diferenca_soma) <= TOLERANCIA_SOMA,
    }


def executar_reconciliacao(pedidos_brutos: list[dict]) -> dict:
    """Resume a origem (os brutos), lê o destino numa conexão nova e devolve a comparação."""
    origem = resumir_origem(pedidos_brutos)
    with conectar() as conexao:
        destino = resumir_destino(conexao)
    return comparar(origem, destino)
