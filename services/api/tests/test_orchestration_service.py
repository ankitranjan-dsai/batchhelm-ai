from __future__ import annotations

import asyncio
from pathlib import Path

from batchhelm_api.agents import Orchestrator
from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.models import AgentRunStatus
from batchhelm_api.orchestration_repository import SQLiteOrchestrationRepository
from batchhelm_api.orchestration_service import OrchestrationService
from batchhelm_api.sample_data import build_demo_incident
from tests.conftest import fallback_gateway, make_settings


def make_service(path: Path) -> OrchestrationService:
    repository = SQLiteOrchestrationRepository(path)
    repository.initialize()
    settings = make_settings(
        ORCHESTRATION_DATABASE_PATH=path,
        QWEN_MAX_RETRIES=1,
    )
    memory = InMemoryMemoryRepository()
    return OrchestrationService(
        repository=repository,
        orchestrator_factory=lambda: Orchestrator(
            gateway=fallback_gateway(),
            memory=memory,
            settings=settings,
        ),
    )


async def test_identical_start_requests_share_one_run_and_worker(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path / "orchestration.db")
    incident = build_demo_incident()

    first, second = await asyncio.gather(
        service.start(incident, request_id="request-1"),
        service.start(incident, request_id="request-1"),
    )
    result = await service.wait_for_result(first.run_id)

    assert first.run_id == second.run_id
    assert result.run_id == first.run_id
    assert service.worker_start_count(first.run_id) == 1


async def test_stream_replays_only_events_after_cursor(tmp_path: Path) -> None:
    service = make_service(tmp_path / "orchestration.db")
    accepted = await service.start(
        build_demo_incident(),
        request_id="request-1",
    )
    await service.wait_for_result(accepted.run_id)

    frames = [frame async for frame in service.stream(accepted.run_id, after=2)]

    ids = [
        int(frame.splitlines()[0].removeprefix("id: "))
        for frame in frames
        if frame.startswith("id:")
    ]
    assert ids
    assert min(ids) == 3
    assert "event: result" in frames[-1]


async def test_recover_restarts_a_persisted_incomplete_run(tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    first = make_service(path)
    run = first.repository.create_run(
        run_id="run-1",
        incident_id=build_demo_incident().id,
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    first.repository.claim_run(run.id, "2026-06-30T09:00:00+00:00")

    restarted = make_service(path)
    await restarted.recover(build_demo_incident)
    result = await restarted.wait_for_result("run-1")

    assert result.status == AgentRunStatus.completed


async def test_closing_subscriber_does_not_cancel_worker(tmp_path: Path) -> None:
    service = make_service(tmp_path / "orchestration.db")
    accepted = await service.start(
        build_demo_incident(),
        request_id="request-1",
    )
    stream = service.stream(accepted.run_id, after=0)
    await anext(stream)
    await stream.aclose()

    result = await service.wait_for_result(accepted.run_id)

    assert result.status == AgentRunStatus.completed


class _FailingAgent(Agent):
    name = "Failing Agent"
    role = "Exercises terminal failure persistence"
    depends_on: tuple[str, ...] = ()

    async def run(self, ctx: AgentContext) -> AgentOutput:
        raise RuntimeError("expected agent failure")


async def test_failed_agent_result_keeps_failed_run_status(tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    repository = SQLiteOrchestrationRepository(path)
    repository.initialize()
    settings = make_settings(
        ORCHESTRATION_DATABASE_PATH=path,
        QWEN_MAX_RETRIES=1,
    )
    service = OrchestrationService(
        repository=repository,
        orchestrator_factory=lambda: Orchestrator(
            gateway=fallback_gateway(),
            memory=InMemoryMemoryRepository(),
            settings=settings,
            agents=[_FailingAgent()],
        ),
    )

    accepted = await service.start(
        build_demo_incident(),
        request_id="request-failure",
    )
    result = await service.wait_for_result(accepted.run_id)

    assert result.status == AgentRunStatus.failed
    assert service.get(accepted.run_id).status == AgentRunStatus.failed
