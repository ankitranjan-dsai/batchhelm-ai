"""Persistent memory for BatchHelm agents.

Stores the things a recall operator should not have to re-teach the system:
supplier name aliases, store layouts, previous decisions, recurring false
positives, and reviewer decisions. Records are upserted by (kind, key) so that
repeated observations increase ``occurrences`` and refresh ``last_seen`` instead
of duplicating. Agent checkpoints are persisted so an orchestration run is
durable and resumable.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from batchhelm_api.models import AgentRunStatus, MemoryKind, MemoryRecord, OutputSource

SCHEMA_VERSION = 1


class MemoryStoreUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class AgentCheckpoint:
    run_id: str
    agent: str
    status: AgentRunStatus
    summary: str
    source: OutputSource
    confidence: int
    finished_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryRepository(Protocol):
    def initialize(self) -> None: ...

    def remember(
        self,
        *,
        kind: MemoryKind,
        key: str,
        value: str,
        detail: str = "",
        confidence: int = 80,
        source: OutputSource = OutputSource.memory,
    ) -> MemoryRecord: ...

    def list_records(self) -> list[MemoryRecord]: ...

    def list_by_kind(self, kind: MemoryKind) -> list[MemoryRecord]: ...

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> None: ...

    def list_checkpoints(self, run_id: str) -> list[AgentCheckpoint]: ...


class InMemoryMemoryRepository:
    """Process-local repository used in tests and ephemeral demos."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], MemoryRecord] = {}
        self._checkpoints: dict[tuple[str, str], AgentCheckpoint] = {}

    def initialize(self) -> None:
        return None

    def remember(
        self,
        *,
        kind: MemoryKind,
        key: str,
        value: str,
        detail: str = "",
        confidence: int = 80,
        source: OutputSource = OutputSource.memory,
    ) -> MemoryRecord:
        composite = (kind.value, key)
        existing = self._records.get(composite)
        now = _now()
        if existing is None:
            record = MemoryRecord(
                id=uuid4().hex,
                kind=kind,
                key=key,
                value=value,
                detail=detail,
                confidence=confidence,
                occurrences=1,
                first_seen=now,
                last_seen=now,
                source=source,
            )
        else:
            record = existing.model_copy(
                update={
                    "value": value,
                    "detail": detail or existing.detail,
                    "confidence": max(existing.confidence, confidence),
                    "occurrences": existing.occurrences + 1,
                    "last_seen": now,
                }
            )
        self._records[composite] = record
        return record

    def list_records(self) -> list[MemoryRecord]:
        return sorted(self._records.values(), key=lambda r: r.last_seen, reverse=True)

    def list_by_kind(self, kind: MemoryKind) -> list[MemoryRecord]:
        return [record for record in self.list_records() if record.kind == kind]

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> None:
        self._checkpoints[(checkpoint.run_id, checkpoint.agent)] = checkpoint

    def list_checkpoints(self, run_id: str) -> list[AgentCheckpoint]:
        return [
            checkpoint
            for (rid, _), checkpoint in self._checkpoints.items()
            if rid == run_id
        ]


