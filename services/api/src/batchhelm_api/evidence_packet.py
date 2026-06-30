from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum

from batchhelm_api.models import (
    EvidencePacket,
    EvidencePacketSection,
    EvidenceStatus,
    ExtractedLabel,
    RecallAnalysis,
    RecallIncidentInput,
    ShelfInspectionResult,
    TaskStatus,
    UploadMetadata,
)


def build_demo_shelf_inspection() -> ShelfInspectionResult:
    upload = UploadMetadata(
        id="demo-shelf-photo",
        original_filename="store-b-cooler-spinach.png",
        stored_filename="demo-shelf-photo.png",
        media_type="image/png",
        size_bytes=204800,
        path="sample-data/store-b-cooler-spinach.png",
    )
    return ShelfInspectionResult(
        upload=upload,
        extracted=ExtractedLabel(
            product_name="Spinach 10 oz",
            lot_code="L2418",
            upc="008500001010",
            best_by="2026-07-18",
            confidence=96,
        ),
        recall_match=True,
        recommended_action="Quarantine item and attach photo to evidence packet.",
        review_required=False,
        evidence_note="Label fields match the active spinach recall criteria.",
        provider="qwen",
        used_fallback=True,
    )


def build_evidence_packet(
    *,
    incident: RecallIncidentInput,
    analysis: RecallAnalysis,
    inspection: ShelfInspectionResult,
    generated_at: datetime | None = None,
) -> EvidencePacket:
    timestamp = generated_at or datetime.now(timezone.utc)
    generated_at_value = timestamp.astimezone(timezone.utc).isoformat()
    sections = [
        _executive_summary(incident, analysis),
        _affected_inventory(analysis),
        _workflow_timeline(analysis),
        _staff_tasks(analysis),
        _evidence_checklist(analysis),
        _customer_notice(analysis),
        _memory_insights(analysis),
        _shelf_inspection(inspection),
        _review_notes(analysis),
    ]
    markdown = _render_markdown(
        incident=incident,
        generated_at=generated_at_value,
        sections=sections,
    )
    return EvidencePacket(
        incident_id=incident.id,
        packet_version=_packet_version(
            incident_id=incident.id,
            sections=sections,
        ),
        filename=f"batchhelm-{_slugify(incident.id)}-evidence.md",
        generated_at=generated_at_value,
        sections=sections,
        markdown=markdown,
    )


