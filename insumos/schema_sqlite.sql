-- Esquema de destino do Desafio Final do Bootcamp (Verdejar) adaptado ao SQLite (caminho de contingencia).
-- Diferencas em relacao ao schema.sql do PostgreSQL: datas guardadas como texto ISO (AAAA-MM-DD);
-- booleano como inteiro 0 ou 1; CHAR(2) como TEXT. Ative as chaves estrangeiras com PRAGMA foreign_keys = ON.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS clientes (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL,
    email         TEXT,
    cidade        TEXT NOT NULL,
    estado        TEXT NOT NULL CHECK (length(estado) = 2),
    cadastro_em   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    produto_id    INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL,
    categoria     TEXT NOT NULL,
    preco_base    NUMERIC NOT NULL
);

CREATE TABLE IF NOT EXISTS pedidos (
    id            INTEGER PRIMARY KEY,
    cliente_id    INTEGER NOT NULL REFERENCES clientes(id),
    data_pedido   TEXT NOT NULL,
    status        TEXT NOT NULL,
    valor_total   NUMERIC NOT NULL,
    valor_itens   NUMERIC NOT NULL,
    divergente    INTEGER NOT NULL DEFAULT 0 CHECK (divergente IN (0, 1))
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    pedido_id       INTEGER NOT NULL REFERENCES pedidos(id),
    linha           INTEGER NOT NULL,
    produto_id      INTEGER NOT NULL REFERENCES produtos(produto_id),
    quantidade      INTEGER NOT NULL,
    preco_unitario  NUMERIC NOT NULL,
    PRIMARY KEY (pedido_id, linha)
);
