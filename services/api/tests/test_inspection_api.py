from pathlib import Path

from fastapi.testclient import TestClient

from batchhelm_api.app import create_app
from batchhelm_api.config import Settings


def make_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        QWEN_API_KEY="",
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug",
        UPLOAD_DIR=tmp_path,
    )
    return TestClient(create_app(settings=settings))


def test_demo_inspection_endpoint_returns_recall_match(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/inspections/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["extracted"]["product_name"] == "Spinach 10 oz"
    assert payload["extracted"]["lot_code"] == "L2418"
    assert payload["recall_match"] is True
    assert payload["used_fallback"] is True


def test_real_shelf_photo_fallback_is_unknown(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/api/inspections/shelf-photo",
        files={"file": ("shelf.png", b"fake-png", "image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["upload"]["original_filename"] == "shelf.png"
    assert payload["upload"]["stored_filename"].endswith(".png")
    assert payload["extracted"]["product_name"] == ""
    assert payload["extracted"]["upc"] == ""
    assert payload["recall_match"] is None
    assert payload["review_required"] is True
    assert Path(payload["upload"]["path"]).exists()


def test_shelf_photo_upload_rejects_text_file(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/api/inspections/shelf-photo",
        files={"file": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "invalid_upload"
