"""Shelf / stockroom image inspection shared by the API and the vision agent."""

from __future__ import annotations

from pathlib import Path

from batchhelm_api.models import (
    ExtractedLabel,
    ModelImageJSONRequest,
    ModelJSONResponse,
    RecallIncidentInput,
    ShelfInspectionResult,
    UploadMetadata,
)
from batchhelm_api.qwen import QwenGateway

# services/api/src/batchhelm_api/inspection.py -> repository root is four
# parents up, mirrored inside the API container by copying sample-data/
# alongside services/ (see Dockerfile).
_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
DEMO_SHELF_IMAGE_PATH = _REPOSITORY_ROOT / "sample-data" / "store-b-cooler-spinach.png"


def demo_upload_metadata() -> UploadMetadata:
    return UploadMetadata(
        id="demo-shelf-photo",
        original_filename="store-b-cooler-spinach.png",
        stored_filename="demo-shelf-photo.png",
        media_type="image/png",
        size_bytes=DEMO_SHELF_IMAGE_PATH.stat().st_size,
        path="sample-data/store-b-cooler-spinach.png",
    )


def demo_shelf_image_bytes() -> bytes:
    return DEMO_SHELF_IMAGE_PATH.read_bytes()


def inspection_request(
    *,
    image_bytes: bytes,
    media_type: str,
    incident: RecallIncidentInput,
    allow_seeded_fallback: bool,
) -> ModelImageJSONRequest:
    criteria = incident.criteria
    lots = ", ".join(criteria.affected_lots)
    upc = criteria.upcs[0] if criteria.upcs else "unknown"
    seeded_fallback = {
        "product_name": criteria.product_name,
        "lot_code": criteria.affected_lots[0] if criteria.affected_lots else "",
        "upc": upc,
        "best_by": "2026-07-18",
        "confidence": 96,
        "recall_match": True,
        "recommended_action": (
            "Quarantine item and attach photo to evidence packet."
        ),
        "review_required": False,
        "evidence_note": "Label fields match the active recall criteria.",
    }
    neutral_fallback = {
        "product_name": "",
        "lot_code": "",
        "upc": "",
        "best_by": None,
        "confidence": 0,
        "recall_match": None,
        "recommended_action": "Review the uploaded shelf image manually.",
        "review_required": True,
        "evidence_note": (
            "Qwen vision was unavailable; no image match was inferred."
        ),
    }
    return ModelImageJSONRequest(
        system=(
            "Inspect a shelf or stockroom image for recall evidence. Return only "
            "JSON with product_name, lot_code, upc, best_by, confidence "
            "(integer 0-100), recall_match (boolean), recommended_action, "
            "review_required (boolean), and evidence_note."
        ),
        user=(
            f"Extract product label fields for the active recall: "
            f"{criteria.product_name}, affected lots {lots}, UPC {upc}."
        ),
        image_bytes=image_bytes,
        media_type=media_type,
        fallback=seeded_fallback if allow_seeded_fallback else neutral_fallback,
    )


def inspection_from_model_content(
    *,
    upload: UploadMetadata,
    model_response: ModelJSONResponse,
) -> ShelfInspectionResult:
    content = model_response.content
    extracted = ExtractedLabel(
        product_name=str(content.get("product_name", "")),
        lot_code=str(content.get("lot_code", "")),
        upc=str(content.get("upc", "")),
        best_by=content.get("best_by"),
        confidence=_as_int(content.get("confidence", 0)),
    )
    raw_match = content.get("recall_match")
    recall_match = raw_match if isinstance(raw_match, bool) else None
    return ShelfInspectionResult(
        upload=upload,
        extracted=extracted,
        recall_match=recall_match,
        recommended_action=str(
            content.get("recommended_action", "Review image manually.")
        ),
        review_required=bool(content.get("review_required", True)),
        evidence_note=str(content.get("evidence_note", "Inspection completed.")),
        provider=model_response.provider,
        used_fallback=model_response.used_fallback,
    )


async def inspect_image(
    *,
    gateway: QwenGateway,
    upload: UploadMetadata,
    image_bytes: bytes,
    media_type: str,
    incident: RecallIncidentInput,
    allow_seeded_fallback: bool,
) -> ShelfInspectionResult:
    response = await gateway.complete_image_json(
        inspection_request(
            image_bytes=image_bytes,
            media_type=media_type,
            incident=incident,
            allow_seeded_fallback=allow_seeded_fallback,
        )
    )
    return inspection_from_model_content(upload=upload, model_response=response)


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
