# BatchHelm Durable Review Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist evidence-packet review decisions in an append-only SQLite ledger so review state and audit history survive refreshes and API restarts.

**Architecture:** Evidence packets receive a timestamp-independent SHA-256 content version. A typed repository protocol isolates SQLite, while a review application service reconstructs state by folding ordered immutable decisions through the pure review projector. FastAPI injects the service and translates repository failures into sanitized API responses.

**Tech Stack:** Python 3.11, FastAPI, Pydantic 2, standard-library `sqlite3`, pytest, React 18, TypeScript, Vite

---

**Design spec:** `docs/superpowers/specs/2026-06-27-batchhelm-durable-review-persistence-design.md`

**Git constraint:** Do not stage, commit, or push during execution until the user
explicitly reopens GitHub work. The local-checkpoint steps below replace the
usual commit steps.

## File Structure

- Modify `services/api/src/batchhelm_api/models.py`
  - Adds `EvidencePacket.packet_version` and `ReviewDecisionRequest.request_id`.
- Modify `services/api/src/batchhelm_api/evidence_packet.py`
  - Computes the stable content-derived packet version.
- Create `services/api/src/batchhelm_api/review_repository.py`
  - Owns immutable records, repository protocol, SQLite schema, transactions,
    idempotency, and sanitized persistence exceptions.
- Modify `services/api/src/batchhelm_api/review_trail.py`
  - Applies persisted decisions to an existing review state without storage
    dependencies.
- Create `services/api/src/batchhelm_api/review_service.py`
  - Coordinates repository reads/writes and chronological state reconstruction.
- Modify `services/api/src/batchhelm_api/config.py`
  - Adds `DATABASE_PATH`.
- Modify `services/api/src/batchhelm_api/app.py`
  - Initializes and injects the repository-backed service and maps errors.
- Modify `services/api/tests/test_evidence_packet.py`
  - Verifies stable and content-sensitive packet versions.
- Create `services/api/tests/test_review_repository.py`
  - Verifies schema migration, restart durability, ordering, concurrency, and
    idempotency.
- Create `services/api/tests/test_review_service.py`
  - Verifies complete audit folding and latest-decision readiness.
- Modify `services/api/tests/test_review_trail.py`
  - Verifies API restart persistence, stable audit time, retries, conflicts,
    and storage errors.
- Modify `apps/web/src/types.ts`
  - Mirrors `packet_version`.
- Modify `apps/web/src/api.ts`
  - Sends one UUID request ID per review action.
- Modify `.env.example`
  - Replaces the unused `DATABASE_URL` with `DATABASE_PATH`.
- Modify `README.md`
  - Documents durable review behavior and the restart demo.
- Modify `docs/architecture.md`
  - Documents the repository boundary, ledger, and packet version.

## Task 1: Stable Evidence Packet Version

**Files:**
- Modify: `services/api/tests/test_evidence_packet.py`
- Modify: `services/api/src/batchhelm_api/models.py:243-248`
- Modify: `services/api/src/batchhelm_api/evidence_packet.py:1-78`

- [x] **Step 1: Write failing stability and content-change tests**

Add imports and these tests to `services/api/tests/test_evidence_packet.py`:

```python
def test_packet_version_ignores_generation_timestamp() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    inspection = build_demo_shelf_inspection()

    first = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=inspection,
        generated_at=datetime(2026, 6, 26, 10, 30, tzinfo=timezone.utc),
    )
    second = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=inspection,
        generated_at=datetime(2026, 6, 27, 18, 45, tzinfo=timezone.utc),
    )

    assert first.generated_at != second.generated_at
    assert first.packet_version == second.packet_version
    assert first.packet_version.startswith("sha256:")


def test_packet_version_changes_when_evidence_changes() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    inspection = build_demo_shelf_inspection()
    changed_inspection = inspection.model_copy(
        update={"evidence_note": "A second shelf image confirmed the lot code."}
    )

    first = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=inspection,
    )
    changed = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=changed_inspection,
    )

    assert first.packet_version != changed.packet_version
```

- [x] **Step 2: Run the tests and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_evidence_packet.py::test_packet_version_ignores_generation_timestamp \
  tests/test_evidence_packet.py::test_packet_version_changes_when_evidence_changes \
  -q
