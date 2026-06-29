"""Production hardening: structured logging, request IDs, rate limiting, telemetry."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonLogFormatter(logging.Formatter):
    """Compact JSON log lines that are safe to ship to a log service.

    Never logs secrets; only known structured fields plus the message.
    """

    _RESERVED = {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and key not in payload and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


class Telemetry:
    """In-process counters surfaced at /api/telemetry."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)

    def increment(self, name: str, amount: int = 1) -> None:
        self._counters[name] += amount

    def snapshot(self) -> dict[str, int]:
        return dict(self._counters)


class _FixedWindowLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._windows: dict[str, tuple[int, int]] = {}

    def allow(self, key: str) -> bool:
        if self._limit <= 0:
            return True
        window = int(time.time() // 60)
        current_window, count = self._windows.get(key, (window, 0))
        if current_window != window:
            current_window, count = window, 0
        if count >= self._limit:
            self._windows[key] = (current_window, count)
            return False
        self._windows[key] = (current_window, count + 1)
        return True


class ObservabilityMiddleware:
    """Pure ASGI middleware (streams SSE without buffering).

    - assigns/propagates an ``X-Request-ID`` per request
    - enforces a fixed-window rate limit per client IP
    - emits a structured access log line and increments telemetry counters
    """

    _EXEMPT_PATHS = frozenset({"/health"})

    def __init__(self, app: Any, *, rate_limit_per_minute: int, telemetry: Telemetry) -> None:
        self.app = app
        self.telemetry = telemetry
        self._limiter = _FixedWindowLimiter(rate_limit_per_minute)
        self._logger = logging.getLogger("batchhelm.access")

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        incoming = headers.get(b"x-request-id", b"").decode() or uuid4().hex
        token = request_id_var.set(incoming)
        path = scope.get("path", "")
        client = scope.get("client")
        client_ip = client[0] if client else "anonymous"

        if path not in self._EXEMPT_PATHS and not self._limiter.allow(client_ip):
            self.telemetry.increment("rate_limited")
            await self._send_429(send, incoming)
            request_id_var.reset(token)
            return

        started = time.perf_counter()
        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", incoming.encode()))
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self.telemetry.increment("requests")
            self._logger.info(
                "request",
                extra={
                    "method": scope.get("method"),
                    "path": path,
                    "status": status_holder["status"],
                    "elapsed_ms": elapsed_ms,
                    "client_ip": client_ip,
                },
            )
            request_id_var.reset(token)

    async def _send_429(self, send: Any, request_id: str) -> None:
        body = json.dumps(
            {
                "code": "rate_limited",
                "message": "Too many requests; slow down and retry shortly.",
                "details": None,
            }
        ).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"x-request-id", request_id.encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
