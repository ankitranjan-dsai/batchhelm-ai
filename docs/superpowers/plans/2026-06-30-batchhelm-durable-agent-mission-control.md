# Durable Agent Mission Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one persisted orchestration run drive the complete BatchHelm dashboard, with ordered SSE replay and restart recovery from the last completed DAG wave.

**Architecture:** Add a dedicated SQLite orchestration repository and a lifecycle service around the existing nine-agent DAG. The orchestrator will accept a caller-owned run ID, persist every event before publication, save a typed blackboard snapshot after each wave, and resume from that snapshot. The React app will own one run session and pass its events and terminal result into Mission Control and the rest of the dashboard.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLite WAL, asyncio, Server-Sent Events, pytest, React 18, TypeScript, Vite, Vitest, Testing Library.

**Approved specification:** `docs/superpowers/specs/2026-06-30-batchhelm-durable-agent-mission-control-design.md`

**Git constraint:** Do not stage, commit, or push these checkpoints until the user explicitly reopens Git activity. The commit commands are recorded for later use.

---

## File Map

### Backend files to create

- `services/api/src/batchhelm_api/orchestration_state.py`
  - Typed checkpoint payload and blackboard serialization.
- `services/api/src/batchhelm_api/orchestration_repository.py`
  - Repository protocol, SQLite implementation, records, and sanitized errors.
- `services/api/src/batchhelm_api/orchestration_service.py`
  - Run lifecycle, worker deduplication, replay, recovery, and subscriber wakeups.
- `services/api/tests/test_orchestration_repository.py`
  - Persistence, idempotency, ordering, concurrency, and failure tests.
- `services/api/tests/test_orchestration_service.py`
  - Worker ownership, event replay, disconnect, and recovery tests.

### Backend files to modify

- `services/api/src/batchhelm_api/models.py`
  - Public run-start and run-status API models.
- `services/api/src/batchhelm_api/config.py`
  - `ORCHESTRATION_DATABASE_PATH`.
- `services/api/src/batchhelm_api/agents/base.py`
  - Persist-before-publish event callback and initial sequence.
- `services/api/src/batchhelm_api/agents/orchestrator.py`
  - Caller-owned run ID, wave snapshots, and resume.
- `services/api/src/batchhelm_api/event_stream.py`
  - Standards-compliant SSE IDs and terminal frames.
- `services/api/src/batchhelm_api/app.py`
  - Lifecycle service wiring and start/status/events endpoints.
- `services/api/tests/conftest.py`
  - Temporary orchestration database settings.
- `services/api/tests/test_orchestrator.py`
  - Snapshot and resume behavior.
- `services/api/tests/test_orchestration_api.py`
  - New HTTP and SSE contracts.

### Frontend files to create

- `apps/web/src/orchestrationSession.ts`
  - Session reducer, event deduplication, and state types.
- `apps/web/src/orchestrationSession.test.ts`
  - Pure session behavior tests.
- `apps/web/src/useOrchestrationRun.ts`
  - One-run lifecycle hook.
- `apps/web/src/useOrchestrationRun.test.tsx`
  - Start-once, stream, reconnect, and rerun tests.

### Frontend files to modify

- `apps/web/package.json`
  - Vitest and Testing Library scripts/dependencies.
- `apps/web/src/api.ts`
  - Start/status/event URL contracts; remove run-on-dashboard-sync.
- `apps/web/src/App.tsx`
  - Own one session and apply one terminal result.
- `apps/web/src/MissionControl.tsx`
  - Presentational DAG, timeline, inspector, and recovery states.
- `apps/web/src/styles.css`
  - Mission Control design-system styles and responsive layout.

### Documentation and deployment files to modify

- `.env.example`
- `README.md`
- `docker-compose.yml`
- `docs/architecture.md`
- `docs/demo-script.md`
- `docs/deployment-alibaba-cloud.md`
- `docs/known-limitations.md`
- `docs/qwen-integration.md`
- `docs/submission-checklist.md`

---

### Task 1: Add Durable Run Domain Contracts

**Files:**
- Modify: `services/api/src/batchhelm_api/models.py`
- Create: `services/api/src/batchhelm_api/orchestration_state.py`
- Modify: `services/api/src/batchhelm_api/config.py`
- Modify: `services/api/tests/conftest.py`
- Test: `services/api/tests/test_orchestration_repository.py`

- [ ] **Step 1: Write failing model and settings tests**

Create `services/api/tests/test_orchestration_repository.py` with the initial
contract tests:

```python
from __future__ import annotations

from uuid import UUID

from batchhelm_api.config import Settings
from batchhelm_api.models import (
    AgentRunStatus,
    OrchestrationRunAccepted,
    OrchestrationStartRequest,
)
from batchhelm_api.orchestration_state import OrchestrationCheckpoint


def test_start_request_requires_uuid_and_accepted_response_has_urls() -> None:
    request = OrchestrationStartRequest(
        request_id="0d05fc09-d47c-43aa-9f01-b021b26f0ac8"
    )
    accepted = OrchestrationRunAccepted(
        run_id="b119e7b8f5aa470ca04ab6ce80e38dd0",
        incident_id="recall-spinach-2026-06",
        status=AgentRunStatus.pending,
        events_url="/api/orchestration/runs/b119/events",
        result_url="/api/orchestration/runs/b119",
    )

    assert isinstance(request.request_id, UUID)
    assert accepted.status == AgentRunStatus.pending
    assert accepted.events_url.endswith("/events")


def test_checkpoint_defaults_to_an_empty_first_wave() -> None:
    checkpoint = OrchestrationCheckpoint(
        run_id="run-1",
        started_at="2026-06-30T09:00:00+00:00",
    )

    assert checkpoint.next_wave == 0
    assert checkpoint.results == []
    assert checkpoint.blackboard.affected_items == 0


def test_settings_exposes_separate_orchestration_database() -> None:
    settings = Settings(
        ORCHESTRATION_DATABASE_PATH="./tmp/orchestration.db",
        _env_file=None,
    )

    assert str(settings.orchestration_database_path).endswith("orchestration.db")
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_repository.py -q
```

Expected: collection fails because the new API models and
`orchestration_state` module do not exist.

- [ ] **Step 3: Add public run API models**

Append to `services/api/src/batchhelm_api/models.py` after
`OrchestrationResult`:

```python
class OrchestrationStartRequest(BaseModel):
    request_id: UUID


class OrchestrationRunAccepted(BaseModel):
    run_id: str
    incident_id: str
    status: AgentRunStatus
    events_url: str
    result_url: str


class OrchestrationRunView(BaseModel):
    run_id: str
    incident_id: str
    status: AgentRunStatus
    provider_mode: str
    started_at: str | None = None
    updated_at: str
    finished_at: str | None = None
    next_wave: int = 0
    checkpoint_version: int = 0
    result: OrchestrationResult | None = None
    error_code: str | None = None
    error_message: str | None = None
```

- [ ] **Step 4: Add typed checkpoint serialization**