```

Expected: FAIL because `EvidencePacket` has no `packet_version`.

- [x] **Step 3: Add the packet field and canonical digest**

Add `packet_version: str` to `EvidencePacket` in `models.py`.

In `evidence_packet.py`, import `hashlib` and `json`, then add:

```python
def _packet_version(
    *,
    incident_id: str,
    sections: list[EvidencePacketSection],
) -> str:
    canonical = json.dumps(
        {
            "incident_id": incident_id,
            "sections": [
                {"title": section.title, "body": section.body}
                for section in sections
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"
```

Set the field in `build_evidence_packet`:

```python
return EvidencePacket(
    incident_id=incident.id,
    packet_version=_packet_version(
        incident_id=incident.id,
        sections=sections,
    ),
    filename=f"batchhelm-{_slugify(incident.id)}-evidence.md",
    generated_at=generated_at_value,
    sections=sections,
    markdown=markdown,
)
```

- [x] **Step 4: Run the packet tests and verify GREEN**

Run: `cd services/api && uv run pytest tests/test_evidence_packet.py -q`

Expected: all evidence-packet tests PASS.

- [x] **Step 5: Record a local checkpoint**

Run: `git diff --check`

Expected: no whitespace errors. Do not stage or commit.

## Task 2: Append-Only SQLite Review Repository

**Files:**
- Create: `services/api/tests/test_review_repository.py`
- Create: `services/api/src/batchhelm_api/review_repository.py`

- [x] **Step 1: Write failing durability and ordering tests**

Create `services/api/tests/test_review_repository.py`:

```python
from pathlib import Path

from batchhelm_api.models import ReviewStatus
from batchhelm_api.review_repository import (
    ReviewDecisionRecord,
    SQLiteReviewRepository,
)


def make_record(
    *,
    decision_id: str,
    request_id: str,
    decision: ReviewStatus,
    decided_at: str,
    note: str,
) -> ReviewDecisionRecord:
    return ReviewDecisionRecord(
        decision_id=decision_id,
        request_id=request_id,
        incident_id="recall-spinach-2026-06",
        packet_version="sha256:packet-one",
        decision=decision,
        reviewer="Operations Manager",
        note=note,
        decided_at=decided_at,
    )


def test_sqlite_repository_survives_reinstantiation(tmp_path: Path) -> None:
    database_path = tmp_path / "batchhelm.db"
    first = SQLiteReviewRepository(database_path)
    first.initialize()
    first.append(
        make_record(
            decision_id="review-1",
            request_id="11111111-1111-4111-8111-111111111111",
            decision=ReviewStatus.approved,
            decided_at="2026-06-27T09:00:00+00:00",
            note="Approved for supplier submission.",
        )
    )

    restarted = SQLiteReviewRepository(database_path)
    restarted.initialize()
    records = restarted.list_for_packet(
        incident_id="recall-spinach-2026-06",
        packet_version="sha256:packet-one",
    )

    assert [record.decision_id for record in records] == ["review-1"]
    assert records[0].decision == ReviewStatus.approved


def test_sqlite_repository_returns_decisions_in_append_order(
    tmp_path: Path,
) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    repository.append(
        make_record(
            decision_id="review-1",
            request_id="11111111-1111-4111-8111-111111111111",
            decision=ReviewStatus.approved,
            decided_at="2026-06-27T09:00:00+00:00",
            note="Approved.",
        )
    )
    repository.append(
        make_record(
            decision_id="review-2",
            request_id="22222222-2222-4222-8222-222222222222",
            decision=ReviewStatus.needs_changes,
            decided_at="2026-06-27T09:05:00+00:00",
            note="Attach signed disposal records.",
        )
    )

    records = repository.list_for_packet(
        incident_id="recall-spinach-2026-06",
        packet_version="sha256:packet-one",
    )

    assert [record.decision_id for record in records] == ["review-1", "review-2"]
```

- [x] **Step 2: Run the repository tests and verify RED**

Run: `cd services/api && uv run pytest tests/test_review_repository.py -q`

Expected: collection ERROR because `batchhelm_api.review_repository` does not
exist.

- [x] **Step 3: Implement the repository models, schema, append, and read**

Create `services/api/src/batchhelm_api/review_repository.py`:

```python
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from batchhelm_api.models import ReviewStatus

SCHEMA_VERSION = 1


class ReviewStoreUnavailable(RuntimeError):
    pass


class ReviewIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class ReviewDecisionRecord:
    decision_id: str
    request_id: str
    incident_id: str
    packet_version: str
    decision: ReviewStatus
    reviewer: str
    note: str
    decided_at: str


class ReviewRepository(Protocol):
    def initialize(self) -> None: ...

    def append(self, record: ReviewDecisionRecord) -> ReviewDecisionRecord: ...

    def list_for_packet(
        self,
        *,
        incident_id: str,
        packet_version: str,
    ) -> list[ReviewDecisionRecord]: ...


class SQLiteReviewRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("PRAGMA journal_mode = WAL")
                    version = int(
                        connection.execute("PRAGMA user_version").fetchone()[0]
                    )
                    if version > SCHEMA_VERSION:
                        raise ReviewStoreUnavailable(
                            "Review database schema is newer than this service."
                        )
                    if version == 0:
                        connection.execute(
                            """
                            CREATE TABLE review_decisions (
                                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                                decision_id TEXT NOT NULL UNIQUE,
                                request_id TEXT NOT NULL UNIQUE,
                                incident_id TEXT NOT NULL,
                                packet_version TEXT NOT NULL,
                                decision TEXT NOT NULL CHECK (
                                    decision IN ('approved', 'needs-changes')
                                ),
                                reviewer TEXT NOT NULL,
                                note TEXT NOT NULL,
                                decided_at TEXT NOT NULL
                            )
                            """
                        )
                        connection.execute(
                            """
                            CREATE INDEX review_decisions_packet_sequence
                            ON review_decisions (
                                incident_id,
                                packet_version,
                                sequence
                            )
                            """
                        )
                        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except ReviewStoreUnavailable:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise ReviewStoreUnavailable(
                "Review history storage is unavailable."
            ) from exc

    def append(self, record: ReviewDecisionRecord) -> ReviewDecisionRecord:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO review_decisions (
                            decision_id,
                            request_id,
                            incident_id,
                            packet_version,
                            decision,
                            reviewer,
                            note,
                            decided_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.decision_id,
                            record.request_id,
                            record.incident_id,
                            record.packet_version,
                            record.decision.value,
                            record.reviewer,
                            record.note,
                            record.decided_at,
                        ),
                    )
                    return record
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise ReviewStoreUnavailable(
                "Review history storage is unavailable."
            ) from exc

    def list_for_packet(
        self,
        *,
        incident_id: str,
        packet_version: str,
    ) -> list[ReviewDecisionRecord]:
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM review_decisions
                    WHERE incident_id = ? AND packet_version = ?
                    ORDER BY sequence ASC
                    """,
                    (incident_id, packet_version),
                ).fetchall()
            return [_record_from_row(row) for row in rows]
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise ReviewStoreUnavailable(
                "Review history storage is unavailable."
            ) from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection


def _record_from_row(row: sqlite3.Row) -> ReviewDecisionRecord:
    return ReviewDecisionRecord(
        decision_id=str(row["decision_id"]),
        request_id=str(row["request_id"]),
        incident_id=str(row["incident_id"]),
        packet_version=str(row["packet_version"]),
        decision=ReviewStatus(str(row["decision"])),
        reviewer=str(row["reviewer"]),
        note=str(row["note"]),
        decided_at=str(row["decided_at"]),
    )


```

- [x] **Step 4: Run the durability tests and verify GREEN**

Run: `cd services/api && uv run pytest tests/test_review_repository.py -q`

Expected: 2 tests PASS.

- [x] **Step 5: Write failing idempotency tests**

Append to `test_review_repository.py`:

```python
import pytest

from batchhelm_api.review_repository import ReviewIdempotencyConflict


def test_identical_request_id_is_idempotent(tmp_path: Path) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    record = make_record(
        decision_id="review-1",
        request_id="11111111-1111-4111-8111-111111111111",
        decision=ReviewStatus.approved,
        decided_at="2026-06-27T09:00:00+00:00",
        note="Approved.",
    )

    first = repository.append(record)
    replay = repository.append(
        make_record(
            decision_id="review-retry",
            request_id=record.request_id,
            decision=record.decision,
            decided_at="2026-06-27T09:01:00+00:00",
            note=record.note,
        )
    )
    records = repository.list_for_packet(
        incident_id=record.incident_id,
        packet_version=record.packet_version,
    )

    assert replay == first
    assert len(records) == 1


def test_request_id_reuse_with_different_payload_conflicts(
    tmp_path: Path,
) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    record = make_record(
        decision_id="review-1",
        request_id="11111111-1111-4111-8111-111111111111",
        decision=ReviewStatus.approved,
        decided_at="2026-06-27T09:00:00+00:00",
        note="Approved.",
    )
    repository.append(record)

    with pytest.raises(ReviewIdempotencyConflict):
        repository.append(
            make_record(
                decision_id="review-2",
                request_id=record.request_id,
                decision=ReviewStatus.needs_changes,
                decided_at="2026-06-27T09:01:00+00:00",
                note="Attach disposal records.",
            )
        )
```

- [x] **Step 6: Run idempotency tests and verify RED**

Run: `cd services/api && uv run pytest tests/test_review_repository.py -q`

Expected: 2 tests FAIL because duplicate request IDs are currently translated
to `ReviewStoreUnavailable`.

- [x] **Step 7: Implement idempotent append and conflict detection**

Replace `SQLiteReviewRepository.append` with:

```python
def append(self, record: ReviewDecisionRecord) -> ReviewDecisionRecord:
    try:
        with closing(self._connect()) as connection:
            with connection:
                existing_row = connection.execute(
                    """
                    SELECT *
                    FROM review_decisions
                    WHERE request_id = ?
                    """,
                    (record.request_id,),
                ).fetchone()
                if existing_row is not None:
                    existing = _record_from_row(existing_row)
                    if _same_request(existing, record):
                        return existing
                    raise ReviewIdempotencyConflict(
                        "Request ID was already used for another review decision."
                    )

                connection.execute(
                    """
                    INSERT INTO review_decisions (
                        decision_id,
                        request_id,
                        incident_id,
                        packet_version,
                        decision,
                        reviewer,
                        note,
                        decided_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.decision_id,
                        record.request_id,
                        record.incident_id,
                        record.packet_version,
                        record.decision.value,
                        record.reviewer,
                        record.note,
                        record.decided_at,
                    ),
                )
                return record
    except ReviewIdempotencyConflict:
        raise
    except (sqlite3.Error, ValueError, KeyError) as exc:
        raise ReviewStoreUnavailable(
            "Review history storage is unavailable."
        ) from exc
```

Add:

```python
def _same_request(
    existing: ReviewDecisionRecord,
    candidate: ReviewDecisionRecord,
) -> bool:
    return (
        existing.request_id == candidate.request_id
        and existing.incident_id == candidate.incident_id
        and existing.packet_version == candidate.packet_version
        and existing.decision == candidate.decision
        and existing.reviewer == candidate.reviewer
        and existing.note == candidate.note
    )
```

- [x] **Step 8: Run repository tests and verify GREEN**

Run: `cd services/api && uv run pytest tests/test_review_repository.py -q`

Expected: all 4 repository tests PASS.

- [x] **Step 9: Record a local checkpoint**

Run: `git diff --check`

Expected: no whitespace errors. Do not stage or commit.

## Task 3: Review History Projection And Application Service

**Files:**
- Modify: `services/api/tests/test_review_trail.py`
- Create: `services/api/tests/test_review_service.py`
- Modify: `services/api/src/batchhelm_api/review_trail.py:39-111`
- Create: `services/api/src/batchhelm_api/review_service.py`

- [x] **Step 1: Rewrite the projector test for immutable event metadata**

Update `test_apply_review_decision_projects_approval_timeline`:

```python
def test_apply_review_decision_projects_approval_timeline() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )
    base_state = build_demo_review_state(
        incident=incident,
        analysis=analysis,
        packet=packet,
    )

    state = apply_review_decision(
        base_state=base_state,
        current_state=base_state,
        reviewer="Operations Manager",
        decision="approved",
        note="Approved for supplier submission.",
        decision_id="review-decision-1",
        decided_at="2026-06-27T09:00:00+00:00",
    )

    assert state.status == "approved"
    assert state.ready_to_submit is True
    assert state.blocker_count == 0
    assert state.timeline[-1].id == "review-decision-1"
    assert state.timeline[-1].at == "2026-06-27T09:00:00+00:00"
    assert state.timeline[-1].title == "Packet Approved"
