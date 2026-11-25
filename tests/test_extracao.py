"""Testes da extração (Parte 1).

Sem rede e sem banco: requests.get é trocado por uma API falsa (monkeypatch) e os arquivos vão
para a pasta temporária do pytest (tmp_path). Os valores esperados são literais, escritos a partir
da entrada de cada teste, e nunca calculados pela própria função testada.
"""

import json
from decimal import Decimal

import pytest
import requests

from etl import extracao, main
from etl.carga import ErroCarga
from etl.extracao import (
    ErroExtracao,
    PaginaInexistente,
    buscar_pagina,
    executar_extracao,
    extrair_rota,
    ler_bruto,
    ler_produtos_csv,
    salvar_bruto,
)
from etl.reconciliacao import ErroReconciliacao

URL = "http://api.falsa"
NAO_JSON = object()  # marcador: o corpo da resposta não é JSON


class RespostaFalsa:
    """Imita a parte de requests.Response que a extração usa: status_code e json()."""

    def __init__(self, status_code: int, corpo: object) -> None:
        self.status_code = status_code
        self._corpo = corpo

    def json(self) -> object:
        if self._corpo is NAO_JSON:
            raise ValueError("corpo nao e JSON")
        return self._corpo


def pagina(page: int, total_pages: int, total_items: int, items: list[dict]) -> RespostaFalsa:
    """Uma página com status 200, no mesmo formato da API real."""
    corpo = {
        "page": page,
        "page_size": 50,
        "total_items": total_items,
        "total_pages": total_pages,
        "items": items,
    }
    return RespostaFalsa(200, corpo)


def instalar_api(monkeypatch: pytest.MonkeyPatch, respostas: dict) -> list[tuple]:
    """Troca requests.get por uma API falsa que responde por (rota, page). Devolve as chamadas."""
    chamadas = []

    def get_falso(url, params, timeout):
        rota = url.rsplit("/", 1)[-1]
        chamadas.append((rota, params["page"], params["page_size"], timeout))
        return respostas[(rota, params["page"])]

    monkeypatch.setattr(extracao.requests, "get", get_falso)
    return chamadas


def instalar_falha(monkeypatch: pytest.MonkeyPatch, excecao: Exception) -> None:
    """Troca requests.get por uma função que sempre levanta a exceção dada."""

    def get_falso(url, params, timeout):
        raise excecao

    monkeypatch.setattr(extracao.requests, "get", get_falso)


# --- paginação (atividade 05) ---


def test_percorre_todas_as_paginas_e_conta(monkeypatch):
    chamadas = instalar_api(
        monkeypatch,
        {
            ("pedidos", 1): pagina(1, 3, 5, [{"id": 1}, {"id": 2}]),
            ("pedidos", 2): pagina(2, 3, 5, [{"id": 2}, {"id": 3}]),
            ("pedidos", 3): pagina(3, 3, 5, [{"id": 4}]),
        },
    )

    registros, paginas = extrair_rota(URL, "pedidos")

    # o id 2 repetido continua: a extração não remove repetidos (isso é a A5, na Parte 2)
    assert [r["id"] for r in registros] == [1, 2, 2, 3, 4]
    assert paginas == 3
    assert chamadas == [("pedidos", 1, 50, 10), ("pedidos", 2, 50, 10), ("pedidos", 3, 50, 10)]


def test_rota_vazia_devolve_lista_vazia(monkeypatch):
    # A API real responde 404 já na página 1 quando a rota não tem registros (total_pages=0).
    instalar_api(
        monkeypatch,
        {("clientes", 1): RespostaFalsa(404, {"erro": "pagina inexistente", "total_pages": 0})},
    )

    assert extrair_rota(URL, "clientes") == ([], 0)


def test_total_items_diferente_do_lido_vira_erro(monkeypatch):
    instalar_api(monkeypatch, {("clientes", 1): pagina(1, 1, 10, [{"id": 1}, {"id": 2}])})

    with pytest.raises(ErroExtracao, match="a API informou 10 registros, mas foram lidos 2"):
        extrair_rota(URL, "clientes")


# --- erros com mensagem clara (atividade 06) ---


