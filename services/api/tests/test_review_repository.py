import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from batchhelm_api.models import ReviewStatus
from batchhelm_api.review_repository import (
    ReviewDecisionRecord,
    ReviewIdempotencyConflict,
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
        packet_generated_at="2026-06-27T08:59:00+00:00",
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


def test_repository_migrates_v1_packet_generation_time(tmp_path: Path) -> None:
    database_path = tmp_path / "batchhelm.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE review_decisions (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id TEXT NOT NULL UNIQUE,
                request_id TEXT NOT NULL UNIQUE,
                incident_id TEXT NOT NULL,
                packet_version TEXT NOT NULL,
                decision TEXT NOT NULL,
                reviewer TEXT NOT NULL,
                note TEXT NOT NULL,
                decided_at TEXT NOT NULL
            )
            """
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
                "review-1",
                "11111111-1111-4111-8111-111111111111",
                "recall-spinach-2026-06",
                "sha256:packet-one",
                "approved",
                "Operations Manager",
                "Approved.",
                "2026-06-27T09:00:00+00:00",
            ),
        )
        connection.execute("PRAGMA user_version = 1")

    repository = SQLiteReviewRepository(database_path)
    repository.initialize()
    record = repository.list_for_packet(
        incident_id="recall-spinach-2026-06",
        packet_version="sha256:packet-one",
    )[0]
    with sqlite3.connect(database_path) as connection:
        schema_version = int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        )

    assert schema_version == 2
    assert record.packet_generated_at == record.decided_at


def test_concurrent_identical_requests_resolve_to_one_record(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "batchhelm.db"
    repository = SQLiteReviewRepository(database_path)
    repository.initialize()
    workers = 6
    barrier = Barrier(workers)

    def append_once(index: int) -> ReviewDecisionRecord:
        concurrent_repository = SQLiteReviewRepository(database_path)
        barrier.wait()
        return concurrent_repository.append(
            make_record(
                decision_id=f"review-{index}",
                request_id="11111111-1111-4111-8111-111111111111",
                decision=ReviewStatus.approved,
                decided_at=f"2026-06-27T09:00:0{index}+00:00",
                note="Approved.",
            )
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(append_once, range(workers)))

    records = repository.list_for_packet(
        incident_id="recall-spinach-2026-06",
        packet_version="sha256:packet-one",
    )

    assert len(records) == 1
    assert all(result.request_id == records[0].request_id for result in results)
