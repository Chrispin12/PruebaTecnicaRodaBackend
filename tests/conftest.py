"""Fixtures compartidas.

Los tests de integracion corren contra un PostgreSQL real, no SQLite: el esquema depende
de NUMERIC y de CHECK constraints, asi que una base en memoria daria tests verdes sobre un
comportamiento que en produccion no existe.

El esquema se crea aplicando las migraciones de Alembic, de modo que cada ejecucion
tambien verifica que las migraciones sigan siendo aplicables.
"""

from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.main import app

ALEMBIC_CONFIG_PATH = "alembic.ini"

# Tasas fijas para los tests de API. Se inyectan por dependencia para que el resultado no
# dependa del .env de quien ejecute los tests: si manana la demo cambia de tasa, estos tests
# deben seguir siendo validos.
TEST_ANNUAL_RATE = Decimal("0.24")
TEST_MAX_ANNUAL_RATE = Decimal("0.45")


class TestSettings(BaseSettings):
    """Configuracion exclusiva de los tests, separada de la de la aplicacion."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    test_database_url: str


@pytest.fixture(scope="session")
def test_settings() -> TestSettings:
    return TestSettings()  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def engine(test_settings: TestSettings) -> Iterator[Engine]:
    _apply_migrations(test_settings.test_database_url)
    engine = create_engine(test_settings.test_database_url)
    yield engine
    engine.dispose()


def _apply_migrations(database_url: str) -> None:
    config = Config(ALEMBIC_CONFIG_PATH)
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """Sesion aislada: cada test corre dentro de una transaccion que se revierte.

    `join_transaction_mode="create_savepoint"` permite que el codigo bajo prueba haga
    commit (como haran los services) sin que los datos sobrevivan al test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def _settings_override(annual_rate: Decimal, max_annual_rate: Decimal) -> Callable[[], Settings]:
    def override() -> Settings:
        return get_settings().model_copy(
            update={
                "credit_annual_rate": annual_rate,
                "credit_max_annual_rate": max_annual_rate,
            }
        )

    return override


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    """Cliente HTTP con la sesion transaccional del test y tasas deterministas."""
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = _settings_override(
        TEST_ANNUAL_RATE, TEST_MAX_ANNUAL_RATE
    )
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def override_rates() -> Callable[[Decimal, Decimal], None]:
    """Cambia la configuracion financiera dentro de un test.

    Sirve para comprobar que la tasa realmente viaja desde la configuracion hasta el motor.
    La limpieza la hace el fixture `client`, que debe pedirse junto a este.
    """

    def apply(annual_rate: Decimal, max_annual_rate: Decimal) -> None:
        app.dependency_overrides[get_settings] = _settings_override(annual_rate, max_annual_rate)

    return apply
