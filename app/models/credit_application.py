import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import Money, Rate
from app.domain.rules import MIN_VEHICLE_VALUE_COP
from app.domain.vehicle import VehicleType
from app.models.customer import Customer

VEHICLE_TYPE_MAX_LENGTH = 30

_ALLOWED_VEHICLE_TYPES = ", ".join(f"'{member.value}'" for member in VehicleType)


class CreditApplication(Base):
    """Solicitud de credito (RF-05).

    Pertenece a un `Customer`. El vehiculo va como snapshot (tipo + valor): no hay inventario
    ni placa, asi que no existe entidad Vehicle. Un cliente puede tener N solicitudes.
    """

    __tablename__ = "credit_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"), index=True)
    customer: Mapped[Customer] = relationship(
        back_populates="credit_applications",
        lazy="selectin",
    )

    vehicle_type: Mapped[VehicleType] = mapped_column(
        Enum(
            VehicleType,
            name="vehicle_type",
            native_enum=False,
            length=VEHICLE_TYPE_MAX_LENGTH,
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    vehicle_value: Mapped[Money]
    down_payment: Mapped[Money]
    term_months: Mapped[int]

    annual_interest_rate: Mapped[Rate]
    monthly_interest_rate: Mapped[Rate]

    financed_amount: Mapped[Money]
    monthly_payment: Mapped[Money]
    total_interest: Mapped[Money]
    total_payment: Mapped[Money]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        CheckConstraint(
            f"vehicle_type IN ({_ALLOWED_VEHICLE_TYPES})",
            name="vehicle_type_allowed",
        ),
        CheckConstraint(
            f"vehicle_value >= {MIN_VEHICLE_VALUE_COP}",
            name="vehicle_value_min",
        ),
        CheckConstraint("down_payment >= 0", name="down_payment_non_negative"),
        CheckConstraint(
            "down_payment <= vehicle_value",
            name="down_payment_not_above_vehicle_value",
        ),
        CheckConstraint("term_months > 0", name="term_months_positive"),
        CheckConstraint("financed_amount > 0", name="financed_amount_positive"),
        CheckConstraint("annual_interest_rate >= 0", name="annual_interest_rate_non_negative"),
        CheckConstraint("monthly_interest_rate >= 0", name="monthly_interest_rate_non_negative"),
        CheckConstraint(
            "monthly_payment >= 0 AND total_interest >= 0 AND total_payment >= 0",
            name="results_non_negative",
        ),
    )
