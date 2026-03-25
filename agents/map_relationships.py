"""Agente A2A responsavel por mapear relacoes entre tabelas.

Ele trabalha apenas com o problema de relacionamentos. Quando precisa de dados
fisicos de constraints, chama o Executer via A2A.
"""

from __future__ import annotations

from typing import Any

from agents.a2a_integration import A2AEnvelope, LocalA2AClient
from agents.runtime import Agent


MAP_RELATIONSHIPS_INSTRUCTIONS = """
Voce e o agente responsavel por analisar o banco e mapear as relacoes entre as
tabelas. Quando precisar de constraints ou chaves estrangeiras, consulte o agente
Executer via A2A. Entregue um mapa claro das relacoes por tabela de origem.
""".strip()


class MapRelationshipsService:
    """Servico do agente de relacionamentos, isolado do acesso ao banco."""

    def __init__(self, executer_client: LocalA2AClient) -> None:
        self.executer_client = executer_client

    def map_relationships(
        self,
        trace: list[dict[str, str]] | None = None,
    ) -> dict[str, list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = {}
        payload: dict[str, object] = {}
        if trace is not None:
            payload["trace"] = trace
        for relationship in self.executer_client.call("list_relationships", **payload):
            grouped.setdefault(relationship["source_table"], []).append(relationship)
        return grouped

    def handle_a2a_message(self, message: A2AEnvelope) -> Any:
        if message.action == "map_relationships":
            trace = message.payload.get("trace")
            return self.map_relationships(
                trace=trace if isinstance(trace, list) else None
            )
        raise ValueError(
            f"Acao A2A desconhecida para MapRelationships: {message.action}"
        )


relationship_agent = Agent(
    name="MapRelationships",
    model="gemini-2.0-flash",
    instruction=MAP_RELATIONSHIPS_INSTRUCTIONS,
)
