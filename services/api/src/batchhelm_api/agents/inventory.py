"""Inventory matching and shelf-vision agents."""

from __future__ import annotations

from batchhelm_api import inspection, qwen_tasks
from batchhelm_api.agents.base import Agent, AgentContext, AgentOutput
from batchhelm_api.agents.intake import DOCUMENT_EXTRACTION
from batchhelm_api.models import InventoryStatus, MemoryKind, OutputSource
from batchhelm_api.workflow import decide_inventory

INVENTORY_MATCHING = "Inventory Matching Agent"
SHELF_VISION = "Shelf Vision Agent"


class InventoryMatchingAgent(Agent):
    name = INVENTORY_MATCHING
    role = "Match recall criteria against inventory, resolving supplier aliases"
    depends_on = (DOCUMENT_EXTRACTION,)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        incident = ctx.incident
        decisions = [decide_inventory(item, incident) for item in incident.inventory]
        affected = [d for d in decisions if d.status == InventoryStatus.quarantined]
        affected_stores = sorted({d.store for d in affected})
        affected_items = sum(d.quarantined for d in affected)

        # Remember every supplier alias we saw so future recalls match faster.
        aliases = sorted({item.supplier_alias for item in incident.inventory})
        for alias in aliases:
            ctx.memory.remember(
                kind=MemoryKind.supplier_alias,
                key=alias.lower(),
                value=alias,
                detail=f"Observed on {incident.product} inventory",
                confidence=85,
            )

        outcome = await qwen_tasks.assess_inventory_match(
            ctx.gateway, incident, decisions, aliases
        )
        reasoning = outcome.value.reasoning
        await ctx.reason(
            self.name,
            reasoning,
            source=outcome.source,
            data={"matched_count": affected_items, "stores": affected_stores},
        )

        # Attach model reasoning to each quarantined decision for the evidence trail.
        if outcome.source == OutputSource.qwen:
            for decision in affected:
                decision.reason = (
                    f"{decision.reason} Qwen review: {reasoning[:160]}"
                )

        ctx.blackboard["decisions"] = decisions
        ctx.blackboard["affected_decisions"] = affected
        ctx.blackboard["affected_stores"] = affected_stores
        ctx.blackboard["affected_items"] = affected_items
        ctx.blackboard["supplier_aliases"] = aliases

        return AgentOutput(
            summary=(
                f"Quarantined {affected_items} units across "
                f"{len(affected_stores)} stores; normalized {len(aliases)} "
                "supplier aliases."
            ),
            reasoning=reasoning,
            confidence=outcome.confidence or 90,
            source=outcome.source,
            used_fallback=outcome.used_fallback,
            provider=outcome.provider,
            model=outcome.model,
        )


class ShelfVisionAgent(Agent):
    name = SHELF_VISION
    role = "Inspect shelf/stockroom photos for recall evidence with Qwen vision"
    depends_on = (DOCUMENT_EXTRACTION,)

    async def run(self, ctx: AgentContext) -> AgentOutput:
        has_real_image = "shelf_image_bytes" in ctx.blackboard
        if has_real_image:
            image_bytes: bytes = ctx.blackboard["shelf_image_bytes"]
            media_type: str = ctx.blackboard.get(
                "shelf_image_media_type", "image/png"
            )
        else:
            # No photo on this run: send the bundled demo photo so live Qwen
            # vision still receives a decodable image (a placeholder byte
            # string is rejected by the provider with HTTP 400).
            image_bytes = inspection.demo_shelf_image_bytes()
            media_type = "image/png"
        upload = ctx.blackboard.get("shelf_upload") or inspection.demo_upload_metadata()

        result = await inspection.inspect_image(
            gateway=ctx.gateway,
            upload=upload,
            image_bytes=image_bytes,
            media_type=media_type,
            incident=ctx.incident,
            allow_seeded_fallback=not has_real_image,
        )
        ctx.blackboard["inspection"] = result

        source = OutputSource.deterministic if result.used_fallback else OutputSource.qwen
        match_label = (
            "match"
            if result.recall_match is True
            else "no match"
            if result.recall_match is False
            else "unknown"
        )
        extracted_label = " ".join(
            part
            for part in (
                result.extracted.product_name,
                (
                    f"lot {result.extracted.lot_code}"
                    if result.extracted.lot_code
                    else ""
                ),
            )
            if part
        ) or "no label extracted"
        await ctx.reason(
            self.name,
            f"Inspected {upload.original_filename}; detected "
            f"{extracted_label} "
            f"({result.extracted.confidence}% confidence); "
            f"recall match: {match_label}.",
            source=source,
            data={"review_required": result.review_required},
        )

        return AgentOutput(
            summary=(
                f"Inspected {upload.original_filename}: {extracted_label} "
                f"({match_label})."
            ),
            reasoning=result.evidence_note,
            confidence=result.extracted.confidence,
            source=source,
            used_fallback=result.used_fallback,
            provider=result.provider,
            model=ctx.settings.qwen_vision_model,
        )
