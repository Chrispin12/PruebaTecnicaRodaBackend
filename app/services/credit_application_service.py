"""Caso de uso: registrar una solicitud de credito (RF-05).

Orquesta el flujo completo: recalcula el credito con el motor, persiste el resultado y
devuelve lo almacenado. No conoce HTTP ni SQLAlchemy; el acceso a datos vive en el repositorio.
"""

from app.domain.applicant import Applicant
from app.models.credit_application import CreditApplication
from app.repositories.credit_application_repository import CreditApplicationRepository
from app.schemas.credit_application import CreditApplicationRequest, CreditApplicationResponse
from app.services.credit_calculator import CreditCalculator


class CreditApplicationService:
    def __init__(
        self,
        calculator: CreditCalculator,
        repository: CreditApplicationRepository,
    ) -> None:
        self._calculator = calculator
        self._repository = repository

    def register(self, request: CreditApplicationRequest) -> CreditApplicationResponse:
        """Registra la solicitud recalculando el credito en el servidor.

        El calculo se repite aqui aunque el usuario venga de simular: los valores financieros
        no se aceptan del cliente, y la tasa que queda registrada es la vigente al momento de
        solicitar.
        """
        terms, plan = self._calculator.calculate(request)
        application = self._repository.create(
            applicant=self._build_applicant(request),
            terms=terms,
            plan=plan,
        )
        return self._to_response(application)

    @staticmethod
    def _to_response(application: CreditApplication) -> CreditApplicationResponse:
        customer = application.customer
        return CreditApplicationResponse(
            id=application.id,
            created_at=application.created_at,
            customer_id=customer.id,
            first_name=customer.first_name,
            last_name=customer.last_name,
            document_type=customer.document_type,
            document_number=customer.document_number,
            email=customer.email,
            phone=customer.phone,
            city=customer.city,
            vehicle_type=application.vehicle_type,
            vehicle_value=application.vehicle_value,
            down_payment=application.down_payment,
            financed_amount=application.financed_amount,
            term_months=application.term_months,
            annual_interest_rate=application.annual_interest_rate,
            monthly_interest_rate=application.monthly_interest_rate,
            monthly_payment=application.monthly_payment,
            total_interest=application.total_interest,
            total_payment=application.total_payment,
        )

    @staticmethod
    def _build_applicant(request: CreditApplicationRequest) -> Applicant:
        return Applicant(
            first_name=request.first_name,
            last_name=request.last_name,
            document_type=request.document_type,
            document_number=request.document_number,
            email=request.email,
            phone=request.phone,
            city=request.city,
        )
