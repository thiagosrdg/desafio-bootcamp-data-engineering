"""Ponto de entrada do ETL: python -m etl.main

Orquestra extração, transformação, carga e reconciliação, e imprime a saída em texto simples
(uma informação por linha, sem cores), no formato da seção 4 do enunciado.

Cada etapa que falha imprime "erro: <etapa>: <motivo>" na saída de erro e encerra com código 1.
"""

import os
import sys

from dotenv import load_dotenv

from etl.carga import ErroCarga, executar_carga
from etl.extracao import ErroExtracao, executar_extracao, ler_bruto
from etl.reconciliacao import ErroReconciliacao, executar_reconciliacao
from etl.transformacao import ErroTransformacao, transformar

API_URL_PADRAO = "http://127.0.0.1:8000"


def imprimir_extracao(contadores: dict[str, int]) -> None:
    print(
        f"extracao: clientes paginas={contadores['clientes_paginas']} "
        f"registros={contadores['clientes_registros']}"
    )
    print(
        f"extracao: pedidos paginas={contadores['pedidos_paginas']} "
        f"registros_brutos={contadores['pedidos_registros_brutos']}"
    )
    print(f"extracao: produtos registros={contadores['produtos_registros']}")
    print("extracao: brutos salvos em brutos/ (clientes.json, pedidos.json, produtos.json)")


def imprimir_transformacao(contadores: dict[str, int]) -> None:
    print(
        f"transformacao: pedidos_unicos={contadores['pedidos_unicos']} "
        f"repetidos_descartados={contadores['repetidos_descartados']}"
    )
    print(
        f"transformacao: emails_nulos={contadores['emails_nulos']} "
        f"estados_padronizados={contadores['estados_padronizados']} "
        f"datas_convertidas={contadores['datas_convertidas']} "
        f"valores_convertidos={contadores['valores_convertidos']}"
    )


def imprimir_carga(contagens: dict[str, int]) -> None:
    print(
        f"carga: clientes={contagens['clientes']} produtos={contagens['produtos']} "
        f"pedidos={contagens['pedidos']} itens={contagens['itens_pedido']}"
    )


def imprimir_reconciliacao(resultado: dict) -> None:
    print(
        f"reconciliacao: pedidos_origem={resultado['pedidos_origem']} "
        f"pedidos_destino={resultado['pedidos_destino']} "
        f"diferenca={resultado['diferenca_pedidos']}"
    )
    print(
        f"reconciliacao: soma_valor_itens_origem={resultado['soma_valor_itens_origem']} "
        f"soma_valor_itens_destino={resultado['soma_valor_itens_destino']} "
        f"diferenca={resultado['diferenca_soma']}"
    )


def main() -> int:
    """Roda o ETL e devolve o código de saída do processo (0 = sucesso, 1 = erro tratado)."""
    load_dotenv()
    url_base = os.environ.get("API_URL", API_URL_PADRAO).rstrip("/")

    try:
        contadores_extracao = executar_extracao(url_base)
    except ErroExtracao as erro:
        print(f"erro: extracao: {erro}", file=sys.stderr)
        return 1
    imprimir_extracao(contadores_extracao)

    # A transformação lê o que ficou em brutos/, e não o que está em memória: assim ela trabalha
    # exatamente sobre os arquivos que permitem reprocessar sem chamar a API de novo.
    try:
        brutos = {nome: ler_bruto(nome) for nome in ("clientes", "pedidos", "produtos")}
        dados, contadores = transformar(brutos["clientes"], brutos["pedidos"], brutos["produtos"])
    except (ErroExtracao, ErroTransformacao) as erro:
        print(f"erro: transformacao: {erro}", file=sys.stderr)
        return 1
    imprimir_transformacao(contadores)

    # As credenciais do banco vêm das variáveis PG* do ambiente (o load_dotenv acima lê o .env).
    try:
        contagens = executar_carga(dados)
    except ErroCarga as erro:
        print(f"erro: carga: {erro}", file=sys.stderr)
        return 1
    imprimir_carga(contagens)

    # A origem são os brutos lidos acima (com os repetidos); o destino é lido de novo do banco.
    try:
        reconciliacao = executar_reconciliacao(brutos["pedidos"])
    except (ErroCarga, ErroReconciliacao) as erro:
        print(f"erro: reconciliacao: {erro}", file=sys.stderr)
        return 1
    imprimir_reconciliacao(reconciliacao)
    if not reconciliacao["confere"]:
        print(
            "erro: reconciliacao: origem e destino nao conferem (a contagem de pedidos precisa "
            "ser igual e a soma de valor_itens pode diferir no maximo 0.01)",
            file=sys.stderr,
        )
        return 1

    print(
        f"divergentes: {contadores['divergentes']} pedidos "
        "com valor_total diferente da soma dos itens"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