```

- [x] **Step 2: Run the projector test and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_trail.py::test_apply_review_decision_projects_approval_timeline \
  -q
```

Expected: FAIL because `apply_review_decision` has the old signature.

- [x] **Step 3: Refactor the pure projector**

Replace the old `apply_review_decision` signature and state setup with:

```python
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
```

- [x] **Step 4: Run the projector tests and verify GREEN**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_trail.py::test_demo_review_state_marks_packet_not_ready_until_blockers_resolved \
  tests/test_review_trail.py::test_apply_review_decision_projects_approval_timeline \
  -q
```

Expected: both pure projector tests PASS. Do not run the decision-route test
until Task 4 updates the route to use `ReviewService`.

- [x] **Step 5: Write failing service history tests**

Create `services/api/tests/test_review_service.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.models import ReviewDecisionRequest
from batchhelm_api.review_repository import SQLiteReviewRepository
from batchhelm_api.review_service import ReviewService
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident


def packet_context():
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )
    return incident, analysis, packet


def test_service_reconstructs_full_history_and_latest_readiness(
    tmp_path: Path,
) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    timestamps = iter(
        [
            datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 6, 27, 9, 5, tzinfo=timezone.utc),
        ]
    )
    ids = iter(["review-1", "review-2"])
    service = ReviewService(
        repository,
        clock=lambda: next(timestamps),
        decision_id_factory=lambda: next(ids),
    )
    incident, analysis, packet = packet_context()

    service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=ReviewDecisionRequest(
            request_id="11111111-1111-4111-8111-111111111111",
            reviewer="Operations Manager",
            decision="approved",
            note="Approved for supplier submission.",
        ),
    )
    final = service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=ReviewDecisionRequest(
            request_id="22222222-2222-4222-8222-222222222222",
            reviewer="Operations Manager",
            decision="needs-changes",
            note="Attach signed disposal records.",
        ),
    )

    assert final.status == "needs-changes"
    assert final.ready_to_submit is False
    assert [event.id for event in final.timeline[-2:]] == ["review-1", "review-2"]


