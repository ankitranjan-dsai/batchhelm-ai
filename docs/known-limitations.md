# Known Limitations & Future Work

BatchHelm is honest about what is real today versus what is scaffolded or
deferred. This is a hackathon build, not a finished commercial product.

## What is real

- A real agent society (9 specialists + orchestrator) running as a DAG with
  parallel waves, retries, failure isolation, durable per-agent checkpoints, and
  live event streaming.
- Qwen drives recall extraction, inventory-match reasoning, risk classification,
  customer-notice drafting, shelf-photo interpretation, and the management
  briefing. Every output is validated against a Pydantic schema and falls back
  deterministically if Qwen is unavailable or returns an unusable shape.
- Persistent memory (supplier aliases, decisions, false positives) and an
  idempotent, append-only review ledger that survives restarts.
- Production hardening: structured JSON logs, request IDs, fixed-window rate
  limiting, provider retries with telemetry, sanitized errors, upload limits.
- Docker images, Compose, CI, and an Alibaba Cloud deployment path.

## Limitations

- **Single bundled incident.** The workflow runs against one demo incident.
  Multi-incident intake and real document upload (PDF/email parsing) are not yet
  wired; `notice_text` is provided as structured demo data.
- **Demo-fallback by default.** Without `QWEN_API_KEY`, all model steps use
  deterministic fallbacks. This is intentional for reliable demos and tests, but
  it means a no-key run does not exercise live Qwen latency or variability.
- **Authentication is simulated.** Reviewer identity is a configurable role
  (`REVIEWER_ROLE`), not real auth. There is no user login or RBAC yet.
- **Memory is SQLite.** The repository layer is Postgres-ready (interface-based)
  but the Postgres adapter is not implemented; multi-node deployments would need
  it or a shared volume.
- **Vision uses a placeholder image in the demo run.** The shelf-photo endpoint
  accepts real uploads, but the orchestration demo passes a placeholder so runs
  are deterministic.
- **No automated browser/E2E tests.** Frontend is covered by typecheck + build;
  backend has unit/integration/orchestration tests. Playwright E2E is future work.
- **Rate limiting is per-process, in-memory.** Fine for a single instance; a
  shared store (e.g., Redis) would be needed behind a load balancer.

## Future work

1. Real recall-notice ingestion (email/PDF) with Qwen document parsing.
2. Postgres (ApsaraDB RDS) adapter for the review ledger and memory.
3. Authentication + reviewer RBAC.
4. Multi-incident dashboard and queue.
5. Playwright end-to-end tests and load testing.
6. Distributed rate limiting and horizontal scaling on ACK.
