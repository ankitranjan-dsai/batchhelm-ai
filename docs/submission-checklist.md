# Qwen Global AI Hackathon — Submission Checklist

Track: **Autopilot Agent** (primary), **Agent Society** (secondary).

Submission deadline: **July 9, 2026 at 2:00 PM Pacific Time**.

## Required items

- [x] Public open-source repository with MIT license
- [x] Text description of features and functionality (`README.md`)
- [x] Deployment path for Alibaba Cloud (`Dockerfile`, `docker-compose.yml`, `docs/deployment-alibaba-cloud.md`)
- [x] Reproducible single-replica ECS release bundle (`deploy/alibaba-ecs/`)
- [x] Protected live-Qwen verification and redacted SQLite receipt
- [x] In-product Qwen evidence control that distinguishes configured from verified
- [x] Architecture diagram (`docs/architecture.md`, mermaid)
- [x] Sample evidence packet artifact (`docs/sample-evidence-packet.md`)
- [x] Sample incident walkthrough (`docs/sample-incident-walkthrough.md`)
- [x] Durable real incident intake backend and committed sample packet
- [x] Demo script (`docs/demo-script.md`)
- [x] **Push the durable Mission Control milestone**
- [x] **Verify real ambiguous intake in desktop and mobile browsers** and capture populated review evidence
- [x] **Deploy the backend on Alibaba Cloud** and capture verifiable service evidence (`docs/alibaba-cloud-proof.md`)
- [x] **Publish a working test URL** that remains available throughout judging — `http://47.84.199.208`
- [x] **Verify live Qwen mode** in the deployed app and capture model/source evidence (`mode: "live"`, real `/api/qwen/proof` receipt)
- [x] **Measure Agent Society efficiency** against a single-agent baseline (`docs/benchmarks/agent-society-vs-single-agent.md`, reproducible via `services/api/scripts/benchmark_agent_society.py`)
- [x] Final proof-first presentation deck with real intake screenshots (`docs/presentation/batchhelm-ai-hackathon-deck.pptx`)
- [ ] **Update the final deck with the deployed URL and captured live-Qwen proof**
- [ ] **Demo video under 3 minutes** uploaded to YouTube/Vimeo/Youku — *record using the demo script; add the link here and in the README*
- [ ] Track selected on Devpost: Autopilot Agent
- [ ] Submit final Devpost entry before the official deadline
- [ ] (Optional) Blog/social post link for bonus prize

## Judging-criteria coverage

| Criterion | Where it shows |
| --- | --- |
| Innovation & AI Creativity (30%) | Multi-agent society, Qwen-driven structured workflow, conflict reconciliation, persistent memory, explainable management briefing |
| Technical Depth & Engineering (30%) | DAG orchestration with parallel waves, retries, typed restart checkpoints, persisted SSE replay, validated Qwen schemas, idempotent SQLite ledgers, observability, Docker/Compose/CI |
| Problem Value & Impact (25%) | Recall response for small grocers/restaurants/pharmacies; audit-ready evidence |
| Presentation & Documentation (15%) | README, architecture, Qwen integration, deployment, demo script, known limitations |

## Pre-submission verification

```bash
cd services/api && uv run pytest -q          # backend tests
cd ../../apps/web && npm test && npm run typecheck && npm run build
cd ../.. && ./scripts/check-attribution.sh   # repository language scan
docker compose config --quiet
docker build -t batchhelm-api:check .        # API image builds
docker build -t batchhelm-web:check apps/web # dashboard image builds
```
