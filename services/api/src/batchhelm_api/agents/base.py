"""Core agent abstractions shared by every BatchHelm specialist agent."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from batchhelm_api.config import Settings
from batchhelm_api.memory_repository import MemoryRepository
from batchhelm_api.models import (
    AgentEventType,
    AgentRunEvent,
    OutputSource,
    RecallIncidentInput,
)
from batchhelm_api.qwen import QwenGateway

EmitCallback = Callable[[AgentRunEvent], Awaitable[None]]
PersistCallback = Callable[[AgentRunEvent], Awaitable[None]]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventRecorder:
    """Collects run events and (optionally) fans them out live."""

    def __init__(
        self,
        run_id: str,
        emit: EmitCallback | None = None,
        *,
        persist: PersistCallback | None = None,
        initial_sequence: int = 0,
    ) -> None:
        self.run_id = run_id
        self.events: list[AgentRunEvent] = []
        self._emit = emit
        self._persist = persist
        self._sequence = initial_sequence

    async def record(
        self,
        *,
        agent: str,
        type: AgentEventType,
        message: str,
        source: OutputSource = OutputSource.deterministic,
        data: dict[str, Any] | None = None,
    ) -> AgentRunEvent:
        self._sequence += 1
        event = AgentRunEvent(
            id=uuid4().hex,
            run_id=self.run_id,
            sequence=self._sequence,
            agent=agent,
            type=type,
            message=message,
            at=utcnow(),
            source=source,
            data=data,
        )
        if self._persist is not None:
            await self._persist(event)
        self.events.append(event)
        if self._emit is not None:
            await self._emit(event)
        return event


@dataclass
class AgentContext:
    """Everything an agent needs to do its job and share results."""

    run_id: str
    incident: RecallIncidentInput
    gateway: QwenGateway
    memory: MemoryRepository
    settings: Settings
    recorder: EventRecorder
    blackboard: dict[str, Any] = field(default_factory=dict)

    async def reason(
        self,
        agent: str,
        message: str,
        *,
        source: OutputSource = OutputSource.deterministic,
        data: dict[str, Any] | None = None,
    ) -> None:
        await self.recorder.record(
            agent=agent,
            type=AgentEventType.reasoning,
            message=message,
            source=source,
            data=data,
        )


@dataclass
class AgentOutput:
    """A specialist agent's report after running.

    The agent writes shared state directly to ``ctx.blackboard``; this object
    describes the run for the timeline, checkpoint, and final result.
    """

    summary: str
    reasoning: str = ""
    confidence: int = 0
    source: OutputSource = OutputSource.deterministic
    used_fallback: bool = True
    provider: str = "qwen"
    model: str = ""


class Agent:
    """Base class for all specialist agents.

    Subclasses set ``name``, ``role`` and ``depends_on`` and implement
    :meth:`run`. The orchestrator wraps every run with timing, retries,
    checkpoints, and start/complete/fail events.
    """

    name: str = "agent"
    role: str = ""
    depends_on: tuple[str, ...] = ()

    async def run(self, ctx: AgentContext) -> AgentOutput:  # pragma: no cover
        raise NotImplementedError
