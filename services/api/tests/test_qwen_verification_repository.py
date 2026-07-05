from pathlib import Path

from batchhelm_api.models import QwenVerificationReceipt
from batchhelm_api.qwen_verification_repository import (
    SQLiteQwenVerificationRepository,
)


def build_receipt(
    request_id: str,
    verified_at: str,
) -> QwenVerificationReceipt:
    return QwenVerificationReceipt(
        model="qwen3.7-plus",
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        provider_request_id=request_id,
        latency_ms=125,
        response_sha256="a" * 64,
        verified_at=verified_at,
    )


def test_sqlite_repository_returns_none_before_first_receipt(
    tmp_path: Path,
) -> None:
    repository = SQLiteQwenVerificationRepository(tmp_path / "proof.db")
    repository.initialize()

    assert repository.latest() is None


def test_sqlite_repository_persists_latest_receipt(tmp_path: Path) -> None:
    database_path = tmp_path / "proof.db"
    repository = SQLiteQwenVerificationRepository(database_path)
    repository.initialize()
    repository.save(build_receipt("request-one", "2026-07-05T10:00:00Z"))
    repository.save(build_receipt("request-two", "2026-07-05T10:01:00Z"))

    reopened = SQLiteQwenVerificationRepository(database_path)
    reopened.initialize()
    latest = reopened.latest()

    assert latest is not None
    assert latest.provider_request_id == "request-two"
    assert latest.verified_at == "2026-07-05T10:01:00Z"
