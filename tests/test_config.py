"""Configuracion: lo que debe fallar al arrancar, no en runtime."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

_DB_URL = "postgresql+psycopg://roda:roda@localhost:5432/roda"


def _settings(**overrides: object) -> Settings:
    return Settings(database_url=_DB_URL, **overrides)  # type: ignore[arg-type]


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOW_ORIGINS"):
        _settings(environment="production", cors_allow_origins="*")


def test_production_rejects_wildcard_among_other_origins() -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOW_ORIGINS"):
        _settings(
            environment="production",
            cors_allow_origins="https://app.example.com,*",
        )


def test_production_accepts_an_explicit_frontend_origin() -> None:
    settings = _settings(
        environment="production",
        cors_allow_origins="https://app.example.com",
    )

    assert settings.cors_origins == ["https://app.example.com"]


def test_local_allows_wildcard_cors() -> None:
    settings = _settings(environment="local", cors_allow_origins="*")

    assert settings.cors_origins == ["*"]


def test_cors_origins_are_split_and_stripped() -> None:
    settings = _settings(
        cors_allow_origins=" http://localhost:5173 , https://preview.example.com ",
    )

    assert settings.cors_origins == [
        "http://localhost:5173",
        "https://preview.example.com",
    ]
