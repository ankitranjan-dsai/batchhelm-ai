from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    qwen_api_key: str = Field(default="", validation_alias="QWEN_API_KEY")
    qwen_base_url: AnyHttpUrl = Field(
        default="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        validation_alias="QWEN_BASE_URL",
    )
    qwen_text_model: str = Field(default="qwen-plus", validation_alias="QWEN_TEXT_MODEL")
    qwen_vision_model: str = Field(
        default="qwen-vl-plus", validation_alias="QWEN_VISION_MODEL"
    )
    qwen_timeout_seconds: float = Field(
        default=30.0, validation_alias="QWEN_TIMEOUT_SECONDS"
    )
    qwen_max_retries: int = Field(default=2, validation_alias="QWEN_MAX_RETRIES")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")
    database_path: Path = Field(
        default=Path("./data/batchhelm.db"),
        validation_alias="DATABASE_PATH",
    )
    memory_path: Path = Field(
        default=Path("./data/batchhelm-memory.db"),
        validation_alias="MEMORY_PATH",
    )
    orchestration_database_path: Path = Field(
        default=Path("./data/orchestration.db"),
        validation_alias="ORCHESTRATION_DATABASE_PATH",
    )
    intake_database_path: Path = Field(
        default=Path("./data/intake.db"),
        validation_alias="INTAKE_DATABASE_PATH",
    )
    upload_dir: Path = Field(default=Path("./data/uploads"), validation_alias="UPLOAD_DIR")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )
    rate_limit_per_minute: int = Field(
        default=60, validation_alias="RATE_LIMIT_PER_MINUTE"
    )
    reviewer_role: str = Field(
        default="Operations Manager", validation_alias="REVIEWER_ROLE"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def qwen_configured(self) -> bool:
        return bool(self.qwen_api_key.strip())

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
