-- Consultas de validação do ETL da Verdejar (PostgreSQL). Os resultados estão no README.
-- Rodar depois do ETL, pelo psql de dentro do contêiner (sem pedir senha):
--   docker exec -i verdejar-pg psql -U postgres -d verdejar < consultas_validacao.sql
-- Cada consulta começa por uma linha "-- consulta: <nome>". O tests/test_consultas.py lê este
-- arquivo por esses marcadores e roda exatamente estas consultas.

-- (a) Total de vendas por mês.
-- Entram todos os pedidos da tabela, de qualquer status, para que a soma dos meses possa ser
-- comparada com a soma geral. Duas colunas de valor: valor_total é o valor informado no pedido;
-- valor_itens é a soma dos itens (A6), o mesmo valor conferido pela reconciliação do ETL.
-- consulta: vendas_por_mes
SELECT
    TO_CHAR(DATE_TRUNC('month', data_pedido), 'YYYY-MM') AS mes,
    COUNT(*) AS pedidos,
    SUM(valor_total) AS valor_total,
    SUM(valor_itens) AS valor_itens
FROM pedidos
GROUP BY mes
ORDER BY mes;

-- (a) Teste de consulta: a soma dos meses deve ser igual à soma geral da tabela.
-- O WITH repete a consulta (a). As duas linhas do resultado precisam ter os mesmos números.
-- consulta: teste_vendas_por_mes
WITH vendas_por_mes AS (
    SELECT
        TO_CHAR(DATE_TRUNC('month', data_pedido), 'YYYY-MM') AS mes,
        COUNT(*) AS pedidos,
        SUM(valor_total) AS valor_total,
        SUM(valor_itens) AS valor_itens
    FROM pedidos
    GROUP BY mes
)
SELECT 'soma dos meses' AS conta, SUM(pedidos) AS pedidos,
       SUM(valor_total) AS valor_total, SUM(valor_itens) AS valor_itens
FROM vendas_por_mes
UNION ALL
SELECT 'soma geral', COUNT(*), SUM(valor_total), SUM(valor_itens)
FROM pedidos;

-- (b) Quantidade de pedidos por estado (o estado do cliente que fez o pedido).
-- consulta: pedidos_por_estado
SELECT c.estado, COUNT(*) AS pedidos
FROM pedidos AS p
JOIN clientes AS c ON c.id = p.cliente_id
GROUP BY c.estado
ORDER BY pedidos DESC, c.estado;

-- (c) Pedidos divergentes (A6): valor_total diferente da soma dos itens em mais de 1 centavo.
-- diferenca = valor_total - valor_itens.
-- consulta: pedidos_divergentes
SELECT id, cliente_id, data_pedido, status, valor_total, valor_itens,
       valor_total - valor_itens AS diferenca
FROM pedidos
WHERE divergente
ORDER BY id;

-- (c) Resumo dos divergentes: quantos pedidos há com cada diferença.
-- consulta: divergentes_por_diferenca
SELECT valor_total - valor_itens AS diferenca, COUNT(*) AS pedidos
FROM pedidos
WHERE divergente
GROUP BY diferenca
ORDER BY pedidos DESC, diferenca;
