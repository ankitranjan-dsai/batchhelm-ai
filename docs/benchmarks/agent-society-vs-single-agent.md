# Agent Society vs. single-agent baseline

Both arms run the same nine specialist agents against the same demo incident (`build_demo_incident()`), in demo-fallback mode (`QWEN_API_KEY` unset, so responses are the deterministic fallback path — this isolates the orchestration strategy as the only variable, independent of live model latency). Reproduce with:

```bash
cd services/api
uv run python scripts/benchmark_agent_society.py
```

## 1. Latency and parallelism

Each agent carries a synthetic 180 ms processing delay (applied identically to both arms) so that wave-level parallelism is visible in wall-clock time; without it, demo-fallback responses return in well under a millisecond and any difference would be noise.

| Arm | Mean run time (ms) | Runs |
| --- | --- | --- |
| Agent Society (DAG, 6 parallel waves) | 1095.3 | 5 |
| Single-agent baseline (9 sequential steps) | 1633.9 | 5 |

**1.49x faster** with the DAG at the same per-agent cost, because independent specialists (e.g. Inventory Matching and Shelf Vision, or Operations Task and Communications) run inside the same wave instead of one after another.

## 2. Failure isolation

`Shelf Vision Agent` is forced to raise on every attempt, simulating a broken specialist (e.g. a vision model outage).

| Arm | Outcome |
| --- | --- |
| Agent Society (DAG) | run status `failed`, still delivered 4/9 completed agents (Recall Intake Agent, Document Extraction Agent, Inventory Matching Agent, Memory Agent); 4 downstream agent(s) skipped cleanly (Risk Scoring Agent, Operations Task Agent, Communications Agent, Compliance Evidence Agent) |
| Single-agent baseline | aborted after 3/9 agents — `RuntimeError: Shelf Vision Agent raised a simulated processing error.` |

The DAG isolates the failing specialist to its own branch and still returns a partial, reviewable analysis; the sequential baseline has no such boundary and loses the entire run.

## 3. Checkpoint and resume

A crash is simulated after wave 4 of 6, then the run resumes from the last persisted checkpoint.

| Arm | Work re-run after a simulated crash |
| --- | --- |
| Agent Society (DAG, `recovery=` checkpoint) | 3/9 agents (33.3%) |
| Single-agent baseline (no checkpoint mechanism) | 9/9 agents (100.0%) |

The baseline has no structural place to resume from, so a crash mid-run means restarting all nine agents; the DAG's per-wave checkpoint replays only the blackboard state and continues from the next wave.
