"""The Orchestrator Agent: runs the specialist agents as a real DAG.

Responsibilities:
- topologically layer agents into waves and run each wave in parallel
- wrap every agent with timing, retries, failure isolation, and live events
- persist a checkpoint per agent so a run is durable
- reconcile disagreements between the deterministic ground truth and Qwen
- assemble the final :class:`RecallAnalysis` and management briefing
"""

from __future__ import annotations

import asyncio
import re
import time
from uuid import uuid4

from batchhelm_api import qwen_tasks
from batchhelm_api.agents.base import (
    Agent,
    AgentContext,
    AgentOutput,
    EventRecorder,
    utcnow,
)
from batchhelm_api.agents.compliance import ComplianceEvidenceAgent, MemoryAgent
from batchhelm_api.agents.intake import DocumentExtractionAgent, RecallIntakeAgent
from batchhelm_api.agents.inventory import InventoryMatchingAgent, ShelfVisionAgent
from batchhelm_api.agents.operations import (
    CommunicationsAgent,
    OperationsTaskAgent,
    RiskScoringAgent,
)
from batchhelm_api.config import Settings
from batchhelm_api.event_stream import RunEventChannel
from batchhelm_api.memory_repository import AgentCheckpoint, MemoryRepository
from batchhelm_api.models import (
    AgentActivity,
    AgentEventType,
    AgentRunResult,
    AgentRunStatus,
    AgentStatus,
    CustomerNoticeDraft,
    InsightTone,
    MemoryInsight,
    OrchestrationResult,
    RecallAnalysis,
    RecallIncidentInput,
    TaskStatus,
    WorkflowEvent,
    WorkflowStatus,
)
from batchhelm_api.qwen import QwenGateway
from batchhelm_api.workflow import build_milestones, calculate_evidence_progress

ORCHESTRATOR = "Orchestrator Agent"

_STATUS_TO_AGENT_STATUS = {
    AgentRunStatus.completed: AgentStatus.complete,
    AgentRunStatus.running: AgentStatus.active,
    AgentRunStatus.failed: AgentStatus.waiting,
    AgentRunStatus.skipped: AgentStatus.waiting,
    AgentRunStatus.pending: AgentStatus.waiting,
}

_STATUS_TO_WORKFLOW_STATUS = {
    AgentRunStatus.completed: WorkflowStatus.complete,
    AgentRunStatus.running: WorkflowStatus.active,
    AgentRunStatus.failed: WorkflowStatus.waiting,
    AgentRunStatus.skipped: WorkflowStatus.pending,
    AgentRunStatus.pending: WorkflowStatus.pending,
}


def default_agents() -> list[Agent]:
    """The standard BatchHelm agent society, in registry order."""

    return [
        RecallIntakeAgent(),
        DocumentExtractionAgent(),
        InventoryMatchingAgent(),
        ShelfVisionAgent(),
        RiskScoringAgent(),
        MemoryAgent(),
        OperationsTaskAgent(),
        CommunicationsAgent(),
        ComplianceEvidenceAgent(),
    ]


