"""Testes das consultas de validação (Parte 4, atividade 19).

As consultas são lidas do próprio consultas_validacao.sql (cada uma começa por uma linha
"-- consulta: <nome>"), para que o teste rode exatamente o que está no arquivo e no README.

- No esquema temporário (fixture conexao), com 4 pedidos escritos à mão, cada consulta precisa
  devolver as linhas esperadas, com as contas feitas à mão.
- Na última carga real do ETL (fixture destino_real, só leitura), o teste de consulta da (a): a
  soma dos meses tem que ser igual à soma geral da tabela. A (b) e a (c) também são conferidas.
"""

from datetime import date
from decimal import Decimal

from etl.carga import carregar
from etl.extracao import RAIZ

ARQUIVO_CONSULTAS = RAIZ / "consultas_validacao.sql"
MARCADOR = "-- consulta:"


def ler_consultas() -> dict[str, str]:
    """Separa as consultas do arquivo pelo marcador "-- consulta: <nome>", sem os comentários."""
    consultas: dict[str, list[str]] = {}
    nome = None
    for linha in ARQUIVO_CONSULTAS.read_text(encoding="utf-8").splitlines():
        if linha.startswith(MARCADOR):
            nome = linha.removeprefix(MARCADOR).strip()
            consultas[nome] = []
        elif nome is not None and not linha.lstrip().startswith("--"):
            consultas[nome].append(linha)
    return {nome: "\n".join(linhas).strip() for nome, linhas in consultas.items()}


def rodar(conexao, nome: str) -> list[tuple]:
    consultas = ler_consultas()
    assert nome in consultas, f"consulta {nome!r} nao encontrada em {ARQUIVO_CONSULTAS.name}"
    return conexao.execute(consultas[nome]).fetchall()


# --- esquema temporário, com dados escritos à mão ---


def dados_consultas() -> dict[str, list[dict]]:
    """3 clientes (2 no RS, 1 em SP), 4 pedidos em janeiro e fevereiro, 1 divergente."""
    produtos = [
        {"produto_id": 1, "nome": "Alface", "categoria": "folhas", "preco_base": Decimal("3.50")},
        {"produto_id": 2, "nome": "Tomate", "categoria": "legumes", "preco_base": Decimal("8.90")},
    ]
    clientes = [
        {"id": 1, "nome": "Ana", "email": None, "cidade": "Pelotas", "estado": "RS",
         "cadastro_em": date(2025, 1, 10)},
        {"id": 2, "nome": "Bruno", "email": None, "cidade": "Campinas", "estado": "SP",
         "cadastro_em": date(2025, 2, 10)},
        {"id": 3, "nome": "Carla", "email": None, "cidade": "Canoas", "estado": "RS",
         "cadastro_em": date(2025, 3, 10)},
    ]  # fmt: skip
    pedidos = [
        # 2 x 3.50 = 7.00
        {"id": 100, "cliente_id": 1, "data_pedido": date(2026, 1, 5), "status": "entregue",
         "valor_total": Decimal("7.00"), "valor_itens": Decimal("7.00"), "divergente": False},
        # 1 x 8.90 = 8.90; último dia de janeiro
        {"id": 101, "cliente_id": 2, "data_pedido": date(2026, 1, 31), "status": "cancelado",
         "valor_total": Decimal("8.90"), "valor_itens": Decimal("8.90"), "divergente": False},
        # 2 x 3.50 + 1 x 8.90 = 15.90; total 20.00: diferença de 4.10, divergente
        {"id": 102, "cliente_id": 3, "data_pedido": date(2026, 2, 1), "status": "entregue",
         "valor_total": Decimal("20.00"), "valor_itens": Decimal("15.90"), "divergente": True},
        # 2 x 8.90 = 17.80; total 17.79: diferença de 1 centavo, tolerada (não é divergente)
        {"id": 103, "cliente_id": 1, "data_pedido": date(2026, 2, 28), "status": "em_transporte",
         "valor_total": Decimal("17.79"), "valor_itens": Decimal("17.80"), "divergente": False},
    ]  # fmt: skip
    itens_pedido = [
        {"pedido_id": 100, "linha": 1, "produto_id": 1, "quantidade": 2,
         "preco_unitario": Decimal("3.50")},
        {"pedido_id": 101, "linha": 1, "produto_id": 2, "quantidade": 1,
         "preco_unitario": Decimal("8.90")},
        {"pedido_id": 102, "linha": 1, "produto_id": 1, "quantidade": 2,
         "preco_unitario": Decimal("3.50")},
        {"pedido_id": 102, "linha": 2, "produto_id": 2, "quantidade": 1,
         "preco_unitario": Decimal("8.90")},
        {"pedido_id": 103, "linha": 1, "produto_id": 2, "quantidade": 2,
         "preco_unitario": Decimal("8.90")},
    ]  # fmt: skip
    return {
        "produtos": produtos,
        "clientes": clientes,
        "pedidos": pedidos,
        "itens_pedido": itens_pedido,
    }


