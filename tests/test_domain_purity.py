"""Protege el limite arquitectonico del dominio.

El motor de credito debe poder calcularse y probarse sin framework web, sin ORM y sin base
de datos. Este test falla si alguien introduce esa dependencia en `app/domain`, que es
exactamente la clase de erosion que no se detecta revisando un diff pequeno.
"""

import ast
from pathlib import Path

import pytest

DOMAIN_PACKAGE = Path(__file__).resolve().parents[1] / "app" / "domain"

FORBIDDEN_IMPORT_ROOTS = (
    "fastapi",
    "starlette",
    "sqlalchemy",
    "psycopg",
    "alembic",
    "pydantic",
    "app.db",
    "app.models",
    "app.api",
    "app.core.config",
    # La dependencia va de fuera hacia dentro: los services y los contratos HTTP conocen el
    # dominio, nunca al contrario.
    "app.schemas",
    "app.services",
)


def domain_modules() -> list[Path]:
    return sorted(path for path in DOMAIN_PACKAGE.glob("*.py") if path.name != "__init__.py")


def imported_modules(source: Path) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_domain_package_is_not_empty() -> None:
    """Evita que el test pase por no encontrar archivos que revisar."""
    assert domain_modules()


@pytest.mark.parametrize("module_path", domain_modules(), ids=lambda path: path.name)
def test_domain_module_has_no_infrastructure_dependencies(module_path: Path) -> None:
    forbidden = {
        imported
        for imported in imported_modules(module_path)
        if imported.startswith(FORBIDDEN_IMPORT_ROOTS)
    }

    assert not forbidden, f"{module_path.name} importa infraestructura: {sorted(forbidden)}"
