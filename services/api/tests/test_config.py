from batchhelm_api.config import Settings


def test_qwen_cloud_defaults_use_current_supported_models() -> None:
    settings = Settings(_env_file=None)

    assert str(settings.qwen_base_url) == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    assert settings.qwen_text_model == "qwen3.7-plus"
    assert settings.qwen_vision_model == "qwen3-vl-plus"