def test_changed_packet_version_starts_a_fresh_review(tmp_path: Path) -> None:
    repository = SQLiteReviewRepository(tmp_path / "batchhelm.db")
    repository.initialize()
    service = ReviewService(
        repository,
        clock=lambda: datetime(2026, 6, 27, 9, 0, tzinfo=timezone.utc),
        decision_id_factory=lambda: "review-1",
    )
    incident, analysis, packet = packet_context()
    service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=ReviewDecisionRequest(
            request_id="11111111-1111-4111-8111-111111111111",
            reviewer="Operations Manager",
            decision="approved",
            note="Approved.",
        ),
    )
    changed_packet = packet.model_copy(
        update={"packet_version": "sha256:changed-evidence"}
    )

    state = service.get_state(
        incident=incident,
        analysis=analysis,
        packet=changed_packet,
    )

    assert state.status == "needs-changes"
    assert state.ready_to_submit is False
    assert all(event.id != "review-1" for event in state.timeline)
```

- [x] **Step 6: Add a failing UUID request-contract test**

Add to `services/api/tests/test_review_trail.py`:

```python
import pytest
from pydantic import ValidationError


def test_review_decision_request_requires_uuid() -> None:
    with pytest.raises(ValidationError):
        ReviewDecisionRequest(
            reviewer="Operations Manager",
            decision="approved",
            note="Approved.",
        )
