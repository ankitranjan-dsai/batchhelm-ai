from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from batchhelm_api.config import Settings, get_settings
from batchhelm_api.models import (
    APIError,
    CustomerNoticeDraft,
    ModelJSONRequest,
    ModelJSONResponse,
    ProviderStatus,
    RecallAnalysis,
    RecallIncidentInput,
)
from batchhelm_api.qwen import QwenGateway, QwenGatewayError
from batchhelm_api.sample_data import build_demo_incident
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

    return app


def get_qwen_gateway(request: Request) -> QwenGateway:
    return QwenGateway(request.app.state.settings)


app = create_app()


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return APIError(code=code, message=message, details=details).model_dump()
