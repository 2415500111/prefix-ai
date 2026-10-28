from functools import lru_cache
from typing import Annotated, Literal, Self

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

type AppEnv = Literal["development", "test", "staging", "production"]
type LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
type LogFormat = Literal["json", "console"]
type MessagingProvider = Literal["console", "live"]
type EmbeddingProviderName = Literal["local"]

_PLACEHOLDER_SECRET_MARKER = "change-me"
_DEV_KEY_ID_PREFIX = "dev"


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
    web_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:3000")

    anthropic_api_key: SecretStr | None = None
    llm_model: str = Field(min_length=1)

    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "prefix-ai"
    jwt_access_ttl_minutes: int = Field(default=15, ge=1, le=60)
    jwt_refresh_ttl_days: int = Field(default=7, ge=1, le=30)

    magic_link_ttl_minutes: int = Field(default=1440, ge=5, le=4320)
    patient_session_ttl_minutes: int = Field(default=720, ge=15, le=1440)

    # "<key-id>:<base64 32-byte key>" entries, comma-separated. The first entry encrypts;
    # all entries decrypt, so old keys stay listed until data is re-encrypted.
    pii_encryption_keys: Annotated[list[SecretStr], NoDecode] = Field(min_length=1)
    pii_blind_index_key: SecretStr = Field(min_length=32)

    # console: log messages instead of sending. live: Twilio for SMS/WhatsApp, SMTP for email.
    messaging_provider: MessagingProvider = "console"
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_sms_from: str | None = None
    twilio_whatsapp_from: str | None = None
    # Public URL Twilio calls for inbound messages; used to verify webhook signatures.
    public_api_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    dispatch_batch_size: int = Field(default=100, ge=1, le=1000)
    translation_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    # The patient waits on the assistant: past this, the question goes to a nurse instead.
    assistant_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    embedding_provider: EmbeddingProviderName = "local"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator(
        "anthropic_api_key",
        "twilio_account_sid",
        "twilio_auth_token",
        "twilio_sms_from",
        "twilio_whatsapp_from",
        "smtp_host",
        "smtp_username",
        "smtp_password",
        "smtp_from",
        mode="before",
    )
    @classmethod
    def _empty_means_unset(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("pii_encryption_keys", mode="before")
    @classmethod
    def _split_pii_keys(cls, value: object) -> object:
        if isinstance(value, str):
            return [entry.strip() for entry in value.split(",") if entry.strip()]
        return value

    @model_validator(mode="after")
    def _live_messaging_needs_credentials(self) -> Self:
        if self.messaging_provider == "live" and not (
            self.twilio_account_sid and self.twilio_auth_token
        ):
            raise ValueError(
                "MESSAGING_PROVIDER=live needs TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN"
            )
        return self

    @model_validator(mode="after")
    def _reject_development_secrets_in_production(self) -> Self:
        if self.app_env != "production":
            return self
        if _PLACEHOLDER_SECRET_MARKER in self.jwt_secret.get_secret_value():
            raise ValueError("JWT_SECRET still has the placeholder value from .env.example")
        if _PLACEHOLDER_SECRET_MARKER in self.pii_blind_index_key.get_secret_value():
            raise ValueError("PII_BLIND_INDEX_KEY still has the placeholder value")
        for entry in self.pii_encryption_keys:
            if entry.get_secret_value().startswith(_DEV_KEY_ID_PREFIX):
                raise ValueError("PII_ENCRYPTION_KEYS contains a development key")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
