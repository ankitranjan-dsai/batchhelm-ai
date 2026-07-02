# Durable Incident Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a real recall notice, inventory CSV, and optional shelf photo into a reviewed immutable incident that launches and recovers through BatchHelm's existing durable agent workflow.

**Architecture:** Add a SQLite-backed intake bounded context with immutable artifact storage, bounded document and CSV parsers, structured Qwen extraction, append-only field provenance, optimistic reviewer updates, and restart-safe local extraction workers. Confirmed snapshots resolve through a new `ResolvedRunInput` boundary so initial and recovered orchestration workers receive the same incident and real shelf artifact.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite WAL, asyncio, pypdf, pypdfium2, Pillow, Qwen Cloud, React 18, TypeScript, Vite, Vitest, Testing Library.

**Approved specification:** `docs/superpowers/specs/2026-07-02-batchhelm-durable-incident-intake-design.md`

**Git policy:** Every checkpoint uses the repository-configured Ankit Ranjan identity. Qwen is documented as a runtime product dependency.

---

## File Map

### Backend files to create

- `services/api/src/batchhelm_api/intake_models.py`
  - Intake lifecycle, artifact, draft, provenance, request, response, and internal run-input models.
- `services/api/src/batchhelm_api/intake_storage.py`
  - Bounded signature-aware staging, fingerprinting, atomic finalization, and cleanup.
- `services/api/src/batchhelm_api/notice_parser.py`
  - Plain-text, text-PDF, scanned-PDF, and image notice parsing.
- `services/api/src/batchhelm_api/inventory_parser.py`
  - Structured CSV header normalization, row validation, duplicate detection, and import summary.
- `services/api/src/batchhelm_api/intake_extraction.py`
  - Qwen extraction, safe literal fallback, evidence merging, and draft assembly.
- `services/api/src/batchhelm_api/intake_repository.py`
  - Typed repository protocol, SQLite schema, idempotency, versioning, snapshots, evidence, and recovery queries.
- `services/api/src/batchhelm_api/intake_service.py`
  - Intake lifecycle, worker ownership, extraction recovery, reviewer updates, confirmation, run linkage, and run-input resolution.
- `services/api/tests/test_intake_models.py`
- `services/api/tests/test_intake_storage.py`
- `services/api/tests/test_notice_parser.py`
- `services/api/tests/test_inventory_parser.py`
- `services/api/tests/test_intake_extraction.py`
- `services/api/tests/test_intake_repository.py`
- `services/api/tests/test_intake_service.py`
- `services/api/tests/test_intake_api.py`

### Backend files to modify

- `services/api/pyproject.toml`
  - Runtime PDF/image parser dependencies and test fixture dependency.
- `services/api/uv.lock`
  - Locked dependency graph.
- `services/api/src/batchhelm_api/config.py`
  - `INTAKE_DATABASE_PATH`.
- `services/api/src/batchhelm_api/models.py`
  - Unknown shelf-match support.
- `services/api/src/batchhelm_api/inspection.py`
  - Neutral fallback for real images.
- `services/api/src/batchhelm_api/agents/inventory.py`
  - Pass real-image fallback policy to shelf inspection.
- `services/api/src/batchhelm_api/agents/orchestrator.py`
  - Carry shelf upload metadata with bytes and media type.
- `services/api/src/batchhelm_api/orchestration_service.py`
  - `ResolvedRunInput` start and restart resolver.
- `services/api/src/batchhelm_api/app.py`
  - Intake wiring, lifecycle order, error handlers, and HTTP endpoints.
- `services/api/tests/conftest.py`
  - Isolated intake database and upload directory.
- `services/api/tests/test_inspection_api.py`
  - Neutral real-image fallback.
- `services/api/tests/test_orchestrator.py`
  - Real shelf metadata propagation.
- `services/api/tests/test_orchestration_service.py`
  - Arbitrary incident and shelf artifact recovery.
- `services/api/tests/test_orchestration_api.py`
  - Demo compatibility after resolver migration.

### Frontend files to create

- `apps/web/src/intakeSession.ts`
  - Intake state, stages, polling/version guards, and reducer.
- `apps/web/src/intakeSession.test.ts`
- `apps/web/src/useIntakeWorkspace.ts`
  - Create, poll, update, confirm, and launch lifecycle.
- `apps/web/src/useIntakeWorkspace.test.tsx`
- `apps/web/src/IntakeWorkspace.tsx`
  - Files, Review, and Launch UI.
- `apps/web/src/IntakeWorkspace.test.tsx`

### Frontend files to modify

- `apps/web/src/api.ts`
  - Intake contracts and HTTP functions.
- `apps/web/src/useOrchestrationRun.ts`
  - Adopt an intake-backed accepted run.
- `apps/web/src/useOrchestrationRun.test.tsx`
  - Run adoption and Strict Mode deduplication.
- `apps/web/src/App.tsx`
  - New Recall command and workspace integration.
- `apps/web/src/styles.css`
  - Responsive intake workspace design system.

### Sample, deployment, and documentation files

- `sample-data/recall-notice-spinach.pdf`
- `sample-data/inventory-spinach.csv`
- `sample-data/inventory-spinach-invalid.csv`
- `sample-data/store-b-cooler-spinach.png`
- `sample-data/README.md`
- `.env.example`
- `Dockerfile`
- `docker-compose.yml`
- `README.md`
- `docs/architecture.md`
- `docs/demo-script.md`
- `docs/deployment-alibaba-cloud.md`
- `docs/known-limitations.md`
- `docs/qwen-integration.md`
- `docs/submission-checklist.md`

---

### Task 1: Define Intake Domain Contracts And Configuration

**Files:**
- Create: `services/api/src/batchhelm_api/intake_models.py`
- Create: `services/api/tests/test_intake_models.py`
- Modify: `services/api/src/batchhelm_api/models.py`
- Modify: `services/api/src/batchhelm_api/config.py`
- Modify: `services/api/tests/conftest.py`
- Modify: `services/api/pyproject.toml`
- Modify: `services/api/uv.lock`

- [ ] **Step 1: Add failing contract tests**

Create `services/api/tests/test_intake_models.py` with focused public-contract
tests:

```python
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
from batchhelm_api.models import OutputSource, ShelfInspectionResult


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
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd services/api
uv run pytest tests/test_intake_models.py -q
```

Expected: collection fails because `intake_models` and
`INTAKE_DATABASE_PATH` do not exist and `recall_match` is not nullable.

- [ ] **Step 3: Add parser dependencies**

Add runtime dependencies in `services/api/pyproject.toml`:

```toml
"pillow>=11.0.0",
"pypdf>=5.4.0",
"pypdfium2>=4.30.0",
```

Add a development dependency used only to build deterministic PDF fixtures:

```toml
"reportlab>=4.2.5",
```

Regenerate the lock:

```bash
cd services/api
uv lock
uv sync --extra dev
```

- [ ] **Step 4: Add intake database configuration**

Add to `Settings` after `orchestration_database_path`:

```python
intake_database_path: Path = Field(
    default=Path("./data/intake.db"),
    validation_alias="INTAKE_DATABASE_PATH",
)
```

Add an isolated path to the `base` dictionary in
`services/api/tests/conftest.py`:

```python
"INTAKE_DATABASE_PATH": (
    Path(gettempdir()) / f"batchhelm-intake-test-{uuid4().hex}.db"
),
"UPLOAD_DIR": (
    Path(gettempdir()) / f"batchhelm-upload-test-{uuid4().hex}"
),
```

- [ ] **Step 5: Add the intake domain models**

Create `services/api/src/batchhelm_api/intake_models.py` with these public
types and constraints:

```python
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
```

- [ ] **Step 6: Make shelf match nullable**

Change `ShelfInspectionResult.recall_match` in
`services/api/src/batchhelm_api/models.py`:

```python
recall_match: bool | None
```

- [ ] **Step 7: Run targeted tests and type-level regression tests**

Run:

```bash
cd services/api
uv run pytest tests/test_intake_models.py tests/test_inspection_api.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 8: Commit and push the contract checkpoint**

```bash
git add services/api/pyproject.toml services/api/uv.lock \
  services/api/src/batchhelm_api/config.py \
  services/api/src/batchhelm_api/models.py \
  services/api/src/batchhelm_api/intake_models.py \
  services/api/tests/conftest.py \
  services/api/tests/test_intake_models.py
git commit -m "feat(api): define durable intake contracts"
git push origin main
```

---

### Task 2: Build Bounded Immutable Artifact Storage

**Files:**
- Create: `services/api/src/batchhelm_api/intake_storage.py`
- Create: `services/api/tests/test_intake_storage.py`

- [ ] **Step 1: Write failing storage tests**

Create `services/api/tests/test_intake_storage.py`:

```python
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from batchhelm_api.intake_models import IntakeArtifactRole
from batchhelm_api.intake_storage import (
    IntakePacketTooLarge,
    IntakeUploadInvalid,
    stage_intake_packet,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 20
PDF = b"%PDF-1.4\n" + b"x" * 20
CSV = b"store,product,lot,on_hand\nStore A,Spinach,L1,2\n"


def test_stages_valid_packet_with_sha256_and_generated_names(tmp_path: Path) -> None:
    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files={
            IntakeArtifactRole.recall_notice: (
                "notice.pdf",
                "application/pdf",
                BytesIO(PDF),
            ),
            IntakeArtifactRole.inventory_csv: (
                "inventory.csv",
                "text/csv",
                BytesIO(CSV),
            ),
            IntakeArtifactRole.shelf_photo: (
                "shelf.png",
                "image/png",
                BytesIO(PNG),
            ),
        },
    )
    assert packet.packet_fingerprint
    assert len(packet.artifacts) == 3
    assert all(item.sha256 and "/" not in item.stored_filename for item in packet.artifacts)
    assert packet.staging_dir.is_dir()


def test_rejects_spoofed_image_signature(tmp_path: Path) -> None:
    with pytest.raises(IntakeUploadInvalid, match="signature"):
        stage_intake_packet(
            root=tmp_path,
            intake_id="intake-1",
            files={
                IntakeArtifactRole.recall_notice: (
                    "notice.png",
                    "image/png",
                    BytesIO(b"not-a-png"),
                ),
                IntakeArtifactRole.inventory_csv: (
                    "inventory.csv",
                    "text/csv",
                    BytesIO(CSV),
                ),
            },
        )


def test_rejects_total_packet_over_limit(tmp_path: Path) -> None:
    with pytest.raises(IntakePacketTooLarge):
        stage_intake_packet(
            root=tmp_path,
            intake_id="intake-1",
            packet_limit=30,
            files={
                IntakeArtifactRole.recall_notice: (
                    "notice.pdf",
                    "application/pdf",
                    BytesIO(PDF),
                ),
                IntakeArtifactRole.inventory_csv: (
                    "inventory.csv",
                    "text/csv",
                    BytesIO(CSV),
                ),
            },
        )
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_intake_storage.py -q
```

Expected: import failure for `intake_storage`.

- [ ] **Step 3: Implement storage contracts and limits**

Create `services/api/src/batchhelm_api/intake_storage.py` with:

```python
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from batchhelm_api.intake_models import IntakeArtifact, IntakeArtifactRole