def test_a_vendas_por_mes(conexao):
    carregar(conexao, dados_consultas())

    # Janeiro: 7.00 + 8.90 = 15.90 nas duas colunas.
    # Fevereiro: valor_total 20.00 + 17.79 = 37.79; valor_itens 15.90 + 17.80 = 33.70.
    assert rodar(conexao, "vendas_por_mes") == [
        ("2026-01", 2, Decimal("15.90"), Decimal("15.90")),
        ("2026-02", 2, Decimal("37.79"), Decimal("33.70")),
    ]


def test_a_teste_de_consulta_soma_dos_meses_igual_a_soma_geral(conexao):
    carregar(conexao, dados_consultas())

    # valor_total: 15.90 + 37.79 = 53.69; valor_itens: 15.90 + 33.70 = 49.60.
    assert rodar(conexao, "teste_vendas_por_mes") == [
        ("soma dos meses", 4, Decimal("53.69"), Decimal("49.60")),
        ("soma geral", 4, Decimal("53.69"), Decimal("49.60")),
    ]


def test_b_pedidos_por_estado(conexao):
    carregar(conexao, dados_consultas())

    # RS: pedidos 100 e 103 (Ana) e 102 (Carla); SP: pedido 101 (Bruno).
    assert rodar(conexao, "pedidos_por_estado") == [("RS", 3), ("SP", 1)]


def test_c_pedidos_divergentes(conexao):
    carregar(conexao, dados_consultas())

    # Só o 102. O 103 difere em 1 centavo e não entra: a consulta segue a marcação da A6.
    assert rodar(conexao, "pedidos_divergentes") == [
        (102, 3, date(2026, 2, 1), "entregue", Decimal("20.00"), Decimal("15.90"), Decimal("4.10")),
    ]
    assert rodar(conexao, "divergentes_por_diferenca") == [(Decimal("4.10"), 1)]


# --- a última carga real do ETL (só leitura) ---


def test_a_na_carga_real_soma_dos_meses_igual_a_soma_geral(destino_real):
    soma_dos_meses, soma_geral = rodar(destino_real, "teste_vendas_por_mes")

    assert soma_dos_meses[0] == "soma dos meses" and soma_geral[0] == "soma geral"
    assert soma_dos_meses[1:] == soma_geral[1:]  # pedidos, valor_total e valor_itens
    assert soma_geral[1] == 5000  # os 5000 pedidos únicos do enunciado
    # A mesma prova sobre a própria consulta (a), somando os meses aqui no Python.
    meses = rodar(destino_real, "vendas_por_mes")
    assert sum(mes[1] for mes in meses) == soma_geral[1]
    assert sum(mes[2] for mes in meses) == soma_geral[2]
    assert sum(mes[3] for mes in meses) == soma_geral[3]


def test_b_na_carga_real_conta_todos_os_pedidos_com_a_sigla_padronizada(destino_real):
    estados = rodar(destino_real, "pedidos_por_estado")

    assert sum(pedidos for _, pedidos in estados) == 5000  # nenhum pedido perdido no JOIN
    assert all(len(sigla) == 2 and sigla.isupper() for sigla, _ in estados)  # A2 no destino


def test_c_na_carga_real_lista_os_divergentes_pela_regra_da_a6(destino_real):
    divergentes = rodar(destino_real, "pedidos_divergentes")
    (recontagem,) = destino_real.execute(
        "SELECT COUNT(*) FROM pedidos WHERE ABS(valor_total - valor_itens) > 0.01"
    ).fetchone()

    assert len(divergentes) == recontagem  # a marcação divergente bate com a regra da A6
    assert all(abs(diferenca) > Decimal("0.01") for *_, diferenca in divergentes)
    por_diferenca = rodar(destino_real, "divergentes_por_diferenca")
    assert sum(pedidos for _, pedidos in por_diferenca) == len(divergentes)
