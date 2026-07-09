from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.event_stream import sse_pack
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.models import AgentEventType, AgentRunEvent, OutputSource
from batchhelm_api.orchestration_repository import (
    OrchestrationIdempotencyConflict,
    OrchestrationStoreUnavailable)
from tests.conftest import make_settings


def make_client(**overrides: object) -> TestClient:
    return TestClient(
        create_app(
            settings=make_settings(**overrides),
            memory_repository=InMemoryMemoryRepository())
    )


def test_list_agents_describes_the_society() -> None:
    response = make_client().get("/api/v1/agents")

    assert response.status_code == 200
    names = [agent["name"] for agent in response.json()]
    assert "Orchestrator" not in names  # orchestrator is the engine, not a node
    assert "Inventory Matching Agent" in names
    assert len(names) == 9


def test_run_endpoint_returns_full_orchestration_result() -> None:
    response = make_client().post("/api/v1/incidents/demo/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert len(payload["agents"]) == 9
    assert payload["analysis"]["affected_items"] == 23
    assert payload["briefing"]["headline"]
    assert payload["events"]


def test_latest_run_returns_404_before_any_run() -> None:
    with make_client() as client:
        response = client.get("/api/v1/orchestration/runs/latest")

    assert response.status_code == 404
    assert response.json()["code"] == "orchestration_run_not_found"


def test_latest_run_returns_most_recent_completed_result() -> None:
    with make_client() as client:
        client.post("/api/v1/incidents/demo/run")
        response = client.get("/api/v1/orchestration/runs/latest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result"] is not None
    assert len(payload["result"]["agents"]) == 9


def test_stream_endpoint_emits_sse_events_and_result() -> None:
    response = make_client().get("/api/v1/incidents/demo/run/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: started" in body
    assert "event: completed" in body
    assert "event: result" in body


def test_memory_endpoint_reflects_run_writes() -> None:
    client = make_client()
    client.post("/api/v1/incidents/demo/run")

    response = client.get("/api/v1/memory")

    assert response.status_code == 200
    records = response.json()
    assert any(r["kind"] == "supplier-alias" for r in records)


def test_briefing_endpoint_returns_management_briefing() -> None:
    response = make_client().post("/api/v1/briefing/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["headline"]
    assert payload["source"] in {"qwen", "deterministic"}


def test_request_id_header_is_returned() -> None:
    response = make_client().get("/health")

    assert response.headers.get("x-request-id")


def test_rate_limit_returns_429_after_threshold() -> None:
    client = make_client(RATE_LIMIT_PER_MINUTE=2)

    assert client.get("/api/v1/incidents/demo").status_code == 200
    assert client.get("/api/v1/incidents/demo").status_code == 200
    blocked = client.get("/api/v1/incidents/demo")

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"


def test_telemetry_counts_requests() -> None:
    client = make_client()
    client.get("/api/v1/incidents/demo")

    response = client.get("/api/v1/telemetry")

    assert response.status_code == 200
    assert response.json()["counters"]["requests"] >= 1


def test_sse_frame_uses_sequence_as_standard_event_id() -> None:
    event = AgentRunEvent(
        id="event-1",
        run_id="run-1",
        sequence=12,
        agent="Inventory Matching Agent",
        type=AgentEventType.completed,
        message="Inventory matched.",
        at="2026-06-30T09:00:00+00:00",
        source=OutputSource.qwen)

    frame = sse_pack(event)

    assert frame.startswith("id: 12\nevent: completed\n")


def test_start_status_and_event_stream_share_one_run() -> None:
    with make_client() as client:
        request_id = str(uuid4())

        started = client.post(
            "/api/v1/incidents/demo/runs",
            json={"request_id": request_id})

        assert started.status_code == 202
        accepted = started.json()
        run_id = accepted["run_id"]
        with client.stream(
            "GET",
            f"/api/v1/orchestration/runs/{run_id}/events") as response:
            body = "".join(response.iter_text())
        status = client.get(f"/api/v1/orchestration/runs/{run_id}")

        assert response.status_code == 200
        assert f'"run_id":"{run_id}"' in body
        assert "event: result" in body
        assert status.status_code == 200
        assert status.json()["result"]["run_id"] == run_id


def test_last_event_id_replays_only_missing_events() -> None:
    with make_client() as client:
        started = client.post(
            "/api/v1/incidents/demo/runs",
            json={"request_id": str(uuid4())}).json()
        run_id = started["run_id"]

        with client.stream(
            "GET",
            f"/api/v1/orchestration/runs/{run_id}/events") as initial:
            initial_body = "".join(initial.iter_text())
        assert "event: result" in initial_body

        response = client.get(
            f"/api/v1/orchestration/runs/{run_id}/events",
            headers={"Last-Event-ID": "2"})

        assert "id: 1\n" not in response.text
        assert "id: 2\n" not in response.text
        assert "id: 3\n" in response.text


def test_unknown_run_and_invalid_cursor_are_structured_errors() -> None:
    with make_client() as client:
        missing = client.get("/api/v1/orchestration/runs/missing")
        invalid = client.get(
            "/api/v1/orchestration/runs/missing/events?after=-1"
        )

        assert missing.status_code == 404
        assert missing.json()["code"] == "run_not_found"
        assert invalid.status_code == 400
        assert invalid.json()["code"] == "invalid_event_cursor"


class _InitializationFailureRepository:
    def initialize(self) -> None:
        raise OrchestrationStoreUnavailable("sqlite path leaked")


def test_orchestration_store_initialization_failure_degrades_to_503() -> None:
    app = create_app(
        settings=make_settings(),
        memory_repository=InMemoryMemoryRepository(),
        orchestration_repository=_InitializationFailureRepository(),  # type: ignore[arg-type]
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/incidents/demo/runs",
            json={"request_id": str(uuid4())})

    assert response.status_code == 503
    assert response.json() == {
        "code": "orchestration_store_unavailable",
        "message": "Orchestration history is temporarily unavailable.",
        "details": None}
    assert "sqlite" not in response.text.lower()


class _IdempotencyConflictRepository:
    def initialize(self) -> None:
        return None

    def list_recoverable(self) -> list[object]:
        return []

    def create_run(self, **_kwargs: object):
        raise OrchestrationIdempotencyConflict("private conflict detail")


def test_orchestration_idempotency_conflict_is_sanitized() -> None:
    app = create_app(
        settings=make_settings(),
        memory_repository=InMemoryMemoryRepository(),
        orchestration_repository=_IdempotencyConflictRepository(),  # type: ignore[arg-type]
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/incidents/demo/runs",
            json={"request_id": str(uuid4())})

    assert response.status_code == 409
    assert response.json()["code"] == "run_idempotency_conflict"
    assert "private conflict detail" not in response.text


def test_non_integer_last_event_id_is_rejected() -> None:
    with make_client() as client:
        response = client.get(
            "/api/v1/orchestration/runs/missing/events",
            headers={"Last-Event-ID": "not-a-number"})

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_event_cursor"