Create `services/api/src/batchhelm_api/orchestration_state.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from batchhelm_api.models import (
    AgentRunResult,
    CustomerNoticeDraft,
    EvidenceItem,
    InventoryDecision,
    MemoryInsight,
    RecallExtraction,
    RiskAssessment,
    ShelfInspectionResult,
    StaffTask,
)


class OrchestrationBlackboard(BaseModel):
    intake_valid: bool = False
    extraction: RecallExtraction | None = None
    decisions: list[InventoryDecision] = Field(default_factory=list)
    affected_decisions: list[InventoryDecision] = Field(default_factory=list)
    affected_stores: list[str] = Field(default_factory=list)
    affected_items: int = 0
    supplier_aliases: list[str] = Field(default_factory=list)
    inspection: ShelfInspectionResult | None = None
    risk: RiskAssessment | None = None
    tasks: list[StaffTask] = Field(default_factory=list)
    customer_notice: CustomerNoticeDraft | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    evidence_progress: int = 0
    insights: list[MemoryInsight] = Field(default_factory=list)

    @classmethod
    def from_runtime(cls, blackboard: dict[str, object]) -> "OrchestrationBlackboard":
        allowed = set(cls.model_fields)
        return cls.model_validate(
            {key: value for key, value in blackboard.items() if key in allowed}
        )

    def to_runtime(self) -> dict[str, object]:
        return {
            key: value
            for key, value in self.__dict__.items()
            if value not in (None, [], "", False)
        }


class OrchestrationCheckpoint(BaseModel):
    run_id: str
    started_at: str
    next_wave: int = Field(default=0, ge=0)
    conflicts_resolved: int = Field(default=0, ge=0)
    blackboard: OrchestrationBlackboard = Field(
        default_factory=OrchestrationBlackboard
    )
    results: list[AgentRunResult] = Field(default_factory=list)
```

- [ ] **Step 5: Add orchestration database configuration**

Add to `Settings` in `services/api/src/batchhelm_api/config.py`:

```python
orchestration_database_path: Path = Field(
    default=Path("./data/orchestration.db"),
    validation_alias="ORCHESTRATION_DATABASE_PATH",
)
```

Import `Path` from `pathlib`, `gettempdir` from `tempfile`, and `uuid4` from
`uuid` in `services/api/tests/conftest.py`. Add this isolated default to the
`base` dictionary in `make_settings`:

```python
"ORCHESTRATION_DATABASE_PATH": (
    Path(gettempdir()) / f"batchhelm-orchestration-test-{uuid4().hex}.db"
)
```

Repository tests continue to override this setting with their pytest
`tmp_path`, while existing app tests receive a unique database file.

- [ ] **Step 6: Run targeted tests and verify GREEN**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_repository.py -q
```

Expected: 3 passed.

- [ ] **Step 7: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add services/api/src/batchhelm_api/models.py \
  services/api/src/batchhelm_api/orchestration_state.py \
  services/api/src/batchhelm_api/config.py \
  services/api/tests/conftest.py \
  services/api/tests/test_orchestration_repository.py
git commit -m "feat(api): define durable orchestration run contracts"
```

---

### Task 2: Implement the SQLite Orchestration Repository

**Files:**
- Create: `services/api/src/batchhelm_api/orchestration_repository.py`
- Expand: `services/api/tests/test_orchestration_repository.py`

- [ ] **Step 1: Add failing repository behavior tests**

Append these tests:

```python
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from batchhelm_api.models import (
    AgentEventType,
    AgentRunEvent,
    AgentRunStatus,
    OutputSource,
)
from batchhelm_api.orchestration_repository import (
    OrchestrationIdempotencyConflict,
    SQLiteOrchestrationRepository,
)


def make_repository(path: Path) -> SQLiteOrchestrationRepository:
    repository = SQLiteOrchestrationRepository(path)
    repository.initialize()
    return repository


def make_event(run_id: str, sequence: int) -> AgentRunEvent:
    return AgentRunEvent(
        id=f"event-{sequence}",
        run_id=run_id,
        sequence=sequence,
        agent="Recall Intake Agent",
        type=AgentEventType.reasoning,
        message=f"event {sequence}",
        at=f"2026-06-30T09:00:0{sequence}+00:00",
        source=OutputSource.deterministic,
    )


def test_run_and_events_survive_repository_restart(tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    repository = make_repository(path)
    run = repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    repository.append_event(make_event(run.id, 1))

    restarted = make_repository(path)

    assert restarted.get_run("run-1") == run
    assert restarted.list_events_after("run-1", 0)[0].sequence == 1


def test_same_idempotency_key_reuses_run_and_conflicting_incident_fails(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    first = repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    replay = repository.create_run(
        run_id="run-2",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )

    assert replay.id == first.id
    with pytest.raises(OrchestrationIdempotencyConflict):
        repository.create_run(
            run_id="run-3",
            incident_id="incident-2",
            idempotency_key="request-1",
            provider_mode="demo-fallback",
        )


def test_concurrent_identical_starts_create_one_run(tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    repository = make_repository(path)

    def create(index: int) -> str:
        return repository.create_run(
            run_id=f"run-{index}",
            incident_id="incident-1",
            idempotency_key="request-1",
            provider_mode="demo-fallback",
        ).id

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(create, range(6)))

    assert len(set(ids)) == 1


def test_checkpoint_and_terminal_result_are_persisted(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    checkpoint = OrchestrationCheckpoint(
        run_id="run-1",
        started_at="2026-06-30T09:00:00+00:00",
        next_wave=2,
    )

    saved = repository.save_checkpoint("run-1", checkpoint)

    assert saved.next_wave == 2
    assert saved.checkpoint_version == 1
    assert repository.load_checkpoint("run-1") == checkpoint
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_repository.py -q
```

Expected: import failure for `orchestration_repository`.

- [ ] **Step 3: Implement records, protocol, and schema**

Create `services/api/src/batchhelm_api/orchestration_repository.py` with:

```python
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
    AgentRunEvent,
    AgentRunStatus,
    OrchestrationResult,
    OrchestrationRunView,
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteOrchestrationRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.execute("PRAGMA foreign_keys = ON")
                    version = int(
                        connection.execute("PRAGMA user_version").fetchone()[0]
                    )
                    if version > SCHEMA_VERSION:
                        raise OrchestrationStoreUnavailable(
                            "Orchestration database schema is newer than this service."
                        )
                    if version == 0:
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

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._database_path, timeout=5.0, check_same_thread=False
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
```

Implement each protocol method using parameterized SQL. Use `BEGIN IMMEDIATE`
for `create_run`, `append_event`, `save_checkpoint`, and terminal state
transitions. Serialize Pydantic models with `model_dump_json()` and validate
loaded JSON with `model_validate_json()`. Map `sqlite3.IntegrityError` on an
existing idempotency key to either the existing run or
`OrchestrationIdempotencyConflict`. Map database and validation failures to
`OrchestrationStoreUnavailable`.

The row conversion helper must be:

```python
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
```

The event conversion helper must validate all enum and JSON fields through
`AgentRunEvent.model_validate`.

