from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from batchhelm_api.models import (
    AgentEventType,
    AgentRunEvent,
    AgentRunStatus,
    OrchestrationResult,
    OrchestrationRunView,
    OutputSource,
)
from batchhelm_api.orchestration_state import OrchestrationCheckpoint

SCHEMA_VERSION = 1


class OrchestrationStoreUnavailable(RuntimeError):
    pass


class OrchestrationRunNotFound(LookupError):
    pass


class OrchestrationIdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class OrchestrationRunRecord:
    id: str
    incident_id: str
    idempotency_key: str
    status: AgentRunStatus
    provider_mode: str
    started_at: str | None
    updated_at: str
    finished_at: str | None
    next_wave: int
    checkpoint_version: int
    error_code: str | None
    error_message: str | None
    result: OrchestrationResult | None = None

    def to_view(self) -> OrchestrationRunView:
        return OrchestrationRunView(
            run_id=self.id,
            incident_id=self.incident_id,
            status=self.status,
            provider_mode=self.provider_mode,
            started_at=self.started_at,
            updated_at=self.updated_at,
            finished_at=self.finished_at,
            next_wave=self.next_wave,
            checkpoint_version=self.checkpoint_version,
            result=self.result,
            error_code=self.error_code,
            error_message=self.error_message,
        )


class OrchestrationRepository(Protocol):
    def initialize(self) -> None: ...

    def create_run(
        self,
        *,
        run_id: str,
        incident_id: str,
        idempotency_key: str,
        provider_mode: str,
    ) -> OrchestrationRunRecord: ...

    def get_run(self, run_id: str) -> OrchestrationRunRecord: ...

    def claim_run(self, run_id: str, started_at: str) -> OrchestrationRunRecord: ...

    def append_event(self, event: AgentRunEvent) -> AgentRunEvent: ...

    def list_events_after(
        self, run_id: str, sequence: int
    ) -> list[AgentRunEvent]: ...

    def latest_sequence(self, run_id: str) -> int: ...

    def save_checkpoint(
        self, run_id: str, checkpoint: OrchestrationCheckpoint
    ) -> OrchestrationRunRecord: ...

    def load_checkpoint(self, run_id: str) -> OrchestrationCheckpoint | None: ...

    def complete_run(
        self, run_id: str, result: OrchestrationResult
    ) -> OrchestrationRunRecord: ...

    def fail_run(
        self, run_id: str, *, code: str, message: str
    ) -> OrchestrationRunRecord: ...

    def list_recoverable(self) -> list[OrchestrationRunRecord]: ...

    def latest_completed_run(self) -> OrchestrationRunRecord | None: ...


