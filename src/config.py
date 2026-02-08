"""Application configuration."""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    fast_track_damage_threshold: float = 25_000.0
    openai_api_key: Optional[str] = None  # Reserved for LLM-enhanced extraction


settings = Settings()