- [ ] **Step 4: Run repository tests and verify GREEN**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_repository.py -q
```

Expected: all repository tests pass.

- [ ] **Step 5: Add corruption and event-cursor tests**

Add tests proving:

```python
def test_event_cursor_returns_only_later_events(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    for sequence in range(1, 4):
        repository.append_event(make_event("run-1", sequence))

    assert [
        event.sequence
        for event in repository.list_events_after("run-1", 1)
    ] == [2, 3]


def test_duplicate_event_sequence_is_rejected(tmp_path: Path) -> None:
    repository = make_repository(tmp_path / "orchestration.db")
    repository.create_run(
        run_id="run-1",
        incident_id="incident-1",
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    repository.append_event(make_event("run-1", 1))

    with pytest.raises(OrchestrationStoreUnavailable):
        repository.append_event(make_event("run-1", 1))
```

Run the file again and expect all tests to pass.

- [ ] **Step 6: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add services/api/src/batchhelm_api/orchestration_repository.py \
  services/api/tests/test_orchestration_repository.py
git commit -m "feat(api): persist orchestration runs and events"
```

---

### Task 3: Persist Events Before Live Publication

**Files:**
- Modify: `services/api/src/batchhelm_api/agents/base.py`
- Modify: `services/api/src/batchhelm_api/event_stream.py`
- Modify: `services/api/tests/test_orchestrator.py`
- Test: `services/api/tests/test_orchestration_api.py`

- [ ] **Step 1: Write failing recorder and SSE tests**

Add to `services/api/tests/test_orchestrator.py`:

```python
from batchhelm_api.agents.base import EventRecorder


async def test_event_is_persisted_before_it_is_published() -> None:
    order: list[str] = []

    async def persist(event):
        order.append(f"persist:{event.sequence}")

    async def publish(event):
        order.append(f"publish:{event.sequence}")

    recorder = EventRecorder(
        "run-1",
        persist=persist,
        emit=publish,
        initial_sequence=7,
    )

    event = await recorder.record(
        agent="Orchestrator Agent",
        type=AgentEventType.started,
        message="Started.",
    )

    assert event.sequence == 8
    assert order == ["persist:8", "publish:8"]
```

Add to `services/api/tests/test_orchestration_api.py`:

```python
from batchhelm_api.event_stream import sse_pack
from batchhelm_api.models import AgentEventType, AgentRunEvent, OutputSource


def test_sse_frame_uses_sequence_as_standard_event_id() -> None:
    event = AgentRunEvent(
        id="event-1",
        run_id="run-1",
        sequence=12,
        agent="Inventory Matching Agent",
        type=AgentEventType.completed,
        message="Inventory matched.",
        at="2026-06-30T09:00:00+00:00",
        source=OutputSource.qwen,
    )

    frame = sse_pack(event)

    assert frame.startswith("id: 12\nevent: completed\n")
```

- [ ] **Step 2: Run both tests and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_orchestrator.py::test_event_is_persisted_before_it_is_published \
  tests/test_orchestration_api.py::test_sse_frame_uses_sequence_as_standard_event_id \
  -q
```

Expected: `EventRecorder` rejects the new arguments and the SSE frame lacks an
`id` line.

- [ ] **Step 3: Update EventRecorder**

In `agents/base.py`, add:

```python
PersistCallback = Callable[[AgentRunEvent], Awaitable[None]]
```

Replace the constructor and the persistence section of `record` with:

```python
def __init__(
    self,
    run_id: str,
    emit: EmitCallback | None = None,
    *,
    persist: PersistCallback | None = None,
    initial_sequence: int = 0,
) -> None:
    self.run_id = run_id
    self.events: list[AgentRunEvent] = []
    self._emit = emit
    self._persist = persist
    self._sequence = initial_sequence


async def _store_and_emit(self, event: AgentRunEvent) -> None:
    if self._persist is not None:
        await self._persist(event)
    self.events.append(event)
    if self._emit is not None:
        await self._emit(event)
```

Call `await self._store_and_emit(event)` from `record` instead of appending and
emitting directly.

- [ ] **Step 4: Update the SSE encoder**

Change `sse_pack` to:

```python
def sse_pack(event: AgentRunEvent) -> str:
    payload = event.model_dump_json()
    return (
        f"id: {event.sequence}\n"
        f"event: {event.type.value}\n"
        f"data: {payload}\n\n"
    )
```

Add terminal helpers:

```python
def sse_result(result_json: str) -> str:
    return f"event: result\ndata: {result_json}\n\n"


def sse_error(code: str, message: str) -> str:
    payload = json.dumps({"code": code, "message": message}, separators=(",", ":"))
    return f"event: run-error\ndata: {payload}\n\n"


def sse_heartbeat() -> str:
    return ": keep-alive\n\n"
```

Import `json` at the top of the file.

- [ ] **Step 5: Run targeted and existing orchestration tests**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestrator.py tests/test_orchestration_api.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add services/api/src/batchhelm_api/agents/base.py \
  services/api/src/batchhelm_api/event_stream.py \
  services/api/tests/test_orchestrator.py \
  services/api/tests/test_orchestration_api.py
git commit -m "feat(api): persist ordered agent events before streaming"
```

---

### Task 4: Make the DAG Resumable at Wave Boundaries

**Files:**
- Modify: `services/api/src/batchhelm_api/agents/orchestrator.py`
- Modify: `services/api/src/batchhelm_api/orchestration_state.py`
- Test: `services/api/tests/test_orchestrator.py`

- [ ] **Step 1: Write failing resume tests**

Append:

```python
from batchhelm_api.orchestration_state import OrchestrationCheckpoint


class _CountingAgent(Agent):
    role = "Counts executions"
    depends_on: tuple[str, ...] = ()

    def __init__(self, name: str, calls: dict[str, int]) -> None:
        self.name = name
        self.calls = calls

    async def run(self, ctx: AgentContext) -> AgentOutput:
        self.calls[self.name] = self.calls.get(self.name, 0) + 1
        ctx.blackboard["intake_valid"] = True
        return AgentOutput(
            summary=f"{self.name} complete",
            confidence=90,
            source=OutputSource.deterministic,
        )


async def test_orchestrator_preserves_caller_run_id_and_saves_each_wave() -> None:
    checkpoints: list[OrchestrationCheckpoint] = []
    orchestrator = _orchestrator(fallback_gateway())

    result = await orchestrator.run(
        build_demo_incident(),
        run_id="run-owned-by-service",
        checkpoint_sink=checkpoints.append,
    )

    assert result.run_id == "run-owned-by-service"
    assert checkpoints
    assert checkpoints[-1].next_wave == len(orchestrator._waves())


async def test_resume_skips_agents_from_completed_waves() -> None:
    calls: dict[str, int] = {}
    first = _CountingAgent("First", calls)
    second = _CountingAgent("Second", calls)
    second.depends_on = ("First",)
    orchestrator = _orchestrator(
        fallback_gateway(),
        agents=[first, second],
    )
    checkpoint = OrchestrationCheckpoint(
        run_id="run-1",
        started_at="2026-06-30T09:00:00+00:00",
        next_wave=1,
        results=[
            AgentRunResult(
                agent="First",
                role=first.role,
                status=AgentRunStatus.completed,
                summary="First complete",
                confidence=90,
                source=OutputSource.deterministic,
                started_at="2026-06-30T09:00:00+00:00",
                finished_at="2026-06-30T09:00:01+00:00",
            )
        ],
    )

    result = await orchestrator.run(
        build_demo_incident(),
        run_id="run-1",
        recovery=checkpoint,
    )

    assert calls.get("First", 0) == 0
    assert calls["Second"] == 1
    assert [agent.agent for agent in result.agents] == ["First", "Second"]
```

Add missing imports for `AgentRunResult`.

- [ ] **Step 2: Run resume tests and verify RED**

Run:

```bash
cd services/api
uv run pytest \
  tests/test_orchestrator.py::test_orchestrator_preserves_caller_run_id_and_saves_each_wave \
  tests/test_orchestrator.py::test_resume_skips_agents_from_completed_waves \
  -q
```

Expected: `Orchestrator.run` rejects `run_id`, `checkpoint_sink`, and
`recovery`.

- [ ] **Step 3: Add checkpoint callback types**

In `orchestrator.py`, import:

```python
from collections.abc import Awaitable, Callable

from batchhelm_api.orchestration_state import (
    OrchestrationBlackboard,
    OrchestrationCheckpoint,
)
```

Define:

```python
CheckpointSink = Callable[[OrchestrationCheckpoint], None]
PersistEvent = Callable[[AgentRunEvent], Awaitable[None]]
```

Import `AgentRunEvent`.

- [ ] **Step 4: Extend Orchestrator.run**

Use this signature:

```python
async def run(
    self,
    incident: RecallIncidentInput,
    *,
    run_id: str | None = None,
    channel: RunEventChannel | None = None,
    persist_event: PersistEvent | None = None,
    initial_sequence: int = 0,
    checkpoint_sink: CheckpointSink | None = None,
    recovery: OrchestrationCheckpoint | None = None,
    shelf_image_bytes: bytes | None = None,
    shelf_image_media_type: str | None = None,
) -> OrchestrationResult:
```

Initialize state with:

```python
resolved_run_id = run_id or uuid4().hex
recorder = EventRecorder(
    resolved_run_id,
    channel.emit if channel else None,
    persist=persist_event,
    initial_sequence=initial_sequence,
)
started_at = recovery.started_at if recovery else utcnow()
blackboard = recovery.blackboard.to_runtime() if recovery else {}
results = (
    {result.agent: result for result in recovery.results}
    if recovery
    else {}
)
start_wave = recovery.next_wave if recovery else 0
```

Pass `blackboard=blackboard` into `AgentContext`. Preserve optional shelf image
values only when explicitly provided.

Replace the wave loop with:

```python
waves = self._waves()
for wave_index in range(start_wave, len(waves)):
    wave = waves[wave_index]
    await asyncio.gather(
        *(self._run_agent(agent, ctx, results) for agent in wave)
    )
    checkpoint = OrchestrationCheckpoint(
        run_id=resolved_run_id,
        started_at=started_at,
        next_wave=wave_index + 1,
        blackboard=OrchestrationBlackboard.from_runtime(ctx.blackboard),
        results=[results[a.name] for a in self.agents if a.name in results],
    )
    if checkpoint_sink is not None:
        checkpoint_sink(checkpoint)
    await recorder.record(
        agent=ORCHESTRATOR,
        type=AgentEventType.checkpoint,
        message=f"Wave {wave_index + 1} checkpoint persisted.",
        data={"next_wave": wave_index + 1},
    )
```

Return `resolved_run_id` in the result. Keep direct calls without a run ID
backward compatible.

- [ ] **Step 5: Run orchestrator tests and verify GREEN**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestrator.py -q
```

Expected: all orchestrator tests pass.

- [ ] **Step 6: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add services/api/src/batchhelm_api/agents/orchestrator.py \
  services/api/src/batchhelm_api/orchestration_state.py \
  services/api/tests/test_orchestrator.py
git commit -m "feat(agents): resume orchestration from durable wave snapshots"
```

---

### Task 5: Add the Orchestration Lifecycle Service

**Files:**
- Create: `services/api/src/batchhelm_api/orchestration_service.py`
- Create: `services/api/tests/test_orchestration_service.py`

- [ ] **Step 1: Write failing lifecycle tests**

Create `services/api/tests/test_orchestration_service.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path

from batchhelm_api.agents import Orchestrator
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.orchestration_repository import SQLiteOrchestrationRepository
from batchhelm_api.orchestration_service import OrchestrationService
from batchhelm_api.sample_data import build_demo_incident
from tests.conftest import fallback_gateway, make_settings


def make_service(path: Path) -> OrchestrationService:
    repository = SQLiteOrchestrationRepository(path)
    repository.initialize()
    settings = make_settings(
        ORCHESTRATION_DATABASE_PATH=path,
        QWEN_MAX_RETRIES=1,
    )
    memory = InMemoryMemoryRepository()
    return OrchestrationService(
        repository=repository,
        orchestrator_factory=lambda: Orchestrator(
            gateway=fallback_gateway(),
            memory=memory,
            settings=settings,
        ),
    )


async def test_identical_start_requests_share_one_run_and_worker(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path / "orchestration.db")
    incident = build_demo_incident()

    first, second = await asyncio.gather(
        service.start(incident, request_id="request-1"),
        service.start(incident, request_id="request-1"),
    )
    result = await service.wait_for_result(first.run_id)

    assert first.run_id == second.run_id
    assert result.run_id == first.run_id
    assert service.worker_start_count(first.run_id) == 1


async def test_stream_replays_only_events_after_cursor(tmp_path: Path) -> None:
    service = make_service(tmp_path / "orchestration.db")
    accepted = await service.start(
        build_demo_incident(),
        request_id="request-1",
    )
    await service.wait_for_result(accepted.run_id)

    frames = [
        frame
        async for frame in service.stream(accepted.run_id, after=2)
    ]

    ids = [
        int(frame.splitlines()[0].removeprefix("id: "))
        for frame in frames
        if frame.startswith("id:")
    ]
    assert ids
    assert min(ids) == 3
    assert "event: result" in frames[-1]


async def test_recover_restarts_a_persisted_incomplete_run(tmp_path: Path) -> None:
    path = tmp_path / "orchestration.db"
    first = make_service(path)
    run = first.repository.create_run(
        run_id="run-1",
        incident_id=build_demo_incident().id,
        idempotency_key="request-1",
        provider_mode="demo-fallback",
    )
    first.repository.claim_run(run.id, "2026-06-30T09:00:00+00:00")

    restarted = make_service(path)
    await restarted.recover(build_demo_incident)
    result = await restarted.wait_for_result("run-1")

    assert result.status.value == "completed"
```

- [ ] **Step 2: Run lifecycle tests and verify RED**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_service.py -q
```

Expected: import failure for `orchestration_service`.

- [ ] **Step 3: Implement service task ownership**

Create `services/api/src/batchhelm_api/orchestration_service.py` with:

```python
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from uuid import uuid4

from batchhelm_api.agents import Orchestrator
from batchhelm_api.event_stream import (
    sse_error,
    sse_heartbeat,
    sse_pack,
    sse_result,
)
from batchhelm_api.models import (
    AgentRunEvent,
    AgentRunStatus,
    OrchestrationResult,
    OrchestrationRunAccepted,
    OrchestrationRunView,
    RecallIncidentInput,
)
from batchhelm_api.orchestration_repository import (
    OrchestrationRepository,
    OrchestrationRunNotFound,
)

OrchestratorFactory = Callable[[], Orchestrator]
IncidentFactory = Callable[[], RecallIncidentInput]


class OrchestrationService:
    def __init__(
        self,
        *,
        repository: OrchestrationRepository,
        orchestrator_factory: OrchestratorFactory,
    ) -> None:
        self.repository = repository
        self._orchestrator_factory = orchestrator_factory
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._conditions: dict[str, asyncio.Condition] = {}
        self._lock = asyncio.Lock()
        self._worker_starts: dict[str, int] = {}

    async def start(
        self,
        incident: RecallIncidentInput,
        *,
        request_id: str,
    ) -> OrchestrationRunAccepted:
        orchestrator = self._orchestrator_factory()
        run = self.repository.create_run(
            run_id=uuid4().hex,
            incident_id=incident.id,
            idempotency_key=request_id,
            provider_mode=orchestrator.gateway.status().mode,
        )
        await self._ensure_worker(run.id, incident)
        return OrchestrationRunAccepted(
            run_id=run.id,
            incident_id=run.incident_id,
            status=run.status,
            events_url=f"/api/orchestration/runs/{run.id}/events",
            result_url=f"/api/orchestration/runs/{run.id}",
        )

    def get(self, run_id: str) -> OrchestrationRunView:
        return self.repository.get_run(run_id).to_view()

    def worker_start_count(self, run_id: str) -> int:
        return self._worker_starts.get(run_id, 0)
```

Complete `_ensure_worker`, `_execute`, `_persist_event`, `wait_for_result`,
`stream`, and `recover` as follows:

- `_ensure_worker` holds `_lock`, checks for an unfinished task, and creates one
  `_execute` task only when absent.
- `_execute` claims the run, loads its checkpoint and latest sequence, invokes
  `Orchestrator.run` with repository callbacks, then persists the result.
- `_execute` catches exceptions, marks the run failed with
  `orchestration_failed`, and never exposes the raw exception in the stored
  message.
- `_persist_event` appends before notifying the run's `asyncio.Condition`.
- `wait_for_result` polls repository state after condition notifications and
  returns the stored result or raises a sanitized runtime error for failed runs.
- `stream` emits all persisted events after the cursor, then emits a terminal
  result/error frame or waits up to fifteen seconds and emits a heartbeat.
- `recover` enumerates `list_recoverable`, resolves each incident with the
  supplied factory, and calls `_ensure_worker`.
- `_execute` reloads all persisted run events after the orchestrator returns
  and replaces `result.events` with that complete history before persisting the
  terminal result. A resumed result therefore includes events from before and
  after the restart.

Use:

```python
async def _persist_event(self, event: AgentRunEvent) -> None:
    self.repository.append_event(event)
    condition = self._conditions.setdefault(event.run_id, asyncio.Condition())
    async with condition:
        condition.notify_all()
```

Use a task done callback that removes only the matching task object from
`_tasks`, preventing an older callback from deleting a newer recovery task.

- [ ] **Step 4: Run lifecycle tests and verify GREEN**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_service.py -q
```

Expected: all lifecycle tests pass.

- [ ] **Step 5: Add disconnect survival test**

Add:

```python
async def test_closing_subscriber_does_not_cancel_worker(tmp_path: Path) -> None:
    service = make_service(tmp_path / "orchestration.db")
    accepted = await service.start(
        build_demo_incident(),
        request_id="request-1",
    )
    stream = service.stream(accepted.run_id, after=0)
    await anext(stream)
    await stream.aclose()

    result = await service.wait_for_result(accepted.run_id)

    assert result.status == AgentRunStatus.completed
```

Run the file and expect all tests to pass.

- [ ] **Step 6: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add services/api/src/batchhelm_api/orchestration_service.py \
  services/api/tests/test_orchestration_service.py
git commit -m "feat(api): coordinate durable orchestration lifecycle"
```

---

### Task 6: Migrate the FastAPI Orchestration Contract

**Files:**
- Modify: `services/api/src/batchhelm_api/app.py`
- Rewrite orchestration cases: `services/api/tests/test_orchestration_api.py`

- [ ] **Step 1: Write failing API contract tests**

Replace the old stream test and add:

```python
from uuid import uuid4


def test_start_status_and_event_stream_share_one_run() -> None:
    client = make_client()
    request_id = str(uuid4())

    started = client.post(
        "/api/incidents/demo/runs",
        json={"request_id": request_id},
    )

    assert started.status_code == 202
    accepted = started.json()
    run_id = accepted["run_id"]
    with client.stream(
        "GET",
        f"/api/orchestration/runs/{run_id}/events",
    ) as response:
        body = "".join(response.iter_text())
    status = client.get(f"/api/orchestration/runs/{run_id}")

    assert response.status_code == 200
    assert f'"run_id":"{run_id}"' in body
    assert "event: result" in body
    assert status.status_code == 200
    assert status.json()["result"]["run_id"] == run_id


def test_last_event_id_replays_only_missing_events() -> None:
    client = make_client()
    started = client.post(
        "/api/incidents/demo/runs",
        json={"request_id": str(uuid4())},
    ).json()
    run_id = started["run_id"]
    client.get(f"/api/orchestration/runs/{run_id}")

    response = client.get(
        f"/api/orchestration/runs/{run_id}/events",
        headers={"Last-Event-ID": "2"},
    )

    assert "id: 1\n" not in response.text
    assert "id: 2\n" not in response.text
    assert "id: 3\n" in response.text


def test_unknown_run_and_invalid_cursor_are_structured_errors() -> None:
    client = make_client()

    missing = client.get("/api/orchestration/runs/missing")
    invalid = client.get(
        "/api/orchestration/runs/missing/events?after=-1"
    )

    assert missing.status_code == 404
    assert missing.json()["code"] == "run_not_found"
    assert invalid.status_code == 400
    assert invalid.json()["code"] == "invalid_event_cursor"
```

- [ ] **Step 2: Run API tests and verify RED**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_api.py -q
```

Expected: new routes return 404.

- [ ] **Step 3: Wire repository, service, and lifespan**

In `create_app`:

1. Create and initialize `SQLiteOrchestrationRepository` using
   `resolved_settings.orchestration_database_path`.
2. Build `OrchestrationService` with an orchestrator factory that uses the
   request-independent settings, memory repository, and a fresh Qwen gateway.
3. Store it as `app.state.orchestration_service`.
4. Use a lifespan closure that calls
   `await orchestration_service.recover(build_demo_incident)` before yielding.

Add:

```python
def get_orchestration_service(request: Request) -> OrchestrationService:
    return request.app.state.orchestration_service
```

Add sanitized exception handlers for
`OrchestrationRunNotFound`, `OrchestrationIdempotencyConflict`, and
`OrchestrationStoreUnavailable`.

- [ ] **Step 4: Add start, status, and stream routes**

Implement:

```python
@app.post(
    "/api/incidents/demo/runs",
    response_model=OrchestrationRunAccepted,
    status_code=202,
)
async def start_demo_run(
    request: OrchestrationStartRequest,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> OrchestrationRunAccepted:
    telemetry.increment("orchestration_runs")
    return await service.start(
        build_demo_incident(),
        request_id=str(request.request_id),
    )


@app.get(
    "/api/orchestration/runs/{run_id}",
    response_model=OrchestrationRunView,
)
async def get_orchestration_run(
    run_id: str,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> OrchestrationRunView:
    return service.get(run_id)


@app.get("/api/orchestration/runs/{run_id}/events")
async def stream_orchestration_run(
    run_id: str,
    request: Request,
    after: int | None = None,
    service: OrchestrationService = Depends(get_orchestration_service),
) -> StreamingResponse:
    if after is not None and after < 0:
        return JSONResponse(
            status_code=400,
            content=APIError(
                code="invalid_event_cursor",
                message="Event cursor must be zero or greater.",
            ).model_dump(),
        )
    header = request.headers.get("last-event-id")
    cursor = after if after is not None else int(header or "0")
    return StreamingResponse(
        service.stream(run_id, after=cursor),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Parse non-integer `Last-Event-ID` into the same HTTP 400 response rather than
letting `ValueError` expose a generic message.

- [ ] **Step 5: Route the compatibility endpoint through the service**

Change `POST /api/incidents/demo/run` to create a random request ID, start one
service run, and await its result:

```python
accepted = await service.start(
    build_demo_incident(),
    request_id=uuid4().hex,
)
return await service.wait_for_result(accepted.run_id)
```

Keep the old stream route only as a deprecated wrapper that starts a run and
streams its canonical run ID. Add `deprecated=True` to its FastAPI decorator.

- [ ] **Step 6: Run API and full backend tests**

Run:

```bash
cd services/api
uv run pytest tests/test_orchestration_api.py -q
uv run pytest -q
```

Expected: orchestration tests pass, followed by the full backend suite.

- [ ] **Step 7: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add services/api/src/batchhelm_api/app.py \
  services/api/tests/test_orchestration_api.py
git commit -m "feat(api): expose durable orchestration run endpoints"
```

---

### Task 7: Build One Frontend Run Session

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Create: `apps/web/src/orchestrationSession.ts`
- Create: `apps/web/src/orchestrationSession.test.ts`
- Create: `apps/web/src/useOrchestrationRun.ts`
- Create: `apps/web/src/useOrchestrationRun.test.tsx`
- Modify: `apps/web/src/api.ts`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1: Install the frontend test runner**

Run:

```bash
cd apps/web
npm install --save-dev vitest jsdom @testing-library/react
```

Add:

```json
"test": "vitest run"
```

to `scripts` in `package.json`.

- [ ] **Step 2: Write failing session reducer tests**

Create `apps/web/src/orchestrationSession.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  initialOrchestrationSession,
  orchestrationSessionReducer,
} from "./orchestrationSession";
import type { AgentRunEvent } from "./api";

const event = (sequence: number): AgentRunEvent => ({
  id: `event-${sequence}`,
  run_id: "run-1",
  sequence,
  agent: "Recall Intake Agent",
  type: "reasoning",
  message: `event ${sequence}`,
  at: "2026-06-30T09:00:00+00:00",
  source: "deterministic",
  data: null,
});

describe("orchestrationSessionReducer", () => {
  it("deduplicates replayed events and keeps sequence order", () => {
    let state = initialOrchestrationSession;
    state = orchestrationSessionReducer(state, {
      type: "event",
      event: event(2),
    });
    state = orchestrationSessionReducer(state, {
      type: "event",
      event: event(1),
    });
    state = orchestrationSessionReducer(state, {
      type: "event",
      event: event(2),
    });

    expect(state.events.map((item) => item.sequence)).toEqual([1, 2]);
    expect(state.lastSequence).toBe(2);
  });
});
```

- [ ] **Step 3: Run reducer test and verify RED**

Run:

```bash
cd apps/web
npm test -- orchestrationSession.test.ts
```

Expected: module import failure.

- [ ] **Step 4: Implement the session reducer**

Create `apps/web/src/orchestrationSession.ts`:

```typescript
import type {
  AgentRunEvent,
  OrchestrationResult,
  OrchestrationRunAccepted,
} from "./api";

export type OrchestrationConnection =
  | "idle"
  | "starting"
  | "streaming"
  | "reconnecting"
  | "completed"
  | "failed";

export interface OrchestrationSession {
  accepted: OrchestrationRunAccepted | null;
  events: AgentRunEvent[];
  result: OrchestrationResult | null;
  connection: OrchestrationConnection;
  lastSequence: number;
  error: string;
}

export const initialOrchestrationSession: OrchestrationSession = {
  accepted: null,
  events: [],
  result: null,
  connection: "idle",
  lastSequence: 0,
  error: "",
};

export type OrchestrationSessionAction =
  | { type: "starting" }
  | { type: "accepted"; accepted: OrchestrationRunAccepted }
  | { type: "event"; event: AgentRunEvent }
  | { type: "reconnecting" }
  | { type: "completed"; result: OrchestrationResult }
  | { type: "failed"; message: string }
  | { type: "reset" };

export function orchestrationSessionReducer(
  state: OrchestrationSession,
  action: OrchestrationSessionAction,
): OrchestrationSession {
  if (action.type === "reset") return initialOrchestrationSession;
  if (action.type === "starting") {
    return { ...initialOrchestrationSession, connection: "starting" };
  }
  if (action.type === "accepted") {
    return { ...state, accepted: action.accepted, connection: "streaming" };
  }
  if (action.type === "event") {
    const bySequence = new Map(
      [...state.events, action.event].map((item) => [item.sequence, item]),
    );
    const events = [...bySequence.values()].sort(
      (left, right) => left.sequence - right.sequence,
    );
    return {
      ...state,
      events,
      lastSequence: events.at(-1)?.sequence ?? 0,
      connection: "streaming",
    };
  }
  if (action.type === "reconnecting") {
    return { ...state, connection: "reconnecting" };
  }
  if (action.type === "completed") {
    return { ...state, result: action.result, connection: "completed" };
  }
  return { ...state, connection: "failed", error: action.message };
}
```

- [ ] **Step 5: Replace frontend API contracts**

In `api.ts`, add:

```typescript
export interface OrchestrationRunAccepted {
  run_id: string;
  incident_id: string;
  status: "pending" | "running" | "completed" | "failed";
  events_url: string;
  result_url: string;
}

export async function startDemoRun(
  requestId: string,
): Promise<OrchestrationRunAccepted> {
  const response = await fetch(`${API_BASE_URL}/api/incidents/demo/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId }),
  });
  if (!response.ok) {
    throw new Error(`Run start failed with ${response.status}`);
  }
  return (await response.json()) as OrchestrationRunAccepted;
}

