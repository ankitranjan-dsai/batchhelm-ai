from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from batchhelm_api.app import create_app
from batchhelm_api.config import Settings
from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.models import ReviewDecisionRequest
from batchhelm_api.review_repository import (
    ReviewDecisionRecord,
    ReviewStoreUnavailable,
)
from batchhelm_api.review_trail import apply_review_decision, build_demo_review_state
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident


def make_client(database_path: Path) -> TestClient:
    settings = Settings(
        QWEN_API_KEY="",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug",
        DATABASE_PATH=database_path,
    )
    return TestClient(create_app(settings=settings))


def test_demo_review_state_marks_packet_not_ready_until_blockers_resolved() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )

    state = build_demo_review_state(
        incident=incident,
        analysis=analysis,
        packet=packet,
    )

    assert state.incident_id == "recall-spinach-2026-06"
    assert state.status == "needs-changes"
    assert state.ready_to_submit is False
    assert state.blocker_count == 2
    assert state.checklist[0].label == "Recall initiation report attached"
    assert "disposal" in state.next_action.lower()


def test_apply_review_decision_projects_approval_timeline() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )

    base_state = build_demo_review_state(
        incident=incident,
        analysis=analysis,
        packet=packet,
    )

    state = apply_review_decision(
        base_state=base_state,
        current_state=base_state,
        reviewer="Operations Manager",
        decision="approved",
        note="Approved for supplier submission.",
        decision_id="review-decision-1",
        decided_at="2026-06-27T09:00:00+00:00",
    )

    assert state.status == "approved"
    assert state.ready_to_submit is True
    assert state.blocker_count == 0
    assert state.timeline[-1].id == "review-decision-1"
    assert state.timeline[-1].at == "2026-06-27T09:00:00+00:00"
    assert state.timeline[-1].title == "Packet Approved"


def test_review_decision_request_requires_uuid() -> None:
    with pytest.raises(ValidationError):
        ReviewDecisionRequest(
            reviewer="Operations Manager",
            decision="approved",
            note="Approved.",
        )


def test_demo_review_endpoint_returns_review_gate(tmp_path: Path) -> None:
    response = make_client(tmp_path / "batchhelm.db").get(
        "/api/evidence/demo-review"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["packet_filename"].endswith(".md")
    assert payload["status"] == "needs-changes"
    assert payload["blocker_count"] == 2


def test_demo_review_decision_endpoint_returns_approved_state(
    tmp_path: Path,
) -> None:
    response = make_client(tmp_path / "batchhelm.db").post(
        "/api/evidence/demo-review/decision",
        json={
            "request_id": "11111111-1111-4111-8111-111111111111",
            "reviewer": "Operations Manager",
            "decision": "approved",
            "note": "Approved for supplier submission.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["ready_to_submit"] is True
    assert payload["timeline"][-1]["title"] == "Packet Approved"


def test_approval_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "batchhelm.db"
    decision = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }

    first = make_client(database_path)
    assert first.post(
        "/api/evidence/demo-review/decision",
        json=decision,
    ).status_code == 200

    restarted = make_client(database_path)
    payload = restarted.get("/api/evidence/demo-review").json()

    assert payload["status"] == "approved"
    assert payload["ready_to_submit"] is True
    assert payload["timeline"][-1]["detail"] == decision["note"]


def test_packet_timeline_timestamp_survives_application_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "batchhelm.db"
    decision = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }

    first = make_client(database_path)
    first_payload = first.post(
        "/api/evidence/demo-review/decision",
        json=decision,
    ).json()
    original_packet_time = first_payload["timeline"][0]["at"]

    restarted = make_client(database_path)
    restarted_payload = restarted.get("/api/evidence/demo-review").json()

    assert restarted_payload["timeline"][0]["at"] == original_packet_time


def test_later_changes_request_keeps_approval_in_history(tmp_path: Path) -> None:
    client = make_client(tmp_path / "batchhelm.db")
    approved = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }
    changes = {
        "request_id": "22222222-2222-4222-8222-222222222222",
        "reviewer": "Operations Manager",
        "decision": "needs-changes",
        "note": "Attach signed disposal records.",
    }

    client.post("/api/evidence/demo-review/decision", json=approved)
    response = client.post("/api/evidence/demo-review/decision", json=changes)
    payload = response.json()

    assert payload["status"] == "needs-changes"
    assert payload["ready_to_submit"] is False
    assert [event["title"] for event in payload["timeline"][-2:]] == [
        "Packet Approved",
        "Changes Requested",
    ]


def test_identical_api_retry_does_not_duplicate_timeline_event(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path / "batchhelm.db")
    decision = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }

    client.post("/api/evidence/demo-review/decision", json=decision)
    payload = client.post(
        "/api/evidence/demo-review/decision",
        json=decision,
    ).json()

    assert sum(
        event["title"] == "Packet Approved"
        for event in payload["timeline"]
    ) == 1


def test_conflicting_request_id_returns_409(tmp_path: Path) -> None:
    client = make_client(tmp_path / "batchhelm.db")
    request_id = "11111111-1111-4111-8111-111111111111"
    client.post(
        "/api/evidence/demo-review/decision",
        json={
            "request_id": request_id,
            "reviewer": "Operations Manager",
            "decision": "approved",
            "note": "Approved.",
        },
    )

    response = client.post(
        "/api/evidence/demo-review/decision",
        json={
            "request_id": request_id,
            "reviewer": "Operations Manager",
            "decision": "needs-changes",
            "note": "Attach disposal records.",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"


class UnavailableReviewRepository:
    def initialize(self) -> None:
        return None

    def append(self, record: ReviewDecisionRecord) -> ReviewDecisionRecord:
        raise ReviewStoreUnavailable("sensitive sqlite failure")

    def list_for_packet(
        self,
        *,
        incident_id: str,
        packet_version: str,
    ) -> list[ReviewDecisionRecord]:
        raise ReviewStoreUnavailable("sensitive sqlite failure")


class InitializationFailureReviewRepository(UnavailableReviewRepository):
    def initialize(self) -> None:
        raise ReviewStoreUnavailable("sensitive sqlite schema failure")


def test_review_store_failure_returns_sanitized_503() -> None:
    settings = Settings(APP_ENV="test")
    client = TestClient(
        create_app(
            settings=settings,
            review_repository=UnavailableReviewRepository(),
        )
    )

    response = client.get("/api/evidence/demo-review")

    assert response.status_code == 503
    assert response.json() == {
        "code": "review_store_unavailable",
        "message": "Review history is temporarily unavailable.",
        "details": None,
    }
    assert "sqlite" not in response.text.lower()


def test_review_store_initialization_failure_returns_sanitized_503() -> None:
    settings = Settings(APP_ENV="test")
    client = TestClient(
        create_app(
            settings=settings,
            review_repository=InitializationFailureReviewRepository(),
        )
    )

    response = client.get("/api/evidence/demo-review")

    assert response.status_code == 503
    assert response.json() == {
        "code": "review_store_unavailable",
        "message": "Review history is temporarily unavailable.",
        "details": None,
    }
    assert "sqlite" not in response.text.lower()
