# Qwen Global AI Hackathon — Submission Checklist

Track: **Autopilot Agent** (primary), **Agent Society** (secondary).

## Required items

- [x] Public open-source repository with MIT license
- [x] Text description of features and functionality (`README.md`)
- [x] Deployment path for Alibaba Cloud (`Dockerfile`, `docker-compose.yml`, `docs/deployment-alibaba-cloud.md`)
- [x] Architecture diagram (`docs/architecture.md`, mermaid)
- [x] Sample evidence packet artifact (`docs/sample-evidence-packet.md`)
- [x] Sample incident walkthrough (`docs/sample-incident-walkthrough.md`)
- [x] Demo script (`docs/demo-script.md`)
- [ ] **Push the durable Mission Control milestone** after Git activity is reopened
- [ ] **Deploy the backend on Alibaba Cloud** and capture verifiable service evidence
- [ ] **Publish a working test URL** that remains available throughout judging
- [ ] **Verify live Qwen mode** in the deployed app and capture model/source evidence
- [x] **Measure Agent Society efficiency** against a single-agent baseline (`docs/benchmarks/agent-society-vs-single-agent.md`, reproducible via `services/api/scripts/benchmark_agent_society.py`)
- [x] **Presentation deck/PPT** with problem, architecture, Qwen use, benchmark, impact, and demo URL (`docs/presentation/batchhelm-ai-hackathon-deck.pptx`; live URL slide pending deployment)
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
