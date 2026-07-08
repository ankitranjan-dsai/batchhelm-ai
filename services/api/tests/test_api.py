import json

import httpx
from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.config import Settings
from batchhelm_api.memory_repository import InMemoryMemoryRepository
from batchhelm_api.qwen import QwenGateway
from batchhelm_api.qwen_verification_repository import (
    InMemoryQwenVerificationRepository,
    QwenVerificationStoreUnavailable)


def make_client() -> TestClient:
    settings = Settings(
        QWEN_API_KEY="",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug")
    return TestClient(
        create_app(settings=settings, memory_repository=InMemoryMemoryRepository())
    )


def make_qwen_proof_client(
    *,
    proof_token: str = "proof-token") -> TestClient:
    settings = Settings(
        QWEN_API_KEY="test-key",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen3.7-plus",
        QWEN_VISION_MODEL="qwen3-vl-plus",
        QWEN_PROOF_TOKEN=proof_token,
        APP_ENV="test",
        LOG_LEVEL="debug")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-api-proof",
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"status": "verified", "service": "batchhelm"}
                            )
                        }
                    }
                ]})

    gateway = QwenGateway(
        settings,
        client_factory=lambda: httpx.AsyncClient(
                        base_url="https://example.com",
                        transport=httpx.MockTransport(handler)))
    return TestClient(
        create_app(
            settings=settings,
            memory_repository=InMemoryMemoryRepository(),
            qwen_gateway_factory=lambda: gateway,
            qwen_verification_repository=InMemoryQwenVerificationRepository())
    )


def test_health_endpoint() -> None:
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "batchhelm-api",
        "version": "0.2.0"}


def test_demo_incident_endpoint_returns_recall_input() -> None:
    response = make_client().get("/api/v1/incidents/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "recall-spinach-2026-06"
    assert payload["criteria"]["affected_lots"] == [
        "L2418",
        "L2419",
        "L2420",
        "L2421",
        "L2422",
    ]


def test_demo_analysis_endpoint_returns_workflow_output() -> None:
    response = make_client().post("/api/v1/incidents/demo/analyze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["affected_items"] == 23
    assert payload["evidence_progress"] == 64
    assert len(payload["inventory"]) == 6
    assert payload["customer_notice"]["requires_review"] is True


def test_qwen_status_reports_demo_fallback_when_key_missing() -> None:
    response = make_client().get("/api/v1/qwen/status")

    assert response.status_code == 200
    assert response.json()["mode"] == "demo-fallback"
    assert response.json()["configured"] is False


def test_qwen_summary_uses_fallback_without_key() -> None:
    response = make_client().post("/api/v1/qwen/recall-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["used_fallback"] is True
    assert "Spinach" in payload["content"]["summary"]


def test_qwen_proof_returns_not_found_before_first_verification() -> None:
    response = make_qwen_proof_client().get("/api/v1/qwen/proof")

    assert response.status_code == 404
    assert response.json()["code"] == "qwen_proof_not_found"


def test_qwen_verify_is_disabled_without_a_proof_token() -> None:
    response = make_qwen_proof_client(proof_token="").post(
        "/api/v1/qwen/verify",
        headers={"X-BatchHelm-Proof-Token": "proof-token"})

    assert response.status_code == 503
    assert response.json()["code"] == "qwen_proof_disabled"


def test_qwen_verify_rejects_the_wrong_proof_token() -> None:
    response = make_qwen_proof_client().post(
        "/api/v1/qwen/verify",
        headers={"X-BatchHelm-Proof-Token": "wrong-token"})

    assert response.status_code == 403
    assert response.json()["code"] == "qwen_proof_forbidden"


def test_qwen_verify_persists_a_public_redacted_receipt() -> None:
    client = make_qwen_proof_client()

    verified = client.post(
        "/api/v1/qwen/verify",
        headers={"X-BatchHelm-Proof-Token": "proof-token"})
    public = client.get("/api/v1/qwen/proof")

    assert verified.status_code == 200
    assert public.status_code == 200
    assert public.json() == verified.json()
    assert public.json()["verified"] is True
    assert public.json()["model"] == "qwen3.7-plus"
    assert "provider_request_id" not in public.text
    serialized = public.text
    assert "test-key" not in serialized
    assert '"status":"verified"' not in serialized
    assert "Verify Qwen Cloud" not in serialized


def test_qwen_proof_reports_unavailable_storage() -> None:
    class UnavailableProofRepository:
        def initialize(self) -> None:
            return None

        def save(self, _receipt: object) -> None:
            raise QwenVerificationStoreUnavailable("unavailable")

        def latest(self) -> None:
            raise QwenVerificationStoreUnavailable("unavailable")

    settings = Settings(APP_ENV="test", LOG_LEVEL="debug")
    client = TestClient(
        create_app(
            settings=settings,
            memory_repository=InMemoryMemoryRepository(),
            qwen_verification_repository=UnavailableProofRepository())
    )

    response = client.get("/api/v1/qwen/proof")

    assert response.status_code == 503
    assert response.json()["code"] == "qwen_proof_store_unavailable"


def test_customer_notice_endpoint_accepts_affected_item_override() -> None:
    response = make_client().post(
        "/api/v1/notices/customer-draft", json={"affected_items": 18}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "Important notice: Spinach 10 oz recall"
    assert "18 items" in payload["body"]