export function orchestrationEventsUrl(
  accepted: OrchestrationRunAccepted,
  after = 0,
): string {
  const base = accepted.events_url.startsWith("http")
    ? accepted.events_url
    : `${API_BASE_URL}${accepted.events_url}`;
  return `${base}?after=${after}`;
}
```

Change `fetchDashboardSync` to fetch only `/api/qwen/status` and return the
provider. Remove the POST to `/api/incidents/demo/run`.

- [ ] **Step 6: Write the failing hook test**

Create `apps/web/src/useOrchestrationRun.test.tsx` using Testing Library's
`renderHook`. Mock `startDemoRun` and a small `EventSource` implementation.
Assert:

```typescript
expect(startDemoRun).toHaveBeenCalledTimes(1);
expect(MockEventSource.instances).toHaveLength(1);
```

After dispatching a `result` event, assert the hook exposes that exact result.
After invoking `rerun`, assert `startDemoRun` has been called exactly twice and
the second request ID differs from the first.

- [ ] **Step 7: Run hook test and verify RED**

Run:

```bash
cd apps/web
npm test -- useOrchestrationRun.test.tsx
```

Expected: module import failure.

- [ ] **Step 8: Implement the one-run hook**

Create `apps/web/src/useOrchestrationRun.ts`:

```typescript
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  orchestrationEventsUrl,
  startDemoRun,
  type AgentRunEvent,
  type OrchestrationResult,
} from "./api";
import {
  initialOrchestrationSession,
  orchestrationSessionReducer,
} from "./orchestrationSession";

