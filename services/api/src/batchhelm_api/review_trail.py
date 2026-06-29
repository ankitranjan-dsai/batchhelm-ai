from __future__ import annotations

from batchhelm_api.models import (
    EvidenceItem,
    EvidencePacket,
    EvidenceReviewState,
    RecallAnalysis,
    RecallIncidentInput,
    ReviewChecklistItem,
    ReviewChecklistStatus,
    ReviewStatus,
    ReviewTimelineEvent,
)


def build_demo_review_state(
    *,
    incident: RecallIncidentInput,
    analysis: RecallAnalysis,
    packet: EvidencePacket,
) -> EvidenceReviewState:
    checklist = _build_checklist(analysis)
    return EvidenceReviewState(
        incident_id=incident.id,
        packet_filename=packet.filename,
        status=ReviewStatus.needs_changes,
        reviewer="Operations Manager",
        ready_to_submit=False,
        blocker_count=_count_blockers(checklist),
        next_action=(
            "Approve the customer notice and attach signed disposal records "
            "before submission."
        ),
        checklist=checklist,
        timeline=_build_timeline(packet),
    )


def apply_review_decision(
    *,
    base_state: EvidenceReviewState,
    current_state: EvidenceReviewState,
    reviewer: str,
    decision: ReviewStatus | str,
    note: str,
    decision_id: str,
    decided_at: str,
) -> EvidenceReviewState:
    review_status = ReviewStatus(decision)
    if review_status == ReviewStatus.pending:
        raise ValueError("A review decision must approve the packet or request changes.")

    reviewer_name = reviewer.strip()
    decision_note = note.strip()
    if not reviewer_name:
        raise ValueError("Reviewer is required.")
    if not decision_note:
        raise ValueError("Review note is required.")

    if review_status == ReviewStatus.approved:
        checklist = [
            item.model_copy(
                update={
                    "status": ReviewChecklistStatus.passed,
                    "detail": (
                        item.detail
                        if item.status == ReviewChecklistStatus.passed
                        else (
                            f"Accepted by reviewer {reviewer_name} "
                            "for this submission."
                        )
                    ),
                }
            )
            for item in base_state.checklist
        ]
        title = "Packet Approved"
        next_action = "Submit the approved packet to supplier and regulatory contacts."
        ready_to_submit = True
    else:
        checklist = base_state.checklist
        title = "Changes Requested"
        next_action = base_state.next_action
        ready_to_submit = False

    timeline = [
        *current_state.timeline,
        ReviewTimelineEvent(
            id=decision_id,
            title=title,
            detail=decision_note,
            actor=reviewer_name,
            at=decided_at,
            status=review_status,
        ),
    ]
    return base_state.model_copy(
        update={
            "status": review_status,
            "reviewer": reviewer_name,
            "ready_to_submit": ready_to_submit,
            "blocker_count": _count_blockers(checklist),
            "next_action": next_action,
            "checklist": checklist,
            "timeline": timeline,
        }
    )


def _build_checklist(analysis: RecallAnalysis) -> list[ReviewChecklistItem]:
    evidence_by_id = {item.id: item for item in analysis.evidence}
    return [
        ReviewChecklistItem(
            id="review-recall-report",
            label="Recall initiation report attached",
            status=ReviewChecklistStatus.passed,
            detail=_evidence_detail(evidence_by_id, "ev-1"),
        ),
        ReviewChecklistItem(
            id="review-inventory",
            label="Inventory impact reconciled",
            status=ReviewChecklistStatus.passed,
            detail=_evidence_detail(evidence_by_id, "ev-2"),
        ),
        ReviewChecklistItem(
            id="review-customer-notice",
            label="Customer communication approved",
            status=ReviewChecklistStatus.blocked,
            detail=_evidence_detail(evidence_by_id, "ev-3"),
        ),
        ReviewChecklistItem(
            id="review-supplier-notice",
            label="Supplier communication included",
            status=ReviewChecklistStatus.passed,
            detail=_evidence_detail(evidence_by_id, "ev-4"),
        ),
        ReviewChecklistItem(
            id="review-disposal",
            label="Disposal records signed",
            status=ReviewChecklistStatus.blocked,
            detail=_evidence_detail(evidence_by_id, "ev-5"),
        ),
        ReviewChecklistItem(
            id="review-regulatory",
            label="Regulatory filing package prepared",
            status=ReviewChecklistStatus.attention,
            detail=_evidence_detail(evidence_by_id, "ev-6"),
        ),
    ]


def _evidence_detail(
    evidence_by_id: dict[str, EvidenceItem],
    evidence_id: str,
) -> str:
    evidence = evidence_by_id.get(evidence_id)
    if evidence is None:
        return "Evidence source is not available."
    return f"{evidence.label}: {evidence.status.value.replace('-', ' ')}."


def _count_blockers(checklist: list[ReviewChecklistItem]) -> int:
    return sum(
        item.status == ReviewChecklistStatus.blocked
        for item in checklist
    )


def _build_timeline(packet: EvidencePacket) -> list[ReviewTimelineEvent]:
    return [
        ReviewTimelineEvent(
            id="review-packet-generated",
            title="Packet Generated",
            detail=f"{len(packet.sections)} evidence sections assembled.",
            actor="Evidence Agent",
            at=packet.generated_at,
            status=ReviewChecklistStatus.passed,
        ),
        ReviewTimelineEvent(
            id="review-automated-checks",
            title="Automated Checks Completed",
            detail="Packet structure, inventory totals, and evidence links checked.",
            actor="Compliance Agent",
            at=packet.generated_at,
            status=ReviewChecklistStatus.attention,
        ),
        ReviewTimelineEvent(
            id="review-queued",
            title="Review Requested",
            detail="Two blocking evidence items require an operations decision.",
            actor="Review Queue",
            at=packet.generated_at,
            status=ReviewStatus.needs_changes,
        ),
    ]
