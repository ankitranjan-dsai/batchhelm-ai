from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from batchhelm_api.intake_models import (
    IntakeArtifact,
    IntakeFieldEvidence,
    RecallCriteriaDraft,
    RecallIncidentDraft,
)
from batchhelm_api.models import (
    IncidentStatus,
    ModelImageJSONRequest,
    ModelJSONRequest,
    ModelJSONResponse,
    OutputSource,
    RecallCriteria,
    RecallIncidentInput,
    Severity,
)
from batchhelm_api.notice_parser import ParsedNotice
from batchhelm_api.qwen import QwenGateway

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


class ExtractedStringField(BaseModel):
    value: str = ""
    confidence: int = Field(default=0, ge=0, le=100)


class ExtractedListField(BaseModel):
    value: list[str] = Field(default_factory=list)
    confidence: int = Field(default=0, ge=0, le=100)


class ExtractedRiskField(BaseModel):
    value: Severity | None = None
    confidence: int = Field(default=0, ge=0, le=100)


class IntakeRecallExtraction(BaseModel):
    product_name: ExtractedStringField
    affected_lots: ExtractedListField
    upcs: ExtractedListField
    risk_level: ExtractedRiskField
    reason: ExtractedStringField
    source: ExtractedStringField


@dataclass
class _Candidate:
    field: str
    value: str | list[str] | Severity
    confidence: int
    locator: str
    modality: str
    requires_review: bool


def _empty_extraction_payload() -> dict[str, object]:
    return {
        "product_name": {"value": "", "confidence": 0},
        "affected_lots": {"value": [], "confidence": 0},
        "upcs": {"value": [], "confidence": 0},
        "risk_level": {"value": None, "confidence": 0},
        "reason": {"value": "", "confidence": 0},
        "source": {"value": "", "confidence": 0},
    }


def _validated_extraction(
    response: ModelJSONResponse,
) -> IntakeRecallExtraction | None:
    if response.used_fallback:
        return None
    try:
        return IntakeRecallExtraction.model_validate(response.content)
    except ValidationError:
        return None


def _text_contains(text: str, value: str) -> bool:
    return bool(value.strip()) and value.strip().casefold() in text.casefold()


def _text_locator(
    parsed_notice: ParsedNotice,
    value: str,
) -> str:
    for page in parsed_notice.text_pages:
        if _text_contains(page.text, value):
            return page.locator
    if parsed_notice.text_pages:
        return parsed_notice.text_pages[0].locator
    return "document"


def _candidates_from_extraction(
    extraction: IntakeRecallExtraction,
    *,
    locator: str,
    modality: str,
    source_text: str | None,
    parsed_notice: ParsedNotice,
) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    string_fields = {
        "product_name": extraction.product_name,
        "reason": extraction.reason,
        "source": extraction.source,
    }
    for field, extracted in string_fields.items():
        value = extracted.value.strip()
        if not value:
            continue
        if source_text is not None and not _text_contains(source_text, value):
            continue
        candidates.append(
            _Candidate(
                field=field,
                value=value,
                confidence=extracted.confidence,
                locator=(
                    _text_locator(parsed_notice, value)
                    if modality == "text"
                    else locator
                ),
                modality=modality,
                requires_review=extracted.confidence < 80,
            )
        )

    for field, extracted in {
        "affected_lots": extraction.affected_lots,
        "upcs": extraction.upcs,
    }.items():
        values = _unique(extracted.value)
        if source_text is not None:
            values = [
                value for value in values if _text_contains(source_text, value)
            ]
        if not values:
            continue
        candidates.append(
            _Candidate(
                field=field,
                value=values,
                confidence=extracted.confidence,
                locator=(
                    _text_locator(parsed_notice, values[0])
                    if modality == "text"
                    else locator
                ),
                modality=modality,
                requires_review=extracted.confidence < 80,
            )
        )

    if extraction.risk_level.value is not None:
        candidates.append(
            _Candidate(
                field="risk_level",
                value=extraction.risk_level.value,
                confidence=extraction.risk_level.confidence,
                locator=(
                    parsed_notice.text_pages[0].locator
                    if modality == "text" and parsed_notice.text_pages
                    else locator
                ),
                modality=modality,
                requires_review=extraction.risk_level.confidence < 80,
            )
        )
    return candidates


