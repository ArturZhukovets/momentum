"""Application configuration.

`.env` is loaded at import time, *before* Settings is built, so real
environment variables (Docker, systemd) always take precedence over the file.
Nothing else in the codebase reads os.environ directly — import `settings`.
The one outside reader is the langsmith SDK: it picks `LANGSMITH_*` up from the
environment on its own, which is why they have no fields here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import PositiveFloat, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    BOT_TOKEN: SecretStr
    BOT_MODE: Literal["polling", "webhook"] = "polling"

    # Webhook mode only.
    WEBHOOK_BASE: str = ""
    WEBHOOK_PATH: str = "/tg/momentum"
    WEBHOOK_SECRET: SecretStr = SecretStr("")
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8080
    INTERNAL_API_KEY: SecretStr = SecretStr("")

    DB_PATH: str = "data/momentum.db"

    # JSON list in .env — pydantic-settings decodes collection fields.
    ADMIN_USER_IDS: frozenset[int]

    APP_TZ: str = "Europe/Belgrade"
    WEEKLY_GOAL: int = 3
    REPORT_HOUR: int = 9

    # Coach comment in reports. An empty key turns it off — there is no separate flag.
    LLM_API_KEY: SecretStr = SecretStr("")
    LLM_MODEL: str = "anthropic:claude-haiku-4-5"
    # Seconds one report may wait for its comment, retries included; the broadcast is sequential.
    LLM_TIMEOUT: PositiveFloat = 60.0
    # OpenAI reasoning models only (none | low | medium | high | ...); empty = the model's default.
    # Ignored for other providers, which don't take the parameter.
    LLM_REASONING_EFFORT: str = "medium"

    LOG_LEVEL: str = "INFO"

    @field_validator("APP_TZ")
    @classmethod
    def _validate_tz(cls, value: str) -> str:
        ZoneInfo(value)  # raises for an unknown zone — fail fast at startup
        return value

    @field_validator("ADMIN_USER_IDS")
    @classmethod
    def _validate_admin_ids(cls, value: frozenset[int]) -> frozenset[int]:
        if not value:
            raise ValueError("ADMIN_USER_IDS must list at least one Telegram user id")
        bad = sorted(user_id for user_id in value if user_id <= 0)
        if bad:
            raise ValueError(f"ADMIN_USER_IDS contains non-positive id(s): {bad}")
        return value

    @model_validator(mode="after")
    def _check_webhook_config(self) -> Settings:
        if self.BOT_MODE == "webhook" and not self.WEBHOOK_BASE.startswith("https://"):
            raise ValueError("BOT_MODE=webhook requires WEBHOOK_BASE to be an https:// URL")
        return self

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.APP_TZ)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.LLM_API_KEY.get_secret_value())

    @property
    def db_file(self) -> Path:
        path = Path(self.DB_PATH)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def webhook_url(self) -> str:
        return f"{self.WEBHOOK_BASE.rstrip('/')}/{self.WEBHOOK_PATH.lstrip('/')}"


settings = Settings()
