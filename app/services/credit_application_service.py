"""Caso de uso: registrar una solicitud de credito (RF-05).

Orquesta el flujo completo: recalcula el credito con el motor, persiste el resultado y
devuelve lo almacenado. No conoce HTTP ni SQLAlchemy; el acceso a datos vive en el repositorio.
"""

from app.domain.applicant import Applicant
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
        return CreditApplicationResponse.model_validate(application)

    @staticmethod
    def _build_applicant(request: CreditApplicationRequest) -> Applicant:
        return Applicant(
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone=request.phone,
            city=request.city,
        )