def _best_candidate(
    candidates: list[_Candidate],
    field: str,
) -> _Candidate | None:
    matches = [candidate for candidate in candidates if candidate.field == field]
    return max(matches, key=lambda candidate: candidate.confidence, default=None)


def _candidate_list(candidates: list[_Candidate], field: str) -> list[str]:
    values: list[str] = []
    for candidate in candidates:
        if candidate.field == field and isinstance(candidate.value, list):
            values.extend(candidate.value)
    return _unique(values)


def _all_required_high_confidence(candidates: list[_Candidate]) -> bool:
    product = _best_candidate(candidates, "product_name")
    risk = _best_candidate(candidates, "risk_level")
    reason = _best_candidate(candidates, "reason")
    source = _best_candidate(candidates, "source")
    identifier_candidates = [
        candidate
        for candidate in candidates
        if candidate.field in {"affected_lots", "upcs"} and candidate.value
    ]
    required = [product, risk, reason, source]
    return (
        all(candidate is not None and candidate.confidence >= 80 for candidate in required)
        and any(candidate.confidence >= 80 for candidate in identifier_candidates)
    )


def _canonical_candidate_value(value: str | list[str] | Severity) -> object:
    if isinstance(value, list):
        return tuple(sorted(item.casefold() for item in value))
    if isinstance(value, Severity):
        return value.value
    return value.casefold()


def _mark_image_disagreements(candidates: list[_Candidate]) -> None:
    for field in {
        candidate.field
        for candidate in candidates
        if candidate.modality == "image"
    }:
        image_candidates = [
            candidate
            for candidate in candidates
            if candidate.modality == "image" and candidate.field == field
        ]
        values = {
            _canonical_candidate_value(candidate.value)
            for candidate in image_candidates
        }
        if len(values) > 1:
            for candidate in image_candidates:
                candidate.requires_review = True


def _candidate_evidence(
    candidate: _Candidate,
    *,
    notice_artifact: IntakeArtifact,
    created_at: str,
) -> IntakeFieldEvidence:
    value = (
        candidate.value.value
        if isinstance(candidate.value, Severity)
        else candidate.value
    )
    return IntakeFieldEvidence(
        id=uuid4().hex,
        intake_id=notice_artifact.intake_id,
        field_path=f"criteria.{candidate.field}",
        value=value,
        artifact_id=notice_artifact.id,
        locator=candidate.locator,
        source=OutputSource.qwen,
        confidence=candidate.confidence,
        requires_review=candidate.requires_review,
        created_at=created_at,
    )


def _literal_evidence_for(
    literal: DraftExtraction,
    field: str,
) -> list[IntakeFieldEvidence]:
    path = f"criteria.{field}"
    return [item for item in literal.evidence if item.field_path == path]


