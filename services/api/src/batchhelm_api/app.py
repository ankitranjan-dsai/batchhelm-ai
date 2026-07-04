from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from batchhelm_api import inspection
from batchhelm_api.agents import Orchestrator
from batchhelm_api.config import Settings, get_settings
from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.memory_repository import (
    MemoryRepository,
    MemoryStoreUnavailable,
    SQLiteMemoryRepository,
)
from batchhelm_api.models import (
    AgentDescriptor,
    APIError,
    CustomerNoticeDraft,
    EvidencePacket,
    EvidenceReviewState,
    ManagementBriefing,
    MemoryRecord,
    ModelJSONRequest,
    ModelJSONResponse,
    OrchestrationResult,
    OrchestrationRunAccepted,
    OrchestrationRunView,
    OrchestrationStartRequest,
    ProviderStatus,
    RecallAnalysis,
    RecallIncidentInput,
    ReviewDecisionRequest,
    ShelfInspectionResult,
)
from batchhelm_api.orchestration_repository import (
    OrchestrationIdempotencyConflict,
    OrchestrationRepository,
    OrchestrationRunNotFound,
    OrchestrationStoreUnavailable,
    SQLiteOrchestrationRepository,
    UnavailableOrchestrationRepository,
)
from batchhelm_api.orchestration_service import (
    OrchestrationExecutionFailed,
    OrchestrationService,
)
from batchhelm_api.observability import (
    ObservabilityMiddleware,
    Telemetry,
    configure_logging,
)
from batchhelm_api.qwen import QwenGateway, QwenGatewayError
from batchhelm_api.qwen_tasks import generate_briefing
from batchhelm_api.review_repository import (
    ReviewIdempotencyConflict,
    ReviewRepository,
    ReviewStoreUnavailable,
    SQLiteReviewRepository,
    UnavailableReviewRepository,
)
from batchhelm_api.review_service import ReviewService
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.storage import UploadValidationError, save_image_upload
from batchhelm_api.workflow import analyze_recall_incident, build_customer_notice


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class CustomerNoticeRequest(BaseModel):
    affected_items: int | None = None


