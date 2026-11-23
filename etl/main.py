"""Ponto de entrada do ETL: python -m etl.main

Orquestra extração, transformação, carga e reconciliação, e imprime a saída em texto simples
(uma informação por linha, sem cores), no formato da seção 4 do enunciado.

Por enquanto (Parte 1), só a extração está ligada.
"""

import os
import sys

from dotenv import load_dotenv

from etl.extracao import ErroExtracao, executar_extracao

API_URL_PADRAO = "http://127.0.0.1:8000"


def main() -> int:
    """Roda o ETL e devolve o código de saída do processo (0 = sucesso, 1 = erro tratado)."""
    load_dotenv()
    url_base = os.environ.get("API_URL", API_URL_PADRAO).rstrip("/")

    try:
        contadores = executar_extracao(url_base)
    except ErroExtracao as erro:
        print(f"erro: extracao: {erro}", file=sys.stderr)
        return 1

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
