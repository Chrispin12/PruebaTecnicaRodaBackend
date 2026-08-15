"""Aplicacion de la configuracion financiera vigente al motor de credito.

Existe para que la simulacion y el registro de solicitud calculen exactamente igual. Es el
unico lugar donde se decide que tasa se aplica, y por tanto el unico lugar donde queda claro
que la tasa la impone el servidor y no el cliente.
"""

from decimal import Decimal
from typing import NamedTuple

from app.domain.credit_engine import CreditPlan, build_credit_plan
from app.domain.credit_terms import CreditTerms
from app.schemas.credit_terms import CreditTermsInput


class CalculatedCredit(NamedTuple):
    """Condiciones aplicadas y resultado del calculo.

    Se devuelven juntas porque quien construye la respuesta o la fila a persistir necesita
    ambas: las condiciones incluyen la tasa aplicada, que no viene en la entrada.
    """

    terms: CreditTerms
    plan: CreditPlan


class CreditCalculator:
    """Calcula un credito con la configuracion vigente.

    Las tasas se inyectan en el constructor en lugar de leer la configuracion aqui dentro:
    hace explicita la dependencia y permite probar con tasas fijas.
    """

    def __init__(self, *, annual_rate: Decimal, max_annual_rate: Decimal) -> None:
        self._annual_rate = annual_rate
        self._max_annual_rate = max_annual_rate

    def calculate(self, requested_terms: CreditTermsInput) -> CalculatedCredit:
        terms = CreditTerms(
            vehicle_type=requested_terms.vehicle_type,
            vehicle_value=requested_terms.vehicle_value,
            down_payment=requested_terms.down_payment,
            term_months=requested_terms.term_months,
            annual_interest_rate=self._annual_rate,
        )
        plan = build_credit_plan(terms, max_annual_rate=self._max_annual_rate)
        return CalculatedCredit(terms=terms, plan=plan)
