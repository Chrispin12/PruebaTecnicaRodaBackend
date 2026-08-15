from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.applicant import (
    CITY_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PHONE_MAX_LENGTH,
)
from app.domain.identity import DOCUMENT_NUMBER_MAX_LENGTH, DocumentType

if TYPE_CHECKING:
    from app.models.credit_application import CreditApplication

_ALLOWED_DOCUMENT_TYPES = ", ".join(f"'{member.value}'" for member in DocumentType)


class Customer(Base):
    """Persona que solicita credito.

    Identidad: documento (tipo + numero) unico. El correo tambien es unico y puede
    actualizarse en solicitudes posteriores de la misma cedula. Nombre, apellido, telefono
    y ciudad quedan fijos desde el primer registro. Un cliente tiene N solicitudes.
    """

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("email", name="uq_customers_email"),
        UniqueConstraint(
            "document_type",
            "document_number",
            name="uq_customers_document",
        ),
        CheckConstraint(
            f"document_type IN ({_ALLOWED_DOCUMENT_TYPES})",
            name="document_type_allowed",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    first_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    last_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            name="document_type",
            native_enum=False,
            length=20,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    document_number: Mapped[str] = mapped_column(String(DOCUMENT_NUMBER_MAX_LENGTH))
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    phone: Mapped[str] = mapped_column(String(PHONE_MAX_LENGTH))
    city: Mapped[str] = mapped_column(String(CITY_MAX_LENGTH))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    credit_applications: Mapped[list[CreditApplication]] = relationship(back_populates="customer")
