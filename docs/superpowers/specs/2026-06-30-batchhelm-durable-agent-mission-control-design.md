# Durable Agent Mission Control Design

**Date:** 2026-06-30
**Status:** Approved design, written specification pending review
**Owner:** Ankit Ranjan

## Summary

BatchHelm already runs nine specialist agents as an asynchronous dependency
graph and streams their activity to the dashboard. This milestone makes that
execution durable and internally consistent.

One orchestration run becomes the canonical source for the entire page. Its
identity, status, wave snapshots, agent results, final output, and ordered event
log are persisted in SQLite. The browser starts one run, subscribes to that
run's event stream, and applies its final result to both Mission Control and the
operational dashboard. A reconnect replays missed events. An API restart
resumes an interrupted run from the last completed wave.

## Existing Baseline

The current implementation already provides:

- nine typed specialist agents;
- topologically sorted parallel execution waves;
- Qwen structured-output calls with deterministic fallbacks;
- retry and dependent-agent failure isolation;
- in-memory Server-Sent Events;
- SQLite memory records and per-agent summary checkpoints;
- a live Mission Control panel;
- an assembled recall analysis and management briefing.

The current implementation has four durability and consistency gaps:

1. Every run receives a new identifier inside `Orchestrator.run`, so a caller
   cannot create a run and subscribe to it separately.
2. Agent checkpoints contain summaries but not the blackboard state required to
   resume execution.
3. Events are stored only in an in-process list and queue, so a reconnect or
   restart cannot replay them.
4. Page initialization starts one REST orchestration run while Mission Control
   starts a second streaming run. The dashboard and timeline can therefore show
   different run IDs and duplicate memory observations.

## Goals

- Start exactly one canonical orchestration run for the demo incident.
- Persist run lifecycle, completed-wave snapshots, agent results, events, and
  final output in SQLite.
- Replay events after a browser reconnect using an ordered sequence cursor.
- Resume an interrupted run after API restart without re-running completed
  waves.
- Prevent duplicate workers for the same run inside one API process.
- Keep the existing direct run endpoint temporarily compatible.
- Make the main dashboard and Mission Control render the same final result.
- Preserve source labels for Qwen, deterministic fallback, memory, and reviewer
  output.
- Retain a repository boundary that can later support Postgres.

## Non-Goals

- Distributed execution across multiple API replicas.
- Redis, Celery, Kafka, or Temporal.
- Arbitrary user-created incidents.
- Authentication and per-user run ownership.
- Resuming a model call in the middle of an agent attempt.
- Editing the DAG from the browser.

## Architecture

### Run Repository

Create an `OrchestrationRepository` protocol and a
`SQLiteOrchestrationRepository` implementation. The repository owns a separate
SQLite database, configured by `ORCHESTRATION_DATABASE_PATH` and defaulting to
`./data/orchestration.db`.

The protocol exposes operations to:

- initialize and migrate the schema;
- create an idempotent run;
- fetch a run by identifier;
- claim and release execution ownership;
- append an event with a monotonically increasing per-run sequence;
- list events after a sequence cursor;
- save a completed-wave snapshot atomically;
- mark a run completed or failed with its final result;
- list interrupted runs that are eligible for recovery.

Repository methods return domain models and do not leak SQLite rows or
exceptions through service or API layers.

### Run Service

Create an `OrchestrationService` that owns run lifecycle and in-process worker
tasks. It receives the repository and an orchestrator factory.

Responsibilities:

- create or reuse a run from an idempotency key;
- start at most one worker task per run in the current process;
- attach live subscribers without starting another run;
- recover missed events from SQLite before waiting for new events;
- resume interrupted runs from their last completed wave;
- expose immutable run snapshots to HTTP handlers;
- remove completed tasks from the local task registry.

The service does not contain agent logic. It coordinates repositories,
orchestrator execution, and subscriber notifications.

### Orchestrator

`Orchestrator.run` accepts an externally supplied `run_id`, an optional recovery
snapshot, and callbacks for events and completed waves.

At the end of each complete wave, the orchestrator serializes:

- the zero-based next wave index;
- the shared blackboard;
- all agent results produced so far;
- run start time;
- current conflict count.

The service saves this snapshot in the same transaction that advances the run's
checkpoint version. A restart reconstructs the agent context from the snapshot
and continues at the next wave. Completed agents are not called again.

