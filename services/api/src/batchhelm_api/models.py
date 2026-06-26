from __future__ import annotations

from enum import Enum
from typing import Any

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
    recall_match: bool
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
    filename: str
    generated_at: str
    sections: list[EvidencePacketSection]
    markdown: str


class APIError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