NOTICE_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
INVENTORY_TYPES = {"text/csv": ".csv"}
SHELF_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ROLE_LIMITS = {
    IntakeArtifactRole.recall_notice: 12 * 1024 * 1024,
    IntakeArtifactRole.inventory_csv: 4 * 1024 * 1024,
    IntakeArtifactRole.shelf_photo: 8 * 1024 * 1024,
}
PACKET_LIMIT = 24 * 1024 * 1024
CHUNK_SIZE = 64 * 1024


class IntakeUploadInvalid(ValueError):
    pass


class IntakePacketTooLarge(IntakeUploadInvalid):
    pass


@dataclass(frozen=True)
class StagedIntakePacket:
    intake_id: str
    staging_dir: Path
    final_dir: Path
    packet_fingerprint: str
    artifacts: tuple[IntakeArtifact, ...]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extension(role: IntakeArtifactRole, media_type: str) -> str:
    allowed = {
        IntakeArtifactRole.recall_notice: NOTICE_TYPES,
        IntakeArtifactRole.inventory_csv: INVENTORY_TYPES,
        IntakeArtifactRole.shelf_photo: SHELF_TYPES,
    }[role]
    try:
        return allowed[media_type]
    except KeyError as exc:
        raise IntakeUploadInvalid(
            f"Unsupported media type for {role.value}."
        ) from exc


def _validate_signature(media_type: str, first_bytes: bytes) -> None:
    signatures = {
        "application/pdf": b"%PDF-",
        "image/jpeg": b"\xff\xd8\xff",
        "image/png": b"\x89PNG\r\n\x1a\n",
        "image/webp": b"RIFF",
    }
    expected = signatures.get(media_type)
    if expected is not None and not first_bytes.startswith(expected):
        raise IntakeUploadInvalid("Uploaded file signature does not match its media type.")
    if media_type == "image/webp" and first_bytes[8:12] != b"WEBP":
        raise IntakeUploadInvalid("Uploaded file signature does not match its media type.")


