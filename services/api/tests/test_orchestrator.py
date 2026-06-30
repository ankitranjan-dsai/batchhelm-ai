from __future__ import annotations

from batchhelm_api.agents import Orchestrator
from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.agents.inventory import INVENTORY_MATCHING, SHELF_VISION
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.models import AgentEventType, AgentRunStatus, OutputSource
from batchhelm_api.sample_data import build_demo_incident
from tests.conftest import fallback_gateway, make_settings, scripted_gateway


def _orchestrator(gateway, **kwargs) -> Orchestrator:
    return Orchestrator(
        gateway=gateway,
        memory=InMemoryMemoryRepository(),
        settings=make_settings(),
        **kwargs,
    )


async def test_full_run_completes_all_agents_in_fallback_mode() -> None:
    orchestrator = _orchestrator(fallback_gateway())

    result = await orchestrator.run(build_demo_incident())

    assert result.status == AgentRunStatus.completed
    assert len(result.agents) == 9
    assert all(a.status == AgentRunStatus.completed for a in result.agents)
    assert result.analysis.affected_items == 23
    assert result.memory_writes > 0
    assert result.briefing.headline
    assert result.events  # live timeline recorded


async def test_inventory_and_vision_run_in_the_same_wave() -> None:
    orchestrator = _orchestrator(fallback_gateway())

    waves = orchestrator._waves()
    wave_names = [{agent.name for agent in wave} for wave in waves]

    matching_wave = next(w for w in wave_names if INVENTORY_MATCHING in w)
    assert SHELF_VISION in matching_wave  # genuine parallelism, not sequential


async def test_checkpoints_are_persisted_per_agent() -> None:
    memory = InMemoryMemoryRepository()
    orchestrator = Orchestrator(
        gateway=fallback_gateway(), memory=memory, settings=make_settings()
    )

    result = await orchestrator.run(build_demo_incident())
    checkpoints = memory.list_checkpoints(result.run_id)

    assert len(checkpoints) == 9
    assert {c.agent for c in checkpoints} == {a.agent for a in result.agents}


async def test_conflict_is_detected_and_resolved_when_qwen_disagrees() -> None:
    # Live extraction proposes fewer lots than the authoritative criteria.
    gateway = scripted_gateway(
        {
            "product_name": "Spinach 10 oz",
            "affected_lots": ["L2418", "L2419"],
            "upcs": ["008500001010"],
            "supplier": "Central Farms",
            "risk_level": "high",
            "urgency": "Remove now",
            "summary": "Partial",
            "confidence": 90,
        }
    )
    orchestrator = _orchestrator(gateway)

    result = await orchestrator.run(build_demo_incident())

    assert result.conflicts_resolved == 1
    conflict_events = [e for e in result.events if e.type == AgentEventType.conflict]
    resolved_events = [e for e in result.events if e.type == AgentEventType.resolved]
    assert conflict_events and resolved_events


# -- failure / retry isolation ------------------------------------------------


class _AlwaysFails(Agent):
    name = "Failing Agent"
    role = "Always raises"
    depends_on: tuple[str, ...] = ()

    async def run(self, ctx: AgentContext) -> AgentOutput:
        raise RuntimeError("boom")


class _DependsOnFailure(Agent):
    name = "Dependent Agent"
    role = "Should be skipped"
    depends_on = ("Failing Agent",)

    async def run(self, ctx: AgentContext) -> AgentOutput:  # pragma: no cover
        return AgentOutput(summary="ran", source=OutputSource.deterministic)


class _FlakyAgent(Agent):
    name = "Flaky Agent"
    role = "Fails once then succeeds"
    depends_on: tuple[str, ...] = ()

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, ctx: AgentContext) -> AgentOutput:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient")
        return AgentOutput(summary="recovered", source=OutputSource.deterministic)


async def test_failing_agent_is_isolated_and_dependents_are_skipped() -> None:
    orchestrator = _orchestrator(
        fallback_gateway(), agents=[_AlwaysFails(), _DependsOnFailure()]
    )

    result = await orchestrator.run(build_demo_incident())

    statuses = {a.agent: a.status for a in result.agents}
    assert statuses["Failing Agent"] == AgentRunStatus.failed
    assert statuses["Dependent Agent"] == AgentRunStatus.skipped
    assert result.status == AgentRunStatus.failed


async def test_flaky_agent_retries_then_succeeds() -> None:
    flaky = _FlakyAgent()
    orchestrator = _orchestrator(fallback_gateway(), agents=[flaky])

    result = await orchestrator.run(build_demo_incident())

    assert flaky.calls == 2
    agent_result = result.agents[0]
    assert agent_result.status == AgentRunStatus.completed
    assert agent_result.attempts == 2
    assert any(e.type == AgentEventType.retry for e in result.events)
