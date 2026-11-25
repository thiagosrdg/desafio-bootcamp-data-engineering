"""Testes das funções de transformação (Parte 2; cobrem também a atividade 17 da Parte 4).

Pelo menos um teste por armadilha (A1 a A6), cada um com uma entrada conhecida e a saída esperada
escrita à mão antes de implementar a função. Sem rede e sem banco.
"""

from datetime import date
from decimal import Decimal

import pytest

from etl.transformacao import (
    ErroTransformacao,
    calcular_valor_itens,
    converter_data,
    converter_valor,
    padronizar_estado,
    remover_repetidos,
    transformar,
    tratar_cliente,
    tratar_email,
    tratar_pedido,
    tratar_produto,
)

# --- A1: e-mail ausente ---


def test_a1_email_nulo_continua_nulo_e_o_cliente_e_mantido():
    cliente = {"id": 7, "nome": "Ana Lima", "email": None}

    assert tratar_email(cliente) == {"id": 7, "nome": "Ana Lima", "email": None}


def test_a1_email_em_branco_vira_nulo():
    assert tratar_email({"id": 8, "email": "   "}) == {"id": 8, "email": None}


def test_a1_email_preenchido_sai_sem_espacos_nas_pontas():
    assert tratar_email({"id": 9, "email": " ana@exemplo.com "}) == {
        "id": 9,
        "email": "ana@exemplo.com",
    }


def test_a1_nao_altera_o_registro_recebido():
    cliente = {"id": 8, "email": "  "}

    tratar_email(cliente)

    assert cliente == {"id": 8, "email": "  "}  # função pura: devolve um registro novo


# --- A2: sigla do estado ---


@pytest.mark.parametrize(
    ("estado", "esperado"),
    [("rs", "RS"), ("RS", "RS"), ("Sc", "SC"), (" pr ", "PR")],
)
def test_a2_estado_sai_em_maiusculas(estado, esperado):
    assert padronizar_estado({"id": 1, "estado": estado}) == {"id": 1, "estado": esperado}


@pytest.mark.parametrize("estado", ["R", "RSS", "", "r1", None])
def test_a2_estado_que_nao_e_sigla_de_duas_letras_vira_erro(estado):
    with pytest.raises(ValueError, match="estado deve ser uma sigla de 2 letras"):
        padronizar_estado({"id": 1, "estado": estado})


# --- A3: data em dois formatos ---


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("2026-02-19", date(2026, 2, 19)),
        ("19/02/2026", date(2026, 2, 19)),
        ("05/03/2026", date(2026, 3, 5)),  # dia 5 de março, nunca 3 de maio
        ("2026-03-05", date(2026, 3, 5)),
    ],
)
def test_a3_converte_os_dois_formatos_para_date(texto, esperado):
    assert converter_data(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "2026/02/19",  # separador trocado
        "19-02-2026",  # separador trocado
        "02/19/2026",  # mês 19 não existe: não aceita MM/DD/AAAA
        "31/02/2026",  # 31 de fevereiro não existe
        "2026-2-9",  # sem zero à esquerda
        "",
        None,
    ],
)
def test_a3_data_fora_dos_dois_formatos_vira_erro(texto):
    with pytest.raises(ValueError, match="data fora dos formatos AAAA-MM-DD e DD/MM/AAAA"):
        converter_data(texto)


# --- A4: valor com vírgula ---


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("125,84", Decimal("125.84")),  # texto com vírgula decimal
        (94.34, Decimal("94.34")),  # número da API
        ("9,9", Decimal("9.90")),
        ("3.5", Decimal("3.50")),  # preco_base do CSV, com ponto
        (12, Decimal("12.00")),
        (-1.84, Decimal("-1.84")),  # existe nos dados: total ajustado em -5 pela A6
    ],
)
def test_a4_converte_para_decimal_com_duas_casas(valor, esperado):
    convertido = converter_valor(valor)

    assert isinstance(convertido, Decimal)
    assert convertido == esperado
    assert str(convertido) == str(esperado)  # duas casas: "9.90", não "9.9"


