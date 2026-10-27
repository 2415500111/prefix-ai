import os

# celery_app reads settings at import time; give it valid values without needing a .env.
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-that-is-at-least-32-chars")
os.environ.setdefault("APP_ENV", "test")
