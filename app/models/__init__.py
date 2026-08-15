"""Modelos SQLAlchemy.

Se importan aqui para que `Base.metadata` este completo cuando Alembic haga autogenerate.
"""

from app.models.credit_application import CreditApplication

__all__ = ["CreditApplication"]
