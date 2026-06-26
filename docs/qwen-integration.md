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

## Current Provider Surface

The first backend milestone exposes:

- `GET /api/qwen/status`
- `POST /api/qwen/recall-summary`

The gateway sends chat-completion payloads with:

- model from `QWEN_TEXT_MODEL`
- system and user messages
- low temperature for operational consistency
- JSON-object response formatting

## Planned Vision Use

The next Qwen milestone will route shelf and stockroom images to the configured vision model. The intended workflow is:

1. Staff uploads a shelf, cooler, or invoice image.
2. Backend stores the file and records an audit event.
3. Vision inspection extracts product name, UPC, lot code, best-by date, and confidence.
4. Workflow engine compares extracted values against recall criteria.
5. Low-confidence matches are routed to human review.

## Local Verification

```bash
cd services/api
uv run pytest -q
uv run uvicorn batchhelm_api.app:app --reload
```

Then open:

- `http://localhost:8000/health`
- `http://localhost:8000/api/qwen/status`
- `http://localhost:8000/docs`
