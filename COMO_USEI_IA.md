# Como usei IA

**Ferramenta:** Claude Code (agente na IDE), no papel de Par com escopo limitado: propõe funções e testes quando eu peço.

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
###  
 ### Parte 1:

- **Trecho pedido:** Solicitei ao Claude Code que corrigisse as pendências apontadas na extração após revisão e que criasse os testes necessários para fechar a Parte 1. 
- **O que a IA propôs:** Validação dos campos e tipos de cada página da API, tratamento da rota vazia (404 com total_pages=0 devolve lista vazia), mensagem de 404 com o motivo dado pela API, captura de falhas gerais de requisição (ex.: API_URL sem http://), tratamento de CSV fora de UTF-8 e PGPORT=5433 no .env.example. Criou tests/test_extracao.py com 23 testes sem rede (API falsa com monkeypatch, arquivos em pasta temporária e valores esperados escritos à mão).
- **Decisão e justificativa:** Aceitei porque as correções eliminam erros não tratados.
- **Como validei:** pytest -q com 23 passed; nova execução do ETL contra a API real, com os mesmos contadores e os brutos idênticos à origem; API real com dados vazios devolvendo ([], 0) para clientes e pedidos.



## Sugestões rejeitadas

## Falhas e retrabalho

Parte 0:  
Retrabalho: Ajustes em arquivos gerados pela IA na estruturação inicial do projeto.

Descobri a necessidade de ajustes durante a revisão detalhada de cada arquivo.

Arquivos ajustados: CLAUDE.md, AGENTS.md, README.md, SKILL.md (data-engineer, reviwer) e .env

Tempo: 1h30
