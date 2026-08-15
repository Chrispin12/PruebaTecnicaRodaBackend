from dataclasses import dataclass
from decimal import Decimal

from app.domain.money import quantize_money
from app.domain.vehicle import VehicleType


@dataclass(frozen=True)
class CreditTerms:
    """Condiciones con las que se calcula un credito.

    La tasa forma parte de las condiciones y no se lee de la configuracion aqui dentro: el
    motor debe ser una funcion pura de su entrada, y ademas la solicitud registrada guarda
    la tasa con la que efectivamente se calculo.

    `vehicle_type` no interviene en el calculo (todos los tipos usan la misma tasa) pero
    forma parte de las condiciones cotizadas, asi que viaja con ellas.
    """

    vehicle_type: VehicleType
    vehicle_value: Decimal
    down_payment: Decimal
    term_months: int
    annual_interest_rate: Decimal

    @property
    def financed_amount(self) -> Decimal:
        """Valor financiado: lo que queda del vehiculo despues de la cuota inicial."""
        return quantize_money(self.vehicle_value - self.down_payment)
