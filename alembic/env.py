"""Entorno de Alembic.

La URL de conexion no se guarda en alembic.ini (no queremos credenciales en el
repositorio): se toma de la configuracion de la aplicacion, es decir de variables de
entorno. Los tests inyectan la URL de la base de pruebas con
`config.set_main_option("sqlalchemy.url", ...)`, que tiene prioridad.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.db.base import Base

# Import por efecto colateral: registra los modelos en Base.metadata para autogenerate.
from app.models import CreditApplication  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    """Genera el SQL de las migraciones sin conectarse a la base de datos."""
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones sobre una conexion real."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Detecta cambios de tipo (por ejemplo precision de NUMERIC), que Alembic
            # ignora por defecto.
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