class SQLiteMemoryRepository:
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
                        raise MemoryStoreUnavailable(
                            "Memory database schema is newer than this service."
                        )
                    if version == 0:
                        connection.execute(
                            """
                            CREATE TABLE memory_records (
                                id TEXT PRIMARY KEY,
                                kind TEXT NOT NULL,
                                key TEXT NOT NULL,
                                value TEXT NOT NULL,
                                detail TEXT NOT NULL DEFAULT '',
                                confidence INTEGER NOT NULL DEFAULT 80,
                                occurrences INTEGER NOT NULL DEFAULT 1,
                                first_seen TEXT NOT NULL,
                                last_seen TEXT NOT NULL,
                                source TEXT NOT NULL DEFAULT 'memory',
                                UNIQUE (kind, key)
                            )
                            """
                        )
                        connection.execute(
                            """
                            CREATE TABLE agent_checkpoints (
                                run_id TEXT NOT NULL,
                                agent TEXT NOT NULL,
                                status TEXT NOT NULL,
                                summary TEXT NOT NULL,
                                source TEXT NOT NULL,
                                confidence INTEGER NOT NULL,
                                finished_at TEXT NOT NULL,
                                PRIMARY KEY (run_id, agent)
                            )
                            """
                        )
                        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except MemoryStoreUnavailable:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise MemoryStoreUnavailable("Memory storage is unavailable.") from exc

    def remember(
        self,
        *,
        kind: MemoryKind,
        key: str,
        value: str,
        detail: str = "",
        confidence: int = 80,
        source: OutputSource = OutputSource.memory,
    ) -> MemoryRecord:
        now = _now()
        try:
            with closing(self._connect()) as connection:
                with connection:
                    existing = connection.execute(
                        "SELECT * FROM memory_records WHERE kind = ? AND key = ?",
                        (kind.value, key),
                    ).fetchone()
                    if existing is None:
                        record = MemoryRecord(
                            id=uuid4().hex,
                            kind=kind,
                            key=key,
                            value=value,
                            detail=detail,
                            confidence=confidence,
                            occurrences=1,
                            first_seen=now,
                            last_seen=now,
                            source=source,
                        )
                        connection.execute(
                            """
                            INSERT INTO memory_records (
                                id, kind, key, value, detail, confidence,
                                occurrences, first_seen, last_seen, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                record.id,
                                record.kind.value,
                                record.key,
                                record.value,
                                record.detail,
                                record.confidence,
                                record.occurrences,
                                record.first_seen,
                                record.last_seen,
                                record.source.value,
                            ),
                        )
                        return record

                    record = MemoryRecord(
                        id=str(existing["id"]),
                        kind=kind,
                        key=key,
                        value=value,
                        detail=detail or str(existing["detail"]),
                        confidence=max(int(existing["confidence"]), confidence),
                        occurrences=int(existing["occurrences"]) + 1,
                        first_seen=str(existing["first_seen"]),
                        last_seen=now,
                        source=source,
                    )
                    connection.execute(
                        """
                        UPDATE memory_records
                        SET value = ?, detail = ?, confidence = ?, occurrences = ?,
                            last_seen = ?, source = ?
                        WHERE id = ?
                        """,
                        (
                            record.value,
                            record.detail,
                            record.confidence,
                            record.occurrences,
                            record.last_seen,
                            record.source.value,
                            record.id,
                        ),
                    )
                    return record
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise MemoryStoreUnavailable("Memory storage is unavailable.") from exc

    def list_records(self) -> list[MemoryRecord]:
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    "SELECT * FROM memory_records ORDER BY last_seen DESC"
                ).fetchall()
            return [_record_from_row(row) for row in rows]
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise MemoryStoreUnavailable("Memory storage is unavailable.") from exc

    def list_by_kind(self, kind: MemoryKind) -> list[MemoryRecord]:
        return [record for record in self.list_records() if record.kind == kind]

    def save_checkpoint(self, checkpoint: AgentCheckpoint) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO agent_checkpoints (
                            run_id, agent, status, summary, source, confidence,
                            finished_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (run_id, agent) DO UPDATE SET
                            status = excluded.status,
                            summary = excluded.summary,
                            source = excluded.source,
                            confidence = excluded.confidence,
                            finished_at = excluded.finished_at
                        """,
                        (
                            checkpoint.run_id,
                            checkpoint.agent,
                            checkpoint.status.value,
                            checkpoint.summary,
                            checkpoint.source.value,
                            checkpoint.confidence,
                            checkpoint.finished_at,
                        ),
                    )
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise MemoryStoreUnavailable("Memory storage is unavailable.") from exc

    def list_checkpoints(self, run_id: str) -> list[AgentCheckpoint]:
        try:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM agent_checkpoints
                    WHERE run_id = ?
                    ORDER BY finished_at ASC
                    """,
                    (run_id,),
                ).fetchall()
            return [
                AgentCheckpoint(
                    run_id=str(row["run_id"]),
                    agent=str(row["agent"]),
                    status=AgentRunStatus(str(row["status"])),
                    summary=str(row["summary"]),
                    source=OutputSource(str(row["source"])),
                    confidence=int(row["confidence"]),
                    finished_at=str(row["finished_at"]),
                )
                for row in rows
            ]
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise MemoryStoreUnavailable("Memory storage is unavailable.") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection


def _record_from_row(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=str(row["id"]),
        kind=MemoryKind(str(row["kind"])),
        key=str(row["key"]),
        value=str(row["value"]),
        detail=str(row["detail"]),
        confidence=int(row["confidence"]),
        occurrences=int(row["occurrences"]),
        first_seen=str(row["first_seen"]),
        last_seen=str(row["last_seen"]),
        source=OutputSource(str(row["source"])),
    )
