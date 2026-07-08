# BatchHelm AI

**BatchHelm AI is an autonomous recall command center for product batches, shelves, and store teams.**

When a food or consumer-product recall arrives, small operators need to know whether they are affected, where the product is, who needs to act, who may need to be notified, and what evidence must be retained. BatchHelm turns recall notices, invoices, inventory files, shelf photos, and task completion records into a coordinated response workflow.

## Vision

BatchHelm is designed for small grocery chains, restaurants, pharmacies, cafeterias, and distributors that do not have enterprise recall-management tooling. The product focuses on urgent operational clarity:

- identify affected products and batches
- match recall notices against invoices, POS exports, and catalog data
- inspect shelf or stockroom photos for labels, dates, UPCs, and lot codes
- create removal, quarantine, disposal, refund, and customer-notice tasks
- preserve evidence in an audit-ready packet
- remember supplier aliases, store layouts, historical decisions, and recurring false positives

## Hackathon Track Fit

BatchHelm is built for the **Qwen Global AI Hackathon** and runs on Qwen models
through Qwen Cloud's OpenAI-compatible endpoint.

**Primary track — Autopilot Agent.** BatchHelm runs an end-to-end recall
response workflow: intake → Qwen extraction → inventory matching → vision →
risk → tasks → customer notice → compliance evidence, with a human review gate
at the critical step.

**Secondary track — Agent Society.** Nine specialist agents, coordinated by an
orchestrator, run as a DAG with parallel waves, retries, failure isolation,
durable checkpoints, and live event streaming. The orchestrator reconciles
disagreement between Qwen and the authoritative inventory.

Supporting capabilities (honest scope):

- **Memory:** the Memory Agent persists supplier aliases, decisions, and false
  positives in SQLite and surfaces insights from prior runs.
- **Mobile intake:** the shelf-photo endpoint accepts real uploads
  (JPEG/PNG/WebP, up to 8 MB) for in-store inspection; queued/offline sync is
  future work and BatchHelm does not claim the hardware-focused EdgeAgent track.
- **Executive communication:** the orchestrator generates a management briefing
  from incident state with Qwen and a deterministic fallback.

## How It Works

**Files.** An operator uploads a recall notice, inventory CSV, and optional
shelf photo. BatchHelm stores the artifacts immutably, parses the packet, and
uses Qwen text or vision extraction when configured.

**Review.** The workspace presents recall criteria, inventory totals, rejected
rows, confidence, and source locators. Reviewer corrections are versioned with
optimistic concurrency and recorded as `reviewer` evidence.

**Launch.** Confirmation compiles an immutable incident snapshot. A separate
request UUID starts exactly one orchestration run for that snapshot, and the
dashboard adopts its run ID, status URL, and replayable event stream.

The dashboard subscribes to
`GET /api/v1/orchestration/runs/{run_id}/events`, which replays persisted events
before following live Server-Sent Events. Refreshing or reconnecting resumes
the same intake and run rather than launching another. Every output is tagged
with its source - `qwen`, `deterministic`, `memory`, or `reviewer` - so model
output is distinguishable from fallback.

Qwen drives extraction, inventory-match reasoning, risk classification, the
customer notice, shelf-photo interpretation, and the briefing. Each call is
validated against a Pydantic schema and repaired to a deterministic fallback on
failure, so the workflow never breaks. See
[docs/qwen-integration.md](docs/qwen-integration.md),
[docs/architecture.md](docs/architecture.md), and
[docs/sample-incident-walkthrough.md](docs/sample-incident-walkthrough.md).

## Real Incident Intake

The intake API accepts:

- recall notices: text, PDF, JPEG, PNG, or WebP, up to 12 MB;
- inventory: UTF-8 CSV, up to 4 MB and 5,000 data rows;
- optional shelf evidence: JPEG, PNG, or WebP, up to 8 MB;
- complete multipart packet: up to 24 MB.

Text PDFs are extracted directly. Scanned PDFs and image notices are rendered
through the vision path. Inventory headers are normalized from supported
aliases, invalid rows are isolated as review warnings, and duplicate inventory
identities are rejected without discarding valid rows.

Try the committed packet in [`sample-data`](sample-data/README.md). It contains
a supplier PDF, a six-row inventory export totaling 23 units, an intentionally
invalid export, and a readable cooler image.

## Product Surface

The current product includes:

- Files -> Review -> Launch incident-intake workspace
- Recall dashboard and incident details
- Affected inventory map
- Agent Mission Control with replayable event timeline
- Inspectable Qwen Cloud evidence control with redacted persisted receipts
- Shelf-photo evidence inspection
- Staff task board and customer notice draft
- Evidence packet preview and durable reviewer approval gate
- Management briefing, memory, and supplier-alias insights

