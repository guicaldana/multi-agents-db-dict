from __future__ import annotations

import json
import os
from pathlib import Path

from agents.build_dictionary import BuildDictionaryService
from agents.discover_schema import DiscoverSchemaService
from agents.executer import executer_service
from agents.map_relationships import MapRelationshipsService
from agents.nl2sql import NL2SQLService
from agents.orchestrator import DataDictionaryOrchestrator
from agents.runtime import A2AClient


def build_output_filename(result: dict[str, object]) -> str:
    database_label = str(result.get("database_label", "database_dictionary"))
    safe_label = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in database_label
    )
    return f"{safe_label}_data_dictionary.json"


def main() -> None:
    executer_client = A2AClient(
        target_name="Executer",
        handler=executer_service.handle_a2a_message,
        sender_name="Main",
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
    result = orchestrator.generate_data_dictionary(
        "Gerar um dicionario de dados com foco em colunas e relacionamentos."
    )
    if os.getenv("DATABASE_URL"):
        result["database_url_configured"] = True

    output_path = Path(build_output_filename(result))
    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="ascii"
    )

    print(json.dumps(result, indent=2, ensure_ascii=True))
    print(f"\nArquivo salvo em: {output_path}")


if __name__ == "__main__":
    main()
