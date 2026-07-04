from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, Enum):
    active = "active"
    monitoring = "monitoring"
    resolved = "resolved"


class WorkflowStatus(str, Enum):
    complete = "complete"
    active = "active"
    waiting = "waiting"
    pending = "pending"


class TaskStatus(str, Enum):
    not_started = "not-started"
    in_progress = "in-progress"
    blocked = "blocked"
    complete = "complete"


class EvidenceStatus(str, Enum):
    completed = "completed"
    in_progress = "in-progress"
    pending = "pending"


class AgentStatus(str, Enum):
    active = "active"
    waiting = "waiting"
    complete = "complete"


class InventoryStatus(str, Enum):
    quarantined = "quarantined"
    review = "review"
    clear = "clear"


class InsightTone(str, Enum):
    success = "success"
    warning = "warning"
    neutral = "neutral"


class RecallCriteria(BaseModel):
    product_name: str
    affected_lots: list[str]
    upcs: list[str] = Field(default_factory=list)
    risk_level: Severity
    reason: str
    source: str


class InventoryItem(BaseModel):
    id: str
    store: str
    sku: str
    product: str
    lot: str
    upc: str
    on_hand: int = Field(ge=0)
    location: str
    supplier_alias: str


class InventoryDecision(BaseModel):
    id: str
    store: str
    sku: str
    product: str
    lot: str
    on_hand: int
    quarantined: int
    confidence: int = Field(ge=0, le=100)
    status: InventoryStatus
    location: str
    reason: str


class WorkflowEvent(BaseModel):
    id: str
    title: str
    detail: str
    time: str
    status: WorkflowStatus


class StaffTask(BaseModel):
    id: str
    title: str
    store: str
    priority: Severity
    assignee: str
    initials: str
    due: str
    status: TaskStatus


class EvidenceItem(BaseModel):
    id: str
    label: str
    status: EvidenceStatus


class AgentActivity(BaseModel):
    id: str
    name: str
    status: AgentStatus
    action: str
    time: str


class MemoryInsight(BaseModel):
    id: str
    title: str
    detail: str
    tone: InsightTone


class Milestone(BaseModel):
    id: str
    title: str
    due: str
    remaining: str
    tone: InsightTone | Severity


class CustomerNoticeDraft(BaseModel):
    subject: str
    body: str
    audience: str
    requires_review: bool = True
    source_incident_id: str


class RecallIncidentInput(BaseModel):
    id: str
    product: str
    lot_range: str
    status: IncidentStatus
    opened_at: str
    stores: list[str]
    criteria: RecallCriteria
    notice_text: str
    inventory: list[InventoryItem]


class RecallAnalysis(BaseModel):
    incident_id: str
    product: str
    lot_range: str
    risk_level: Severity
    affected_stores: list[str]
    affected_items: int
    open_tasks: int
    evidence_progress: int
    workflow: list[WorkflowEvent]
    inventory: list[InventoryDecision]
    tasks: list[StaffTask]
    evidence: list[EvidenceItem]
    agents: list[AgentActivity]
    insights: list[MemoryInsight]
    milestones: list[Milestone]
    customer_notice: CustomerNoticeDraft


class ProviderStatus(BaseModel):
    provider: str = "qwen"
    configured: bool
    base_url: str
    text_model: str
    vision_model: str
    mode: str


class ModelJSONRequest(BaseModel):
    system: str
    user: str
    fallback: dict[str, Any] = Field(default_factory=dict)


class ModelImageJSONRequest(ModelJSONRequest):
    image_bytes: bytes = Field(exclude=True)
    media_type: str


class ModelJSONResponse(BaseModel):
    provider: str
    model: str
    used_fallback: bool
    content: dict[str, Any]
    raw_text: str | None = None


class UploadMetadata(BaseModel):
    id: str
    original_filename: str
    stored_filename: str
    media_type: str
    size_bytes: int
    path: str


class ExtractedLabel(BaseModel):
    product_name: str
    lot_code: str
    upc: str
    best_by: str | None = None
    confidence: int = Field(ge=0, le=100)


class ShelfInspectionResult(BaseModel):
    upload: UploadMetadata
    extracted: ExtractedLabel
    recall_match: bool | None
    recommended_action: str
    review_required: bool
    evidence_note: str
    provider: str
    used_fallback: bool


class EvidencePacketSection(BaseModel):
    title: str
    body: str


class EvidencePacket(BaseModel):
    incident_id: str
    packet_version: str
    filename: str
    generated_at: str
    sections: list[EvidencePacketSection]
    markdown: str


class ReviewStatus(str, Enum):
    pending = "pending"
    needs_changes = "needs-changes"
    approved = "approved"


class ReviewChecklistStatus(str, Enum):
    passed = "passed"
    attention = "attention"
    blocked = "blocked"


class ReviewChecklistItem(BaseModel):
    id: str
    label: str
    status: ReviewChecklistStatus
    detail: str


class ReviewTimelineEvent(BaseModel):
    id: str
    title: str
    detail: str
    actor: str
    at: str
    status: ReviewStatus | ReviewChecklistStatus


