from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: Literal["pilot", "production", "test"] = "pilot"
    app_origin: str = "http://localhost:8080"
    database_url: str = "sqlite:///./presspilot.db"
    data_dir: Path = Path("./data")
    static_dir: Path = Path("../frontend/dist")
    secure_cookies: bool = False
    session_ttl_seconds: int = Field(default=43200, ge=300, le=86400)
    max_upload_mb: int = Field(default=25, ge=1, le=100)
    scanner_url: str = ""
    scanner_token: str = ""
    scan_timeout_seconds: int = Field(default=45, ge=10, le=120)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    llm_base_url: str = ""  # Optional Ollama /api/chat endpoint; operator-controlled.
    llm_model: str = ""

    @model_validator(mode="after")
    def enforce_production(self):
        self.app_origin = self.app_origin.rstrip("/")
        if self.app_env == "production":
            if not self.secure_cookies or not self.app_origin.startswith("https://"):
                raise ValueError("Production requires HTTPS APP_ORIGIN and SECURE_COOKIES=true")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Production requires PostgreSQL")
            if not self.scanner_url or len(self.scanner_token) < 32:
                raise ValueError("Production requires the isolated scanner and a strong scanner token")
        return self


@lru_cache
def settings() -> Settings:
    return Settings()
