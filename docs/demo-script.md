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

Set `QWEN_API_KEY` before recording and verify `/api/qwen/status` reports
`mode: "live"`. Deterministic fallback is for local development and automated
verification; the submission recording must visibly demonstrate Qwen output.

## Run of show

| Time | On screen | Say |
| --- | --- | --- |
| 0:00–0:20 | Recall inbox / incident summary | "Small grocers get a recall notice and have minutes to act. BatchHelm is an autonomous recall command center." |
| 0:20–0:45 | Agent Mission Control streaming six waves | "One action starts one durable run. Nine specialists divide the work, with inventory and vision executing in parallel." |
| 0:45–1:05 | Event timeline and Qwen/source badges | "Every event is persisted before it appears. Source badges distinguish live Qwen reasoning, deterministic safeguards, and memory." |
| 1:05–1:25 | Select an agent to open its inspector | "The inspector exposes each agent's role, reasoning, confidence, attempts, source, and timing rather than hiding the workflow behind a chat box." |
| 1:25–1:40 | Reload; the same run and ordered history return | "A refresh reuses the same run ID and replays only missing ordered events. Completed waves survive an API restart." |
| 1:40–2:00 | Affected inventory and conflict/resolved events | "Qwen extracts the criteria and reasons over matches. The orchestrator resolves disagreement against authoritative inventory before action." |
| 2:00–2:20 | Tasks and customer notice | "It creates removal, quarantine, and disposal tasks and drafts a customer notice with Qwen." |
| 2:20–2:40 | Evidence review gate | "Critical release steps require human approval. The idempotent ledger survives restarts and packet regeneration." |
| 2:40–2:52 | Management briefing and memory | "It briefs management and remembers supplier aliases and prior decisions for the next recall." |
| 2:52–3:00 | Evidence packet and public URL | "The result is an audit-ready packet, running on Alibaba Cloud and powered by Qwen." |

## Key lines to land

- "A real agent society, not a static dashboard — every event you see is a real
  agent step."
- "Qwen drives extraction, reasoning, risk, comms, and the briefing; a
  deterministic core keeps it reliable."
- "Durable run history, memory, and an idempotent review ledger make the
  workflow recoverable and auditable."
