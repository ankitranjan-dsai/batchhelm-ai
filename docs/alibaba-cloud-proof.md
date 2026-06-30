# Proof of Alibaba Cloud Usage

This file records exactly how BatchHelm depends on Alibaba Cloud, for hackathon
verification.

## 1. Qwen models via Alibaba Cloud Model Studio (required)

BatchHelm's reasoning runs on **Qwen models hosted on Alibaba Cloud Model
Studio**, through its OpenAI-compatible endpoint.

- Endpoint: `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- Default models: `qwen-plus` (text), `qwen-vl-plus` (vision)
- Auth: `QWEN_API_KEY` (a Model Studio API key) sent as a bearer token.

Code references:

- Gateway: `services/api/src/batchhelm_api/qwen.py`
  (`QwenGateway._post` posts `/chat/completions` with retries + telemetry)
- Config: `services/api/src/batchhelm_api/config.py` (`qwen_base_url`, models, key)
- Workflow tasks driven by Qwen: `services/api/src/batchhelm_api/qwen_tasks.py`
  (recall extraction, inventory-match reasoning, risk classification, customer
  notice, management briefing)
- Vision inspection: `services/api/src/batchhelm_api/inspection.py`

Live confirmation at runtime:

```bash
curl http://<host>:8000/api/qwen/status
# {"provider":"qwen","configured":true,"base_url":"https://dashscope-intl.aliyuncs.com/compatible-mode/v1","mode":"live", ...}
```

When `QWEN_API_KEY` is unset the service runs in deterministic `demo-fallback`
mode so demos and tests never depend on credentials. Every API response and the
dashboard label whether output came from Qwen or the fallback.

## 2. Hosting on Alibaba Cloud compute

- `Dockerfile` (API) and `apps/web/Dockerfile` (dashboard) produce the two
  images.
- `docker-compose.yml` deploys both on an **ECS** instance.
- The Container Registry (ACR) + **ACK** path is documented in
  [deployment-alibaba-cloud.md](deployment-alibaba-cloud.md).

## 3. Data residency

Durable state (review ledger, agent memory, uploads) is stored on a mounted
volume (`/data`), so it can be backed by an Alibaba Cloud disk or NAS in
production. The repository layer is interface-based and Postgres-ready
(ApsaraDB RDS) — see `review_repository.py` and `memory_repository.py`.
