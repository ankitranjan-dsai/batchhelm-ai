from __future__ import annotations

from pydantic import BaseModel, Field

from batchhelm_api.models import (
    AgentRunResult,
    CustomerNoticeDraft,
    EvidenceItem,
    InventoryDecision,
    MemoryInsight,
    RecallExtraction,
    RiskAssessment,
    ShelfInspectionResult,
    StaffTask,
)


class OrchestrationBlackboard(BaseModel):
    intake_valid: bool = False
    extraction: RecallExtraction | None = None
    decisions: list[InventoryDecision] = Field(default_factory=list)
    affected_decisions: list[InventoryDecision] = Field(default_factory=list)
    affected_stores: list[str] = Field(default_factory=list)
    affected_items: int = 0
    supplier_aliases: list[str] = Field(default_factory=list)
    inspection: ShelfInspectionResult | None = None
    risk: RiskAssessment | None = None
    tasks: list[StaffTask] = Field(default_factory=list)
    customer_notice: CustomerNoticeDraft | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_progress: int = 0
    insights: list[MemoryInsight] = Field(default_factory=list)

    @classmethod
    def from_runtime(
        cls, blackboard: dict[str, object]
    ) -> "OrchestrationBlackboard":
        allowed = set(cls.model_fields)
        return cls.model_validate(
            {key: value for key, value in blackboard.items() if key in allowed}
        )

    def to_runtime(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.__dict__.items()
            if value not in (None, [], "", False)
        }


class OrchestrationCheckpoint(BaseModel):
    run_id: str
    started_at: str
    next_wave: int = Field(default=0, ge=0)
    conflicts_resolved: int = Field(default=0, ge=0)
    blackboard: OrchestrationBlackboard = Field(
        default_factory=OrchestrationBlackboard
    )
    results: list[AgentRunResult] = Field(default_factory=list)
