from __future__ import annotations

from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest

from batchhelm_api.intake_models import (
    IntakeArtifact,
    IntakeArtifactRole,
    IntakeConfirmRequest,
    IntakeDraftUpdate,
    IntakeStatus)
from batchhelm_api.intake_repository import (
    IntakeStoreUnavailable,
    SQLiteIntakeRepository)
from batchhelm_api.intake_service import (
    CreateIntakeCommand,
    IntakeService,
    IntakeUpload,
    IntakeValidationFailed)
from batchhelm_api.intake_storage import (
    finalize_staged_packet,
    stage_intake_packet)
from batchhelm_api.models import ModelImageJSONRequest, ModelJSONResponse
from batchhelm_api.qwen import QwenGateway
from tests.conftest import fallback_gateway, make_settings

NOTICE = (
    b"Spinach 10 oz\n"
    b"Central Farms supplier alert\n"
    b"Affected lot L2418\n"
    b"UPC 008500001010. Possible contamination risk.\n"
)
CSV = (
    b"store,sku,product,lot,upc,on_hand,location,supplier\n"
    b"Store A,SPN10Z,Spinach 10 oz,L2418,008500001010,6,"
    b"Cooler,Central Farms\n"
)
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20


def repository(path: Path) -> SQLiteIntakeRepository:
    result = SQLiteIntakeRepository(path)
    result.initialize()
    return result


def service(
    tmp_path: Path,
    *,
    intake_repository: SQLiteIntakeRepository | None = None,
    gateway_factory: Callable[[], QwenGateway] = fallback_gateway) -> IntakeService:
    return IntakeService(
        repository=intake_repository or repository(tmp_path / "intake.db"),
        artifact_root=tmp_path / "uploads",
        gateway_factory=gateway_factory)


def create_command(
    request_id: str,
    *,
    inventory: bytes = CSV,
    notice: bytes = NOTICE,
    shelf: bool = False) -> CreateIntakeCommand:
    return CreateIntakeCommand(
        request_id=request_id,
        notice=IntakeUpload(
            filename="notice.txt",
            media_type="text/plain",
            stream=BytesIO(notice)),
        inventory=IntakeUpload(
            filename="inventory.csv",
            media_type="text/csv",
            stream=BytesIO(inventory)),
        shelf_photo=(
            IntakeUpload(
                filename="shelf.png",
                media_type="image/png",
                stream=BytesIO(PNG))
            if shelf
            else None
        ))


class CapturingGateway(QwenGateway):
    def __init__(self) -> None:
        super().__init__(make_settings())
        self.image_prompt = ""

    async def complete_image_json(
        self,
        request: ModelImageJSONRequest) -> ModelJSONResponse:
        self.image_prompt = request.user
        return await super().complete_image_json(request)


async def test_duplicate_create_starts_one_extraction_worker(
    tmp_path: Path) -> None:
    intake_service = service(tmp_path)

    first = await intake_service.create(create_command("request-1"))
    replay = await intake_service.create(create_command("request-1"))
    await intake_service.wait_for_extraction(first.intake_id)

    assert replay.intake_id == first.intake_id
    assert intake_service.worker_start_count(first.intake_id) == 1
    assert (
        intake_service.get(first.intake_id).status
        == IntakeStatus.review_required
    )


async def test_restart_recovers_extracting_intake(tmp_path: Path) -> None:
    path = tmp_path / "intake.db"
    intake_repository = repository(path)
    packet = stage_intake_packet(
        root=tmp_path / "uploads",
        intake_id="a" * 32,
        files={
            IntakeArtifactRole.recall_notice: (
                "notice.txt",
                "text/plain",
                BytesIO(NOTICE)),
            IntakeArtifactRole.inventory_csv: (
                "inventory.csv",
                "text/csv",
                BytesIO(CSV))})
    finalize_staged_packet(packet)
    intake_repository.create_intake(
        intake_id=packet.intake_id,
        request_id="request-1",
        packet_fingerprint=packet.packet_fingerprint,
        provider_mode="demo-fallback",
        artifacts=list(packet.artifacts))
    intake_repository.claim_extraction(packet.intake_id)

    restarted = service(tmp_path, intake_repository=intake_repository)
    await restarted.recover()
    await restarted.wait_for_extraction(packet.intake_id)

    assert restarted.get(packet.intake_id).status == IntakeStatus.review_required


async def test_confirmed_intake_resolves_real_shelf_artifact(
    tmp_path: Path) -> None:
    intake_service = service(tmp_path)
    accepted = await intake_service.create(
        create_command("request-1", shelf=True)
    )
    await intake_service.wait_for_extraction(accepted.intake_id)
    review = intake_service.get(accepted.intake_id)

    ready = intake_service.confirm(
        accepted.intake_id,
        IntakeConfirmRequest(
            request_id=uuid4(),
            expected_version=review.version))
    resolved = intake_service.resolve_run_input(ready.incident_id or "")

    assert resolved is not None
    assert resolved.incident.product == "Spinach 10 oz"
    assert resolved.shelf_image_bytes == PNG
    assert resolved.shelf_artifact is not None
    assert resolved.shelf_artifact.original_filename == "shelf.png"


