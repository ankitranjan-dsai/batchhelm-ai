from __future__ import annotations

import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ValidationError

from batchhelm_api import inspection
from batchhelm_api.agents import Orchestrator
from batchhelm_api.config import Settings, get_settings
from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.intake_models import (
    IntakeAccepted,
    IntakeConfirmRequest,
    IntakeCreateRequest,
    IntakeDraftUpdate,
    IntakeRunAccepted,
    IntakeRunRequest,
    IntakeStatus,
    IntakeView,
    ResolvedRunInput,
)
from batchhelm_api.intake_repository import (
    IntakeIdempotencyConflict,
    IntakeNotFound,
    IntakeRepository,
    IntakeStateConflict,
    IntakeStoreUnavailable,
    IntakeVersionConflict,
    SQLiteIntakeRepository,
    UnavailableIntakeRepository,
)
from batchhelm_api.intake_service import (
    CreateIntakeCommand,
    IntakeProcessingFailed,
    IntakeService,
    IntakeUpload,
    IntakeValidationFailed,
)
from batchhelm_api.intake_storage import (
    IntakePacketTooLarge,
    IntakeUploadInvalid,
)
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
    QwenVerificationReceipt,
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
from batchhelm_api.qwen_verification_repository import (
    QwenVerificationRepository,
    QwenVerificationStoreUnavailable,
    SQLiteQwenVerificationRepository,
)
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
    intake_repository: IntakeRepository | None = None,
    qwen_gateway_factory: Callable[[], QwenGateway] | None = None,
    qwen_verification_repository: QwenVerificationRepository | None = None,
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

    intake_store = (
        intake_repository
        or SQLiteIntakeRepository(resolved_settings.intake_database_path)
    )
    try:
        intake_store.initialize()
    except IntakeStoreUnavailable as exc:
        intake_store = UnavailableIntakeRepository(exc)

    verification_store = (
        qwen_verification_repository
        or SQLiteQwenVerificationRepository(
            resolved_settings.qwen_proof_database_path
        )
    )
    verification_store.initialize()

    gateway_factory = qwen_gateway_factory or (
        lambda: QwenGateway(resolved_settings)
    )

    intake_service = IntakeService(
        repository=intake_store,
        artifact_root=resolved_settings.upload_dir,
        gateway_factory=gateway_factory,
    )

    def build_orchestrator() -> Orchestrator:
        return Orchestrator(
            gateway=gateway_factory(),
            memory=memory,
            settings=resolved_settings,
        )

    orchestration_service = OrchestrationService(
        repository=orchestration_store,
        orchestrator_factory=build_orchestrator,
    )

    def resolve_run_input(incident_id: str) -> ResolvedRunInput | None:
        demo_incident = build_demo_incident()
        if incident_id == demo_incident.id:
            return ResolvedRunInput(incident=demo_incident)
        try:
            return intake_service.resolve_run_input(incident_id)
        except (IntakeStoreUnavailable, IntakeProcessingFailed):
            return None

    @asynccontextmanager
    async def app_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        with suppress(IntakeStoreUnavailable):
            await intake_service.recover()
        await orchestration_service.recover(resolve_run_input)
        yield

    telemetry = Telemetry()

    app = FastAPI(
        title="BatchHelm API",
        version="0.2.0",
        description="Autonomous recall command center API for BatchHelm.",
        lifespan=app_lifespan,
    )
    # Hide server version in responses
    app.state.settings = resolved_settings
    app.state.review_service = review_service
    app.state.memory = memory
    app.state.orchestration_service = orchestration_service
    app.state.intake_service = intake_service
    app.state.telemetry = telemetry
    app.state.qwen_gateway_factory = gateway_factory
    app.state.qwen_verification_repository = verification_store

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response

    @app.middleware("http")
    async def hide_server_header_middleware(request: Request, call_next):
        response = await call_next(request)
        # Remove Server header to avoid version disclosure
        if "server" in response.headers:
            del response.headers["server"]
        return response

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
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID", "X-BatchHelm-Proof-Token", "Authorization", "X-BatchHelm-Demo-Key"],
    )

    def require_demo_auth(request: Request) -> None:
        if not resolved_settings.demo_auth_enabled:
            return
        supplied = request.headers.get("X-BatchHelm-Demo-Key", "")
        if not secrets.compare_digest(supplied, resolved_settings.demo_api_key):
            raise HTTPException(
                status_code=401,
                detail="Demo API key is required. Set X-BatchHelm-Demo-Key header.",
            )

    @app.middleware("http")
    async def demo_auth_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1/"):
            require_demo_auth(request)
        return await call_next(request)

    @app.exception_handler(QwenGatewayError)
    async def qwen_error_handler(
        _request: Request, exc: QwenGatewayError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content=APIError(code="qwen_gateway_error", message=str(exc)).model_dump(),
        )

    @app.exception_handler(QwenVerificationStoreUnavailable)
    async def qwen_verification_store_handler(
        _request: Request,
        _exc: QwenVerificationStoreUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=APIError(
                code="qwen_proof_store_unavailable",
                message="Qwen verification proof is temporarily unavailable.",
            ).model_dump(),
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

    @app.exception_handler(IntakeNotFound)
    async def intake_not_found_handler(
        _request: Request,
        _exc: IntakeNotFound,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content=APIError(
                code="intake_not_found",
                message="Incident intake was not found.",
            ).model_dump(),
        )

    @app.exception_handler(IntakeIdempotencyConflict)
    async def intake_idempotency_handler(
        _request: Request,
        _exc: IntakeIdempotencyConflict,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=APIError(
                code="idempotency_conflict",
                message="Request ID was already used for another intake operation.",
            ).model_dump(),
        )

    @app.exception_handler(IntakeStateConflict)
    async def intake_state_handler(
        _request: Request,
        _exc: IntakeStateConflict,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=APIError(
                code="intake_state_conflict",
                message="Incident intake is not in the required state.",
            ).model_dump(),
        )

    @app.exception_handler(IntakeVersionConflict)
    async def intake_version_handler(
        _request: Request,
        _exc: IntakeVersionConflict,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content=APIError(
                code="intake_version_conflict",
                message="Incident intake was updated by another reviewer.",
            ).model_dump(),
        )

    @app.exception_handler(IntakePacketTooLarge)
    async def intake_packet_too_large_handler(
        _request: Request,
        _exc: IntakePacketTooLarge,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=413,
            content=APIError(
                code="upload_too_large",
                message="Incident intake files exceed the upload limit.",
            ).model_dump(),
        )

    @app.exception_handler(IntakeUploadInvalid)
    async def intake_upload_handler(
        _request: Request,
        _exc: IntakeUploadInvalid,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=APIError(
                code="invalid_upload",
                message="Incident intake files could not be accepted.",
            ).model_dump(),
        )

    @app.exception_handler(IntakeValidationFailed)
    async def intake_validation_handler(
        _request: Request,
        exc: IntakeValidationFailed,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=APIError(
                code="intake_validation_failed",
                message=str(exc),
            ).model_dump(),
        )

    @app.exception_handler(IntakeStoreUnavailable)
    async def intake_store_handler(
        _request: Request,
        _exc: IntakeStoreUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content=APIError(
                code="intake_store_unavailable",
                message="Incident intake is temporarily unavailable.",
            ).model_dump(),
        )

    @app.exception_handler(IntakeProcessingFailed)
    async def intake_processing_handler(
        _request: Request,
        _exc: IntakeProcessingFailed,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=APIError(
                code="intake_processing_failed",
                message="Incident intake could not be processed.",
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

    @app.get("/api/v1/health", response_model=HealthResponse)
    async def health_v1() -> HealthResponse:
        return HealthResponse(status="ok", service="batchhelm-api", version="0.2.0")

    @app.post(
        "/api/v1/intakes",
        response_model=IntakeAccepted,
        status_code=202,
    )
    async def create_intake(

        request_id: Annotated[str, Form()],
        notice: Annotated[UploadFile, File()],
        inventory: Annotated[UploadFile, File()],
        shelf_photo: Annotated[UploadFile | None, File()] = None,
        service: IntakeService = Depends(get_intake_service),
    ) -> IntakeAccepted:
        try:
            parsed_request = IntakeCreateRequest(request_id=request_id)
        except ValidationError as exc:
            raise IntakeValidationFailed(
                "Request ID must be a valid UUID."
            ) from exc
        telemetry.increment("intake_packets")
        return await service.create(
            CreateIntakeCommand(
                request_id=str(parsed_request.request_id),
                notice=IntakeUpload(
                    filename=notice.filename or "recall-notice",
                    media_type=notice.content_type or "application/octet-stream",
                    stream=notice.file,
                ),
                inventory=IntakeUpload(
                    filename=inventory.filename or "inventory.csv",
                    media_type=(
                        inventory.content_type or "application/octet-stream"
                    ),
                    stream=inventory.file,
                ),
                shelf_photo=(
                    IntakeUpload(
                        filename=shelf_photo.filename or "shelf-photo",
                        media_type=(
                            shelf_photo.content_type
                            or "application/octet-stream"
                        ),
                        stream=shelf_photo.file,
                    )
                    if shelf_photo is not None
                    else None
                ),
            )
        )

    @app.get("/api/v1/intakes/{intake_id}", response_model=IntakeView)
    async def get_intake(

        intake_id: str,
        service: IntakeService = Depends(get_intake_service),
    ) -> IntakeView:
        return service.get(intake_id)

    @app.patch("/api/v1/intakes/{intake_id}/draft", response_model=IntakeView)
    async def update_intake_draft(

        intake_id: str,
        request: IntakeDraftUpdate,
        service: IntakeService = Depends(get_intake_service),
    ) -> IntakeView:
        return service.update_draft(intake_id, request)

    @app.post("/api/v1/intakes/{intake_id}/confirm", response_model=IntakeView)
    async def confirm_intake(

        intake_id: str,
        request: IntakeConfirmRequest,
        service: IntakeService = Depends(get_intake_service),
    ) -> IntakeView:
        return service.confirm(intake_id, request)

    @app.post(
        "/api/v1/intakes/{intake_id}/runs",
        response_model=IntakeRunAccepted,
        status_code=202,
    )
    async def start_intake_run(

        intake_id: str,
        request: IntakeRunRequest,
        intake_service: IntakeService = Depends(get_intake_service),
        orchestration_service: OrchestrationService = Depends(
            get_orchestration_service
        ),
    ) -> IntakeRunAccepted:
        view = intake_service.get(intake_id)
        if view.status == IntakeStatus.run_started and view.run_id is not None:
            run_view = orchestration_service.get(view.run_id)
            accepted = OrchestrationRunAccepted(
                run_id=run_view.run_id,
                incident_id=run_view.incident_id,
                status=run_view.status,
                events_url=(
                    f"/api/v1/orchestration/runs/{run_view.run_id}/events"
                ),
                result_url=f"/api/v1/orchestration/runs/{run_view.run_id}",
            )
            return IntakeRunAccepted(intake=view, run=accepted)
        if view.status != IntakeStatus.ready or view.incident_id is None:
            raise IntakeStateConflict(
                "Intake must be confirmed before a run can start."
            )
        run_input = intake_service.resolve_run_input(view.incident_id)
        if run_input is None:
            raise IntakeStateConflict(
                "Confirmed incident input is unavailable."
            )
        telemetry.increment("orchestration_runs")
        accepted = await orchestration_service.start(
            run_input,
            request_id=str(request.request_id),
        )
        linked = intake_service.link_run(
            intake_id,
            request_id=str(request.request_id),
            run_id=accepted.run_id,
        )
        return IntakeRunAccepted(intake=linked, run=accepted)

    @app.get("/api/v1/incidents/demo", response_model=RecallIncidentInput, include_in_schema=False)
    async def get_demo_incident(
) -> RecallIncidentInput:
        return build_demo_incident()

    @app.post("/api/v1/incidents/demo/analyze", response_model=RecallAnalysis, include_in_schema=False)
    async def analyze_demo_incident(
) -> RecallAnalysis:
        return analyze_recall_incident(build_demo_incident())

    @app.get("/api/v1/agents", response_model=list[AgentDescriptor], include_in_schema=False)
    async def list_agents(

        orchestrator: Orchestrator = Depends(get_orchestrator),
    ) -> list[AgentDescriptor]:
        return [AgentDescriptor(**descriptor) for descriptor in orchestrator.descriptors()]

    @app.post(
        "/api/v1/incidents/demo/runs",
        response_model=OrchestrationRunAccepted,
        status_code=202,
        include_in_schema=False,
    )
    async def start_demo_run(

        request: OrchestrationStartRequest,
        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationRunAccepted:
        telemetry.increment("orchestration_runs")
        return await service.start(
            ResolvedRunInput(incident=build_demo_incident()),
            request_id=str(request.request_id),
        )

    @app.get(
        "/api/v1/orchestration/runs/latest",
        response_model=OrchestrationRunView,
        include_in_schema=False,
    )
    async def latest_orchestration_run(

        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationRunView | JSONResponse:
        view = service.latest()
        if view is None:
            return JSONResponse(
                status_code=404,
                content=APIError(
                    code="orchestration_run_not_found",
                    message="No completed orchestration run is available yet.",
                ).model_dump(),
            )
        return view

    @app.get(
        "/api/v1/orchestration/runs/{run_id}",
        response_model=OrchestrationRunView,
        include_in_schema=False,
    )
    async def get_orchestration_run(

        run_id: str,
        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationRunView:
        return service.get(run_id)

    @app.get("/api/v1/orchestration/runs/{run_id}/events", include_in_schema=False)
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

    @app.post("/api/v1/incidents/demo/run", response_model=OrchestrationResult, include_in_schema=False)
    async def run_demo_orchestration(

        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> OrchestrationResult:
        telemetry.increment("orchestration_runs")
        accepted = await service.start(
            ResolvedRunInput(incident=build_demo_incident()),
            request_id=uuid4().hex,
        )
        return await service.wait_for_result(accepted.run_id)

    @app.get("/api/v1/incidents/demo/run/stream", deprecated=True, include_in_schema=False)
    async def stream_demo_orchestration(

        service: OrchestrationService = Depends(get_orchestration_service),
    ) -> StreamingResponse:
        telemetry.increment("orchestration_streams")
        accepted = await service.start(
            ResolvedRunInput(incident=build_demo_incident()),
            request_id=uuid4().hex,
        )
        return StreamingResponse(
            service.stream(accepted.run_id, after=0),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/v1/memory", response_model=list[MemoryRecord], include_in_schema=False)
    async def list_memory(

        memory_repo: MemoryRepository = Depends(get_memory),
    ) -> list[MemoryRecord]:
        return memory_repo.list_records()

    @app.post("/api/v1/briefing/demo", response_model=ManagementBriefing, include_in_schema=False)
    async def demo_briefing(

        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> ManagementBriefing:
        incident = build_demo_incident()
        analysis = analyze_recall_incident(incident)
        outcome = await generate_briefing(gateway, incident, analysis)
        return outcome.value

    @app.get("/api/v1/telemetry", include_in_schema=False)
    async def telemetry_snapshot(
) -> dict[str, Any]:
        return {"counters": telemetry.snapshot()}

    @app.get("/api/v1/qwen/status", response_model=ProviderStatus, include_in_schema=False)
    async def qwen_status(
gateway: QwenGateway = Depends(get_qwen_gateway)) -> ProviderStatus:
        return gateway.status()

    @app.post("/api/v1/qwen/verify", response_model=QwenVerificationReceipt, include_in_schema=False)
    async def verify_qwen(

        request: Request,
        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> QwenVerificationReceipt | JSONResponse:
        expected_token = resolved_settings.qwen_proof_token.strip()
        if not expected_token:
            return JSONResponse(
                status_code=503,
                content=APIError(
                    code="qwen_proof_disabled",
                    message="Live Qwen verification is not enabled.",
                ).model_dump(),
            )

        supplied_token = request.headers.get("X-BatchHelm-Proof-Token", "")
        if not secrets.compare_digest(supplied_token, expected_token):
            return JSONResponse(
                status_code=403,
                content=APIError(
                    code="qwen_proof_forbidden",
                    message="The Qwen verification token is invalid.",
                ).model_dump(),
            )

        receipt = await gateway.verify_live()
        verification_store.save(receipt)
        telemetry.increment("qwen_verifications")
        return receipt

    @app.get("/api/v1/qwen/proof", response_model=QwenVerificationReceipt, include_in_schema=False)
    async def qwen_proof(
) -> QwenVerificationReceipt | JSONResponse:
        receipt = verification_store.latest()
        if receipt is None:
            return JSONResponse(
                status_code=404,
                content=APIError(
                    code="qwen_proof_not_found",
                    message="No successful live Qwen verification has been recorded.",
                ).model_dump(),
            )
        return receipt

    @app.post("/api/v1/qwen/recall-summary", response_model=ModelJSONResponse, include_in_schema=False)
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

    @app.post("/api/v1/notices/customer-draft", response_model=CustomerNoticeDraft, include_in_schema=False)
    async def customer_notice_draft(

        request: CustomerNoticeRequest | None = None,
    ) -> CustomerNoticeDraft:
        incident = build_demo_incident()
        affected_items = request.affected_items if request else None
        if affected_items is None:
            affected_items = analyze_recall_incident(incident).affected_items
        return build_customer_notice(incident, affected_items=affected_items)

    @app.get("/api/v1/evidence/demo-packet", response_model=EvidencePacket, include_in_schema=False)
    async def demo_evidence_packet(
) -> EvidencePacket:
        return _build_demo_evidence_packet()

    @app.get(
        "/api/v1/evidence/demo-packet.md",
        response_class=PlainTextResponse,
        include_in_schema=False,
    )
    async def download_demo_evidence_packet(
) -> PlainTextResponse:
        packet = _build_demo_evidence_packet()
        return PlainTextResponse(
            packet.markdown,
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{packet.filename}"',
            },
        )

    @app.get("/api/v1/evidence/demo-review", response_model=EvidenceReviewState, include_in_schema=False)
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
        "/api/v1/evidence/demo-review/decision",
        response_model=EvidenceReviewState,
        include_in_schema=False,
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

    @app.get("/api/v1/inspections/demo", response_model=ShelfInspectionResult, include_in_schema=False)
    async def demo_shelf_inspection(

        gateway: QwenGateway = Depends(get_qwen_gateway),
    ) -> ShelfInspectionResult:
        return await inspection.inspect_image(
            gateway=gateway,
            upload=inspection.demo_upload_metadata(),
            image_bytes=inspection.demo_shelf_image_bytes(),
            media_type="image/png",
            incident=build_demo_incident(),
            allow_seeded_fallback=True,
        )

    @app.post("/api/v1/inspections/shelf-photo", response_model=ShelfInspectionResult, include_in_schema=False)
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
    return request.app.state.qwen_gateway_factory()


def get_request_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_review_service(request: Request) -> ReviewService:
    return request.app.state.review_service


def get_memory(request: Request) -> MemoryRepository:
    return request.app.state.memory


def get_orchestrator(request: Request) -> Orchestrator:
    return Orchestrator(
        gateway=request.app.state.qwen_gateway_factory(),
        memory=request.app.state.memory,
        settings=request.app.state.settings,
    )


def get_orchestration_service(request: Request) -> OrchestrationService:
    return request.app.state.orchestration_service


def get_intake_service(request: Request) -> IntakeService:
    return request.app.state.intake_service


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
