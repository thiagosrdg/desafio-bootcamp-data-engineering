# Contrato de dados

Para cada tabela de destino (ver `insumos/schema.sql`): campo, tipo, se admite nulo, origem e regra de transformação.
As regras das armadilhas A1 a A6 aparecem na coluna "Regra". As funções citadas estão em `etl/transformacao.py`.

## Regras gerais

- **Entrada:** a transformação lê os arquivos de `brutos/` (gravados pela extração sem nenhuma alteração), não a API.
- **Ordem:** primeiro a A5 (remove os pedidos repetidos) e depois as demais regras. Por isso os contadores de datas,
  valores e divergentes contam só os pedidos únicos.
- **Dinheiro:** sempre `decimal.Decimal` com 2 casas, arredondado meio centavo para cima (`ROUND_HALF_UP`). Nunca `float`.
- **Datas:** só dois formatos são aceitos, e só na forma exata, com zero à esquerda: `AAAA-MM-DD` e `DD/MM/AAAA`.
  O formato `MM/DD/AAAA` nunca é aceito.
- **Texto obrigatório:** sai sem espaços nas pontas. Se vier vazio, ausente ou não for texto, é um erro.
- **Registro inválido:** interrompe a execução com uma mensagem que identifica o registro (por exemplo,
  `pedido id=99: data fora dos formatos...`). Nenhum registro é descartado em silêncio, porque isso quebraria a reconciliação.

## produtos

Origem: `insumos/dados/produtos.csv`, lido com o módulo `csv` (todos os valores chegam como texto). Função: `tratar_produto`.

| Campo | Tipo | Nulo? | Origem | Regra |
|---|---|---|---|---|
| produto_id | INTEGER (PK) | não | `produto_id` | Texto convertido em inteiro. |
| nome | TEXT | não | `nome` | Texto obrigatório. |
| categoria | TEXT | não | `categoria` | Texto obrigatório (folhas, legumes, frutas). |
| preco_base | NUMERIC(10,2) | não | `preco_base` | Texto com ponto (`3.5`) convertido em `Decimal` com 2 casas (`3.50`), pela mesma função da A4. |

## clientes

Origem: API, rota `/clientes`. Função: `tratar_cliente`.

| Campo | Tipo | Nulo? | Origem | Regra |
|---|---|---|---|---|
| id | INTEGER (PK) | não | `id` | Copiado como veio. |
| nome | TEXT | não | `nome` | Texto obrigatório. |
| email | TEXT | **sim** | `email` | **A1** (`tratar_email`): o cliente é sempre mantido. `null` ou texto em branco vira `NULL`. Os demais e-mails saem sem espaços nas pontas. Contador: `emails_nulos`. |
| cidade | TEXT | não | `cidade` | Texto obrigatório. |
| estado | CHAR(2) | não | `estado` | **A2** (`padronizar_estado`): sem espaços nas pontas e em maiúsculas (`rs` vira `RS`). Precisa ser uma sigla de exatamente 2 letras. Contador: `estados_padronizados` (clientes cujo estado mudou). |
| cadastro_em | DATE | não | `cadastro_em` | Convertido em data pela mesma função da A3. Na origem vem sempre em `AAAA-MM-DD`, por isso não entra no contador `datas_convertidas`. |

## pedidos

Origem: API, rota `/pedidos`. Funções: `remover_repetidos`, `tratar_pedido` e `calcular_valor_itens`.

| Campo | Tipo | Nulo? | Origem | Regra |
|---|---|---|---|---|
| id | INTEGER (PK) | não | `id` | **A5** (`remover_repetidos`): um pedido por id. Fica a primeira ocorrência, na ordem das páginas da API (1 até `total_pages`), que a extração e os brutos preservam. Contadores: `pedidos_unicos` e `repetidos_descartados`. |
| cliente_id | INTEGER (FK clientes.id) | não | `cliente_id` | Copiado como veio. A chave estrangeira é conferida pelo banco na carga. |
| data_pedido | DATE | não | `data_pedido` | **A3** (`converter_data`): `AAAA-MM-DD` ou `DD/MM/AAAA` viram data (`19/02/2026` vira 19 de fevereiro de 2026). Qualquer outro formato, ou uma data inexistente como `31/02/2026`, é erro. Contador: `datas_convertidas` (pedidos únicos cuja data veio em `DD/MM/AAAA`). |
| status | TEXT | não | `status` | Texto obrigatório (entregue, em_transporte, cancelado). |
| valor_total | NUMERIC(12,2) | não | `valor_total` | **A4** (`converter_valor`): número (`94.34`) ou texto com vírgula decimal (`125,84`) viram `Decimal` com 2 casas. O valor é gravado como veio, mesmo divergente (A6). Texto com separador de milhar (`1.234,56`) é recusado, por ser ambíguo. Valor negativo é aceito: existe nos dados (`-1.84`), resultado do ajuste da A6. Contador: `valores_convertidos` (pedidos únicos cujo valor veio como texto). |
| valor_itens | NUMERIC(12,2) | não | calculado | **A6** (`calcular_valor_itens`): soma de `quantidade × preco_unitario` dos itens do pedido, em `Decimal`. |
| divergente | BOOLEAN | não | calculado | **A6**: `TRUE` quando a diferença entre `valor_total` e `valor_itens` é maior que 1 centavo (`> 0.01`). Diferença de exatamente 1 centavo não é divergência. Contador: `divergentes`. |

## itens_pedido

Origem: API, rota `/pedidos` (lista `itens` de cada pedido único, depois da A5). Função: `tratar_item`.

| Campo | Tipo | Nulo? | Origem | Regra |
|---|---|---|---|---|
| pedido_id | INTEGER (FK pedidos.id; PK com linha) | não | `id` do pedido | Copiado do pedido ao qual o item pertence. |
| linha | INTEGER (PK com pedido_id) | não | posição na lista `itens` | Começa em 1 e segue a ordem da API. A API não manda um número de linha. |
| produto_id | INTEGER (FK produtos.produto_id) | não | `itens[].produto_id` | Copiado como veio. A chave estrangeira é conferida pelo banco na carga. |
| quantidade | INTEGER | não | `itens[].quantidade` | Precisa ser um inteiro maior que zero. Texto, decimal ou booleano é erro. |
| preco_unitario | NUMERIC(10,2) | não | `itens[].preco_unitario` | Número convertido em `Decimal` com 2 casas, pela mesma função da A4. |

## Contadores impressos

A transformação imprime estas linhas, no formato da seção 4 do enunciado:

```text
transformacao: pedidos_unicos=N repetidos_descartados=N
transformacao: emails_nulos=N estados_padronizados=N datas_convertidas=N valores_convertidos=N
divergentes: N pedidos com valor_total diferente da soma dos itens
```

| Contador | O que conta |
|---|---|
| pedidos_unicos | Pedidos depois da A5. |
| repetidos_descartados | Pedidos brutos menos pedidos únicos. |
| emails_nulos | Clientes com `email` nulo depois da A1. |
| estados_padronizados | Clientes cujo `estado` mudou na A2. |
| datas_convertidas | Pedidos únicos com `data_pedido` em `DD/MM/AAAA`, convertida na A3. |
| valores_convertidos | Pedidos únicos com `valor_total` em texto, convertido na A4. |
| divergentes | Pedidos únicos com `divergente = TRUE` (A6). |
