"""Dependencias compartidas de la API.

Construye los servicios a partir de la configuracion y de la sesion del request. Es el unico
punto donde se conectan configuracion, base de datos y capa de aplicacion, para que los
servicios no lean variables de entorno ni abran sesiones.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.repositories.credit_application_repository import CreditApplicationRepository
from app.services.credit_application_service import CreditApplicationService
from app.services.credit_calculator import CreditCalculator
from app.services.simulation_service import SimulationService


def get_credit_calculator(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CreditCalculator:
    return CreditCalculator(
        annual_rate=settings.credit_annual_rate,
        max_annual_rate=settings.credit_max_annual_rate,
    )


CreditCalculatorDep = Annotated[CreditCalculator, Depends(get_credit_calculator)]


def get_simulation_service(calculator: CreditCalculatorDep) -> SimulationService:
    return SimulationService(calculator)


def get_credit_application_service(
    calculator: CreditCalculatorDep,
    session: Annotated[Session, Depends(get_session)],
) -> CreditApplicationService:
    return CreditApplicationService(calculator, CreditApplicationRepository(session))


SimulationServiceDep = Annotated[SimulationService, Depends(get_simulation_service)]
CreditApplicationServiceDep = Annotated[
    CreditApplicationService, Depends(get_credit_application_service)
]
