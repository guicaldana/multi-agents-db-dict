# Sistema multi-agente para construcao de um dicionario de dados

Este projeto implementa a base de um sistema multi-agente para inspecionar um banco de dados e produzir um dicionario de dados. A arquitetura foi organizada em torno de dois conceitos principais:

- `A2A`: cada agente possui uma responsabilidade clara e um contrato bem definido, inclusive na comunicacao entre agentes.
- `MCP`: o acesso fisico ao banco fica concentrado no agente `Executer`, que expoe tools de introspeccao.

O principio central do projeto e que cada agente trabalha isolado na sua propria
especialidade e so chama outro agente quando precisa de uma capacidade externa ao
seu dominio.

## Agentes

- `Orchestrator`: coordena os demais agentes e consolida a resposta final, sem executar trabalho especializado.
- `DiscoverSchema`: entende o schema e chama o `Executer` via A2A quando precisa de metadados fisicos.
- `MapRelationships`: entende relacionamentos e chama o `Executer` via A2A quando precisa de constraints.
- `NL2SQL`: interpreta o pedido do usuario e sugere consultas SQL de metadados.
- `BuildDictionary`: transforma metadados tecnicos em um dicionario de dados semantico.
- `Executer`: representa a camada de acesso fisico ao banco via MCP e responde a requisicoes A2A dos outros agentes.

## Estrutura atual

- `agents/executer.py`: servidor MCP e agente de execucao fisica do banco.
- `agents/discover_schema.py`: agente especializado em schema, consumindo o `Executer` via A2A.
- `agents/runtime.py`: adaptadores leves e contratos basicos de mensagens A2A.
- `agents/map_relationships.py`: agente especializado em relacionamentos, tambem consumindo o `Executer` via A2A.
- `agents/nl2sql.py`: agente especializado em traducao para SQL de metadados.
- `agents/build_dictionary.py`: agente especializado em enriquecer o resultado com descricoes semanticas.
- `agents/orchestrator.py`: coordenacao do fluxo usando apenas chamadas A2A.
- `main.py`: exemplo simples de execucao ponta a ponta.
- `tests/test_a2a_contracts.py`: testes de contrato para garantir que os agentes colaboram apenas via A2A.

## Como executar

Instale as dependencias e rode:

```bash
python main.py
```

A saida agora inclui uma trilha de execucao em `execution_trace`, mostrando quais agentes foram usados e em qual ordem. Alem disso, o resultado completo e salvo automaticamente em um arquivo JSON com nome derivado do banco atual, por exemplo `chinook_data_dictionary.json`.

Se quiser testar com um PostgreSQL real, configure a variavel `DATABASE_URL` antes de executar:

```bash
export DATABASE_URL="postgresql://usuario:senha@host:5432/banco"
python main.py
```

Sem `DATABASE_URL`, o sistema cai automaticamente no catalogo mockado local.

Tambem e possivel usar SQLite com um arquivo local:

```bash
export DATABASE_URL="sqlite:///./Chinook.db"
python main.py
```

Para testar com o banco Chinook, baixe o arquivo SQLite do projeto Chinook e aponte `DATABASE_URL` para ele. O `Executer` vai introspectar tabelas, colunas e chaves estrangeiras via SQLite sem mudar os contratos A2A dos outros agentes.

Agora a saida final tambem inclui `data_dictionary`, que representa o dicionario de dados semantico gerado a partir do schema introspectado.

Para validar os contratos A2A localmente:

```bash
pytest
```

Para iniciar apenas o servidor MCP do executer:

```bash
python agents/executer.py
```

## Proximos passos naturais

- trocar o catalogo mockado por introspeccao real em PostgreSQL via `psycopg2`;
- conectar os agentes A2A por transporte real, em vez de apenas servicos locais;
- exportar o dicionario final em JSON e Markdown;
- adicionar testes para os contratos entre agentes.

## Bancos publicos para teste

Voce pode apontar `DATABASE_URL` para bases de demonstracao disponiveis na internet, desde que exponham PostgreSQL com acesso de leitura. Algumas opcoes comuns sao:

- instancias temporarias criadas em Neon, Supabase ou Railway;
- bancos de exemplo hospedados pelo proprio curso, laboratorio ou equipe;
- containers locais publicados via tunel seguro apenas para testes.

Como bancos publicos realmente abertos mudam com frequencia e podem sair do ar, o projeto foi deixado com fallback local. Assim voce consegue desenvolver o fluxo A2A + MCP mesmo quando nao tiver uma base remota estavel.

Para o caso do Chinook, a opcao mais pratica e usar a versao SQLite local, porque ela e estavel, facil de baixar e boa para validar introspeccao de schema e relacionamentos.

## Evolucao para A2A real

Hoje o projeto usa `A2AClient` local para simular a troca de mensagens entre agentes sem depender de rede. Para migrar para um transporte A2A real, o caminho recomendado e:

- expor cada `handle_a2a_message` como endpoint ou worker independente;
- trocar o `handler` local por um cliente HTTP, RPC ou fila;
- manter o mesmo contrato de `action` e `payload` para nao reescrever a logica dos agentes;
- preservar o `Executer` como unico agente com acesso MCP ao banco.
