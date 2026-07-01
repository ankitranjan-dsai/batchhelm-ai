# Sample Incident Walkthrough

This traces the bundled demo recall (`recall-spinach-2026-06`) end to end. The
event log below is real output from `POST /api/incidents/demo/run` in
deterministic `demo-fallback` mode; with `QWEN_API_KEY` set, the same steps run
on Qwen and the source badges flip to `qwen`.

## The incident

- Product: **Spinach 10 oz**, lots **L2418–L2422**, UPC `008500001010`
- Source: supplier alert `CF-2026-06-18` (possible contamination)
- Inventory: 6 rows across Store A and Store B, under two supplier aliases
  (`CF Baby Spinach 10OZ`, `Central Farms Greens 10OZ`)

## Execution waves (real parallelism)

```
Wave 1: Recall Intake Agent
Wave 2: Document Extraction Agent
Wave 3: Inventory Matching Agent | Shelf Vision Agent      (parallel)
Wave 4: Risk Scoring Agent | Memory Agent                  (parallel)
Wave 5: Operations Task Agent | Communications Agent       (parallel)
Wave 6: Compliance Evidence Agent
```

## Event log (abridged)

| # | Source | Agent · Event | Message |
| --- | --- | --- | --- |
| 1 | deterministic | Orchestrator · orchestrator | Coordinating 9 agents for Spinach 10 oz |
| 4 | deterministic | Recall Intake · completed | Triaged recall from supplier alert CF-2026-06-18 |
| 7 | qwen* | Document Extraction · completed | Structured 5 affected lots and 1 UPC from the notice |
| 10 | qwen* | Inventory Matching · completed | Quarantined 23 units across 2 stores; normalized 2 supplier aliases |
| 13 | qwen* | Shelf Vision · completed | Inspected shelf photo: Spinach 10 oz lot L2418 (match) |
| 16 | qwen* | Risk Scoring · completed | Classified risk as high (priority high) |
| 19 | memory | Memory · completed | Persisted decision; surfaced 2 insights from memory |
| 22 | deterministic | Operations Task · completed | Created 5 removal/quarantine/notice tasks |
| 25 | qwen* | Communications · completed | Drafted customer recall notice (pending approval) |
| 28 | deterministic | Compliance Evidence · completed | Evidence packet 64% ready (6 items) |
| 29 | deterministic | Orchestrator · resolved | Ground truth and Qwen reasoning agree on 23 affected units |
| 30 | deterministic | Orchestrator · orchestrator | Management briefing ready |

`*` shows `qwen` when `QWEN_API_KEY` is configured; `deterministic` in fallback.

## Result

- 9/9 agents completed; 0 conflicts (sources agreed); 4 memory records written
- **23 units** quarantined across 2 stores
- Evidence packet readiness **64%** (blocked on disposal records + customer comms)
- Customer notice drafted, awaiting reviewer approval at the evidence gate
- Management briefing produced by the orchestrator

## Conflict reconciliation

When Qwen extraction proposes a lot set that differs from the authoritative
inventory criteria, the orchestrator emits a `conflict` event, resolves in favor
of the inventory ground truth, and flags it for reviewer confirmation
(`resolved` event). This is exercised by
`tests/test_orchestrator.py::test_conflict_is_detected_and_resolved_when_qwen_disagrees`.

## Reproduce

```bash
cd services/api
uv run uvicorn batchhelm_api.app:app --reload
curl -s -X POST http://localhost:8000/api/incidents/demo/run | python -m json.tool
# live event stream:
curl -N http://localhost:8000/api/incidents/demo/run/stream
```
