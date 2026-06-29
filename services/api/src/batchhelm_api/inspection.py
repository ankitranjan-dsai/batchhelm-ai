"""Shelf / stockroom image inspection shared by the API and the vision agent."""

from __future__ import annotations

from batchhelm_api.models import (
    ExtractedLabel,
    ModelImageJSONRequest,
    ModelJSONResponse,
    RecallIncidentInput,
    ShelfInspectionResult,
    UploadMetadata,
)
from batchhelm_api.qwen import QwenGateway


def demo_upload_metadata() -> UploadMetadata:
    return UploadMetadata(
        id="demo-shelf-photo",
        original_filename="store-b-cooler-spinach.png",
        stored_filename="demo-shelf-photo.png",
        media_type="image/png",
        size_bytes=204800,
        path="sample-data/store-b-cooler-spinach.png",
    )


def inspection_request(
    *,
    image_bytes: bytes,
    media_type: str,
    incident: RecallIncidentInput,
) -> ModelImageJSONRequest:
    criteria = incident.criteria
    lots = ", ".join(criteria.affected_lots)
    upc = criteria.upcs[0] if criteria.upcs else "unknown"
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
        fallback={
            "product_name": criteria.product_name,
            "lot_code": criteria.affected_lots[0] if criteria.affected_lots else "",
            "upc": upc,
            "best_by": "2026-07-18",
            "confidence": 96,
            "recall_match": True,
            "recommended_action": "Quarantine item and attach photo to evidence packet.",
            "review_required": False,
            "evidence_note": "Label fields match the active recall criteria.",
        },
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
    return ShelfInspectionResult(
        upload=upload,
        extracted=extracted,
        recall_match=bool(content.get("recall_match", False)),
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
) -> ShelfInspectionResult:
    response = await gateway.complete_image_json(
        inspection_request(
            image_bytes=image_bytes, media_type=media_type, incident=incident
        )
    )
    return inspection_from_model_content(upload=upload, model_response=response)


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