def test_rota_inexistente_tem_mensagem_clara(monkeypatch):
    corpo = {"erro": "rota inexistente", "rotas": ["/clientes", "/pedidos", "/saude"]}
    instalar_api(monkeypatch, {("vendas", 1): RespostaFalsa(404, corpo)})

    with pytest.raises(PaginaInexistente, match="rota inexistente: http://api.falsa/vendas page=1"):
        extrair_rota(URL, "vendas")


def test_pagina_inexistente_no_meio_tem_mensagem_clara(monkeypatch):
    # A página 1 promete 2 páginas, mas a página 2 sumiu (a origem mudou durante a extração).
    instalar_api(
        monkeypatch,
        {
            ("clientes", 1): pagina(1, 2, 3, [{"id": 1}, {"id": 2}]),
            ("clientes", 2): RespostaFalsa(404, {"erro": "pagina inexistente", "total_pages": 1}),
        },
    )

    with pytest.raises(
        PaginaInexistente, match="pagina inexistente: http://api.falsa/clientes page=2"
    ):
        extrair_rota(URL, "clientes")


@pytest.mark.parametrize(
    ("excecao", "mensagem"),
    [
        (requests.ConnectionError(), "sem conexao com a API em http://api.falsa"),
        (requests.Timeout(), "a API nao respondeu em 10 s"),
        (requests.exceptions.InvalidURL("url ruim"), "falha na requisicao"),
    ],
)
def test_falha_de_rede_vira_erro_claro(monkeypatch, excecao, mensagem):
    instalar_falha(monkeypatch, excecao)

    with pytest.raises(ErroExtracao, match=mensagem):
        buscar_pagina(URL, "clientes", 1)


def test_status_diferente_de_200_vira_erro_claro(monkeypatch):
    instalar_api(monkeypatch, {("pedidos", 1): RespostaFalsa(500, {"erro": "falha interna"})})

    with pytest.raises(ErroExtracao, match="resposta inesperada: .* \\(HTTP 500\\)"):
        buscar_pagina(URL, "pedidos", 1)


@pytest.mark.parametrize(
    ("corpo", "mensagem"),
    [
        (NAO_JSON, "nao e um objeto JSON"),
        ([{"id": 1}], "nao e um objeto JSON"),
        ({"items": [], "total_items": 0}, "faltam os campos \\['total_pages'\\]"),
        ({"items": "x", "total_items": 0, "total_pages": 1}, "items deve ser lista"),
        ({"items": [], "total_items": "5", "total_pages": 1}, "total_items/total_pages inteiros"),
    ],
)
def test_corpo_fora_do_formato_vira_erro_claro(monkeypatch, corpo, mensagem):
    # Antes desta validação, um campo ausente estourava como KeyError não tratado.
    instalar_api(monkeypatch, {("pedidos", 1): RespostaFalsa(200, corpo)})

    with pytest.raises(ErroExtracao, match=mensagem):
        buscar_pagina(URL, "pedidos", 1)


# --- leitura do CSV (atividade 07) ---


def test_le_produtos_sem_converter_nada(tmp_path):
    caminho = tmp_path / "produtos.csv"
    caminho.write_text(
        "produto_id,nome,categoria,preco_base\n1,Alface crespa,folhas,3.5\n2,Rúcula,folhas,4.2\n",
        encoding="utf-8",
    )

    assert ler_produtos_csv(caminho) == [
        {"produto_id": "1", "nome": "Alface crespa", "categoria": "folhas", "preco_base": "3.5"},
        {"produto_id": "2", "nome": "Rúcula", "categoria": "folhas", "preco_base": "4.2"},
    ]


def test_csv_sem_coluna_obrigatoria_vira_erro(tmp_path):
    caminho = tmp_path / "produtos.csv"
    caminho.write_text("produto_id,nome,categoria\n1,Alface,folhas\n", encoding="utf-8")

    with pytest.raises(ErroExtracao, match="faltam as colunas \\['preco_base'\\]"):
        ler_produtos_csv(caminho)


def test_csv_ausente_vira_erro(tmp_path):
    with pytest.raises(ErroExtracao, match="arquivo de produtos nao encontrado"):
        ler_produtos_csv(tmp_path / "nao_existe.csv")


def test_csv_fora_de_utf8_vira_erro(tmp_path):
    caminho = tmp_path / "produtos.csv"
    caminho.write_bytes(
        "produto_id,nome,categoria,preco_base\n1,Maçã,frutas,9.9\n".encode("latin-1")
    )

    with pytest.raises(ErroExtracao, match="nao esta em UTF-8"):
        ler_produtos_csv(caminho)


