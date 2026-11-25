# Como usei IA

**Ferramenta:** Claude Code (agente na IDE), no papel de Par com escopo limitado: propõe funções e testes quando eu peço.
A partir da Parte 1, deleguei cada parte do ETL inteira ao Claude Code (detalhes em cada entrada). Os commits foram sempre meus.

<!-- Modelo de entrada:

### N. Título
- **Trecho pedido:** o que eu pedi, e em que escopo.
- **O que a IA propôs:** resumo (e o trecho, se curto).
- **Decisão e justificativa:** por que aceitei ou rejeitei.
- **Como validei:** teste, comando ou execução, e o resultado.
-->

## Sugestões aceitas

### Parte 0:

- **Trecho pedido:** Solicitei ao Claude Code a lista de comandos a serem executados no terminal ZSH do Linux Fedora para configurar o container Docker. Também pedi explicação sobre cada comando.
- **O que a IA propôs:** Enviou a lista de comandos e configurações com explicações detalhadas.
- **Decisão e justificativa:** Os comandos enviados pela IA foram aceitos, executados e verificados com testes.
- **Como validei:** testes para verificar se o container Docker subiu corretamente.

### Parte 0:

- **Trecho pedido:** Solicitei ao Claude Code que me auxiliasse na criação das skills que serão utilizadas no projeto em .claude/skills e dos arquivos CLAUDE.md, AGENTS.md e a base de arquivos conforme orientado na guideline do projeto.
- **O que a IA propôs:** Estruturou a base do projeto criando os arquivos necessários.
- **Decisão e justificativa:** Solicitei isso para agilizar a configuração inicial.
- **Como validei:** Cada arquivo foi cuidadosamente revisado. Fiz ajustes necessários e mantive o que estava bom para o momento do projeto.

### Parte 1:

- **Trecho pedido:** Solicitei ao Claude Code: paginação da API com verificação do status HTTP, extração de clientes e pedidos com tratamento de erros, leitura do produtos.csv com o módulo csv e gravação dos brutos em brutos/. Também pedi a explicação linha a linha do código.
- **O que a IA propôs:** Escreveu etl/extracao.py (funções pequenas e a exceção ErroExtracao) e etl/main.py, que imprime os contadores no formato da seção 4. Apontou, sem corrigir, quatro pendências: falta de testes, KeyError se o JSON da API mudasse de formato, rota vazia tratada como erro e PGPORT=5432 no .env.example.
- **Decisão e justificativa:** Aceitei para agilizar a Parte 1. Pedi a explicação linha a linha para entender o código.
- **Como validei:** Execução do ETL contra a API real (clientes paginas=20 registros=1000; pedidos paginas=102 registros_brutos=5100; produtos registros=12).

### Parte 1:

- **Trecho pedido:** Solicitei ao Claude Code que corrigisse as pendências apontadas na extração após revisão e que criasse os testes necessários para fechar a Parte 1.
- **O que a IA propôs:** Validação dos campos e tipos de cada página da API, tratamento da rota vazia (404 com total_pages=0 devolve lista vazia), mensagem de 404 com o motivo dado pela API, captura de falhas gerais de requisição (ex.: API_URL sem http://), tratamento de CSV fora de UTF-8 e PGPORT=5433 no .env.example. Criou tests/test_extracao.py com 23 testes sem rede.
- **Decisão e justificativa:** Aceitei porque as correções eliminam erros não tratados.
- **Como validei:** pytest -q com 23 passed; nova execução do ETL contra a API real, com os mesmos contadores e os brutos idênticos à origem.

### Parte 2:

- **Trecho pedido:** Solicitei ao Claude Code na Parte 2: o CONTRATO_DE_DADOS.md, as funções das armadilhas A1 a A6, a remoção dos repetidos, o cálculo de valor_itens e divergente, e os contadores impressos.
- **O que a IA propôs:**
  - etl/transformacao.py, com uma função pura por armadilha: tratar_email, padronizar_estado, converter_data, converter_valor, remover_repetidos e calcular_valor_itens.
  - A função transformar, que devolve as linhas das quatro tabelas e os contadores.
  - ler_bruto, para a transformação ler os arquivos de brutos/ e não a memória.
  - O contrato coerente com o schema.sql e testes com pelo menos um caso por armadilha.
  - Dinheiro em Decimal(str(valor)) com ROUND_HALF_UP, datas só nos dois formatos exatos (MM/DD/AAAA é recusado), registro inválido interrompe o ETL com o id dele na mensagem.
- **Decisão e justificativa:** Aceitei. As regras seguem o enunciado e o AGENTS.md. Mantive três decisões propostas:
  - datas_convertidas e valores_convertidos contam só o que precisou de conversão. Se contassem tudo, seriam sempre iguais a pedidos_unicos.
  - valor_total negativo é aceito, porque existe nos dados (-1.84).
  - Registro inválido não é descartado porque isso quebraria a reconciliação.
- **Como validei:**
  - ETL contra a API real: pedidos_unicos=5000, repetidos_descartados=100, emails_nulos=81, estados_padronizados=151, datas_convertidas=1037, valores_convertidos=1255 e divergentes=238.
  - Os números foram conferidos por um script à parte, que lê os brutos sem as funções do ETL.
  - pytest -q com 93 passed.
  - 16 erros introduzidos de propósito no código, todos pegos pelos testes.

### Parte 3:

- **Trecho pedido:** Solicitei na Parte 3: carga na ordem das chaves, idempotência documentada e inserções com parâmetros e uma checagem rápida das Partes 1 e 2.
- **O que a IA propôs:**
  - etl/carga.py com psycopg 3. A conexão usa as variáveis PG\* do .env e exige as cinco; sem a PGPORT, cairia na 5432, que é o PostgreSQL nativo da máquina.
  - TRUNCATE das quatro tabelas e INSERT na ordem produtos, clientes, pedidos e itens_pedido, numa transação só.
  - INSERTs com parâmetros %(campo)s e executemany e contagens lidas do banco depois do commit.
  - tests/test_carga.py, rodando num esquema temporário sem tocar nas tabelas reais.
  - A checagem das partes anteriores achou só lacunas de documentação, como o caminho do banco faltando no README.
- **Decisão e justificativa:** Aceitei a estratégia por que julguei fazer sentido para o projeto.
- **Como validei:**
  - Duas execuções seguidas com saídas idênticas (carga: clientes=1000 produtos=12 pedidos=5000 itens=12455).
  - Testes de idempotência, de rollback e de SQL parametrizado: o nome `Robert'); DROP TABLE clientes; --` foi gravado como dado.
  - Ao tirar de propósito a transação e depois o TRUNCATE, os testes certos falharam. pytest -q com 99 passed.

### Parte 4:

- **Trecho pedido:** Solicitei na Parte 4: testes, reconciliação, consultas de validação e resultados no README.
- **O que a IA propôs:**
  - etl/reconciliacao.py, que compara a contagem de pedidos (sem tolerância) e a soma de valor_itens (tolerância de 1 centavo). Se não conferir, o ETL imprime as diferenças e sai com código 1.
  - A origem é calculada direto dos brutos, sem as funções da transformação, e o destino é lido numa conexão nova, depois do commit.
  - consultas_validacao.sql com (a), o teste de consulta, (b), (c) e um resumo dos divergentes.
  - tests/test_reconciliacao.py e tests/test_consultas.py, este lendo as consultas do próprio arquivo .sql.
  - As fixtures de banco em tests/conftest.py, inclusive uma sessão só de leitura para conferir a carga real.
  - Os testes foram escritos antes do código: falharam primeiro e passaram depois.
- **Decisão e justificativa:** Aceitei. Calcular a origem sem a transformação faz da reconciliação uma prova de verdade e não uma comparação do ETL com ele mesmo.
- **Como validei:**
  - Duas execuções seguidas, com saídas idênticas e reconciliação com diferenca=0 e diferenca=0.00 (311228.75 nos dois lados).
  - Teste de consulta: a soma dos meses é igual à soma geral (5000 pedidos; 312047.75 de valor_total e 311228.75 de valor_itens).
  - 11 erros introduzidos de propósito no código e no SQL, todos pegos.
  - pytest -q com 127 passed, sem testes pulados.

## Sugestões rejeitadas

### Parte 0: IA criando o .env

- **Trecho pedido:** Pedi para configurar o ambiente do projeto (Python, dependências, Docker e o que mais faltasse).
- **O que a IA propôs:** Além do ambiente Python, tentou criar o .env sozinha: copiar o .env.example e gravar nele uma senha aleatória (gerada com openssl) e PGPORT=5433, sem mostrar a senha.
- **Decisão e justificativa:** Rejeitei. A regra que defini no AGENTS.md é que a IA nunca lê nem altera o .env, e o .claude/settings.json nega Read e Edit nele. A tentativa por shell foi barrada pelas permissões do Claude Code.
- **Como validei:** pg_isready -p 5433 aceitando conexões e a carga conectando ao banco com as variáveis do .env. A regra ficou registrada na memória do projeto para as sessões seguintes.

### Parte 2: comando com rm -rf

- **Trecho pedido:** Parte 2. No caminho, a IA decidiu fazer um teste de mutação: colocar erros no código, um de cada vez, para ver se os testes falham.
- **O que a IA propôs:** Um comando que apagava e recriava uma pasta temporária com rm -rf, antes de copiar o código para ela.
- **Decisão e justificativa:** Rejeitado pela regra deny `Bash(rm -rf:*)` que configurei no .claude/settings.json. Não quero que o agente apague pastas sem eu ver e nem as temporárias. A IA refez o comando sem apagar nada e criando uma pasta nova.
- **Como validei:** O teste de mutação rodou na pasta nova sem remover nenhum arquivo e os testes pegaram os 16 erros introduzidos.

## Falhas e retrabalho

### Parte 0: ajustes nos arquivos da estrutura inicial

- **Falha:** Os arquivos gerados pela IA na estruturação inicial do projeto precisaram de ajustes.
- **Como descobri:** Durante a revisão detalhada de cada arquivo.
- **Retrabalho:** Ajustei CLAUDE.md, AGENTS.md, README.md, SKILL.md (data-engineer, reviwer) e .env.
- Tempo: 1h30.

### Parte 1: lacunas na primeira versão da extração

- **Falha:** A primeira versão de etl/extracao.py, proposta pela IA, tinha quatro problemas:
  - não tinha testes;
  - estourava KeyError se o JSON da API mudasse de formato;
  - tratava a rota vazia (404 com total_pages=0) como erro;
  - o .env.example trazia PGPORT=5432, que nesta máquina é outro PostgreSQL, o nativo.
- **Como descobri:** A IA listou as pendências ao entregar a parte. Revisei e pedi a correção antes de começar a Parte 2.
- **Retrabalho:** Validação dos campos e tipos de cada página, rota vazia devolvendo ([], 0), PGPORT=5433 e 23 testes.
- Tempo: 2h.

### Parte 2: teste de arredondamento que não testava

- **Falha:** O teste da A4 com 2.675 passava mesmo com o arredondamento errado. Com o arredondamento bancário (ROUND_HALF_EVEN), 2.675 também vira 2.68 então o teste não distinguia o ROUND_HALF_UP exigido no contrato.
- **Como descobri:** No teste de mutação a troca de ROUND_HALF_UP por ROUND_HALF_EVEN passou sem nenhum teste falhar.
- **Retrabalho:** Novo caso no teste: `converter_valor("2,665") == Decimal("2.67")`, em que o arredondamento bancário daria 2.66. Com isso, os 16 erros introduzidos passaram a ser pegos.
- Tempo: 1h.

### Parte 4: teste de reconciliação que não pegava o erro do float

- **Falha:** Se a reconciliação usasse Decimal(preco) direto do float da API, sem o str(), nenhum teste falharia. O arredondamento final para 2 casas escondia o erro binário nos casos testados.
- **Como descobri:** No teste de mutação essa troca passou sem nenhum teste falhar.
- **Retrabalho:** Novo caso com preço 2.675. Pelo float, Decimal(2.675) é 2.67499999... e arredonda para 2.67 e o certo é 2.68.
- **Como validei:** Nova rodada de mutação, com os 7 erros da reconciliação pegos; pytest -q com 127 passed.
- Tempo: 1h30.
