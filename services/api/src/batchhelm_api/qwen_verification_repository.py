from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from batchhelm_api.models import QwenVerificationReceipt

SCHEMA_VERSION = 2


class QwenVerificationStoreUnavailable(RuntimeError):
    pass


class QwenVerificationRepository(Protocol):
    def initialize(self) -> None: ...

    def save(self, receipt: QwenVerificationReceipt) -> None: ...

    def latest(self) -> QwenVerificationReceipt | None: ...


class InMemoryQwenVerificationRepository:
    def __init__(self) -> None:
        self._receipts: list[QwenVerificationReceipt] = []

    def initialize(self) -> None:
        return None

    def save(self, receipt: QwenVerificationReceipt) -> None:
        self._receipts.append(receipt)

    def latest(self) -> QwenVerificationReceipt | None:
        return self._receipts[-1] if self._receipts else None


class SQLiteQwenVerificationRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute("PRAGMA journal_mode = WAL")
                    version = int(
                        connection.execute("PRAGMA user_version").fetchone()[0]
                    )
                    if version > SCHEMA_VERSION:
                        raise QwenVerificationStoreUnavailable(
                            "Qwen verification database schema is newer than this service."
                        )
                    if version == 0:
                        connection.execute(
                            """
                            CREATE TABLE qwen_verification_receipts (
                                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                                provider TEXT NOT NULL,
                                verified INTEGER NOT NULL CHECK (verified = 1),
                                model TEXT NOT NULL,
                                latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
                                response_sha256 TEXT NOT NULL CHECK (
                                    length(response_sha256) = 64
                                ),
                                verified_at TEXT NOT NULL
                            )
                            """
                        )
                        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    elif version < SCHEMA_VERSION:
                        connection.execute(
                            "DROP TABLE IF EXISTS qwen_verification_receipts"
                        )
                        connection.execute(
                            """
                            CREATE TABLE qwen_verification_receipts (
                                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                                provider TEXT NOT NULL,
                                verified INTEGER NOT NULL CHECK (verified = 1),
                                model TEXT NOT NULL,
                                latency_ms INTEGER NOT NULL CHECK (latency_ms >= 0),
                                response_sha256 TEXT NOT NULL CHECK (
                                    length(response_sha256) = 64
                                ),
                                verified_at TEXT NOT NULL
                            )
                            """
                        )
                        connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except QwenVerificationStoreUnavailable:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise QwenVerificationStoreUnavailable(
                "Qwen verification storage is unavailable."
            ) from exc

    def save(self, receipt: QwenVerificationReceipt) -> None:
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO qwen_verification_receipts (
                            provider,
                            verified,
                            model,
                            latency_ms,
                            response_sha256,
                            verified_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            receipt.provider,
                            int(receipt.verified),
                            receipt.model,
                            receipt.latency_ms,
                            receipt.response_sha256,
                            receipt.verified_at,
                        ),
                    )
        except sqlite3.Error as exc:
            raise QwenVerificationStoreUnavailable(
                "Qwen verification storage is unavailable."
            ) from exc

    def latest(self) -> QwenVerificationReceipt | None:
        try:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT
                        provider,
                        verified,
                        model,
                        latency_ms,
                        response_sha256,
                        verified_at
                    FROM qwen_verification_receipts
                    ORDER BY sequence DESC
                    LIMIT 1
                    """
                ).fetchone()
        except sqlite3.Error as exc:
            raise QwenVerificationStoreUnavailable(
                "Qwen verification storage is unavailable."
            ) from exc

        if row is None:
            return None
        return QwenVerificationReceipt(
            provider=str(row["provider"]),
            verified=bool(row["verified"]),
            model=str(row["model"]),
            latency_ms=int(row["latency_ms"]),
            response_sha256=str(row["response_sha256"]),
            verified_at=str(row["verified_at"]),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
