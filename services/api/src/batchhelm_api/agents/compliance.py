"""Compliance evidence and memory agents (the durable tail of the pipeline)."""

from __future__ import annotations

from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.agents.inventory import INVENTORY_MATCHING, SHELF_VISION
from batchhelm_api.agents.operations import COMMUNICATIONS
from batchhelm_api.models import (
    InsightTone,
    InventoryStatus,
    MemoryInsight,
    MemoryKind,
    OutputSource,
)
from batchhelm_api.workflow import build_evidence_items, calculate_evidence_progress

COMPLIANCE_EVIDENCE = "Compliance Evidence Agent"
MEMORY_AGENT = "Memory Agent"


class ComplianceEvidenceAgent(Agent):
    name = COMPLIANCE_EVIDENCE
    role = "Assemble the audit-ready evidence checklist"
    depends_on = (INVENTORY_MATCHING, SHELF_VISION, COMMUNICATIONS)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        evidence = build_evidence_items()
        progress = calculate_evidence_progress(evidence)
        ctx.blackboard["evidence"] = evidence
        ctx.blackboard["evidence_progress"] = progress

        await ctx.reason(
            self.name,
            f"Compiled {len(evidence)} evidence items; packet readiness "
            f"{progress}%.",
        )
        return AgentOutput(
            summary=f"Evidence packet {progress}% ready ({len(evidence)} items).",
            reasoning="Evidence checklist tracks regulatory submission readiness.",
            confidence=90,
            source=OutputSource.deterministic,
            used_fallback=True,
        )


class MemoryAgent(Agent):
    name = MEMORY_AGENT
    role = "Persist aliases, decisions, and false positives; surface prior experience"
    depends_on = (INVENTORY_MATCHING,)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        incident = ctx.incident
        decisions = ctx.blackboard.get("decisions", [])

        # Persist this incident's outcome so future recalls can reference it.
        ctx.memory.remember(
            kind=MemoryKind.decision,
            key=incident.id,
            value=f"Quarantined {ctx.blackboard.get('affected_items', 0)} units",
            detail=f"{incident.product} | {incident.criteria.reason}",
            confidence=92,
        )

        # Rows that share the product but did not match are recurring false-positive
        # candidates worth remembering so reviewers are not re-prompted.
        false_positives = [
            d
            for d in decisions
            if d.status == InventoryStatus.clear
            and incident.criteria.product_name.lower() in d.product.lower()
        ]
        for decision in false_positives:
            ctx.memory.remember(
                kind=MemoryKind.false_positive,
                key=f"{decision.sku}:{decision.lot}",
                value=f"{decision.product} lot {decision.lot}",
                detail="Product name matched but lot/UPC did not — not affected.",
                confidence=80,
            )

        insights = self._build_insights(ctx, false_positive_count=len(false_positives))
        ctx.blackboard["insights"] = insights
        await ctx.reason(
            self.name,
            f"Memory now holds {len(ctx.memory.list_records())} records; "
            f"surfaced {len(insights)} insights.",
            source=OutputSource.memory,
        )
        return AgentOutput(
            summary=(
                f"Persisted decision + {len(false_positives)} false positives; "
                f"{len(insights)} insights surfaced from memory."
            ),
            reasoning="Memory accumulates aliases, decisions, and false positives.",
            confidence=93,
            source=OutputSource.memory,
            used_fallback=True,
        )

    def _build_insights(
        self, ctx: AgentContext, *, false_positive_count: int
    ) -> list[MemoryInsight]:
        aliases = ctx.memory.list_by_kind(MemoryKind.supplier_alias)
        decisions = ctx.memory.list_by_kind(MemoryKind.decision)
        insights: list[MemoryInsight] = []

        if aliases:
            insights.append(
                MemoryInsight(
                    id="insight-aliases",
                    title="Supplier Aliases Learned",
                    detail=(
                        f"{len(aliases)} aliases normalized so future recalls match "
                        "without re-teaching."
                    ),
                    tone=InsightTone.success,
                )
            )

        prior_decisions = [d for d in decisions if d.key != ctx.incident.id]
        if prior_decisions:
            previous = prior_decisions[0]
            insights.append(
                MemoryInsight(
                    id="insight-prior",
                    title="Similar Recall Found",
                    detail=f"Prior decision on record: {previous.detail}",
                    tone=InsightTone.success,
                )
            )
        else:
            insights.append(
                MemoryInsight(
                    id="insight-first",
                    title="First Recall For This Product",
                    detail="No prior decision on file; this run seeds memory.",
                    tone=InsightTone.neutral,
                )
            )

        if false_positive_count:
            insights.append(
                MemoryInsight(
                    id="insight-false-positive",
                    title="False Positives Suppressed",
                    detail=(
                        f"{false_positive_count} look-alike rows remembered as not "
                        "affected."
                    ),
                    tone=InsightTone.warning,
                )
            )
        return insights