def create_app(
    settings: Settings | None = None,
    review_repository: ReviewRepository | None = None,
    memory_repository: MemoryRepository | None = None,
    orchestration_repository: OrchestrationRepository | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    repository = review_repository or SQLiteReviewRepository(
        resolved_settings.database_path
    )
    try:
        repository.initialize()
    except ReviewStoreUnavailable as exc:
        repository = UnavailableReviewRepository(exc)
    review_service = ReviewService(repository)

    memory = memory_repository or SQLiteMemoryRepository(resolved_settings.memory_path)
    try:
        memory.initialize()
    except MemoryStoreUnavailable:
        from batchhelm_api.memory_repository import InMemoryMemoryRepository

        memory = InMemoryMemoryRepository()

    orchestration_store = (
        orchestration_repository
        or SQLiteOrchestrationRepository(
            resolved_settings.orchestration_database_path
        )
    )
    try:
        orchestration_store.initialize()
    except OrchestrationStoreUnavailable as exc:
        orchestration_store = UnavailableOrchestrationRepository(exc)

    def build_orchestrator() -> Orchestrator:
        return Orchestrator(
            gateway=QwenGateway(resolved_settings),
            memory=memory,
            settings=resolved_settings,
        )

    orchestration_service = OrchestrationService(
        repository=orchestration_store,
        orchestrator_factory=build_orchestrator,
    )

    @asynccontextmanager
    async def app_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await orchestration_service.recover(build_demo_incident)
        yield

    telemetry = Telemetry()

    app = FastAPI(
        title="BatchHelm API",
        version="0.2.0",
        description="Autonomous recall command center API for BatchHelm.",
        lifespan=app_lifespan,
    )
    app.state.settings = resolved_settings
    app.state.review_service = review_service
    app.state.memory = memory
    app.state.orchestration_service = orchestration_service
    app.state.telemetry = telemetry

    # Inner middleware first; CORS added last so it stays outermost and always
    # decorates responses (including rate-limit 429s) with CORS headers.
    app.add_middleware(
        ObservabilityMiddleware,
        rate_limit_per_minute=resolved_settings.rate_limit_per_minute,
        telemetry=telemetry,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
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

    @app.exception_handler(ReviewIdempotencyConflict)
    async def review_idempotency_handler(
        _request: Request,
        _exc: ReviewIdempotencyConflict,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=APIError(
                code="idempotency_conflict",
                message="Request ID was already used for another review decision.",
            ).model_dump(),
        )

    @app.exception_handler(ReviewStoreUnavailable)
    async def review_store_handler(
        _request: Request,
        _exc: ReviewStoreUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=APIError(
                code="review_store_unavailable",
                message="Review history is temporarily unavailable.",
            ).model_dump(),
        )

    @app.exception_handler(MemoryStoreUnavailable)
    async def memory_store_handler(
        _request: Request,
        _exc: MemoryStoreUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=APIError(
                code="memory_store_unavailable",
                message="Memory is temporarily unavailable.",
            ).model_dump(),
        )

    @app.exception_handler(OrchestrationRunNotFound)
    async def orchestration_not_found_handler(
        _request: Request,
        _exc: OrchestrationRunNotFound,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=APIError(
                code="run_not_found",
                message="Orchestration run was not found.",
            ).model_dump(),
        )

    @app.exception_handler(OrchestrationIdempotencyConflict)
    async def orchestration_idempotency_handler(
        _request: Request,
        _exc: OrchestrationIdempotencyConflict,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=APIError(
                code="run_idempotency_conflict",
                message="Request ID was already used for another run.",
            ).model_dump(),
        )

    @app.exception_handler(OrchestrationStoreUnavailable)
    async def orchestration_store_handler(
        _request: Request,
        _exc: OrchestrationStoreUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=APIError(
                code="orchestration_store_unavailable",
                message="Orchestration history is temporarily unavailable.",
            ).model_dump(),
        )

    @app.exception_handler(OrchestrationExecutionFailed)
    async def orchestration_execution_handler(
        _request: Request,
        _exc: OrchestrationExecutionFailed,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=APIError(
                code="orchestration_failed",
                message="The orchestration run could not be completed.",
            ).model_dump(),
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
        return HealthResponse(status="ok", service="batchhelm-api", version="0.2.0")

    @app.get("/api/incidents/demo", response_model=RecallIncidentInput)
    async def get_demo_incident() -> RecallIncidentInput:
        return build_demo_incident()

    @app.post("/api/incidents/demo/analyze", response_model=RecallAnalysis)
    async def analyze_demo_incident() -> RecallAnalysis:
        return analyze_recall_incident(build_demo_incident())

    @app.get("/api/agents", response_model=list[AgentDescriptor])
    async def list_agents(
        orchestrator: Orchestrator = Depends(get_orchestrator),
    ) -> list[AgentDescriptor]:
        return [AgentDescriptor(**descriptor) for descriptor in orchestrator.descriptors()]

    @app.post(
        "/api/incidents/demo/runs",
        response_model=OrchestrationRunAccepted,
        status_code=202,
    )
    async def start_demo_run(
        request: OrchestrationStartRequest,
        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationRunAccepted:
        telemetry.increment("orchestration_runs")
        return await service.start(
            build_demo_incident(),
            request_id=str(request.request_id),
        )

    @app.get(
        "/api/orchestration/runs/{run_id}",
        response_model=OrchestrationRunView,
    )
    async def get_orchestration_run(
        run_id: str,
        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationRunView:
        return service.get(run_id)

    @app.get("/api/orchestration/runs/{run_id}/events")
    async def stream_orchestration_run(
        run_id: str,
        request: Request,
        after: int | None = None,
        service: OrchestrationService = Depends(get_orchestration_service),
    ):
        cursor = after
        if cursor is None:
            raw_cursor = request.headers.get("last-event-id", "0")
            try:
                cursor = int(raw_cursor)
            except ValueError:
                return _invalid_event_cursor()
        if cursor < 0:
            return _invalid_event_cursor()
        service.get(run_id)
        return StreamingResponse(
            service.stream(run_id, after=cursor),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/api/incidents/demo/run", response_model=OrchestrationResult)
    async def run_demo_orchestration(
        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationResult:
        telemetry.increment("orchestration_runs")
        accepted = await service.start(
            build_demo_incident(),
            request_id=uuid4().hex,
        )
        return await service.wait_for_result(accepted.run_id)

    @app.get("/api/incidents/demo/run/stream", deprecated=True)
    async def stream_demo_orchestration(
        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> StreamingResponse:
        telemetry.increment("orchestration_streams")
        accepted = await service.start(
            build_demo_incident(),
            request_id=uuid4().hex,
        )
        return StreamingResponse(
            service.stream(accepted.run_id, after=0),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/memory", response_model=list[MemoryRecord])
    async def list_memory(
        memory_repo: MemoryRepository = Depends(get_memory),
    ) -> list[MemoryRecord]:
        return memory_repo.list_records()

    @app.post("/api/briefing/demo", response_model=ManagementBriefing)
    async def demo_briefing(
        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> ManagementBriefing:
        incident = build_demo_incident()
        analysis = analyze_recall_incident(incident)
        outcome = await generate_briefing(gateway, incident, analysis)
        return outcome.value

    @app.get("/api/telemetry")
    async def telemetry_snapshot() -> dict[str, Any]:
        return {"counters": telemetry.snapshot()}

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

    @app.get("/api/evidence/demo-packet", response_model=EvidencePacket)
    async def demo_evidence_packet() -> EvidencePacket:
        return _build_demo_evidence_packet()

    @app.get(
        "/api/evidence/demo-packet.md",
        response_class=PlainTextResponse,
    )
    async def download_demo_evidence_packet() -> PlainTextResponse:
        packet = _build_demo_evidence_packet()
        return PlainTextResponse(
            packet.markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{packet.filename}"',
            },
        )

    @app.get("/api/evidence/demo-review", response_model=EvidenceReviewState)
    def demo_evidence_review(
        service: ReviewService = Depends(get_review_service),
    ) -> EvidenceReviewState:
        incident, analysis, packet = _build_demo_packet_context()
        return service.get_state(
            incident=incident,
            analysis=analysis,
            packet=packet,
        )

    @app.post(
        "/api/evidence/demo-review/decision",
        response_model=EvidenceReviewState,
    )
    def demo_evidence_review_decision(
        request: ReviewDecisionRequest,
        service: ReviewService = Depends(get_review_service),
    ) -> EvidenceReviewState:
        incident, analysis, packet = _build_demo_packet_context()
        return service.record_decision(
            incident=incident,
            analysis=analysis,
            packet=packet,
            request=request,
        )

    @app.get("/api/inspections/demo", response_model=ShelfInspectionResult)
    async def demo_shelf_inspection(
        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> ShelfInspectionResult:
        return await inspection.inspect_image(
            gateway=gateway,
            upload=inspection.demo_upload_metadata(),
            image_bytes=b"demo-image",
            media_type="image/png",
            incident=build_demo_incident(),
            allow_seeded_fallback=True,
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
        return await inspection.inspect_image(
            gateway=gateway,
            upload=upload,
            image_bytes=content,
            media_type=media_type,
            incident=build_demo_incident(),
            allow_seeded_fallback=False,
        )

    return app


def get_qwen_gateway(request: Request) -> QwenGateway:
    return QwenGateway(request.app.state.settings)


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


def get_memory(request: Request) -> MemoryRepository:
    return request.app.state.memory


def get_orchestrator(request: Request) -> Orchestrator:
    return Orchestrator(
        gateway=QwenGateway(request.app.state.settings),
        memory=request.app.state.memory,
        settings=request.app.state.settings,
    )


def get_orchestration_service(request: Request) -> OrchestrationService:
    return request.app.state.orchestration_service


app = create_app()


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return APIError(code=code, message=message, details=details).model_dump()


def _invalid_event_cursor() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=APIError(
            code="invalid_event_cursor",
            message="Event cursor must be zero or greater.",
        ).model_dump(),
    )


def _build_demo_evidence_packet() -> EvidencePacket:
    return _build_demo_packet_context()[2]


def _build_demo_packet_context() -> tuple[
    RecallIncidentInput,
    RecallAnalysis,
    EvidencePacket,
]:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)
    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
    )
    return incident, analysis, packet