async def test_reviewer_update_supersedes_extracted_evidence(
    tmp_path: Path) -> None:
    intake_service = service(tmp_path)
    accepted = await intake_service.create(create_command("request-1"))
    await intake_service.wait_for_extraction(accepted.intake_id)
    review = intake_service.get(accepted.intake_id)
    assert review.draft is not None
    original = next(
        item
        for item in review.evidence
        if item.field_path == "criteria.product_name"
    )
    criteria = review.draft.criteria.model_copy(
        update={"product_name": "Baby Spinach 10 oz"}
    )

    updated = intake_service.update_draft(
        accepted.intake_id,
        IntakeDraftUpdate(
            request_id=uuid4(),
            expected_version=review.version,
            criteria=criteria,
            inventory=review.draft.inventory))

    reviewer = updated.evidence[-1]
    assert updated.version == review.version + 1
    assert reviewer.value == "Baby Spinach 10 oz"
    assert reviewer.supersedes_id == original.id
    assert reviewer.source.value == "reviewer"


async def test_artifact_path_cannot_escape_upload_root(tmp_path: Path) -> None:
    intake_repository = repository(tmp_path / "intake.db")
    intake_id = "b" * 32
    packet_artifacts = [
        IntakeArtifact(
            id="notice",
            intake_id=intake_id,
            role=IntakeArtifactRole.recall_notice,
            original_filename="notice.txt",
            stored_filename="notice.txt",
            media_type="text/plain",
            size_bytes=len(NOTICE),
            sha256="a" * 64,
            relative_path="../../secret",
            created_at="2026-07-04T08:00:00+00:00"),
        IntakeArtifact(
            id="inventory",
            intake_id=intake_id,
            role=IntakeArtifactRole.inventory_csv,
            original_filename="inventory.csv",
            stored_filename="inventory.csv",
            media_type="text/csv",
            size_bytes=len(CSV),
            sha256="b" * 64,
            relative_path=f"intakes/{intake_id}/inventory.csv",
            created_at="2026-07-04T08:00:00+00:00"),
    ]
    intake_repository.create_intake(
        intake_id=intake_id,
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=packet_artifacts)
    restarted = service(tmp_path, intake_repository=intake_repository)

    await restarted.recover()
    await restarted.wait_for_extraction(intake_id)
    view = restarted.get(intake_id)

    assert view.status == IntakeStatus.failed
    assert view.error_code == "artifact_unavailable"


async def test_confirmation_rejects_incomplete_review(tmp_path: Path) -> None:
    intake_service = service(tmp_path)
    accepted = await intake_service.create(create_command("request-1"))
    await intake_service.wait_for_extraction(accepted.intake_id)
    review = intake_service.get(accepted.intake_id)
    assert review.draft is not None
    incomplete = review.draft.criteria.model_copy(
        update={"affected_lots": [], "upcs": []}
    )
    updated = intake_service.update_draft(
        accepted.intake_id,
        IntakeDraftUpdate(
            request_id=uuid4(),
            expected_version=review.version,
            criteria=incomplete,
            inventory=review.draft.inventory))

    with pytest.raises(IntakeValidationFailed, match="lot or UPC"):
        intake_service.confirm(
            accepted.intake_id,
            IntakeConfirmRequest(
                request_id=uuid4(),
                expected_version=updated.version))


async def test_incomplete_intake_never_seeds_demo_criteria_into_vision(
    tmp_path: Path) -> None:
    gateway = CapturingGateway()
    intake_service = service(tmp_path, gateway_factory=lambda: gateway)
    accepted = await intake_service.create(
        create_command(
            "request-1",
            notice=b"Recall notice without identifiers",
            shelf=True)
    )

    await intake_service.wait_for_extraction(accepted.intake_id)

    assert gateway.image_prompt
    assert "Spinach 10 oz" not in gateway.image_prompt
    assert "L2418" not in gateway.image_prompt


async def test_repository_failure_discards_staged_packet(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch) -> None:
    intake_repository = repository(tmp_path / "intake.db")
    intake_service = service(tmp_path, intake_repository=intake_repository)

    def unavailable(_request_id: str) -> None:
        raise IntakeStoreUnavailable("offline")

    monkeypatch.setattr(
        intake_repository,
        "get_by_request",
        unavailable)

    with pytest.raises(IntakeStoreUnavailable):
        await intake_service.create(create_command("request-1"))

    staging_root = tmp_path / "uploads" / ".staging"
    assert not staging_root.exists() or list(staging_root.iterdir()) == []