# --- brutos (atividade 08) ---


def test_salvar_bruto_grava_sem_alterar(tmp_path):
    registros = [
        {"id": 1, "email": None, "estado": "rs", "valor_total": "125,84"},
        {"id": 2, "email": "ana@exemplo.com", "cidade": "São Paulo", "valor_total": 94.34},
    ]

    caminho = salvar_bruto(registros, "pedidos", tmp_path / "brutos")

    assert caminho == tmp_path / "brutos" / "pedidos.json"
    texto = caminho.read_text(encoding="utf-8")
    assert '"valor_total": "125,84"' in texto  # texto com vírgula continua texto (A4 é na Parte 2)
    assert '"valor_total": 94.34' in texto  # número continua número, com o mesmo texto
    assert '"email": null' in texto  # nulo continua nulo (A1 é na Parte 2)
    assert '"São Paulo"' in texto  # acento legível (ensure_ascii=False)


def test_executar_extracao_grava_brutos_e_devolve_contadores(monkeypatch, tmp_path):
    instalar_api(
        monkeypatch,
        {
            ("clientes", 1): pagina(1, 2, 3, [{"id": 1}, {"id": 2}]),
            ("clientes", 2): pagina(2, 2, 3, [{"id": 3}]),
            ("pedidos", 1): pagina(1, 1, 2, [{"id": 10}, {"id": 10}]),
        },
    )
    csv_produtos = tmp_path / "produtos.csv"
    csv_produtos.write_text(
        "produto_id,nome,categoria,preco_base\n1,Alface crespa,folhas,3.5\n", encoding="utf-8"
    )
    brutos = tmp_path / "brutos"

    contadores = executar_extracao(URL, brutos, csv_produtos)

    assert contadores == {
        "clientes_paginas": 2,
        "clientes_registros": 3,
        "pedidos_paginas": 1,
        "pedidos_registros_brutos": 2,
        "produtos_registros": 1,
    }
    assert sorted(p.name for p in brutos.iterdir()) == [
        "clientes.json",
        "pedidos.json",
        "produtos.json",
    ]
    pedidos_gravados = json.loads((brutos / "pedidos.json").read_text(encoding="utf-8"))
    assert pedidos_gravados == [{"id": 10}, {"id": 10}]


def test_falha_em_pedidos_nao_grava_nenhum_bruto(monkeypatch, tmp_path):
    instalar_api(
        monkeypatch,
        {
            ("clientes", 1): pagina(1, 1, 1, [{"id": 1}]),
            ("pedidos", 1): RespostaFalsa(500, {"erro": "falha interna"}),
        },
    )
    brutos = tmp_path / "brutos"

    with pytest.raises(ErroExtracao, match="HTTP 500"):
        executar_extracao(URL, brutos, tmp_path / "produtos.csv")

    assert not brutos.exists()  # clientes foi extraído, mas nada foi gravado


# --- leitura dos brutos (entrada da transformação, Parte 2) ---


def test_ler_bruto_devolve_os_registros_gravados(tmp_path):
    registros = [{"id": 1, "valor_total": "125,84"}, {"id": 2, "email": None}]
    salvar_bruto(registros, "pedidos", tmp_path)

    assert ler_bruto("pedidos", tmp_path) == [
        {"id": 1, "valor_total": "125,84"},
        {"id": 2, "email": None},
    ]


def test_ler_bruto_ausente_vira_erro(tmp_path):
    with pytest.raises(ErroExtracao, match="bruto nao encontrado: .*clientes.json"):
        ler_bruto("clientes", tmp_path)


@pytest.mark.parametrize(
    ("conteudo", "mensagem"),
    [
        ('{"id": 1}', "deveria conter uma lista de registros"),
        ('[{"id": 1}', "nao foi possivel ler"),  # JSON cortado no meio
    ],
)
def test_ler_bruto_fora_do_formato_vira_erro(tmp_path, conteudo, mensagem):
    (tmp_path / "pedidos.json").write_text(conteudo, encoding="utf-8")

    with pytest.raises(ErroExtracao, match=mensagem):
        ler_bruto("pedidos", tmp_path)


# --- saída do ETL (formato da seção 4) ---

