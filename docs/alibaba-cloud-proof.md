# Proof Of Alibaba Cloud And Qwen Cloud Usage

This file defines the exact evidence BatchHelm can present for the Qwen Global
AI Hackathon. Code readiness and external runtime evidence are kept separate so
the submission never treats configuration as proof of a successful call.

## Evidence Status

| Evidence | Status | Authoritative location |
| --- | --- | --- |
| Qwen Cloud API integration | Implemented and tested | `services/api/v1/src/batchhelm_api/qwen.py` |
| Redacted live-call receipt | Implemented and tested | `/api/v1/qwen/verify`, `/api/v1/qwen/proof` |
| SQLite proof history | Implemented and tested | `qwen_verification_repository.py` |
| ECS release automation | Implemented and tested | `deploy/alibaba-ecs/` |
| Public Alibaba ECS URL | **Captured** — `http://47.84.199.208` | Section 4 |
| Live provider receipt | **Captured** — `mode: "live"`, real `/api/v1/qwen/proof` receipt | Section 4 |
| ECS Workbench screenshots | Pending console screenshot | submission checklist |

## 1. Qwen Cloud API

BatchHelm calls Qwen models through Qwen Cloud's OpenAI-compatible endpoint:

```text
https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions
```

Default models:

- text and structured operational reasoning: `qwen3.7-plus`;
- dedicated shelf and document vision: `qwen3-vl-plus`.

Authentication uses `QWEN_API_KEY` as a bearer token. The key is loaded from
the environment and is never written to model responses, logs, proof receipts,
or source control.

Code references:

- gateway, retries, structured output, and verification:
  `services/api/v1/src/batchhelm_api/qwen.py`;
- runtime configuration: `services/api/v1/src/batchhelm_api/config.py`;
- typed workflow tasks: `services/api/v1/src/batchhelm_api/qwen_tasks.py`;
- image inspection: `services/api/v1/src/batchhelm_api/inspection.py`;
- public API and protected verification:
  `services/api/v1/src/batchhelm_api/app.py`.

Official hackathon resources identify the same base URL and current models:
`https://qwencloud-hackathon.devpost.com/resources`.

## 2. Live Verification Receipt

`POST /api/v1/qwen/verify` performs one real, billable, minimal structured Qwen
Cloud request. It requires the independent `X-BatchHelm-Proof-Token` header.
The endpoint is disabled when `QWEN_PROOF_TOKEN` is unset.

After a successful response, BatchHelm persists only:

- provider name;
- verified flag;
- model ID;
- Qwen Cloud base URL;
- provider response ID when supplied;
- measured latency;
- UTC verification time;
- SHA-256 fingerprint of the structured response.

It does not persist the Qwen key, proof token, request prompt, response body, or
authorization headers.

`GET /api/v1/qwen/proof` exposes the latest redacted receipt without triggering
another provider call. This is safe for judges to inspect and survives API
restart through `/data/qwen-proof.db`.

## 3. Alibaba Cloud ECS

The production bundle in `deploy/alibaba-ecs/` demonstrates the backend
deployment:

- `cloud-init.sh` prepares an Ubuntu ECS host;
- `compose.yaml` builds the exact repository revision;
- `deploy.sh` transfers runtime secrets, starts the service, checks health, and
  captures live Qwen proof;
- `backup.sh` captures all SQLite databases and uploads as one recovery unit.

The security boundary exposes nginx on TCP `80`, keeps FastAPI TCP `8000`
private, and allows only one API replica.

## 4. Evidence Capture After Deployment

Deployed on Alibaba Cloud ECS (Singapore region, `ecs.t6-c1m2.large`, Ubuntu
22.04) via `deploy/alibaba-ecs/`. Public URL:

```text
http://47.84.199.208
```

The following was captured directly from an external machine hitting the
public IP (not over SSH), on 2026-07-07.

**`GET /health`**

```json
{"status":"ok","service":"batchhelm-api","version":"0.2.0"}
```

**`GET /api/v1/qwen/status`**

```json
{"provider":"qwen","configured":true,"base_url":"https://dashscope-intl.aliyuncs.com/compatible-mode/v1","text_model":"qwen3.7-plus","vision_model":"qwen3-vl-plus","mode":"live"}
```

**`GET /api/v1/qwen/proof`** — redacted receipt from a real, billable Qwen Cloud call:

```json
{"provider":"qwen-cloud","verified":true,"model":"qwen3.7-plus","base_url":"https://dashscope-intl.aliyuncs.com/compatible-mode/v1","provider_request_id":"chatcmpl-1781c58f-8bfe-9ef9-b872-f08cedd8ec47","latency_ms":7636,"response_sha256":"94425335f351d67ae67337877e0dd3d52da72ead8c1b64144c3555df64024deb","verified_at":"2026-07-07T23:09:16.918885Z"}
```

**`GET /api/v1/inspections/demo`** — live Qwen vision call against the bundled
sample photo (`sample-data/store-b-cooler-spinach.png`), not a fallback:

```json
{"extracted":{"product_name":"Spinach 10 oz","lot_code":"L2418","upc":"008500001010","confidence":100},"recall_match":true,"provider":"qwen","used_fallback":false}
```

**`docker compose ps`** on the ECS host — both services healthy:

```text
NAME              IMAGE                 SERVICE   STATUS
batchhelm-api-1   batchhelm-api:local   api       Up (healthy)
batchhelm-web-1   batchhelm-web:...     web       Up (healthy)
```

Still pending: an Alibaba Cloud console (ECS Workbench / instance overview)
screenshot showing the running host, which requires an authenticated console
session and is captured separately for the final deck.

## 5. What This Does Not Claim Yet

Section 4 now provides external runtime evidence that the ECS instance is
running and that real Qwen Cloud requests succeed. The one remaining gap is a
console-level (ECS Workbench / instance overview) screenshot, which requires
an authenticated Alibaba Cloud session and is not something this repository's
automation can capture on its own.
