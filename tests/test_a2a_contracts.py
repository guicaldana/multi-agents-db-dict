from __future__ import annotations

import sqlite3
from pathlib import Path

from agents.a2a_integration import A2AEnvelope, LocalA2AClient
from agents.build_dictionary import BuildDictionaryService
from agents.discover_schema import DiscoverSchemaService
from agents.executer import DatabaseGateway, ExecuterService, executer_service
from agents.map_relationships import MapRelationshipsService
from agents.nl2sql import NL2SQLService
from agents.orchestrator import DataDictionaryOrchestrator


def build_agent_network() -> tuple[
    DataDictionaryOrchestrator,
    DiscoverSchemaService,
    MapRelationshipsService,
    NL2SQLService,
]:
    discover_schema_service = DiscoverSchemaService(
        LocalA2AClient(
            target_name="Executer",
            handler=executer_service.handle_a2a_message,
            sender_name="DiscoverSchema",
        )
    )
    map_relationships_service = MapRelationshipsService(
        LocalA2AClient(
            target_name="Executer",
            handler=executer_service.handle_a2a_message,
            sender_name="MapRelationships",
        )
    )
    nl2sql_service = NL2SQLService()
    build_dictionary_service = BuildDictionaryService()

    orchestrator = DataDictionaryOrchestrator(
        discover_schema_client=LocalA2AClient(
            target_name="DiscoverSchema",
            handler=discover_schema_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        map_relationships_client=LocalA2AClient(
            target_name="MapRelationships",
            handler=map_relationships_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        nl2sql_client=LocalA2AClient(
            target_name="NL2SQL",
            handler=nl2sql_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        build_dictionary_client=LocalA2AClient(
            target_name="BuildDictionary",
            handler=build_dictionary_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
        executer_client=LocalA2AClient(
            target_name="Executer",
            handler=executer_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
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
        A2AEnvelope(action="describe_schema", payload={}, sender="TestHarness")
    )

    assert schema
    first_table_name = next(iter(schema))
    assert any(column["name"] for column in schema[first_table_name])


def test_map_relationships_uses_a2a_contract() -> None:
    _, _, map_relationships_service, _ = build_agent_network()

    relationship_map = map_relationships_service.handle_a2a_message(
        A2AEnvelope(action="map_relationships", payload={}, sender="TestHarness")
    )

    assert relationship_map
    first_source_table = next(iter(relationship_map))
    assert relationship_map[first_source_table][0]["target_table"]


def test_orchestrator_is_consultable_via_a2a() -> None:
    orchestrator, _, _, _ = build_agent_network()

    result = orchestrator.handle_a2a_message(
        A2AEnvelope(
            action="generate_data_dictionary",
            payload={
                "user_request": "Gerar um dicionario de dados com relacionamentos"
            },
            sender="TestHarness",
        )
    )

    assert result["database_mode"] in {"mock", "postgres", "sqlite"}
    assert result["database_label"]
    assert result["execution_trace"]
    assert result["execution_path"]
    assert result["tables"]
    assert result["data_dictionary"]
    dictionary_only = {
        "database_label": result["database_label"],
        "database_mode": result["database_mode"],
        "request": result["request"],
        "interpretation": result["interpretation"],
        "data_dictionary": result["data_dictionary"],
    }
    assert all("business_description" in entry for entry in result["data_dictionary"])
    assert "execution_trace" not in dictionary_only
    assert "execution_path" not in dictionary_only
    assert any(
        step["target"] == "BuildDictionary" for step in result["execution_trace"]
    )
    assert any(
        step["sender"] == "Orchestrator" and step["target"] == "DiscoverSchema"
        for step in result["execution_trace"]
    )
    assert any(
        step["sender"] in {"DiscoverSchema", "MapRelationships", "Orchestrator"}
        and step["target"] == "Executer"
        for step in result["execution_trace"]
    )
    assert any(
        "Orchestrator chamou DiscoverSchema" in step
        for step in result["execution_path"]
    )


def test_nl2sql_a2a_contract() -> None:
    _, _, _, nl2sql_service = build_agent_network()

    explanation = nl2sql_service.handle_a2a_message(
        A2AEnvelope(
            action="explain_request",
            payload={"user_request": "Liste colunas e relacionamentos"},
            sender="TestHarness",
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
