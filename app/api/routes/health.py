from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_session

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    database: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def read_health(
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Comprueba que el proceso responde y que la base de datos esta alcanzable.

    Incluye la base de datos a proposito: en un despliegue con Cloud SQL, un 200 aqui
    demuestra que la conexion esta bien configurada, no solo que el contenedor arranco.
    """
    _assert_database_available(session)
    return HealthResponse(status="ok", version=settings.app_version, database="ok")


def _assert_database_available(session: Session) -> None:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise ServiceUnavailableError("La base de datos no esta disponible.") from exc
