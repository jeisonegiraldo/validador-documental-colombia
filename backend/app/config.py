from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GCP_PROJECT_ID: str = ""
    GCS_BUCKET_NAME: str = "validador-documental-col-docs"
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_SECRET_NAME: str = "gemini-api-key"
    GEMINI_MODEL: str = "gemini-2.0-flash"
    SESSION_TTL_HOURS: int = 24
    SIGNED_URL_EXPIRATION_MINUTES: int = 60
    USE_LOCAL_API_KEY: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_gemini_api_key(settings: Settings | None = None) -> str:
    """Retrieve the Gemini API key from Secret Manager or env var."""
    settings = settings or get_settings()

    if settings.USE_LOCAL_API_KEY or settings.GEMINI_API_KEY:
        return settings.GEMINI_API_KEY

    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{settings.GCP_PROJECT_ID}/secrets/{settings.GEMINI_API_KEY_SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")
