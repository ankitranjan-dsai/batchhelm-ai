from __future__ import annotations

from pathlib import Path

import pytest

from batchhelm_api.memory_repository import (
    AgentCheckpoint,
    InMemoryMemoryRepository,
    SQLiteMemoryRepository,
)
from batchhelm_api.models import AgentRunStatus, MemoryKind, OutputSource


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path: Path):
    if request.param == "memory":
        store = InMemoryMemoryRepository()
    else:
        store = SQLiteMemoryRepository(tmp_path / "memory.db")
    store.initialize()
    return store


def test_remember_upserts_and_increments_occurrences(repo) -> None:
    first = repo.remember(
        kind=MemoryKind.supplier_alias, key="cf", value="Central Farms"
    )
    assert first.occurrences == 1

    second = repo.remember(
        kind=MemoryKind.supplier_alias, key="cf", value="Central Farms Inc"
    )
    assert second.occurrences == 2
    assert second.value == "Central Farms Inc"
    assert len(repo.list_records()) == 1


def test_list_by_kind_filters(repo) -> None:
    repo.remember(kind=MemoryKind.supplier_alias, key="cf", value="Central Farms")
    repo.remember(kind=MemoryKind.decision, key="r1", value="quarantine")

    aliases = repo.list_by_kind(MemoryKind.supplier_alias)
    assert len(aliases) == 1
    assert aliases[0].kind == MemoryKind.supplier_alias


def test_checkpoints_round_trip(repo) -> None:
    repo.save_checkpoint(
        AgentCheckpoint(
            run_id="run-1",
            agent="Inventory Matching Agent",
            status=AgentRunStatus.completed,
            summary="done",
            source=OutputSource.deterministic,
            confidence=90,
            finished_at="2026-06-27T00:00:00Z",
        )
    )
    checkpoints = repo.list_checkpoints("run-1")

    assert len(checkpoints) == 1
    assert checkpoints[0].agent == "Inventory Matching Agent"
    assert checkpoints[0].status == AgentRunStatus.completed


def test_sqlite_memory_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "memory.db"
    first = SQLiteMemoryRepository(db)
    first.initialize()
    first.remember(kind=MemoryKind.decision, key="r1", value="quarantine")

    second = SQLiteMemoryRepository(db)
    second.initialize()
    records = second.list_records()

    assert len(records) == 1
    assert records[0].key == "r1"
