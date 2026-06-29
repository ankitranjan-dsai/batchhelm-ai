"""Qwen-driven workflow tasks.

Each function here turns a step of the recall workflow into a structured Qwen
call. Qwen output is always validated against a Pydantic schema; if the model
is unconfigured, returns invalid JSON, or returns a shape we cannot trust, we
repair to a deterministic fallback so the workflow never breaks.

This is the layer that lets Qwen *drive* the main workflow (extraction, match
reasoning, risk classification, customer comms, management briefing) while
keeping the product reliable for demos and tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from batchhelm_api.models import (
    CustomerNoticeContent,
    InventoryDecision,
    InventoryMatchReasoning,
    ManagementBriefing,
    ModelJSONRequest,
    ModelJSONResponse,
    OutputSource,
    RecallAnalysis,
    RecallExtraction,
    RecallIncidentInput,
    RiskAssessment,
    Severity,
)
from batchhelm_api.qwen import QwenGateway, QwenGatewayError

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class QwenOutcome(Generic[T]):
    """The validated result of a single Qwen workflow task."""

    value: T
    source: OutputSource
    used_fallback: bool
    provider: str
    model: str

    @property
    def confidence(self) -> int:
        return int(getattr(self.value, "confidence", 0) or 0)


async def _run(
    gateway: QwenGateway,
    request: ModelJSONRequest,
    schema: type[T],
    fallback: T,
) -> QwenOutcome[T]:
    """Call Qwen, validate the JSON into ``schema``, or repair to ``fallback``."""

    try:
        response: ModelJSONResponse = await gateway.complete_json(request)
    except (QwenGatewayError, Exception):  # noqa: BLE001 - degrade gracefully
        return QwenOutcome(
            value=fallback,
            source=OutputSource.deterministic,
            used_fallback=True,
            provider="qwen",
            model=gateway.settings.qwen_text_model,
        )

    if response.used_fallback:
        return QwenOutcome(
            value=fallback,
            source=OutputSource.deterministic,
            used_fallback=True,
            provider=response.provider,
            model=response.model,
        )

    try:
        value = schema.model_validate(response.content)
    except ValidationError:
        # Qwen answered but the shape was wrong: repair to the deterministic value.
        return QwenOutcome(
            value=fallback,
            source=OutputSource.deterministic,
            used_fallback=True,
            provider=response.provider,
            model=response.model,
        )

    return QwenOutcome(
        value=value,
        source=OutputSource.qwen,
        used_fallback=False,
        provider=response.provider,
        model=response.model,
    )


async def extract_recall(
    gateway: QwenGateway, incident: RecallIncidentInput
) -> QwenOutcome[RecallExtraction]:
    fallback = RecallExtraction(
        product_name=incident.criteria.product_name,
        affected_lots=list(incident.criteria.affected_lots),
        upcs=list(incident.criteria.upcs),
        supplier=incident.criteria.source,
        risk_level=incident.criteria.risk_level,
        urgency="Remove from sale immediately and quarantine affected lots.",
        summary=(
            f"{incident.product} lots {incident.lot_range} are affected by "
            f"{incident.criteria.reason.lower()}."
        ),
        confidence=92,
    )
    request = ModelJSONRequest(
        system=(
            "You extract structured recall criteria from a raw recall notice. "
            "Return ONLY a JSON object with keys: product_name (string), "
            "affected_lots (array of strings), upcs (array of strings), supplier "
            "(string), risk_level (one of low|medium|high|critical), urgency "
            "(string), summary (string), confidence (integer 0-100)."
        ),
        user=f"Recall notice:\n{incident.notice_text}",
        fallback=fallback.model_dump(mode="json"),
    )
    return await _run(gateway, request, RecallExtraction, fallback)


async def assess_inventory_match(
    gateway: QwenGateway,
    incident: RecallIncidentInput,
    decisions: list[InventoryDecision],
    known_aliases: list[str],
) -> QwenOutcome[InventoryMatchReasoning]:
    matched = sum(1 for decision in decisions if decision.quarantined > 0)
    fallback = InventoryMatchReasoning(
        reasoning=(
            f"Matched {matched} inventory rows where lot, UPC, and product name "
            "all align with the recall criteria. Supplier aliases were normalized "
            "before comparison to avoid false negatives."
        ),
        matched_count=matched,
        flagged_aliases=known_aliases[:3],
        confidence=90,
    )
    alias_lines = "\n".join(
        f"- {item.store} | {item.product} | lot {item.lot} | "
        f"alias '{item.supplier_alias}' | on_hand {item.on_hand}"
        for item in incident.inventory
    )
    request = ModelJSONRequest(
        system=(
            "You explain how inventory rows were matched against a product "
            "recall. Account for supplier name aliases. Return ONLY JSON with "
            "keys: reasoning (string), matched_count (integer), flagged_aliases "
            "(array of strings), confidence (integer 0-100)."
        ),
        user=(
            f"Recall criteria: product '{incident.criteria.product_name}', lots "
            f"{incident.criteria.affected_lots}, upcs {incident.criteria.upcs}.\n"
            f"Inventory rows:\n{alias_lines}"
        ),
        fallback=fallback.model_dump(mode="json"),
    )
    return await _run(gateway, request, InventoryMatchReasoning, fallback)


async def assess_risk(
    gateway: QwenGateway,
    incident: RecallIncidentInput,
    affected_items: int,
    affected_stores: list[str],
) -> QwenOutcome[RiskAssessment]:
    fallback = RiskAssessment(
        risk_level=incident.criteria.risk_level,
        rationale=(
            f"{affected_items} units across {len(affected_stores)} stores match a "
            f"{incident.criteria.risk_level.value} supplier alert citing "
            f"{incident.criteria.reason.lower()}."
        ),
        recommended_priority=Severity.high,
        confidence=89,
    )
    request = ModelJSONRequest(
        system=(
            "You classify the operational risk of a product recall. Return ONLY "
            "JSON with keys: risk_level (low|medium|high|critical), rationale "
            "(string), recommended_priority (low|medium|high|critical), "
            "confidence (integer 0-100)."
        ),
        user=(
            f"Product: {incident.product}. Reason: {incident.criteria.reason}. "
            f"Affected units: {affected_items}. Affected stores: "
            f"{', '.join(affected_stores) or 'none'}. Supplier risk level: "
            f"{incident.criteria.risk_level.value}."
        ),
        fallback=fallback.model_dump(mode="json"),
    )
    return await _run(gateway, request, RiskAssessment, fallback)


async def draft_customer_notice(
    gateway: QwenGateway,
    incident: RecallIncidentInput,
    affected_items: int,
) -> QwenOutcome[CustomerNoticeContent]:
    fallback = CustomerNoticeContent(
        subject=f"Important notice: {incident.product} recall",
        body=(
            f"We are removing {incident.product} lots {incident.lot_range} from "
            "sale after a supplier alert. Our records show "
            f"{affected_items} affected items across our stores. Customers who "
            "purchased this product should not consume it and may return it for a "
            "full refund. Store teams are available to answer questions."
        ),
        audience="Customers with matching loyalty-card or order history",
        confidence=88,
    )
    request = ModelJSONRequest(
        system=(
            "You draft a clear, calm customer recall notice for a small grocery "
            "operator. Do not invent facts. Return ONLY JSON with keys: subject "
            "(string), body (string), audience (string), confidence (integer "
            "0-100)."
        ),
        user=(
            f"Product: {incident.product}. Lots: {incident.lot_range}. Reason: "
            f"{incident.criteria.reason}. Affected items: {affected_items}."
        ),
        fallback=fallback.model_dump(mode="json"),
    )
    return await _run(gateway, request, CustomerNoticeContent, fallback)


async def generate_briefing(
    gateway: QwenGateway,
    incident: RecallIncidentInput,
    analysis: RecallAnalysis,
) -> QwenOutcome[ManagementBriefing]:
    open_actions = [task.title for task in analysis.tasks if task.status.value != "complete"]
    fallback = ManagementBriefing(
        headline=(
            f"{incident.product} recall active across "
            f"{len(analysis.affected_stores)} stores"
        ),
        situation=(
            f"{analysis.affected_items} units of {incident.product} lots "
            f"{incident.lot_range} are quarantined. Risk level is "
            f"{analysis.risk_level.value}. Evidence readiness is "
            f"{analysis.evidence_progress}%."
        ),
        actions=open_actions[:4]
        or ["Confirm disposal records", "Finalize regulatory filing"],
        risks=[
            "Customer notice still pending reviewer approval",
            "Disposal/destruction records not yet attached",
        ],
        next_review="Customer notice approval due today 11:00 AM",
        confidence=87,
    )
    request = ModelJSONRequest(
        system=(
            "You write a concise management briefing for a recall incident. "
            "Return ONLY JSON with keys: headline (string), situation (string), "
            "actions (array of strings), risks (array of strings), next_review "
            "(string), confidence (integer 0-100)."
        ),
        user=(
            f"Product: {incident.product}. Lots: {incident.lot_range}. Affected "
            f"units: {analysis.affected_items}. Affected stores: "
            f"{', '.join(analysis.affected_stores)}. Open tasks: "
            f"{', '.join(open_actions) or 'none'}. Evidence readiness: "
            f"{analysis.evidence_progress}%. Risk: {analysis.risk_level.value}."
        ),
        fallback=fallback.model_dump(mode="json"),
    )
    outcome = await _run(gateway, request, ManagementBriefing, fallback)
    briefing = outcome.value.model_copy(
        update={
            "source": outcome.source,
            "provider": outcome.provider,
            "used_fallback": outcome.used_fallback,
        }
    )
    return QwenOutcome(
        value=briefing,
        source=outcome.source,
        used_fallback=outcome.used_fallback,
        provider=outcome.provider,
        model=outcome.model,
    )
