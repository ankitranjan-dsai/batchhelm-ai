from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from batchhelm_api.models import (
    EvidencePacket,
    EvidenceReviewState,
    RecallAnalysis,
    RecallIncidentInput,
    ReviewDecisionRequest,
    ReviewStatus,
)
from batchhelm_api.review_repository import (
    ReviewDecisionRecord,
    ReviewRepository,
)
from batchhelm_api.review_trail import apply_review_decision, build_demo_review_state


class ReviewService:
    def __init__(
        self,
        repository: ReviewRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        decision_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._decision_id_factory = decision_id_factory or (
            lambda: f"review-{uuid4().hex}"
        )

    def get_state(
        self,
        *,
        incident: RecallIncidentInput,
        analysis: RecallAnalysis,
        packet: EvidencePacket,
    ) -> EvidenceReviewState:
        records = self._repository.list_for_packet(
            incident_id=incident.id,
            packet_version=packet.packet_version,
        )
        review_packet = (
            packet.model_copy(
                update={"generated_at": records[0].packet_generated_at}
            )
            if records
            else packet
        )
        base_state = build_demo_review_state(
            incident=incident,
            analysis=analysis,
            packet=review_packet,
        )
        state = base_state
        for record in records:
            state = apply_review_decision(
                base_state=base_state,
                current_state=state,
                reviewer=record.reviewer,
                decision=record.decision,
                note=record.note,
                decision_id=record.decision_id,
                decided_at=record.decided_at,
            )
        return state

    def record_decision(
        self,
        *,
        incident: RecallIncidentInput,
        analysis: RecallAnalysis,
        packet: EvidencePacket,
        request: ReviewDecisionRequest,
    ) -> EvidenceReviewState:
        decision = ReviewStatus(request.decision)
        if decision == ReviewStatus.pending:
            raise ValueError(
                "A review decision must approve the packet or request changes."
            )
        reviewer = request.reviewer.strip()
        note = request.note.strip()
        if not reviewer:
            raise ValueError("Reviewer is required.")
        if not note:
            raise ValueError("Review note is required.")

        decided_at = self._clock()
        if decided_at.tzinfo is None:
            raise ValueError("Review decision clock must be timezone-aware.")
        self._repository.append(
            ReviewDecisionRecord(
                decision_id=self._decision_id_factory(),
                request_id=str(request.request_id),
                incident_id=incident.id,
                packet_version=packet.packet_version,
                packet_generated_at=packet.generated_at,
                decision=decision,
                reviewer=reviewer,
                note=note,
                decided_at=decided_at.astimezone(timezone.utc).isoformat(),
            )
        )
        return self.get_state(
            incident=incident,
            analysis=analysis,
            packet=packet,
        )
