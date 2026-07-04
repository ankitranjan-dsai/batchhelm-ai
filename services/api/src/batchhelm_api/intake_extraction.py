from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from batchhelm_api.intake_models import (
    IntakeFieldEvidence,
    RecallCriteriaDraft,
    RecallIncidentDraft,
)
from batchhelm_api.models import (
    IncidentStatus,
    OutputSource,
    RecallCriteria,
    RecallIncidentInput,
    Severity,
)

LOT_PATTERN = re.compile(
    r"\b(?:LOT\s*)?([A-Z]{1,4}\d{2,12})\b",
    re.IGNORECASE,
)
UPC_PATTERN = re.compile(
    r"\b(?:UPC|GTIN|BARCODE)"
    r"\s*(?:NO\.?|NUMBER|CODE)?\s*[:#-]?\s*(\d{8,14})\b",
    re.IGNORECASE,
)
RISK_WORDS = {
    "critical": Severity.critical,
    "death": Severity.critical,
    "hospitalization": Severity.critical,
    "contamination": Severity.high,
    "allergen": Severity.high,
    "mislabel": Severity.medium,
}
GENERIC_PRODUCT_HEADINGS = {
    "recall notice",
    "urgent recall notice",
    "urgent",
    "supplier alert",
    "recall alert",
}


class IntakeCompilationError(ValueError):
    pass


@dataclass(frozen=True)
class DraftExtraction:
    criteria: RecallCriteriaDraft
    evidence: tuple[IntakeFieldEvidence, ...]
    review_required: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = raw.strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _line_locator(text: str, value: str) -> str:
    needle = value.casefold()
    for index, line in enumerate(text.splitlines(), start=1):
        if needle in line.casefold():
            return f"line {index}"
    return "document"


def _product_candidate(lines: list[str]) -> str:
    if not lines:
        return ""
    candidate = lines[0].strip()
    folded = candidate.casefold().rstrip(":")
    if any(
        folded == heading
        or folded.startswith(f"{heading} ")
        or folded.startswith(f"{heading}:")
        for heading in GENERIC_PRODUCT_HEADINGS
    ):
        return ""
    product_match = re.fullmatch(r"product\s*:\s*(.+)", candidate, re.IGNORECASE)
    if product_match:
        candidate = product_match.group(1).strip()
    return candidate if 3 <= len(candidate) <= 120 else ""


def _risk(text: str) -> tuple[Severity | None, str]:
    folded = text.casefold()
    for word, severity in RISK_WORDS.items():
        if word in folded:
            return severity, word
    return None, ""


def _matching_line(lines: list[str], terms: tuple[str, ...]) -> str:
    for line in lines:
        folded = line.casefold()
        if any(term in folded for term in terms):
            return line
    return ""


def _evidence(
    *,
    intake_id: str,
    artifact_id: str | None,
    field_path: str,
    value: object,
    locator: str,
    confidence: int,
    created_at: str,
) -> IntakeFieldEvidence:
    return IntakeFieldEvidence(
        id=uuid4().hex,
        intake_id=intake_id,
        field_path=field_path,
        value=value,
        artifact_id=artifact_id,
        locator=locator,
        source=OutputSource.deterministic,
        confidence=confidence,
        requires_review=True,
        created_at=created_at,
    )


