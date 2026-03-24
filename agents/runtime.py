"""Adaptadores leves para ADK, A2A e MCP.

Os imports reais continuam sendo priorizados. Quando o ambiente ainda nao tem as
bibliotecas instaladas, este modulo oferece fallbacks pequenos para permitir que
o projeto rode em modo local e que a analise estatica do editor nao quebre.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


try:
    from google.adk.agents import Agent as ADKAgent  # type: ignore[import-not-found]
except ImportError:

    @dataclass
    class ADKAgent:
        name: str
        model: str
        instruction: str
        tools: list[Callable[..., Any]] = field(default_factory=list)


try:
    from fastmcp import FastMCP as MCPRuntime  # type: ignore[import-not-found]
except ImportError:

    class MCPRuntime:
        def __init__(self, name: str) -> None:
            self.name = name
            self.registered_tools: dict[str, Callable[..., Any]] = {}

        def tool(self, func: Callable[..., Any]) -> Callable[..., Any]:
            self.registered_tools[func.__name__] = func
            return func

        def run(self) -> None:
            tools = ", ".join(sorted(self.registered_tools)) or "nenhuma"
            print(f"MCP '{self.name}' em modo fallback. Tools registradas: {tools}.")


Agent = ADKAgent
FastMCP = MCPRuntime


@dataclass
class A2AMessage:
    """Mensagem simples para simular troca estruturada entre agentes."""

    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    sender: str = "anonymous"


@dataclass
class A2ATraceEntry:
    """Representa um passo na trilha de chamadas entre agentes."""

    sender: str
    target: str
    action: str


class A2AClient:
    """Cliente A2A minimo para chamadas locais entre agentes.

    Enquanto o transporte real nao e plugado, esta classe simula uma chamada A2A
    enviando uma mensagem estruturada para um servico alvo.
    """

    def __init__(
        self,
        target_name: str,
        handler: Callable[[A2AMessage], Any],
        sender_name: str = "anonymous",
    ) -> None:
        self.target_name = target_name
        self.handler = handler
        self.sender_name = sender_name

    def call(self, action: str, **payload: Any) -> Any:
        trace = payload.setdefault("trace", [])
        if isinstance(trace, list):
            trace.append(
                {
                    "sender": self.sender_name,
                    "target": self.target_name,
                    "action": action,
                }
            )
        message = A2AMessage(action=action, payload=payload, sender=self.sender_name)
        return self.handler(message)
