from __future__ import annotations

from collections.abc import Iterable

from batchhelm_api.models import (
    AgentActivity,
    AgentStatus,
    CustomerNoticeDraft,
    EvidenceItem,
    EvidenceStatus,
    InsightTone,
    InventoryDecision,
    InventoryItem,
    InventoryStatus,
    MemoryInsight,
    Milestone,
    RecallAnalysis,
    RecallIncidentInput,
    Severity,
    StaffTask,
    TaskStatus,
    WorkflowEvent,
    WorkflowStatus,
)


def analyze_recall_incident(incident: RecallIncidentInput) -> RecallAnalysis:
    decisions = [_decide_inventory(item, incident) for item in incident.inventory]
    affected_decisions = [
        decision for decision in decisions if decision.status == InventoryStatus.quarantined
    ]
    affected_stores = sorted({decision.store for decision in affected_decisions})
    affected_items = sum(decision.quarantined for decision in affected_decisions)
    tasks = _build_tasks(affected_stores)
    evidence = _build_evidence()

    return RecallAnalysis(
        incident_id=incident.id,
        product=incident.product,
        lot_range=incident.lot_range,
        risk_level=incident.criteria.risk_level,
        affected_stores=affected_stores,
        affected_items=affected_items,
        open_tasks=sum(1 for task in tasks if task.status != TaskStatus.complete),
        evidence_progress=calculate_evidence_progress(evidence),
        workflow=_build_workflow(affected_items),
        inventory=affected_decisions,
        tasks=tasks,
        evidence=evidence,
        agents=_build_agents(),
        insights=_build_insights(),
        milestones=_build_milestones(),
        customer_notice=build_customer_notice(incident, affected_items),
    )


def calculate_evidence_progress(evidence: Iterable[EvidenceItem]) -> int:
    evidence_list = list(evidence)
    if not evidence_list:
        return 0

    score = 0.0
    for item in evidence_list:
        if item.status == EvidenceStatus.completed:
            score += 1.0
        elif item.status == EvidenceStatus.in_progress:
            score += 0.42

    return round((score / len(evidence_list)) * 100)


def build_customer_notice(
    incident: RecallIncidentInput, affected_items: int
) -> CustomerNoticeDraft:
    body = (
        f"Central Foods Co. is removing {incident.product} lots "
        f"{incident.lot_range} from sale after a supplier alert. Our records show "
        f"{affected_items} items were identified across affected stores. Customers "
        "who purchased this product should not consume it and may return it for a "
        "refund. Store teams are available to answer questions."
    )
    return CustomerNoticeDraft(
        subject=f"Important notice: {incident.product} recall",
        body=body,
        audience="Customers with matching loyalty-card or order history",
        source_incident_id=incident.id,
    )


def _decide_inventory(
    item: InventoryItem, incident: RecallIncidentInput
) -> InventoryDecision:
    lot_match = item.lot in incident.criteria.affected_lots
    upc_match = not incident.criteria.upcs or item.upc in incident.criteria.upcs
    product_match = incident.criteria.product_name.lower() in item.product.lower()
    affected = lot_match and upc_match and product_match

    if affected:
        confidence = 93 + min(5, incident.criteria.affected_lots.index(item.lot))
        return InventoryDecision(
            id=item.id,
            store=item.store,
            sku=item.sku,
            product=item.product,
            lot=item.lot,
            on_hand=item.on_hand,
            quarantined=item.on_hand,
            confidence=min(confidence, 98),
            status=InventoryStatus.quarantined,
            location=item.location,
            reason="Lot, UPC, and product name match recall criteria.",
        )

    return InventoryDecision(
        id=item.id,
        store=item.store,
        sku=item.sku,
        product=item.product,
        lot=item.lot,
        on_hand=item.on_hand,
        quarantined=0,
        confidence=88,
        status=InventoryStatus.clear,
        location=item.location,
        reason="Inventory row does not match all recall criteria.",
    )


def _build_workflow(affected_items: int) -> list[WorkflowEvent]:
    return [
        WorkflowEvent(
            id="trigger",
            title="Recall Trigger Detected",
            detail="Contamination alert from supplier",
            time="Today 8:12 AM",
            status=WorkflowStatus.complete,
        ),
        WorkflowEvent(
            id="impact",
            title="Impact Assessment",
            detail="Criteria extracted and normalized",
            time="Today 8:15 AM",
            status=WorkflowStatus.complete,
        ),
        WorkflowEvent(
            id="inventory",
            title="Inventory Scan",
            detail=f"Scanned 2 stores, {affected_items} items",
            time="Today 8:18 AM",
            status=WorkflowStatus.complete,
        ),
        WorkflowEvent(
            id="alerts",
            title="Notifications",
            detail="Internal alerts sent",
            time="Today 8:20 AM",
            status=WorkflowStatus.complete,
        ),
        WorkflowEvent(
            id="notice",
            title="Customer Notice Drafted",
            detail="Draft generated for review",
            time="Today 8:25 AM",
            status=WorkflowStatus.active,
        ),
        WorkflowEvent(
            id="filing",
            title="Regulatory Filing",
            detail="Evidence packet in progress",
            time="Today 8:29 AM",
            status=WorkflowStatus.pending,
        ),
    ]


