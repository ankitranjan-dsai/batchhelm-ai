from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from batchhelm_api.models import (
    InventoryItem,
    OrchestrationRunAccepted,
    OutputSource,
    RecallIncidentInput,
    Severity,
    ShelfInspectionResult,
)


class IntakeStatus(str, Enum):
    uploaded = "uploaded"
    extracting = "extracting"
    review_required = "review_required"
    ready = "ready"
    run_started = "run_started"
    failed = "failed"


class IntakeArtifactRole(str, Enum):
    recall_notice = "recall_notice"
    inventory_csv = "inventory_csv"
    shelf_photo = "shelf_photo"


class IntakeCreateRequest(BaseModel):
    request_id: UUID


class IntakeArtifact(BaseModel):
    id: str
    intake_id: str
    role: IntakeArtifactRole
    original_filename: str
    stored_filename: str
    media_type: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(min_length=64, max_length=64)
    relative_path: str
    created_at: str


class PublicIntakeArtifact(BaseModel):
    id: str
    role: IntakeArtifactRole
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str


class RecallCriteriaDraft(BaseModel):
    product_name: str = ""
    affected_lots: list[str] = Field(default_factory=list)
    upcs: list[str] = Field(default_factory=list)
    risk_level: Severity | None = None
    reason: str = ""
    source: str = ""


class InventoryImportSummary(BaseModel):
    accepted_rows: int = 0
    rejected_rows: int = 0
    stores: int = 0
    mapped_headers: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RecallIncidentDraft(BaseModel):
    criteria: RecallCriteriaDraft = Field(default_factory=RecallCriteriaDraft)
    notice_text: str = ""
    inventory: list[InventoryItem] = Field(default_factory=list)
    stores: list[str] = Field(default_factory=list)
    import_summary: InventoryImportSummary = Field(
        default_factory=InventoryImportSummary
    )
    shelf_inspection: ShelfInspectionResult | None = None
    review_required: bool = True


class IntakeFieldEvidence(BaseModel):
    id: str
    intake_id: str
    field_path: str
    value: Any
    artifact_id: str | None = None
    locator: str
    source: OutputSource
    confidence: int = Field(ge=0, le=100)
    requires_review: bool
    supersedes_id: str | None = None
    created_at: str


class IntakeAccepted(BaseModel):
    intake_id: str
    status: IntakeStatus
    status_url: str
    created_at: str


class IntakeView(BaseModel):
    intake_id: str
    status: IntakeStatus
    version: int = Field(ge=0)
    provider_mode: str
    created_at: str
    updated_at: str
    artifacts: list[PublicIntakeArtifact] = Field(default_factory=list)
    draft: RecallIncidentDraft | None = None
    evidence: list[IntakeFieldEvidence] = Field(default_factory=list)
    incident_id: str | None = None
    run_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class IntakeDraftUpdate(BaseModel):
    request_id: UUID
    expected_version: int = Field(ge=0)
    criteria: RecallCriteriaDraft
    inventory: list[InventoryItem]


class IntakeConfirmRequest(BaseModel):
    request_id: UUID
    expected_version: int = Field(ge=0)


class IntakeRunRequest(BaseModel):
    request_id: UUID


class ResolvedRunInput(BaseModel):
    incident: RecallIncidentInput
    shelf_artifact: IntakeArtifact | None = None
    shelf_image_bytes: bytes | None = Field(default=None, exclude=True)
    shelf_image_media_type: str | None = None


class IntakeRunAccepted(BaseModel):
    intake: IntakeView
    run: OrchestrationRunAccepted