```

- [x] **Step 7: Run service and request tests and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_service.py \
  tests/test_review_trail.py::test_review_decision_request_requires_uuid \
  -q
```

Expected: collection ERROR because `batchhelm_api.review_service` does not
exist; after isolating the request test, it FAILS because the current model does
not require a request UUID.

- [x] **Step 8: Add the request UUID and implement `ReviewService`**

In `models.py`, import `UUID` and change the request model:

```python
class ReviewDecisionRequest(BaseModel):
    request_id: UUID
    reviewer: str = Field(default="Operations Manager", min_length=2)
    decision: ReviewStatus
    note: str = Field(min_length=2)
```

Create `services/api/src/batchhelm_api/review_service.py`:

```python
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
        base_state = build_demo_review_state(
            incident=incident,
            analysis=analysis,
            packet=packet,
        )
        state = base_state
        records = self._repository.list_for_packet(
            incident_id=incident.id,
            packet_version=packet.packet_version,
        )
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
```

- [x] **Step 9: Run service and domain tests and verify GREEN**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_service.py \
  tests/test_review_trail.py::test_demo_review_state_marks_packet_not_ready_until_blockers_resolved \
  tests/test_review_trail.py::test_apply_review_decision_projects_approval_timeline \
  tests/test_review_trail.py::test_review_decision_request_requires_uuid \
  -q
```

Expected: service, request-contract, and pure-domain tests PASS. Leave API route
changes for Task 4.

- [x] **Step 10: Record a local checkpoint**

Run: `git diff --check`

Expected: no whitespace errors. Do not stage or commit.

## Task 4: FastAPI Persistence, Restart Recovery, And Errors

**Files:**
- Modify: `services/api/tests/test_review_trail.py`
- Modify: `services/api/src/batchhelm_api/config.py:10-28`
- Modify: `services/api/src/batchhelm_api/app.py:12-188`

- [x] **Step 1: Write failing API restart and complete-history tests**

Change the test helper to accept a temporary database:

```python
from pathlib import Path


def make_client(database_path: Path) -> TestClient:
    settings = Settings(
        QWEN_API_KEY="",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug",
        DATABASE_PATH=database_path,
    )
    return TestClient(create_app(settings=settings))
```

Update existing API tests to accept `tmp_path: Path` and call
`make_client(tmp_path / "batchhelm.db")`. Add `request_id` to every decision
payload.

Add:

```python
def test_approval_survives_application_restart(tmp_path: Path) -> None:
    database_path = tmp_path / "batchhelm.db"
    decision = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }

    first = make_client(database_path)
    assert first.post(
        "/api/evidence/demo-review/decision",
        json=decision,
    ).status_code == 200

    restarted = make_client(database_path)
    payload = restarted.get("/api/evidence/demo-review").json()

    assert payload["status"] == "approved"
    assert payload["ready_to_submit"] is True
    assert payload["timeline"][-1]["detail"] == decision["note"]


def test_later_changes_request_keeps_approval_in_history(tmp_path: Path) -> None:
    client = make_client(tmp_path / "batchhelm.db")
    approved = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }
    changes = {
        "request_id": "22222222-2222-4222-8222-222222222222",
        "reviewer": "Operations Manager",
        "decision": "needs-changes",
        "note": "Attach signed disposal records.",
    }

    client.post("/api/evidence/demo-review/decision", json=approved)
    response = client.post("/api/evidence/demo-review/decision", json=changes)
    payload = response.json()

    assert payload["status"] == "needs-changes"
    assert payload["ready_to_submit"] is False
    assert [event["title"] for event in payload["timeline"][-2:]] == [
        "Packet Approved",
        "Changes Requested",
    ]
```

- [x] **Step 2: Run restart tests and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_trail.py::test_approval_survives_application_restart \
  tests/test_review_trail.py::test_later_changes_request_keeps_approval_in_history \
  -q
```

Expected: FAIL because `Settings` and `create_app` do not wire a database-backed
review service.

- [x] **Step 3: Add database configuration and app wiring**

Add to `Settings`:

```python
database_path: Path = Field(
    default=Path("./data/batchhelm.db"),
    validation_alias="DATABASE_PATH",
)
```

