"""Caso de uso: simular un credito.

Capa de aplicacion. Traduce el contrato de entrada, delega el calculo y traduce el resultado
al contrato de salida. No conoce HTTP (ni request, ni status codes, ni headers) ni base de
datos: una simulacion no se persiste.
"""

from app.domain.credit_engine import CreditPlan
from app.domain.credit_terms import CreditTerms
from app.domain.interest import quantize_rate
from app.schemas.simulation import (
    AmortizationInstallment,
    SimulationRequest,
    SimulationResponse,
)
from app.services.credit_calculator import CreditCalculator


class SimulationService:
    def __init__(self, calculator: CreditCalculator) -> None:
        self._calculator = calculator

    def simulate(self, request: SimulationRequest) -> SimulationResponse:
        terms, plan = self._calculator.calculate(request)
        return self._build_response(terms, plan)

    @staticmethod
    def _build_response(terms: CreditTerms, plan: CreditPlan) -> SimulationResponse:
        return SimulationResponse(
            vehicle_type=terms.vehicle_type,
            vehicle_value=terms.vehicle_value,
            down_payment=terms.down_payment,
            financed_amount=plan.financed_amount,
            term_months=terms.term_months,
            annual_interest_rate=terms.annual_interest_rate,
            monthly_interest_rate=quantize_rate(plan.monthly_interest_rate),
            monthly_payment=plan.monthly_payment,
            total_interest=plan.total_interest,
            total_payment=plan.total_payment,
            schedule=[
                AmortizationInstallment(
                    installment_number=entry.installment_number,
                    payment=entry.payment,
                    interest=entry.interest,
                    principal=entry.principal,
                    remaining_balance=entry.remaining_balance,
                )
                for entry in plan.schedule
            ],
        )
