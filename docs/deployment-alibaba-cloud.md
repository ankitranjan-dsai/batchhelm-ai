# Deploying BatchHelm on Alibaba Cloud

BatchHelm runs on Alibaba Cloud two ways. Both use **Qwen models on Alibaba
Cloud Model Studio** as the reasoning engine.

1. **Elastic Compute Service (ECS) with Docker Compose** — simplest path.
2. **Container Service for Kubernetes (ACK)** - for managed deployment, with
   the API held to one replica in this release.

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

Persistent state is stored on the `batchhelm-data` Docker volume mounted at
`/data`:

- review ledger: `/data/batchhelm.db`
- agent memory: `/data/batchhelm-memory.db`
- orchestration runs, events, and checkpoints: `/data/orchestration.db`
- intake lifecycle, drafts, and confirmed snapshots: `/data/intake.db`
- immutable notice, inventory, and shelf artifacts: `/data/uploads/intakes`

Run one API replica for the current SQLite-backed worker model. The run and
intake history survives process restarts, including pending extraction,
confirmed incident resolution, event replay, and wave recovery. Multiple
replicas require shared databases and artifact storage plus distributed worker
claims or leases.

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
   `/data`. Keep the API Deployment at one replica for this release. Front the
   `web` Service with an Alibaba Cloud SLB / Ingress.

Horizontal API scaling is a future mode after the SQLite repositories are
replaced by shared storage and run ownership is coordinated across workers.

Back up all four SQLite databases and `/data/uploads/intakes` as one recovery
unit. SQLite WAL files must be checkpointed or captured with a SQLite-aware
backup before copying a live volume.

## Secrets

- The Qwen key is injected at runtime via environment only. It is never baked
  into an image, committed, or written to logs.
- `LOG_LEVEL`, `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE`, `REVIEWER_ROLE`,
  `INTAKE_DATABASE_PATH`, and all other storage paths are environment-tunable.

See [alibaba-cloud-proof.md](alibaba-cloud-proof.md) for the explicit record of
which Alibaba Cloud services and APIs BatchHelm depends on.