def _packet_version(
    *,
    incident_id: str,
    sections: list[EvidencePacketSection],
) -> str:
    canonical = json.dumps(
        {
            "incident_id": incident_id,
            "sections": [
                {"title": section.title, "body": section.body}
                for section in sections
            ],
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _executive_summary(
    incident: RecallIncidentInput,
    analysis: RecallAnalysis,
) -> EvidencePacketSection:
    body = "\n".join(
        [
            f"- Product: {incident.product}",
            f"- Lot range: {incident.lot_range}",
            f"- Incident status: {_label(incident.status)}",
            f"- Risk level: {_label(analysis.risk_level)}",
            f"- Source: {incident.criteria.source}",
            f"- Reason: {incident.criteria.reason}",
            f"- Affected stores: {', '.join(analysis.affected_stores)}",
            f"- Quarantined units: {analysis.affected_items}",
            f"- Open tasks: {analysis.open_tasks}",
            f"- Evidence readiness: {analysis.evidence_progress}%",
        ]
    )
    return EvidencePacketSection(title="Executive Summary", body=body)


def _affected_inventory(analysis: RecallAnalysis) -> EvidencePacketSection:
    rows = [
        [
            decision.store,
            decision.sku,
            decision.product,
            decision.lot,
            str(decision.quarantined),
            decision.location,
            f"{decision.confidence}%",
        ]
        for decision in analysis.inventory
    ]
    body = _table(
        ["Store", "SKU", "Product", "Lot", "Quarantined", "Location", "Confidence"],
        rows,
    )
    return EvidencePacketSection(title="Affected Inventory", body=body)


def _workflow_timeline(analysis: RecallAnalysis) -> EvidencePacketSection:
    rows = [
        [event.time, event.title, event.detail, _label(event.status)]
        for event in analysis.workflow
    ]
    body = _table(["Time", "Event", "Detail", "Status"], rows)
    return EvidencePacketSection(title="Workflow Timeline", body=body)


def _staff_tasks(analysis: RecallAnalysis) -> EvidencePacketSection:
    rows = [
        [
            task.title,
            task.store,
            _label(task.priority),
            task.assignee,
            task.due,
            _format_task_status(task.status),
        ]
        for task in analysis.tasks
    ]
    body = _table(["Task", "Store", "Priority", "Assignee", "Due", "Status"], rows)
    return EvidencePacketSection(title="Staff Task Checklist", body=body)


def _evidence_checklist(analysis: RecallAnalysis) -> EvidencePacketSection:
    rows = [
        [item.label, _format_evidence_status(item.status)]
        for item in analysis.evidence
    ]
    body = _table(["Evidence Item", "Status"], rows)
    return EvidencePacketSection(title="Evidence Checklist", body=body)


def _customer_notice(analysis: RecallAnalysis) -> EvidencePacketSection:
    notice = analysis.customer_notice
    body = "\n".join(
        [
            f"- Subject: {notice.subject}",
            f"- Audience: {notice.audience}",
            f"- Requires review: {'Yes' if notice.requires_review else 'No'}",
            "",
            notice.body,
        ]
    )
    return EvidencePacketSection(title="Customer Notice Draft", body=body)


def _memory_insights(analysis: RecallAnalysis) -> EvidencePacketSection:
    body = "\n".join(
        [
            f"- {insight.title}: {insight.detail} ({_label(insight.tone)})"
            for insight in analysis.insights
        ]
    )
    return EvidencePacketSection(title="Memory Insights", body=body)


def _shelf_inspection(inspection: ShelfInspectionResult) -> EvidencePacketSection:
    extracted = inspection.extracted
    body = "\n".join(
        [
            f"- Source file: {inspection.upload.original_filename}",
            f"- Product detected: {extracted.product_name}",
            f"- Lot detected: {extracted.lot_code}",
            f"- UPC detected: {extracted.upc}",
            f"- Best by: {extracted.best_by or 'Not visible'}",
            f"- Confidence: {extracted.confidence}%",
            f"- Recall match: {'Yes' if inspection.recall_match else 'No'}",
            f"- Review required: {'Yes' if inspection.review_required else 'No'}",
            f"- Provider mode: {'demo fallback' if inspection.used_fallback else inspection.provider}",
            "",
            inspection.evidence_note,
        ]
    )
    return EvidencePacketSection(title="Shelf Inspection Evidence", body=body)


def _review_notes(analysis: RecallAnalysis) -> EvidencePacketSection:
    incomplete_evidence = [
        item.label
        for item in analysis.evidence
        if item.status != EvidenceStatus.completed
    ]
    active_tasks = [
        task.title for task in analysis.tasks if task.status != TaskStatus.complete
    ]
    body = "\n".join(
        [
            "- Human review required before regulatory submission.",
            f"- Remaining evidence: {', '.join(incomplete_evidence)}",
            f"- Remaining tasks: {', '.join(active_tasks)}",
            "- Attach signed disposal records once product destruction is confirmed.",
        ]
    )
    return EvidencePacketSection(title="Review Notes", body=body)


def _render_markdown(
    *,
    incident: RecallIncidentInput,
    generated_at: str,
    sections: list[EvidencePacketSection],
) -> str:
    header = "\n".join(
        [
            "# BatchHelm Recall Evidence Packet",
            "",
            f"- Incident ID: {incident.id}",
            f"- Generated at: {generated_at}",
            f"- Product: {incident.product}",
        ]
    )
    rendered_sections = [
        f"## {section.title}\n\n{section.body}" for section in sections
    ]
    return "\n\n".join([header, *rendered_sections]) + "\n"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    header_row = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    table_rows = [
        "| " + " | ".join(_escape_cell(cell) for cell in row) + " |"
        for row in rows
    ]
    return "\n".join([header_row, separator, *table_rows])


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _label(value: Enum | str) -> str:
    raw_value = value.value if isinstance(value, Enum) else value
    return raw_value.replace("-", " ").title()


def _format_task_status(status: TaskStatus) -> str:
    labels = {
        TaskStatus.not_started: "Not Started",
        TaskStatus.in_progress: "In Progress",
        TaskStatus.blocked: "Blocked",
        TaskStatus.complete: "Complete",
    }
    return labels[status]


def _format_evidence_status(status: EvidenceStatus) -> str:
    labels = {
        EvidenceStatus.completed: "Completed",
        EvidenceStatus.in_progress: "In Progress",
        EvidenceStatus.pending: "Pending",
    }
    return labels[status]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "recall"
