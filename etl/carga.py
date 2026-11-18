"""Carga (Parte 3).

Responsabilidades:
- conectar ao PostgreSQL com as credenciais de variáveis de ambiente (nunca no código);
- carregar na ordem das chaves estrangeiras: produtos, clientes, pedidos, itens_pedido;
- garantir idempotência (estratégia documentada no README);
- usar consultas parametrizadas.
"""
