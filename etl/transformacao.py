"""Transformação (Parte 2).

Funções pequenas e puras: recebem um registro (ou um valor) e devolvem um novo, sem alterar o que
receberam e sem ler nem gravar nada. Uma por armadilha:
- A1 e-mail ausente: tratar_email
- A2 sigla do estado: padronizar_estado
- A3 data em dois formatos: converter_data
- A4 valor com vírgula: converter_valor
- A5 pedidos repetidos: remover_repetidos
- A6 valor_total diferente da soma dos itens: calcular_valor_itens

transformar junta tudo: devolve as linhas de cada tabela do schema.sql e os contadores de cada
transformação. As regras de cada campo estão em CONTRATO_DE_DADOS.md.
"""

import re
from collections.abc import Callable
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")
FORMATOS_DATA = ("%Y-%m-%d", "%d/%m/%Y")  # AAAA-MM-DD e DD/MM/AAAA
VALOR_EM_TEXTO = re.compile(r"-?\d+(?:[.,]\d+)?")  # 125,84 ou 3.5; nunca 1.234,56


class ErroTransformacao(Exception):
    """Registro que não pôde ser transformado, com a identificação dele na mensagem."""


def texto_obrigatorio(valor: object, campo: str) -> str:
    """Devolve o texto sem espaços nas pontas. ValueError se não for texto ou se ficar vazio."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"{campo} e obrigatorio: {valor!r}")
    return valor.strip()


# --- uma função por armadilha ---


def tratar_email(cliente: dict) -> dict:
    """A1: mantém o cliente; e-mail nulo ou em branco vira None, os demais saem sem espaços."""
    email = cliente["email"]
    if email is None:
        return {**cliente, "email": None}
    if not isinstance(email, str):
        raise ValueError(f"email deve ser texto ou nulo: {email!r}")
    return {**cliente, "email": email.strip() or None}


def padronizar_estado(cliente: dict) -> dict:
    """A2: sigla do estado em maiúsculas. Recusa o que não for uma sigla de 2 letras."""
    estado = cliente["estado"]
    sigla = estado.strip().upper() if isinstance(estado, str) else ""
    if not (len(sigla) == 2 and sigla.isascii() and sigla.isalpha()):
        raise ValueError(f"estado deve ser uma sigla de 2 letras: {estado!r}")
    return {**cliente, "estado": sigla}


def converter_data(texto: str) -> date:
    """A3: converte AAAA-MM-DD ou DD/MM/AAAA em date. Qualquer outro formato levanta ValueError.

    Só aceita a forma exata (com zero à esquerda), para que nenhuma data ambígua passe calada.
    """
    if isinstance(texto, str):
        texto = texto.strip()
        for formato in FORMATOS_DATA:
            try:
                data = datetime.strptime(texto, formato).date()
            except ValueError:
                continue
            if data.strftime(formato) == texto:  # recusa 2026-2-9, que o strptime aceitaria
                return data
    raise ValueError(f"data fora dos formatos AAAA-MM-DD e DD/MM/AAAA: {texto!r}")


def converter_valor(valor: str | int | float | Decimal) -> Decimal:
    """A4: converte número ou texto com vírgula decimal em Decimal com duas casas.

    O float passa por str() antes do Decimal: str(94.34) é "94.34", enquanto Decimal(94.34) traria
    o erro binário do float (94.340000000000003410...). O meio centavo arredonda para cima.
    """
    if isinstance(valor, str) and VALOR_EM_TEXTO.fullmatch(valor.strip()):
        numero = Decimal(valor.strip().replace(",", "."))
    elif isinstance(valor, (int, float, Decimal)) and not isinstance(valor, bool):
        numero = Decimal(str(valor))
    else:
        raise ValueError(f"valor invalido: {valor!r}")
    if not numero.is_finite():
        raise ValueError(f"valor invalido: {valor!r}")
    return numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def remover_repetidos(pedidos: list[dict]) -> list[dict]:
    """A5: devolve os pedidos sem repetição de id, na ordem original, com a primeira ocorrência.

    A ordem é a das páginas da API (1 até total_pages), preservada pela extração e pelos brutos.
    """
    vistos = set()
    unicos = []
    for pedido in pedidos:
        if pedido["id"] not in vistos:
            vistos.add(pedido["id"])
            unicos.append(pedido)
    return unicos


def calcular_valor_itens(pedido: dict) -> dict:
    """A6: acrescenta valor_itens (soma de quantidade x preco_unitario) e divergente.

    Espera valor_total e preco_unitario já em Decimal (A4). Mantém os dois valores e marca
    divergente quando a diferença entre eles passa de 1 centavo.
    """
    valor_itens = sum(
        (item["quantidade"] * item["preco_unitario"] for item in pedido["itens"]), Decimal("0.00")
    )
    divergente = abs(pedido["valor_total"] - valor_itens) > CENTAVO
    return {**pedido, "valor_itens": valor_itens, "divergente": divergente}


# --- um registro completo por tabela ---


def tratar_produto(bruto: dict) -> dict:
    """Linha de produtos: o CSV traz tudo como texto, então converte o id e o preço."""
    return {
        "produto_id": int(bruto["produto_id"]),
        "nome": texto_obrigatorio(bruto["nome"], "nome"),
        "categoria": texto_obrigatorio(bruto["categoria"], "categoria"),
        "preco_base": converter_valor(bruto["preco_base"]),
    }


def tratar_cliente(bruto: dict) -> dict:
    """Linha de clientes: A1, A2 e a data de cadastro (que já vem em AAAA-MM-DD) em date."""
    cliente = {
        "id": bruto["id"],
        "nome": texto_obrigatorio(bruto["nome"], "nome"),
        "email": bruto["email"],
        "cidade": texto_obrigatorio(bruto["cidade"], "cidade"),
        "estado": bruto["estado"],
        "cadastro_em": converter_data(bruto["cadastro_em"]),
    }
    return padronizar_estado(tratar_email(cliente))


def tratar_item(item: dict, linha: int) -> dict:
    """Item de pedido com o número da linha (1, 2, ...) e o preço em Decimal."""
    quantidade = item["quantidade"]
    if not isinstance(quantidade, int) or isinstance(quantidade, bool) or quantidade < 1:
        raise ValueError(f"quantidade deve ser um inteiro maior que zero: {quantidade!r}")
    return {
        "linha": linha,
        "produto_id": item["produto_id"],
        "quantidade": quantidade,
        "preco_unitario": converter_valor(item["preco_unitario"]),
    }


def tratar_pedido(bruto: dict) -> dict:
    """Pedido com A3 (data), A4 (valor_total e preços) e A6 (valor_itens e divergente)."""
    pedido = {
        "id": bruto["id"],
        "cliente_id": bruto["cliente_id"],
        "data_pedido": converter_data(bruto["data_pedido"]),
        "status": texto_obrigatorio(bruto["status"], "status"),
        "valor_total": converter_valor(bruto["valor_total"]),
        "itens": [tratar_item(item, n) for n, item in enumerate(bruto["itens"], start=1)],
    }
    return calcular_valor_itens(pedido)


# --- transformação completa ---


def aplicar(tratar: Callable[[dict], dict], bruto: dict, entidade: str, chave: str) -> dict:
    """Aplica a função ao registro e, se falhar, levanta ErroTransformacao dizendo qual registro."""
    try:
        return tratar(bruto)
    except KeyError as erro:
        motivo = f"campo ausente {erro}"
    except (TypeError, ValueError) as erro:
        motivo = str(erro)
    raise ErroTransformacao(f"{entidade} {chave}={bruto.get(chave)}: {motivo}")


def transformar(
    clientes_brutos: list[dict], pedidos_brutos: list[dict], produtos_brutos: list[dict]
) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Transforma os brutos nas linhas de produtos, clientes, pedidos e itens_pedido.

    Devolve (dados, contadores). A5 vem primeiro: os contadores de data, valor e divergência
    contam só os pedidos únicos. Um registro inválido interrompe tudo com ErroTransformacao,
    em vez de ser descartado em silêncio (o que quebraria a reconciliação).
    """
    produtos = [aplicar(tratar_produto, p, "produto", "produto_id") for p in produtos_brutos]
    clientes = [aplicar(tratar_cliente, c, "cliente", "id") for c in clientes_brutos]
    try:
        unicos = remover_repetidos(pedidos_brutos)
    except KeyError:
        raise ErroTransformacao("pedido sem o campo id: nao da para remover os repetidos") from None
    tratados = [aplicar(tratar_pedido, p, "pedido", "id") for p in unicos]

    pedidos = [{campo: v for campo, v in p.items() if campo != "itens"} for p in tratados]
    itens_pedido = [{"pedido_id": p["id"], **item} for p in tratados for item in p["itens"]]

    contadores = {
        "pedidos_unicos": len(unicos),
        "repetidos_descartados": len(pedidos_brutos) - len(unicos),
        "emails_nulos": sum(c["email"] is None for c in clientes),
        "estados_padronizados": sum(
            c["estado"] != b["estado"] for b, c in zip(clientes_brutos, clientes, strict=True)
        ),
        "datas_convertidas": sum(
            p["data_pedido"].isoformat() != b["data_pedido"]
            for b, p in zip(unicos, pedidos, strict=True)
        ),
        "valores_convertidos": sum(isinstance(b["valor_total"], str) for b in unicos),
        "divergentes": sum(p["divergente"] for p in pedidos),
    }
    dados = {
        "produtos": produtos,
        "clientes": clientes,
        "pedidos": pedidos,
        "itens_pedido": itens_pedido,
    }
    return dados, contadores