def safe_literal_extraction(
    notice_text: str,
    *,
    intake_id: str = "",
    artifact_id: str | None = None,
) -> DraftExtraction:
    lines = [line.strip() for line in notice_text.splitlines() if line.strip()]
    product = _product_candidate(lines)
    lots = _unique(match.group(1) for match in LOT_PATTERN.finditer(notice_text))
    upcs = _unique(match.group(1) for match in UPC_PATTERN.finditer(notice_text))
    risk_level, risk_word = _risk(notice_text)
    reason = (
        _matching_line(
            lines,
            tuple(RISK_WORDS),
        )
        if risk_level is not None
        else ""
    )
    source = _matching_line(
        lines,
        ("supplier", "manufacturer", "source", "recall alert"),
    )
    criteria = RecallCriteriaDraft(
        product_name=product,
        affected_lots=lots,
        upcs=upcs,
        risk_level=risk_level,
        reason=reason,
        source=source,
    )
    created_at = _now()
    evidence: list[IntakeFieldEvidence] = []
    if product:
        evidence.append(
            _evidence(
                intake_id=intake_id,
                artifact_id=artifact_id,
                field_path="criteria.product_name",
                value=product,
                locator=_line_locator(notice_text, product),
                confidence=65,
                created_at=created_at,
            )
        )
    if lots:
        evidence.append(
            _evidence(
                intake_id=intake_id,
                artifact_id=artifact_id,
                field_path="criteria.affected_lots",
                value=lots,
                locator=_line_locator(notice_text, lots[0]),
                confidence=65,
                created_at=created_at,
            )
        )
    if upcs:
        evidence.append(
            _evidence(
                intake_id=intake_id,
                artifact_id=artifact_id,
                field_path="criteria.upcs",
                value=upcs,
                locator=_line_locator(notice_text, upcs[0]),
                confidence=65,
                created_at=created_at,
            )
        )
    if risk_level is not None:
        evidence.append(
            _evidence(
                intake_id=intake_id,
                artifact_id=artifact_id,
                field_path="criteria.risk_level",
                value=risk_level.value,
                locator=_line_locator(notice_text, risk_word),
                confidence=55,
                created_at=created_at,
            )
        )
    if reason:
        evidence.append(
            _evidence(
                intake_id=intake_id,
                artifact_id=artifact_id,
                field_path="criteria.reason",
                value=reason,
                locator=_line_locator(notice_text, reason),
                confidence=55,
                created_at=created_at,
            )
        )
    if source:
        evidence.append(
            _evidence(
                intake_id=intake_id,
                artifact_id=artifact_id,
                field_path="criteria.source",
                value=source,
                locator=_line_locator(notice_text, source),
                confidence=55,
                created_at=created_at,
            )
        )
    return DraftExtraction(
        criteria=criteria,
        evidence=tuple(evidence),
        review_required=True,
    )


def _clean_list(values: list[str]) -> list[str]:
    return _unique(list(values))


def compile_incident_snapshot(
    intake_id: str,
    draft: RecallIncidentDraft,
    *,
    now: datetime | None = None,
) -> RecallIncidentInput:
    product = draft.criteria.product_name.strip()
    lots = _clean_list(draft.criteria.affected_lots)
    upcs = _clean_list(draft.criteria.upcs)
    reason = draft.criteria.reason.strip()
    source = draft.criteria.source.strip()
    notice_text = draft.notice_text.strip()

    if not product:
        raise IntakeCompilationError("A confirmed product name is required.")
    if not lots and not upcs:
        raise IntakeCompilationError(
            "At least one confirmed lot or UPC is required."
        )
    if draft.criteria.risk_level is None:
        raise IntakeCompilationError("A confirmed risk level is required.")
    if not reason:
        raise IntakeCompilationError("A confirmed recall reason is required.")
    if not source:
        raise IntakeCompilationError("A confirmed notice source is required.")
    if not notice_text:
        raise IntakeCompilationError("The source notice text is required.")
    if not draft.inventory:
        raise IntakeCompilationError("At least one inventory row is required.")

    opened_at = now or datetime.now(timezone.utc)
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    opened_at = opened_at.astimezone(timezone.utc)
    identity = hashlib.sha256(
        f"batchhelm:intake:{intake_id}".encode("utf-8")
    ).hexdigest()[:12]
    lot_range = ", ".join(lots) if lots else f"UPC {', '.join(upcs)}"
    stores = sorted({item.store.strip() for item in draft.inventory if item.store.strip()})

    return RecallIncidentInput(
        id=f"intake-{intake_id}-{identity}",
        product=product,
        lot_range=lot_range,
        status=IncidentStatus.active,
        opened_at=opened_at.isoformat(),
        stores=stores,
        criteria=RecallCriteria(
            product_name=product,
            affected_lots=lots,
            upcs=upcs,
            risk_level=draft.criteria.risk_level,
            reason=reason,
            source=source,
        ),
        notice_text=notice_text,
        inventory=list(draft.inventory),
    )
