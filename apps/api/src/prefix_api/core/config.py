from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

type AppEnv = Literal["development", "test", "staging", "production"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type LogFormat = Literal["json", "console"]
type MessagingProvider = Literal["console"]

_PLACEHOLDER_SECRET_MARKER = "change-me"  # noqa: S105 - a marker we reject, not a secret


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables and an optional `.env` file.

    Commands are expected to run from the repository root, where `.env` lives.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    app_env: AppEnv = "development"
    log_level: LogLevel = "INFO"
    log_format: LogFormat = "json"

    database_url: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://prefix:prefix@localhost:5432/prefix"
    )
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]

    anthropic_api_key: SecretStr | None = None
    llm_model: str = Field(min_length=1)

    jwt_secret: SecretStr = Field(min_length=32)

    messaging_provider: MessagingProvider = "console"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _reject_placeholder_secrets_in_production(self) -> Self:
        if self.app_env == "production" and (
            _PLACEHOLDER_SECRET_MARKER in self.jwt_secret.get_secret_value()
        ):
            raise ValueError("JWT_SECRET still has the placeholder value from .env.example")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