BRUTOS_MAIN = {
    "clientes": [
        {
            "id": 1,
            "nome": "Ana Lima",
            "email": None,
            "cidade": "Porto Alegre",
            "estado": "rs",
            "cadastro_em": "2024-01-10",
        }
    ],
    "pedidos": [
        {
            "id": 10,
            "cliente_id": 1,
            "data_pedido": "05/03/2026",
            "status": "entregue",
            "valor_total": "13,00",
            "itens": [{"produto_id": 1, "quantidade": 2, "preco_unitario": 5.0}],
        },
    ]
    * 2,  # o mesmo pedido duas vezes (A5)
    "produtos": [
        {"produto_id": "1", "nome": "Alface crespa", "categoria": "folhas", "preco_base": "3.5"}
    ],
}


# Reconciliação que confere, para o pedido 10 do BRUTOS_MAIN: itens 2 x 5.00 = 10.00.
RECONCILIACAO_OK = {
    "pedidos_origem": 1,
    "pedidos_destino": 1,
    "diferenca_pedidos": 0,
    "soma_valor_itens_origem": Decimal("10.00"),
    "soma_valor_itens_destino": Decimal("10.00"),
    "diferenca_soma": Decimal("0.00"),
    "confere": True,
}


def instalar_etl_falso(monkeypatch: pytest.MonkeyPatch, brutos: dict) -> dict:
    """Troca a extração (rede e disco) por contadores fixos, a leitura dos brutos pelo dict, e a
    carga e a reconciliação (banco) por funções que só guardam o que receberam: nenhum teste do
    main toca o banco real."""
    monkeypatch.setattr(main, "load_dotenv", lambda: None)  # não lê o .env durante o teste
    recebido = {}

    def carga_falsa(dados):
        recebido["linhas_por_tabela"] = {tabela: len(linhas) for tabela, linhas in dados.items()}
        return {"clientes": 1, "produtos": 1, "pedidos": 1, "itens_pedido": 1}

    monkeypatch.setattr(main, "executar_carga", carga_falsa)

    def reconciliacao_falsa(pedidos_brutos):
        recebido["pedidos_reconciliados"] = pedidos_brutos
        return RECONCILIACAO_OK

    monkeypatch.setattr(main, "executar_reconciliacao", reconciliacao_falsa)

    def extracao_falsa(url_base):
        recebido["url_base"] = url_base
        return {
            "clientes_paginas": 1,
            "clientes_registros": 1,
            "pedidos_paginas": 1,
            "pedidos_registros_brutos": 2,
            "produtos_registros": 1,
        }

    monkeypatch.setattr(main, "executar_extracao", extracao_falsa)
    monkeypatch.setattr(main, "ler_bruto", lambda nome: brutos[nome])
    return recebido


def test_main_imprime_contadores_no_formato_da_secao_4(monkeypatch, capsys):
    monkeypatch.setenv("API_URL", "http://api.falsa/")
    recebido = instalar_etl_falso(monkeypatch, BRUTOS_MAIN)

    assert main.main() == 0
    assert recebido["url_base"] == "http://api.falsa"  # a barra final foi removida
    # A carga recebe as linhas transformadas: o pedido repetido já saiu (A5).
    assert recebido["linhas_por_tabela"] == {
        "produtos": 1,
        "clientes": 1,
        "pedidos": 1,
        "itens_pedido": 1,
    }
    # Conta à mão: 1 pedido único (o 10) e 1 repetido; e-mail nulo, "rs", data DD/MM/AAAA e
    # valor com vírgula, 1 de cada; total 13.00 contra itens 2 x 5.00 = 10.00, divergente.
    assert capsys.readouterr().out.splitlines() == [
        "extracao: clientes paginas=1 registros=1",
        "extracao: pedidos paginas=1 registros_brutos=2",
        "extracao: produtos registros=1",
        "extracao: brutos salvos em brutos/ (clientes.json, pedidos.json, produtos.json)",
        "transformacao: pedidos_unicos=1 repetidos_descartados=1",
        "transformacao: emails_nulos=1 estados_padronizados=1 datas_convertidas=1 "
        "valores_convertidos=1",
        "carga: clientes=1 produtos=1 pedidos=1 itens=1",
        "reconciliacao: pedidos_origem=1 pedidos_destino=1 diferenca=0",
        "reconciliacao: soma_valor_itens_origem=10.00 soma_valor_itens_destino=10.00 "
        "diferenca=0.00",
        "divergentes: 1 pedidos com valor_total diferente da soma dos itens",
    ]
    # A origem da reconciliação são os brutos, com o repetido: a A5 não pode ser pulada nela.
    assert recebido["pedidos_reconciliados"] == BRUTOS_MAIN["pedidos"]


