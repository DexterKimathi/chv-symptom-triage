"""Application settings, read from environment variables or a .env file."""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite keeps local development dependency-free. Set a postgresql+psycopg:// URL
    # in .env to run against PostgreSQL; nothing else changes.
    database_url: str = f"sqlite:///{ROOT / 'chv.db'}"

    # Left empty, a random key is generated at startup. Tokens then stop working after a
    # restart, which is acceptable in development and never a security hole.
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    model_path: str = str(ROOT / "app" / "services" / "model" / "model.joblib")
    model_version: str = "v0.1-lr-uncalibrated"

    # Referral thresholds. PROVISIONAL: to be set from held-out test results and stated in
    # the report. Below low_confidence the top result is not named. A gap between the top
    # two smaller than proximity_margin is too close to call (proposal 1.5.2).
    low_confidence: float = 0.50
    proximity_margin: float = 0.10

    def resolved_secret(self) -> str:
        return self.jwt_secret_key or _GENERATED_SECRET


_GENERATED_SECRET = secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    return Settings()
