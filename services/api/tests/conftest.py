from __future__ import annotations

import json
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

import httpx

from batchhelm_api.config import Settings
from batchhelm_api.qwen import QwenGateway


def make_settings(api_key: str = "", **overrides: object) -> Settings:
    base: dict[str, object] = {
        "QWEN_API_KEY": api_key,
        "QWEN_BASE_URL": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "QWEN_TEXT_MODEL": "qwen-plus",
        "QWEN_VISION_MODEL": "qwen-vl-plus",
        "APP_ENV": "test",
        "LOG_LEVEL": "debug",
        "ORCHESTRATION_DATABASE_PATH": (
            Path(gettempdir()) / f"batchhelm-orchestration-test-{uuid4().hex}.db"
        ),
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def fallback_gateway() -> QwenGateway:
    """A gateway with no API key — always returns deterministic fallback."""

    return QwenGateway(make_settings())


def scripted_gateway(content: dict[str, object]) -> QwenGateway:
    """A 'live' gateway whose provider always returns ``content`` as JSON."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(content)}}]},
        )

    transport = httpx.MockTransport(handler)
    return QwenGateway(
        make_settings(api_key="test-key"),
        client_factory=lambda: httpx.AsyncClient(
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
            transport=transport,
        ),
    )
