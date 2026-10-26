from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[3] / ".env", extra="ignore")
    database_url: str = "postgresql+psycopg://easycrm:easycrm@localhost:5432/easycrm"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    cookie_secure: bool = False
    session_ttl_seconds: int = 3600
    gemini_api_key: SecretStr = SecretStr("")
    nvidia_api_key: SecretStr = SecretStr("")
    nvidia_models: list[str] = [
        "nvidia/nemotron-3-ultra-550b-a55b",
        "nvidia/llama-3.3-nemotron-super-49b-v1.5",
    ]
    ai_timeout_seconds: float = 60
    ai_models_cache_seconds: int = 300

    @field_validator("nvidia_models")
    @classmethod
    def valid_models(cls, values: list[str]) -> list[str]:
        import re

        if any(
            not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/-]{0,199}", x)
            or any(part in ("", ".", "..") for part in x.split("/"))
            for x in values
        ):
            raise ValueError("Invalid model identifier")
        return list(dict.fromkeys(values))


@lru_cache
def get_settings() -> Settings:
    return Settings()
