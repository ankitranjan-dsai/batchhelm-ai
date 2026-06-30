from __future__ import annotations

from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from tests.conftest import make_settings


def make_client(**overrides: object) -> TestClient:
    return TestClient(
        create_app(
            settings=make_settings(**overrides),
            memory_repository=InMemoryMemoryRepository(),
        )
    )


def test_list_agents_describes_the_society() -> None:
    response = make_client().get("/api/agents")

    assert response.status_code == 200
    names = [agent["name"] for agent in response.json()]
    assert "Orchestrator" not in names  # orchestrator is the engine, not a node
    assert "Inventory Matching Agent" in names
    assert len(names) == 9


def test_run_endpoint_returns_full_orchestration_result() -> None:
    response = make_client().post("/api/incidents/demo/run")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert len(payload["agents"]) == 9
    assert payload["analysis"]["affected_items"] == 23
    assert payload["briefing"]["headline"]
    assert payload["events"]


def test_stream_endpoint_emits_sse_events_and_result() -> None:
    response = make_client().get("/api/incidents/demo/run/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: started" in body
    assert "event: completed" in body
    assert "event: result" in body


def test_memory_endpoint_reflects_run_writes() -> None:
    client = make_client()
    client.post("/api/incidents/demo/run")

    response = client.get("/api/memory")

    assert response.status_code == 200
    records = response.json()
    assert any(r["kind"] == "supplier-alias" for r in records)


def test_briefing_endpoint_returns_management_briefing() -> None:
    response = make_client().post("/api/briefing/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["headline"]
    assert payload["source"] in {"qwen", "deterministic"}


def test_request_id_header_is_returned() -> None:
    response = make_client().get("/health")

    assert response.headers.get("x-request-id")


def test_rate_limit_returns_429_after_threshold() -> None:
    client = make_client(RATE_LIMIT_PER_MINUTE=2)

    assert client.get("/api/incidents/demo").status_code == 200
    assert client.get("/api/incidents/demo").status_code == 200
    blocked = client.get("/api/incidents/demo")

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"


def test_telemetry_counts_requests() -> None:
    client = make_client()
    client.get("/api/incidents/demo")

    response = client.get("/api/telemetry")

    assert response.status_code == 200
    assert response.json()["counters"]["requests"] >= 1
