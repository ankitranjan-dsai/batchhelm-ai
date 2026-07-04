from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from batchhelm_api import inspection
from batchhelm_api.intake_extraction import (
    IntakeCompilationError,
    compile_incident_snapshot,
    extract_notice_draft,
)
from batchhelm_api.intake_models import (
    IntakeAccepted,
    IntakeArtifact,
    IntakeArtifactRole,
    IntakeConfirmRequest,
    IntakeDraftUpdate,
    IntakeFieldEvidence,
    IntakeStatus,
    IntakeView,
    RecallCriteriaDraft,
    RecallIncidentDraft,
    ResolvedRunInput,
)
from batchhelm_api.intake_repository import (
    IntakeIdempotencyConflict,
    IntakeRecord,
    IntakeRepository,
)
from batchhelm_api.intake_storage import (
    discard_packet,
    finalize_staged_packet,
    remove_orphaned_intake_directories,
    stage_intake_packet,
)
from batchhelm_api.inventory_parser import parse_inventory_csv
from batchhelm_api.models import (
    IncidentStatus,
    InventoryItem,
    OutputSource,
    RecallCriteria,
    RecallIncidentInput,
    Severity,
    UploadMetadata,
)
from batchhelm_api.notice_parser import parse_notice
from batchhelm_api.qwen import QwenGateway

GatewayFactory = Callable[[], QwenGateway]


@dataclass(frozen=True)
class IntakeUpload:
    filename: str
    media_type: str
    stream: BinaryIO


@dataclass(frozen=True)
class CreateIntakeCommand:
    request_id: str
    notice: IntakeUpload
    inventory: IntakeUpload
    shelf_photo: IntakeUpload | None = None


class IntakeValidationFailed(ValueError):
    pass


class IntakeProcessingFailed(RuntimeError):
    pass


class _ArtifactUnavailable(RuntimeError):
    pass


