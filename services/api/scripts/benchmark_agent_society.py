"""Measures the Agent Society DAG against a single-agent baseline.

Both arms wrap the exact same nine specialist agents (`default_agents()`) —
only the execution strategy differs. The DAG arm is the real
`Orchestrator` (parallel waves, per-agent retries, failure isolation,
per-wave checkpoints). The baseline arm is `SingleAgentPipeline`, a
strictly sequential runner with no parallelism, no isolation between
agents, and no checkpointing, built from the same agent objects.

Three trials are run:

1. Latency — wall-clock time to process the demo incident, with an
   optional synthetic per-agent delay so wave-level parallelism becomes
   measurable even in demo-fallback mode (which is otherwise too fast
   for wall-clock differences to be meaningful).
2. Failure isolation — one agent is made to always fail; the DAG still
   delivers a partial result while the baseline aborts the whole run.
3. Checkpoint/resume — a crash is simulated mid-run; the DAG resumes
   from its last wave checkpoint while the baseline has no structural
   way to resume and would have to restart from agent one.

Usage (from services/api):

    uv run python scripts/benchmark_agent_society.py
    uv run python scripts/benchmark_agent_society.py --report ../../docs/benchmarks/agent-society-vs-single-agent.md
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path

from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.agents.inventory import SHELF_VISION
from batchhelm_api.agents.orchestrator import Orchestrator, default_agents
from batchhelm_api.config import Settings
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.models import AgentRunStatus, RecallIncidentInput
from batchhelm_api.orchestration_state import OrchestrationCheckpoint
from batchhelm_api.qwen import QwenGateway
from batchhelm_api.sample_data import build_demo_incident

REPO_ROOT = Path(__file__).resolve().parents[3]


def _new_settings() -> Settings:
    """Deterministic, offline settings — demo-fallback mode, no local .env."""

    return Settings(QWEN_API_KEY="", _env_file=None)  # type: ignore[call-arg]


class SingleAgentPipeline:
    """Baseline: the same specialist agents run one after another.

    No parallel waves, no dependency-failure isolation (the first
    exception aborts the whole run), and no checkpointing.
    """

    def __init__(
        self,
        *,
        gateway: QwenGateway,
        memory: InMemoryMemoryRepository,
        settings: Settings,
        agents: list[Agent],
    ) -> None:
        self.gateway = gateway
        self.memory = memory
        self.settings = settings
        self.agents = agents

    async def run(self, incident: RecallIncidentInput) -> "SingleAgentPipelineResult":
        from batchhelm_api.agents.base import EventRecorder
        from uuid import uuid4

        run_id = uuid4().hex
        recorder = EventRecorder(run_id)
        ctx = AgentContext(
            run_id=run_id,
            incident=incident,
            gateway=self.gateway,
            memory=self.memory,
            settings=self.settings,
            recorder=recorder,
        )
        completed: list[str] = []
        try:
            for agent in self.agents:
                await agent.run(ctx)
                completed.append(agent.name)
        except Exception as exc:  # noqa: BLE001 - the baseline has no isolation
            return SingleAgentPipelineResult(
                completed_agents=completed,
                aborted=True,
                error=f"{type(exc).__name__}: {exc}",
            )
        return SingleAgentPipelineResult(completed_agents=completed, aborted=False, error="")


@dataclass
class SingleAgentPipelineResult:
    completed_agents: list[str]
    aborted: bool
    error: str


class _DelayedAgent(Agent):
    """Wraps a real agent with a synthetic per-agent processing delay.

    Applied identically to both arms, so it only makes wave-level
    parallelism (DAG) versus strict sequencing (baseline) visible in
    wall-clock time — it does not favor either arm.
    """

    def __init__(self, inner: Agent, delay_seconds: float) -> None:
        self.inner = inner
        self.delay_seconds = delay_seconds
        self.name = inner.name
        self.role = inner.role
        self.depends_on = inner.depends_on

    async def run(self, ctx: AgentContext) -> AgentOutput:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        return await self.inner.run(ctx)


class _CountingAgent(Agent):
    """Wraps a real agent and counts how many times it actually executes."""

    def __init__(self, inner: Agent, counts: dict[str, int]) -> None:
        self.inner = inner
        self.counts = counts
        self.name = inner.name
        self.role = inner.role
        self.depends_on = inner.depends_on

    async def run(self, ctx: AgentContext) -> AgentOutput:
        self.counts[self.name] = self.counts.get(self.name, 0) + 1
        return await self.inner.run(ctx)


class _AlwaysFailingAgent(Agent):
    """Wraps a real agent but always raises, standing in for a broken specialist."""

    def __init__(self, inner: Agent) -> None:
        self.inner = inner
        self.name = inner.name
        self.role = inner.role
        self.depends_on = inner.depends_on

    async def run(self, ctx: AgentContext) -> AgentOutput:
        raise RuntimeError(f"{self.name} raised a simulated processing error.")


def _build_agents(
    *,
    delay_seconds: float = 0.0,
    counts: dict[str, int] | None = None,
    fail_agent: str | None = None,
) -> list[Agent]:
    agents: list[Agent] = []
    for agent in default_agents():
        wrapped: Agent = agent
        if fail_agent is not None and agent.name == fail_agent:
            wrapped = _AlwaysFailingAgent(wrapped)
        if delay_seconds:
            wrapped = _DelayedAgent(wrapped, delay_seconds)
        if counts is not None:
            wrapped = _CountingAgent(wrapped, counts)
        agents.append(wrapped)
    return agents


# -- Trial 1: latency -------------------------------------------------------


@dataclass
class LatencyTrialResult:
    trials: int
    delay_seconds: float
    dag_ms: list[float] = field(default_factory=list)
    baseline_ms: list[float] = field(default_factory=list)

    @property
    def dag_mean_ms(self) -> float:
        return statistics.mean(self.dag_ms)

    @property
    def baseline_mean_ms(self) -> float:
        return statistics.mean(self.baseline_ms)

    @property
    def speedup(self) -> float:
        return self.baseline_mean_ms / self.dag_mean_ms if self.dag_mean_ms else 0.0


async def run_latency_trial(*, trials: int, delay_seconds: float) -> LatencyTrialResult:
    result = LatencyTrialResult(trials=trials, delay_seconds=delay_seconds)
    incident = build_demo_incident()

    for _ in range(trials):
        settings = _new_settings()
        gateway = QwenGateway(settings)
        memory = InMemoryMemoryRepository()
        orchestrator = Orchestrator(
            gateway=gateway,
            memory=memory,
            settings=settings,
            agents=_build_agents(delay_seconds=delay_seconds),
        )
        start = time.perf_counter()
        await orchestrator.run(incident)
        result.dag_ms.append((time.perf_counter() - start) * 1000)

    for _ in range(trials):
        settings = _new_settings()
        gateway = QwenGateway(settings)
        memory = InMemoryMemoryRepository()
        pipeline = SingleAgentPipeline(
            gateway=gateway,
            memory=memory,
            settings=settings,
            agents=_build_agents(delay_seconds=delay_seconds),
        )
        start = time.perf_counter()
        await pipeline.run(incident)
        result.baseline_ms.append((time.perf_counter() - start) * 1000)

    return result


# -- Trial 2: failure isolation ----------------------------------------------


@dataclass
class IsolationTrialResult:
    fail_agent: str
    dag_status: str
    dag_completed: list[str]
    dag_failed: list[str]
    dag_skipped: list[str]
    baseline_completed: list[str]
    baseline_aborted: bool
    baseline_error: str


async def run_isolation_trial(*, fail_agent: str) -> IsolationTrialResult:
    incident = build_demo_incident()

    dag_settings = _new_settings()
    orchestrator = Orchestrator(
        gateway=QwenGateway(dag_settings),
        memory=InMemoryMemoryRepository(),
        settings=dag_settings,
        agents=_build_agents(fail_agent=fail_agent),
    )
    dag_result = await orchestrator.run(incident)
    dag_completed = [a.agent for a in dag_result.agents if a.status == AgentRunStatus.completed]
    dag_failed = [a.agent for a in dag_result.agents if a.status == AgentRunStatus.failed]
    dag_skipped = [a.agent for a in dag_result.agents if a.status == AgentRunStatus.skipped]

    baseline_settings = _new_settings()
    pipeline = SingleAgentPipeline(
        gateway=QwenGateway(baseline_settings),
        memory=InMemoryMemoryRepository(),
        settings=baseline_settings,
        agents=_build_agents(fail_agent=fail_agent),
    )
    baseline_result = await pipeline.run(incident)

    return IsolationTrialResult(
        fail_agent=fail_agent,
        dag_status=dag_result.status.value,
        dag_completed=dag_completed,
        dag_failed=dag_failed,
        dag_skipped=dag_skipped,
        baseline_completed=baseline_result.completed_agents,
        baseline_aborted=baseline_result.aborted,
        baseline_error=baseline_result.error,
    )


# -- Trial 3: checkpoint / resume --------------------------------------------


@dataclass
class RecoveryTrialResult:
    total_agents: int
    wave_count: int
    resume_from_wave: int
    dag_resumed_agent_calls: int
    dag_percent_rerun: float
    baseline_percent_rerun: float


async def run_recovery_trial() -> RecoveryTrialResult:
    incident = build_demo_incident()

    full_settings = _new_settings()
    full_orchestrator = Orchestrator(
        gateway=QwenGateway(full_settings),
        memory=InMemoryMemoryRepository(),
        settings=full_settings,
    )
    wave_count = len(full_orchestrator._waves())
    checkpoints: list[OrchestrationCheckpoint] = []
    await full_orchestrator.run(incident, checkpoint_sink=checkpoints.append)

    resume_from_wave = wave_count - 2
    mid_checkpoint = next(c for c in checkpoints if c.next_wave == resume_from_wave)

    resumed_counts: dict[str, int] = {}
    resume_settings = _new_settings()
    resume_orchestrator = Orchestrator(
        gateway=QwenGateway(resume_settings),
        memory=InMemoryMemoryRepository(),
        settings=resume_settings,
        agents=_build_agents(counts=resumed_counts),
    )
    await resume_orchestrator.run(
        incident,
        run_id=mid_checkpoint.run_id,
        recovery=mid_checkpoint,
    )

    total_agents = len(default_agents())
    dag_resumed_calls = sum(resumed_counts.values())
    return RecoveryTrialResult(
        total_agents=total_agents,
        wave_count=wave_count,
        resume_from_wave=resume_from_wave,
        dag_resumed_agent_calls=dag_resumed_calls,
        dag_percent_rerun=round(100 * dag_resumed_calls / total_agents, 1),
        baseline_percent_rerun=100.0,
    )


# -- report -------------------------------------------------------------


def render_markdown(
    *,
    latency: LatencyTrialResult,
    isolation: IsolationTrialResult,
    recovery: RecoveryTrialResult,
) -> str:
    lines = [
        "# Agent Society vs. single-agent baseline",
        "",
        "Both arms run the same nine specialist agents against the same demo "
        "incident (`build_demo_incident()`), in demo-fallback mode "
        "(`QWEN_API_KEY` unset, so responses are the deterministic fallback "
        "path — this isolates the orchestration strategy as the only "
        "variable, independent of live model latency). Reproduce with:",
        "",
        "```bash",
        "cd services/api",
        "uv run python scripts/benchmark_agent_society.py",
        "```",
        "",
        "## 1. Latency and parallelism",
        "",
        f"Each agent carries a synthetic {latency.delay_seconds * 1000:.0f} ms "
        "processing delay (applied identically to both arms) so that "
        "wave-level parallelism is visible in wall-clock time; without it, "
        "demo-fallback responses return in well under a millisecond and any "
        "difference would be noise.",
        "",
        "| Arm | Mean run time (ms) | Runs |",
        "| --- | --- | --- |",
        f"| Agent Society (DAG, 6 parallel waves) | {latency.dag_mean_ms:.1f} | {latency.trials} |",
        f"| Single-agent baseline (9 sequential steps) | {latency.baseline_mean_ms:.1f} | {latency.trials} |",
        "",
        f"**{latency.speedup:.2f}x faster** with the DAG at the same "
        "per-agent cost, because independent specialists "
        "(e.g. Inventory Matching and Shelf Vision, or Operations Task and "
        "Communications) run inside the same wave instead of one after "
        "another.",
        "",
        "## 2. Failure isolation",
        "",
        f"`{isolation.fail_agent}` is forced to raise on every attempt, "
        "simulating a broken specialist (e.g. a vision model outage).",
        "",
        "| Arm | Outcome |",
        "| --- | --- |",
        (
            "| Agent Society (DAG) | run status `"
            f"{isolation.dag_status}`, still delivered "
            f"{len(isolation.dag_completed)}/9 completed agents "
            f"({', '.join(isolation.dag_completed)}); "
            f"{len(isolation.dag_skipped)} downstream agent(s) skipped "
            f"cleanly ({', '.join(isolation.dag_skipped) or 'none'}) |"
        ),
        (
            "| Single-agent baseline | aborted after "
            f"{len(isolation.baseline_completed)}/9 agents — "
            f"`{isolation.baseline_error}` |"
        ),
        "",
        "The DAG isolates the failing specialist to its own branch and still "
        "returns a partial, reviewable analysis; the sequential baseline has "
        "no such boundary and loses the entire run.",
        "",
        "## 3. Checkpoint and resume",
        "",
        f"A crash is simulated after wave {recovery.resume_from_wave} of "
        f"{recovery.wave_count}, then the run resumes from the last "
        "persisted checkpoint.",
        "",
        "| Arm | Work re-run after a simulated crash |",
        "| --- | --- |",
        (
            "| Agent Society (DAG, `recovery=` checkpoint) | "
            f"{recovery.dag_resumed_agent_calls}/{recovery.total_agents} "
            f"agents ({recovery.dag_percent_rerun}%) |"
        ),
        (
            "| Single-agent baseline (no checkpoint mechanism) | "
            f"{recovery.total_agents}/{recovery.total_agents} agents "
            f"({recovery.baseline_percent_rerun}%) |"
        ),
        "",
        "The baseline has no structural place to resume from, so a crash "
        "mid-run means restarting all nine agents; the DAG's per-wave "
        "checkpoint replays only the blackboard state and continues from "
        "the next wave.",
        "",
    ]
    return "\n".join(lines)


async def main_async(args: argparse.Namespace) -> str:
    latency = await run_latency_trial(
        trials=args.trials, delay_seconds=args.delay_ms / 1000
    )
    isolation = await run_isolation_trial(fail_agent=args.fail_agent)
    recovery = await run_recovery_trial()
    return render_markdown(latency=latency, isolation=isolation, recovery=recovery)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=int, default=5, help="Latency trial repeats per arm.")
    parser.add_argument(
        "--delay-ms",
        type=float,
        default=180.0,
        help="Synthetic per-agent processing delay for the latency trial.",
    )
    parser.add_argument(
        "--fail-agent",
        default=SHELF_VISION,
        help="Agent name to force-fail for the isolation trial.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the Markdown report to this path (relative to repo root if not absolute).",
    )
    args = parser.parse_args()

    report_text = asyncio.run(main_async(args))
    print(report_text)

    if args.report is not None:
        report_path = args.report if args.report.is_absolute() else REPO_ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report_text, encoding="utf-8")
        print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
