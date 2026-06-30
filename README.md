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
via Alibaba Cloud Model Studio's OpenAI-compatible endpoint.

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
- **Edge / mobile:** the shelf-photo endpoint accepts real uploads (JPEG/PNG/WebP,
  ≤8 MB) for in-store inspection; queued/offline sync is future work.
- **AI Showrunner:** the orchestrator generates a management briefing from
  incident state (Qwen with deterministic fallback).

## How It Works

`POST /api/incidents/demo/run` runs the full agent society and returns the
timeline, per-agent results, the assembled analysis, and the briefing.
`GET /api/incidents/demo/run/stream` streams the same run as Server-Sent Events
so the dashboard shows live mission control. Every output is tagged with its
source — `qwen`, `deterministic`, `memory`, or `reviewer` — so it is always
clear what is real model output versus deterministic fallback.

Qwen drives extraction, inventory-match reasoning, risk classification, the
customer notice, shelf-photo interpretation, and the briefing. Each call is
validated against a Pydantic schema and repaired to a deterministic fallback on
failure, so the workflow never breaks. See
[docs/qwen-integration.md](docs/qwen-integration.md),
[docs/architecture.md](docs/architecture.md), and
[docs/sample-incident-walkthrough.md](docs/sample-incident-walkthrough.md).

## Initial Product Surface

The first release will be a premium operations dashboard with these core screens:

- Recall inbox and incident details
- Affected inventory map
- Agent workflow timeline
- Shelf-photo inspection queue
- Staff task board
- Customer notice composer
- Evidence packet preview
- Evidence reviewer approval gate and audit trail
- Memory and alias manager

## Technology Direction

- Frontend: React, Vite, TypeScript
- Backend: FastAPI, Python, Pydantic
- Model integration: Qwen Cloud via configurable provider interface
- Storage: SQLite for local demo, Postgres-ready repository layer
- Documents: generated Markdown/PDF evidence packet
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
npm run typecheck
npm run build
```

The current dashboard implementation is visually tracked against:

- `docs/design-assets/batchhelm-dashboard-concept.png`
- `docs/design-assets/screenshots/dashboard-desktop-native.png`
- `docs/design-assets/screenshots/dashboard-mobile.png`

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
| `GET` | `/api/incidents/demo` | Returns the demo recall input |
| `POST` | `/api/incidents/demo/analyze` | Deterministic baseline analysis |
| `POST` | `/api/incidents/demo/run` | Runs the full multi-agent orchestration |
| `GET` | `/api/incidents/demo/run/stream` | Live SSE stream of agent events |
| `GET` | `/api/agents` | Lists the agent society and dependencies |
| `GET` | `/api/memory` | Returns persisted memory records |
| `POST` | `/api/briefing/demo` | Generates the AI Showrunner briefing |
| `GET` | `/api/telemetry` | In-process telemetry counters |
| `GET` | `/api/inspections/demo` | Returns a demo shelf inspection result |
| `POST` | `/api/inspections/shelf-photo` | Inspects an uploaded shelf photo |
| `GET` | `/api/evidence/demo-packet` | Returns a structured Markdown evidence packet preview |
| `GET` | `/api/evidence/demo-packet.md` | Downloads the same packet as an audit-ready Markdown attachment |
| `GET` | `/api/evidence/demo-review` | Returns packet readiness, blockers, release checks, and audit history |
| `POST` | `/api/evidence/demo-review/decision` | Persists an idempotent reviewer decision and returns the complete audit history |
| `GET` | `/api/qwen/status` | Reports Qwen gateway mode and configured models |
| `POST` | `/api/qwen/recall-summary` | Generates a structured recall summary |
| `POST` | `/api/notices/customer-draft` | Generates a customer notice draft |

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
npm run build

cd ../..
scripts/check-attribution.sh
```

## Verify Repository Attribution Language

```bash
scripts/check-attribution.sh
```

## Deployment

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

## Submission

- Track: **Autopilot Agent** (primary), **Agent Society** (secondary)
- Checklist: [docs/submission-checklist.md](docs/submission-checklist.md)
- Demo script: [docs/demo-script.md](docs/demo-script.md)
- Sample artifacts: [evidence packet](docs/sample-evidence-packet.md) ·
  [incident walkthrough](docs/sample-incident-walkthrough.md)
- Known limitations: [docs/known-limitations.md](docs/known-limitations.md)
- Demo video: _add link after recording_

## Author

Ankit Ranjan

## License

MIT
