from collections.abc import Callable

import pytest
from api_testkit import TEST_KEY_ACTIVE, TEST_KEY_OLD
from pydantic import ValidationError

from prefix_api.core.config import Settings

type SettingsFactory = Callable[..., Settings]


def test_settings_are_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000, https://app.prefix.ai")
    monkeypatch.setenv("LLM_MODEL", "env-model")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("PII_ENCRYPTION_KEYS", f"{TEST_KEY_ACTIVE}, {TEST_KEY_OLD}")
    monkeypatch.setenv("PII_BLIND_INDEX_KEY", "b" * 32)

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:3000", "https://app.prefix.ai"]
    assert settings.llm_model == "env-model"
    assert [key.get_secret_value() for key in settings.pii_encryption_keys] == [
        TEST_KEY_ACTIVE,
        TEST_KEY_OLD,
    ]


def test_llm_model_is_required(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="llm_model"):
        make_settings(llm_model="")


def test_short_jwt_secret_is_rejected(make_settings: SettingsFactory) -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        make_settings(jwt_secret="too-short")


def test_placeholder_jwt_secret_is_rejected_in_production(
    make_settings: SettingsFactory,
) -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        make_settings(app_env="production", jwt_secret="change-me-" + "x" * 32)


def test_placeholder_jwt_secret_is_allowed_in_development(
    make_settings: SettingsFactory,
) -> None:
    settings = make_settings(app_env="development", jwt_secret="change-me-" + "x" * 32)

    assert settings.app_env == "development"


def test_secrets_are_masked_in_repr(make_settings: SettingsFactory) -> None:
    settings = make_settings(anthropic_api_key="sk-ant-secret-value")

    assert "sk-ant-secret-value" not in repr(settings)


def test_development_encryption_key_is_rejected_in_production(
    make_settings: SettingsFactory,
) -> None:
    with pytest.raises(ValidationError, match="development key"):
        make_settings(
            app_env="production",
            jwt_secret="x" * 40,
            pii_blind_index_key="y" * 40,
            pii_encryption_keys=["dev1:" + TEST_KEY_ACTIVE.split(":")[1]],
        )


def test_placeholder_blind_index_key_is_rejected_in_production(
    make_settings: SettingsFactory,
) -> None:
    with pytest.raises(ValidationError, match="PII_BLIND_INDEX_KEY"):
        make_settings(
            app_env="production", jwt_secret="x" * 40, pii_blind_index_key="change-me-" + "y" * 32
        )