In `app.py`, import:

```python
from batchhelm_api.review_repository import (
    ReviewIdempotencyConflict,
    ReviewRepository,
    ReviewStoreUnavailable,
    SQLiteReviewRepository,
)
from batchhelm_api.review_service import ReviewService
```

Change the app factory and initialize the service:

```python
def create_app(
    settings: Settings | None = None,
    review_repository: ReviewRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    repository = review_repository or SQLiteReviewRepository(
        resolved_settings.database_path
    )
    repository.initialize()
    review_service = ReviewService(repository)

    app = FastAPI(
        title="BatchHelm API",
        version="0.1.0",
        description="Recall workflow API for BatchHelm.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.review_service = review_service
```

Add a dependency before `app = create_app()`:

```python
def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service
```

Replace the review routes with synchronous routes so FastAPI runs blocking
SQLite work in its thread pool:

```python
@app.get("/api/evidence/demo-review", response_model=EvidenceReviewState)
def demo_evidence_review(
    service: ReviewService = Depends(get_review_service),
) -> EvidenceReviewState:
    incident, analysis, packet = _build_demo_packet_context()
    return service.get_state(
        incident=incident,
        analysis=analysis,
        packet=packet,
    )


@app.post(
    "/api/evidence/demo-review/decision",
    response_model=EvidenceReviewState,
)
def demo_evidence_review_decision(
    request: ReviewDecisionRequest,
    service: ReviewService = Depends(get_review_service),
) -> EvidenceReviewState:
    incident, analysis, packet = _build_demo_packet_context()
    return service.record_decision(
        incident=incident,
        analysis=analysis,
        packet=packet,
        request=request,
    )
```

- [x] **Step 4: Run restart tests and verify GREEN**

Run: `cd services/api && uv run pytest tests/test_review_trail.py -q`

Expected: review API tests PASS and state survives a new app instance.

- [x] **Step 5: Write failing idempotency and sanitized-error API tests**

Append to `test_review_trail.py`:

```python
from batchhelm_api.review_repository import (
    ReviewDecisionRecord,
    ReviewStoreUnavailable,
)


def test_identical_api_retry_does_not_duplicate_timeline_event(
    tmp_path: Path,
) -> None:
    client = make_client(tmp_path / "batchhelm.db")
    decision = {
        "request_id": "11111111-1111-4111-8111-111111111111",
        "reviewer": "Operations Manager",
        "decision": "approved",
        "note": "Approved for supplier submission.",
    }

    client.post("/api/evidence/demo-review/decision", json=decision)
    payload = client.post(
        "/api/evidence/demo-review/decision",
        json=decision,
    ).json()

    assert sum(
        event["title"] == "Packet Approved"
        for event in payload["timeline"]
    ) == 1


def test_conflicting_request_id_returns_409(tmp_path: Path) -> None:
    client = make_client(tmp_path / "batchhelm.db")
    request_id = "11111111-1111-4111-8111-111111111111"
    client.post(
        "/api/evidence/demo-review/decision",
        json={
            "request_id": request_id,
            "reviewer": "Operations Manager",
            "decision": "approved",
            "note": "Approved.",
        },
    )

    response = client.post(
        "/api/evidence/demo-review/decision",
        json={
            "request_id": request_id,
            "reviewer": "Operations Manager",
            "decision": "needs-changes",
            "note": "Attach disposal records.",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"


class UnavailableReviewRepository:
    def initialize(self) -> None:
        return None

    def append(self, record: ReviewDecisionRecord) -> ReviewDecisionRecord:
        raise ReviewStoreUnavailable("sensitive sqlite failure")

    def list_for_packet(
        self,
        *,
        incident_id: str,
        packet_version: str,
    ) -> list[ReviewDecisionRecord]:
        raise ReviewStoreUnavailable("sensitive sqlite failure")


def test_review_store_failure_returns_sanitized_503() -> None:
    settings = Settings(APP_ENV="test")
    client = TestClient(
        create_app(
            settings=settings,
            review_repository=UnavailableReviewRepository(),
        )
    )

    response = client.get("/api/evidence/demo-review")

    assert response.status_code == 503
    assert response.json() == {
        "code": "review_store_unavailable",
        "message": "Review history is temporarily unavailable.",
        "details": None,
    }
    assert "sqlite" not in response.text.lower()
```

- [x] **Step 6: Run error tests and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_trail.py::test_conflicting_request_id_returns_409 \
  tests/test_review_trail.py::test_review_store_failure_returns_sanitized_503 \
  -q
```

Expected: FAIL because repository exceptions do not yet have FastAPI handlers.

- [x] **Step 7: Add specific API error handlers**

Add these handlers before the broad `ValueError` handler:

```python
@app.exception_handler(ReviewIdempotencyConflict)
async def review_idempotency_handler(
    _request: Request,
    _exc: ReviewIdempotencyConflict,
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=APIError(
            code="idempotency_conflict",
            message="Request ID was already used for another review decision.",
        ).model_dump(),
    )


