"""Intake and document-extraction agents (front of the recall pipeline)."""

from __future__ import annotations

from batchhelm_api import qwen_tasks
from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.models import MemoryKind, OutputSource

RECALL_INTAKE = "Recall Intake Agent"
DOCUMENT_EXTRACTION = "Document Extraction Agent"


class RecallIntakeAgent(Agent):
    name = RECALL_INTAKE
    role = "Validate and normalize the incoming recall notice"
    depends_on: tuple[str, ...] = ()

    async def run(self, ctx: AgentContext) -> AgentOutput:
        incident = ctx.incident
        if not incident.notice_text.strip():
            raise ValueError("Recall notice text is empty; cannot triage incident.")

        await ctx.reason(
            self.name,
            f"Received supplier alert for {incident.product} "
            f"({len(incident.inventory)} inventory rows across "
            f"{len(incident.stores)} stores).",
        )
        ctx.blackboard["intake_valid"] = True
        return AgentOutput(
            summary=(
                f"Triaged {incident.product} recall from "
                f"{incident.criteria.source}."
            ),
            reasoning="Notice present and well-formed; routing to extraction.",
            confidence=99,
            source=OutputSource.deterministic,
            used_fallback=True,
        )


class DocumentExtractionAgent(Agent):
    name = DOCUMENT_EXTRACTION
    role = "Extract structured recall criteria from the raw notice with Qwen"
    depends_on = (RECALL_INTAKE,)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        outcome = await qwen_tasks.extract_recall(ctx.gateway, ctx.incident)
        extraction = outcome.value
        ctx.blackboard["extraction"] = extraction

        await ctx.reason(
            self.name,
            f"Extracted product '{extraction.product_name}', lots "
            f"{', '.join(extraction.affected_lots)}, UPCs "
            f"{', '.join(extraction.upcs) or 'none'}.",
            source=outcome.source,
            data={"summary": extraction.summary, "urgency": extraction.urgency},
        )

        if extraction.supplier:
            ctx.memory.remember(
                kind=MemoryKind.supplier_alias,
                key=extraction.supplier.lower(),
                value=extraction.supplier,
                detail=f"Source of {ctx.incident.product} recall",
                confidence=extraction.confidence or 80,
            )

        return AgentOutput(
            summary=(
                f"Structured {len(extraction.affected_lots)} affected lots and "
                f"{len(extraction.upcs)} UPCs from the notice."
            ),
            reasoning=extraction.summary,
            confidence=extraction.confidence,
            source=outcome.source,
            used_fallback=outcome.used_fallback,
            provider=outcome.provider,
            model=outcome.model,
        )