class IntakeService:
    def __init__(
        self,
        *,
        repository: IntakeRepository,
        artifact_root: Path,
        gateway_factory: GatewayFactory,
    ) -> None:
        self.repository = repository
        self.artifact_root = artifact_root
        self._gateway_factory = gateway_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()
        self._worker_starts: dict[str, int] = {}

    async def create(self, command: CreateIntakeCommand) -> IntakeAccepted:
        intake_id = uuid4().hex
        files = {
            IntakeArtifactRole.recall_notice: (
                command.notice.filename,
                command.notice.media_type,
                command.notice.stream,
            ),
            IntakeArtifactRole.inventory_csv: (
                command.inventory.filename,
                command.inventory.media_type,
                command.inventory.stream,
            ),
        }
        if command.shelf_photo is not None:
            files[IntakeArtifactRole.shelf_photo] = (
                command.shelf_photo.filename,
                command.shelf_photo.media_type,
                command.shelf_photo.stream,
            )
        packet = stage_intake_packet(
            root=self.artifact_root,
            intake_id=intake_id,
            files=files,
        )
        try:
            provider_mode = self._gateway_factory().status().mode
            existing = self.repository.get_by_request(command.request_id)
        except Exception:
            discard_packet(packet.staging_dir)
            raise
        if existing is not None:
            discard_packet(packet.staging_dir)
            if (
                existing.packet_fingerprint != packet.packet_fingerprint
                or existing.provider_mode != provider_mode
            ):
                raise IntakeIdempotencyConflict(
                    "Request ID was already used for another intake packet."
                )
            await self._ensure_worker(existing.id)
            return self._accepted(existing)

        finalize_staged_packet(packet)
        try:
            record = self.repository.create_intake(
                intake_id=intake_id,
                request_id=command.request_id,
                packet_fingerprint=packet.packet_fingerprint,
                provider_mode=provider_mode,
                artifacts=list(packet.artifacts),
            )
        except Exception:
            discard_packet(packet.final_dir)
            raise

        if record.id != intake_id:
            discard_packet(packet.final_dir)
        await self._ensure_worker(record.id)
        return self._accepted(record)

    def get(self, intake_id: str) -> IntakeView:
        return self.repository.get_intake(intake_id).to_view()

    def worker_start_count(self, intake_id: str) -> int:
        return self._worker_starts.get(intake_id, 0)

    async def wait_for_extraction(self, intake_id: str) -> IntakeView:
        deadline = asyncio.get_running_loop().time() + 15.0
        while True:
            view = self.get(intake_id)
            if view.status not in {
                IntakeStatus.uploaded,
                IntakeStatus.extracting,
            }:
                return view
            task = self._tasks.get(intake_id)
            if task is not None:
                await asyncio.shield(task)
            else:
                await asyncio.sleep(0)
            if asyncio.get_running_loop().time() >= deadline:
                raise IntakeProcessingFailed(
                    "Intake extraction did not finish in time."
                )

    async def recover(self) -> None:
        known_ids = self.repository.list_intake_ids()
        remove_orphaned_intake_directories(self.artifact_root, known_ids)
        for record in self.repository.list_recoverable():
            await self._ensure_worker(record.id)

    def update_draft(
        self,
        intake_id: str,
        request: IntakeDraftUpdate,
    ) -> IntakeView:
        current = self.repository.get_intake(intake_id)
        if current.draft is None:
            raise IntakeValidationFailed(
                "Intake extraction must finish before review."
            )
        stores = sorted(
            {
                item.store.strip()
                for item in request.inventory
                if item.store.strip()
            }
        )
        summary = current.draft.import_summary.model_copy(
            update={
                "accepted_rows": len(request.inventory),
                "stores": len(stores),
            }
        )
        updated = RecallIncidentDraft(
            criteria=request.criteria,
            notice_text=current.draft.notice_text,
            inventory=request.inventory,
            stores=stores,
            import_summary=summary,
            shelf_inspection=current.draft.shelf_inspection,
            review_required=self._has_blockers(
                criteria=request.criteria,
                notice_text=current.draft.notice_text,
                inventory_count=len(request.inventory),
            ),
        )
        reviewer_evidence = self._reviewer_evidence(current, updated)
        return self.repository.update_draft(
            intake_id,
            request_id=str(request.request_id),
            expected_version=request.expected_version,
            draft=updated,
            evidence=reviewer_evidence,
        ).to_view()

    def confirm(
        self,
        intake_id: str,
        request: IntakeConfirmRequest,
    ) -> IntakeView:
        current = self.repository.get_intake(intake_id)
        if current.draft is None:
            raise IntakeValidationFailed(
                "Intake extraction must finish before confirmation."
            )
        try:
            snapshot = compile_incident_snapshot(intake_id, current.draft)
        except IntakeCompilationError as exc:
            raise IntakeValidationFailed(str(exc)) from exc
        return self.repository.confirm_intake(
            intake_id,
            request_id=str(request.request_id),
            expected_version=request.expected_version,
            snapshot=snapshot,
        ).to_view()

    def link_run(
        self,
        intake_id: str,
        *,
        request_id: str,
        run_id: str,
    ) -> IntakeView:
        return self.repository.link_run(
            intake_id,
            request_id=request_id,
            run_id=run_id,
        ).to_view()

    def resolve_run_input(self, incident_id: str) -> ResolvedRunInput | None:
        record = self.repository.get_by_incident(incident_id)
        if record is None or record.snapshot is None:
            return None
        shelf_artifact = self.repository.find_artifact(
            record.id,
            IntakeArtifactRole.shelf_photo,
        )
        shelf_bytes: bytes | None = None
        if shelf_artifact is not None:
            try:
                shelf_bytes = self._read_artifact(shelf_artifact)
            except _ArtifactUnavailable as exc:
                raise IntakeProcessingFailed(
                    "Confirmed shelf evidence is unavailable."
                ) from exc
        return ResolvedRunInput(
            incident=record.snapshot,
            shelf_artifact=shelf_artifact,
            shelf_image_bytes=shelf_bytes,
            shelf_image_media_type=(
                shelf_artifact.media_type if shelf_artifact is not None else None
            ),
        )

    async def _ensure_worker(self, intake_id: str) -> None:
        async with self._lock:
            record = self.repository.get_intake(intake_id)
            if record.status not in {
                IntakeStatus.uploaded,
                IntakeStatus.extracting,
            }:
                return
            existing = self._tasks.get(intake_id)
            if existing is not None and not existing.done():
                return
            task = asyncio.create_task(self._extract(intake_id))
            self._tasks[intake_id] = task
            self._worker_starts[intake_id] = (
                self._worker_starts.get(intake_id, 0) + 1
            )
            task.add_done_callback(
                lambda completed, iid=intake_id: self._remove_task(
                    iid,
                    completed,
                )
            )

    async def _extract(self, intake_id: str) -> None:
        try:
            record = self.repository.claim_extraction(intake_id)
            artifacts = {item.role: item for item in record.artifacts}
            notice_artifact = artifacts.get(IntakeArtifactRole.recall_notice)
            inventory_artifact = artifacts.get(IntakeArtifactRole.inventory_csv)
            if notice_artifact is None or inventory_artifact is None:
                raise _ArtifactUnavailable("Required intake artifact is missing.")
            notice_content = self._read_artifact(notice_artifact)
            inventory_content = self._read_artifact(inventory_artifact)
            parsed_notice = parse_notice(
                media_type=notice_artifact.media_type,
                content=notice_content,
            )
            parsed_inventory = parse_inventory_csv(inventory_content)
            gateway = self._gateway_factory()
            extracted = await extract_notice_draft(
                gateway=gateway,
                parsed_notice=parsed_notice,
                notice_artifact=notice_artifact,
            )
            shelf_result = None
            evidence = list(extracted.evidence)
            shelf_artifact = artifacts.get(IntakeArtifactRole.shelf_photo)
            if shelf_artifact is not None:
                shelf_content = self._read_artifact(shelf_artifact)
                shelf_result = await inspection.inspect_image(
                    gateway=gateway,
                    upload=self._upload_metadata(shelf_artifact),
                    image_bytes=shelf_content,
                    media_type=shelf_artifact.media_type,
                    incident=self._provisional_incident(
                        intake_id,
                        parsed_notice.normalized_text,
                        parsed_inventory.rows,
                        extracted.criteria,
                    ),
                    allow_seeded_fallback=False,
                )
                evidence.append(
                    IntakeFieldEvidence(
                        id=uuid4().hex,
                        intake_id=intake_id,
                        field_path="shelf_inspection",
                        value=shelf_result.model_dump(mode="json"),
                        artifact_id=shelf_artifact.id,
                        locator="uploaded image",
                        source=(
                            OutputSource.deterministic
                            if shelf_result.used_fallback
                            else OutputSource.qwen
                        ),
                        confidence=shelf_result.extracted.confidence,
                        requires_review=shelf_result.review_required,
                        created_at=self._now(),
                    )
                )
            stores = sorted({item.store for item in parsed_inventory.rows})
            draft = RecallIncidentDraft(
                criteria=extracted.criteria,
                notice_text=parsed_notice.normalized_text,
                inventory=list(parsed_inventory.rows),
                stores=stores,
                import_summary=parsed_inventory.summary,
                shelf_inspection=shelf_result,
                review_required=(
                    extracted.review_required
                    or parsed_inventory.summary.rejected_rows > 0
                    or bool(shelf_result and shelf_result.review_required)
                ),
            )
            self.repository.save_extraction(
                intake_id,
                draft=draft,
                evidence=evidence,
            )
        except asyncio.CancelledError:
            raise
        except _ArtifactUnavailable:
            with suppress(Exception):
                self.repository.fail_intake(
                    intake_id,
                    code="artifact_unavailable",
                    message="An intake artifact could not be loaded.",
                )
        except Exception:
            with suppress(Exception):
                self.repository.fail_intake(
                    intake_id,
                    code="intake_processing_failed",
                    message="The intake packet could not be processed.",
                )

    def _read_artifact(self, artifact: IntakeArtifact) -> bytes:
        try:
            root = self.artifact_root.resolve()
            target = (root / artifact.relative_path).resolve(strict=True)
            target.relative_to(root)
            if not target.is_file():
                raise _ArtifactUnavailable("Artifact is not a regular file.")
            content = target.read_bytes()
            if (
                len(content) != artifact.size_bytes
                or hashlib.sha256(content).hexdigest() != artifact.sha256
            ):
                raise _ArtifactUnavailable("Artifact content does not match.")
            return content
        except (OSError, ValueError) as exc:
            raise _ArtifactUnavailable("Artifact path is unavailable.") from exc

    @staticmethod
    def _upload_metadata(artifact: IntakeArtifact) -> UploadMetadata:
        return UploadMetadata(
            id=artifact.id,
            original_filename=artifact.original_filename,
            stored_filename=artifact.stored_filename,
            media_type=artifact.media_type,
            size_bytes=artifact.size_bytes,
            path=artifact.relative_path,
        )

    @staticmethod
    def _provisional_incident(
        intake_id: str,
        notice_text: str,
        inventory: tuple[InventoryItem, ...],
        criteria: RecallCriteriaDraft,
    ) -> RecallIncidentInput:
        lots = list(criteria.affected_lots)
        upcs = list(criteria.upcs)
        return RecallIncidentInput(
            id=f"intake-{intake_id}-provisional",
            product=criteria.product_name,
            lot_range=", ".join(lots),
            status=IncidentStatus.active,
            opened_at=IntakeService._now(),
            stores=sorted({item.store for item in inventory}),
            criteria=RecallCriteria(
                product_name=criteria.product_name,
                affected_lots=lots,
                upcs=upcs,
                risk_level=criteria.risk_level or Severity.low,
                reason=criteria.reason,
                source=criteria.source,
            ),
            notice_text=notice_text,
            inventory=list(inventory),
        )

    @staticmethod
    def _reviewer_evidence(
        current: IntakeRecord,
        updated: RecallIncidentDraft,
    ) -> list[IntakeFieldEvidence]:
        if current.draft is None:
            return []
        previous = current.draft.criteria.model_dump(mode="json")
        changed = updated.criteria.model_dump(mode="json")
        result: list[IntakeFieldEvidence] = []
        for field, value in changed.items():
            if previous.get(field) == value:
                continue
            path = f"criteria.{field}"
            prior = next(
                (
                    item
                    for item in reversed(current.evidence)
                    if item.field_path == path
                ),
                None,
            )
            result.append(
                IntakeFieldEvidence(
                    id=uuid4().hex,
                    intake_id=current.id,
                    field_path=path,
                    value=value,
                    artifact_id=None,
                    locator="reviewer correction",
                    source=OutputSource.reviewer,
                    confidence=100,
                    requires_review=False,
                    supersedes_id=prior.id if prior is not None else None,
                    created_at=IntakeService._now(),
                )
            )
        return result

    @staticmethod
    def _has_blockers(
        *,
        criteria,
        notice_text: str,
        inventory_count: int,
    ) -> bool:
        return not (
            criteria.product_name.strip()
            and (criteria.affected_lots or criteria.upcs)
            and criteria.risk_level is not None
            and criteria.reason.strip()
            and criteria.source.strip()
            and notice_text.strip()
            and inventory_count > 0
        )

    @staticmethod
    def _accepted(record: IntakeRecord) -> IntakeAccepted:
        return IntakeAccepted(
            intake_id=record.id,
            status=record.status,
            status_url=f"/api/intakes/{record.id}",
            created_at=record.created_at,
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _remove_task(
        self,
        intake_id: str,
        completed: asyncio.Task[None],
    ) -> None:
        if self._tasks.get(intake_id) is completed:
            self._tasks.pop(intake_id, None)
