from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from base64 import b64encode
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from batchhelm_api.config import Settings
from batchhelm_api.models import (
    ModelImageJSONRequest,
    ModelJSONRequest,
    ModelJSONResponse,
    ProviderStatus,
    QwenVerificationReceipt,
)

logger = logging.getLogger("batchhelm.qwen")


class QwenGatewayError(RuntimeError):
    """Raised when the Qwen provider returns an unusable response."""


@dataclass(frozen=True)
class _ProviderCall:
    payload: dict[str, Any]
    elapsed_ms: int
    request_id: str | None


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
        call = await self._post(payload, label="text")
        raw_text = self._extract_message_content(call.payload)
        return ModelJSONResponse(
            provider="qwen",
            model=self.settings.qwen_text_model,
            used_fallback=False,
            content=_parse_json_object(raw_text),
            raw_text=raw_text,
        )

    async def complete_image_json(
        self, request: ModelImageJSONRequest
    ) -> ModelJSONResponse:
        if not self.settings.qwen_configured:
            return ModelJSONResponse(
                provider="qwen",
                model=self.settings.qwen_vision_model,
                used_fallback=True,
                content=request.fallback,
            )

        payload = self._build_image_payload(request)
        call = await self._post(payload, label="vision")
        raw_text = self._extract_message_content(call.payload)
        return ModelJSONResponse(
            provider="qwen",
            model=self.settings.qwen_vision_model,
            used_fallback=False,
            content=_parse_json_object(raw_text),
            raw_text=raw_text,
        )

    async def verify_live(self) -> QwenVerificationReceipt:
        if not self.settings.qwen_configured:
            raise QwenGatewayError("Qwen provider is not configured.")

        payload = {
            "model": self.settings.qwen_text_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only. Respond with exactly "
                        '{"status":"verified","service":"batchhelm"}.'
                    ),
                },
                {
                    "role": "user",
                    "content": "Verify Qwen Cloud connectivity for BatchHelm.",
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        call = await self._post(payload, label="verification")
        raw_text = self._extract_message_content(call.payload)
        content = _parse_json_object(raw_text)
        if content != {"status": "verified", "service": "batchhelm"}:
            raise QwenGatewayError(
                "Qwen verification response did not match the proof contract."
            )

        return QwenVerificationReceipt(
            model=self.settings.qwen_text_model,
            latency_ms=call.elapsed_ms,
            response_sha256=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            verified_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )

    async def _post(self, payload: dict[str, Any], *, label: str) -> _ProviderCall:
        """POST to the provider with bounded retries and telemetry.

        Retries on transient transport errors and 5xx responses with
        exponential backoff. 4xx responses fail fast (they will not improve on
        retry). The API key is never logged.
        """

        headers = {
            "Authorization": f"Bearer {self.settings.qwen_api_key}",
            "Content-Type": "application/json",
        }
        attempts = max(1, self.settings.qwen_max_retries)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                async with self._make_client() as client:
                    response = await client.post(
                        "/chat/completions", headers=headers, json=payload
                    )
                response.raise_for_status()
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "qwen call ok",
                    extra={
                        "qwen_label": label,
                        "qwen_model": payload.get("model"),
                        "qwen_attempt": attempt,
                        "qwen_elapsed_ms": elapsed_ms,
                    },
                )
                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise QwenGatewayError(
                        "Qwen provider response was not valid JSON."
                    ) from exc
                if not isinstance(data, dict):
                    raise QwenGatewayError(
                        "Qwen provider response must be a JSON object."
                    )
                request_id = data.get("id")
                if not isinstance(request_id, str) or not request_id.strip():
                    request_id = (
                        response.headers.get("x-request-id")
                        or response.headers.get("x-dashscope-request-id")
                    )
                return _ProviderCall(
                    payload=data,
                    elapsed_ms=elapsed_ms,
                    request_id=request_id,
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status = exc.response.status_code
                if status < 500 or attempt >= attempts:
                    logger.warning(
                        "qwen call failed",
                        extra={
                            "qwen_label": label,
                            "qwen_status": status,
                            "qwen_attempt": attempt,
                        },
                    )
                    raise QwenGatewayError(
                        f"Qwen provider returned HTTP {status}."
                    ) from exc
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= attempts:
                    logger.warning(
                        "qwen transport error",
                        extra={"qwen_label": label, "qwen_attempt": attempt},
                    )
                    raise QwenGatewayError("Qwen provider request failed.") from exc
            await asyncio.sleep(0.2 * attempt)

        raise QwenGatewayError("Qwen provider request failed.") from last_error

    def _make_client(self) -> httpx.AsyncClient:
        if self._client_factory is not None:
            return self._client_factory()

        return httpx.AsyncClient(
            base_url=str(self.settings.qwen_base_url).rstrip("/"),
            timeout=httpx.Timeout(
                self.settings.qwen_timeout_seconds, connect=10.0
            ),
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

    def _build_image_payload(self, request: ModelImageJSONRequest) -> dict[str, Any]:
        image_data = b64encode(request.image_bytes).decode("ascii")
        data_url = f"data:{request.media_type};base64,{image_data}"
        return {
            "model": self.settings.qwen_vision_model,
            "messages": [
                {"role": "system", "content": request.system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.user},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0.1,
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