def test_main_com_falha_na_carga_sai_com_mensagem_e_codigo_1(monkeypatch, capsys):
    monkeypatch.setenv("API_URL", URL)
    instalar_etl_falso(monkeypatch, BRUTOS_MAIN)

    def carga_que_falha(dados):
        raise ErroCarga("tabela pedidos: violacao de chave estrangeira")

    monkeypatch.setattr(main, "executar_carga", carga_que_falha)

    assert main.main() == 1
    saida = capsys.readouterr()
    assert "carga:" not in saida.out  # nenhuma contagem é impressa
    assert "divergentes:" not in saida.out
    assert saida.err == "erro: carga: tabela pedidos: violacao de chave estrangeira\n"


def test_main_com_reconciliacao_que_nao_confere_sai_com_codigo_1(monkeypatch, capsys):
    monkeypatch.setenv("API_URL", URL)
    instalar_etl_falso(monkeypatch, BRUTOS_MAIN)
    faltou_o_pedido = {
        **RECONCILIACAO_OK,
        "pedidos_destino": 0,
        "diferenca_pedidos": 1,
        "soma_valor_itens_destino": Decimal("0.00"),
        "diferenca_soma": Decimal("10.00"),
        "confere": False,
    }
    monkeypatch.setattr(main, "executar_reconciliacao", lambda pedidos_brutos: faltou_o_pedido)

    assert main.main() == 1
    saida = capsys.readouterr()
    # Os números são impressos mesmo assim, para mostrar onde está a diferença.
    assert saida.out.splitlines()[-2:] == [
        "reconciliacao: pedidos_origem=1 pedidos_destino=0 diferenca=1",
        "reconciliacao: soma_valor_itens_origem=10.00 soma_valor_itens_destino=0.00 "
        "diferenca=10.00",
    ]
    assert "divergentes:" not in saida.out
    assert saida.err.startswith("erro: reconciliacao: origem e destino nao conferem")


@pytest.mark.parametrize(
    "erro",
    [
        ErroCarga("sem conexao com o PostgreSQL em localhost:5433/verdejar"),
        ErroReconciliacao('leitura do destino: relation "pedidos" does not exist'),
    ],
)
def test_main_com_falha_na_reconciliacao_sai_com_mensagem_e_codigo_1(monkeypatch, capsys, erro):
    monkeypatch.setenv("API_URL", URL)
    instalar_etl_falso(monkeypatch, BRUTOS_MAIN)

    def reconciliacao_que_falha(pedidos_brutos):
        raise erro

    monkeypatch.setattr(main, "executar_reconciliacao", reconciliacao_que_falha)

    assert main.main() == 1
    saida = capsys.readouterr()
    assert "reconciliacao:" not in saida.out
    assert "divergentes:" not in saida.out
    assert saida.err == f"erro: reconciliacao: {erro}\n"


def test_main_com_registro_invalido_sai_com_mensagem_e_codigo_1(monkeypatch, capsys):
    monkeypatch.setenv("API_URL", URL)
    pedido_ruim = dict(BRUTOS_MAIN["pedidos"][0], data_pedido="2026/03/05")
    instalar_etl_falso(monkeypatch, dict(BRUTOS_MAIN, pedidos=[pedido_ruim]))

    assert main.main() == 1
    saida = capsys.readouterr()
    assert "transformacao:" not in saida.out  # nenhum contador parcial é impresso
    assert saida.err.startswith("erro: transformacao: pedido id=10: data fora dos formatos")


def test_main_sem_api_sai_com_mensagem_e_codigo_1(monkeypatch, capsys):
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setenv("API_URL", URL)
    instalar_falha(monkeypatch, requests.ConnectionError())

    assert main.main() == 1
    saida = capsys.readouterr()
    assert saida.out == ""
    assert saida.err.startswith("erro: extracao: sem conexao com a API em http://api.falsa")
