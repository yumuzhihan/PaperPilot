import logging
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    BASE_DIR: Path = Path(__file__).parent.parent.parent
    ENV_FILE_PATH: Path = BASE_DIR / ".env"

    # 基础配置
    LOG_DIR: Path = BASE_DIR / "logs"
    DATA_DIR: Path = BASE_DIR / "data"
    LOG_LEVEL: str = "INFO"
    MAX_TURNS: int = 30
    OUTPUT_LANGUAGE: str = "中文"

    # LLM 配置
    LLM_PROVIDER: str = "ollama"
    LLM_MODEL: str = "qwen3:8b"
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_TEMP: float = 0.7
    LLM_THINK: bool = True
    LLM_RETRY_MAX_ATTEMPTS: int = 5
    LLM_RETRY_BASE_DELAY: float = 1.0
    LLM_RETRY_MAX_DELAY: float = 16.0

    model_config = SettingsConfigDict(
        env_file=ENV_FILE_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
