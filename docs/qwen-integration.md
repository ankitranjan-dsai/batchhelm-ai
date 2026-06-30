# Qwen Cloud Integration

BatchHelm uses Qwen Cloud through Alibaba Cloud Model Studio's OpenAI-compatible chat API. The integration is isolated in `services/api/src/batchhelm_api/qwen.py` so the rest of the product can use typed workflow outputs without depending on provider-specific request details.

Official reference:

- Alibaba Cloud Model Studio compatibility guide: `https://www.alibabacloud.com/help/en/model-studio/compatibility-of-openai-with-dashscope`

## Environment Variables

Set these values in your runtime environment or a local `.env` file:

```bash
QWEN_API_KEY=your-model-studio-key
QWEN_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1
QWEN_TEXT_MODEL=qwen-plus
QWEN_VISION_MODEL=qwen-vl-plus
VITE_API_BASE_URL=http://localhost:8000
```

The API key is never committed. BatchHelm reads it at runtime through Pydantic settings.

## Runtime Modes

BatchHelm supports two modes:

- `live`: `QWEN_API_KEY` is configured, so the backend can call Qwen Cloud.
- `demo-fallback`: no key is configured, so the backend returns deterministic structured demo outputs.

The fallback mode exists so demos, tests, and screenshots stay reliable without external credentials. It does not replace the Qwen integration; it keeps the product usable while credentials are absent.

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

Validation rule: if Qwen is unconfigured, errors, or returns JSON that fails
schema validation, the task returns the deterministic fallback and marks the
output `source = deterministic`. Valid live output is marked `source = qwen`.
This is surfaced everywhere — API fields, agent events, and the dashboard badges.

## Provider Surface (API)

- `GET /api/qwen/status` — provider mode + configured models
- `POST /api/incidents/demo/run` — full multi-agent run (Qwen-driven)
- `GET /api/incidents/demo/run/stream` — live SSE event stream
- `POST /api/briefing/demo` — management briefing
- `GET /api/inspections/demo`, `POST /api/inspections/shelf-photo` — vision
- `POST /api/qwen/recall-summary` — single-shot structured summary

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

Current upload policy:

- accepted media types: JPEG, PNG, WebP
- maximum file size: 8 MB
- generated server filenames only
- raw image contents are not written to logs

## Local Verification

```bash
cd services/api
uv run pytest -q
uv run uvicorn batchhelm_api.app:app --reload
```

Then open:

- `http://localhost:8000/health`
- `http://localhost:8000/api/qwen/status`
- `http://localhost:8000/api/inspections/demo`
- `http://localhost:8000/docs`