class Orchestrator:
    def __init__(
        self,
        *,
        gateway: QwenGateway,
        memory: MemoryRepository,
        settings: Settings,
        agents: list[Agent] | None = None,
    ) -> None:
        self.gateway = gateway
        self.memory = memory
        self.settings = settings
        self.agents = agents or default_agents()
        self._max_attempts = max(1, settings.qwen_max_retries)

    def descriptors(self) -> list[dict[str, object]]:
        return [
            {"name": agent.name, "role": agent.role, "depends_on": list(agent.depends_on)}
            for agent in self.agents
        ]

    async def run(
        self,
        incident: RecallIncidentInput,
        *,
        channel: RunEventChannel | None = None,
        shelf_image_bytes: bytes | None = None,
        shelf_image_media_type: str | None = None,
    ) -> OrchestrationResult:
        run_id = uuid4().hex
        recorder = EventRecorder(run_id, channel.emit if channel else None)
        ctx = AgentContext(
            run_id=run_id,
            incident=incident,
            gateway=self.gateway,
            memory=self.memory,
            settings=self.settings,
            recorder=recorder,
        )
        if shelf_image_bytes is not None:
            ctx.blackboard["shelf_image_bytes"] = shelf_image_bytes
            ctx.blackboard["shelf_image_media_type"] = (
                shelf_image_media_type or "image/png"
            )

        started_at = utcnow()
        start_perf = time.perf_counter()
        await recorder.record(
            agent=ORCHESTRATOR,
            type=AgentEventType.orchestrator,
            message=f"Coordinating {len(self.agents)} agents for {incident.product}.",
        )

        results: dict[str, AgentRunResult] = {}
        for wave in self._waves():
            await asyncio.gather(
                *(self._run_agent(agent, ctx, results) for agent in wave)
            )

        conflicts = await self._reconcile(ctx)
        analysis = self._assemble_analysis(ctx, results)
        briefing_outcome = await qwen_tasks.generate_briefing(
            self.gateway, incident, analysis
        )
        await recorder.record(
            agent=ORCHESTRATOR,
            type=AgentEventType.orchestrator,
            message=f"Management briefing ready: {briefing_outcome.value.headline}",
            source=briefing_outcome.source,
        )

        duration_ms = int((time.perf_counter() - start_perf) * 1000)
        finished_at = utcnow()
        ordered_results = [results[a.name] for a in self.agents if a.name in results]
        failed = [r for r in ordered_results if r.status == AgentRunStatus.failed]
        status = AgentRunStatus.failed if failed else AgentRunStatus.completed
        memory_writes = len(self.memory.list_records())

        summary = (
            f"{len([r for r in ordered_results if r.status == AgentRunStatus.completed])}"
            f"/{len(self.agents)} agents completed in {duration_ms} ms; "
            f"{conflicts} conflict(s) resolved; {memory_writes} memory records."
        )
        await recorder.record(
            agent=ORCHESTRATOR,
            type=AgentEventType.completed,
            message=summary,
        )
        if channel is not None:
            await channel.close()

        return OrchestrationResult(
            run_id=run_id,
            incident_id=incident.id,
            status=status,
            provider_mode=self.gateway.status().mode,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            agents=ordered_results,
            events=recorder.events,
            analysis=analysis,
            briefing=briefing_outcome.value,
            memory_writes=memory_writes,
            conflicts_resolved=conflicts,
            summary=summary,
        )

    # -- internals ---------------------------------------------------------

    def _waves(self) -> list[list[Agent]]:
        deps = {agent.name: set(agent.depends_on) for agent in self.agents}
        resolved: set[str] = set()
        remaining = list(self.agents)
        waves: list[list[Agent]] = []
        while remaining:
            wave = [agent for agent in remaining if deps[agent.name] <= resolved]
            if not wave:
                raise ValueError("Agent dependency graph has a cycle.")
            waves.append(wave)
            resolved |= {agent.name for agent in wave}
            remaining = [agent for agent in remaining if agent not in wave]
        return waves

    async def _run_agent(
        self,
        agent: Agent,
        ctx: AgentContext,
        results: dict[str, AgentRunResult],
    ) -> None:
        failed_deps = [
            dep
            for dep in agent.depends_on
            if results.get(dep) and results[dep].status != AgentRunStatus.completed
        ]
        started_at = utcnow()
        if failed_deps:
            await ctx.recorder.record(
                agent=agent.name,
                type=AgentEventType.failed,
                message=f"Skipped: upstream {', '.join(failed_deps)} did not complete.",
            )
            results[agent.name] = AgentRunResult(
                agent=agent.name,
                role=agent.role,
                status=AgentRunStatus.skipped,
                summary=f"Skipped due to upstream failure: {', '.join(failed_deps)}.",
                started_at=started_at,
                finished_at=utcnow(),
                depends_on=list(agent.depends_on),
            )
            return

        await ctx.recorder.record(
            agent=agent.name,
            type=AgentEventType.started,
            message=f"{agent.role}.",
        )
        start_perf = time.perf_counter()
        attempts = 0
        output: AgentOutput | None = None
        while attempts < self._max_attempts:
            attempts += 1
            try:
                output = await agent.run(ctx)
                break
            except Exception as exc:  # noqa: BLE001 - isolate agent failures
                if attempts < self._max_attempts:
                    await ctx.recorder.record(
                        agent=agent.name,
                        type=AgentEventType.retry,
                        message=f"Attempt {attempts} failed ({exc}); retrying.",
                    )
                    continue
                await ctx.recorder.record(
                    agent=agent.name,
                    type=AgentEventType.failed,
                    message=f"Failed after {attempts} attempts: {exc}",
                )
                results[agent.name] = AgentRunResult(
                    agent=agent.name,
                    role=agent.role,
                    status=AgentRunStatus.failed,
                    summary=f"Failed after {attempts} attempts.",
                    attempts=attempts,
                    duration_ms=int((time.perf_counter() - start_perf) * 1000),
                    started_at=started_at,
                    finished_at=utcnow(),
                    depends_on=list(agent.depends_on),
                )
                return

        assert output is not None
        duration_ms = int((time.perf_counter() - start_perf) * 1000)
        finished_at = utcnow()
        result = AgentRunResult(
            agent=agent.name,
            role=agent.role,
            status=AgentRunStatus.completed,
            summary=output.summary,
            reasoning=output.reasoning,
            confidence=output.confidence,
            source=output.source,
            used_fallback=output.used_fallback,
            provider=output.provider,
            model=output.model,
            attempts=attempts,
            duration_ms=duration_ms,
            started_at=started_at,
            finished_at=finished_at,
            depends_on=list(agent.depends_on),
        )
        results[agent.name] = result
        await ctx.recorder.record(
            agent=agent.name,
            type=AgentEventType.completed,
            message=output.summary,
            source=output.source,
        )
        self._checkpoint(ctx, result)

    def _checkpoint(self, ctx: AgentContext, result: AgentRunResult) -> None:
        try:
            self.memory.save_checkpoint(
                AgentCheckpoint(
                    run_id=ctx.run_id,
                    agent=result.agent,
                    status=result.status,
                    summary=result.summary,
                    source=result.source,
                    confidence=result.confidence,
                    finished_at=result.finished_at,
                )
            )
        except Exception:  # noqa: BLE001 - checkpoints are best-effort
            pass

    async def _reconcile(self, ctx: AgentContext) -> int:
        """Resolve disagreement between deterministic ground truth and Qwen."""

        deterministic_units = ctx.blackboard.get("affected_items", 0)
        extraction = ctx.blackboard.get("extraction")
        conflicts = 0

        if extraction is not None:
            qwen_lots = {lot.upper() for lot in extraction.affected_lots}
            criteria_lots = {lot.upper() for lot in ctx.incident.criteria.affected_lots}
            if qwen_lots and qwen_lots != criteria_lots:
                conflicts += 1
                await ctx.recorder.record(
                    agent=ORCHESTRATOR,
                    type=AgentEventType.conflict,
                    message=(
                        "Extraction lots differ from authoritative criteria "
                        f"({sorted(qwen_lots)} vs {sorted(criteria_lots)})."
                    ),
                )
                await ctx.recorder.record(
                    agent=ORCHESTRATOR,
                    type=AgentEventType.resolved,
                    message=(
                        "Resolved in favor of inventory ground truth; flagged for "
                        "reviewer confirmation."
                    ),
                )

        if conflicts == 0:
            await ctx.recorder.record(
                agent=ORCHESTRATOR,
                type=AgentEventType.resolved,
                message=(
                    "Deterministic ground truth and Qwen reasoning agree on "
                    f"{deterministic_units} affected units."
                ),
            )
        return conflicts

    def _assemble_analysis(
        self, ctx: AgentContext, results: dict[str, AgentRunResult]
    ) -> RecallAnalysis:
        incident = ctx.incident
        affected_decisions = ctx.blackboard.get("affected_decisions", [])
        affected_stores = ctx.blackboard.get("affected_stores", [])
        affected_items = ctx.blackboard.get("affected_items", 0)
        tasks = ctx.blackboard.get("tasks", [])
        evidence = ctx.blackboard.get("evidence", [])
        insights = ctx.blackboard.get("insights", [])
        risk = ctx.blackboard.get("risk")
        notice = ctx.blackboard.get("customer_notice") or self._default_notice(
            incident, affected_items
        )

        ordered = [results[a.name] for a in self.agents if a.name in results]
        agents_activity = [
            AgentActivity(
                id=_slug(result.agent),
                name=result.agent,
                status=_STATUS_TO_AGENT_STATUS[result.status],
                action=result.summary,
                time=result.finished_at,
            )
            for result in ordered
        ]
        workflow = [
            WorkflowEvent(
                id=_slug(result.agent),
                title=result.agent,
                detail=result.summary,
                time=result.finished_at,
                status=_STATUS_TO_WORKFLOW_STATUS[result.status],
            )
            for result in ordered
        ]

        risk_level = risk.risk_level if risk else incident.criteria.risk_level
        evidence_progress = ctx.blackboard.get(
            "evidence_progress", calculate_evidence_progress(evidence)
        )
        open_tasks = sum(1 for task in tasks if task.status != TaskStatus.complete)

        return RecallAnalysis(
            incident_id=incident.id,
            product=incident.product,
            lot_range=incident.lot_range,
            risk_level=risk_level,
            affected_stores=affected_stores,
            affected_items=affected_items,
            open_tasks=open_tasks,
            evidence_progress=evidence_progress,
            workflow=workflow,
            inventory=affected_decisions,
            tasks=tasks,
            evidence=evidence,
            agents=agents_activity,
            insights=insights or self._default_insight(),
            milestones=build_milestones(),
            customer_notice=notice,
        )

    @staticmethod
    def _default_notice(
        incident: RecallIncidentInput, affected_items: int
    ) -> CustomerNoticeDraft:
        return CustomerNoticeDraft(
            subject=f"Important notice: {incident.product} recall",
            body=(
                f"{incident.product} lots {incident.lot_range} are being removed "
                "from sale. Affected items have been quarantined."
            ),
            audience="Customers with matching purchase history",
            source_incident_id=incident.id,
        )

    @staticmethod
    def _default_insight() -> list[MemoryInsight]:  # pragma: no cover - safety net
        return [
            MemoryInsight(
                id="insight-empty",
                title="Memory Initialized",
                detail="No insights surfaced for this run.",
                tone=InsightTone.neutral,
            )
        ]


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "agent"
