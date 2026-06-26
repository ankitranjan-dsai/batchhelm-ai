from datetime import datetime, timezone

from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.config import Settings
from batchhelm_api.evidence_packet import build_demo_shelf_inspection, build_evidence_packet
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident


def make_client() -> TestClient:
    settings = Settings(
        QWEN_API_KEY="",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug",
    )
    return TestClient(create_app(settings=settings))


def test_build_evidence_packet_contains_core_recall_sections() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)

    packet = build_evidence_packet(
        incident=incident,
        analysis=analysis,
        inspection=build_demo_shelf_inspection(),
        generated_at=datetime(2026, 6, 26, 10, 30, tzinfo=timezone.utc),
    )

    assert packet.filename == "batchhelm-recall-spinach-2026-06-evidence.md"
    assert packet.incident_id == "recall-spinach-2026-06"
    assert packet.generated_at == "2026-06-26T10:30:00+00:00"
    assert packet.sections[0].title == "Executive Summary"
    assert "## Executive Summary" in packet.markdown
    assert "Spinach 10 oz" in packet.markdown
    assert "L2418-L2422" in packet.markdown
    assert (
        "| Store | SKU | Product | Lot | Quarantined | Location | Confidence |"
        in packet.markdown
    )
    assert "Customer Notice Draft" in packet.markdown
    assert "Shelf Inspection Evidence" in packet.markdown


def test_demo_evidence_packet_endpoint_returns_preview() -> None:
    response = make_client().get("/api/evidence/demo-packet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"].endswith(".md")
    assert payload["sections"][0]["title"] == "Executive Summary"
    assert "Regulatory Filing Package" in payload["markdown"]
    assert payload["incident_id"] == "recall-spinach-2026-06"


def test_demo_evidence_packet_download_has_attachment_header() -> None:
    response = make_client().get("/api/evidence/demo-packet.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "attachment" in response.headers["content-disposition"]
    assert (
        "batchhelm-recall-spinach-2026-06-evidence.md"
        in response.headers["content-disposition"]
    )
    assert "# BatchHelm Recall Evidence Packet" in response.text