export function useOrchestrationRun() {
  const [generation, setGeneration] = useState(0);
  const [session, dispatch] = useReducer(
    orchestrationSessionReducer,
    initialOrchestrationSession,
  );
  const sequenceRef = useRef(0);

  useEffect(() => {
    let active = true;
    let source: EventSource | null = null;
    dispatch({ type: "starting" });
    const requestId = crypto.randomUUID();

    void startDemoRun(requestId)
      .then((accepted) => {
        if (!active) return;
        dispatch({ type: "accepted", accepted });
        source = new EventSource(
          orchestrationEventsUrl(accepted, sequenceRef.current),
        );
        const eventTypes = [
          "started",
          "reasoning",
          "output",
          "completed",
          "failed",
          "retry",
          "conflict",
          "resolved",
          "checkpoint",
          "orchestrator",
        ];
        for (const type of eventTypes) {
          source.addEventListener(type, (message) => {
            const event = JSON.parse(
              (message as MessageEvent).data,
            ) as AgentRunEvent;
            sequenceRef.current = Math.max(
              sequenceRef.current,
              event.sequence,
            );
            dispatch({ type: "event", event });
          });
        }
        source.addEventListener("result", (message) => {
          dispatch({
            type: "completed",
            result: JSON.parse(
              (message as MessageEvent).data,
            ) as OrchestrationResult,
          });
          source?.close();
        });
        source.addEventListener("run-error", (message) => {
          const payload = JSON.parse((message as MessageEvent).data) as {
            message: string;
          };
          dispatch({ type: "failed", message: payload.message });
          source?.close();
        });
        source.onerror = () => dispatch({ type: "reconnecting" });
      })
      .catch(() => {
        if (active) {
          dispatch({
            type: "failed",
            message: "Agent Mission Control is unavailable.",
          });
        }
      });

    return () => {
      active = false;
      source?.close();
    };
  }, [generation]);

  const rerun = useCallback(() => {
    sequenceRef.current = 0;
    dispatch({ type: "reset" });
    setGeneration((value) => value + 1);
  }, []);

  return { session, rerun };
}
```

The named SSE `run-error` event marks the persisted run failed. Browser
transport `onerror` sets reconnecting and allows native `EventSource`
reconnection. Do not call `close()` from transport `onerror`.

- [ ] **Step 9: Make App own and apply the run**

In `App.tsx`:

- call `useOrchestrationRun()` once;
- remove the orchestration call from `fetchDashboardSync`;
- when `session.result` changes, call `toIncident(session.result.analysis)` and
  update `incident` and `tasks`;
- pass `session` and `rerun` into `MissionControl`;
- use provider status only for the top bar.

The result effect must guard against applying the same run twice:

```typescript
useEffect(() => {
  if (!session.result) return;
  const next = toIncident(session.result.analysis);
  setIncident(next);
  setTasks(next.tasks);
  setSyncState("connected");
}, [session.result]);
```

Export `toIncident` from `api.ts`.

- [ ] **Step 10: Run frontend tests and build**

Run:

```bash
cd apps/web
npm test
npm run build
```

Expected: all Vitest tests pass and Vite builds successfully.

- [ ] **Step 11: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add apps/web/package.json apps/web/package-lock.json \
  apps/web/src/api.ts apps/web/src/App.tsx \
  apps/web/src/orchestrationSession.ts \
  apps/web/src/orchestrationSession.test.ts \
  apps/web/src/useOrchestrationRun.ts \
  apps/web/src/useOrchestrationRun.test.tsx
git commit -m "feat(web): use one durable orchestration session"
```