If the process stops during a wave, that incomplete wave runs again. Agent
memory writes are already upserted by semantic key, so replay changes occurrence
counts but does not create duplicate records. Review-ledger decisions are not
part of orchestration and remain idempotent by request ID.

### Event Recorder

`EventRecorder` delegates sequence assignment and persistence to the run
repository. Persisting an event happens before it is published to live
subscribers.

Every SSE frame includes:

```text
id: <sequence>
event: <event-type>
data: <AgentRunEvent JSON>
```

The event identifier is the per-run sequence rather than a random UUID. Event
UUIDs remain in the JSON model for traceability.

## Persistence Model

### `orchestration_runs`

| Column | Type | Rule |
| --- | --- | --- |
| `id` | TEXT | Primary key, UUID |
| `incident_id` | TEXT | Non-null |
| `idempotency_key` | TEXT | Unique, non-null |
| `status` | TEXT | `pending`, `running`, `completed`, or `failed` |
| `provider_mode` | TEXT | Non-null |
| `started_at` | TEXT | Nullable until claimed |
| `updated_at` | TEXT | Non-null UTC timestamp |
| `finished_at` | TEXT | Nullable |
| `next_wave` | INTEGER | Non-null, defaults to zero |
| `checkpoint_version` | INTEGER | Non-null, defaults to zero |
| `snapshot_json` | TEXT | Nullable validated JSON |
| `result_json` | TEXT | Nullable validated JSON |
| `error_code` | TEXT | Nullable sanitized code |
| `error_message` | TEXT | Nullable sanitized message |

### `orchestration_events`

| Column | Type | Rule |
| --- | --- | --- |
| `run_id` | TEXT | Foreign key to `orchestration_runs` |
| `sequence` | INTEGER | Per-run ordered sequence |
| `event_id` | TEXT | Unique UUID |
| `agent` | TEXT | Non-null |
| `event_type` | TEXT | Non-null |
| `message` | TEXT | Non-null |
| `occurred_at` | TEXT | Non-null UTC timestamp |
| `source` | TEXT | Non-null |
| `data_json` | TEXT | Nullable validated JSON |

The primary key is `(run_id, sequence)`. An index on
`(run_id, sequence)` supports reconnect replay.

### Schema Rules

- SQLite uses WAL mode, foreign keys, a five-second busy timeout, and explicit
  transactions.
- The repository has its own schema version independent of review and memory
  databases.
- Invalid persisted JSON produces a sanitized repository-unavailable error.
- Run creation and idempotency-key conflict handling are atomic.

## API Contract

### Start a run

`POST /api/incidents/demo/runs`

Request:

```json
{
  "request_id": "0d05fc09-d47c-43aa-9f01-b021b26f0ac8"
}
```

Response `202 Accepted`:

```json
{
  "run_id": "run UUID",
  "status": "pending",
  "events_url": "/api/orchestration/runs/<run-id>/events",
  "result_url": "/api/orchestration/runs/<run-id>"
}
```

Replaying the same request ID returns the same run. Reusing it for a different
incident returns HTTP 409.

### Read a run

`GET /api/orchestration/runs/{run_id}`

Returns the current snapshot. A completed response includes the full
`OrchestrationResult`. Unknown runs return HTTP 404.

### Subscribe or reconnect

`GET /api/orchestration/runs/{run_id}/events?after=<sequence>`

The server first emits persisted events where `sequence > after`, then waits for
live events. It emits a terminal `result` frame for a completed run or an
`error` frame for a failed run. The standard `Last-Event-ID` header is accepted
when the query parameter is absent.

### Compatibility endpoint

`POST /api/incidents/demo/run` remains available during this milestone. It uses
the service internally, waits for completion, and returns the final result.
Documentation marks it as a synchronous compatibility endpoint.

The old `GET /api/incidents/demo/run/stream` endpoint redirects conceptually to
the new start-and-subscribe flow and is removed from the frontend.

## Recovery Flow

1. Run creation persists a `pending` row before any worker starts.
2. A worker atomically claims the run and changes it to `running`.
3. The orchestrator restores the latest validated snapshot, if present.
4. It runs the next incomplete wave.
5. A completed wave and its snapshot are persisted atomically.
6. Events are appended before subscriber publication.
7. The final result is persisted before the terminal result event is published.
8. During application startup, the service finds `pending` and stale `running`
   runs and schedules them for recovery.
