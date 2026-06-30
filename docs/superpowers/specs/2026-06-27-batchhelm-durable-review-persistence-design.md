# BatchHelm Durable Review Persistence Design

**Status:** Architecture approved

**Date:** 2026-06-27

## Goal

Persist evidence-packet review decisions and their audit history so approvals
survive browser refreshes and API restarts. The implementation must remain
zero-setup for hackathon judges while preserving a clean migration path to
Postgres.

## Scope

This slice will:

- add a stable content-derived version to each evidence packet;
- store review decisions in an append-only SQLite ledger;
- reconstruct the current review state from the complete decision history;
- preserve the packet's original audit timestamp across API restarts;
- make decision submission idempotent;
- surface stable API errors for storage failures and idempotency conflicts;
- configure the database path through the environment;
- document and test restart persistence.

This slice will not add authentication, role-based authorization, packet
editing, database replication, or a Postgres adapter. Those concerns can build
on the repository boundary without changing the review domain service.

## Architectural Decision

Use Python's standard-library `sqlite3` module behind a typed repository
protocol.

SQLite gives the local demo transactional durability without requiring a
separate service. A narrow `ReviewRepository` interface prevents FastAPI routes
and review-domain logic from depending on SQLite details, allowing a Postgres
implementation to replace it later.

The rejected alternatives are:

- JSON-file storage, because it does not provide safe transactions or
  concurrent writes;
- immediate Postgres deployment, because it adds infrastructure requirements
  that weaken the zero-setup judging experience;
- SQLAlchemy and Alembic in this slice, because one append-only table does not
  justify the additional dependency and migration surface.

## Components

### Evidence packet versioning

`EvidencePacket` gains a `packet_version` field. The value is
`sha256:<hex-digest>` over canonical JSON containing:

- the incident ID;
- each packet section's title;
- each packet section's body;
- the original order of the sections.

The canonical representation uses UTF-8, compact JSON separators, and stable
object-key ordering. It deliberately excludes `generated_at` and rendered
Markdown because the generation timestamp changes on every request.

Identical evidence content therefore produces the same version across API
restarts. Any changed section produces a new version and starts a fresh review
gate.

### Review repository

`review_repository.py` owns:

- `ReviewDecisionRecord`, the immutable persistence model;
- `ReviewRepository`, a protocol with `initialize`, `append`, and `list_for_packet`;
- `SQLiteReviewRepository`, the local durable implementation;
- repository-specific exceptions that do not expose SQLite internals.

The SQLite adapter opens a short-lived connection per operation, enables
foreign keys, configures a busy timeout, and uses WAL mode for reliable
concurrent reads. Writes run in explicit transactions.

### Review service

`review_service.py` owns application-level review behavior:

- build the base review state from the incident, analysis, and packet;
- load ordered decisions for the packet version;
- fold all decisions into the current state and full timeline;
- validate and append a new decision;
- return the reconstructed state after a successful append.

`review_trail.py` remains pure domain projection code. It will accept persisted
decision IDs and UTC timestamps instead of using the packet-generation time for
human decisions.

### FastAPI wiring

`create_app` accepts an optional `ReviewRepository`. Production wiring creates a
`SQLiteReviewRepository` from `Settings.database_path`; tests inject a
temporary repository. The repository is initialized during app construction so
the existing `TestClient` pattern and normal server startup both receive a
ready schema.

The GET and POST review routes delegate to `ReviewService`. They contain no SQL
or state-reconstruction logic.

## Data Model

SQLite schema version 2 contains one append-only table:

| Column | Type | Constraint |
| --- | --- | --- |
| `sequence` | INTEGER | Primary key, autoincrement |
| `decision_id` | TEXT | Unique, non-null |
| `request_id` | TEXT | Unique, non-null |
| `incident_id` | TEXT | Non-null |
| `packet_version` | TEXT | Non-null |
| `packet_generated_at` | TEXT | Non-null UTC ISO 8601 |
| `decision` | TEXT | Non-null, approved or needs-changes |
| `reviewer` | TEXT | Non-null |
| `note` | TEXT | Non-null |
| `decided_at` | TEXT | Non-null UTC ISO 8601 |