## Technology Direction

- Frontend: React, Vite, TypeScript
- Backend: FastAPI, Python, Pydantic
- Model integration: Qwen Cloud via configurable provider interface
- Storage: SQLite for local demo, Postgres-ready repository layer
- Documents: text/PDF/image notice intake and generated Markdown evidence packet
- Deployment target: Alibaba Cloud Container Service or Elastic Compute Service with Docker

## Run The Frontend

```bash
cd apps/web
npm install
npm run dev
```

Open `http://localhost:5173`.

## Verify The Frontend

```bash
cd apps/web
npm test
npm run typecheck
npm run build
```

The current dashboard implementation is visually tracked against:

- `docs/design-assets/batchhelm-dashboard-concept.png`
- `docs/design-assets/screenshots/dashboard-desktop-native.png`
- `docs/design-assets/screenshots/dashboard-mobile.png`
- `docs/design-assets/screenshots/mission-control-desktop.png`
- `docs/design-assets/screenshots/mission-control-mobile.png`
- [Populated intake files - desktop](docs/design-assets/screenshots/intake-files-desktop.png)
- [Provenance and warning review - desktop](docs/design-assets/screenshots/intake-review-desktop.png)
- [Inventory warning review - mobile](docs/design-assets/screenshots/intake-review-mobile.png)

## Run The Backend

```bash
cd services/api
uv sync --extra dev
uv run uvicorn batchhelm_api.app:app --reload
```

Open `http://localhost:8000/docs` for the API reference.

## Verify The Backend

```bash
cd services/api
uv run pytest -q
```

Important endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `POST` | `/api/v1/intakes` | Idempotently stores a multipart packet and starts extraction |
| `GET` | `/api/v1/intakes/{intake_id}` | Returns durable extraction, evidence, draft, and status |
| `PATCH` | `/api/v1/intakes/{intake_id}/draft` | Saves a version-checked reviewer correction |
| `POST` | `/api/v1/intakes/{intake_id}/confirm` | Compiles an immutable confirmed incident snapshot |
| `POST` | `/api/v1/intakes/{intake_id}/runs` | Idempotently launches the confirmed incident |
| `GET` | `/api/v1/incidents/demo` | Returns the demo recall input |
| `POST` | `/api/v1/incidents/demo/analyze` | Deterministic baseline analysis |
| `POST` | `/api/v1/incidents/demo/runs` | Idempotently starts one durable orchestration run |
| `GET` | `/api/v1/orchestration/runs/{run_id}` | Returns persisted run status and terminal result |
| `GET` | `/api/v1/orchestration/runs/{run_id}/events` | Replays ordered events, then follows the live SSE stream |
| `POST` | `/api/v1/incidents/demo/run` | Synchronous compatibility endpoint for a full run |
| `GET` | `/api/v1/incidents/demo/run/stream` | Deprecated compatibility SSE endpoint |
| `GET` | `/api/v1/agents` | Lists the agent society and dependencies |
| `GET` | `/api/v1/memory` | Returns persisted memory records |
| `POST` | `/api/v1/briefing/demo` | Generates the management briefing |
| `GET` | `/api/v1/telemetry` | In-process telemetry counters |
| `GET` | `/api/v1/inspections/demo` | Returns a demo shelf inspection result |
| `POST` | `/api/v1/inspections/shelf-photo` | Inspects an uploaded shelf photo |
| `GET` | `/api/v1/evidence/demo-packet` | Returns a structured Markdown evidence packet preview |
| `GET` | `/api/v1/evidence/demo-packet.md` | Downloads the same packet as an audit-ready Markdown attachment |
| `GET` | `/api/v1/evidence/demo-review` | Returns packet readiness, blockers, release checks, and audit history |
| `POST` | `/api/v1/evidence/demo-review/decision` | Persists an idempotent reviewer decision and returns the complete audit history |
| `GET` | `/api/v1/qwen/status` | Reports Qwen gateway mode and configured models |
| `POST` | `/api/v1/qwen/verify` | Performs a token-protected live Qwen verification and stores a redacted receipt |
| `GET` | `/api/v1/qwen/proof` | Returns the latest persisted redacted Qwen receipt without another model call |
| `POST` | `/api/v1/qwen/recall-summary` | Generates a structured recall summary |
| `POST` | `/api/v1/notices/customer-draft` | Generates a customer notice draft |

### Durable Review Storage

