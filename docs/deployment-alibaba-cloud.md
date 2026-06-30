# Deploying BatchHelm on Alibaba Cloud

BatchHelm runs on Alibaba Cloud two ways. Both use **Qwen models on Alibaba
Cloud Model Studio** as the reasoning engine.

1. **Elastic Compute Service (ECS) with Docker Compose** — simplest path.
2. **Container Service for Kubernetes (ACK)** — for managed scaling.

## What runs where

| Component | Image | Port | Notes |
| --- | --- | --- | --- |
| `api` | `batchhelm-api` (root `Dockerfile`) | 8000 | FastAPI + agent orchestrator |
| `web` | `batchhelm-web` (`apps/web/Dockerfile`) | 80 | Vite build served by nginx, proxies `/api` |
| Qwen | Alibaba Cloud Model Studio | — | OpenAI-compatible endpoint, called from `api` |

## Option 1 — ECS + Docker Compose

1. Create an ECS instance (Ubuntu 22.04, 2 vCPU / 4 GB is enough for the demo).
2. Install Docker and the Compose plugin.
3. Clone the repository and create an env file:

   ```bash
   cp .env.example .env
   # edit .env and set QWEN_API_KEY to your Model Studio key
   ```

4. Build and start:

   ```bash
   docker compose up -d --build
   ```

5. Verify:

   ```bash
   curl http://<ecs-public-ip>:8000/health
   curl http://<ecs-public-ip>:8000/api/qwen/status   # mode: "live" when the key is set
   ```

   The dashboard is on port `8080`.

Persistent state (review ledger + agent memory + uploads) is stored on the
`batchhelm-data` Docker volume mounted at `/data`.

## Option 2 — Container Service for Kubernetes (ACK)

1. Push both images to Alibaba Cloud Container Registry (ACR):

   ```bash
   docker build -t registry.<region>.aliyuncs.com/<ns>/batchhelm-api:0.2.0 .
   docker build -t registry.<region>.aliyuncs.com/<ns>/batchhelm-web:0.2.0 apps/web
   docker push registry.<region>.aliyuncs.com/<ns>/batchhelm-api:0.2.0
   docker push registry.<region>.aliyuncs.com/<ns>/batchhelm-web:0.2.0
   ```

2. Store the Qwen key as a Kubernetes secret:

   ```bash
   kubectl create secret generic batchhelm-qwen --from-literal=QWEN_API_KEY=<key>
   ```

3. Deploy the `api` and `web` Deployments + Services, mounting the secret as
   the `QWEN_API_KEY` environment variable, and attach a persistent volume for
   `/data`. Front the `web` Service with an Alibaba Cloud SLB / Ingress.

## Secrets

- The Qwen key is injected at runtime via environment only. It is never baked
  into an image, committed, or written to logs.
- `LOG_LEVEL`, `CORS_ORIGINS`, and `RATE_LIMIT_PER_MINUTE` are environment-tunable.

See [alibaba-cloud-proof.md](alibaba-cloud-proof.md) for the explicit record of
which Alibaba Cloud services and APIs BatchHelm depends on.
