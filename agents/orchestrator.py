"""Agente orquestrador do sistema multi-agente.

O orquestrador nao executa trabalho especializado. Ele apenas coordena os demais
agentes via A2A e consolida a resposta final.
"""

from __future__ import annotations

from typing import Any

from agents.runtime import A2AClient, A2AMessage, Agent


ORCHESTRATOR_INSTRUCTIONS = """
Voce e o agente orquestrador. Seu trabalho e coordenar os demais agentes A2A,
solicitando schema, relacionamentos e interpretacao do pedido para montar um
dicionario de dados consolidado.
""".strip()


class DataDictionaryOrchestrator:
    """Coordena agentes especialistas exclusivamente por meio de A2A."""

    def __init__(
        self,
        discover_schema_client: A2AClient,
        map_relationships_client: A2AClient,
        nl2sql_client: A2AClient,
        build_dictionary_client: A2AClient,
        executer_client: A2AClient,
    ) -> None:
        self.discover_schema_client = discover_schema_client
        self.map_relationships_client = map_relationships_client
        self.nl2sql_client = nl2sql_client
        self.build_dictionary_client = build_dictionary_client
        self.executer_client = executer_client

    def generate_data_dictionary(self, user_request: str) -> dict[str, object]:
        trace: list[dict[str, str]] = []

        schema = self.discover_schema_client.call("describe_schema", trace=trace)
        relationship_map = self.map_relationships_client.call(
            "map_relationships", trace=trace
        )
        interpretation = self.nl2sql_client.call(
            "explain_request", user_request=user_request, trace=trace
        )
        database_mode = self.executer_client.call("database_mode", trace=trace)
        database_label = self.executer_client.call("database_label", trace=trace)

        tables: list[dict[str, object]] = []
        for table_name, columns in schema.items():
            table_details = self.discover_schema_client.call(
                "describe_table", table_name=table_name, trace=trace
            )
            metadata_query = self.nl2sql_client.call(
                "build_metadata_query", table_name=table_name, trace=trace
            )
            tables.append(
                {
                    "table_name": table_name,
                    "description": table_details.get("description", ""),
                    "metadata_query": metadata_query,
                    "columns": columns,
                    "relationships": relationship_map.get(table_name, []),
                }
            )

        dictionary_payload = self.build_dictionary_client.call(
            "build_dictionary",
            user_request=user_request,
            interpretation=interpretation,
            tables=tables,
            trace=trace,
        )

        return {
            "request": user_request,
            "interpretation": interpretation,
            "database_mode": database_mode,
            "database_label": database_label,
            "execution_trace": trace,
            "tables": tables,
            "data_dictionary": dictionary_payload["dictionary"],
        }

    def handle_a2a_message(self, message: A2AMessage) -> Any:
        if message.action == "generate_data_dictionary":
            return self.generate_data_dictionary(message.payload["user_request"])
        raise ValueError(f"Acao A2A desconhecida para Orchestrator: {message.action}")


orchestrator_agent = Agent(
    name="Orchestrator",
    model="gemini-2.0-flash",
    instruction=ORCHESTRATOR_INSTRUCTIONS,
)
