from __future__ import annotations

import sqlite3
from pathlib import Path

from agents.build_dictionary import BuildDictionaryService
from agents.discover_schema import DiscoverSchemaService
from agents.executer import DatabaseGateway, ExecuterService, executer_service
from agents.map_relationships import MapRelationshipsService
from agents.nl2sql import NL2SQLService
from agents.orchestrator import DataDictionaryOrchestrator
from agents.runtime import A2AClient, A2AMessage


def build_agent_network() -> tuple[
    DataDictionaryOrchestrator,
    DiscoverSchemaService,
    MapRelationshipsService,
    NL2SQLService,
]:
    executer_client = A2AClient(
        target_name="Executer",
        handler=executer_service.handle_a2a_message,
        sender_name="TestHarness",
    )
    discover_schema_service = DiscoverSchemaService(executer_client)
    map_relationships_service = MapRelationshipsService(executer_client)
    nl2sql_service = NL2SQLService()
    build_dictionary_service = BuildDictionaryService()

    orchestrator = DataDictionaryOrchestrator(
        discover_schema_client=A2AClient(
            target_name="DiscoverSchema",
            handler=discover_schema_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        map_relationships_client=A2AClient(
            target_name="MapRelationships",
            handler=map_relationships_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        nl2sql_client=A2AClient(
            target_name="NL2SQL",
            handler=nl2sql_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        build_dictionary_client=A2AClient(
            target_name="BuildDictionary",
            handler=build_dictionary_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        executer_client=executer_client,
    )
    return (
        orchestrator,
        discover_schema_service,
        map_relationships_service,
        nl2sql_service,
    )


def test_discover_schema_uses_a2a_contract() -> None:
    _, discover_schema_service, _, _ = build_agent_network()

    schema = discover_schema_service.handle_a2a_message(
        A2AMessage(action="describe_schema")
    )

    assert "customers" in schema
    assert any(column["name"] == "id" for column in schema["customers"])


def test_map_relationships_uses_a2a_contract() -> None:
    _, _, map_relationships_service, _ = build_agent_network()

    relationship_map = map_relationships_service.handle_a2a_message(
        A2AMessage(action="map_relationships")
    )

    assert "orders" in relationship_map
    assert relationship_map["orders"][0]["target_table"] == "customers"


def test_orchestrator_is_consultable_via_a2a() -> None:
    orchestrator, _, _, _ = build_agent_network()

    result = orchestrator.handle_a2a_message(
        A2AMessage(
            action="generate_data_dictionary",
            payload={
                "user_request": "Gerar um dicionario de dados com relacionamentos"
            },
        )
    )

    assert result["database_mode"] in {"mock", "postgres", "sqlite"}
    assert result["database_label"]
    assert result["execution_trace"]
    assert any(table["table_name"] == "orders" for table in result["tables"])
    assert any(entry["table_name"] == "orders" for entry in result["data_dictionary"])
    assert all("business_description" in entry for entry in result["data_dictionary"])
    assert any(
        step["target"] == "BuildDictionary" for step in result["execution_trace"]
    )


def test_nl2sql_a2a_contract() -> None:
    _, _, _, nl2sql_service = build_agent_network()

    explanation = nl2sql_service.handle_a2a_message(
        A2AMessage(
            action="explain_request",
            payload={"user_request": "Liste colunas e relacionamentos"},
        )
    )

    assert isinstance(explanation, str)
    assert explanation


def test_sqlite_chinook_style_introspection(tmp_path: Path) -> None:
    database_path = tmp_path / "chinook-mini.db"
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute(
        "CREATE TABLE Artist (ArtistId INTEGER PRIMARY KEY, Name TEXT NOT NULL);"
    )
    connection.execute(
        "CREATE TABLE Album (AlbumId INTEGER PRIMARY KEY, Title TEXT NOT NULL, ArtistId INTEGER NOT NULL, FOREIGN KEY (ArtistId) REFERENCES Artist(ArtistId));"
    )
    connection.commit()
    connection.close()

    gateway = DatabaseGateway(f"sqlite:///{database_path}")
    service = ExecuterService(gateway)

    assert service.database_mode() == "sqlite"
    assert service.list_tables() == ["Album", "Artist"]
    assert any(column["name"] == "ArtistId" for column in service.list_columns("Album"))
    assert service.list_relationships()[0]["target_table"] == "Artist"
