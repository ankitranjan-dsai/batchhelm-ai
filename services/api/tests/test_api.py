from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.config import Settings
from batchhelm_api.memory_repository import InMemoryMemoryRepository


def make_client() -> TestClient:
    settings = Settings(
        QWEN_API_KEY="",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug",
    )
    return TestClient(
        create_app(settings=settings, memory_repository=InMemoryMemoryRepository())
    )


def test_health_endpoint() -> None:
    response = make_client().get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "batchhelm-api",
        "version": "0.2.0",
    }


def test_demo_incident_endpoint_returns_recall_input() -> None:
    response = make_client().get("/api/incidents/demo")

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
    response = make_client().post("/api/incidents/demo/analyze")

    assert response.status_code == 200
    payload = response.json()
    assert payload["affected_items"] == 23
    assert payload["evidence_progress"] == 64
    assert len(payload["inventory"]) == 6
    assert payload["customer_notice"]["requires_review"] is True


def test_qwen_status_reports_demo_fallback_when_key_missing() -> None:
    response = make_client().get("/api/qwen/status")

    assert response.status_code == 200
    assert response.json()["mode"] == "demo-fallback"
    assert response.json()["configured"] is False


def test_qwen_summary_uses_fallback_without_key() -> None:
    response = make_client().post("/api/qwen/recall-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["used_fallback"] is True
    assert "Spinach" in payload["content"]["summary"]


def test_customer_notice_endpoint_accepts_affected_item_override() -> None:
    response = make_client().post(
        "/api/notices/customer-draft", json={"affected_items": 18}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "Important notice: Spinach 10 oz recall"
    assert "18 items" in payload["body"]
