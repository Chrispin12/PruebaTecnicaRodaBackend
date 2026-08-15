from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_session
from app.main import app


def test_health_reports_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["version"]


def test_health_reports_503_when_database_is_unreachable(broken_db_client: TestClient) -> None:
    response = broken_db_client.get("/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"


def test_unknown_route_returns_the_standard_error_envelope(client: TestClient) -> None:
    response = client.get("/no-existe")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert "message" in error


class _UnreachableSession:
    """Doble de sesion que falla al consultar, como una base de datos caida."""

    def execute(self, *_args: object, **_kwargs: object) -> None:
        raise SQLAlchemyError("connection refused")


@pytest.fixture
def broken_db_client() -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = _UnreachableSession
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
