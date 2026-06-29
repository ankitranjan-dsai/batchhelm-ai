"""Risk, task, and communications agents (the operational response)."""

from __future__ import annotations

from batchhelm_api import qwen_tasks
from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.agents.inventory import INVENTORY_MATCHING, SHELF_VISION
from batchhelm_api.models import CustomerNoticeDraft, OutputSource

RISK_SCORING = "Risk Scoring Agent"
OPERATIONS_TASK = "Operations Task Agent"
COMMUNICATIONS = "Communications Agent"


class RiskScoringAgent(Agent):
    name = RISK_SCORING
    role = "Classify operational risk and recommend response priority with Qwen"
    depends_on = (INVENTORY_MATCHING, SHELF_VISION)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        affected_items = ctx.blackboard.get("affected_items", 0)
        affected_stores = ctx.blackboard.get("affected_stores", [])
        outcome = await qwen_tasks.assess_risk(
            ctx.gateway, ctx.incident, affected_items, affected_stores
        )
        risk = outcome.value
        ctx.blackboard["risk"] = risk

        await ctx.reason(
            self.name,
            f"Risk {risk.risk_level.value}: {risk.rationale}",
            source=outcome.source,
            data={"recommended_priority": risk.recommended_priority.value},
        )
        return AgentOutput(
            summary=(
                f"Classified risk as {risk.risk_level.value} "
                f"(priority {risk.recommended_priority.value})."
            ),
            reasoning=risk.rationale,
            confidence=outcome.confidence or 89,
            source=outcome.source,
            used_fallback=outcome.used_fallback,
            provider=outcome.provider,
            model=outcome.model,
        )


class OperationsTaskAgent(Agent):
    name = OPERATIONS_TASK
    role = "Generate removal, quarantine, disposal, and notice tasks for staff"
    depends_on = (INVENTORY_MATCHING, RISK_SCORING)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        from batchhelm_api.workflow import build_staff_tasks

        affected_stores = ctx.blackboard.get("affected_stores") or ["All Stores"]
        tasks = build_staff_tasks(affected_stores)
        ctx.blackboard["tasks"] = tasks

        await ctx.reason(
            self.name,
            f"Generated {len(tasks)} staff tasks across "
            f"{len(affected_stores)} affected stores.",
        )
        return AgentOutput(
            summary=f"Created {len(tasks)} removal, quarantine, and notice tasks.",
            reasoning="Tasks derived from affected stores and recall severity.",
            confidence=95,
            source=OutputSource.deterministic,
            used_fallback=True,
        )


class CommunicationsAgent(Agent):
    name = COMMUNICATIONS
    role = "Draft the customer recall notice with Qwen"
    depends_on = (INVENTORY_MATCHING, RISK_SCORING)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        affected_items = ctx.blackboard.get("affected_items", 0)
        outcome = await qwen_tasks.draft_customer_notice(
            ctx.gateway, ctx.incident, affected_items
        )
        content = outcome.value
        notice = CustomerNoticeDraft(
            subject=content.subject,
            body=content.body,
            audience=content.audience,
            requires_review=True,
            source_incident_id=ctx.incident.id,
        )
        ctx.blackboard["customer_notice"] = notice

        await ctx.reason(
            self.name,
            f"Drafted customer notice '{content.subject}' for review.",
            source=outcome.source,
        )
        return AgentOutput(
            summary="Drafted customer recall notice (pending reviewer approval).",
            reasoning=content.body[:200],
            confidence=outcome.confidence or 88,
            source=outcome.source,
            used_fallback=outcome.used_fallback,
            provider=outcome.provider,
            model=outcome.model,
        )


__all__ = [
    "RiskScoringAgent",
    "OperationsTaskAgent",
    "CommunicationsAgent",
    "RISK_SCORING",
    "OPERATIONS_TASK",
    "COMMUNICATIONS",
]