@app.exception_handler(ReviewStoreUnavailable)
async def review_store_handler(
    _request: Request,
    _exc: ReviewStoreUnavailable,
) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=APIError(
            code="review_store_unavailable",
            message="Review history is temporarily unavailable.",
        ).model_dump(),
    )
```

- [x] **Step 8: Run review API tests and verify GREEN**

Run: `cd services/api && uv run pytest tests/test_review_trail.py -q`

Expected: all review API tests PASS.

- [x] **Step 9: Run the complete backend suite**

Run: `cd services/api && uv run pytest -q`

Expected: all tests PASS, aside from any already-known third-party deprecation
warning.

- [x] **Step 10: Record a local checkpoint**

Run: `git diff --check`

Expected: no whitespace errors. Do not stage or commit.

## Task 5: Frontend Idempotency Wiring

**Files:**
- Modify: `apps/web/src/types.ts:74-80`
- Modify: `apps/web/src/api.ts:148-170`

- [x] **Step 1: Add the packet version type and request UUID**

Update `EvidencePacket` in `types.ts`:

```typescript
export interface EvidencePacket {
  incident_id: string;
  packet_version: string;
  filename: string;
  generated_at: string;
  sections: EvidencePacketSection[];
  markdown: string;
}
```

Update the request body in `submitReviewDecision`:

```typescript
body: JSON.stringify({
  request_id: crypto.randomUUID(),
  reviewer: "Operations Manager",
  decision,
  note:
    decision === "approved"
      ? "Approved for supplier submission."
      : "Resolve open evidence blockers before submission.",
}),
```

Create the UUID once inside the function call so one user action has one request
ID. Do not generate another ID while handling the same `fetch` response.

- [x] **Step 2: Run TypeScript and production-build verification**

Run: `cd apps/web && npm run build`

Expected: TypeScript and Vite production build PASS.

- [x] **Step 3: Record a local checkpoint**

Run: `git diff --check`

Expected: no whitespace errors. Do not stage or commit.

## Task 6: Configuration And Documentation

**Files:**
- Modify: `.env.example:14-16`
- Modify: `README.md`
- Modify: `docs/architecture.md`

- [x] **Step 1: Correct the environment example**

Replace:

```text
DATABASE_URL=sqlite:///./data/batchhelm.db
```

with:

```text
DATABASE_PATH=./data/batchhelm.db
```

Keep `UPLOAD_DIR` unchanged.

- [x] **Step 2: Update README behavior and demo instructions**

Change the POST route description to:

```markdown
| `POST` | `/api/evidence/demo-review/decision` | Persists an idempotent reviewer decision and returns the complete audit history |
```

Add after the endpoint table:

```markdown
### Durable Review Storage

Review decisions are stored in an append-only SQLite ledger at
`DATABASE_PATH` (default `./data/batchhelm.db`). Evidence packets expose a
canonical SHA-256 `packet_version` that excludes generation timestamps, so an
approval survives packet regeneration while changed evidence starts a new
review.

Each decision request carries a UUID. Replaying the same request is safe;
reusing its UUID for different content returns HTTP 409. Storage failures
return a sanitized HTTP 503 response without database details. The repository
interface is ready for a future Postgres adapter.
```

Replace the Evidence Review Demo list with:

```markdown
1. Open the Evidence panel and select **Review**.
2. Inspect the blocking release checks and select **Approve packet**.
3. Refresh the browser and confirm the approved state and timeline remain.
4. Restart the API, refresh again, and confirm the approval is still present.
5. Select **Request changes** and confirm both human decisions remain in order.
6. Select **Packet** to inspect or download the unchanged Markdown evidence artifact.
```

- [x] **Step 3: Update the architecture document**

Replace the Persistence paragraph with:

```markdown
Local demo storage uses filesystem uploads and `SQLiteReviewRepository` behind
the typed `ReviewRepository` application boundary. Evidence-packet content is
versioned with canonical SHA-256 data that excludes generation timestamps.
Reviewer decisions are immutable ledger rows and are folded chronologically to
reconstruct current readiness and the complete audit trail. A Postgres adapter
can implement the same protocol without changing the review service or API.
```

Add to Error Handling:

```markdown
- Conflicting idempotency keys return HTTP 409 without duplicating audit events.
- Review storage failures return sanitized HTTP 503 responses without database details.
```

- [x] **Step 4: Verify database artifacts are ignored**

Run:

```bash
git check-ignore -v \
  data/batchhelm.db \
  data/batchhelm.db-wal \
  data/batchhelm.db-shm
```

Expected: all three paths match `.gitignore` rule `data/`.

- [x] **Step 5: Scan documentation for placeholders and attribution**

Run:

```bash
rg -n "TBD|TODO|FIXME|DATABASE_URL|Projects an approval" \
  README.md docs/architecture.md .env.example
