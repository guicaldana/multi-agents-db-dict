"""Integracao local com os tipos oficiais da biblioteca A2A.

O transporte continua local para manter o projeto simples, mas as mensagens e o
modelo de execucao passam a usar o SDK A2A real em vez do cliente caseiro.
"""

from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from typing import Any, Callable, Protocol

HAS_A2A = importlib.util.find_spec("a2a") is not None

if HAS_A2A:
    from a2a.client import create_text_message_object  # type: ignore[import-not-found]
    from a2a.server.agent_execution import (  # type: ignore[import-not-found]
        AgentExecutor,
        RequestContext,
    )
    from a2a.server.events import EventQueue  # type: ignore[import-not-found]
    from a2a.types import SendMessageRequest  # type: ignore[import-not-found]
    from a2a.utils import (  # type: ignore[import-not-found]
        get_message_text,
        new_agent_text_message,
    )
else:

    class AgentExecutor:
        def execute(self, context: Any, event_queue: Any) -> None:
            raise NotImplementedError

        def cancel(self, context: Any, event_queue: Any) -> None:
            raise NotImplementedError

    @dataclass
    class RequestContext:
        request: Any = None

    class EventQueue:
        def __init__(self) -> None:
            self._events: list[Any] = []

        def enqueue_event(self, event: Any) -> None:
            self._events.append(event)

        def dequeue_event(self) -> Any:
            return self._events.pop(0) if self._events else None

        def close(self, immediate: bool = False) -> None:
            return None

    @dataclass
    class _SimpleMessage:
        content: str

    @dataclass
    class _SimpleParams:
        message: _SimpleMessage

    @dataclass
    class SendMessageRequest:
        id: str
        params: Any

    def create_text_message_object(content: str) -> _SimpleMessage:
        return _SimpleMessage(content=content)

    def get_message_text(message: _SimpleMessage) -> str:
        return message.content

    def new_agent_text_message(text: str) -> _SimpleMessage:
        return _SimpleMessage(content=text)


@dataclass
class A2AEnvelope:
    action: str
    payload: dict[str, Any]
    sender: str


class A2AExecutorProtocol(Protocol):
    def execute(self, context: RequestContext, event_queue: EventQueue) -> None: ...

    def cancel(self, context: RequestContext, event_queue: EventQueue) -> None: ...


class LocalA2AExecutor:
    def __init__(self, handler: Callable[[A2AEnvelope], Any]) -> None:
        self.handler = handler

    def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if context.request is None:
            raise ValueError("RequestContext sem request para execucao A2A.")

        raw_text = get_message_text(context.request.message)
        content = json.loads(raw_text)
        envelope = A2AEnvelope(
            action=content["action"],
            payload=content.get("payload", {}),
            sender=content.get("sender", "anonymous"),
        )
        result = self.handler(envelope)
        event_queue.enqueue_event(
            new_agent_text_message(json.dumps(result, ensure_ascii=True))
        )
        event_queue.close()

    def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        event_queue.close(immediate=True)


class LocalA2AClient:
    def __init__(
        self,
        target_name: str,
        handler: Callable[[A2AEnvelope], Any],
        sender_name: str,
    ) -> None:
        self.target_name = target_name
        self.sender_name = sender_name
        self.executor: A2AExecutorProtocol = LocalA2AExecutor(handler)

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

        request = SendMessageRequest(
            id=f"{self.sender_name}-{self.target_name}-{action}",
            params={
                "message": create_text_message_object(
                    content=json.dumps(
                        {
                            "action": action,
                            "payload": payload,
                            "sender": self.sender_name,
                        },
                        ensure_ascii=True,
                    )
                )
            },
        )
        request_payload = request.params
        if isinstance(request_payload, dict):
            request_payload = _SimpleParams(message=request_payload["message"])
        context = RequestContext(request=request_payload)
        event_queue = EventQueue()
        self.executor.execute(context, event_queue)
        response = event_queue.dequeue_event()
        if response is None:
            raise RuntimeError("Nenhuma resposta retornou da chamada A2A.")
        return json.loads(get_message_text(response))
