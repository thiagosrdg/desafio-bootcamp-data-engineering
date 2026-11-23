"""Extração (Parte 1).

Responsabilidades:
- percorrer uma rota paginada da API (page, page_size) até total_pages, verificando o status HTTP;
- extrair clientes e pedidos, tratando erro de conexão e página inexistente com mensagem clara;
- ler produtos.csv com o módulo csv;
- salvar os dados brutos em brutos/ antes de qualquer transformação;
- informar os contadores de páginas e registros.

Nada aqui transforma os dados: os registros saem da API e do CSV e vão para brutos/ como vieram.
"""

import csv
import json
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BRUTOS = RAIZ / "brutos"
CAMINHO_PRODUTOS = RAIZ / "insumos" / "dados" / "produtos.csv"
COLUNAS_PRODUTOS = ("produto_id", "nome", "categoria", "preco_base")

PAGE_SIZE = 50  # padrão da API, que aceita de 1 a 200
TIMEOUT_SEGUNDOS = 10


class ErroExtracao(Exception):
    """Falha prevista na extração, com uma mensagem clara para quem roda o ETL."""


def buscar_pagina(url_base: str, rota: str, page: int, page_size: int = PAGE_SIZE) -> dict:
    """Busca uma página de uma rota da API e devolve o corpo da resposta (JSON).

    Levanta ErroExtracao se a API estiver fora do ar, não responder a tempo, responder com
    status diferente de 200 ou devolver algo que não é JSON.
    """
    url = f"{url_base}/{rota}"
    try:
        resposta = requests.get(
            url, params={"page": page, "page_size": page_size}, timeout=TIMEOUT_SEGUNDOS
        )
    except requests.ConnectionError:
        raise ErroExtracao(
            f"sem conexao com a API em {url_base}. A API esta rodando? "
            "(python insumos/api_verdejar.py --dados insumos/dados)"
        ) from None
    except requests.Timeout:
        raise ErroExtracao(
            f"a API nao respondeu em {TIMEOUT_SEGUNDOS} s: {url} page={page}"
        ) from None

    if resposta.status_code == 404:
        raise ErroExtracao(f"pagina inexistente ou rota invalida: {url} page={page} (HTTP 404)")
    if resposta.status_code != 200:
        raise ErroExtracao(f"resposta inesperada: {url} page={page} (HTTP {resposta.status_code})")

    try:
        return resposta.json()
    except ValueError:
        raise ErroExtracao(f"resposta nao e um JSON valido: {url} page={page}") from None


def extrair_rota(url_base: str, rota: str, page_size: int = PAGE_SIZE) -> tuple[list[dict], int]:
    """Percorre todas as páginas de uma rota, da 1 até total_pages.

    Devolve (registros, paginas_lidas). Os registros saem como vieram da API, sem tratamento.
    No fim, confere se a quantidade lida bate com o total_items informado pela própria API.
    """
    primeira = buscar_pagina(url_base, rota, 1, page_size)
    total_pages = primeira["total_pages"]
    registros = list(primeira["items"])
    paginas_lidas = 1

    for page in range(2, total_pages + 1):
        registros.extend(buscar_pagina(url_base, rota, page, page_size)["items"])
        paginas_lidas += 1

    if len(registros) != primeira["total_items"]:
        raise ErroExtracao(
            f"/{rota}: a API informou {primeira['total_items']} registros, "
            f"mas foram lidos {len(registros)}"
        )
    return registros, paginas_lidas


def ler_produtos_csv(caminho: Path = CAMINHO_PRODUTOS) -> list[dict]:
    """Lê o catálogo de produtos com o módulo csv e devolve uma lista de dicionários.

    Todos os valores saem como texto, exatamente como estão no arquivo (sem converter preco_base).
    """
    try:
        with caminho.open(encoding="utf-8", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            faltando = set(COLUNAS_PRODUTOS) - set(leitor.fieldnames or [])
            if faltando:
                raise ErroExtracao(f"{caminho.name}: faltam as colunas {sorted(faltando)}")
            return list(leitor)
    except FileNotFoundError:
        raise ErroExtracao(f"arquivo de produtos nao encontrado: {caminho}") from None


def salvar_bruto(registros: list[dict], nome: str, pasta: Path = PASTA_BRUTOS) -> Path:
    """Grava os registros, sem nenhuma alteração, em <pasta>/<nome>.json e devolve o caminho."""
    caminho = pasta / f"{nome}.json"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as arquivo:
            json.dump(registros, arquivo, ensure_ascii=False, indent=2)
    except OSError as erro:
        raise ErroExtracao(f"nao foi possivel gravar {caminho}: {erro}") from None
    return caminho


def executar_extracao(url_base: str) -> dict[str, int]:
    """Extrai clientes, pedidos e produtos, grava os brutos e devolve os contadores.

    Primeiro extrai tudo e só depois grava, para que brutos/ nunca misture arquivos de execuções
    diferentes quando uma das rotas falha no meio.
    """
    clientes, paginas_clientes = extrair_rota(url_base, "clientes")
    pedidos, paginas_pedidos = extrair_rota(url_base, "pedidos")
    produtos = ler_produtos_csv()

    salvar_bruto(clientes, "clientes")
    salvar_bruto(pedidos, "pedidos")
    salvar_bruto(produtos, "produtos")

    return {
        "clientes_paginas": paginas_clientes,
        "clientes_registros": len(clientes),
        "pedidos_paginas": paginas_pedidos,
        "pedidos_registros_brutos": len(pedidos),
        "produtos_registros": len(produtos),
    }