```

Expected: no stale placeholder or old configuration matches.

Run: `scripts/check-attribution.sh`

Expected: `Attribution-language scan passed.`

## Task 7: End-To-End Verification

**Files:**
- Verify all modified files; do not create a commit.

- [x] **Step 1: Run fresh backend verification**

Run: `cd services/api && uv run pytest -q`

Expected: all backend tests PASS.

- [x] **Step 2: Run fresh frontend verification**

Run: `cd apps/web && npm run build`

Expected: typecheck and Vite production build PASS.

- [x] **Step 3: Run repository hygiene checks**

Run: `git diff --check`

Expected: no whitespace errors.

Run: `scripts/check-attribution.sh`

Expected: attribution-language scan PASS.

Run: `git diff --cached --stat`

Expected: no output because nothing is staged.

- [x] **Step 4: Run the API and web app**

Start the API:

```bash
cd services/api
uv run uvicorn batchhelm_api.app:app --reload --port 8000
```

Start the web app in another session:

```bash
cd apps/web
npm run dev -- --host 127.0.0.1 --port 5173
```

Expected: both servers start without errors.

- [x] **Step 5: Verify the browser workflow**

At `http://127.0.0.1:5173`:

1. Open the Evidence review panel and confirm `Needs Changes`.
2. Select `Approve packet`.
3. Refresh and confirm the packet remains `Approved`.
4. Inspect the POST payload and confirm `request_id` is a UUID.
5. Restart only the API and refresh again.
6. Confirm approval and the `Packet Approved` event remain.
7. Select `Request changes`.
8. Confirm the state is `Needs Changes` and the timeline shows both human
   decisions in order.
9. Confirm the browser console has no errors and there is no horizontal
   overflow at 1280x720 or 390x844.

- [x] **Step 6: Stop both development servers**

Terminate the Vite and Uvicorn sessions cleanly.

- [x] **Step 7: Inspect final local state**

Run: `git status --short --branch`

Expected:

- the branch remains ahead only by the already-existing local plan commit;
- durable-review files are modified or untracked locally;
- nothing is staged;
- no SQLite database, WAL, or shared-memory file appears.

- [x] **Step 8: Report the result**

Summarize:

- durable SQLite review history;
- stable packet versioning;
- idempotent reviewer actions;
- restart and browser evidence;
- exact backend test count and frontend build result;
- that no staging, commit, or push occurred.

## Task 8: Fail-Closed Repository Initialization

**Files:**
- Modify: `services/api/tests/test_review_trail.py`
- Modify: `services/api/src/batchhelm_api/review_repository.py`
- Modify: `services/api/src/batchhelm_api/app.py`

- [x] **Step 1: Write the failing startup-error test**

Add a repository double whose `initialize` method raises
`ReviewStoreUnavailable`, then assert that creating the app and requesting the
review endpoint returns the existing sanitized HTTP 503 payload:

```python
class InitializationFailureReviewRepository(UnavailableReviewRepository):
    def initialize(self) -> None:
        raise ReviewStoreUnavailable("sensitive sqlite schema failure")


def test_review_store_initialization_failure_returns_sanitized_503() -> None:
    client = TestClient(
        create_app(
            settings=Settings(APP_ENV="test"),
            review_repository=InitializationFailureReviewRepository(),
        )
    )

    response = client.get("/api/evidence/demo-review")

    assert response.status_code == 503
    assert response.json()["code"] == "review_store_unavailable"
    assert "sqlite" not in response.text.lower()
```

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_review_trail.py::test_review_store_initialization_failure_returns_sanitized_503 \
  -q
```

Expected: FAIL because `ReviewStoreUnavailable` escapes from `create_app`.

- [x] **Step 3: Add the fail-closed repository adapter**

Add `UnavailableReviewRepository` to `review_repository.py`. Its read and write
methods raise a sanitized `ReviewStoreUnavailable` chained from the captured
initialization error.

Wrap repository initialization in `create_app`:

```python
try:
    repository.initialize()
except ReviewStoreUnavailable as exc:
    repository = UnavailableReviewRepository(exc)
```

This preserves application startup while routing later review requests through
FastAPI's existing HTTP 503 exception handler.

- [x] **Step 4: Verify GREEN and run the complete backend suite**

Run the focused test, then run:

```bash
cd services/api
uv run pytest -q
```

Expected: 47 tests PASS with only the existing Starlette/httpx deprecation
warning.

- [x] **Step 5: Record a local checkpoint**

Run: `git diff --check`

Expected: no whitespace errors. Do not stage or commit.

## Plan Self-Review

- **Spec coverage:** Tasks 1-8 cover stable packet versions, append-only
  persistence, idempotency, restart recovery, sanitized read/write/startup
  failures, frontend request IDs, configuration, documentation, and browser QA.
- **Placeholder scan:** No unresolved implementation placeholders remain.
- **Type consistency:** `packet_version`, `request_id`,
  `ReviewDecisionRecord`, `ReviewRepository`, and `ReviewService` signatures
  match across models, storage, service, API, frontend, and tests.