async def extract_notice_draft(
    *,
    gateway: QwenGateway,
    parsed_notice: ParsedNotice,
    notice_artifact: IntakeArtifact,
) -> DraftExtraction:
    candidates: list[_Candidate] = []
    fallback = _empty_extraction_payload()

    if parsed_notice.normalized_text:
        request = ModelJSONRequest(
            system=(
                "Extract recall criteria. Return only JSON with product_name, "
                "affected_lots, upcs, risk_level, reason, and source. Each field "
                "must contain value and confidence. Do not invent values."
            ),
            user=f"Recall notice:\n{parsed_notice.normalized_text}",
            fallback=fallback,
        )
        try:
            response = await gateway.complete_json(request)
            extraction = _validated_extraction(response)
        except Exception:
            extraction = None
        if extraction is not None:
            candidates.extend(
                _candidates_from_extraction(
                    extraction,
                    locator=(
                        parsed_notice.text_pages[0].locator
                        if parsed_notice.text_pages
                        else "document"
                    ),
                    modality="text",
                    source_text=parsed_notice.normalized_text,
                    parsed_notice=parsed_notice,
                )
            )

    if not _all_required_high_confidence(candidates):
        for page in parsed_notice.rendered_pages[:3]:
            request = ModelImageJSONRequest(
                system=(
                    "Extract recall criteria from this notice image. Return only "
                    "JSON with product_name, affected_lots, upcs, risk_level, "
                    "reason, and source. Each field must contain value and "
                    "confidence. Do not invent values."
                ),
                user="Read only values visible in this recall notice page.",
                fallback=fallback,
                image_bytes=page.png_bytes,
                media_type=page.media_type,
            )
            try:
                response = await gateway.complete_image_json(request)
                extraction = _validated_extraction(response)
            except Exception:
                extraction = None
            if extraction is not None:
                candidates.extend(
                    _candidates_from_extraction(
                        extraction,
                        locator=page.locator,
                        modality="image",
                        source_text=None,
                        parsed_notice=parsed_notice,
                    )
                )
            if _all_required_high_confidence(candidates):
                break

    _mark_image_disagreements(candidates)
    literal = safe_literal_extraction(
        parsed_notice.normalized_text,
        intake_id=notice_artifact.intake_id,
        artifact_id=notice_artifact.id,
    )
    product_candidate = _best_candidate(candidates, "product_name")
    risk_candidate = _best_candidate(candidates, "risk_level")
    reason_candidate = _best_candidate(candidates, "reason")
    source_candidate = _best_candidate(candidates, "source")
    qwen_lots = _candidate_list(candidates, "affected_lots")
    qwen_upcs = _candidate_list(candidates, "upcs")
    lots = _unique([*qwen_lots, *literal.criteria.affected_lots])
    upcs = _unique([*qwen_upcs, *literal.criteria.upcs])
    criteria = RecallCriteriaDraft(
        product_name=(
            str(product_candidate.value)
            if product_candidate is not None
            else literal.criteria.product_name
        ),
        affected_lots=lots,
        upcs=upcs,
        risk_level=(
            risk_candidate.value
            if risk_candidate is not None
            and isinstance(risk_candidate.value, Severity)
            else literal.criteria.risk_level
        ),
        reason=(
            str(reason_candidate.value)
            if reason_candidate is not None
            else literal.criteria.reason
        ),
        source=(
            str(source_candidate.value)
            if source_candidate is not None
            else literal.criteria.source
        ),
    )

    created_at = _now()
    evidence = [
        _candidate_evidence(
            candidate,
            notice_artifact=notice_artifact,
            created_at=created_at,
        )
        for candidate in candidates
    ]
    if product_candidate is None and literal.criteria.product_name:
        evidence.extend(_literal_evidence_for(literal, "product_name"))
    if set(value.casefold() for value in lots) - set(
        value.casefold() for value in qwen_lots
    ):
        evidence.extend(_literal_evidence_for(literal, "affected_lots"))
    if set(value.casefold() for value in upcs) - set(
        value.casefold() for value in qwen_upcs
    ):
        evidence.extend(_literal_evidence_for(literal, "upcs"))
    if risk_candidate is None and literal.criteria.risk_level is not None:
        evidence.extend(_literal_evidence_for(literal, "risk_level"))
    if reason_candidate is None and literal.criteria.reason:
        evidence.extend(_literal_evidence_for(literal, "reason"))
    if source_candidate is None and literal.criteria.source:
        evidence.extend(_literal_evidence_for(literal, "source"))

    complete = (
        bool(criteria.product_name)
        and bool(criteria.affected_lots or criteria.upcs)
        and criteria.risk_level is not None
        and bool(criteria.reason)
        and bool(criteria.source)
    )
    return DraftExtraction(
        criteria=criteria,
        evidence=tuple(evidence),
        review_required=(
            not complete
            or any(item.requires_review for item in evidence)
        ),
    )


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
