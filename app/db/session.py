from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

# Cloud Run crea y destruye instancias con frecuencia y Cloud SQL limita conexiones:
# un pool pequeno con reciclado evita agotar el limite con conexiones inactivas.
POOL_SIZE = 5
MAX_OVERFLOW = 5
POOL_RECYCLE_SECONDS = 1800


@lru_cache
def get_engine() -> Engine:
    """Engine unico por proceso. Perezoso para no abrir conexiones al importar modulos."""
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_recycle=POOL_RECYCLE_SECONDS,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    # expire_on_commit=False permite leer atributos del objeto despues del commit,
    # sin que SQLAlchemy dispare un SELECT adicional al serializar la respuesta.
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Dependencia FastAPI: una sesion por request, cerrada siempre al terminar."""
    with get_session_factory()() as session:
        yield session


def dispose_engine() -> None:
    """Cierra el pool si este proceso llego a abrirlo.

    Cloud Run envia SIGTERM al retirar una instancia. Sin esto, las conexiones a Cloud SQL
    quedan abiertas hasta que el motor las recicle. No se crea el engine aqui: los tests
    inyectan la sesion y nunca llaman a `get_engine`, y abrir una conexion solo para
    cerrarla apuntaria a DATABASE_URL del entorno, no a la base de pruebas.
    """
    if get_engine.cache_info().currsize == 0:
        return
    get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
