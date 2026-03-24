"""Agente A2A responsavel por estudar o banco e entender o schema.

Este agente trabalha de forma autonoma dentro do seu dominio: ele decide como
descobrir o schema, mas sempre delega a leitura fisica ao Executer via A2A.
"""

from __future__ import annotations

from typing import Any

from agents.runtime import A2AClient, A2AMessage, Agent


DISCOVER_SCHEMA_INSTRUCTIONS = """
Voce e o agente responsavel por estudar o banco de dados e entender o schema.
Voce nao acessa o banco diretamente. Quando precisar de metadados fisicos, chame
o agente Executer via A2A. Seu objetivo e devolver uma visao organizada do schema
para os outros agentes.
""".strip()


class DiscoverSchemaService:
    """Servico do agente DiscoverSchema, isolado da implementacao do Executer."""

    def __init__(self, executer_client: A2AClient) -> None:
        self.executer_client = executer_client

    def list_tables(self) -> list[str]:
        return self.executer_client.call("list_tables")

    def list_columns(self, table_name: str) -> list[dict[str, Any]]:
        return self.executer_client.call("list_columns", table_name=table_name)

    def describe_table(self, table_name: str) -> dict[str, Any]:
        return self.executer_client.call("describe_table", table_name=table_name)

    def describe_schema(self) -> dict[str, list[dict[str, Any]]]:
        return {
            table_name: self.list_columns(table_name)
            for table_name in self.list_tables()
        }

    def handle_a2a_message(self, message: A2AMessage) -> Any:
        if message.action == "describe_schema":
            return self.describe_schema()
        if message.action == "describe_table":
            return self.describe_table(message.payload["table_name"])
        raise ValueError(f"Acao A2A desconhecida para DiscoverSchema: {message.action}")


schema_agent = Agent(
    name="DiscoverSchema",
    model="gemini-2.0-flash",
    instruction=DISCOVER_SCHEMA_INSTRUCTIONS,
)