Review decisions are stored in an append-only SQLite ledger at
`DATABASE_PATH` (default `./data/batchhelm.db`). Evidence packets expose a
canonical SHA-256 `packet_version` that excludes generation timestamps, so an
approval survives packet regeneration while changed evidence starts a new
review. The ledger also pins the packet's original audit timestamp so timeline
chronology remains stable after an API restart.

Each decision request carries a UUID. Replaying the same request is safe;
reusing its UUID for different content returns HTTP 409. Storage failures
return a sanitized HTTP 503 response without database details. The repository
interface is ready for a future Postgres adapter.

Shelf-photo inspection accepts JPEG, PNG, and WebP files up to 8 MB.

### Durable Intake Storage

Intake lifecycle state, versions, artifact metadata, extraction evidence, and
confirmed incident snapshots are stored in a dedicated SQLite WAL database at
`INTAKE_DATABASE_PATH` (default `./data/intake.db`). Accepted files are written
under `UPLOAD_DIR/intakes/{intake_id}` with generated names and SHA-256
digests; staging directories are never treated as accepted artifacts.

The create endpoint is idempotent by request UUID and packet fingerprint.
Extraction resumes after API startup if a durable intake remains in
`uploaded` or `extracting`. Reviewer updates require the current version, so a
stale browser cannot overwrite a newer correction. Confirmation freezes the
validated criteria and inventory into the incident used by orchestration.

### Durable Orchestration Storage

Runs, typed wave checkpoints, ordered events, terminal results, and sanitized
failure states are stored in a separate SQLite WAL database at
`ORCHESTRATION_DATABASE_PATH` (default `./data/orchestration.db`). Events are
persisted before publication. SSE clients can replay from `Last-Event-ID` or
the `after` query parameter, and API startup resumes non-terminal runs from the
last completed wave.

Worker ownership and lifecycle recovery are currently single-process. Intake
and arbitrary incident run state survive an API restart, including resolution
of the confirmed snapshot and optional shelf artifact. A horizontally scaled
deployment requires shared storage and distributed worker coordination.

## Evidence Review Demo

1. Open the Evidence panel and select **Review**.
2. Inspect the blocking release checks and select **Approve packet**.
3. Refresh the browser and confirm the approved state and timeline remain.
4. Restart the API, refresh again, and confirm the approval is still present.
5. Select **Request changes** and confirm both human decisions remain in order.
6. Select **Packet** to inspect or download the unchanged Markdown evidence artifact.

## Full Verification

```bash
cd services/api
uv run pytest -q

cd ../../apps/web
npm test
npm run typecheck
npm run build

cd ../..
scripts/check-attribution.sh
```

## Verify Repository Attribution Language

```bash
scripts/check-attribution.sh
```

## Deployment

**Live on Alibaba Cloud ECS:** [http://47.84.199.208](http://47.84.199.208)
— see [docs/alibaba-cloud-proof.md](docs/alibaba-cloud-proof.md) for the
captured `/health`, `/api/v1/qwen/status` (`mode: "live"`), and `/api/v1/qwen/proof`
evidence.

BatchHelm ships with a root `Dockerfile` (API), `apps/web/Dockerfile`
(dashboard), and `docker-compose.yml`:

```bash
cp .env.example .env      # set QWEN_API_KEY for live Qwen mode
docker compose up -d --build
# dashboard on :8080, API on :8000
```

Alibaba Cloud (ECS / ACK) deployment is documented in
[docs/deployment-alibaba-cloud.md](docs/deployment-alibaba-cloud.md), and the
explicit record of Alibaba Cloud usage is in
[docs/alibaba-cloud-proof.md](docs/alibaba-cloud-proof.md).

The production ECS path is reproducible:

```bash
export BATCHHELM_HOST=ecs-user@ecs-address
export QWEN_API_KEY='the Qwen Cloud pay-as-you-go key'
export QWEN_PROOF_TOKEN="$(openssl rand -hex 32)"
bash deploy/alibaba-ecs/deploy.sh
```

The script deploys the exact local commit, waits for health, performs one
protected live Qwen call, and prints the public redacted proof receipt.

## Submission

- Track: **Autopilot Agent** (primary), **Agent Society** (secondary)
- Live deployment: [http://47.84.199.208](http://47.84.199.208)
- Checklist: [docs/submission-checklist.md](docs/submission-checklist.md)
- Demo script: [docs/demo-script.md](docs/demo-script.md)
- Sample artifacts: [evidence packet](docs/sample-evidence-packet.md) ·
  [incident walkthrough](docs/sample-incident-walkthrough.md)
- Known limitations: [docs/known-limitations.md](docs/known-limitations.md)
- Demo video: not yet recorded; required before the July 9 submission deadline

## Author

Ankit Ranjan

## License

MIT
