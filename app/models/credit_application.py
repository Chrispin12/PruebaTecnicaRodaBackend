import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import Money, Rate
from app.domain.applicant import (
    CITY_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PHONE_MAX_LENGTH,
)
from app.domain.rules import MIN_VEHICLE_VALUE_COP
from app.domain.vehicle import VehicleType

VEHICLE_TYPE_MAX_LENGTH = 30

# Valores permitidos derivados del enum: el enum sigue siendo la unica fuente de verdad.
_ALLOWED_VEHICLE_TYPES = ", ".join(f"'{member.value}'" for member in VehicleType)


class CreditApplication(Base):
    """Solicitud de credito registrada (RF-05).

    Guarda en una sola fila los datos del solicitante, la simulacion que acepto, los
    parametros con los que se calculo y el resultado financiero. Los resultados se
    persisten como fotografia: si manana cambia la tasa configurada, las solicitudes ya
    registradas siguen siendo auditables tal como se le mostraron al usuario.
    """

    __tablename__ = "credit_applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Solicitante
    first_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    last_name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    email: Mapped[str] = mapped_column(String(EMAIL_MAX_LENGTH))
    phone: Mapped[str] = mapped_column(String(PHONE_MAX_LENGTH))
    city: Mapped[str] = mapped_column(String(CITY_MAX_LENGTH))

    # Entradas de la simulacion
    vehicle_type: Mapped[VehicleType] = mapped_column(
        # VARCHAR en lugar de un ENUM nativo de PostgreSQL: agregar un tipo de vehiculo es
        # una migracion trivial en vez de un ALTER TYPE. El CHECK que restringe los valores
        # se declara en __table_args__ y no con `create_constraint=True`, porque el que
        # genera el propio tipo Enum es invisible para el autogenerate de Alembic y
        # provocaria migraciones que intentan eliminarlo.
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

    # Parametros con los que se calculo, no configuracion vigente. La tasa anual es el dato
    # contractual; la mensual se guarda porque es la que explica cada linea del plan de pagos,
    # aunque sea derivable de la anual.
    annual_interest_rate: Mapped[Rate]
    monthly_interest_rate: Mapped[Rate]

    # Resultado financiero (RF-02)
    financed_amount: Mapped[Money]
    monthly_payment: Mapped[Money]
    total_interest: Mapped[Money]
    total_payment: Mapped[Money]

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Invariantes del enunciado a nivel de base de datos: aunque la API valide antes,
    # ninguna via de escritura puede dejar la tabla en un estado incoherente.
    # El rango de plazo permitido no se restringe aqui a proposito: es configuracion del
    # dominio y llevarlo al esquema obligaria a migrar para cambiar un parametro.
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