An index on `(incident_id, packet_version, sequence)` supports chronological
history reads. Schema setup uses `PRAGMA user_version` so later changes can add
explicit forward migrations. Version 1 databases are migrated in place;
existing rows use their decision time as the safest available packet timestamp.

Rows are never updated or deleted by application code. The latest row
determines current readiness, while every earlier row remains visible in the
audit timeline.

## Idempotency

`ReviewDecisionRequest` gains a required UUID `request_id`. The web client
creates it with `crypto.randomUUID()` once per user action.

Submitting the same request ID with the same payload does not append another
timeline event; the service returns the current state reconstructed from the
ledger. Reusing the request ID with different content raises an idempotency
conflict and returns HTTP 409. This makes network retries safe without hiding
contradictory reviewer actions.

## Data Flow

### Read current review

1. Build the current deterministic incident, analysis, and packet.
2. Compute the stable packet version.
3. Build the unresolved base review state.
4. Load decisions for the incident and packet version in sequence order.
5. When history exists, use its first `packet_generated_at` value for the base
   audit events.
6. Apply every decision to the base state.
7. Return current readiness, release checks, and complete audit history.

### Record a decision

1. Validate the request model and review-domain rules.
2. Create an immutable record with a server-generated decision ID and UTC time.
3. Append it transactionally, enforcing request-ID uniqueness.
4. Reload the complete ordered history.
5. Reconstruct and return the current review state.

If evidence changes between decisions, the new packet version receives no
prior decisions and starts in `needs-changes`. Historical rows for the previous
version remain intact.

## Error Handling

- Invalid decisions continue to return HTTP 400 with the existing structured
  `bad_request` payload.
- A reused request ID with a different payload returns HTTP 409 and
  `idempotency_conflict`.
- SQLite connection, schema, read, or write failures return HTTP 503 and
  `review_store_unavailable`.
- API responses do not expose database paths, SQL statements, or raw SQLite
  messages.
- Failed writes roll back and never produce a partial audit record.

The frontend keeps the prior review state visible and shows its existing
action-level error message when a decision cannot be recorded.

## Configuration

`Settings` gains:

```text
DATABASE_PATH=./data/batchhelm.db
```

The parent directory is created when needed. Local database files, WAL files,
and shared-memory files remain excluded from Git.

No new Python dependency is required.

## Testing Strategy

Tests will be written before implementation and will cover:

1. Stable packet versions across different generation timestamps.
2. A changed evidence section producing a different packet version.
3. SQLite schema creation and ordered append/read behavior.
4. A decision surviving repository and application re-instantiation.
5. Version 1 databases migrating to schema version 2.
6. Packet-generation audit time surviving application re-instantiation.
7. POST followed by GET returning the persisted approved state.
8. Multiple decisions remaining in the timeline with the latest decision
   controlling readiness.
9. Identical concurrent retries producing one stored event.
10. Conflicting reuse of a request ID returning HTTP 409.
11. Repository failure returning a sanitized HTTP 503 response.
12. Existing backend tests and the frontend production build remaining green.

Tests use temporary on-disk databases rather than SQLite `:memory:` databases
so connection and restart behavior matches production semantics.

## Documentation

The README, architecture document, environment example, and API documentation
will explain:

- the SQLite default and `DATABASE_PATH`;
- the append-only review ledger;
- stable packet-version behavior;
- request idempotency;
- the Postgres-ready repository boundary;
- a demo sequence proving approval survives an API restart.

## Acceptance Criteria

- Approving the demo packet and restarting the API preserves the approved state.
- Refreshing the browser preserves the full review timeline.
- Packet-generation audit time remains stable after an API restart.
- Requesting changes after approval appends a second event and makes the packet
  not ready without erasing the approval event.
- Replaying the same request does not duplicate an event.
- Changed packet evidence requires a new review.
- Database failures produce a sanitized structured response.
- The database and its WAL artifacts are not tracked by Git.
- All backend tests, frontend checks, attribution scans, and whitespace checks
  pass.
