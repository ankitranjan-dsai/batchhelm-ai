from batchhelm_api.models import EvidenceItem, EvidenceStatus
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import (
    analyze_recall_incident,
    build_customer_notice,
    calculate_evidence_progress,
)


def test_demo_recall_matches_all_affected_inventory() -> None:
    incident = build_demo_incident()

    analysis = analyze_recall_incident(incident)

    assert analysis.affected_stores == ["Store A", "Store B"]
    assert analysis.affected_items == 23
    assert len(analysis.inventory) == 6
    assert {item.lot for item in analysis.inventory} == {
        "L2418",
        "L2419",
        "L2420",
        "L2421",
        "L2422",
    }
    assert all(item.status == "quarantined" for item in analysis.inventory)


def test_workflow_generates_tasks_and_evidence_packet_progress() -> None:
    analysis = analyze_recall_incident(build_demo_incident())

    assert analysis.open_tasks == 5
    assert [task.title for task in analysis.tasks][:2] == [
        "Review customer notice draft",
        "Verify quarantined inventory",
    ]
    assert analysis.evidence_progress == 64
    assert analysis.evidence[-1].label == "Regulatory Filing Package"


def test_evidence_progress_handles_weighted_in_progress_items() -> None:
    evidence = [
        EvidenceItem(id="a", label="A", status=EvidenceStatus.completed),
        EvidenceItem(id="b", label="B", status=EvidenceStatus.in_progress),
        EvidenceItem(id="c", label="C", status=EvidenceStatus.pending),
    ]

    assert calculate_evidence_progress(evidence) == 47


def test_customer_notice_is_specific_to_recall() -> None:
    incident = build_demo_incident()

    notice = build_customer_notice(incident, affected_items=23)

    assert notice.subject == "Important notice: Spinach 10 oz recall"
    assert "L2418-L2422" in notice.body
    assert "23 items" in notice.body
    assert notice.requires_review is True
