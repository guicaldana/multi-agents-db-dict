# Sistema multi-agente para construção de um dicionário de dados

Este projeto é um sistema multi-agente que utiliza IA para consultar e analisar bancos de dados e com isso construir um dicionário de dados. Tal dicionário de dados deve conter informações sobre as tabelas, colunas, relações entre tabelas, etc.

## Agentes

- **Orquestrador**: Agente responsável por orquestrar os outros agentes.
- **Discover Schema**: Agente responsável por estudar o banco de dados e entender o schema.
- **Map Relationships**: Agente responsável por analisar o banco de dados e mapear as relações entre as tabelas.
- **NL2SQL**: Agente responsável por traduzir a linguagem natural escrita pelo usuário para SQL.
- **Executer**: Agente responsável por executar as consultas SQL no banco de dados.



