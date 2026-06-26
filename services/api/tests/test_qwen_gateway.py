from __future__ import annotations

import httpx
import pytest

from batchhelm_api.config import Settings
from batchhelm_api.models import ModelImageJSONRequest, ModelJSONRequest
from batchhelm_api.qwen import QwenGateway, QwenGatewayError


def make_settings(api_key: str = "") -> Settings:
    return Settings(
        QWEN_API_KEY=api_key,
        QWEN_BASE_URL="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        QWEN_TEXT_MODEL="qwen-plus",
        QWEN_VISION_MODEL="qwen-vl-plus",
        APP_ENV="test",
        LOG_LEVEL="debug",
    )


@pytest.mark.asyncio
async def test_gateway_returns_fallback_when_key_is_missing() -> None:
    gateway = QwenGateway(make_settings())
    request = ModelJSONRequest(
        system="Return JSON.",
        user="Analyze recall.",
        fallback={"risk_level": "high", "affected_items": 23},
    )

    response = await gateway.complete_json(request)

    assert response.used_fallback is True
    assert response.content == {"risk_level": "high", "affected_items": 23}
    assert gateway.status().mode == "demo-fallback"


@pytest.mark.asyncio
async def test_gateway_posts_openai_compatible_chat_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"summary":"matched lots","confidence":97}'}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    def client_factory() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            transport=transport,
        )

    gateway = QwenGateway(make_settings(api_key="test-key"), client_factory=client_factory)

    response = await gateway.complete_json(
        ModelJSONRequest(system="Return JSON.", user="Analyze recall.")
    )

    assert captured["path"] == "/compatible-mode/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key"
    assert '"response_format":{"type":"json_object"}' in str(captured["payload"])
    assert response.used_fallback is False
    assert response.content == {"summary": "matched lots", "confidence": 97}
    assert gateway.status().mode == "live"


@pytest.mark.asyncio
async def test_gateway_rejects_non_json_provider_content() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )
    )

    gateway = QwenGateway(
        make_settings(api_key="test-key"),
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            transport=transport,
        ),
    )

    with pytest.raises(QwenGatewayError):
        await gateway.complete_json(ModelJSONRequest(system="Return JSON.", user="Analyze."))


@pytest.mark.asyncio
async def test_vision_gateway_returns_fallback_when_key_is_missing() -> None:
    gateway = QwenGateway(make_settings())

    response = await gateway.complete_image_json(
        ModelImageJSONRequest(
            system="Inspect shelf image.",
            user="Extract label fields.",
            image_bytes=b"image",
            media_type="image/png",
            fallback={"product_name": "Spinach 10 oz", "lot_code": "L2418"},
        )
    )

    assert response.used_fallback is True
    assert response.model == "qwen-vl-plus"
    assert response.content["lot_code"] == "L2418"


@pytest.mark.asyncio
async def test_vision_gateway_posts_image_url_content_part() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"product_name":"Spinach 10 oz","lot_code":"L2418",'
                                '"upc":"008500001010","confidence":96}'
                            )
                        }
                    }
                ]
            },
        )

    gateway = QwenGateway(
        make_settings(api_key="test-key"),
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            transport=httpx.MockTransport(handler),
        ),
    )

    response = await gateway.complete_image_json(
        ModelImageJSONRequest(
            system="Inspect shelf image.",
            user="Extract label fields.",
            image_bytes=b"abc",
            media_type="image/png",
        )
    )

    payload = str(captured["payload"])
    assert '"model":"qwen-vl-plus"' in payload
    assert '"type":"image_url"' in payload
    assert "data:image/png;base64,YWJj" in payload
    assert response.used_fallback is False
    assert response.content["confidence"] == 96