def test_a4_arredonda_meio_centavo_para_cima_sem_erro_de_float():
    # round(2.675, 2) devolve 2.67, porque o float 2.675 é guardado como 2.67499999...
    assert converter_valor(2.675) == Decimal("2.68")
    assert converter_valor("2,675") == Decimal("2.68")
    # sempre para cima, mesmo com o vizinho par embaixo (o arredondamento bancário daria 2.66)
    assert converter_valor("2,665") == Decimal("2.67")


@pytest.mark.parametrize(
    "valor",
    ["1.234,56", "abc", "", "12,", ",5", "1e3", None, True, float("nan")],
)
def test_a4_valor_que_nao_e_numero_vira_erro(valor):
    with pytest.raises(ValueError, match="valor invalido"):
        converter_valor(valor)


# --- A5: pedidos repetidos ---


def test_a5_remove_repetidos_pelo_id_mantendo_a_primeira_ocorrencia():
    pedidos = [
        {"id": 1, "origem": "pagina 1"},
        {"id": 2, "origem": "pagina 1"},
        {"id": 1, "origem": "pagina 3"},
        {"id": 3, "origem": "pagina 3"},
        {"id": 2, "origem": "pagina 4"},
    ]

    assert remover_repetidos(pedidos) == [
        {"id": 1, "origem": "pagina 1"},
        {"id": 2, "origem": "pagina 1"},
        {"id": 3, "origem": "pagina 3"},
    ]
    assert len(pedidos) == 5  # a lista recebida não muda


def test_a5_sem_repetidos_devolve_a_mesma_sequencia():
    pedidos = [{"id": 3}, {"id": 1}, {"id": 2}]

    assert remover_repetidos(pedidos) == [{"id": 3}, {"id": 1}, {"id": 2}]


# --- A6: divergência entre valor_total e a soma dos itens ---


def pedido_com_total(valor_total: str) -> dict:
    """Pedido já convertido (A3 e A4 aplicadas) cujos itens somam 20.00 (2 x 4.30 + 1 x 11.40)."""
    return {
        "id": 1,
        "valor_total": Decimal(valor_total),
        "itens": [
            {"linha": 1, "produto_id": 2, "quantidade": 2, "preco_unitario": Decimal("4.30")},
            {"linha": 2, "produto_id": 9, "quantidade": 1, "preco_unitario": Decimal("11.40")},
        ],
    }


@pytest.mark.parametrize(
    ("valor_total", "divergente"),
    [
        ("20.00", False),  # bate com a soma
        ("20.01", False),  # diferença de exatamente 1 centavo: tolerada
        ("19.99", False),
        ("20.02", True),  # mais de 1 centavo
        ("17.98", True),  # mais de 1 centavo, para baixo
        ("23.00", True),
    ],
)
def test_a6_soma_os_itens_e_marca_divergencia_acima_de_um_centavo(valor_total, divergente):
    resultado = calcular_valor_itens(pedido_com_total(valor_total))

    assert resultado["valor_itens"] == Decimal("20.00")
    assert resultado["valor_total"] == Decimal(valor_total)  # os dois valores são mantidos
    assert resultado["divergente"] is divergente


def test_a6_nao_altera_o_pedido_recebido():
    pedido = pedido_com_total("23.00")

    calcular_valor_itens(pedido)

    assert "valor_itens" not in pedido and "divergente" not in pedido


# --- registros completos ---


def test_tratar_cliente_aplica_a1_a2_e_converte_o_cadastro():
    bruto = {
        "id": 1,
        "nome": "Diego Fernandes",
        "email": None,
        "cidade": "Campinas",
        "estado": "sp",
        "cadastro_em": "2025-04-04",
    }

    assert tratar_cliente(bruto) == {
        "id": 1,
        "nome": "Diego Fernandes",
        "email": None,
        "cidade": "Campinas",
        "estado": "SP",
        "cadastro_em": date(2025, 4, 4),
    }


@pytest.mark.parametrize("campo", ["nome", "cidade"])
def test_tratar_cliente_sem_texto_obrigatorio_vira_erro(campo):
    bruto = {
        "id": 1,
        "nome": "Diego Fernandes",
        "email": None,
        "cidade": "Campinas",
        "estado": "SP",
        "cadastro_em": "2025-04-04",
    }
    bruto[campo] = "  "

    with pytest.raises(ValueError, match=f"{campo} e obrigatorio"):
        tratar_cliente(bruto)


