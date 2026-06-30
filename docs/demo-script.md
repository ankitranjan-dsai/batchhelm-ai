# BatchHelm Demo Script (under 3 minutes)

Target: the Qwen Global AI Hackathon submission video. Track: **Autopilot Agent**
(with a clear **Agent Society** of cooperating specialists).

## Setup (before recording)

```bash
# Backend
cd services/api && uv sync --extra dev && uv run uvicorn batchhelm_api.app:app --reload
# Frontend (second terminal)
cd apps/web && npm install && npm run dev
```

Optional: export `QWEN_API_KEY` to record in live Qwen mode. Without it the demo
runs in deterministic fallback and still shows the full flow.

## Run of show

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:20 | Recall inbox / incident summary | "Small grocers get a recall notice and have minutes to act. BatchHelm is an autonomous recall command center." |
| 0:20–0:45 | Agent Mission Control streaming | "One click runs a society of specialist agents — intake, extraction, inventory matching, vision, risk, operations, communications, compliance, and memory — coordinated by an orchestrator." |
| 0:45–1:10 | Event timeline with source badges | "Events stream live. Each badge shows whether the output came from Qwen, the deterministic fallback, or persistent memory. Inventory and vision run in parallel." |
| 1:10–1:35 | Affected inventory + conflict/resolved events | "Qwen extracts recall criteria from the raw notice and reasons over the inventory match. The orchestrator reconciles any disagreement against the authoritative inventory before acting." |
| 1:35–2:00 | Tasks + customer notice | "It generates removal, quarantine, and disposal tasks and drafts a customer notice with Qwen." |
| 2:00–2:25 | Evidence review gate | "Critical steps require human approval. The decision is stored in a durable, idempotent ledger that survives restarts and packet regeneration." |
| 2:25–2:45 | AI Showrunner briefing + memory panel | "It writes a management briefing and remembers supplier aliases and decisions so the next recall is faster." |
| 2:45–3:00 | Evidence packet download | "Finally, an audit-ready evidence packet. Production-ready, deployed on Alibaba Cloud, powered by Qwen." |

## Key lines to land

- "A real agent society, not a static dashboard — every event you see is a real
  agent step."
- "Qwen drives extraction, reasoning, risk, comms, and the briefing; a
  deterministic core keeps it reliable."
- "Durable memory and an idempotent review ledger make it production-ready."
