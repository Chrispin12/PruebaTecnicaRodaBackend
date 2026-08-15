"""Contrato de las condiciones de financiacion.

Lo comparten la simulacion y la solicitud de credito: son los mismos cuatro datos y deben
validarse igual en los dos endpoints. Se define una vez para que no puedan divergir.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.money import MONEY_DECIMAL_PLACES
from app.domain.vehicle import VehicleType

# Coherente con NUMERIC(14,2), dejando margen para los totales que calcula el backend.
MONEY_MAX_DIGITS = 12


class CreditTermsInput(BaseModel):
    """Datos de la financiacion que el cliente puede enviar.

    Valida unicamente estructura: tipos, obligatoriedad, positividad y numero de decimales.
    Los umbrales de negocio (valor minimo del vehiculo, plazo maximo, tope de tasa) NO se
    validan aqui: viven en `app.domain.rules`, para que cada regla tenga un unico dueno y para
    que se apliquen igual cuando el motor se invoca desde un script o un test.

    `extra="forbid"` es deliberado: la cuota, los intereses, el valor financiado, los totales
    y la tasa los calcula el backend. Si el cliente los envia recibe un 422 en lugar de que el
    campo se descarte en silencio.
    """

    model_config = ConfigDict(extra="forbid")

    vehicle_type: VehicleType = Field(description="Tipo de vehiculo a financiar.")
    vehicle_value: Decimal = Field(
        gt=0,
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        description="Valor del vehiculo en COP.",
    )
    down_payment: Decimal = Field(
        ge=0,
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        description="Cuota inicial en COP. Puede ser cero.",
    )
    term_months: int = Field(gt=0, description="Plazo en meses.")
