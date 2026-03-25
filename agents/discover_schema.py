"""Agente A2A responsavel por estudar o banco e entender o schema.

Este agente trabalha de forma autonoma dentro do seu dominio: ele decide como
descobrir o schema, mas sempre delega a leitura fisica ao Executer via A2A.
"""

from __future__ import annotations

from typing import Any

from agents.a2a_integration import A2AEnvelope, LocalA2AClient
from agents.runtime import Agent


DISCOVER_SCHEMA_INSTRUCTIONS = """
Voce e o agente responsavel por estudar o banco de dados e entender o schema.
Voce nao acessa o banco diretamente. Quando precisar de metadados fisicos, chame
o agente Executer via A2A. Seu objetivo e devolver uma visao organizada do schema
para os outros agentes.
""".strip()


class DiscoverSchemaService:
    """Servico do agente DiscoverSchema, isolado da implementacao do Executer."""

    def __init__(self, executer_client: LocalA2AClient) -> None:
        self.executer_client = executer_client

    def list_tables(self, trace: list[dict[str, str]] | None = None) -> list[str]:
        payload: dict[str, object] = {}
        if trace is not None:
            payload["trace"] = trace
        return self.executer_client.call("list_tables", **payload)

    def list_columns(
        self,
        table_name: str,
        trace: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, object] = {"table_name": table_name}
        if trace is not None:
            payload["trace"] = trace
        return self.executer_client.call("list_columns", **payload)

    def describe_table(
        self,
        table_name: str,
        trace: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, object] = {"table_name": table_name}
        if trace is not None:
            payload["trace"] = trace
        return self.executer_client.call("describe_table", **payload)

    def describe_schema(
        self,
        trace: list[dict[str, str]] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            table_name: self.list_columns(table_name, trace=trace)
            for table_name in self.list_tables(trace=trace)
        }

    def handle_a2a_message(self, message: A2AEnvelope) -> Any:
        trace = message.payload.get("trace")
        if message.action == "describe_schema":
            return self.describe_schema(
                trace=trace if isinstance(trace, list) else None
            )
        if message.action == "describe_table":
            return self.describe_table(
                message.payload["table_name"],
                trace=trace if isinstance(trace, list) else None,
            )
        raise ValueError(f"Acao A2A desconhecida para DiscoverSchema: {message.action}")


schema_agent = Agent(
    name="DiscoverSchema",
    model="gemini-2.0-flash",
    instruction=DISCOVER_SCHEMA_INSTRUCTIONS,
)
