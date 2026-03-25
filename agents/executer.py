"""Agente responsavel pelo acesso fisico aos bancos via MCP.

Este modulo concentra a comunicacao com PostgreSQL e expoe tools de introspeccao
que podem ser consumidas pelos demais agentes. A ideia e que o restante do
sistema pense em A2A, enquanto este componente se responsabiliza pelo MCP.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psycopg2

from agents.a2a_integration import A2AEnvelope
from agents.runtime import FastMCP


# Catalogo local usado como fallback para desenvolvimento e testes offline.
MOCK_DATABASE: dict[str, dict[str, Any]] = {
    "customers": {
        "description": "Cadastro principal de clientes.",
        "columns": [
            {
                "name": "id",
                "type": "integer",
                "nullable": False,
                "description": "Identificador unico do cliente.",
            },
            {
                "name": "name",
                "type": "varchar",
                "nullable": False,
                "description": "Nome completo do cliente.",
            },
            {
                "name": "email",
                "type": "varchar",
                "nullable": False,
                "description": "Email principal para contato.",
            },
        ],
        "relationships": [],
    },
    "orders": {
        "description": "Pedidos realizados pelos clientes.",
        "columns": [
            {
                "name": "id",
                "type": "integer",
                "nullable": False,
                "description": "Identificador unico do pedido.",
            },
            {
                "name": "customer_id",
                "type": "integer",
                "nullable": False,
                "description": "Referencia ao cliente dono do pedido.",
            },
            {
                "name": "status",
                "type": "varchar",
                "nullable": False,
                "description": "Estado atual do pedido.",
            },
        ],
        "relationships": [
            {
                "source_column": "customer_id",
                "target_table": "customers",
                "target_column": "id",
                "type": "many-to-one",
            }
        ],
    },
}


class DatabaseGateway:
    """Encapsula o acesso ao banco e aplica fallback quando nao ha conexao real.

    O DSN pode ser fornecido via construtor ou pela variavel `DATABASE_URL`.
    Se nenhum DSN for informado, o gateway usa o catalogo mockado para manter o
    projeto funcional durante o desenvolvimento.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.getenv("DATABASE_URL")

    def using_mock(self) -> bool:
        return not self.dsn

    def using_sqlite(self) -> bool:
        return bool(self.dsn) and self.dsn.startswith("sqlite:///")

    def using_postgres(self) -> bool:
        return bool(self.dsn) and not self.using_sqlite()

    def database_label(self) -> str:
        if self.using_mock():
            return "mock_database"
        if self.using_sqlite():
            return Path(self._sqlite_path()).stem or "sqlite_database"

        parsed = urlparse(self.dsn or "")
        if parsed.path:
            return Path(parsed.path.lstrip("/")).stem or "postgres_database"
        return "postgres_database"

    def list_tables(self) -> list[str]:
        if self.using_mock():
            return sorted(MOCK_DATABASE)

        if self.using_sqlite():
            query = """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name;
            """
            return [row[0] for row in self._fetch_all_sqlite(query)]

        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """
        return [row[0] for row in self._fetch_all(query)]

    def list_columns(self, table_name: str) -> list[dict[str, Any]]:
        if self.using_mock():
            table = self._get_mock_table(table_name)
            return table["columns"]

        if self.using_sqlite():
            rows = self._fetch_all_sqlite(
                f"PRAGMA table_info({self._quote_identifier(table_name)});"
            )
            return [
                {
                    "name": row[1],
                    "type": row[2] or "TEXT",
                    "nullable": row[3] == 0,
                    "description": "",
                }
                for row in rows
            ]

        query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                COALESCE(col_description(format('%s.%s', table_schema, table_name)::regclass::oid, ordinal_position), '')
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """
        rows = self._fetch_all(query, (table_name,))
        return [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "description": row[3],
            }
            for row in rows
        ]

    def describe_table(self, table_name: str) -> dict[str, Any]:
        if self.using_mock():
            return self._get_mock_table(table_name)

        if self.using_sqlite():
            return {
                "description": "",
                "columns": self.list_columns(table_name),
                "relationships": [
                    relation
                    for relation in self.list_relationships()
                    if relation["source_table"] == table_name
                ],
            }

        return {
            "description": self._load_table_comment(table_name),
            "columns": self.list_columns(table_name),
            "relationships": [
                relation
                for relation in self.list_relationships()
                if relation["source_table"] == table_name
            ],
        }

    def list_relationships(self) -> list[dict[str, str]]:
        if self.using_mock():
            relationships: list[dict[str, str]] = []
            for table_name, table_data in MOCK_DATABASE.items():
                for relationship in table_data.get("relationships", []):
                    relationships.append(
                        {
                            "source_table": table_name,
                            "source_column": relationship["source_column"],
                            "target_table": relationship["target_table"],
                            "target_column": relationship["target_column"],
                            "relationship_type": relationship.get(
                                "type", "many-to-one"
                            ),
                        }
                    )
            return relationships

        if self.using_sqlite():
            relationships: list[dict[str, str]] = []
            for table_name in self.list_tables():
                pragma_rows = self._fetch_all_sqlite(
                    f"PRAGMA foreign_key_list({self._quote_identifier(table_name)});"
                )
                for row in pragma_rows:
                    relationships.append(
                        {
                            "source_table": table_name,
                            "source_column": row[3],
                            "target_table": row[2],
                            "target_column": row[4],
                            "relationship_type": "many-to-one",
                        }
                    )
            return relationships

        query = """
            SELECT
                tc.table_name AS source_table,
                kcu.column_name AS source_column,
                ccu.table_name AS target_table,
                ccu.column_name AS target_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = 'public'
            ORDER BY tc.table_name, kcu.column_name;
        """
        rows = self._fetch_all(query)
        return [
            {
                "source_table": row[0],
                "source_column": row[1],
                "target_table": row[2],
                "target_column": row[3],
                "relationship_type": "many-to-one",
            }
            for row in rows
        ]

    def _load_table_comment(self, table_name: str) -> str:
        query = """
            SELECT COALESCE(obj_description(format('public.%s', %s)::regclass::oid, 'pg_class'), '')
        """
        rows = self._fetch_all(query, (table_name, table_name))
        return rows[0][0] if rows else ""

    def _fetch_all(
        self, query: str, params: tuple[Any, ...] = ()
    ) -> list[tuple[Any, ...]]:
        with closing(psycopg2.connect(self.dsn)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()

    def _fetch_all_sqlite(self, query: str) -> list[tuple[Any, ...]]:
        with closing(sqlite3.connect(self._sqlite_path())) as connection:
            cursor = connection.cursor()
            cursor.execute(query)
            return cursor.fetchall()

    def _sqlite_path(self) -> str:
        if not self.dsn:
            raise ValueError("DSN SQLite nao configurado.")
        return str(Path(self.dsn.removeprefix("sqlite:///"))).strip()

    def _quote_identifier(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _get_mock_table(self, table_name: str) -> dict[str, Any]:
        table = MOCK_DATABASE.get(table_name)
        if table is None:
            raise KeyError(f"Tabela '{table_name}' nao encontrada.")
        return table


class ExecuterService:
    """Faixada de servico usada pelos agentes A2A para falar com o MCP.

    Embora neste momento a chamada ainda aconteca no mesmo processo, esta classe
    deixa explicito que o DiscoverSchema nao deve introspectar o banco por conta
    propria. Toda leitura fisica passa pelo Executer.
    """

    def __init__(self, gateway_instance: DatabaseGateway | None = None) -> None:
        self.gateway = gateway_instance or gateway

    def database_mode(self) -> str:
        if self.gateway.using_mock():
            return "mock"
        if self.gateway.using_sqlite():
            return "sqlite"
        return "postgres"

    def database_label(self) -> str:
        return self.gateway.database_label()

    def list_tables(self) -> list[str]:
        return self.gateway.list_tables()

    def list_columns(self, table_name: str) -> list[dict[str, Any]]:
        return self.gateway.list_columns(table_name)

    def describe_table(self, table_name: str) -> dict[str, Any]:
        return self.gateway.describe_table(table_name)

    def list_relationships(self) -> list[dict[str, str]]:
        return self.gateway.list_relationships()

    def handle_a2a_message(self, message: A2AEnvelope) -> Any:
        """Recebe chamadas A2A e as traduz para operacoes MCP do Executer."""
        if message.action == "database_mode":
            return self.database_mode()
        if message.action == "database_label":
            return self.database_label()
        if message.action == "list_tables":
            return self.list_tables()
        if message.action == "list_columns":
            return self.list_columns(message.payload["table_name"])
        if message.action == "describe_table":
            return self.describe_table(message.payload["table_name"])
        if message.action == "list_relationships":
            return self.list_relationships()
        raise ValueError(f"Acao A2A desconhecida para Executer: {message.action}")


mcp = FastMCP("db-dictionary-mcp")
gateway = DatabaseGateway()
executer_service = ExecuterService(gateway)


@mcp.tool
def database_mode() -> str:
    """Indica se o executer esta usando banco remoto ou catalogo mockado."""
    return executer_service.database_mode()


@mcp.tool
def database_label() -> str:
    """Retorna um nome curto e seguro para o banco atual."""
    return executer_service.database_label()


@mcp.tool
def list_tables() -> list[str]:
    """Lista as tabelas disponiveis no banco conectado ou no mock local."""
    return executer_service.list_tables()


@mcp.tool
def list_columns(table_name: str) -> list[dict[str, Any]]:
    """Lista colunas de uma tabela com tipo, nulabilidade e descricao."""
    return executer_service.list_columns(table_name)


@mcp.tool
def describe_table(table_name: str) -> dict[str, Any]:
    """Retorna o pacote completo de metadados para uma tabela."""
    return executer_service.describe_table(table_name)


@mcp.tool
def list_relationships() -> list[dict[str, str]]:
    """Retorna todas as relacoes detectadas no schema atual."""
    return executer_service.list_relationships()


if __name__ == "__main__":
    mcp.run()
