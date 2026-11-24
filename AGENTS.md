# Desafio Final: ETL da Verdejar. Regras para agentes de IA

ETL que leva clientes e pedidos de uma API local (paginada) e produtos de um CSV para um PostgreSQL,
com seis armadilhas de qualidade (A1 a A6), testes e reconciliação.
O contrato está em `CONTRATO_DE_DADOS.md`.

## Seu papel: Par com escopo limitado (regra do programa)
- Você  cria e realiza funções e testes **somente quando eu peço**, dentro do escopo que eu definir.
- **Eu** executo, depuro, corrijo, explico e faço os commits.
- Se o pedido estiver ambíguo, diga e proponha como dividir. Não presuma.
- Explique cada proposta linha por linha.
- Se você vir um problema fora do escopo do pedido, **aponte**, mas não corrija sem minha revisão.

## Regras técnicas
- **Testes:** os valores esperados vêm de mim. Nunca calcule o esperado com a própria função testada.

- **Saída do ETL:** texto simples, uma informação por linha, sem cores e sem barras de progresso
  (formato da seção 4 do enunciado).
- **Dinheiro:** `decimal.Decimal`, nunca `float`.
- **SQL:** sempre com parâmetros, nunca montado concatenando texto com dados.
- **Brutos:** salvos em `brutos/` antes de qualquer transformação.
- **Segredos:** nunca leia o `.env` e nunca coloque senha no código.
- **Nada inventado:** antes de dizer que algo funciona, rode o comando e mostre a saída real.

## Comandos
- Testes: `pytest -q`
- Lint: `ruff check .`
- Formatação: `ruff format .`
- API: `python insumos/api_verdejar.py --dados insumos/dados`
- ETL: `python -m etl.main`


