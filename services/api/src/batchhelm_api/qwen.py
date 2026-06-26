from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx

from batchhelm_api.config import Settings
from batchhelm_api.models import ModelJSONRequest, ModelJSONResponse, ProviderStatus


class QwenGatewayError(RuntimeError):
    """Raised when the Qwen provider returns an unusable response."""


class QwenGateway:
    def __init__(
        self,
        settings: Settings,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            configured=self.settings.qwen_configured,
            base_url=str(self.settings.qwen_base_url),
            text_model=self.settings.qwen_text_model,
            vision_model=self.settings.qwen_vision_model,
            mode="live" if self.settings.qwen_configured else "demo-fallback",
        )

    async def complete_json(self, request: ModelJSONRequest) -> ModelJSONResponse:
        if not self.settings.qwen_configured:
            return ModelJSONResponse(
                provider="qwen",
                model=self.settings.qwen_text_model,
                used_fallback=True,
                content=request.fallback,
            )

        payload = self._build_chat_payload(request)
        headers = {
            "Authorization": f"Bearer {self.settings.qwen_api_key}",
            "Content-Type": "application/json",
        }
        async with self._make_client() as client:
            response = await client.post(
                "/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        raw_text = self._extract_message_content(response.json())
        return ModelJSONResponse(
            provider="qwen",
            model=self.settings.qwen_text_model,
            used_fallback=False,
            content=_parse_json_object(raw_text),
            raw_text=raw_text,
        )

    def _make_client(self) -> httpx.AsyncClient:
        if self._client_factory is not None:
            return self._client_factory()

        return httpx.AsyncClient(
            base_url=str(self.settings.qwen_base_url).rstrip("/"),
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    def _build_chat_payload(self, request: ModelJSONRequest) -> dict[str, Any]:
        return {
            "model": self.settings.qwen_text_model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }

    @staticmethod
    def _extract_message_content(payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise QwenGatewayError("Provider response did not include message content.") from exc

        if not isinstance(content, str) or not content.strip():
            raise QwenGatewayError("Provider response message content was empty.")

        return content


def _parse_json_object(raw_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise QwenGatewayError("Provider response was not valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise QwenGatewayError("Provider response JSON must be an object.")

    return parsed
