"""Agente A2A responsavel por transformar metadados em dicionario semantico.

Este agente recebe schema, relacionamentos e contexto textual do pedido do
usuario. A partir disso, monta uma estrutura mais proxima de um dicionario de
dados real, com descricoes semanticas, papeis de colunas e relacoes explicadas.
"""

from __future__ import annotations

from typing import Any, cast

from agents.a2a_integration import A2AEnvelope
from agents.runtime import Agent


BUILD_DICTIONARY_INSTRUCTIONS = """
Voce e o agente responsavel por transformar metadados tecnicos em um dicionario
de dados semantico. Sua saida deve explicar tabelas, colunas e relacionamentos
de forma clara para humanos, e nao apenas listar metadados crus.
""".strip()


class BuildDictionaryService:
    """Converte introspeccao tecnica em uma representacao semantica."""

    def build_dictionary(
        self,
        user_request: str,
        interpretation: str,
        tables: list[dict[str, object]],
    ) -> dict[str, object]:
        return {
            "request": user_request,
            "interpretation": interpretation,
            "dictionary": [self._build_table_entry(table) for table in tables],
        }

    def handle_a2a_message(self, message: A2AEnvelope) -> Any:
        if message.action == "build_dictionary":
            return self.build_dictionary(
                user_request=message.payload["user_request"],
                interpretation=message.payload["interpretation"],
                tables=message.payload["tables"],
            )
        raise ValueError(
            f"Acao A2A desconhecida para BuildDictionary: {message.action}"
        )

    def _build_table_entry(self, table: dict[str, object]) -> dict[str, object]:
        table_name = str(table["table_name"])
        raw_columns = table.get("columns", [])
        raw_relationships = table.get("relationships", [])
        columns = (
            cast(list[dict[str, object]], raw_columns)
            if isinstance(raw_columns, list)
            else []
        )
        relationships = (
            cast(list[dict[str, object]], raw_relationships)
            if isinstance(raw_relationships, list)
            else []
        )

        return {
            "table_name": table_name,
            "technical_description": table.get("description", ""),
            "business_description": self._describe_table(table_name, relationships),
            "table_summary": self._summarize_table(table_name, columns, relationships),
            "metadata_query": table.get("metadata_query", ""),
            "columns": [
                self._build_column_entry(table_name, column, relationships)
                for column in columns
            ],
            "relationships": [
                self._build_relationship_entry(table_name, relationship)
                for relationship in relationships
            ],
        }

    def _build_column_entry(
        self,
        table_name: str,
        column: dict[str, object],
        relationships: list[dict[str, object]],
    ) -> dict[str, object]:
        column_name = str(column["name"])
        role = self._infer_column_role(column_name, relationships)
        description = str(column.get("description") or "")

        if not description:
            description = self._describe_column(table_name, column_name, role)

        return {
            "name": column_name,
            "data_type": column.get("type", ""),
            "nullable": column.get("nullable", True),
            "role": role,
            "description": description,
        }

    def _build_relationship_entry(
        self,
        table_name: str,
        relationship: dict[str, object],
    ) -> dict[str, object]:
        target_table = str(relationship["target_table"])
        source_column = str(relationship["source_column"])
        target_column = str(relationship["target_column"])
        relationship_type = str(relationship.get("relationship_type", "many-to-one"))

        return {
            "target_table": target_table,
            "source_column": source_column,
            "target_column": target_column,
            "relationship_type": relationship_type,
            "description": (
                f"Cada registro de {table_name} se relaciona com {target_table} "
                f"por meio de {source_column} -> {target_column}."
            ),
        }

    def _infer_column_role(
        self,
        column_name: str,
        relationships: list[dict[str, object]],
    ) -> str:
        normalized = column_name.lower()
        if normalized == "id" or normalized.endswith("id") and "_" not in normalized:
            return "primary_key"
        if any(rel["source_column"] == column_name for rel in relationships):
            return "foreign_key"
        return "attribute"

    def _describe_table(
        self,
        table_name: str,
        relationships: list[dict[str, object]],
    ) -> str:
        if relationships:
            return (
                f"Armazena registros de {table_name} e conecta essa entidade a outras "
                "partes do dominio por meio de relacionamentos mapeados."
            )
        return f"Armazena os dados principais da entidade {table_name}."

    def _summarize_table(
        self,
        table_name: str,
        columns: list[dict[str, object]],
        relationships: list[dict[str, object]],
    ) -> str:
        return (
            f"A tabela {table_name} possui {len(columns)} colunas e "
            f"{len(relationships)} relacionamentos identificados."
        )

    def _describe_column(self, table_name: str, column_name: str, role: str) -> str:
        if role == "primary_key":
            return f"Identificador principal usado para distinguir registros de {table_name}."
        if role == "foreign_key":
            return (
                f"Chave de referencia usada para conectar {table_name} a outra tabela."
            )
        return f"Atributo informacional da tabela {table_name}."


build_dictionary_agent = Agent(
    name="BuildDictionary",
    model="gemini-2.0-flash",
    instruction=BUILD_DICTIONARY_INSTRUCTIONS,
)
