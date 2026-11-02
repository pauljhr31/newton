"""Application settings. All secrets come from environment variables, never from code."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False, extra="ignore")

    newton_env: Literal["development", "test", "production"] = "development"

    # Restricted runtime role (subject to Row-Level Security).
    database_url: str = Field(..., description="postgresql+psycopg://newton_app:...@db/newton")

    jwt_secret: str = Field(..., min_length=32)
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Cookies must be Secure in production (HTTPS). Local dev runs over plain HTTP.
    cookie_secure: bool = False

    login_max_failures: int = 5
    login_window_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
