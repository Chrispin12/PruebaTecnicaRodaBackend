"""Contratos HTTP de la solicitud de credito (RF-05)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.domain.applicant import (
    CITY_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    PHONE_MAX_LENGTH,
)
from app.domain.vehicle import VehicleType
from app.schemas.credit_terms import CreditTermsInput

# Se acepta un numero de 7 a 15 digitos con prefijo internacional opcional: cubre fijos y
# celulares colombianos sin excluir un numero extranjero. No se comprueba que exista; eso
# requeriria verificacion por SMS, que no forma parte del alcance. Los separadores (espacios,
# guiones, parentesis) los normaliza el cliente antes de enviar.
PHONE_PATTERN = r"^\+?\d{7,15}$"

# Texto obligatorio: se recortan los espacios y despues se exige contenido, para que una
# cadena de espacios no cuente como nombre.
PersonName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_LENGTH),
]
CityName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=CITY_MAX_LENGTH),
]


class CreditApplicationRequest(CreditTermsInput):
    """Entrada del registro de solicitud.

    Hereda las condiciones de financiacion, incluido `extra="forbid"`: el cliente envia los
    datos del solicitante y lo que quiere financiar, nunca el resultado financiero.

    Las longitudes maximas son las que declara el dominio, las mismas que usan las columnas:
    asi el contrato rechaza con un 422 lo que de otro modo llegaria a PostgreSQL y fallaria por
    longitud de columna.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Laura",
                "last_name": "Gomez",
                "email": "laura.gomez@example.com",
                "phone": "3001234567",
                "city": "Bogota",
                "vehicle_type": "electric_motorcycle",
                "vehicle_value": "8000000.00",
                "down_payment": "2000000.00",
                "term_months": 24,
            }
        }
    )

    first_name: PersonName
    last_name: PersonName
    email: Annotated[EmailStr, StringConstraints(max_length=EMAIL_MAX_LENGTH)]
    phone: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, pattern=PHONE_PATTERN, max_length=PHONE_MAX_LENGTH
        ),
    ]
    city: CityName


class CreditApplicationResponse(BaseModel):
    """Solicitud registrada.

    Se construye desde la fila persistida (`from_attributes`) y no desde el resultado del
    calculo: asi lo que devuelve la API es exactamente lo que quedo almacenado, incluidos el
    identificador y la fecha que genera la base de datos.

    No incluye el plan de pagos: es derivable de estos parametros y el cliente ya lo obtuvo en
    la simulacion. Tampoco expone nada de infraestructura.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime

    first_name: str
    last_name: str
    # `str` y no `EmailStr`: un schema de salida describe lo que se devuelve. Validar el correo
    # otra vez al salir solo convertiria un dato corrupto en la tabla en un error 500.
    email: str
    phone: str
    city: str

    vehicle_type: VehicleType
    vehicle_value: Decimal
    down_payment: Decimal
    financed_amount: Decimal
    term_months: int
    annual_interest_rate: Decimal = Field(
        description="Tasa con la que se calculo esta solicitud, efectiva anual."
    )
    monthly_interest_rate: Decimal
    monthly_payment: Decimal
    total_interest: Decimal
    total_payment: Decimal
