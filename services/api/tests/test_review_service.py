from datetime import datetime, timezone
from pathlib import Path

from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.models import ReviewDecisionRequest
from batchhelm_api.review_repository import SQLiteReviewRepository
from batchhelm_api.review_service import ReviewService
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident


def packet_context():
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )
    return incident, analysis, packet


def test_service_reconstructs_full_history_and_latest_readiness(
    tmp_path: Path,
) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    timestamps = iter(
        [
            datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 27, 9, 5, tzinfo=timezone.utc),
        ]
    )
    ids = iter(["review-1", "review-2"])
    service = ReviewService(
        repository,
        clock=lambda: next(timestamps),
        decision_id_factory=lambda: next(ids),
    )
    incident, analysis, packet = packet_context()

    service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=ReviewDecisionRequest(
            request_id="11111111-1111-4111-8111-111111111111",
            reviewer="Operations Manager",
            decision="approved",
            note="Approved for supplier submission.",
        ),
    )
    final = service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=ReviewDecisionRequest(
            request_id="22222222-2222-4222-8222-222222222222",
            reviewer="Operations Manager",
            decision="needs-changes",
            note="Attach signed disposal records.",
        ),
    )

    assert final.status == "needs-changes"
    assert final.ready_to_submit is False
    assert [event.id for event in final.timeline[-2:]] == ["review-1", "review-2"]


def test_changed_packet_version_starts_a_fresh_review(tmp_path: Path) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    service = ReviewService(
        repository,
        clock=lambda: datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
        decision_id_factory=lambda: "review-1",
    )
    incident, analysis, packet = packet_context()
    service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=ReviewDecisionRequest(
            request_id="11111111-1111-4111-8111-111111111111",
            reviewer="Operations Manager",
            decision="approved",
            note="Approved.",
        ),
    )
    changed_packet = packet.model_copy(
        update={"packet_version": "sha256:changed-evidence"}
    )

    state = service.get_state(
        incident=incident,
        analysis=analysis,
        packet=changed_packet,
    )

    assert state.status == "needs-changes"
    assert state.ready_to_submit is False
    assert all(event.id != "review-1" for event in state.timeline)
