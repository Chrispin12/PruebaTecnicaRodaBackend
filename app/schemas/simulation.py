"""Contratos HTTP de la simulacion.

Los modelos SQLAlchemy no se usan como contrato de API: el esquema de la tabla y el contrato
publico evolucionan por razones distintas y acoplarlos convierte cualquier cambio de columna
en un cambio incompatible para el cliente.

Nota sobre serializacion: los importes viajan como cadenas ("310395.84"), que es como Pydantic
serializa `Decimal` en JSON. Se mantiene ese comportamiento en lugar de convertirlos a numero
porque un numero JSON pasa por un float de doble precision en cualquier cliente de JavaScript;
como cadena el valor llega exacto y el frontend solo lo formatea para mostrarlo.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.vehicle import VehicleType
from app.schemas.credit_terms import CreditTermsInput


class SimulationRequest(CreditTermsInput):
    """Entrada de la simulacion (RF-01)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vehicle_type": "electric_motorcycle",
                "vehicle_value": "8000000.00",
                "down_payment": "2000000.00",
                "term_months": 24,
            }
        }
    )


class AmortizationInstallment(BaseModel):
    """Una linea del plan de pagos (RF-04)."""

    installment_number: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    remaining_balance: Decimal


class SimulationResponse(BaseModel):
    """Resultado de la simulacion (RF-02, RF-03 y RF-04).

    Repite las entradas para que el frontend pueda renderizar el resumen completo sin
    reconstruirlo desde el formulario, e incluye la tasa efectivamente aplicada.
    """

    vehicle_type: VehicleType
    vehicle_value: Decimal
    down_payment: Decimal
    financed_amount: Decimal
    term_months: int
    annual_interest_rate: Decimal = Field(
        description="Tasa aplicada, efectiva anual en fraccion decimal (0.24 = 24 % E.A.)."
    )
    monthly_interest_rate: Decimal = Field(
        description="Tasa mensual equivalente, informativa. Redondeada para presentacion."
    )
    monthly_payment: Decimal = Field(
        description="Cuota fija del plan. La ultima cuota puede diferir en centavos."
    )
    total_interest: Decimal
    total_payment: Decimal
    schedule: list[AmortizationInstallment]