---

### Task 8: Rebuild Mission Control Around the Persisted DAG

**Files:**
- Modify: `apps/web/src/MissionControl.tsx`
- Modify: `apps/web/src/styles.css`
- Test: `apps/web/src/orchestrationSession.test.ts`

- [ ] **Step 1: Add failing derived-status test**

Export `deriveAgentStates` from `orchestrationSession.ts` and test:

```typescript
it("derives running and completed agent states from ordered events", () => {
  const states = deriveAgentStates([
    { ...event(1), agent: "Recall Intake Agent", type: "started" },
    { ...event(2), agent: "Recall Intake Agent", type: "completed" },
    { ...event(3), agent: "Document Extraction Agent", type: "started" },
  ]);

  expect(states["Recall Intake Agent"]).toBe("completed");
  expect(states["Document Extraction Agent"]).toBe("running");
});
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
cd apps/web
npm test -- orchestrationSession.test.ts
```

Expected: `deriveAgentStates` is not exported.

- [ ] **Step 3: Implement derived status**

Add:

```typescript
export type AgentExecutionState =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "skipped";

export function deriveAgentStates(
  events: AgentRunEvent[],
): Record<string, AgentExecutionState> {
  const states: Record<string, AgentExecutionState> = {};
  for (const event of [...events].sort(
    (left, right) => left.sequence - right.sequence,
  )) {
    if (event.type === "started") states[event.agent] = "running";
    if (event.type === "completed") states[event.agent] = "completed";
    if (event.type === "failed") states[event.agent] = "failed";
  }
  return states;
}
```

