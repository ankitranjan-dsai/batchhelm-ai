# Qwen Cloud Integration

BatchHelm uses Qwen Cloud through its OpenAI-compatible chat API. The
integration is isolated in `services/api/v1/src/batchhelm_api/qwen.py` so the rest
of the product can use typed workflow outputs without depending on
provider-specific request details.

Official reference:

- Qwen Cloud first API call:
  `https://docs.qwencloud.com/developer-guides/getting-started/first-api-call`
- Qwen Cloud structured output:
  `https://docs.qwencloud.com/developer-guides/text-generation/structured-output`

## Environment Variables

Set these values in your runtime environment or a local `.env` file:

```bash
QWEN_API_KEY=your-model-studio-key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_TEXT_MODEL=qwen3.7-plus
QWEN_VISION_MODEL=qwen3-vl-plus
QWEN_PROOF_TOKEN=a-long-random-deployment-proof-token
ORCHESTRATION_DATABASE_PATH=./data/orchestration.db
INTAKE_DATABASE_PATH=./data/intake.db
QWEN_PROOF_DATABASE_PATH=./data/qwen-proof.db
UPLOAD_DIR=./data/uploads
VITE_API_BASE_URL=http://localhost:8000
```

The API key is never committed. BatchHelm reads it at runtime through Pydantic settings.

## Runtime Modes

BatchHelm supports two modes:

- `live`: `QWEN_API_KEY` is configured, so the backend can call Qwen Cloud.
- `demo-fallback`: no key is configured, so the backend returns deterministic structured demo outputs.

The fallback mode exists so demos, tests, and screenshots stay reliable without external credentials. It does not replace the Qwen integration; it keeps the product usable while credentials are absent.

`mode: "live"` means a key is configured. It is not a network-success claim.
Use the persisted verification receipt below for that stronger evidence.

## Live Provider Verification

The billable verification endpoint is separate from normal status:

```bash
curl -fsS -X POST \
  -H "X-BatchHelm-Proof-Token: $QWEN_PROOF_TOKEN" \
  http://localhost:8000/api/v1/qwen/verify

curl -fsS http://localhost:8000/api/v1/qwen/proof
```

The first call uses Qwen Cloud and stores a redacted receipt. The second reads
that receipt without spending tokens. The receipt contains provider metadata,
latency, time, and a response fingerprint, but never the request, response
body, or credentials.

## Qwen Drives The Workflow

Qwen is the reasoning engine of the agent society, not a side feature. The
typed task layer in `qwen_tasks.py` turns each workflow step into a structured
Qwen call whose output is validated against a Pydantic schema and repaired to a
deterministic fallback on any failure:

| Workflow step | Qwen task | Schema |
| --- | --- | --- |
| Recall notice → criteria | `extract_recall` | `RecallExtraction` |
| Inventory match reasoning | `assess_inventory_match` | `InventoryMatchReasoning` |
| Risk classification | `assess_risk` | `RiskAssessment` |
| Customer notice draft | `draft_customer_notice` | `CustomerNoticeContent` |
| Management briefing | `generate_briefing` | `ManagementBriefing` |
| Shelf-photo interpretation | `inspection.inspect_image` | `ShelfInspectionResult` |

For real intake notices, the service first extracts bounded text from text
files and text PDFs. Scanned PDFs and image notices are rendered and sent to
the vision model. Each extracted field is paired with an artifact ID, source
locator, confidence, and provider source before it reaches review.

Validation rule: if Qwen is unconfigured, errors, or returns JSON that fails
schema validation, the task returns the deterministic fallback and marks the
output `source = deterministic`. Valid live output is marked `source = qwen`.
This is surfaced everywhere — API fields, agent events, and the dashboard badges.

The fallback policy distinguishes bundled demo data from arbitrary uploads.
Literal text parsing may recover values that are actually present in a real
notice, but it never copies seeded demo criteria into an uploaded incident.
Likewise, failure while inspecting a real shelf image returns `recall_match =
null`, zero confidence, and `review_required = true`; it cannot fabricate a
positive match.

## Provider Surface (API)

- `GET /api/v1/qwen/status` — provider mode + configured models
- `POST /api/v1/qwen/verify` — protected real-call verification + persisted receipt
- `GET /api/v1/qwen/proof` — latest public redacted verification receipt
- `POST /api/v1/intakes` — stores a real packet and starts typed extraction
- `GET /api/v1/intakes/{intake_id}` — returns extraction status and provenance
- `PATCH /api/v1/intakes/{intake_id}/draft` — saves reviewer evidence
- `POST /api/v1/intakes/{intake_id}/confirm` — freezes the incident snapshot
- `POST /api/v1/intakes/{intake_id}/runs` — starts the snapshot's durable run
- `POST /api/v1/incidents/demo/runs` — idempotently starts one durable Qwen-driven run
- `GET /api/v1/orchestration/runs/{run_id}` — persisted run status and result
- `GET /api/v1/orchestration/runs/{run_id}/events` — ordered replay plus live SSE
- `POST /api/v1/incidents/demo/run` — synchronous compatibility run
- `GET /api/v1/incidents/demo/run/stream` — deprecated compatibility stream
- `POST /api/v1/briefing/demo` — management briefing
- `GET /api/v1/inspections/demo`, `POST /api/v1/inspections/shelf-photo` — vision
- `POST /api/v1/qwen/recall-summary` — single-shot structured summary

The gateway sends chat-completion payloads with:

- model from `QWEN_TEXT_MODEL` / `QWEN_VISION_MODEL`
- system and user messages
- low temperature for operational consistency
- JSON-object response formatting
- bounded retries on 5xx/transport errors with latency telemetry

## Vision Use

BatchHelm routes shelf and stockroom images to the configured vision model through the backend inspection endpoint. The workflow is:

1. Staff uploads a shelf, cooler, or invoice image.
2. Backend stores the file and records an audit event.
3. Vision inspection extracts product name, UPC, lot code, best-by date, and confidence.
4. Workflow engine compares extracted values against recall criteria.
5. Low-confidence matches are routed to human review.

For intake-backed orchestration, the Shelf Vision Agent resolves the exact
artifact stored with the confirmed incident. The bundled demo image is only
eligible for the explicit demo route.

Current upload policy:

- accepted media types: JPEG, PNG, WebP
- maximum file size: 8 MB
- generated server filenames only
- SHA-256 metadata attached to the intake record
- raw image contents are not written to logs

## Local Verification

```bash
cd services/api
uv run pytest -q
uv run uvicorn batchhelm_api.app:app --reload
```

Then open:

- `http://localhost:8000/health`
- `http://localhost:8000/api/v1/qwen/status`
- `http://localhost:8000/api/v1/inspections/demo`
- `http://localhost:8000/docs`