class EvidenceReviewState(BaseModel):
    incident_id: str
    packet_filename: str
    status: ReviewStatus
    reviewer: str
    ready_to_submit: bool
    blocker_count: int
    next_action: str
    checklist: list[ReviewChecklistItem]
    timeline: list[ReviewTimelineEvent]


class ReviewDecisionRequest(BaseModel):
    request_id: UUID
    reviewer: str = Field(default="Operations Manager", min_length=2)
    decision: ReviewStatus
    note: str = Field(min_length=2)


class APIError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Qwen structured output schemas
#
# Every Qwen call in the main workflow returns one of these typed objects. The
# gateway returns raw JSON; the workflow validates it against these schemas and
# falls back to deterministic values when validation fails. This is what makes
# Qwen "drive" the workflow while staying safe.
# ---------------------------------------------------------------------------


class OutputSource(str, Enum):
    """Where a piece of analysis came from. Surfaced in the UI so judges and
    operators can always tell real model output from deterministic fallback."""

    qwen = "qwen"
    deterministic = "deterministic"
    memory = "memory"
    reviewer = "reviewer"


class RecallExtraction(BaseModel):
    product_name: str
    affected_lots: list[str] = Field(default_factory=list)
    upcs: list[str] = Field(default_factory=list)
    supplier: str = ""
    risk_level: Severity = Severity.high
    urgency: str = ""
    summary: str = ""
    confidence: int = Field(default=0, ge=0, le=100)


class InventoryMatchReasoning(BaseModel):
    reasoning: str
    matched_count: int = Field(default=0, ge=0)
    flagged_aliases: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=100)


class RiskAssessment(BaseModel):
    risk_level: Severity
    rationale: str
    recommended_priority: Severity = Severity.high
    confidence: int = Field(default=0, ge=0, le=100)


class CustomerNoticeContent(BaseModel):
    subject: str
    body: str
    audience: str
    confidence: int = Field(default=0, ge=0, le=100)


class ManagementBriefing(BaseModel):
    headline: str
    situation: str
    actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_review: str = ""
    confidence: int = Field(default=0, ge=0, le=100)
    source: OutputSource = OutputSource.deterministic
    provider: str = "qwen"
    used_fallback: bool = True


# ---------------------------------------------------------------------------
# Persistent memory
# ---------------------------------------------------------------------------


class MemoryKind(str, Enum):
    supplier_alias = "supplier-alias"
    store_layout = "store-layout"
    decision = "decision"
    false_positive = "false-positive"
    reviewer_decision = "reviewer-decision"


class MemoryRecord(BaseModel):
    id: str
    kind: MemoryKind
    key: str
    value: str
    detail: str = ""
    confidence: int = Field(default=80, ge=0, le=100)
    occurrences: int = Field(default=1, ge=1)
    first_seen: str
    last_seen: str
    source: OutputSource = OutputSource.memory


# ---------------------------------------------------------------------------
# Agent orchestration
# ---------------------------------------------------------------------------


class AgentRunStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class AgentEventType(str, Enum):
    started = "started"
    reasoning = "reasoning"
    output = "output"
    completed = "completed"
    failed = "failed"
    retry = "retry"
    conflict = "conflict"
    resolved = "resolved"
    checkpoint = "checkpoint"
    orchestrator = "orchestrator"


class AgentDescriptor(BaseModel):
    name: str
    role: str
    depends_on: list[str] = Field(default_factory=list)


class AgentRunEvent(BaseModel):
    id: str
    run_id: str
    sequence: int
    agent: str
    type: AgentEventType
    message: str
    at: str
    source: OutputSource = OutputSource.deterministic
    data: dict[str, Any] | None = None


class AgentRunResult(BaseModel):
    agent: str
    role: str
    status: AgentRunStatus
    summary: str
    reasoning: str = ""
    confidence: int = Field(default=0, ge=0, le=100)
    source: OutputSource = OutputSource.deterministic
    provider: str = "qwen"
    used_fallback: bool = True
    model: str = ""
    attempts: int = 1
    duration_ms: int = 0
    started_at: str
    finished_at: str
    depends_on: list[str] = Field(default_factory=list)


class OrchestrationResult(BaseModel):
    run_id: str
    incident_id: str
    status: AgentRunStatus
    provider_mode: str
    started_at: str
    finished_at: str
    duration_ms: int
    agents: list[AgentRunResult]
    events: list[AgentRunEvent]
    analysis: RecallAnalysis
    briefing: ManagementBriefing
    memory_writes: int = 0
    conflicts_resolved: int = 0
    summary: str = ""


class OrchestrationStartRequest(BaseModel):
    request_id: UUID


class OrchestrationRunAccepted(BaseModel):
    run_id: str
    incident_id: str
    status: AgentRunStatus
    events_url: str
    result_url: str


class OrchestrationRunView(BaseModel):
    run_id: str
    incident_id: str
    status: AgentRunStatus
    provider_mode: str
    started_at: str | None = None
    updated_at: str
    finished_at: str | None = None
    next_wave: int = 0
    checkpoint_version: int = 0
    result: OrchestrationResult | None = None
    error_code: str | None = None
    error_message: str | None = None