def test_tratar_produto_converte_id_e_preco():
    bruto = {"produto_id": "1", "nome": "Alface crespa", "categoria": "folhas", "preco_base": "3.5"}

    assert tratar_produto(bruto) == {
        "produto_id": 1,
        "nome": "Alface crespa",
        "categoria": "folhas",
        "preco_base": Decimal("3.50"),
    }


def test_tratar_pedido_aplica_a3_a4_e_a6():
    # Pedido 1 dos dados reais, com a data reescrita em DD/MM/AAAA. Conta feita à mão:
    # 3 x 4.30 = 12.90; 5 x 15.86 = 79.30; 4 x 9.66 = 38.64; soma = 130.84 (total 125.84).
    bruto = {
        "id": 1,
        "cliente_id": 303,
        "data_pedido": "19/02/2026",
        "status": "entregue",
        "valor_total": "125,84",
        "itens": [
            {"produto_id": 2, "quantidade": 3, "preco_unitario": 4.3},
            {"produto_id": 9, "quantidade": 5, "preco_unitario": 15.86},
            {"produto_id": 7, "quantidade": 4, "preco_unitario": 9.66},
        ],
    }

    assert tratar_pedido(bruto) == {
        "id": 1,
        "cliente_id": 303,
        "data_pedido": date(2026, 2, 19),
        "status": "entregue",
        "valor_total": Decimal("125.84"),
        "itens": [
            {"linha": 1, "produto_id": 2, "quantidade": 3, "preco_unitario": Decimal("4.30")},
            {"linha": 2, "produto_id": 9, "quantidade": 5, "preco_unitario": Decimal("15.86")},
            {"linha": 3, "produto_id": 7, "quantidade": 4, "preco_unitario": Decimal("9.66")},
        ],
        "valor_itens": Decimal("130.84"),
        "divergente": True,
    }


@pytest.mark.parametrize("quantidade", [0, -1, "3", True, 1.5])
def test_tratar_pedido_com_quantidade_invalida_vira_erro(quantidade):
    bruto = {
        "id": 1,
        "cliente_id": 303,
        "data_pedido": "2026-02-19",
        "status": "entregue",
        "valor_total": 4.3,
        "itens": [{"produto_id": 2, "quantidade": quantidade, "preco_unitario": 4.3}],
    }

    with pytest.raises(ValueError, match="quantidade deve ser um inteiro maior que zero"):
        tratar_pedido(bruto)


# --- transformação completa e contadores (atividades 11 a 13) ---

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
        "cidade": "Joinville",
        "estado": "SC",
        "cadastro_em": "2025-06-01",
    },
    {
        "id": 3,
        "nome": "Carla Rocha",
        "email": "",
        "cidade": "Curitiba",
        "estado": "pr",
        "cadastro_em": "2025-12-28",
    },
]

PRODUTOS_BRUTOS = [
    {"produto_id": "1", "nome": "Alface crespa", "categoria": "folhas", "preco_base": "3.5"},
    {"produto_id": "2", "nome": "Rucula", "categoria": "folhas", "preco_base": "4.2"},
]

PEDIDO_10 = {
    "id": 10,
    "cliente_id": 1,
    "data_pedido": "2026-03-05",
    "status": "entregue",
    "valor_total": "10,00",
    "itens": [{"produto_id": 1, "quantidade": 2, "preco_unitario": 5.0}],
}

PEDIDOS_BRUTOS = [
    PEDIDO_10,
    {
        "id": 11,
        "cliente_id": 2,
        "data_pedido": "05/03/2026",
        "status": "cancelado",
        "valor_total": 13.0,
        "itens": [
            {"produto_id": 2, "quantidade": 1, "preco_unitario": 4.2},
            {"produto_id": 1, "quantidade": 1, "preco_unitario": 5.8},
        ],
    },
    dict(PEDIDO_10),  # repetido, com o mesmo conteúdo (A5)
    {
        "id": 12,
        "cliente_id": 3,
        "data_pedido": "01/10/2026",
        "status": "em_transporte",
        "valor_total": "7,50",
        "itens": [{"produto_id": 2, "quantidade": 3, "preco_unitario": 2.5}],
    },
]


