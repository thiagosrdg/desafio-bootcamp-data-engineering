"""Extração (Parte 1).

Responsabilidades:
- percorrer uma rota paginada da API (page, page_size) até total_pages, verificando o status HTTP;
- extrair clientes e pedidos, tratando erro de conexão e página inexistente com mensagem clara;
- ler produtos.csv com o módulo csv;
- salvar os dados brutos em brutos/ antes de qualquer transformação;
- informar os contadores de páginas e registros.
"""