class UnavailableOrchestrationRepository:
    def __init__(self, cause: OrchestrationStoreUnavailable) -> None:
        self._cause = cause

    def initialize(self) -> None:
        return None

    def create_run(
        self,
        *,
        run_id: str,
        incident_id: str,
        idempotency_key: str,
        provider_mode: str,
    ) -> OrchestrationRunRecord:
        self._raise()

    def get_run(self, run_id: str) -> OrchestrationRunRecord:
        self._raise()

    def claim_run(self, run_id: str, started_at: str) -> OrchestrationRunRecord:
        self._raise()

    def append_event(self, event: AgentRunEvent) -> AgentRunEvent:
        self._raise()

    def list_events_after(
        self, run_id: str, sequence: int
    ) -> list[AgentRunEvent]:
        self._raise()

    def latest_sequence(self, run_id: str) -> int:
        self._raise()

    def save_checkpoint(
        self, run_id: str, checkpoint: OrchestrationCheckpoint
    ) -> OrchestrationRunRecord:
        self._raise()

    def load_checkpoint(self, run_id: str) -> OrchestrationCheckpoint | None:
        self._raise()

    def complete_run(
        self, run_id: str, result: OrchestrationResult
    ) -> OrchestrationRunRecord:
        self._raise()

    def fail_run(
        self, run_id: str, *, code: str, message: str
    ) -> OrchestrationRunRecord:
        self._raise()

    def list_recoverable(self) -> list[OrchestrationRunRecord]:
        return []

    def latest_completed_run(self) -> OrchestrationRunRecord | None:
        return None

    def _raise(self):
        raise OrchestrationStoreUnavailable(
            "Orchestration storage is unavailable."
        ) from self._cause


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteOrchestrationRepository:
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
                    raise OrchestrationStoreUnavailable(
                        "Orchestration database schema is newer than this service."
                    )
                if version == 0:
                    with connection:
                        connection.executescript(
                            """
                            CREATE TABLE orchestration_runs (
                                id TEXT PRIMARY KEY,
                                incident_id TEXT NOT NULL,
                                idempotency_key TEXT NOT NULL UNIQUE,
                                status TEXT NOT NULL,
                                provider_mode TEXT NOT NULL,
                                started_at TEXT,
                                updated_at TEXT NOT NULL,
                                finished_at TEXT,
                                next_wave INTEGER NOT NULL DEFAULT 0,
                                checkpoint_version INTEGER NOT NULL DEFAULT 0,
                                snapshot_json TEXT,
                                result_json TEXT,
                                error_code TEXT,
                                error_message TEXT
                            );
                            CREATE TABLE orchestration_events (
                                run_id TEXT NOT NULL,
                                sequence INTEGER NOT NULL,
                                event_id TEXT NOT NULL UNIQUE,
                                agent TEXT NOT NULL,
                                event_type TEXT NOT NULL,
                                message TEXT NOT NULL,
                                occurred_at TEXT NOT NULL,
                                source TEXT NOT NULL,
                                data_json TEXT,
                                PRIMARY KEY (run_id, sequence),
                                FOREIGN KEY (run_id)
                                    REFERENCES orchestration_runs(id)
                                    ON DELETE CASCADE
                            );
                            CREATE INDEX orchestration_events_run_sequence
                            ON orchestration_events(run_id, sequence);
                            PRAGMA user_version = 1;
                            """
                        )
        except OrchestrationStoreUnavailable:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def create_run(
        self,
        *,
        run_id: str,
        incident_id: str,
        idempotency_key: str,
        provider_mode: str,
    ) -> OrchestrationRunRecord:
        now = _now()
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                try:
                    connection.execute(
                        """
                        INSERT INTO orchestration_runs (
                            id, incident_id, idempotency_key, status,
                            provider_mode, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            incident_id,
                            idempotency_key,
                            AgentRunStatus.pending.value,
                            provider_mode,
                            now,
                        ),
                    )
                    row = self._select_run(connection, run_id)
                    connection.commit()
                    return _run_from_row(row)
                except sqlite3.IntegrityError:
                    row = connection.execute(
                        """
                        SELECT * FROM orchestration_runs
                        WHERE idempotency_key = ?
                        """,
                        (idempotency_key,),
                    ).fetchone()
                    if row is None:
                        connection.rollback()
                        raise
                    existing = _run_from_row(row)
                    if (
                        existing.incident_id != incident_id
                        or existing.provider_mode != provider_mode
                    ):
                        connection.rollback()
                        raise OrchestrationIdempotencyConflict(
                            "Request ID was already used for another run."
                        )
                    connection.commit()
                    return existing
        except OrchestrationIdempotencyConflict:
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def get_run(self, run_id: str) -> OrchestrationRunRecord:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    "SELECT * FROM orchestration_runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
            if row is None:
                raise OrchestrationRunNotFound("Orchestration run was not found.")
            return _run_from_row(row)
        except OrchestrationRunNotFound:
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def claim_run(self, run_id: str, started_at: str) -> OrchestrationRunRecord:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE orchestration_runs
                    SET status = ?, started_at = COALESCE(started_at, ?),
                        updated_at = ?
                    WHERE id = ? AND status IN (?, ?)
                    """,
                    (
                        AgentRunStatus.running.value,
                        started_at,
                        _now(),
                        run_id,
                        AgentRunStatus.pending.value,
                        AgentRunStatus.running.value,
                    ),
                )
                if cursor.rowcount == 0:
                    row = connection.execute(
                        "SELECT * FROM orchestration_runs WHERE id = ?",
                        (run_id,),
                    ).fetchone()
                    connection.rollback()
                    if row is None:
                        raise OrchestrationRunNotFound(
                            "Orchestration run was not found."
                        )
                    return _run_from_row(row)
                row = self._select_run(connection, run_id)
                connection.commit()
                return _run_from_row(row)
        except OrchestrationRunNotFound:
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def append_event(self, event: AgentRunEvent) -> AgentRunEvent:
        data_json = (
            json.dumps(event.data, separators=(",", ":"), sort_keys=True)
            if event.data is not None
            else None
        )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO orchestration_events (
                        run_id, sequence, event_id, agent, event_type,
                        message, occurred_at, source, data_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.run_id,
                        event.sequence,
                        event.id,
                        event.agent,
                        event.type.value,
                        event.message,
                        event.at,
                        event.source.value,
                        data_json,
                    ),
                )
                connection.commit()
            return event
        except (
            OSError,
            sqlite3.Error,
            TypeError,
            ValueError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def list_events_after(
        self, run_id: str, sequence: int
    ) -> list[AgentRunEvent]:
        if sequence < 0:
            raise ValueError("Event sequence must be zero or greater.")
        self.get_run(run_id)
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM orchestration_events
                    WHERE run_id = ? AND sequence > ?
                    ORDER BY sequence ASC
                    """,
                    (run_id, sequence),
                ).fetchall()
            return [_event_from_row(row) for row in rows]
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def latest_sequence(self, run_id: str) -> int:
        self.get_run(run_id)
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) AS sequence
                    FROM orchestration_events WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchone()
            return int(row["sequence"])
        except (OSError, sqlite3.Error, TypeError, ValueError, KeyError) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def save_checkpoint(
        self, run_id: str, checkpoint: OrchestrationCheckpoint
    ) -> OrchestrationRunRecord:
        if checkpoint.run_id != run_id:
            raise ValueError("Checkpoint run ID does not match its target run.")
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE orchestration_runs
                    SET next_wave = ?, checkpoint_version = checkpoint_version + 1,
                        snapshot_json = ?, updated_at = ?
                    WHERE id = ? AND status NOT IN (?, ?)
                    """,
                    (
                        checkpoint.next_wave,
                        checkpoint.model_dump_json(),
                        _now(),
                        run_id,
                        AgentRunStatus.completed.value,
                        AgentRunStatus.failed.value,
                    ),
                )
                if cursor.rowcount == 0:
                    self._raise_missing_or_terminal(connection, run_id)
                row = self._select_run(connection, run_id)
                connection.commit()
                return _run_from_row(row)
        except (OrchestrationRunNotFound, ValueError):
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def load_checkpoint(self, run_id: str) -> OrchestrationCheckpoint | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT snapshot_json FROM orchestration_runs
                    WHERE id = ?
                    """,
                    (run_id,),
                ).fetchone()
            if row is None:
                raise OrchestrationRunNotFound("Orchestration run was not found.")
            snapshot_json = row["snapshot_json"]
            if snapshot_json is None:
                return None
            return OrchestrationCheckpoint.model_validate_json(str(snapshot_json))
        except OrchestrationRunNotFound:
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def complete_run(
        self, run_id: str, result: OrchestrationResult
    ) -> OrchestrationRunRecord:
        if result.run_id != run_id:
            raise ValueError("Result run ID does not match its target run.")
        terminal_status = (
            result.status
            if result.status
            in {AgentRunStatus.completed, AgentRunStatus.failed}
            else AgentRunStatus.completed
        )
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE orchestration_runs
                    SET status = ?, result_json = ?, finished_at = ?,
                        updated_at = ?, error_code = NULL, error_message = NULL
                    WHERE id = ? AND status NOT IN (?, ?)
                    """,
                    (
                        terminal_status.value,
                        result.model_dump_json(),
                        result.finished_at,
                        _now(),
                        run_id,
                        AgentRunStatus.completed.value,
                        AgentRunStatus.failed.value,
                    ),
                )
                if cursor.rowcount == 0:
                    self._raise_missing_or_terminal(connection, run_id)
                row = self._select_run(connection, run_id)
                connection.commit()
                return _run_from_row(row)
        except (OrchestrationRunNotFound, ValueError):
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def fail_run(
        self, run_id: str, *, code: str, message: str
    ) -> OrchestrationRunRecord:
        try:
            with closing(self._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    """
                    UPDATE orchestration_runs
                    SET status = ?, finished_at = ?, updated_at = ?,
                        error_code = ?, error_message = ?
                    WHERE id = ? AND status NOT IN (?, ?)
                    """,
                    (
                        AgentRunStatus.failed.value,
                        _now(),
                        _now(),
                        code,
                        message,
                        run_id,
                        AgentRunStatus.completed.value,
                        AgentRunStatus.failed.value,
                    ),
                )
                if cursor.rowcount == 0:
                    self._raise_missing_or_terminal(connection, run_id)
                row = self._select_run(connection, run_id)
                connection.commit()
                return _run_from_row(row)
        except OrchestrationRunNotFound:
            raise
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def list_recoverable(self) -> list[OrchestrationRunRecord]:
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM orchestration_runs
                    WHERE status IN (?, ?) AND result_json IS NULL
                    ORDER BY updated_at ASC
                    """,
                    (
                        AgentRunStatus.pending.value,
                        AgentRunStatus.running.value,
                    ),
                ).fetchall()
            return [_run_from_row(row) for row in rows]
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

    def latest_completed_run(self) -> OrchestrationRunRecord | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT * FROM orchestration_runs
                    WHERE status = ? AND result_json IS NOT NULL
                    ORDER BY finished_at DESC
                    LIMIT 1
                    """,
                    (AgentRunStatus.completed.value,),
                ).fetchone()
            if row is None:
                return None
            return _run_from_row(row)
        except (
            OSError,
            sqlite3.Error,
            ValidationError,
            ValueError,
            KeyError,
        ) as exc:
            raise OrchestrationStoreUnavailable(
                "Orchestration storage is unavailable."
            ) from exc

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
    def _select_run(
        connection: sqlite3.Connection, run_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM orchestration_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise OrchestrationRunNotFound("Orchestration run was not found.")
        return row

    @staticmethod
    def _raise_missing_or_terminal(
        connection: sqlite3.Connection, run_id: str
    ) -> None:
        row = connection.execute(
            "SELECT status FROM orchestration_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise OrchestrationRunNotFound("Orchestration run was not found.")
        raise ValueError("Orchestration run is already terminal.")


def _run_from_row(row: sqlite3.Row) -> OrchestrationRunRecord:
    result_json = row["result_json"]
    return OrchestrationRunRecord(
        id=str(row["id"]),
        incident_id=str(row["incident_id"]),
        idempotency_key=str(row["idempotency_key"]),
        status=AgentRunStatus(str(row["status"])),
        provider_mode=str(row["provider_mode"]),
        started_at=row["started_at"],
        updated_at=str(row["updated_at"]),
        finished_at=row["finished_at"],
        next_wave=int(row["next_wave"]),
        checkpoint_version=int(row["checkpoint_version"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        result=(
            OrchestrationResult.model_validate_json(str(result_json))
            if result_json
            else None
        ),
    )


def _event_from_row(row: sqlite3.Row) -> AgentRunEvent:
    data_json = row["data_json"]
    return AgentRunEvent(
        id=str(row["event_id"]),
        run_id=str(row["run_id"]),
        sequence=int(row["sequence"]),
        agent=str(row["agent"]),
        type=AgentEventType(str(row["event_type"])),
        message=str(row["message"]),
        at=str(row["occurred_at"]),
        source=OutputSource(str(row["source"])),
        data=json.loads(str(data_json)) if data_json is not None else None,
    )
