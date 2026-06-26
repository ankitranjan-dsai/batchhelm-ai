from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from batchhelm_api.config import Settings, get_settings
from batchhelm_api.models import (
    APIError,
    CustomerNoticeDraft,
    ExtractedLabel,
    ModelImageJSONRequest,
    ModelJSONRequest,
    ModelJSONResponse,
    ProviderStatus,
    RecallAnalysis,
    RecallIncidentInput,
    ShelfInspectionResult,
    UploadMetadata,
)
from batchhelm_api.qwen import QwenGateway, QwenGatewayError
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.storage import UploadValidationError, save_image_upload
from batchhelm_api.workflow import analyze_recall_incident, build_customer_notice


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class CustomerNoticeRequest(BaseModel):
    affected_items: int | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(
        title="BatchHelm API",
        version="0.1.0",
        description="Recall workflow API for BatchHelm.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(QwenGatewayError)
    async def qwen_error_handler(
        _request: Request, exc: QwenGatewayError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=APIError(code="qwen_gateway_error", message=str(exc)).model_dump(),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=APIError(code="bad_request", message=str(exc)).model_dump(),
        )

    @app.exception_handler(UploadValidationError)
    async def upload_error_handler(
        _request: Request, exc: UploadValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=APIError(code="invalid_upload", message=str(exc)).model_dump(),
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", service="batchhelm-api", version="0.1.0")

    @app.get("/api/incidents/demo", response_model=RecallIncidentInput)
    async def get_demo_incident() -> RecallIncidentInput:
        return build_demo_incident()

    @app.post("/api/incidents/demo/analyze", response_model=RecallAnalysis)
    async def analyze_demo_incident() -> RecallAnalysis:
        return analyze_recall_incident(build_demo_incident())

    @app.get("/api/qwen/status", response_model=ProviderStatus)
    async def qwen_status(gateway: QwenGateway = Depends(get_qwen_gateway)) -> ProviderStatus:
        return gateway.status()

    @app.post("/api/qwen/recall-summary", response_model=ModelJSONResponse)
    async def qwen_recall_summary(
        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> ModelJSONResponse:
        incident = build_demo_incident()
        analysis = analyze_recall_incident(incident)
        return await gateway.complete_json(
            ModelJSONRequest(
                system=(
                    "Return a compact JSON object for a product recall operations "
                    "summary. Include summary, next_action, and confidence."
                ),
                user=(
                    f"Recall: {incident.product} lots {incident.lot_range}. "
                    f"Affected items: {analysis.affected_items}. "
                    f"Open tasks: {analysis.open_tasks}."
                ),
                fallback={
                    "summary": "Spinach lots L2418-L2422 are quarantined across two stores.",
                    "next_action": "Review customer notice and verify quarantined inventory.",
                    "confidence": 96,
                },
            )
        )

    @app.post("/api/notices/customer-draft", response_model=CustomerNoticeDraft)
    async def customer_notice_draft(
        request: CustomerNoticeRequest | None = None,
    ) -> CustomerNoticeDraft:
        incident = build_demo_incident()
        affected_items = request.affected_items if request else None
        if affected_items is None:
            affected_items = analyze_recall_incident(incident).affected_items
        return build_customer_notice(incident, affected_items=affected_items)

    @app.get("/api/inspections/demo", response_model=ShelfInspectionResult)
    async def demo_shelf_inspection(
        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> ShelfInspectionResult:
        upload = UploadMetadata(
            id="demo-shelf-photo",
            original_filename="store-b-cooler-spinach.png",
            stored_filename="demo-shelf-photo.png",
            media_type="image/png",
            size_bytes=204800,
            path="sample-data/store-b-cooler-spinach.png",
        )
        return _inspection_from_model_content(
            upload=upload,
            model_response=await gateway.complete_image_json(
                _inspection_request(
                    image_bytes=b"demo-image",
                    media_type="image/png",
                )
            ),
        )

    @app.post("/api/inspections/shelf-photo", response_model=ShelfInspectionResult)
    async def inspect_shelf_photo(
        file: UploadFile = File(...),
        gateway: QwenGateway = Depends(get_qwen_gateway),
        settings: Settings = Depends(get_request_settings),
    ) -> ShelfInspectionResult:
        content = await file.read()
        media_type = file.content_type or "application/octet-stream"
        upload = save_image_upload(
            upload_dir=settings.upload_dir,
            filename=file.filename or "shelf-photo",
            media_type=media_type,
            content=content,
        )
        model_response = await gateway.complete_image_json(
            _inspection_request(image_bytes=content, media_type=media_type)
        )
        return _inspection_from_model_content(upload=upload, model_response=model_response)

    return app


def get_qwen_gateway(request: Request) -> QwenGateway:
    return QwenGateway(request.app.state.settings)


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings


app = create_app()


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return APIError(code=code, message=message, details=details).model_dump()


def _inspection_request(image_bytes: bytes, media_type: str) -> ModelImageJSONRequest:
    return ModelImageJSONRequest(
        system=(
            "Inspect a shelf or stockroom image for recall evidence. Return only "
            "JSON with product_name, lot_code, upc, best_by, confidence, "
            "recall_match, recommended_action, review_required, and evidence_note."
        ),
        user=(
            "Extract product label fields for the active recall: Spinach 10 oz, "
            "affected lots L2418-L2422, UPC 008500001010."
        ),
        image_bytes=image_bytes,
        media_type=media_type,
        fallback={
            "product_name": "Spinach 10 oz",
            "lot_code": "L2418",
            "upc": "008500001010",
            "best_by": "2026-07-18",
            "confidence": 96,
            "recall_match": True,
            "recommended_action": "Quarantine item and attach photo to evidence packet.",
            "review_required": False,
            "evidence_note": "Label fields match the active spinach recall criteria.",
        },
    )


def _inspection_from_model_content(
    upload: UploadMetadata,
    model_response: ModelJSONResponse,
) -> ShelfInspectionResult:
    content = model_response.content
    extracted = ExtractedLabel(
        product_name=str(content.get("product_name", "")),
        lot_code=str(content.get("lot_code", "")),
        upc=str(content.get("upc", "")),
        best_by=content.get("best_by"),
        confidence=int(content.get("confidence", 0)),
    )
    return ShelfInspectionResult(
        upload=upload,
        extracted=extracted,
        recall_match=bool(content.get("recall_match", False)),
        recommended_action=str(content.get("recommended_action", "Review image manually.")),
        review_required=bool(content.get("review_required", True)),
        evidence_note=str(content.get("evidence_note", "Inspection completed.")),
        provider=model_response.provider,
        used_fallback=model_response.used_fallback,
    )
