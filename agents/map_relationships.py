"""Agente A2A responsavel por mapear relacoes entre tabelas.

Ele trabalha apenas com o problema de relacionamentos. Quando precisa de dados
fisicos de constraints, chama o Executer via A2A.
"""

from __future__ import annotations

from typing import Any

from agents.runtime import A2AClient, A2AMessage, Agent


MAP_RELATIONSHIPS_INSTRUCTIONS = """
Voce e o agente responsavel por analisar o banco e mapear as relacoes entre as
tabelas. Quando precisar de constraints ou chaves estrangeiras, consulte o agente
Executer via A2A. Entregue um mapa claro das relacoes por tabela de origem.
""".strip()


class MapRelationshipsService:
    """Servico do agente de relacionamentos, isolado do acesso ao banco."""

    def __init__(self, executer_client: A2AClient) -> None:
        self.executer_client = executer_client

    def map_relationships(self) -> dict[str, list[dict[str, str]]]:
        grouped: dict[str, list[dict[str, str]]] = {}
        for relationship in self.executer_client.call("list_relationships"):
            grouped.setdefault(relationship["source_table"], []).append(relationship)
        return grouped

    def handle_a2a_message(self, message: A2AMessage) -> Any:
        if message.action == "map_relationships":
            return self.map_relationships()
        raise ValueError(
            f"Acao A2A desconhecida para MapRelationships: {message.action}"
        )


relationship_agent = Agent(
    name="MapRelationships",
    model="gemini-2.0-flash",
    instruction=MAP_RELATIONSHIPS_INSTRUCTIONS,
)
