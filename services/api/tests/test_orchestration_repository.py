from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import UUID

import pytest

from batchhelm_api.config import Settings
from batchhelm_api.models import (
    AgentEventType,
    AgentRunEvent,
    AgentRunStatus,
    OrchestrationRunAccepted,
    OrchestrationStartRequest,
    OutputSource)
from batchhelm_api.orchestration_repository import (
    OrchestrationIdempotencyConflict,
    OrchestrationStoreUnavailable,
    SQLiteOrchestrationRepository)
from batchhelm_api.orchestration_state import OrchestrationCheckpoint


def test_start_request_requires_uuid_and_accepted_response_has_urls() -> None:
    request = OrchestrationStartRequest(
        request_id="0d05fc09-d47c-43aa-9f01-b021b26f0ac8"
    )
    accepted = OrchestrationRunAccepted(
        run_id="b119e7b8f5aa470ca04ab6ce80e38dd0",
        incident_id="recall-spinach-2026-06",
        status=AgentRunStatus.pending,
        events_url="/api/v1/orchestration/runs/b119/events",
        result_url="/api/v1/orchestration/runs/b119")

    assert isinstance(request.request_id, UUID)
    assert accepted.status == AgentRunStatus.pending
    assert accepted.events_url.endswith("/events")


def test_checkpoint_defaults_to_an_empty_first_wave() -> None:
    checkpoint = OrchestrationCheckpoint(
        run_id="run-1",
        started_at="2026-06-30T09:00:00+00:00")

    assert checkpoint.next_wave == 0
    assert checkpoint.results == []
    assert checkpoint.blackboard.affected_items == 0


def test_settings_exposes_separate_orchestration_database() -> None:
    settings = Settings(
        ORCHESTRATION_DATABASE_PATH="./tmp/orchestration.db",
        _env_file=None)

    assert str(settings.orchestration_database_path).endswith("orchestration.db")


def make_repository(path: Path) -> SQLiteOrchestrationRepository:
    repository = SQLiteOrchestrationRepository(path)
    repository.initialize()
    return repository


def make_event(run_id: str, sequence: int) -> AgentRunEvent:
    return AgentRunEvent(
        id=f"event-{sequence}",
        run_id=run_id,
        sequence=sequence,
        agent="Recall Intake Agent",
        type=AgentEventType.reasoning,
        message=f"event {sequence}",
        at=f"2026-06-30T09:00:{sequence:02d}+00:00",
        source=OutputSource.deterministic)


def test_run_and_events_survive_repository_restart(tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    repository = make_repository(path)
    run = repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback")
    repository.append_event(make_event(run.id, 1))

    restarted = make_repository(path)

    assert restarted.get_run("run-1") == run
    assert restarted.list_events_after("run-1", 0)[0].sequence == 1


def test_same_idempotency_key_reuses_run_and_conflicting_incident_fails(
    tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    first = repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback")
    replay = repository.create_run(
        run_id="run-2",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback")

    assert replay.id == first.id
    with pytest.raises(OrchestrationIdempotencyConflict):
        repository.create_run(
            run_id="run-3",
            incident_id="incident-2",
            idempotency_key="request-1",
            provider_mode="demo-fallback")


def test_concurrent_identical_starts_create_one_run(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")

    def create(index: int) -> str:
        return repository.create_run(
            run_id=f"run-{index}",
            incident_id="incident-1",
            idempotency_key="request-1",
            provider_mode="demo-fallback").id

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(create, range(6)))

    assert len(set(ids)) == 1


def test_checkpoint_is_replaced_atomically_and_survives_restart(
    tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    repository = make_repository(path)
    repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback")
    first = OrchestrationCheckpoint(
        run_id="run-1",
        started_at="2026-06-30T09:00:00+00:00",
        next_wave=1)
    second = first.model_copy(update={"next_wave": 2})

    first_record = repository.save_checkpoint("run-1", first)
    second_record = repository.save_checkpoint("run-1", second)

    assert first_record.checkpoint_version == 1
    assert second_record.checkpoint_version == 2
    assert second_record.next_wave == 2
    assert make_repository(path).load_checkpoint("run-1") == second


def test_event_cursor_returns_only_later_events(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback")
    for sequence in range(1, 4):
        repository.append_event(make_event("run-1", sequence))

    assert [
        event.sequence for event in repository.list_events_after("run-1", 1)
    ] == [2, 3]
    assert repository.latest_sequence("run-1") == 3


def test_duplicate_event_sequence_is_rejected(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback")
    repository.append_event(make_event("run-1", 1))

    with pytest.raises(OrchestrationStoreUnavailable):
        repository.append_event(
            make_event("run-1", 1).model_copy(update={"id": "another-event"})
        )
