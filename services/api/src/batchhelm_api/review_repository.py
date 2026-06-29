from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from batchhelm_api.models import ReviewStatus

SCHEMA_VERSION = 2


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
    packet_generated_at: str
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


class UnavailableReviewRepository:
    def __init__(self, cause: ReviewStoreUnavailable) -> None:
        self._cause = cause

    def initialize(self) -> None:
        return None

    def append(self, record: ReviewDecisionRecord) -> ReviewDecisionRecord:
        raise ReviewStoreUnavailable(
            "Review history storage is unavailable."
        ) from self._cause

    def list_for_packet(
        self,
        *,
        incident_id: str,
        packet_version: str,
    ) -> list[ReviewDecisionRecord]:
        raise ReviewStoreUnavailable(
            "Review history storage is unavailable."
        ) from self._cause


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
                                packet_generated_at TEXT NOT NULL,
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
                    elif version == 1:
                        connection.execute(
                            """
                            ALTER TABLE review_decisions
                            ADD COLUMN packet_generated_at TEXT
                            """
                        )
                        connection.execute(
                            """
                            UPDATE review_decisions
                            SET packet_generated_at = decided_at
                            WHERE packet_generated_at IS NULL
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
                            packet_generated_at,
                            decision,
                            reviewer,
                            note,
                            decided_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.decision_id,
                            record.request_id,
                            record.incident_id,
                            record.packet_version,
                            record.packet_generated_at,
                            record.decision.value,
                            record.reviewer,
                            record.note,
                            record.decided_at,
                        ),
                    )
                    return record
        except sqlite3.IntegrityError as exc:
            return self._resolve_integrity_conflict(record, exc)
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise ReviewStoreUnavailable(
                "Review history storage is unavailable."
            ) from exc

    def _resolve_integrity_conflict(
        self,
        record: ReviewDecisionRecord,
        cause: sqlite3.IntegrityError,
    ) -> ReviewDecisionRecord:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM review_decisions
                    WHERE request_id = ?
                    """,
                    (record.request_id,),
                ).fetchone()
            if row is None:
                raise ReviewStoreUnavailable(
                    "Review history storage is unavailable."
                ) from cause
            existing = _record_from_row(row)
        except ReviewStoreUnavailable:
            raise
        except (sqlite3.Error, ValueError, KeyError) as exc:
            raise ReviewStoreUnavailable(
                "Review history storage is unavailable."
            ) from exc

        if _same_request(existing, record):
            return existing
        raise ReviewIdempotencyConflict(
            "Request ID was already used for another review decision."
        ) from cause

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
        packet_generated_at=str(row["packet_generated_at"]),
        decision=ReviewStatus(str(row["decision"])),
        reviewer=str(row["reviewer"]),
        note=str(row["note"]),
        decided_at=str(row["decided_at"]),
    )


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