def test_transformar_conta_cada_transformacao():
    _, contadores = transformar(CLIENTES_BRUTOS, PEDIDOS_BRUTOS, PRODUTOS_BRUTOS)

    assert contadores == {
        "pedidos_unicos": 3,  # 10, 11 e 12
        "repetidos_descartados": 1,  # a segunda ocorrência do 10
        "emails_nulos": 2,  # cliente 1 (null) e cliente 3 (vazio)
        "estados_padronizados": 2,  # rs e pr
        "datas_convertidas": 2,  # pedidos 11 e 12, em DD/MM/AAAA
        "valores_convertidos": 2,  # pedidos 10 e 12, texto com vírgula
        "divergentes": 1,  # pedido 11: total 13.00, itens 4.20 + 5.80 = 10.00
    }


def test_transformar_devolve_as_linhas_de_cada_tabela():
    dados, _ = transformar(CLIENTES_BRUTOS, PEDIDOS_BRUTOS, PRODUTOS_BRUTOS)

    assert [c["estado"] for c in dados["clientes"]] == ["RS", "SC", "PR"]
    assert [p["preco_base"] for p in dados["produtos"]] == [Decimal("3.50"), Decimal("4.20")]
    assert dados["pedidos"] == [
        {
            "id": 10,
            "cliente_id": 1,
            "data_pedido": date(2026, 3, 5),
            "status": "entregue",
            "valor_total": Decimal("10.00"),
            "valor_itens": Decimal("10.00"),
            "divergente": False,
        },
        {
            "id": 11,
            "cliente_id": 2,
            "data_pedido": date(2026, 3, 5),
            "status": "cancelado",
            "valor_total": Decimal("13.00"),
            "valor_itens": Decimal("10.00"),
            "divergente": True,
        },
        {
            "id": 12,
            "cliente_id": 3,
            "data_pedido": date(2026, 10, 1),
            "status": "em_transporte",
            "valor_total": Decimal("7.50"),
            "valor_itens": Decimal("7.50"),
            "divergente": False,
        },
    ]
    assert dados["itens_pedido"] == [
        {"pedido_id": 10, "linha": 1, "produto_id": 1, "quantidade": 2,
         "preco_unitario": Decimal("5.00")},
        {"pedido_id": 11, "linha": 1, "produto_id": 2, "quantidade": 1,
         "preco_unitario": Decimal("4.20")},
        {"pedido_id": 11, "linha": 2, "produto_id": 1, "quantidade": 1,
         "preco_unitario": Decimal("5.80")},
        {"pedido_id": 12, "linha": 1, "produto_id": 2, "quantidade": 3,
         "preco_unitario": Decimal("2.50")},
    ]  # fmt: skip


def test_transformar_nao_altera_os_brutos():
    pedidos = [dict(PEDIDO_10)]

    transformar([], pedidos, [])

    assert pedidos == [PEDIDO_10]


def test_transformar_identifica_o_registro_com_problema():
    pedido_ruim = dict(PEDIDO_10, id=99, data_pedido="2026/03/05")

    with pytest.raises(ErroTransformacao, match="pedido id=99: data fora dos formatos"):
        transformar(CLIENTES_BRUTOS, [pedido_ruim], PRODUTOS_BRUTOS)


def test_transformar_com_campo_ausente_vira_erro_claro():
    cliente_sem_estado = {k: v for k, v in CLIENTES_BRUTOS[0].items() if k != "estado"}

    with pytest.raises(ErroTransformacao, match="cliente id=1: campo ausente 'estado'"):
        transformar([cliente_sem_estado], [], [])


def test_transformar_pedido_sem_id_vira_erro_claro():
    pedido_sem_id = {k: v for k, v in PEDIDO_10.items() if k != "id"}

    with pytest.raises(ErroTransformacao, match="pedido sem o campo id"):
        transformar([], [pedido_sem_id], [])
