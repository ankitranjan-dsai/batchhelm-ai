from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import NoReturn, Protocol

from pydantic import ValidationError

from batchhelm_api.intake_models import (
    IntakeArtifact,
    IntakeArtifactRole,
    IntakeFieldEvidence,
    IntakeStatus,
    IntakeView,
    PublicIntakeArtifact,
    RecallIncidentDraft,
)
from batchhelm_api.models import RecallIncidentInput

SCHEMA_VERSION = 1


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


class IntakeRepository(Protocol):
    def initialize(self) -> None: ...

    def get_by_request(self, request_id: str) -> IntakeRecord | None: ...

    def list_intake_ids(self) -> set[str]: ...

    def create_intake(
        self,
        *,
        intake_id: str,
        request_id: str,
        packet_fingerprint: str,
        provider_mode: str,
        artifacts: list[IntakeArtifact],
    ) -> IntakeRecord: ...

    def get_intake(self, intake_id: str) -> IntakeRecord: ...

    def claim_extraction(self, intake_id: str) -> IntakeRecord: ...

    def save_extraction(
        self,
        intake_id: str,
        *,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord: ...

    def update_draft(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord: ...

    def confirm_intake(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        snapshot: RecallIncidentInput,
    ) -> IntakeRecord: ...

    def link_run(
        self,
        intake_id: str,
        *,
        request_id: str,
        run_id: str,
    ) -> IntakeRecord: ...

    def fail_intake(
        self,
        intake_id: str,
        *,
        code: str,
        message: str,
    ) -> IntakeRecord: ...

    def list_recoverable(self) -> list[IntakeRecord]: ...

    def resolve_incident(self, incident_id: str) -> RecallIncidentInput | None: ...

    def find_artifact(
        self,
        intake_id: str,
        role: IntakeArtifactRole,
    ) -> IntakeArtifact | None: ...


class UnavailableIntakeRepository:
    def __init__(self, cause: IntakeStoreUnavailable) -> None:
        self._cause = cause

    def initialize(self) -> None:
        return None

    def get_by_request(self, request_id: str) -> IntakeRecord | None:
        self._raise()

    def list_intake_ids(self) -> set[str]:
        self._raise()

    def create_intake(
        self,
        *,
        intake_id: str,
        request_id: str,
        packet_fingerprint: str,
        provider_mode: str,
        artifacts: list[IntakeArtifact],
    ) -> IntakeRecord:
        self._raise()

    def get_intake(self, intake_id: str) -> IntakeRecord:
        self._raise()

    def claim_extraction(self, intake_id: str) -> IntakeRecord:
        self._raise()

    def save_extraction(
        self,
        intake_id: str,
        *,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord:
        self._raise()

    def update_draft(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord:
        self._raise()

    def confirm_intake(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        snapshot: RecallIncidentInput,
    ) -> IntakeRecord:
        self._raise()

    def link_run(
        self,
        intake_id: str,
        *,
        request_id: str,
        run_id: str,
    ) -> IntakeRecord:
        self._raise()

    def fail_intake(
        self,
        intake_id: str,
        *,
        code: str,
        message: str,
    ) -> IntakeRecord:
        self._raise()

    def list_recoverable(self) -> list[IntakeRecord]:
        return []

    def resolve_incident(self, incident_id: str) -> RecallIncidentInput | None:
        self._raise()

    def find_artifact(
        self,
        intake_id: str,
        role: IntakeArtifactRole,
    ) -> IntakeArtifact | None:
        self._raise()

    def _raise(self) -> NoReturn:
        raise IntakeStoreUnavailable(
            "Intake storage is unavailable."
        ) from self._cause


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _payload_hash(value: object) -> str:
    payload = json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class SQLiteIntakeRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                connection.execute("PRAGMA journal_mode = WAL")
                version = int(
                    connection.execute("PRAGMA user_version").fetchone()[0]
                )
                if version > SCHEMA_VERSION:
                    raise IntakeStoreUnavailable(
                        "Intake database schema is newer than this service."
                    )
                if version == 0:
                    with connection:
                        connection.executescript(
                            """
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
                                FOREIGN KEY (intake_id)
                                    REFERENCES intakes(id) ON DELETE CASCADE
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
                                FOREIGN KEY (intake_id)
                                    REFERENCES intakes(id) ON DELETE CASCADE,
                                FOREIGN KEY (artifact_id)
                                    REFERENCES intake_artifacts(id),
                                FOREIGN KEY (supersedes_id)
                                    REFERENCES intake_field_evidence(id)
                            );

                            CREATE TABLE intake_requests (
                                request_id TEXT PRIMARY KEY,
                                intake_id TEXT NOT NULL,
                                operation TEXT NOT NULL,
                                payload_hash TEXT NOT NULL,
                                result_version INTEGER NOT NULL,
                                created_at TEXT NOT NULL,
                                FOREIGN KEY (intake_id)
                                    REFERENCES intakes(id) ON DELETE CASCADE
                            );

                            CREATE INDEX intake_evidence_sequence
                            ON intake_field_evidence(intake_id, sequence);

                            CREATE INDEX intake_status_updated
                            ON intakes(status, updated_at);

                            PRAGMA user_version = 1;
                            """
                        )
        except IntakeStoreUnavailable:
            raise
        except (OSError, sqlite3.Error, TypeError, ValueError) as exc:
            raise IntakeStoreUnavailable(
                "Intake storage is unavailable."
            ) from exc

    def get_by_request(self, request_id: str) -> IntakeRecord | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT id FROM intakes WHERE request_id = ?",
                    (request_id,),
                ).fetchone()
                return (
                    self._record(connection, str(row["id"]))
                    if row is not None
                    else None
                )
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def list_intake_ids(self) -> set[str]:
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute("SELECT id FROM intakes").fetchall()
            return {str(row["id"]) for row in rows}
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def create_intake(
        self,
        *,
        intake_id: str,
        request_id: str,
        packet_fingerprint: str,
        provider_mode: str,
        artifacts: list[IntakeArtifact],
    ) -> IntakeRecord:
        payload_hash = _payload_hash(
            {
                "packet_fingerprint": packet_fingerprint,
                "provider_mode": provider_mode,
            }
        )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                replay = self._request_replay(
                    connection,
                    request_id=request_id,
                    intake_id=None,
                    operation="create",
                    payload_hash=payload_hash,
                )
                if replay is not None:
                    record = self._record(connection, replay)
                    connection.commit()
                    return record

                if any(item.intake_id != intake_id for item in artifacts):
                    raise ValueError("Artifact intake ID does not match.")
                now = _now()
                connection.execute(
                    """
                    INSERT INTO intakes (
                        id, request_id, packet_fingerprint, status,
                        provider_mode, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        intake_id,
                        request_id,
                        packet_fingerprint,
                        IntakeStatus.uploaded.value,
                        provider_mode,
                        now,
                        now,
                    ),
                )
                for item in artifacts:
                    connection.execute(
                        """
                        INSERT INTO intake_artifacts (
                            id, intake_id, role, original_filename,
                            stored_filename, media_type, size_bytes, sha256,
                            relative_path, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.id,
                            item.intake_id,
                            item.role.value,
                            item.original_filename,
                            item.stored_filename,
                            item.media_type,
                            item.size_bytes,
                            item.sha256,
                            item.relative_path,
                            item.created_at,
                        ),
                    )
                self._save_request(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="create",
                    payload_hash=payload_hash,
                    result_version=0,
                )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except IntakeIdempotencyConflict:
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def get_intake(self, intake_id: str) -> IntakeRecord:
        try:
            with closing(self._connect()) as connection:
                return self._record(connection, intake_id)
        except IntakeNotFound:
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def claim_extraction(self, intake_id: str) -> IntakeRecord:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._intake_row(connection, intake_id)
                status = IntakeStatus(str(row["status"]))
                if status == IntakeStatus.uploaded:
                    connection.execute(
                        """
                        UPDATE intakes
                        SET status = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (IntakeStatus.extracting.value, _now(), intake_id),
                    )
                elif status != IntakeStatus.extracting:
                    raise IntakeStateConflict(
                        "Intake is not available for extraction."
                    )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except (IntakeNotFound, IntakeStateConflict):
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def save_extraction(
        self,
        intake_id: str,
        *,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._intake_row(connection, intake_id)
                if IntakeStatus(str(row["status"])) != IntakeStatus.extracting:
                    raise IntakeStateConflict(
                        "Intake is not in extraction."
                    )
                self._append_evidence(connection, intake_id, evidence)
                connection.execute(
                    """
                    UPDATE intakes
                    SET status = ?, draft_json = ?, version = version + 1,
                        updated_at = ?, error_code = NULL, error_message = NULL
                    WHERE id = ?
                    """,
                    (
                        IntakeStatus.review_required.value,
                        draft.model_dump_json(),
                        _now(),
                        intake_id,
                    ),
                )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except (IntakeNotFound, IntakeStateConflict):
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def update_draft(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        draft: RecallIncidentDraft,
        evidence: list[IntakeFieldEvidence],
    ) -> IntakeRecord:
        payload_hash = _payload_hash(
            {
                "expected_version": expected_version,
                "draft": draft.model_dump(mode="json"),
            }
        )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                replay = self._request_replay(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="update",
                    payload_hash=payload_hash,
                )
                if replay is not None:
                    record = self._record(connection, replay)
                    connection.commit()
                    return record

                row = self._intake_row(connection, intake_id)
                self._require_reviewable(row, expected_version)
                self._append_evidence(connection, intake_id, evidence)
                result_version = expected_version + 1
                connection.execute(
                    """
                    UPDATE intakes
                    SET draft_json = ?, version = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        draft.model_dump_json(),
                        result_version,
                        _now(),
                        intake_id,
                    ),
                )
                self._save_request(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="update",
                    payload_hash=payload_hash,
                    result_version=result_version,
                )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except (
            IntakeIdempotencyConflict,
            IntakeNotFound,
            IntakeStateConflict,
            IntakeVersionConflict,
        ):
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def confirm_intake(
        self,
        intake_id: str,
        *,
        request_id: str,
        expected_version: int,
        snapshot: RecallIncidentInput,
    ) -> IntakeRecord:
        payload_hash = _payload_hash(
            {
                "expected_version": expected_version,
                "incident_id": snapshot.id,
            }
        )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                replay = self._request_replay(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="confirm",
                    payload_hash=payload_hash,
                )
                if replay is not None:
                    record = self._record(connection, replay)
                    connection.commit()
                    return record

                row = self._intake_row(connection, intake_id)
                self._require_reviewable(row, expected_version)
                result_version = expected_version + 1
                connection.execute(
                    """
                    UPDATE intakes
                    SET status = ?, snapshot_json = ?, incident_id = ?,
                        version = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        IntakeStatus.ready.value,
                        snapshot.model_dump_json(),
                        snapshot.id,
                        result_version,
                        _now(),
                        intake_id,
                    ),
                )
                self._save_request(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="confirm",
                    payload_hash=payload_hash,
                    result_version=result_version,
                )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except (
            IntakeIdempotencyConflict,
            IntakeNotFound,
            IntakeStateConflict,
            IntakeVersionConflict,
        ):
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def link_run(
        self,
        intake_id: str,
        *,
        request_id: str,
        run_id: str,
    ) -> IntakeRecord:
        payload_hash = _payload_hash({"run_id": run_id})
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                replay = self._request_replay(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="run",
                    payload_hash=payload_hash,
                )
                if replay is not None:
                    record = self._record(connection, replay)
                    connection.commit()
                    return record

                row = self._intake_row(connection, intake_id)
                if IntakeStatus(str(row["status"])) != IntakeStatus.ready:
                    raise IntakeStateConflict(
                        "Intake is not ready to start a run."
                    )
                result_version = int(row["version"]) + 1
                connection.execute(
                    """
                    UPDATE intakes
                    SET status = ?, run_id = ?, version = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        IntakeStatus.run_started.value,
                        run_id,
                        result_version,
                        _now(),
                        intake_id,
                    ),
                )
                self._save_request(
                    connection,
                    request_id=request_id,
                    intake_id=intake_id,
                    operation="run",
                    payload_hash=payload_hash,
                    result_version=result_version,
                )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except (
            IntakeIdempotencyConflict,
            IntakeNotFound,
            IntakeStateConflict,
        ):
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def fail_intake(
        self,
        intake_id: str,
        *,
        code: str,
        message: str,
    ) -> IntakeRecord:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = self._intake_row(connection, intake_id)
                status = IntakeStatus(str(row["status"]))
                if status == IntakeStatus.failed:
                    connection.commit()
                    return self._record(connection, intake_id)
                if status in {IntakeStatus.ready, IntakeStatus.run_started}:
                    raise IntakeStateConflict(
                        "Confirmed intake cannot be marked as failed."
                    )
                connection.execute(
                    """
                    UPDATE intakes
                    SET status = ?, version = version + 1, updated_at = ?,
                        error_code = ?, error_message = ?
                    WHERE id = ?
                    """,
                    (
                        IntakeStatus.failed.value,
                        _now(),
                        code,
                        message,
                        intake_id,
                    ),
                )
                record = self._record(connection, intake_id)
                connection.commit()
                return record
        except (IntakeNotFound, IntakeStateConflict):
            raise
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def list_recoverable(self) -> list[IntakeRecord]:
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT id FROM intakes
                    WHERE status IN (?, ?)
                    ORDER BY updated_at ASC
                    """,
                    (
                        IntakeStatus.uploaded.value,
                        IntakeStatus.extracting.value,
                    ),
                ).fetchall()
                return [
                    self._record(connection, str(row["id"]))
                    for row in rows
                ]
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def resolve_incident(self, incident_id: str) -> RecallIncidentInput | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT snapshot_json FROM intakes
                    WHERE incident_id = ?
                    """,
                    (incident_id,),
                ).fetchone()
            if row is None:
                return None
            snapshot_json = row["snapshot_json"]
            if snapshot_json is None:
                return None
            return RecallIncidentInput.model_validate_json(str(snapshot_json))
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def find_artifact(
        self,
        intake_id: str,
        role: IntakeArtifactRole,
    ) -> IntakeArtifact | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT * FROM intake_artifacts
                    WHERE intake_id = ? AND role = ?
                    """,
                    (intake_id, role.value),
                ).fetchone()
            return _artifact_from_row(row) if row is not None else None
        except self._storage_errors() as exc:
            self._raise_unavailable(exc)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path,
            timeout=5.0,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _storage_errors() -> tuple[type[Exception], ...]:
        return (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        )

    @staticmethod
    def _raise_unavailable(exc: Exception) -> NoReturn:
        raise IntakeStoreUnavailable(
            "Intake storage is unavailable."
        ) from exc

    @staticmethod
    def _intake_row(
        connection: sqlite3.Connection,
        intake_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM intakes WHERE id = ?",
            (intake_id,),
        ).fetchone()
        if row is None:
            raise IntakeNotFound("Intake was not found.")
        return row

    def _record(
        self,
        connection: sqlite3.Connection,
        intake_id: str,
    ) -> IntakeRecord:
        row = self._intake_row(connection, intake_id)
        artifact_rows = connection.execute(
            """
            SELECT * FROM intake_artifacts
            WHERE intake_id = ? ORDER BY rowid ASC
            """,
            (intake_id,),
        ).fetchall()
        evidence_rows = connection.execute(
            """
            SELECT * FROM intake_field_evidence
            WHERE intake_id = ? ORDER BY sequence ASC
            """,
            (intake_id,),
        ).fetchall()
        draft_json = row["draft_json"]
        snapshot_json = row["snapshot_json"]
        return IntakeRecord(
            id=str(row["id"]),
            request_id=str(row["request_id"]),
            packet_fingerprint=str(row["packet_fingerprint"]),
            status=IntakeStatus(str(row["status"])),
            provider_mode=str(row["provider_mode"]),
            version=int(row["version"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            artifacts=tuple(_artifact_from_row(item) for item in artifact_rows),
            draft=(
                RecallIncidentDraft.model_validate_json(str(draft_json))
                if draft_json is not None
                else None
            ),
            evidence=tuple(
                _evidence_from_row(item) for item in evidence_rows
            ),
            snapshot=(
                RecallIncidentInput.model_validate_json(str(snapshot_json))
                if snapshot_json is not None
                else None
            ),
            incident_id=row["incident_id"],
            run_id=row["run_id"],
            error_code=row["error_code"],
            error_message=row["error_message"],
        )

    def _request_replay(
        self,
        connection: sqlite3.Connection,
        *,
        request_id: str,
        intake_id: str | None,
        operation: str,
        payload_hash: str,
    ) -> str | None:
        row = connection.execute(
            "SELECT * FROM intake_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        existing_intake_id = str(row["intake_id"])
        if (
            (intake_id is not None and existing_intake_id != intake_id)
            or str(row["operation"]) != operation
            or str(row["payload_hash"]) != payload_hash
        ):
            raise IntakeIdempotencyConflict(
                "Request ID was already used for another intake operation."
            )
        return existing_intake_id

    @staticmethod
    def _save_request(
        connection: sqlite3.Connection,
        *,
        request_id: str,
        intake_id: str,
        operation: str,
        payload_hash: str,
        result_version: int,
    ) -> None:
        connection.execute(
            """
            INSERT INTO intake_requests (
                request_id, intake_id, operation, payload_hash,
                result_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                intake_id,
                operation,
                payload_hash,
                result_version,
                _now(),
            ),
        )

    @staticmethod
    def _append_evidence(
        connection: sqlite3.Connection,
        intake_id: str,
        evidence: list[IntakeFieldEvidence],
    ) -> None:
        for item in evidence:
            if item.intake_id != intake_id:
                raise ValueError("Evidence intake ID does not match.")
            if item.artifact_id is not None:
                artifact = connection.execute(
                    """
                    SELECT intake_id FROM intake_artifacts WHERE id = ?
                    """,
                    (item.artifact_id,),
                ).fetchone()
                if artifact is None or str(artifact["intake_id"]) != intake_id:
                    raise ValueError(
                        "Evidence artifact does not belong to this intake."
                    )
            value = item.model_dump(mode="json")["value"]
            connection.execute(
                """
                INSERT INTO intake_field_evidence (
                    id, intake_id, field_path, value_json, artifact_id,
                    locator, source, confidence, requires_review,
                    supersedes_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.intake_id,
                    item.field_path,
                    json.dumps(
                        value,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    item.artifact_id,
                    item.locator,
                    item.source.value,
                    item.confidence,
                    int(item.requires_review),
                    item.supersedes_id,
                    item.created_at,
                ),
            )

    @staticmethod
    def _require_reviewable(
        row: sqlite3.Row,
        expected_version: int,
    ) -> None:
        if IntakeStatus(str(row["status"])) != IntakeStatus.review_required:
            raise IntakeStateConflict("Intake is not available for review.")
        if int(row["version"]) != expected_version:
            raise IntakeVersionConflict(
                "Intake was updated by another reviewer."
            )


def _artifact_from_row(row: sqlite3.Row) -> IntakeArtifact:
    return IntakeArtifact(
        id=str(row["id"]),
        intake_id=str(row["intake_id"]),
        role=IntakeArtifactRole(str(row["role"])),
        original_filename=str(row["original_filename"]),
        stored_filename=str(row["stored_filename"]),
        media_type=str(row["media_type"]),
        size_bytes=int(row["size_bytes"]),
        sha256=str(row["sha256"]),
        relative_path=str(row["relative_path"]),
        created_at=str(row["created_at"]),
    )


def _evidence_from_row(row: sqlite3.Row) -> IntakeFieldEvidence:
    return IntakeFieldEvidence(
        id=str(row["id"]),
        intake_id=str(row["intake_id"]),
        field_path=str(row["field_path"]),
        value=json.loads(str(row["value_json"])),
        artifact_id=row["artifact_id"],
        locator=str(row["locator"]),
        source=str(row["source"]),
        confidence=int(row["confidence"]),
        requires_review=bool(row["requires_review"]),
        supersedes_id=row["supersedes_id"],
        created_at=str(row["created_at"]),
    )
