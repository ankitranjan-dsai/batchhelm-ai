# Qwen Global AI Hackathon — Submission Checklist

Track: **Autopilot Agent** (primary), **Agent Society** (secondary).

## Required items

- [x] Public open-source repository with all source and assets
- [x] Text description of features and functionality (`README.md`)
- [x] Proof of Alibaba Cloud usage (`docs/alibaba-cloud-proof.md`)
- [x] Deployment path for Alibaba Cloud (`Dockerfile`, `docker-compose.yml`, `docs/deployment-alibaba-cloud.md`)
- [x] Architecture diagram (`docs/architecture.md`, mermaid)
- [x] Sample evidence packet artifact (`docs/sample-evidence-packet.md`)
- [x] Sample incident walkthrough (`docs/sample-incident-walkthrough.md`)
- [x] Demo script (`docs/demo-script.md`)
- [ ] **Demo video under 3 minutes** uploaded to YouTube/Vimeo/Youku — *record using the demo script; add the link here and in the README*
- [ ] Track selected on Devpost: Autopilot Agent
- [ ] (Optional) Blog/social post link for bonus prize

## Judging-criteria coverage

| Criterion | Where it shows |
| --- | --- |
| Innovation & AI Creativity (30%) | Multi-agent society, Qwen-driven structured workflow, conflict reconciliation, persistent memory, AI Showrunner briefing |
| Technical Depth & Engineering (30%) | DAG orchestration with parallel waves + retries + checkpoints, validated Qwen schemas, idempotent SQLite ledger, observability (request IDs, rate limiting, structured logs, telemetry), Docker/Compose/CI |
| Problem Value & Impact (25%) | Recall response for small grocers/restaurants/pharmacies; audit-ready evidence |
| Presentation & Documentation (15%) | README, architecture, Qwen integration, deployment, demo script, known limitations |

## Pre-submission verification

```bash
cd services/api && uv run pytest -q          # backend tests
cd ../../apps/web && npm run typecheck && npm run build
cd ../.. && ./scripts/check-attribution.sh   # repository language scan
docker build -t batchhelm-api:check .        # API image builds
```