9. A recovered run replays the incomplete wave and continues normally.

Within one process, an async lock and task registry prevent duplicate workers.
SQLite claim compare-and-set behavior prevents accidental double claims during
recovery. Multi-replica execution remains out of scope.

## Frontend Experience

`App` owns one run session:

1. Generate one UUID request ID.
2. Start a run through the API.
3. Pass the returned run ID to Mission Control.
4. Subscribe to that run's SSE endpoint.
5. Render persisted and live events without duplicates by sequence.
6. When the terminal result arrives, update the dashboard incident and Mission
   Control metrics from the same `OrchestrationResult`.

Mission Control displays:

- DAG stages grouped by execution wave;
- pending, running, completed, failed, and skipped status;
- live event timeline with source badges;
- attempts, duration, confidence, and fallback state;
- selected-agent reasoning and summary;
- reconnecting and recovered-run states;
- the management briefing after completion.

The implementation uses the existing design system and stylesheet rather than
component-level inline styles. On mobile, the DAG becomes a vertical stage list
and the inspector opens below the selected agent.

## Error Handling

- Unknown run: HTTP 404 with `run_not_found`.
- Idempotency conflict: HTTP 409 with `run_idempotency_conflict`.
- Repository unavailable: HTTP 503 with `orchestration_store_unavailable`.
- Invalid cursor: HTTP 400 with `invalid_event_cursor`.
- Agent failure: persisted failed agent result; dependent agents are skipped.
- Unhandled worker failure: run marked failed with a sanitized error code.
- Subscriber disconnect: worker continues and events remain persisted.
- API restart: stale run is recovered from its last complete wave.
- Qwen failure: existing typed fallback and retry behavior remains visible.

Terminal run failures use an SSE event named `run-error`. This is deliberately
different from the browser's transport-level `error` event so the frontend can
distinguish a persisted failed run from a temporary network interruption.

Raw SQLite messages, API keys, document contents, and customer data never appear
in public error responses.

## Testing Strategy

### Repository tests

- schema initialization and restart persistence;
- idempotent run creation and conflict detection;
- concurrent identical starts create one run;
- event ordering under concurrent append attempts;
- event replay after a sequence cursor;
- atomic wave snapshot replacement;
- terminal result persistence;
- corrupted JSON and database failures return sanitized exceptions.

### Orchestrator tests

- caller-supplied run ID is preserved;
- completed waves serialize recoverable blackboard and results;
- resume starts at the next wave;
- an incomplete wave is re-executed;
- completed agents are not invoked twice;
- cycles, retries, failure isolation, and reconciliation still work.

### Service and API tests

- one request ID starts one worker;
- reconnect receives only missed events;
- completed runs return an immediate terminal result;
- subscriber disconnect does not cancel execution;
- application restart recovers a stale run;
- compatibility endpoint returns the same final model;
- 404, 409, 400, and 503 responses are sanitized.

### Frontend verification

- API client typecheck;
- one run is started per page session;
- event sequences are deduplicated;
- one result updates both dashboard and Mission Control;
- desktop and mobile browser verification;
- reconnect and API-unavailable states are visually verified.

## Documentation Changes

- Update the architecture diagram with the run service and event store.
- Document the start, status, and stream API contracts.
- Update the demo script to show disconnect and replay.
- Correct the known limitations after recovery is verified.
- Add the orchestration database environment variable to `.env.example`,
  Compose, and Alibaba Cloud instructions.

## Acceptance Criteria

- A normal page load executes the demo incident exactly once.
- Dashboard metrics, agent results, events, and briefing share one run ID.
- Refreshing or reconnecting does not create a new run until the user selects
  **Run again**.
- A reconnect after sequence N receives every later event exactly once.
- Restarting the API during a run resumes from the last completed wave.
- Completed agents from earlier waves are not called again.
- The final result and event history remain readable after restart.
- All backend tests, frontend typecheck/build, attribution scan, and whitespace
  checks pass.
- Desktop and mobile screenshots show no overflow, overlap, or blank states.
- Repository attribution remains solely under Ankit Ranjan.