def stage_intake_packet(
    *,
    root: Path,
    intake_id: str,
    files: dict[IntakeArtifactRole, tuple[str, str, BinaryIO]],
    packet_limit: int = PACKET_LIMIT,
) -> StagedIntakePacket:
    required = {
        IntakeArtifactRole.recall_notice,
        IntakeArtifactRole.inventory_csv,
    }
    if not required.issubset(files):
        raise IntakeUploadInvalid("Recall notice and inventory CSV are required.")

    staging_dir = root / ".staging" / uuid4().hex
    final_dir = root / "intakes" / intake_id
    staging_dir.mkdir(parents=True, exist_ok=False)
    artifacts: list[IntakeArtifact] = []
    total = 0
    try:
        for role in sorted(files, key=lambda value: value.value):
            original_name, media_type, stream = files[role]
            extension = _extension(role, media_type)
            artifact_id = uuid4().hex
            stored_filename = f"{artifact_id}{extension}"
            target = staging_dir / stored_filename
            digest = hashlib.sha256()
            size = 0
            first = b""
            with target.open("wb") as output:
                while chunk := stream.read(CHUNK_SIZE):
                    if not first:
                        first = chunk[:16]
                    size += len(chunk)
                    total += len(chunk)
                    if size > ROLE_LIMITS[role] or total > packet_limit:
                        raise IntakePacketTooLarge("Uploaded intake packet is too large.")
                    digest.update(chunk)
                    output.write(chunk)
            if size == 0:
                raise IntakeUploadInvalid("Uploaded file was empty.")
            _validate_signature(media_type, first)
            if media_type in {"text/plain", "text/csv"}:
                text_content = target.read_bytes()
                text_content.decode("utf-8-sig")
                if b"\x00" in text_content:
                    raise IntakeUploadInvalid("Text uploads cannot contain NUL bytes.")
            artifacts.append(
                IntakeArtifact(
                    id=artifact_id,
                    intake_id=intake_id,
                    role=role,
                    original_filename=Path(original_name).name,
                    stored_filename=stored_filename,
                    media_type=media_type,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                    relative_path=str(Path("intakes") / intake_id / stored_filename),
                    created_at=_now(),
                )
            )
        fingerprint_payload = [
            {"role": item.role.value, "sha256": item.sha256}
            for item in sorted(artifacts, key=lambda item: item.role.value)
        ]
        packet_fingerprint = hashlib.sha256(
            json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return StagedIntakePacket(
            intake_id=intake_id,
            staging_dir=staging_dir,
            final_dir=final_dir,
            packet_fingerprint=packet_fingerprint,
            artifacts=tuple(artifacts),
        )
    except (UnicodeDecodeError, OSError) as exc:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise IntakeUploadInvalid("Uploaded file could not be validated.") from exc
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def finalize_staged_packet(packet: StagedIntakePacket) -> None:
    packet.final_dir.parent.mkdir(parents=True, exist_ok=True)
    if packet.final_dir.exists():
        raise IntakeUploadInvalid("Intake artifact destination already exists.")
    os.replace(packet.staging_dir, packet.final_dir)


def discard_packet(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


def remove_orphaned_intake_directories(
    root: Path,
    known_intake_ids: set[str],
) -> None:
    intake_root = root / "intakes"
    if not intake_root.is_dir():
        return
    for child in intake_root.iterdir():
        if (
            child.name not in known_intake_ids
            and re.fullmatch(r"[0-9a-f]{32}", child.name)
            and child.is_dir()
            and not child.is_symlink()
        ):
            shutil.rmtree(child)
```

- [ ] **Step 4: Expand tests for each media type and cleanup path**

Add tests for:

```python
@pytest.mark.parametrize(
    ("media_type", "content"),
    [
        ("text/plain", b"Recall notice"),
        ("application/pdf", PDF),
        ("image/jpeg", b"\xff\xd8\xff" + b"x" * 20),
        ("image/png", PNG),
        ("image/webp", b"RIFF\x10\x00\x00\x00WEBP" + b"x" * 20),
    ],
)
def test_notice_media_types_are_accepted(
    tmp_path: Path, media_type: str, content: bytes
) -> None:
    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files={
            IntakeArtifactRole.recall_notice: ("notice", media_type, BytesIO(content)),
            IntakeArtifactRole.inventory_csv: (
                "inventory.csv",
                "text/csv",
                BytesIO(CSV),
            ),
        },
    )
    assert packet.artifacts[0].size_bytes > 0


def test_original_path_components_are_removed(tmp_path: Path) -> None:
    packet = stage_intake_packet(
        root=tmp_path,
        intake_id="intake-1",
        files={
            IntakeArtifactRole.recall_notice: (
                "../../notice.pdf",
                "application/pdf",
                BytesIO(PDF),
            ),
            IntakeArtifactRole.inventory_csv: (
                "../inventory.csv",
                "text/csv",
                BytesIO(CSV),
            ),
        },
    )
    assert {item.original_filename for item in packet.artifacts} == {
        "notice.pdf",
        "inventory.csv",
    }
```

- [ ] **Step 5: Run storage tests and full existing upload tests**

```bash
cd services/api
uv run pytest tests/test_intake_storage.py tests/test_storage.py -q
```

Expected: all tests pass and no artifact remains outside the pytest temporary
directory.

- [ ] **Step 6: Commit and push immutable storage**

```bash
git add services/api/src/batchhelm_api/intake_storage.py \
  services/api/tests/test_intake_storage.py
git commit -m "feat(api): store intake artifacts immutably"
git push origin main
```

---

### Task 3: Parse Text, PDF, Scanned PDF, And Image Notices

**Files:**
- Create: `services/api/src/batchhelm_api/notice_parser.py`
- Create: `services/api/tests/test_notice_parser.py`

- [ ] **Step 1: Write failing notice-parser tests**

Create tests using `reportlab` to build text and scanned fixtures in
`tmp_path`:

```python
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from reportlab.pdfgen.canvas import Canvas

from batchhelm_api.notice_parser import (
    NoticeParseError,
    parse_notice,
)


def text_pdf(text: str) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(72, 720, text)
    canvas.save()
    return buffer.getvalue()


def image_notice() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (640, 480), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def test_extracts_text_and_page_locator_from_pdf() -> None:
    parsed = parse_notice(
        media_type="application/pdf",
        content=text_pdf("Spinach lot L2418 UPC 008500001010"),
    )
    assert "Spinach lot L2418" in parsed.normalized_text
    assert parsed.page_count == 1
    assert parsed.rendered_pages == []
    assert parsed.text_pages[0].locator == "page 1"


def test_treats_image_only_pdf_as_scanned(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(image_notice())
    pdf = BytesIO()
    canvas = Canvas(pdf)
    canvas.drawImage(str(source), 72, 240, width=468, height=360)
    canvas.save()
    parsed = parse_notice(
        media_type="application/pdf",
        content=pdf.getvalue(),
    )
    assert parsed.normalized_text == ""
    assert parsed.page_count == 1
    assert len(parsed.rendered_pages) == 1
    assert parsed.rendered_pages[0].locator == "page 1"
    assert parsed.rendered_pages[0].png_bytes.startswith(b"\x89PNG")


def test_accepts_image_notice_without_fabricated_text() -> None:
    parsed = parse_notice(media_type="image/png", content=image_notice())
    assert parsed.normalized_text == ""
    assert len(parsed.rendered_pages) == 1
    assert parsed.rendered_pages[0].locator == "image 1"


def test_rejects_pdf_over_page_limit() -> None:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for _index in range(11):
        canvas.drawString(72, 720, "Recall")
        canvas.showPage()
    canvas.save()
    with pytest.raises(NoticeParseError, match="10 pages"):
        parse_notice(media_type="application/pdf", content=buffer.getvalue())
```

- [ ] **Step 2: Run the parser tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_notice_parser.py -q
```

Expected: import failure for `notice_parser`.

- [ ] **Step 3: Implement typed parser output**

Create these parser result types:

```python
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import pypdfium2 as pdfium
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

MAX_PDF_PAGES = 10
MAX_NOTICE_CHARACTERS = 100_000
SCANNED_TEXT_THRESHOLD = 200
MAX_RENDERED_PAGES = 3


class NoticeParseError(ValueError):
    pass


@dataclass(frozen=True)
class NoticeTextPage:
    locator: str
    text: str


@dataclass(frozen=True)
class RenderedNoticePage:
    locator: str
    png_bytes: bytes
    media_type: str = "image/png"


@dataclass(frozen=True)
class ParsedNotice:
    normalized_text: str
    page_count: int
    text_pages: tuple[NoticeTextPage, ...]
    rendered_pages: tuple[RenderedNoticePage, ...]
    warnings: tuple[str, ...]
```

Implement `parse_notice(media_type: str, content: bytes) -> ParsedNotice`:

- decode `text/plain` with `utf-8-sig`;
- normalize CRLF to LF, collapse more than two blank lines, and trim;
- return JPEG/PNG/WebP as one rendered page with no invented text;
- read PDFs with `PdfReader(BytesIO(content), strict=False)`;
- reject encrypted documents that cannot be decrypted with an empty password;
- reject more than 10 pages;
- extract at most 100,000 normalized characters;
- treat fewer than 200 non-whitespace characters in the first three pages as
  scanned;
- render at most the first three scanned pages at 144 DPI using
  `pdfium.PdfDocument(content)`, `page.render(scale=2)`, and Pillow PNG output;
- translate parser/library exceptions into `NoticeParseError` without paths or
  raw content.

- [ ] **Step 4: Add memory-bound and malformed-file tests**

Add:

```python
def test_rejects_malformed_pdf() -> None:
    with pytest.raises(NoticeParseError, match="could not be read"):
        parse_notice(media_type="application/pdf", content=b"%PDF-not-valid")


def test_rejects_text_over_character_limit() -> None:
    with pytest.raises(NoticeParseError, match="100000"):
        parse_notice(
            media_type="text/plain",
            content=("x" * 100_001).encode("utf-8"),
        )
```

Also monkeypatch a PDF page content stream whose decoded data exceeds the
parser's per-page content-stream ceiling and assert rejection before
`extract_text()` is called.

- [ ] **Step 5: Run notice parser tests**

```bash
cd services/api
uv run pytest tests/test_notice_parser.py -q
```

Expected: text, PDF, scanned-PDF, image, malformed, encrypted, page-limit, and
character-limit tests all pass.

- [ ] **Step 6: Commit and push notice parsing**

```bash
git add services/api/src/batchhelm_api/notice_parser.py \
  services/api/tests/test_notice_parser.py
git commit -m "feat(api): parse bounded recall notice formats"
git push origin main
```

---

### Task 4: Parse Inventory CSV And Compile Reviewable Drafts

**Files:**
- Create: `services/api/src/batchhelm_api/inventory_parser.py`
- Create: `services/api/tests/test_inventory_parser.py`
- Create: `services/api/src/batchhelm_api/intake_extraction.py`
- Create: `services/api/tests/test_intake_extraction.py`

- [ ] **Step 1: Write failing CSV tests**

Create `services/api/tests/test_inventory_parser.py`:

```python
from batchhelm_api.inventory_parser import InventoryParseError, parse_inventory_csv


def test_maps_header_aliases_and_builds_inventory_rows() -> None:
    parsed = parse_inventory_csv(
        b"Store Name,Item SKU,Product Name,Lot Code,UPC,Qty,Location,Supplier\n"
        b"Store A,SPN10Z,Spinach 10 oz,L2418,008500001010,6,Back Room,Central Farms\n"
    )
    assert parsed.rows[0].store == "Store A"
    assert parsed.rows[0].on_hand == 6
    assert parsed.summary.mapped_headers["Store Name"] == "store"
    assert parsed.summary.accepted_rows == 1


def test_reports_invalid_rows_without_dropping_valid_rows() -> None:
    parsed = parse_inventory_csv(
        b"store,product,lot,on_hand\n"
        b"Store A,Spinach,L2418,6\n"
        b"Store B,Spinach,L2419,-2\n"
    )
    assert len(parsed.rows) == 1
    assert parsed.summary.rejected_rows == 1
    assert "row 3" in parsed.summary.warnings[0].lower()


def test_rejects_duplicate_inventory_identity() -> None:
    parsed = parse_inventory_csv(
        b"store,sku,product,lot,on_hand,location\n"
        b"Store A,S1,Spinach,L1,2,Cooler\n"
        b"Store A,S1,Spinach,L1,3,Cooler\n"
    )
    assert parsed.summary.accepted_rows == 1
    assert parsed.summary.rejected_rows == 1


def test_rejects_csv_with_no_valid_rows() -> None:
    with pytest.raises(InventoryParseError, match="valid inventory"):
        parse_inventory_csv(b"store,product,lot,on_hand\n,,,bad\n")
```

- [ ] **Step 2: Run CSV tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_inventory_parser.py -q
```

Expected: import failure for `inventory_parser`.

- [ ] **Step 3: Implement the structured CSV parser**

Create `ParsedInventory` and `parse_inventory_csv`:

```python
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from io import StringIO

from batchhelm_api.intake_models import InventoryImportSummary
from batchhelm_api.models import InventoryItem

MAX_ROWS = 5_000
MAX_COLUMNS = 128

HEADER_ALIASES = {
    "store": {"store", "store_name", "location_name", "branch"},
    "sku": {"sku", "item_sku", "stock_code"},
    "product": {"product", "product_name", "item", "description"},
    "lot": {"lot", "lot_code", "batch", "batch_code"},
    "upc": {"upc", "barcode", "gtin"},
    "on_hand": {"on_hand", "qty", "quantity", "stock"},
    "location": {"location", "bin", "stock_location"},
    "supplier_alias": {"supplier", "supplier_alias", "vendor"},
}
REQUIRED = {"store", "product", "lot", "on_hand"}


class InventoryParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedInventory:
    rows: tuple[InventoryItem, ...]
    summary: InventoryImportSummary


def _normalize_header(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")
```

`parse_inventory_csv(content: bytes) -> ParsedInventory` must:

1. decode with `utf-8-sig`;
2. use `csv.DictReader` and reject missing headers;
3. reject more than 128 columns or 5,000 data rows;
4. map normalized aliases exactly once and reject ambiguous duplicate mappings;
5. require mapped `store`, `product`, `lot`, and `on_hand`;
6. parse non-negative integer quantities;
7. assign stable row IDs from the one-based CSV data row number;
8. keep optional values as empty strings;
9. identify duplicates by `(store, sku, lot, location)`;
10. emit sanitized row warnings;
11. reject a file with zero valid rows.

- [ ] **Step 4: Write failing safe-extraction and compiler tests**

Create `services/api/tests/test_intake_extraction.py`:

```python
from __future__ import annotations

from batchhelm_api.intake_extraction import (
    compile_incident_snapshot,
    safe_literal_extraction,
)
from batchhelm_api.intake_models import RecallCriteriaDraft, RecallIncidentDraft
from batchhelm_api.inventory_parser import parse_inventory_csv


NOTICE = (
    "Spinach 10 oz\n"
    "Central Farms supplier alert\n"
    "Affected lots L2418 and L2419\n"
    "UPC 008500001010. Possible contamination risk."
)


def test_safe_extraction_uses_only_verbatim_notice_values() -> None:
    result = safe_literal_extraction(NOTICE)
    assert result.criteria.affected_lots == ["L2418", "L2419"]
    assert result.criteria.upcs == ["008500001010"]
    assert result.criteria.product_name == "Spinach 10 oz"
    assert result.review_required is True
    assert all(item.confidence <= 65 for item in result.evidence)


def test_safe_extraction_never_copies_demo_values() -> None:
    result = safe_literal_extraction("Recall notice without identifiers")
    assert result.criteria.affected_lots == []
    assert result.criteria.upcs == []
    assert "Spinach" not in result.criteria.product_name


def test_compiler_requires_confirmed_criteria_and_inventory() -> None:
    inventory = parse_inventory_csv(
        b"store,product,lot,on_hand\nStore A,Spinach,L2418,6\n"
    )
    draft = RecallIncidentDraft(
        criteria=RecallCriteriaDraft(
            product_name="Spinach",
            affected_lots=["L2418"],
            risk_level="high",
            reason="Possible contamination",
            source="Central Farms alert",
        ),
        notice_text=NOTICE,
        inventory=list(inventory.rows),
        stores=["Store A"],
        import_summary=inventory.summary,
        review_required=False,
    )
    snapshot = compile_incident_snapshot("intake-1", draft)
    assert snapshot.id.startswith("intake-intake-1-")
    assert snapshot.inventory[0].lot == "L2418"
```

- [ ] **Step 5: Implement literal extraction and snapshot compilation**

In `intake_extraction.py`, define:

```python
@dataclass(frozen=True)
class DraftExtraction:
    criteria: RecallCriteriaDraft
    evidence: tuple[IntakeFieldEvidence, ...]
    review_required: bool
```

Use bounded regular expressions:

```python
LOT_PATTERN = re.compile(r"\b(?:LOT\s*)?([A-Z]{1,4}\d{2,12})\b", re.IGNORECASE)
UPC_PATTERN = re.compile(r"\b\d{8,14}\b")
RISK_WORDS = {
    "critical": Severity.critical,
    "death": Severity.critical,
    "hospitalization": Severity.critical,
    "contamination": Severity.high,
    "allergen": Severity.high,
    "mislabel": Severity.medium,
}
```

Only store substrings present in normalized notice text. Use the first non-empty
line as the product candidate only when it is 3-120 characters and not a
generic heading such as `recall notice`, `urgent`, or `supplier alert`.

`compile_incident_snapshot(intake_id, draft, now=None)` must reject:

- blank product;
- no affected lots and no UPCs;
- missing risk;
- blank reason or source;
- blank notice text;
- no inventory rows.

It returns `RecallIncidentInput` with sorted unique stores, active status, UTC
timestamp, and a generated immutable incident ID.

- [ ] **Step 6: Run parser and compiler tests**

```bash
cd services/api
uv run pytest tests/test_inventory_parser.py tests/test_intake_extraction.py -q
```

Expected: CSV normalization, warning behavior, literal safety, and compilation
tests pass.

- [ ] **Step 7: Commit and push structured parsing**

```bash
git add services/api/src/batchhelm_api/inventory_parser.py \
  services/api/src/batchhelm_api/intake_extraction.py \
  services/api/tests/test_inventory_parser.py \
  services/api/tests/test_intake_extraction.py
git commit -m "feat(api): normalize intake evidence safely"
git push origin main
```

---

### Task 5: Add Qwen Intake Extraction And Neutral Real-Image Vision

**Files:**
- Modify: `services/api/src/batchhelm_api/intake_extraction.py`
- Modify: `services/api/src/batchhelm_api/inspection.py`
- Modify: `services/api/src/batchhelm_api/agents/inventory.py`
- Modify: `services/api/src/batchhelm_api/models.py`
- Expand: `services/api/tests/test_intake_extraction.py`
- Modify: `services/api/tests/test_inspection_api.py`

- [ ] **Step 1: Add failing Qwen extraction tests**

Add mocked text and vision cases:

```python
@pytest.mark.asyncio
async def test_qwen_text_extraction_returns_field_evidence() -> None:
    gateway = scripted_gateway(
        {
            "product_name": {"value": "Spinach 10 oz", "confidence": 96},
            "affected_lots": {"value": ["L2418"], "confidence": 95},
            "upcs": {"value": ["008500001010"], "confidence": 94},
            "risk_level": {"value": "high", "confidence": 90},
            "reason": {"value": "Possible contamination", "confidence": 91},
            "source": {"value": "Central Farms", "confidence": 92},
        }
    )
    result = await extract_notice_draft(
        gateway=gateway,
        parsed_notice=ParsedNotice(
            normalized_text=NOTICE,
            page_count=1,
            text_pages=(NoticeTextPage(locator="page 1", text=NOTICE),),
            rendered_pages=(),
            warnings=(),
        ),
        notice_artifact=artifact("notice"),
    )
    assert result.criteria.product_name == "Spinach 10 oz"
    assert all(item.source == OutputSource.qwen for item in result.evidence)


@pytest.mark.asyncio
async def test_unavailable_qwen_returns_literal_review_draft() -> None:
    result = await extract_notice_draft(
        gateway=fallback_gateway(),
        parsed_notice=parsed_text_notice(NOTICE),
        notice_artifact=artifact("notice"),
    )
    assert result.review_required is True
    assert result.criteria.affected_lots == ["L2418", "L2419"]
    assert all(item.source == OutputSource.deterministic for item in result.evidence)
```

- [ ] **Step 2: Add failing neutral shelf fallback test**

Add:

```python
@pytest.mark.asyncio
async def test_real_image_fallback_is_unknown_not_positive(tmp_path: Path) -> None:
    result = await inspection.inspect_image(
        gateway=fallback_gateway(),
        upload=real_upload(tmp_path),
        image_bytes=PNG,
        media_type="image/png",
        incident=build_demo_incident(),
        allow_seeded_fallback=False,
    )
    assert result.recall_match is None
    assert result.extracted.product_name == ""
    assert result.review_required is True
```

Run and verify RED:

```bash
cd services/api
uv run pytest tests/test_intake_extraction.py tests/test_inspection_api.py -q
```

- [ ] **Step 3: Implement typed per-field Qwen extraction**

Add private Pydantic models in `intake_extraction.py`:

```python
class ExtractedStringField(BaseModel):
    value: str = ""
    confidence: int = Field(default=0, ge=0, le=100)


class ExtractedListField(BaseModel):
    value: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=100)


class ExtractedRiskField(BaseModel):
    value: Severity | None = None
    confidence: int = Field(default=0, ge=0, le=100)


class IntakeRecallExtraction(BaseModel):
    product_name: ExtractedStringField
    affected_lots: ExtractedListField
    upcs: ExtractedListField
    risk_level: ExtractedRiskField
    reason: ExtractedStringField
    source: ExtractedStringField
```

Implement:

```python
async def extract_notice_draft(
    *,
    gateway: QwenGateway,
    parsed_notice: ParsedNotice,
    notice_artifact: IntakeArtifact,
) -> DraftExtraction:
```

Rules:

- text input calls `complete_json`;
- rendered pages call `complete_image_json` at most three times;
- every call uses an empty structured fallback, not demo data;
- provider fallback or invalid JSON routes to `safe_literal_extraction`;
- returned values must appear verbatim in text input, except normalized risk
  enum values;
- image values retain the rendered page locator;
- merge identical list values case-insensitively;
- stop image calls when all required fields reach 80 confidence;
- confidence below 80 sets `requires_review`;
- every image-derived field requires review when two pages disagree.

- [ ] **Step 4: Implement neutral shelf inspection fallback**

Change:

```python
def inspection_request(
    *,
    image_bytes: bytes,
    media_type: str,
    incident: RecallIncidentInput,
    allow_seeded_fallback: bool,
) -> ModelImageJSONRequest:
```

Use the current seeded fallback only when `allow_seeded_fallback` is true.
Otherwise use:

```python
{
    "product_name": "",
    "lot_code": "",
    "upc": "",
    "best_by": None,
    "confidence": 0,
    "recall_match": None,
    "recommended_action": "Review the uploaded shelf image manually.",
    "review_required": True,
    "evidence_note": "Qwen vision was unavailable; no image match was inferred.",
}
```

Propagate the flag through `inspect_image`. In `ShelfVisionAgent`, use:

```python
has_real_image = "shelf_image_bytes" in ctx.blackboard
result = await inspection.inspect_image(
    gateway=ctx.gateway,
    upload=upload,
    image_bytes=image_bytes,
    media_type=media_type,
    incident=ctx.incident,
    allow_seeded_fallback=not has_real_image,
)
```

In `inspection_from_model_content`, preserve unknown match state:

```python
raw_match = content.get("recall_match")
recall_match = raw_match if isinstance(raw_match, bool) else None
```

Pass `recall_match` into `ShelfInspectionResult` instead of coercing with
`bool(...)`.

Render unknown state explicitly in Shelf Vision reasoning and summaries:

```python
match_label = (
    "match"
    if result.recall_match is True
    else "no match"
    if result.recall_match is False
    else "unknown"
)
```

The explicit `/api/inspections/demo` endpoint passes
`allow_seeded_fallback=True`; `/api/inspections/shelf-photo` passes false.

- [ ] **Step 5: Run extraction, inspection, Qwen, and agent tests**

```bash
cd services/api
uv run pytest tests/test_intake_extraction.py tests/test_inspection_api.py \
  tests/test_qwen_gateway.py tests/test_qwen_tasks.py tests/test_orchestrator.py -q
```

Expected: live mocked Qwen, no-key literal fallback, seeded demo vision, neutral
real vision, and existing orchestration cases pass.

- [ ] **Step 6: Commit and push Qwen intake extraction**

```bash
git add services/api/src/batchhelm_api/intake_extraction.py \
  services/api/src/batchhelm_api/inspection.py \
  services/api/src/batchhelm_api/agents/inventory.py \
  services/api/src/batchhelm_api/models.py \
  services/api/tests/test_intake_extraction.py \
  services/api/tests/test_inspection_api.py
git commit -m "feat(api): extract real intake evidence with Qwen"
git push origin main
```

---

### Task 6: Persist Intakes, Artifacts, Evidence, And Snapshots In SQLite

**Files:**
- Create: `services/api/src/batchhelm_api/intake_repository.py`
- Create: `services/api/tests/test_intake_repository.py`

- [ ] **Step 1: Write failing repository behavior tests**

Cover persistence, idempotency, optimistic versioning, immutable confirmation,
run linkage, and recovery:

```python
def test_intake_artifacts_and_evidence_survive_restart(tmp_path: Path) -> None:
    path = tmp_path / "intake.db"
    repository = make_repository(path)
    record = repository.create_intake(
        intake_id="intake-1",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-1"),
    )
    repository.claim_extraction(record.id)
    repository.save_extraction(
        record.id,
        draft=review_draft(),
        evidence=evidence("intake-1"),
    )

    restarted = make_repository(path)
    view = restarted.get_intake(record.id).to_view()
    assert view.status == IntakeStatus.review_required
    assert view.artifacts[0].original_filename == "notice.txt"
    assert view.evidence[0].field_path == "criteria.product_name"


def test_identical_create_request_reuses_intake(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "intake.db")
    first = repository.create_intake(
        intake_id="intake-1",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-1"),
    )
    replay = repository.create_intake(
        intake_id="intake-2",
        request_id="request-1",
        packet_fingerprint="a" * 64,
        provider_mode="demo-fallback",
        artifacts=artifacts("intake-2"),
    )
    assert replay.id == first.id


def test_stale_reviewer_version_is_rejected(tmp_path: Path) -> None:
    repository = reviewable_repository(tmp_path)
    first = repository.update_draft(
        "intake-1",
        request_id="update-1",
        expected_version=1,
        draft=review_draft(product="Spinach"),
        evidence=reviewer_evidence("Spinach"),
    )
    assert first.version == 2
    with pytest.raises(IntakeVersionConflict):
        repository.update_draft(
            "intake-1",
            request_id="update-2",
            expected_version=1,
            draft=review_draft(product="Wrong"),
            evidence=reviewer_evidence("Wrong"),
        )


def test_confirmation_snapshot_is_immutable(tmp_path: Path) -> None:
    repository = reviewable_repository(tmp_path)
    snapshot = confirmed_snapshot()
    ready = repository.confirm_intake(
        "intake-1",
        request_id="confirm-1",
        expected_version=1,
        snapshot=snapshot,
    )
    assert ready.status == IntakeStatus.ready
    assert repository.resolve_incident(snapshot.id) == snapshot
    with pytest.raises(IntakeStateConflict):
        repository.update_draft(
            "intake-1",
            request_id="update-late",
            expected_version=ready.version,
            draft=review_draft(),
            evidence=[],
        )
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_intake_repository.py -q
```

Expected: import failure for `intake_repository`.

- [ ] **Step 3: Define repository records, protocol, and errors**

Create:

```python
class IntakeStoreUnavailable(RuntimeError):
    pass


class IntakeNotFound(LookupError):
    pass


class IntakeIdempotencyConflict(RuntimeError):
    pass


class IntakeStateConflict(RuntimeError):
    pass


class IntakeVersionConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class IntakeRecord:
    id: str
    request_id: str
    packet_fingerprint: str
    status: IntakeStatus
    provider_mode: str
    version: int
    created_at: str
    updated_at: str
    artifacts: tuple[IntakeArtifact, ...] = ()
    draft: RecallIncidentDraft | None = None
    evidence: tuple[IntakeFieldEvidence, ...] = ()
    snapshot: RecallIncidentInput | None = None
    incident_id: str | None = None
    run_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_view(self) -> IntakeView:
        return IntakeView(
            intake_id=self.id,
            status=self.status,
            version=self.version,
            provider_mode=self.provider_mode,
            created_at=self.created_at,
            updated_at=self.updated_at,
            artifacts=[
                PublicIntakeArtifact(
                    id=item.id,
                    role=item.role,
                    original_filename=item.original_filename,
                    media_type=item.media_type,
                    size_bytes=item.size_bytes,
                    sha256=item.sha256,
                )
                for item in self.artifacts
            ],
            draft=self.draft,
            evidence=list(self.evidence),
            incident_id=self.incident_id,
            run_id=self.run_id,
            error_code=self.error_code,
            error_message=self.error_message,
        )
```

The `IntakeRepository` protocol exposes:

```python
class IntakeRepository(Protocol):
    def initialize(self) -> None:
        pass

    def get_by_request(self, request_id: str) -> IntakeRecord | None:
        pass

    def list_intake_ids(self) -> set[str]:
        pass

    def create_intake(
        self,
        *,
        intake_id: str,
        request_id: str,
        packet_fingerprint: str,
        provider_mode: str,
        artifacts: list[IntakeArtifact],
    ) -> IntakeRecord:
        pass

    def get_intake(self, intake_id: str) -> IntakeRecord:
        pass

    def claim_extraction(self, intake_id: str) -> IntakeRecord:
        pass

    def save_extraction(
        self,
        intake_id: str,
        *,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord:
        pass

    def update_draft(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord:
        pass

    def confirm_intake(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        snapshot: RecallIncidentInput,
    ) -> IntakeRecord:
        pass

    def link_run(
        self,
        intake_id: str,
        *,
        request_id: str,
        run_id: str,
    ) -> IntakeRecord:
        pass

    def fail_intake(
        self,
        intake_id: str,
        *,
        code: str,
        message: str,
    ) -> IntakeRecord:
        pass

    def list_recoverable(self) -> list[IntakeRecord]:
        pass

    def resolve_incident(self, incident_id: str) -> RecallIncidentInput | None:
        pass

    def find_artifact(
        self,
        intake_id: str,
        role: IntakeArtifactRole,
    ) -> IntakeArtifact | None:
        pass
```

- [ ] **Step 4: Create schema version 1**

Use WAL, foreign keys, `busy_timeout = 5000`, and:

```sql
CREATE TABLE intakes (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE,
    packet_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    provider_mode TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    draft_json TEXT,
    snapshot_json TEXT,
    incident_id TEXT UNIQUE,
    run_id TEXT,
    error_code TEXT,
    error_message TEXT
);

CREATE TABLE intake_artifacts (
    id TEXT PRIMARY KEY,
    intake_id TEXT NOT NULL,
    role TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (intake_id, role),
    FOREIGN KEY (intake_id) REFERENCES intakes(id) ON DELETE CASCADE
);

CREATE TABLE intake_field_evidence (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    id TEXT NOT NULL UNIQUE,
    intake_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    value_json TEXT NOT NULL,
    artifact_id TEXT,
    locator TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    requires_review INTEGER NOT NULL,
    supersedes_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (intake_id) REFERENCES intakes(id) ON DELETE CASCADE,
    FOREIGN KEY (artifact_id) REFERENCES intake_artifacts(id),
    FOREIGN KEY (supersedes_id) REFERENCES intake_field_evidence(id)
);

CREATE TABLE intake_requests (
    request_id TEXT PRIMARY KEY,
    intake_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    result_version INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (intake_id) REFERENCES intakes(id) ON DELETE CASCADE
);

CREATE INDEX intake_evidence_sequence
ON intake_field_evidence(intake_id, sequence);

CREATE INDEX intake_status_updated
ON intakes(status, updated_at);
```

- [ ] **Step 5: Implement transaction invariants**

Use `BEGIN IMMEDIATE` for create, update, confirm, and run linkage.

- Create reuses only identical request ID, fingerprint, and provider mode.
- Claim accepts `uploaded` or `extracting` and sets `extracting`.
- Save extraction appends evidence and sets `review_required` in one
  transaction.
- Update verifies state `review_required`, expected version, and request
  payload hash; it appends reviewer evidence and increments version once.
- Confirm verifies state, version, and idempotency before storing canonical
  snapshot JSON and incident ID.
- Link run accepts `ready` or the identical replay in `run_started`.
- Recoverable records are `uploaded` and `extracting`.
- Repository decoding validates all JSON through Pydantic.
- SQLite, OS, JSON, and validation failures become
  `IntakeStoreUnavailable`; domain errors retain their typed exceptions.

- [ ] **Step 6: Add unavailable repository behavior**

`UnavailableIntakeRepository` raises sanitized `IntakeStoreUnavailable` for all
operations except:

```python
def initialize(self) -> None:
    return None

def list_recoverable(self) -> list[IntakeRecord]:
    return []
```

- [ ] **Step 7: Run repository tests**

```bash
cd services/api
uv run pytest tests/test_intake_repository.py -q
```

Expected: persistence, idempotency, version conflicts, immutable snapshots,
run linkage, recovery listing, and unavailable-store tests pass.

- [ ] **Step 8: Commit and push the SQLite repository**

```bash
git add services/api/src/batchhelm_api/intake_repository.py \
  services/api/tests/test_intake_repository.py
git commit -m "feat(api): persist incident intake lifecycle"
git push origin main
```

---

### Task 7: Coordinate Restart-Safe Intake Extraction

**Files:**
- Create: `services/api/src/batchhelm_api/intake_service.py`
- Create: `services/api/tests/test_intake_service.py`
- Modify: `services/api/src/batchhelm_api/intake_extraction.py`

- [ ] **Step 1: Write failing lifecycle tests**

Cover one worker, idempotent create, disconnect-independent work, recovery,
review update, confirmation, and run-input resolution:

```python
@pytest.mark.asyncio
async def test_duplicate_create_starts_one_extraction_worker(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    first = await service.create(create_command("request-1"))
    replay = await service.create(create_command("request-1"))
    await service.wait_for_extraction(first.intake_id)
    assert replay.intake_id == first.intake_id
    assert service.worker_start_count(first.intake_id) == 1


@pytest.mark.asyncio
async def test_restart_recovers_extracting_intake(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "intake.db")
    create_persisted_extracting_intake(repository, tmp_path)
    restarted = make_service(tmp_path, repository=repository)
    await restarted.recover()
    await restarted.wait_for_extraction("intake-1")
    assert restarted.get("intake-1").status == IntakeStatus.review_required


@pytest.mark.asyncio
async def test_confirmed_intake_resolves_real_shelf_artifact(tmp_path: Path) -> None:
    service = await confirmed_service(tmp_path)
    resolved = service.resolve_run_input(service.get("intake-1").incident_id)
    assert resolved is not None
    assert resolved.incident.product == "Spinach 10 oz"
    assert resolved.shelf_image_bytes == PNG
    assert resolved.shelf_artifact.original_filename == "shelf.png"
```

- [ ] **Step 2: Run tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_intake_service.py -q
```

Expected: import failure for `intake_service`.

- [ ] **Step 3: Define command and service boundaries**

Add:

```python
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
```

`IntakeService` constructor receives:

```python
repository: IntakeRepository
artifact_root: Path
gateway_factory: Callable[[], QwenGateway]
```

It owns:

```python
self._tasks: dict[str, asyncio.Task[None]]
self._lock = asyncio.Lock()
self._worker_starts: dict[str, int]
```

- [ ] **Step 4: Implement create and worker lifecycle**

`create(command)`:

1. generate an intake ID;
2. stage and fingerprint the packet;
3. call `repository.get_by_request(command.request_id)`;
4. if an existing record has the same fingerprint and provider mode, discard
   staging, ensure its worker, and return it;
5. if an existing record differs, discard staging and raise
   `IntakeIdempotencyConflict`;
6. atomically finalize the staged directory;
7. call `repository.create_intake` with final relative paths;
8. if a concurrent identical request won the unique-key race, remove this
   intake's final directory and return the winning record;
9. remove this intake's final directory on any persistence failure;
10. ensure one extraction worker;
11. return `IntakeAccepted`.

Startup calls `remove_orphaned_intake_directories` after repository
initialization. The function compares generated directory names under
`UPLOAD_DIR/intakes` with repository intake IDs and removes only generated
directories that have no row. It never follows symlinks.

`_extract(intake_id)`:

1. claim extraction;
2. load artifact bytes from repository-relative paths under `artifact_root`;
3. parse the notice and inventory;
4. run Qwen/safe extraction;
5. run optional shelf inspection with neutral fallback;
6. assemble draft and evidence;
7. save draft/evidence atomically;
8. mark sanitized failure on non-cancellation errors.

`recover()` starts workers for repository `uploaded` and `extracting` records.
It verifies each relative path resolves under `artifact_root`; missing or
escaping artifacts fail with `artifact_unavailable`.

- [ ] **Step 5: Implement reviewer operations**

`update_draft`:

- validates current draft;
- diffs criteria and inventory against stored draft;
- creates reviewer evidence only for changed criteria fields;
- uses the previous current evidence ID as `supersedes_id`;
- recomputes stores, import summary, and review flag;
- delegates optimistic version and request idempotency to the repository.

`confirm`:

- compiles `RecallIncidentInput`;
- rejects remaining blocking criteria or no valid inventory;
- stores the immutable snapshot.

`resolve_run_input(incident_id)`:

- loads the confirmed snapshot;
- finds optional shelf artifact;
- validates and reads bytes from its relative path;
- returns `ResolvedRunInput`;
- returns `None` for unknown incident IDs.

- [ ] **Step 6: Add path escape and cancellation tests**

Add:

```python
@pytest.mark.asyncio
async def test_artifact_path_cannot_escape_upload_root(tmp_path: Path) -> None:
    service = service_with_artifact_path(tmp_path, "../../secret")
    await service.recover()
    view = service.get("intake-1")
    assert view.status == IntakeStatus.failed
    assert view.error_code == "artifact_unavailable"


@pytest.mark.asyncio
async def test_client_scope_does_not_cancel_extraction(tmp_path: Path) -> None:
    gate = asyncio.Event()
    service = make_slow_service(tmp_path, gate)
    accepted = await service.create(create_command("request-1"))
    gate.set()
    await service.wait_for_extraction(accepted.intake_id)
    assert service.get(accepted.intake_id).status == IntakeStatus.review_required
```

- [ ] **Step 7: Run lifecycle tests**

```bash
cd services/api
uv run pytest tests/test_intake_service.py \
  tests/test_intake_repository.py tests/test_intake_extraction.py -q
```

Expected: all intake lifecycle tests pass.

- [ ] **Step 8: Commit and push intake lifecycle**

```bash
git add services/api/src/batchhelm_api/intake_service.py \
  services/api/src/batchhelm_api/intake_extraction.py \
  services/api/tests/test_intake_service.py
git commit -m "feat(api): coordinate restart-safe intake extraction"
git push origin main
```

---

### Task 8: Expose The Intake HTTP Lifecycle

**Files:**
- Modify: `services/api/src/batchhelm_api/app.py`
- Create: `services/api/tests/test_intake_api.py`
- Modify: `services/api/tests/conftest.py`

- [ ] **Step 1: Write failing endpoint tests**

Test create, polling, update, confirmation, launch-state rejection, and
sanitized errors:

```python
def test_create_intake_returns_202_and_reviewable_status(client: TestClient) -> None:
    response = client.post(
        "/api/intakes",
        data={"request_id": "0d05fc09-d47c-43aa-9f01-b021b26f0ac8"},
        files={
            "notice": ("notice.txt", NOTICE.encode(), "text/plain"),
            "inventory": ("inventory.csv", CSV, "text/csv"),
        },
    )
    assert response.status_code == 202
    accepted = response.json()
    view = wait_for_intake(client, accepted["status_url"])
    assert view["status"] == "review_required"
    assert view["draft"]["criteria"]["affected_lots"] == ["L2418"]


def test_confirm_before_reviewable_returns_state_conflict(client: TestClient) -> None:
    response = client.post(
        "/api/intakes/missing/confirm",
        json={
            "request_id": "1d05fc09-d47c-43aa-9f01-b021b26f0ac8",
            "expected_version": 0,
        },
    )
    assert response.status_code == 404
    assert response.json()["code"] == "intake_not_found"


def test_packet_over_limit_returns_413_without_paths(client: TestClient) -> None:
    response = client.post(
        "/api/intakes",
        data={"request_id": "2d05fc09-d47c-43aa-9f01-b021b26f0ac8"},
        files={
            "notice": ("notice.txt", b"x" * (12 * 1024 * 1024 + 1), "text/plain"),
            "inventory": ("inventory.csv", CSV, "text/csv"),
        },
    )
    assert response.status_code == 413
    assert response.json()["code"] == "upload_too_large"
    assert "/tmp/" not in response.text
```

- [ ] **Step 2: Run API tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_intake_api.py -q
```

Expected: 404 or route-not-found failures for the new endpoints.

- [ ] **Step 3: Wire repository and service before app lifespan**

Extend `create_app`:

```python
def create_app(
    settings: Settings | None = None,
    review_repository: ReviewRepository | None = None,
    memory_repository: MemoryRepository | None = None,
    orchestration_repository: OrchestrationRepository | None = None,
    intake_repository: IntakeRepository | None = None,
) -> FastAPI:
```

Initialize `SQLiteIntakeRepository`, degrade to
`UnavailableIntakeRepository`, construct `IntakeService`, and store both on
`app.state`.

Update lifespan order:

```python
await intake_service.recover()
await orchestration_service.recover(resolve_run_input)
yield
```

The resolver returns the demo run input for the demo incident ID and otherwise
delegates to `intake_service.resolve_run_input`.

- [ ] **Step 4: Register typed intake exception handlers**

Map:

```python
IntakeNotFound -> 404 intake_not_found
IntakeIdempotencyConflict -> 409 idempotency_conflict
IntakeStateConflict -> 409 intake_state_conflict
IntakeVersionConflict -> 409 intake_version_conflict
IntakeUploadInvalid -> 400 invalid_upload
IntakePacketTooLarge -> 413 upload_too_large
IntakeValidationFailed -> 422 intake_validation_failed
IntakeStoreUnavailable -> 503 intake_store_unavailable
IntakeProcessingFailed -> 500 intake_processing_failed
```

Messages are fixed public strings and never `str(exc)` for store, parser, or
processing exceptions.

- [ ] **Step 5: Add API routes**

Use `Form` and `UploadFile`:

```python
@app.post("/api/intakes", response_model=IntakeAccepted, status_code=202)
async def create_intake(
    request_id: Annotated[str, Form()],
    notice: Annotated[UploadFile, File()],
    inventory: Annotated[UploadFile, File()],
    shelf_photo: Annotated[UploadFile | None, File()] = None,
    service: IntakeService = Depends(get_intake_service),
) -> IntakeAccepted:
```

Pass each `UploadFile.file` spooled stream into `CreateIntakeCommand`. Validate
the UUID with `IntakeCreateRequest` before service invocation.

Add:

```text
GET   /api/intakes/{intake_id}
PATCH /api/intakes/{intake_id}/draft
POST  /api/intakes/{intake_id}/confirm
POST  /api/intakes/{intake_id}/runs
```

The run endpoint remains state-gated and is completed after Task 9 adds the
resolved run boundary.

- [ ] **Step 6: Test startup degradation and structured errors**

Add a repository whose `initialize()` raises `IntakeStoreUnavailable`. Confirm
the app starts, `/health` remains 200, and intake endpoints return sanitized
503 without the underlying path or SQL message.

- [ ] **Step 7: Run intake and existing API suites**

```bash
cd services/api
uv run pytest tests/test_intake_api.py tests/test_api.py \
  tests/test_inspection_api.py tests/test_orchestration_api.py -q
```

Expected: new lifecycle endpoints and existing public endpoints pass.

- [ ] **Step 8: Commit and push the HTTP lifecycle**

```bash
git add services/api/src/batchhelm_api/app.py \
  services/api/tests/conftest.py \
  services/api/tests/test_intake_api.py
git commit -m "feat(api): expose durable incident intake endpoints"
git push origin main
```

---

### Task 9: Launch And Recover Arbitrary Incidents With Real Shelf Evidence

**Files:**
- Modify: `services/api/src/batchhelm_api/orchestration_service.py`
- Modify: `services/api/src/batchhelm_api/agents/orchestrator.py`
- Modify: `services/api/src/batchhelm_api/agents/inventory.py`
- Modify: `services/api/src/batchhelm_api/app.py`
- Modify: `services/api/tests/test_orchestration_service.py`
- Modify: `services/api/tests/test_orchestrator.py`
- Modify: `services/api/tests/test_orchestration_api.py`
- Expand: `services/api/tests/test_intake_api.py`

- [ ] **Step 1: Write failing arbitrary-input recovery tests**

Change service tests to pass `ResolvedRunInput`:

```python
@pytest.mark.asyncio
async def test_start_passes_real_shelf_artifact_to_orchestrator(tmp_path: Path) -> None:
    captured: list[tuple[bytes | None, str | None, str | None]] = []
    service = service_with_capturing_orchestrator(tmp_path, captured)
    run_input = ResolvedRunInput(
        incident=build_custom_incident(),
        shelf_artifact=shelf_artifact(),
        shelf_image_bytes=PNG,
        shelf_image_media_type="image/png",
    )
    accepted = await service.start(run_input, request_id="request-1")
    await service.wait_for_result(accepted.run_id)
    assert captured == [(PNG, "image/png", "shelf.png")]


@pytest.mark.asyncio
async def test_restart_resolves_non_demo_incident_by_id(tmp_path: Path) -> None:
    repository = running_repository(tmp_path, incident_id="incident-custom")
    service = make_service(repository)
    calls: list[str] = []

    def resolver(incident_id: str) -> ResolvedRunInput | None:
        calls.append(incident_id)
        return custom_run_input() if incident_id == "incident-custom" else None

    await service.recover(resolver)
    await service.wait_for_result("run-1")
    assert calls == ["incident-custom"]
```

- [ ] **Step 2: Run service tests and verify RED**

```bash
cd services/api
uv run pytest tests/test_orchestration_service.py tests/test_orchestrator.py -q
```

Expected: signature/type failures because the service accepts only
`RecallIncidentInput`.

- [ ] **Step 3: Migrate orchestration service to `ResolvedRunInput`**

Define:

```python
RunInputResolver = Callable[[str], ResolvedRunInput | None]
```

Change:

```python
async def start(
    self,
    run_input: ResolvedRunInput,
    *,
    request_id: str,
) -> OrchestrationRunAccepted:
```

Create the run using `run_input.incident.id`, and pass the complete input to
`_ensure_worker`.

Change recovery:

```python
async def recover(self, resolver: RunInputResolver) -> None:
    for run in self.repository.list_recoverable():
        run_input = resolver(run.incident_id)
        if run_input is None:
            self.repository.fail_run(
                run.id,
                code="incident_unavailable",
                message="The incident for this run is unavailable.",
            )
            await self._notify(run.id)
            continue
        await self._ensure_worker(run.id, run_input)
```

Change `_execute`:

```python
result = await orchestrator.run(
    run_input.incident,
    run_id=run_id,
    persist_event=self._persist_event,
    initial_sequence=initial_sequence,
    checkpoint_sink=lambda value: self.repository.save_checkpoint(run_id, value),
    recovery=checkpoint,
    shelf_image_bytes=run_input.shelf_image_bytes,
    shelf_image_media_type=run_input.shelf_image_media_type,
    shelf_upload=run_input.shelf_artifact,
)
```

- [ ] **Step 4: Carry shelf upload metadata through the orchestrator**

Add to `Orchestrator.run`:

```python
shelf_upload: IntakeArtifact | None = None,
```

When shelf bytes exist:

```python
ctx.blackboard["shelf_image_bytes"] = shelf_image_bytes
ctx.blackboard["shelf_image_media_type"] = shelf_image_media_type or "image/png"
if shelf_upload is not None:
    ctx.blackboard["shelf_upload"] = UploadMetadata(
        id=shelf_upload.id,
        original_filename=shelf_upload.original_filename,
        stored_filename=shelf_upload.stored_filename,
        media_type=shelf_upload.media_type,
        size_bytes=shelf_upload.size_bytes,
        path=shelf_upload.relative_path,
    )
```

Do not serialize image bytes into wave checkpoints. On recovery the resolver
re-injects them before skipped/completed waves continue.

- [ ] **Step 5: Complete intake run endpoint**

`POST /api/intakes/{intake_id}/runs`:

1. resolve confirmed run input;
2. call `orchestration_service.start(run_input, request_id)`;
3. link accepted run ID to the intake idempotently;
4. return `IntakeRunAccepted`.

Update every demo service call:

```python
ResolvedRunInput(incident=build_demo_incident())
```

Update app startup resolver:

```python
def resolve_run_input(incident_id: str) -> ResolvedRunInput | None:
    if incident_id == build_demo_incident().id:
        return ResolvedRunInput(incident=build_demo_incident())
    return intake_service.resolve_run_input(incident_id)
```

- [ ] **Step 6: Add restart test proving no demo image substitution**

Persist an intake-backed run after wave 2, restart the service with a resolver
that loads the real shelf artifact, and assert the final Shelf Vision result
contains the uploaded original filename and neutral fallback behavior when
Qwen is unconfigured.

- [ ] **Step 7: Run all orchestration and intake API tests**

```bash
cd services/api
uv run pytest tests/test_orchestration_service.py \
  tests/test_orchestrator.py tests/test_orchestration_api.py \
  tests/test_intake_service.py tests/test_intake_api.py -q
```

Expected: demo and intake-backed start, replay, checkpoint, and restart tests
all pass.

- [ ] **Step 8: Commit and push arbitrary run recovery**

```bash
git add services/api/src/batchhelm_api/orchestration_service.py \
  services/api/src/batchhelm_api/agents/orchestrator.py \
  services/api/src/batchhelm_api/agents/inventory.py \
  services/api/src/batchhelm_api/app.py \
  services/api/tests/test_orchestration_service.py \
  services/api/tests/test_orchestrator.py \
  services/api/tests/test_orchestration_api.py \
  services/api/tests/test_intake_api.py
git commit -m "feat(agents): run confirmed intake evidence durably"
git push origin main
```

---

### Task 10: Build The Frontend Intake State And HTTP Client

**Files:**
- Modify: `apps/web/src/api.ts`
- Create: `apps/web/src/intakeSession.ts`
- Create: `apps/web/src/intakeSession.test.ts`
- Create: `apps/web/src/useIntakeWorkspace.ts`
- Create: `apps/web/src/useIntakeWorkspace.test.tsx`
- Modify: `apps/web/src/useOrchestrationRun.ts`
- Modify: `apps/web/src/useOrchestrationRun.test.tsx`

- [ ] **Step 1: Add failing reducer tests**

Create:

```typescript
import { describe, expect, it } from "vitest";
import {
  initialIntakeSession,
  intakeSessionReducer,
} from "./intakeSession";

describe("intakeSessionReducer", () => {
  it("moves from files to review only for a reviewable persisted intake", () => {
    const state = intakeSessionReducer(initialIntakeSession, {
      type: "received",
      intake: intakeView({ status: "review_required", version: 1 }),
    });
    expect(state.stage).toBe("review");
    expect(state.serverVersion).toBe(1);
  });

  it("ignores stale poll responses", () => {
    const current = {
      ...initialIntakeSession,
      view: intakeView({ status: "review_required", version: 3 }),
      serverVersion: 3,
    };
    const state = intakeSessionReducer(current, {
      type: "received",
      intake: intakeView({ status: "extracting", version: 2 }),
    });
    expect(state.serverVersion).toBe(3);
    expect(state.view?.status).toBe("review_required");
  });

  it("marks locally edited criteria as dirty", () => {
    const state = intakeSessionReducer(reviewSession(), {
      type: "edit-criteria",
      field: "product_name",
      value: "Corrected Spinach",
    });
    expect(state.dirtyFields).toContain("criteria.product_name");
  });
});
```

- [ ] **Step 2: Run reducer tests and verify RED**

```bash
cd apps/web
npm test -- intakeSession.test.ts
```

Expected: module import failure.

- [ ] **Step 3: Add TypeScript API contracts**

Mirror backend enums and views in `api.ts`:

```typescript
export type IntakeStatus =
  | "uploaded"
  | "extracting"
  | "review_required"
  | "ready"
  | "run_started"
  | "failed";

export interface RecallCriteriaDraft {
  product_name: string;
  affected_lots: string[];
  upcs: string[];
  risk_level: "low" | "medium" | "high" | "critical" | null;
  reason: string;
  source: string;
}

export interface IntakeView {
  intake_id: string;
  status: IntakeStatus;
  version: number;
  provider_mode: string;
  created_at: string;
  updated_at: string;
  artifacts: PublicIntakeArtifact[];
  draft: RecallIncidentDraft | null;
  evidence: IntakeFieldEvidence[];
  incident_id: string | null;
  run_id: string | null;
  error_code: string | null;
  error_message: string | null;
}
```

Add:

```typescript
createIntakePacket(
  requestId: string,
  notice: File,
  inventory: File,
  shelfPhoto?: File,
): Promise<IntakeAccepted>
fetchIntake(statusUrl: string): Promise<IntakeView>
updateIntakeDraft(intakeId: string, request: IntakeDraftUpdate): Promise<IntakeView>
confirmIntake(intakeId: string, request: IntakeConfirmRequest): Promise<IntakeView>
startIntakeRun(intakeId: string, requestId: string): Promise<IntakeRunAccepted>
```

`createIntakePacket` uses `FormData` and does not set a manual `Content-Type`
header. Change the existing shelf result contract to:

```typescript
recall_match: boolean | null;
```

- [ ] **Step 4: Implement intake reducer**

`IntakeStage` is `"files" | "processing" | "review" | "launch"`.

Define:

```typescript
export interface IntakeFiles {
  notice: File | null;
  inventory: File | null;
  shelfPhoto: File | null;
}

export interface UseIntakeWorkspaceOptions {
  onRunAccepted?: (accepted: OrchestrationRunAccepted) => void;
}
```

The reducer stores selected files outside serializable server state, tracks the
latest version, preserves local edits while a same-version poll arrives, and
clears dirty fields only after the server returns a newer version containing
the saved values.

Failed state exposes only the sanitized API message.

- [ ] **Step 5: Write failing hook lifecycle tests**

Mock API functions and fake timers:

```typescript
it("creates one intake and polls until review", async () => {
  const create = vi.spyOn(api, "createIntakePacket").mockResolvedValue(accepted);
  vi.spyOn(api, "fetchIntake")
    .mockResolvedValueOnce(intakeView({ status: "extracting", version: 0 }))
    .mockResolvedValueOnce(intakeView({ status: "review_required", version: 1 }));

  const { result } = renderHook(() => useIntakeWorkspace());
  act(() => result.current.selectFiles(files));
  await act(() => result.current.processFiles());
  await vi.advanceTimersByTimeAsync(800);

  expect(create).toHaveBeenCalledTimes(1);
  await waitFor(() => expect(result.current.session.stage).toBe("review"));
});

it("closing the workspace stops polling without cancelling the intake", async () => {
  const fetch = vi.spyOn(api, "fetchIntake").mockResolvedValue(
    intakeView({ status: "extracting", version: 0 }),
  );
  const { result } = renderHook(() => useIntakeWorkspace());
  await startProcessing(result);
  act(() => result.current.close());
  await vi.advanceTimersByTimeAsync(1600);
  expect(fetch).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 6: Implement `useIntakeWorkspace`**

Use one `AbortController` per active poll request and a 750 ms timeout between
polls. Do not use `setInterval`.

Expose:

```typescript
{
  isOpen,
  session,
  open,
  close,
  selectFiles,
  processFiles,
  editCriteria,
  saveDraft,
  confirm,
  launch,
  reset,
}
```

Guard each command with an in-flight ref so React Strict Mode and double clicks
cannot create duplicates. Generate one UUID per logical command and reuse it
until that command settles.

- [ ] **Step 7: Add failing orchestration adoption test**

```typescript
it("adopts an intake run without starting a demo run", async () => {
  const start = vi.spyOn(api, "startDemoRun").mockResolvedValue(demoAccepted);
  const { result } = renderHook(() => useOrchestrationRun());
  await waitFor(() => expect(start).toHaveBeenCalledTimes(1));

  act(() => result.current.adoptRun(intakeAccepted));
  await waitFor(() => {
    expect(MockEventSource.instances.at(-1)?.url).toContain(
      intakeAccepted.run_id,
    );
  });
  expect(start).toHaveBeenCalledTimes(1);
});
```

Implement `adoptRun(accepted)` by writing the accepted run to the existing
session-storage key and incrementing the hook generation. Effect cleanup closes
the prior event source; the next effect restores the adopted run instead of
calling `startDemoRun`.

- [ ] **Step 8: Run frontend state tests and typecheck**

```bash
cd apps/web
npm test -- intakeSession.test.ts useIntakeWorkspace.test.tsx \
  useOrchestrationRun.test.tsx
npm run typecheck
```

Expected: reducer, lifecycle, Strict Mode, polling, and run-adoption tests pass.

- [ ] **Step 9: Commit and push frontend lifecycle**

```bash
git add apps/web/src/api.ts \
  apps/web/src/intakeSession.ts \
  apps/web/src/intakeSession.test.ts \
  apps/web/src/useIntakeWorkspace.ts \
  apps/web/src/useIntakeWorkspace.test.tsx \
  apps/web/src/useOrchestrationRun.ts \
  apps/web/src/useOrchestrationRun.test.tsx
git commit -m "feat(web): coordinate durable intake sessions"
git push origin main
```

---

### Task 11: Build The Files, Review, And Launch Workspace

**Files:**
- Create: `apps/web/src/IntakeWorkspace.tsx`
- Create: `apps/web/src/IntakeWorkspace.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/styles.css`

- [ ] **Step 1: Write failing component behavior tests**

Test accessible stage navigation and launch:

```typescript
import { fireEvent, render, screen } from "@testing-library/react";

it("requires notice and inventory before processing", () => {
  render(<IntakeWorkspace controller={filesController()} />);
  const button = screen.getByRole("button", {
    name: "Process files",
  }) as HTMLButtonElement;
  expect(button.disabled).toBe(true);
});

it("shows provenance and editable extracted criteria", () => {
  render(<IntakeWorkspace controller={reviewController()} />);
  const product = screen.getByLabelText("Product name") as HTMLInputElement;
  expect(product.value).toBe("Spinach 10 oz");
  expect(screen.getByText("notice.pdf · page 1")).toBeTruthy();
  expect(screen.getByText("96% confidence")).toBeTruthy();
});

it("launches the confirmed run and closes the workspace", async () => {
  const controller = launchController();
  render(<IntakeWorkspace controller={controller} />);
  fireEvent.click(
    screen.getByRole("button", {
      name: "Confirm and run agents",
    }),
  );
  expect(controller.launch).toHaveBeenCalledTimes(1);
});
```

- [ ] **Step 2: Run component tests and verify RED**

```bash
cd apps/web
npm test -- IntakeWorkspace.test.tsx
```

Expected: module import failure.

- [ ] **Step 3: Implement the workspace structure**

`IntakeWorkspace` renders only when open:

```tsx
export type IntakeWorkspaceController = ReturnType<
  typeof useIntakeWorkspace
>;

interface IntakeWorkspaceProps {
  controller: IntakeWorkspaceController;
}

<div className="intake-backdrop">
  <section
    className="intake-workspace"
    role="dialog"
    aria-modal="true"
    aria-labelledby="intake-title"
  >
    <header className="intake-header">
      <div>
        <p className="eyebrow">Incident intake</p>
        <h2 id="intake-title">New recall</h2>
      </div>
      <button type="button" className="icon-button" aria-label="Close intake">
        <X />
      </button>
    </header>
    <nav className="intake-stages" aria-label="Intake stages">
      <span aria-current={stage === "files" ? "step" : undefined}>Files</span>
      <span aria-current={stage === "review" ? "step" : undefined}>Review</span>
      <span aria-current={stage === "launch" ? "step" : undefined}>Launch</span>
    </nav>
    <div className="intake-content">{stageContent}</div>
    <footer className="intake-actions">{stageActions}</footer>
  </section>
</div>
```

Use Lucide icons `FilePlus2`, `FileText`, `Table2`, `Image`, `X`,
`ChevronLeft`, `ShieldCheck`, `LoaderCircle`, `AlertTriangle`, and
`Rocket`.

The stages are status indicators, not freely clickable tabs; navigation uses
Back and primary command buttons so confirmation cannot be bypassed.

- [ ] **Step 4: Implement Files stage**

Three file controls:

- notice accepts PDF, text, JPEG, PNG, WebP;
- inventory accepts CSV;
- shelf accepts JPEG, PNG, WebP and is marked optional.

Show selected metadata, client-side size errors, and a processing summary. Use
native file inputs hidden behind accessible labels, not drag-only behavior.

- [ ] **Step 5: Implement Review stage**

Render:

- editable product, lot list, UPC list, risk select, reason, and source;
- source/confidence line beneath every field;
- inventory import metrics;
- bounded first-10-row table;
- warning list;
- optional shelf result with `Match`, `No match`, or `Unknown`;
- Save corrections command;
- Continue command disabled while dirty or invalid.

Lot and UPC inputs use comma-separated display and normalize to trimmed unique
arrays on change.

- [ ] **Step 6: Implement Launch stage**

Show immutable summary, provider mode, store and row counts, shelf evidence,
and unresolved non-blocking warnings. The primary command is exactly
`Confirm and run agents`; loading text is `Starting agent workflow`.

If confirmation and launch are separate HTTP calls, the controller performs
them sequentially under the same user action and exposes which phase failed.
A confirmed intake can retry launch without creating a new snapshot.

- [ ] **Step 7: Integrate with App**

In `App`:

```typescript
const orchestrationController = useOrchestrationRun();
const intakeController = useIntakeWorkspace({
  onRunAccepted: orchestrationController.adoptRun,
});
```

Add `New recall` as a command in the incident action area, using
`FilePlus2`. Do not add a landing page.

Render `IntakeWorkspace` once at app-shell level so the dialog is not nested
inside a dashboard panel.

- [ ] **Step 8: Add responsive design-system CSS**

Use:

```css
.intake-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: stretch end;
  background: rgb(13 31 38 / 48%);
}

.intake-workspace {
  width: min(960px, calc(100vw - 72px));
  height: 100dvh;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  background: var(--surface);
  border-left: 1px solid var(--border);
}

.intake-content {
  min-height: 0;
  overflow: auto;
  padding: 20px 24px;
}

.intake-review-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.9fr) minmax(420px, 1.1fr);
  gap: 20px;
}

@media (max-width: 760px) {
  .intake-workspace {
    width: 100vw;
  }

  .intake-review-grid {
    grid-template-columns: 1fr;
  }
}
```

Use existing color variables. Cards remain at 8 px radius or less. Ensure the
fixed action footer does not cover scrollable content.

- [ ] **Step 9: Run component, lifecycle, type, and build checks**

```bash
cd apps/web
npm test
npm run typecheck
npm run build
```

Expected: all frontend tests pass and Vite produces the production bundle.

- [ ] **Step 10: Commit and push the intake workspace**

```bash
git add apps/web/src/IntakeWorkspace.tsx \
  apps/web/src/IntakeWorkspace.test.tsx \
  apps/web/src/App.tsx apps/web/src/styles.css
git commit -m "feat(web): add reviewed recall intake workspace"
git push origin main
```

---

### Task 12: Add Demonstration Fixtures And Deployment Configuration

**Files:**
- Create: `sample-data/recall-notice-spinach.pdf`
- Create: `sample-data/inventory-spinach.csv`
- Create: `sample-data/inventory-spinach-invalid.csv`
- Create: `sample-data/store-b-cooler-spinach.png`
- Modify: `sample-data/README.md`
- Modify: `.env.example`
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Test: `services/api/tests/test_intake_api.py`

- [ ] **Step 1: Create exact CSV fixtures**

`sample-data/inventory-spinach.csv`:

```csv
Store Name,Item SKU,Product Name,Lot Code,UPC,Qty,Location,Supplier
Store A,SPN10Z,Spinach 10 oz,L2418,008500001010,6,Back Room 1,CF Baby Spinach 10OZ
Store A,SPN10Z,Spinach 10 oz,L2419,008500001010,4,Back Room 1,CF Baby Spinach 10OZ
Store A,SPN10Z,Spinach 10 oz,L2420,008500001010,3,Cooler A,Central Farms Greens 10OZ
Store B,SPN10Z,Spinach 10 oz,L2418,008500001010,5,Back Room 2,CF Baby Spinach 10OZ
Store B,SPN10Z,Spinach 10 oz,L2421,008500001010,2,Cooler B,Central Farms Greens 10OZ
Store B,SPN10Z,Spinach 10 oz,L2422,008500001010,3,Back Room 2,CF Baby Spinach 10OZ
```

`sample-data/inventory-spinach-invalid.csv` adds one negative quantity and one
duplicate identity after the valid rows so the review UI shows two warnings.

- [ ] **Step 2: Create the recall PDF**

Use the PDF skill to create a one-page, letter-sized supplier notice containing
exactly:

```text
CENTRAL FARMS SUPPLIER RECALL ALERT
Reference: CF-2026-06-18

Product: Spinach 10 oz clamshell
Affected lots: L2418, L2419, L2420, L2421, L2422
UPC: 008500001010
Risk: Possible contamination

Remove affected product from sale immediately. Quarantine all matching units
and hold them for supplier disposition instructions.
```

Render and inspect the PDF. Confirm text extraction reproduces every product,
lot, UPC, risk, and reference value.

- [ ] **Step 3: Create the shelf-photo fixture**

Use the image generation tool to create a realistic grocery cooler photo with a
single inspectable spinach clamshell in the foreground. The label must visibly
show `Spinach 10 oz`, `L2418`, and `008500001010`. Inspect the generated image
at original resolution; regenerate or edit until all three strings are legible.

- [ ] **Step 4: Test the committed sample packet**

Add:

```python
def test_sample_packet_reaches_review_and_matches_demo_totals(
    client: TestClient,
) -> None:
    response = upload_sample_packet(client)
    assert response.status_code == 202
    view = wait_for_intake(client, response.json()["status_url"])
    assert view["draft"]["import_summary"]["accepted_rows"] == 6
    assert sum(row["on_hand"] for row in view["draft"]["inventory"]) == 23
    assert view["draft"]["criteria"]["affected_lots"] == [
        "L2418",
        "L2419",
        "L2420",
        "L2421",
        "L2422",
    ]
```

- [ ] **Step 5: Add persistent intake configuration**

`.env.example`:

```dotenv
INTAKE_DATABASE_PATH=./data/intake.db
```

`Dockerfile`:

```dockerfile
INTAKE_DATABASE_PATH=/data/intake.db \
```

`docker-compose.yml` API environment:

```yaml
INTAKE_DATABASE_PATH: /data/intake.db
```

Uploads already use `/data/uploads`.

- [ ] **Step 6: Document fixture use**

In `sample-data/README.md`, list each file, expected totals, and the browser
sequence. State that fixtures were created for BatchHelm and are covered by the
repository MIT license.

- [ ] **Step 7: Run sample and full backend suites**

```bash
cd services/api
uv run pytest tests/test_intake_api.py -q
uv run pytest -q
```

Expected: sample packet test and complete backend suite pass.

- [ ] **Step 8: Commit and push fixtures and deployment config**

```bash
git add sample-data .env.example Dockerfile docker-compose.yml \
  services/api/tests/test_intake_api.py
git commit -m "test: add real incident intake packet"
git push origin main
```

---

### Task 13: Update Public Documentation And Submission Evidence

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/demo-script.md`
- Modify: `docs/deployment-alibaba-cloud.md`
- Modify: `docs/known-limitations.md`
- Modify: `docs/qwen-integration.md`
- Modify: `docs/submission-checklist.md`

- [ ] **Step 1: Update public product claims**

Document:

- real packet intake formats and limits;
- Files -> Review -> Launch workflow;
- field provenance and reviewer overrides;
- intake SQLite repository and artifact paths;
- intake API endpoints;
- arbitrary incident restart recovery;
- neutral real-image fallback;
- single-process lifecycle scope.

Remove the `single bundled incident` limitation. Keep multi-incident queueing,
email mailbox ingestion, auth, Postgres, distributed rate limiting, and
multi-replica workers as limitations.

Correct the README's `Markdown/PDF evidence packet` wording unless a real PDF
evidence export exists by this checkpoint.

- [ ] **Step 2: Update architecture diagram**

Show:

```text
Files -> IntakeService -> SQLite Intake Store
IntakeService -> Notice/CSV Parsers
IntakeService -> Qwen Text/Vision
Reviewer -> Confirmed Incident Snapshot
Confirmed Snapshot -> OrchestrationService -> Agent DAG
Intake Artifact Store -> Shelf Vision Agent
```

The diagram must keep review ledger, memory store, and run/event store as
separate persistence responsibilities.

- [ ] **Step 3: Update demo script**

Replace the bundled-input opening with:

1. upload the sample packet;
2. show extraction progress;
3. correct one low-confidence field;
4. show field provenance and inventory warnings;
5. confirm and launch;
6. show real shelf evidence in Mission Control;
7. refresh to show durable replay;
8. show review gate and evidence packet.

Keep the final recording under three minutes and require live Qwen mode.

- [ ] **Step 4: Correct submission checklist state**

Mark durable Mission Control as pushed. Mark real ambiguous intake complete
only after browser verification. Keep Alibaba deployment, live URL, live Qwen
proof, deck overhaul, video, Devpost track selection, and final submission
unchecked.

- [ ] **Step 5: Run documentation integrity checks**

```bash
./scripts/check-attribution.sh
git diff --check
rg -n "single bundled incident|AI Showrunner|Markdown/PDF evidence" \
  README.md docs --glob '!docs/superpowers/**'
```

Expected: attribution and whitespace pass; stale public claims return no
matches.

- [ ] **Step 6: Commit and push public documentation**

```bash
git add README.md docs/architecture.md docs/demo-script.md \
  docs/deployment-alibaba-cloud.md docs/known-limitations.md \
  docs/qwen-integration.md docs/submission-checklist.md
git commit -m "docs: document real-world incident intake"
git push origin main
```

---

### Task 14: Run Browser QA, Capture Evidence, And Close The Milestone

**Files:**
- Create: `docs/design-assets/screenshots/intake-files-desktop.png`
- Create: `docs/design-assets/screenshots/intake-review-desktop.png`
- Create: `docs/design-assets/screenshots/intake-review-mobile.png`
- Modify: `README.md`
- Modify: `docs/submission-checklist.md`

- [ ] **Step 1: Run complete automated verification**

```bash
cd services/api
uv run pytest -q

cd ../../apps/web
npm test
npm run typecheck
npm run build

cd ../..
./scripts/check-attribution.sh
git diff --check
```

Expected:

- all backend tests pass;
- all frontend tests pass;
- typecheck and production build pass;
- attribution scan passes;
- whitespace check is silent.

- [ ] **Step 2: Run container verification**

```bash
docker compose config --quiet
docker build -t batchhelm-api:intake .
docker build -t batchhelm-web:intake apps/web
```

If Docker is unavailable locally, require the pushed GitHub Actions Docker job
to pass before this milestone is closed.

- [ ] **Step 3: Start the application**

```bash
cd services/api
uv run uvicorn batchhelm_api.app:app --host 127.0.0.1 --port 8000
```

```bash
cd apps/web
npm run dev -- --host 127.0.0.1 --port 5173
```

- [ ] **Step 4: Verify desktop flow at 1280 x 720**

Confirm:

- New Recall opens one workspace;
- required files gate Process files;
- one POST creates one intake;
- extraction progresses to Review;
- provenance, confidence, warning counts, and inventory preview render;
- manual correction persists one new version;
- stale version returns a visible conflict without data loss;
- confirm and launch create one run;
- dashboard and Mission Control use the uploaded incident;
- Shelf Vision names the uploaded photo and does not infer a positive match in
  fallback mode;
- refresh reconnects without duplicate intake, run, or events;
- no overflow, overlap, blank region, or console error.

- [ ] **Step 5: Verify mobile flow at 390 x 844**

Confirm:

- workspace uses full width;
- stages, fields, file names, and commands fit;
- footer does not cover content;
- inventory table scrolls within its region;
- long lots, UPCs, and warnings wrap;
- no horizontal document overflow;
- correction, confirmation, and launch remain keyboard accessible.

- [ ] **Step 6: Capture screenshots**

Save populated PNG evidence:

```text
docs/design-assets/screenshots/intake-files-desktop.png
docs/design-assets/screenshots/intake-review-desktop.png
docs/design-assets/screenshots/intake-review-mobile.png
```

The review screenshots must show provenance, confidence, inventory summary,
and at least one warning or reviewer-required field.

- [ ] **Step 7: Verify restart behavior manually**

During extraction, stop and restart the API; confirm the same intake reaches
Review. After launch and before the final wave, restart again; confirm the same
run ID resumes from its last wave and uses the intake snapshot and shelf
artifact.

- [ ] **Step 8: Update screenshot references and checklist**

Add screenshot links to README and mark real ambiguous intake complete in the
submission checklist. Do not mark live Qwen or Alibaba deployment complete
from fallback/local evidence.

- [ ] **Step 9: Commit, push, and verify authorship**

```bash
git add docs/design-assets/screenshots README.md docs/submission-checklist.md
git commit -m "docs: capture durable intake workflow"
git push origin main
git log --format='%an <%ae> | %cn <%ce>' -15
```

Expected: every displayed author and committer is Ankit Ranjan.

- [ ] **Step 10: Verify remote CI**

Open the latest GitHub Actions run and require success for:

- backend pytest;
- frontend typecheck/build/tests;
- attribution scan;
- API and frontend Docker builds.

---

## Completion Gate

Do not call the milestone complete until current evidence proves every item:

- [ ] One request ID creates one durable intake.
- [ ] Restart preserves artifacts, draft, evidence, corrections, and status.
- [ ] Plain text, text PDF, scanned PDF, image notice, and CSV paths work.
- [ ] Arbitrary fallback extraction never copies demo safety criteria.
- [ ] Real-image provider failure cannot produce a fabricated positive match.
- [ ] Every confirmed safety-critical field has extraction or reviewer provenance.
- [ ] Stale reviewer versions cannot overwrite newer corrections.
- [ ] Intake cannot launch before confirmation.
- [ ] Confirmation creates an immutable valid incident snapshot.
- [ ] One launch request creates one durable orchestration run.
- [ ] Restart resolves the same incident and optional shelf artifact.
- [ ] Shelf Vision does not use the demo image for intake-backed runs.
- [ ] Existing demo, event replay, retries, memory, review, and wave recovery pass.
- [ ] Backend, frontend, attribution, and Docker CI checks pass.
- [ ] Desktop and mobile end-to-end verification pass.
- [ ] Public documentation distinguishes real intake from bundled demo behavior.
