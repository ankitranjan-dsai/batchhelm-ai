from __future__ import annotations

from pathlib import Path
from uuid import UUID

from batchhelm_api.config import Settings
from batchhelm_api.intake_models import (
    IntakeArtifactRole,
    IntakeCreateRequest,
    IntakeStatus,
    RecallCriteriaDraft,
    RecallIncidentDraft,
)
from batchhelm_api.models import ShelfInspectionResult


def test_intake_create_request_requires_uuid() -> None:
    request = IntakeCreateRequest(
        request_id="0d05fc09-d47c-43aa-9f01-b021b26f0ac8"
    )
    assert isinstance(request.request_id, UUID)


def test_draft_can_represent_missing_fields_before_review() -> None:
    draft = RecallIncidentDraft(
        criteria=RecallCriteriaDraft(),
        notice_text="Supplier notice",
    )
    assert draft.criteria.product_name == ""
    assert draft.inventory == []
    assert draft.review_required is True


def test_intake_status_and_artifact_roles_are_stable() -> None:
    assert IntakeStatus.review_required.value == "review_required"
    assert IntakeArtifactRole.recall_notice.value == "recall_notice"
    assert IntakeArtifactRole.inventory_csv.value == "inventory_csv"
    assert IntakeArtifactRole.shelf_photo.value == "shelf_photo"


def test_settings_exposes_separate_intake_database(tmp_path: Path) -> None:
    settings = Settings(
        INTAKE_DATABASE_PATH=tmp_path / "intake.db",
        _env_file=None,
    )
    assert settings.intake_database_path == tmp_path / "intake.db"


def test_real_shelf_inspection_can_report_unknown_match() -> None:
    field = ShelfInspectionResult.model_fields["recall_match"]
    assert field.annotation == bool | None