Final result agent statuses override event-derived states for `skipped`.

- [ ] **Step 4: Convert MissionControl to a presentational component**

Use this public shape:

```typescript
interface MissionControlProps {
  session: OrchestrationSession;
  onRerun: () => void;
}
```

Remove all `EventSource`, `useEffect`, and run-key code from
`MissionControl.tsx`. Render:

- a compact header with provider and connection status;
- four execution waves based on the known agent dependencies;
- stable agent buttons using Lucide status icons;
- an event timeline sorted by sequence;
- a selected-agent inspector showing role, source, attempts, confidence,
  duration, summary, and reasoning;
- management briefing after completion;
- reconnecting, recovered, failed, and empty states;
- a RotateCcw icon button with tooltip for rerun.

Use the following wave constants:

```typescript
const WAVES = [
  ["Recall Intake Agent"],
  ["Document Extraction Agent"],
  ["Inventory Matching Agent", "Shelf Vision Agent"],
  ["Risk Scoring Agent", "Memory Agent"],
  ["Operations Task Agent", "Communications Agent"],
  ["Compliance Evidence Agent"],
] as const;
```

These six groups match the current backend dependency graph. Add an API
contract assertion that the descriptors still resolve into the same waves so a
future dependency change cannot silently make the visualization inaccurate.

