"""Endpoint de simulacion de credito (RF-01 a RF-04)."""

from http import HTTPStatus

from fastapi import APIRouter

from app.api.dependencies import SimulationServiceDep
from app.schemas.errors import ErrorResponse
from app.schemas.simulation import SimulationRequest, SimulationResponse

router = APIRouter(tags=["simulations"])


@router.post(
    "/simulations",
    response_model=SimulationResponse,
    status_code=HTTPStatus.OK,
    summary="Simula un credito y devuelve el plan de pagos",
    responses={
        HTTPStatus.BAD_REQUEST: {"model": ErrorResponse, "description": "Regla de negocio"},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Datos invalidos"},
    },
)
def create_simulation(
    request: SimulationRequest,
    service: SimulationServiceDep,
) -> SimulationResponse:
    """Calcula la simulacion. No persiste nada: simular no es solicitar un credito.

    Devuelve 200 y no 201 porque no se crea ningun recurso; el POST se usa porque la entrada
    no cabe razonablemente en una query string y no queremos que se cachee.
    """
    return service.simulate(request)
