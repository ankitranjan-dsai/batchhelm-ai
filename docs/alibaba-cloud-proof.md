# Proof Of Alibaba Cloud And Qwen Cloud Usage

This file defines the exact evidence BatchHelm can present for the Qwen Global
AI Hackathon. Code readiness and external runtime evidence are kept separate so
the submission never treats configuration as proof of a successful call.

## Evidence Status

| Evidence | Status | Authoritative location |
| --- | --- | --- |
| Qwen Cloud API integration | Implemented and tested | `services/api/src/batchhelm_api/qwen.py` |
| Redacted live-call receipt | Implemented and tested | `/api/qwen/verify`, `/api/qwen/proof` |
| SQLite proof history | Implemented and tested | `qwen_verification_repository.py` |
| ECS release automation | Implemented and tested | `deploy/alibaba-ecs/` |
| Public Alibaba ECS URL | Pending external deployment | submission checklist |
| Live provider receipt | Pending Qwen key and ECS run | submission checklist |
| ECS Workbench screenshots | Pending external deployment | submission checklist |

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
  `services/api/src/batchhelm_api/qwen.py`;
- runtime configuration: `services/api/src/batchhelm_api/config.py`;
- typed workflow tasks: `services/api/src/batchhelm_api/qwen_tasks.py`;
- image inspection: `services/api/src/batchhelm_api/inspection.py`;
- public API and protected verification:
  `services/api/src/batchhelm_api/app.py`.

Official hackathon resources identify the same base URL and current models:
`https://qwencloud-hackathon.devpost.com/resources`.

## 2. Live Verification Receipt

`POST /api/qwen/verify` performs one real, billable, minimal structured Qwen
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

`GET /api/qwen/proof` exposes the latest redacted receipt without triggering
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

After running `deploy.sh`, capture:

1. the public dashboard with the browser address visible;
2. `GET /health`;
3. `GET /api/qwen/status` showing `mode: "live"` and current models;
4. `GET /api/qwen/proof` showing the redacted successful receipt;
5. Alibaba Cloud ECS Workbench or instance overview showing the running host;
6. `docker compose ps` showing healthy `api` and `web` services.

Add the public URL and screenshots to the README, final deck, and demo video
only after these observations exist.

## 5. What This Does Not Claim Yet

Repository code proves that the deployment and verification paths exist. It
does not by itself prove that an ECS instance is currently running or that a
real Qwen request has succeeded. Those two claims remain pending until external
runtime evidence is captured.