- [ ] **Step 5: Move all visual styling into the design system**

Delete component-level style objects from `MissionControl.tsx`. Add focused
classes to `styles.css`:

```css
.mission-control {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface);
}

.mission-waves {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.mission-agent {
  width: 100%;
  min-height: 76px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--surface-raised);
  text-align: left;
}

@media (max-width: 760px) {
  .mission-waves {
    grid-template-columns: 1fr;
  }
}
```

Use the actual CSS custom-property names already defined at the top of
`styles.css`; do not introduce duplicate color tokens.

- [ ] **Step 6: Run tests and production build**

Run:

```bash
cd apps/web
npm test
npm run build
```

Expected: all tests and the production build pass.

- [ ] **Step 7: Run browser verification**

Start:

```bash
cd services/api
uv run uvicorn batchhelm_api.app:app --host 127.0.0.1 --port 8000
```

and:

```bash
cd apps/web
npm run dev -- --host 127.0.0.1 --port 5173
```

Verify at 1280×720 and 390×844:

- one POST to `/api/incidents/demo/runs`;
- the dashboard and Mission Control share one run ID;
- agents visibly progress through waves;
- selecting an agent opens its details;
- refresh/reconnect does not duplicate event rows;
- rerun creates exactly one new run;
- no horizontal overflow, overlap, blank panel, or console error.

- [ ] **Step 8: Record the deferred Git checkpoint**

When Git activity is reopened:

```bash
git add apps/web/src/MissionControl.tsx \
  apps/web/src/orchestrationSession.ts \
  apps/web/src/orchestrationSession.test.ts \
  apps/web/src/styles.css
git commit -m "feat(web): visualize durable agent execution graph"
```

---

### Task 9: Update Deployment, Documentation, and Release Evidence

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/demo-script.md`
- Modify: `docs/deployment-alibaba-cloud.md`
- Modify: `docs/known-limitations.md`
- Modify: `docs/qwen-integration.md`
- Modify: `docs/submission-checklist.md`

- [ ] **Step 1: Add the environment variable**

Add:

```dotenv
ORCHESTRATION_DATABASE_PATH=./data/orchestration.db
```

to `.env.example`. Add the same variable to the API environment in
`docker-compose.yml`, using the container's persistent data directory.

- [ ] **Step 2: Update architecture and API documentation**

Document:

- `OrchestrationService`;
- the separate SQLite run/event store;
- persist-before-publish event flow;
- completed-wave recovery;
- start, status, and SSE replay endpoints;
- the synchronous compatibility endpoint;
- single-process recovery scope.

The architecture Mermaid diagram must show:

```text
React Dashboard -> Run Service -> Agent Orchestrator -> Qwen Gateway
Run Service -> SQLite Run/Event Store
Agent Orchestrator -> SQLite Memory Store
```

- [ ] **Step 3: Update demo and submission evidence**

The demo script must include:

1. Start one run.
2. Point out parallel waves and source badges.
3. Briefly disconnect/reload and show event replay.
4. Open an agent inspector.
5. Show the management briefing.
6. Show the evidence review gate.

Remove the checkpoint-resume limitation from `known-limitations.md` only after
the restart test and manual restart demonstration pass. Keep multi-replica
execution explicitly out of scope.

- [ ] **Step 4: Run complete release verification**

Run:

```bash
cd services/api
uv run pytest -q

cd ../../apps/web
npm test
npm run build

cd ../..
./scripts/check-attribution.sh
git diff --check
git status --short --branch
```

Expected:

- backend suite passes;
- frontend tests and build pass;
- attribution scan passes;
- whitespace check is silent;
- only intended milestone files are modified or untracked.

Run Docker checks when Docker is installed:

```bash
docker compose config --quiet
docker build -t batchhelm-api:durable-mission-control .
docker build -t batchhelm-web:durable-mission-control apps/web
```

- [ ] **Step 5: Capture final runtime evidence**

Capture desktop and mobile screenshots under:

```text
docs/design-assets/screenshots/mission-control-desktop.png
docs/design-assets/screenshots/mission-control-mobile.png
```

Confirm the screenshots contain populated events, agent statuses, and the
management briefing.

- [ ] **Step 6: Record the deferred Git checkpoints**

When Git activity is reopened:

```bash
git add .env.example docker-compose.yml README.md \
  docs/architecture.md docs/demo-script.md \
  docs/deployment-alibaba-cloud.md docs/known-limitations.md \
  docs/qwen-integration.md docs/submission-checklist.md \
  docs/design-assets/screenshots/mission-control-desktop.png \
  docs/design-assets/screenshots/mission-control-mobile.png
git commit -m "docs: document durable Agent Mission Control"

git add docs/superpowers/specs/2026-06-30-batchhelm-durable-agent-mission-control-design.md \
  docs/superpowers/plans/2026-06-30-batchhelm-durable-agent-mission-control.md
git commit -m "docs: add durable mission control design and plan"

git push origin main
```

Before pushing, run `git log --format='%an <%ae> | %cn <%ce>' -12` and confirm
all public repository authorship remains under Ankit Ranjan.

---

## Completion Gate

Do not call this milestone complete until all statements below are supported by
current command output or runtime evidence:

- [ ] One page session creates exactly one orchestration run.
- [ ] Dashboard and Mission Control consume the same terminal result.
- [ ] Events are persisted before they are published.
- [ ] `Last-Event-ID` and `after` replay only missing ordered events.
- [ ] Completed-wave snapshots survive repository restart.
- [ ] Restart recovery skips completed waves and finishes the run.
- [ ] Duplicate request IDs never start duplicate workers.
- [ ] Subscriber disconnect never cancels a worker.
- [ ] Structured 400, 404, 409, and 503 responses expose no storage details.
- [ ] Existing Qwen fallback, retries, reconciliation, memory, and evidence review still pass.
- [ ] Backend and frontend automated suites pass.
- [ ] Desktop and mobile browser verification pass.
- [ ] Attribution and whitespace checks pass.
- [ ] Docker builds pass when Docker is available.
- [ ] Documentation matches implemented behavior.
