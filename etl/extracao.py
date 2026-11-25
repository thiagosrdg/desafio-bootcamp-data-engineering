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
CAMPOS_PAGINA = ("total_items", "total_pages", "items")

PAGE_SIZE = 50  # padrão da API, que aceita de 1 a 200
TIMEOUT_SEGUNDOS = 10


class ErroExtracao(Exception):
    """Falha prevista na extração, com uma mensagem clara para quem roda o ETL."""


class PaginaInexistente(ErroExtracao):
    """A API respondeu 404. Guarda o total_pages informado no corpo da resposta, se houver."""

    def __init__(self, mensagem: str, total_pages: int | None = None) -> None:
        super().__init__(mensagem)
        self.total_pages = total_pages


def ler_json(resposta: requests.Response) -> dict | None:
    """Devolve o corpo da resposta como dicionário, ou None se ele não for um objeto JSON."""
    try:
        corpo = resposta.json()
    except ValueError:
        return None
    return corpo if isinstance(corpo, dict) else None


def validar_pagina(corpo: dict | None, origem: str) -> dict:
    """Confere se o corpo tem o formato de página da API e o devolve sem alteração.

    Se faltar um campo ou um campo vier com o tipo errado, levanta ErroExtracao com mensagem
    clara, em vez de deixar estourar um KeyError ou TypeError mais adiante.
    """
    if corpo is None:
        raise ErroExtracao(f"resposta nao e um objeto JSON: {origem}")
    faltando = [campo for campo in CAMPOS_PAGINA if campo not in corpo]
    if faltando:
        raise ErroExtracao(f"formato inesperado, faltam os campos {faltando}: {origem}")
    tipos_ok = (
        isinstance(corpo["items"], list)
        and isinstance(corpo["total_items"], int)
        and isinstance(corpo["total_pages"], int)
    )
    if not tipos_ok:
        raise ErroExtracao(
            f"formato inesperado, items deve ser lista e total_items/total_pages inteiros: {origem}"
        )
    return corpo


def buscar_pagina(url_base: str, rota: str, page: int, page_size: int = PAGE_SIZE) -> dict:
    """Busca uma página de uma rota da API e devolve o corpo da resposta, já validado.

    Levanta PaginaInexistente (subclasse de ErroExtracao) quando o status é 404, e ErroExtracao
    quando a API está fora do ar, não responde a tempo, responde com outro status diferente de 200
    ou devolve um corpo fora do formato de página.
    """
    url = f"{url_base}/{rota}"
    origem = f"{url} page={page}"
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
        raise ErroExtracao(f"a API nao respondeu em {TIMEOUT_SEGUNDOS} s: {origem}") from None
    except requests.RequestException as erro:
        raise ErroExtracao(f"falha na requisicao: {origem} ({erro})") from None

    corpo = ler_json(resposta)
    if resposta.status_code == 404:
        detalhe = corpo or {}
        motivo = detalhe.get("erro", "pagina ou rota inexistente")
        raise PaginaInexistente(f"{motivo}: {origem} (HTTP 404)", detalhe.get("total_pages"))
    if resposta.status_code != 200:
        raise ErroExtracao(f"resposta inesperada: {origem} (HTTP {resposta.status_code})")
    return validar_pagina(corpo, origem)


def extrair_rota(url_base: str, rota: str, page_size: int = PAGE_SIZE) -> tuple[list[dict], int]:
    """Percorre todas as páginas de uma rota, da 1 até total_pages.

    Devolve (registros, paginas_lidas). Os registros saem como vieram da API, sem tratamento.
    Rota vazia: esta API responde 404 já na página 1, com total_pages=0 no corpo; nesse caso a
    função devolve ([], 0). No fim, confere se a quantidade lida bate com o total_items da API.
    """
    try:
        primeira = buscar_pagina(url_base, rota, 1, page_size)
    except PaginaInexistente as erro:
        if erro.total_pages == 0:
            return [], 0
        raise

    registros = list(primeira["items"])
    paginas_lidas = 1
    for page in range(2, primeira["total_pages"] + 1):
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
    except UnicodeDecodeError:
        raise ErroExtracao(f"{caminho.name} nao esta em UTF-8") from None


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


def ler_bruto(nome: str, pasta: Path = PASTA_BRUTOS) -> list[dict]:
    """Lê <pasta>/<nome>.json, gravado por salvar_bruto, e devolve os registros como estão.

    É a entrada da transformação: ela trabalha sobre o que ficou em brutos/, sem chamar a API.
    """
    caminho = pasta / f"{nome}.json"
    try:
        with caminho.open(encoding="utf-8") as arquivo:
            registros = json.load(arquivo)
    except FileNotFoundError:
        raise ErroExtracao(f"bruto nao encontrado: {caminho}") from None
    except (OSError, ValueError) as erro:  # ValueError cobre JSON inválido e texto fora de UTF-8
        raise ErroExtracao(f"nao foi possivel ler {caminho}: {erro}") from None
    if not isinstance(registros, list):
        raise ErroExtracao(f"{caminho} deveria conter uma lista de registros")
    return registros


def executar_extracao(
    url_base: str,
    pasta_brutos: Path = PASTA_BRUTOS,
    caminho_produtos: Path = CAMINHO_PRODUTOS,
) -> dict[str, int]:
    """Extrai clientes, pedidos e produtos, grava os brutos e devolve os contadores.

    Primeiro extrai tudo e só depois grava, para que brutos/ nunca misture arquivos de execuções
    diferentes quando uma das rotas falha no meio.
    """
    clientes, paginas_clientes = extrair_rota(url_base, "clientes")
    pedidos, paginas_pedidos = extrair_rota(url_base, "pedidos")
    produtos = ler_produtos_csv(caminho_produtos)

    salvar_bruto(clientes, "clientes", pasta_brutos)
    salvar_bruto(pedidos, "pedidos", pasta_brutos)
    salvar_bruto(produtos, "produtos", pasta_brutos)

    return {
        "clientes_paginas": paginas_clientes,
        "clientes_registros": len(clientes),
        "pedidos_paginas": paginas_pedidos,
        "pedidos_registros_brutos": len(pedidos),
        "produtos_registros": len(produtos),
    }
