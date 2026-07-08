# Deploying BatchHelm On Alibaba Cloud ECS

BatchHelm's release deployment is a single Alibaba Cloud Elastic Compute
Service instance running Docker Compose. One FastAPI container owns the SQLite
worker lifecycle, one nginx container serves the React application and proxies
same-origin API traffic, and Qwen Cloud provides text and vision inference.

The repository contains the complete deployment bundle under
`deploy/alibaba-ecs/`.

## Deployment Status

Deployed and live: **[http://47.84.199.208](http://47.84.199.208)** (Alibaba
Cloud ECS, Singapore region, `ecs.t6-c1m2.large`, Ubuntu 22.04). Captured
`/health`, `/api/v1/qwen/status` (`mode: "live"`), and `/api/v1/qwen/proof` evidence
is in [docs/alibaba-cloud-proof.md](alibaba-cloud-proof.md).

## Runtime Topology

| Component | Exposure | Responsibility |
| --- | --- | --- |
| `web` | ECS TCP `80` | React dashboard, `/api` reverse proxy, SSE |
| `api` | Compose network only | FastAPI, nine-agent orchestrator, proof endpoint |
| `/srv/batchhelm/data` | ECS disk | Five SQLite databases and uploaded evidence |
| Qwen Cloud | Outbound HTTPS | `qwen3.7-plus` text and `qwen3-vl-plus` vision |

The API is fixed at one replica because run ownership and worker claims are
SQLite-backed. The web service is the only public container port.

## 1. Create The ECS Instance

Create an Ubuntu 22.04 or 24.04 ECS instance with:

- at least 2 vCPU and 4 GB RAM;
- a public IPv4 address or Elastic IP;
- an SSH key pair rather than a password;
- enough disk space for images, SQLite state, uploads, and backups.

Use this security group:

| Port | Source | Purpose |
| --- | --- | --- |
| TCP `22` | operator public IP only | deployment and maintenance |
| TCP `80` | `0.0.0.0/0` | public judging URL |

Do not expose TCP `8000`. The nginx container reaches FastAPI over the private
Compose network.

Alibaba Cloud's ECS user-data documentation recommends cloud-init for
repeatable initialization:
`https://www.alibabacloud.com/help/en/ecs/user-guide/customize-the-initialization-configuration-for-an-instance`.

## 2. Bootstrap The Host

Connect to the instance, clone the public repository, and run the idempotent
host bootstrap:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/ankitranjan-dsai/batchhelm-ai.git
cd batchhelm-ai
sudo bash deploy/alibaba-ecs/cloud-init.sh
```

The script installs Docker Engine, Compose, git, curl, and jq; enables Docker;
and creates:

```text
/opt/batchhelm
/srv/batchhelm/data
/srv/batchhelm/backups
```

It does not accept, log, or write application secrets.

## 3. Deploy An Exact Revision

Run the deployment command from the local repository:

```bash
export BATCHHELM_HOST=ecs-user@ecs-address
export QWEN_API_KEY='the Qwen Cloud pay-as-you-go key'
export QWEN_PROOF_TOKEN="$(openssl rand -hex 32)"

bash deploy/alibaba-ecs/deploy.sh
```

Optional variables:

```bash
export BATCHHELM_SSH_KEY="$HOME/.ssh/alibaba-ecs"
export PUBLIC_ORIGIN="http://ecs-address"
export BATCHHELM_REVISION="$(git rev-parse HEAD)"
```

`deploy.sh`:

1. validates required inputs without printing them;
2. transfers a mode-`600` environment file;
3. checks out the exact 40-character commit SHA on ECS;
4. builds both containers from that revision;
5. starts the one-replica production topology;
6. waits for the proxied health endpoint;
7. performs one protected live Qwen Cloud verification;
8. reads the public redacted receipt.

The Qwen key and proof token are runtime values. They are not image layers,
source files, command output, or receipt fields.

## 4. Verify The Deployment

The deploy command performs these checks automatically. They can also be run
independently:

```bash
curl -fsS http://ecs-address/health | jq .
curl -fsS http://ecs-address/api/v1/qwen/status | jq .
curl -fsS http://ecs-address/api/v1/qwen/proof | jq .
```

Expected health:

```json
{"status":"ok","service":"batchhelm-api","version":"0.2.0"}
```

`/api/v1/qwen/status` reports configuration and model selection. It does not prove
that a network call succeeded. `/api/v1/qwen/proof` returns the latest persisted
successful provider receipt and is the stronger evidence.

## 5. Back Up The Recovery Unit

On ECS:

```bash
sudo bash /opt/batchhelm/deploy/alibaba-ecs/backup.sh
```

The command stops API writes, creates SQLite-native backups through
`Connection.backup()`, copies uploaded artifacts, creates a timestamped archive
under `/srv/batchhelm/backups`, and restarts the API. It captures:

- `batchhelm.db`;
- `batchhelm-memory.db`;
- `orchestration.db`;
- `intake.db`;
- `qwen-proof.db`;
- `uploads/`.

## 6. Update Or Roll Back

Deploy the current revision:

```bash
export BATCHHELM_REVISION="$(git rev-parse HEAD)"
bash deploy/alibaba-ecs/deploy.sh
```

Roll back by exporting a previously verified full commit SHA and running the
same command. State remains on `/srv/batchhelm/data`.

## ACK Is A Future Scale Mode

Alibaba Cloud Container Service for Kubernetes remains a valid later target,
but increasing API replicas now would create competing SQLite worker owners.
ACK requires shared databases, shared artifact storage, and distributed leases
before it is an honest production topology.

See [alibaba-cloud-proof.md](alibaba-cloud-proof.md) for the submission evidence
boundary and [qwen-integration.md](qwen-integration.md) for provider behavior.
