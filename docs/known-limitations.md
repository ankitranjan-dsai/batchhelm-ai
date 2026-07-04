# Known Limitations And Future Work

BatchHelm distinguishes the production-shaped workflow implemented in this
repository from the infrastructure and product breadth still required for a
commercial rollout.

## What Is Real

- Multipart incident intake for text, PDF, scanned PDF, image notices, UTF-8
  inventory CSVs, and optional shelf evidence, with signature and byte limits.
- Immutable artifact storage, SHA-256 metadata, restart-safe extraction,
  field-level provenance, optimistic reviewer versions, and confirmed incident
  snapshots in a dedicated SQLite repository.
- A nine-specialist agent society running as a DAG with parallel waves, retries,
  failure isolation, typed checkpoints, persist-before-publish events, SSE
  replay, and restart recovery.
- Intake-backed orchestration that resolves the confirmed incident and exact
  optional shelf artifact instead of substituting bundled demo data.
- Qwen-backed extraction, inventory reasoning, risk, communication, shelf
  interpretation, and management briefing through validated typed contracts.
- Persistent supplier memory and an idempotent append-only review ledger.
- Structured logs, request IDs, bounded provider retries, telemetry, sanitized
  errors, Docker images, Compose, CI, and an Alibaba Cloud deployment path.

## Limitations

- **No multi-incident operations queue.** The API can persist independent
  intakes, but the dashboard manages one accepted intake session at a time. It
  does not yet provide assignment, prioritization, search, or queue views.
- **No mailbox or vendor-portal ingestion.** Operators upload files manually.
  Automatic email attachment ingestion and supplier connectors are future work.
- **Fallback is the default without credentials.** No-key runs exercise the
  same schemas and lifecycle but do not prove live Qwen latency or variability.
  Real-image fallback is intentionally neutral and requires manual review.
- **Authentication is simulated.** Reviewer identity comes from
  `REVIEWER_ROLE`; there is no login, tenant isolation, or RBAC.
- **SQLite and local artifacts require one API replica.** The repository
  interfaces are ready for shared adapters, but Postgres, object storage, and
  distributed extraction or orchestration claims are not implemented.
- **Rate limiting is per process.** A load-balanced deployment needs a shared
  limiter such as Redis.
- **Evidence export is Markdown.** The supplier notice input can be PDF, but the
  generated audit evidence artifact is currently Markdown rather than a
  generated PDF.
- **No automated browser end-to-end suite.** Hooks and components have Vitest
  coverage and the interface is manually verified at desktop and mobile sizes,
  but Playwright CI coverage remains future work.

## Future Work

1. Multi-incident inbox, queue assignment, and cross-store portfolio views.
2. Email mailbox, supplier portal, and webhook ingestion.
3. Authentication, tenant isolation, and reviewer RBAC.
4. ApsaraDB RDS Postgres adapters, Object Storage Service artifacts, and
   distributed worker leases.
5. Shared rate limiting, horizontal ACK scaling, and load testing.
6. Generated PDF evidence export and automated browser end-to-end tests.
