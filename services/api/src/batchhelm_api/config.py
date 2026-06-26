from __future__ import annotations

from functools import lru_cache

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
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: str = Field(default="info", validation_alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def qwen_configured(self) -> bool:
        return bool(self.qwen_api_key.strip())


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
