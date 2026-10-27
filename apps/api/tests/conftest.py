from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prefix_api.core.config import Settings
from prefix_api.main import create_app

type SettingsFactory = Callable[..., Settings]

TEST_JWT_SECRET = "test-jwt-secret-that-is-at-least-32-chars"


@pytest.fixture
def make_settings() -> SettingsFactory:
    """Build Settings from explicit values only, ignoring the environment and `.env`."""

    def factory(**overrides: object) -> Settings:
        values: dict[str, object] = {
            "app_env": "test",
            "llm_model": "test-model",
            "jwt_secret": TEST_JWT_SECRET,
            "cors_origins": ["http://localhost:3000"],
        }
        values.update(overrides)
        return Settings.model_validate(values)

    return factory


@pytest.fixture
def settings(make_settings: SettingsFactory) -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
