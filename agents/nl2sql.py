"""Agente A2A responsavel por traduzir linguagem natural em consultas SQL.

Ele nao acessa banco nem schema diretamente. Sua especialidade e interpretar o
pedido do usuario e sugerir consultas de metadados adequadas.
"""

from __future__ import annotations

from typing import Any

from agents.a2a_integration import A2AEnvelope
from agents.runtime import Agent


NL2SQL_INSTRUCTIONS = """
Voce e o agente responsavel por traduzir a linguagem natural do usuario para SQL.
Seu foco atual e construir consultas de introspeccao para apoiar a geracao de um
dicionario de dados. Gere SQL legivel e seguro, sempre orientado a metadados.
""".strip()


class NL2SQLService:
    """Servico especializado em interpretar intencao e propor SQL."""

    def explain_request(self, user_request: str) -> str:
        normalized = user_request.lower()
        if "relacion" in normalized:
            return "Priorizar consultas sobre chaves estrangeiras e cardinalidade."
        if "coluna" in normalized or "schema" in normalized:
            return "Priorizar consultas sobre colunas, tipos e nulabilidade."
        return (
            "Combinar consultas de schema e relacionamentos para montar o dicionario."
        )

    def build_metadata_query(self, table_name: str) -> str:
        return (
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            f"WHERE table_name = '{table_name}' "
            "ORDER BY ordinal_position;"
        )

    def handle_a2a_message(self, message: A2AEnvelope) -> Any:
        if message.action == "explain_request":
            return self.explain_request(message.payload["user_request"])
        if message.action == "build_metadata_query":
            return self.build_metadata_query(message.payload["table_name"])
        raise ValueError(f"Acao A2A desconhecida para NL2SQL: {message.action}")


nl2sql_agent = Agent(
    name="NL2SQL",
    model="gemini-2.0-flash",
    instruction=NL2SQL_INSTRUCTIONS,
)
