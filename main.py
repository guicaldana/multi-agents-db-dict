from __future__ import annotations

import json
import os
from pathlib import Path

from agents.a2a_integration import LocalA2AClient
from agents.build_dictionary import BuildDictionaryService
from agents.discover_schema import DiscoverSchemaService
from agents.executer import executer_service
from agents.map_relationships import MapRelationshipsService
from agents.nl2sql import NL2SQLService
from agents.orchestrator import DataDictionaryOrchestrator


def build_output_filename(result: dict[str, object]) -> str:
    database_label = str(result.get("database_label", "database_dictionary"))
    safe_label = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in database_label
    )
    return f"{safe_label}_data_dictionary.json"


def build_trace_filename(result: dict[str, object]) -> str:
    database_label = str(result.get("database_label", "database_dictionary"))
    safe_label = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in database_label
    )
    return f"{safe_label}_execution_trace.json"


def build_path_filename(result: dict[str, object]) -> str:
    database_label = str(result.get("database_label", "database_dictionary"))
    safe_label = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in database_label
    )
    return f"{safe_label}_execution_path.json"


def build_dictionary_output(result: dict[str, object]) -> dict[str, object]:
    return {
        "database_label": result.get("database_label"),
        "database_mode": result.get("database_mode"),
        "request": result.get("request"),
        "interpretation": result.get("interpretation"),
        "data_dictionary": result.get("data_dictionary", []),
    }


def print_execution_path(result: dict[str, object]) -> None:
    execution_path = result.get("execution_path", [])
    if not isinstance(execution_path, list) or not execution_path:
        return

    print("\nTrilha de execucao:")
    for step in execution_path:
        print(f"- {step}")


def main() -> None:
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

    discover_schema_client = LocalA2AClient(
        target_name="DiscoverSchema",
        handler=discover_schema_service.handle_a2a_message,
        sender_name="Orchestrator",
    )
    map_relationships_client = LocalA2AClient(
        target_name="MapRelationships",
        handler=map_relationships_service.handle_a2a_message,
        sender_name="Orchestrator",
    )
    nl2sql_client = LocalA2AClient(
        target_name="NL2SQL",
        handler=nl2sql_service.handle_a2a_message,
        sender_name="Orchestrator",
    )
    build_dictionary_client = LocalA2AClient(
        target_name="BuildDictionary",
        handler=build_dictionary_service.handle_a2a_message,
        sender_name="Orchestrator",
    )

    orchestrator = DataDictionaryOrchestrator(
        discover_schema_client=discover_schema_client,
        map_relationships_client=map_relationships_client,
        nl2sql_client=nl2sql_client,
        build_dictionary_client=build_dictionary_client,
        executer_client=LocalA2AClient(
            target_name="Executer",
            handler=executer_service.handle_a2a_message,
            sender_name="Orchestrator",
        ),
    )
    result = orchestrator.generate_data_dictionary(
        "Gerar um dicionario de dados com foco em colunas e relacionamentos."
    )
    if os.getenv("DATABASE_URL"):
        result["database_url_configured"] = True

    dictionary_output = build_dictionary_output(result)
    output_path = Path(build_output_filename(result))
    trace_path = Path(build_trace_filename(result))
    execution_path_file = Path(build_path_filename(result))

    output_path.write_text(
        json.dumps(dictionary_output, indent=2, ensure_ascii=True) + "\n",
        encoding="ascii",
    )
    trace_path.write_text(
        json.dumps(result.get("execution_trace", []), indent=2, ensure_ascii=True)
        + "\n",
        encoding="ascii",
    )
    execution_path_file.write_text(
        json.dumps(result.get("execution_path", []), indent=2, ensure_ascii=True)
        + "\n",
        encoding="ascii",
    )

    print(json.dumps(dictionary_output, indent=2, ensure_ascii=True))
    print_execution_path(result)
    print(f"\nDicionario salvo em: {output_path}")
    print(f"Trace salvo em: {trace_path}")
    print(f"Trilha legivel salva em: {execution_path_file}")


if __name__ == "__main__":
    main()
