from __future__ import annotations

from batchhelm_api.agents import Orchestrator
from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput, EventRecorder
from batchhelm_api.agents.inventory import INVENTORY_MATCHING, SHELF_VISION
from batchhelm_api.intake_models import IntakeArtifact, IntakeArtifactRole
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.models import (
    AgentEventType,
    AgentRunResult,
    AgentRunStatus,
    OutputSource,
)
from batchhelm_api.orchestration_state import OrchestrationCheckpoint
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


async def test_real_shelf_fallback_names_artifact_without_inferring_match() -> None:
    orchestrator = _orchestrator(fallback_gateway())
    shelf_bytes = b"\x89PNG\r\n\x1a\n" + b"x" * 20
    shelf_artifact = IntakeArtifact(
        id="shelf-1",
        intake_id="intake-1",
        role=IntakeArtifactRole.shelf_photo,
        original_filename="store-b-cooler-spinach.png",
        stored_filename="shelf-1.png",
        media_type="image/png",
        size_bytes=len(shelf_bytes),
        sha256="a" * 64,
        relative_path="intakes/intake-1/shelf-1.png",
        created_at="2026-07-04T08:00:00+00:00",
    )

    result = await orchestrator.run(
        build_demo_incident(),
        shelf_image_bytes=shelf_bytes,
        shelf_image_media_type="image/png",
        shelf_upload=shelf_artifact,
    )
    vision = next(agent for agent in result.agents if agent.agent == SHELF_VISION)

    assert "store-b-cooler-spinach.png" in vision.summary
    assert "unknown" in vision.summary
    assert vision.confidence == 0
    assert vision.reasoning == (
        "Qwen vision was unavailable; no image match was inferred."
    )


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


async def test_event_is_persisted_before_it_is_published() -> None:
    order: list[str] = []

    async def persist(event) -> None:
        order.append(f"persist:{event.sequence}")

    async def publish(event) -> None:
        order.append(f"publish:{event.sequence}")

    recorder = EventRecorder(
        "run-1",
        persist=persist,
        emit=publish,
        initial_sequence=7,
    )

    event = await recorder.record(
        agent="Orchestrator Agent",
        type=AgentEventType.started,
        message="Started.",
    )

    assert event.sequence == 8
    assert order == ["persist:8", "publish:8"]


class _CountingAgent(Agent):
    role = "Counts executions"

    def __init__(
        self,
        name: str,
        calls: dict[str, int],
        depends_on: tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.calls = calls
        self.depends_on = depends_on

    async def run(self, ctx: AgentContext) -> AgentOutput:
        self.calls[self.name] = self.calls.get(self.name, 0) + 1
        ctx.blackboard["intake_valid"] = True
        return AgentOutput(
            summary=f"{self.name} complete",
            confidence=90,
            source=OutputSource.deterministic,
        )


async def test_orchestrator_preserves_caller_run_id_and_saves_each_wave() -> None:
    checkpoints: list[OrchestrationCheckpoint] = []
    orchestrator = _orchestrator(fallback_gateway())

    result = await orchestrator.run(
        build_demo_incident(),
        run_id="run-owned-by-service",
        checkpoint_sink=checkpoints.append,
    )

    assert result.run_id == "run-owned-by-service"
    assert checkpoints
    assert checkpoints[-1].next_wave == len(orchestrator._waves())


async def test_resume_skips_agents_from_completed_waves() -> None:
    calls: dict[str, int] = {}
    first = _CountingAgent("First", calls)
    second = _CountingAgent("Second", calls, depends_on=("First",))
    orchestrator = _orchestrator(
        fallback_gateway(),
        agents=[first, second],
    )
    checkpoint = OrchestrationCheckpoint(
        run_id="run-1",
        started_at="2026-06-30T09:00:00+00:00",
        next_wave=1,
        results=[
            AgentRunResult(
                agent="First",
                role=first.role,
                status=AgentRunStatus.completed,
                summary="First complete",
                confidence=90,
                source=OutputSource.deterministic,
                started_at="2026-06-30T09:00:00+00:00",
                finished_at="2026-06-30T09:00:01+00:00",
            )
        ],
    )

    result = await orchestrator.run(
        build_demo_incident(),
        run_id="run-1",
        recovery=checkpoint,
    )

    assert calls.get("First", 0) == 0
    assert calls["Second"] == 1
    assert [agent.agent for agent in result.agents] == ["First", "Second"]
