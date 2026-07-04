from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from uuid import uuid4

from batchhelm_api.agents import Orchestrator
from batchhelm_api.agents.base import utcnow
from batchhelm_api.event_stream import (
    sse_error,
    sse_heartbeat,
    sse_pack,
    sse_result,
)
from batchhelm_api.intake_models import ResolvedRunInput
from batchhelm_api.models import (
    AgentRunEvent,
    AgentRunStatus,
    OrchestrationResult,
    OrchestrationRunAccepted,
    OrchestrationRunView,
)
from batchhelm_api.orchestration_repository import OrchestrationRepository

OrchestratorFactory = Callable[[], Orchestrator]
RunInputResolver = Callable[[str], ResolvedRunInput | None]


class OrchestrationExecutionFailed(RuntimeError):
    pass


class OrchestrationService:
    def __init__(
        self,
        *,
        repository: OrchestrationRepository,
        orchestrator_factory: OrchestratorFactory,
    ) -> None:
        self.repository = repository
        self._orchestrator_factory = orchestrator_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._conditions: dict[str, asyncio.Condition] = {}
        self._lock = asyncio.Lock()
        self._worker_starts: dict[str, int] = {}

    async def start(
        self,
        run_input: ResolvedRunInput,
        *,
        request_id: str,
    ) -> OrchestrationRunAccepted:
        orchestrator = self._orchestrator_factory()
        run = self.repository.create_run(
            run_id=uuid4().hex,
            incident_id=run_input.incident.id,
            idempotency_key=request_id,
            provider_mode=orchestrator.gateway.status().mode,
        )
        await self._ensure_worker(run.id, run_input)
        return OrchestrationRunAccepted(
            run_id=run.id,
            incident_id=run.incident_id,
            status=run.status,
            events_url=f"/api/orchestration/runs/{run.id}/events",
            result_url=f"/api/orchestration/runs/{run.id}",
        )

    def get(self, run_id: str) -> OrchestrationRunView:
        return self.repository.get_run(run_id).to_view()

    def worker_start_count(self, run_id: str) -> int:
        return self._worker_starts.get(run_id, 0)

    async def wait_for_result(self, run_id: str) -> OrchestrationResult:
        condition = self._condition(run_id)
        while True:
            async with condition:
                run = self.repository.get_run(run_id)
                if run.result is not None:
                    return run.result
                if run.status == AgentRunStatus.failed:
                    raise OrchestrationExecutionFailed(
                        run.error_message or "Orchestration run failed."
                    )
                try:
                    await asyncio.wait_for(condition.wait(), timeout=15.0)
                except TimeoutError:
                    continue

    async def stream(
        self,
        run_id: str,
        *,
        after: int = 0,
    ) -> AsyncIterator[str]:
        cursor = after
        condition = self._condition(run_id)
        while True:
            events = self.repository.list_events_after(run_id, cursor)
            for event in events:
                cursor = event.sequence
                yield sse_pack(event)

            run = self.repository.get_run(run_id)
            if run.result is not None:
                yield sse_result(run.result.model_dump_json())
                return
            if run.status == AgentRunStatus.failed:
                yield sse_error(
                    run.error_code or "orchestration_failed",
                    run.error_message or "Orchestration run failed.",
                )
                return

            send_heartbeat = False
            async with condition:
                if self.repository.latest_sequence(run_id) > cursor:
                    continue
                current = self.repository.get_run(run_id)
                if (
                    current.result is not None
                    or current.status == AgentRunStatus.failed
                ):
                    continue
                try:
                    await asyncio.wait_for(condition.wait(), timeout=15.0)
                except TimeoutError:
                    send_heartbeat = True
            if send_heartbeat:
                yield sse_heartbeat()

    async def recover(self, resolver: RunInputResolver) -> None:
        for run in self.repository.list_recoverable():
            run_input = resolver(run.incident_id)
            if run_input is None:
                self.repository.fail_run(
                    run.id,
                    code="incident_unavailable",
                    message="The incident for this run is unavailable.",
                )
                await self._notify(run.id)
                continue
            await self._ensure_worker(run.id, run_input)

    async def _ensure_worker(
        self,
        run_id: str,
        run_input: ResolvedRunInput,
    ) -> None:
        async with self._lock:
            run = self.repository.get_run(run_id)
            if run.result is not None or run.status == AgentRunStatus.failed:
                return
            existing = self._tasks.get(run_id)
            if existing is not None and not existing.done():
                return
            task = asyncio.create_task(self._execute(run_id, run_input))
            self._tasks[run_id] = task
            self._worker_starts[run_id] = self._worker_starts.get(run_id, 0) + 1
            task.add_done_callback(
                lambda completed, rid=run_id: self._remove_task(rid, completed)
            )

    async def _execute(
        self,
        run_id: str,
        run_input: ResolvedRunInput,
    ) -> None:
        try:
            orchestrator = self._orchestrator_factory()
            checkpoint = self.repository.load_checkpoint(run_id)
            started_at = checkpoint.started_at if checkpoint else utcnow()
            run = self.repository.claim_run(run_id, started_at)
            if run.result is not None or run.status == AgentRunStatus.completed:
                return
            initial_sequence = self.repository.latest_sequence(run_id)
            result = await orchestrator.run(
                run_input.incident,
                run_id=run_id,
                persist_event=self._persist_event,
                initial_sequence=initial_sequence,
                checkpoint_sink=lambda value: self.repository.save_checkpoint(
                    run_id, value
                ),
                recovery=checkpoint,
                shelf_image_bytes=run_input.shelf_image_bytes,
                shelf_image_media_type=run_input.shelf_image_media_type,
                shelf_upload=run_input.shelf_artifact,
            )
            complete_history = self.repository.list_events_after(run_id, 0)
            result = result.model_copy(update={"events": complete_history})
            self.repository.complete_run(run_id, result)
            await self._notify(run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            with suppress(Exception):
                self.repository.fail_run(
                    run_id,
                    code="orchestration_failed",
                    message="The orchestration run could not be completed.",
                )
            await self._notify(run_id)

    async def _persist_event(self, event: AgentRunEvent) -> None:
        self.repository.append_event(event)
        await self._notify(event.run_id)

    async def _notify(self, run_id: str) -> None:
        condition = self._condition(run_id)
        async with condition:
            condition.notify_all()

    def _condition(self, run_id: str) -> asyncio.Condition:
        return self._conditions.setdefault(run_id, asyncio.Condition())

    def _remove_task(
        self,
        run_id: str,
        completed: asyncio.Task[None],
    ) -> None:
        if self._tasks.get(run_id) is completed:
            self._tasks.pop(run_id, None)