def _build_tasks(affected_stores: list[str]) -> list[StaffTask]:
    has_store_a = "Store A" in affected_stores
    return [
        StaffTask(
            id="task-1",
            title="Review customer notice draft",
            store="All Stores",
            priority=Severity.high,
            assignee="J. Martinez",
            initials="JM",
            due="Today 11:00 AM",
            status=TaskStatus.in_progress,
        ),
        StaffTask(
            id="task-2",
            title="Verify quarantined inventory",
            store="Store A" if has_store_a else affected_stores[0],
            priority=Severity.high,
            assignee="A. Patel",
            initials="AP",
            due="Today 12:00 PM",
            status=TaskStatus.in_progress,
        ),
        StaffTask(
            id="task-3",
            title="Post in-store recall signage",
            store="Store B",
            priority=Severity.medium,
            assignee="T. Nguyen",
            initials="TN",
            due="Today 2:00 PM",
            status=TaskStatus.not_started,
        ),
        StaffTask(
            id="task-4",
            title="Customer service brief",
            store="All Stores",
            priority=Severity.medium,
            assignee="S. Johnson",
            initials="SJ",
            due="Tomorrow 9:00 AM",
            status=TaskStatus.not_started,
        ),
        StaffTask(
            id="task-5",
            title="Confirm product destruction",
            store="Store A" if has_store_a else affected_stores[0],
            priority=Severity.high,
            assignee="A. Patel",
            initials="AP",
            due="Tomorrow 3:00 PM",
            status=TaskStatus.not_started,
        ),
    ]


def _build_evidence() -> list[EvidenceItem]:
    return [
        EvidenceItem(id="ev-1", label="Recall Initiation Report", status=EvidenceStatus.completed),
        EvidenceItem(id="ev-2", label="Inventory Impact Report", status=EvidenceStatus.completed),
        EvidenceItem(id="ev-3", label="Customer Communication", status=EvidenceStatus.in_progress),
        EvidenceItem(id="ev-4", label="Supplier Communications", status=EvidenceStatus.completed),
        EvidenceItem(
            id="ev-5",
            label="Disposal / Destruction Records",
            status=EvidenceStatus.in_progress,
        ),
        EvidenceItem(id="ev-6", label="Regulatory Filing Package", status=EvidenceStatus.pending),
    ]


def _build_agents() -> list[AgentActivity]:
    return [
        AgentActivity(
            id="agent-1",
            name="Inventory Agent",
            status=AgentStatus.active,
            action="Scanning Store B cooler inventory",
            time="Today 8:28 AM",
        ),
        AgentActivity(
            id="agent-2",
            name="Notifications Agent",
            status=AgentStatus.active,
            action="Preparing customer email draft",
            time="Today 8:27 AM",
        ),
        AgentActivity(
            id="agent-3",
            name="Compliance Agent",
            status=AgentStatus.active,
            action="Building regulatory packet",
            time="Today 8:26 AM",
        ),
        AgentActivity(
            id="agent-4",
            name="Supplier Agent",
            status=AgentStatus.waiting,
            action="Awaiting supplier test results",
            time="Today 8:20 AM",
        ),
        AgentActivity(
            id="agent-5",
            name="Analytics Agent",
            status=AgentStatus.active,
            action="Monitoring return rate signals",
            time="Today 8:19 AM",
        ),
    ]


def _build_insights() -> list[MemoryInsight]:
    return [
        MemoryInsight(
            id="insight-1",
            title="Similar Recall Found",
            detail="Apr 2023 romaine lettuce, 72% similarity",
            tone=InsightTone.success,
        ),
        MemoryInsight(
            id="insight-2",
            title="Effective Communication",
            detail="Email template used in 3 recalls with high engagement",
            tone=InsightTone.neutral,
        ),
        MemoryInsight(
            id="insight-3",
            title="Return Rate Spike",
            detail="Leafy greens category +18% vs 7-day baseline",
            tone=InsightTone.warning,
        ),
    ]


def _build_milestones() -> list[Milestone]:
    return [
        Milestone(
            id="mile-1",
            title="Customer notice review",
            due="Due today 11:00 AM",
            remaining="1h 32m",
            tone=Severity.high,
        ),
        Milestone(
            id="mile-2",
            title="Inventory verification",
            due="Due today 12:00 PM",
            remaining="2h 32m",
            tone=Severity.high,
        ),
        Milestone(
            id="mile-3",
            title="Regulatory submission",
            due="Due tomorrow 5:00 PM",
            remaining="1d 7h",
            tone=InsightTone.neutral,
        ),
    ]
