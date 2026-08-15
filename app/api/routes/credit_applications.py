"""Endpoint de registro de solicitudes de credito (RF-05)."""

from http import HTTPStatus

from fastapi import APIRouter

from app.api.dependencies import CreditApplicationServiceDep
from app.schemas.credit_application import CreditApplicationRequest, CreditApplicationResponse
from app.schemas.errors import ErrorResponse

router = APIRouter(tags=["credit-applications"])


@router.post(
    "/credit-applications",
    response_model=CreditApplicationResponse,
    status_code=HTTPStatus.CREATED,
    summary="Registra una solicitud de credito",
    responses={
        HTTPStatus.BAD_REQUEST: {"model": ErrorResponse, "description": "Regla de negocio"},
        HTTPStatus.UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Datos invalidos"},
    },
)
def create_credit_application(
    request: CreditApplicationRequest,
    service: CreditApplicationServiceDep,
) -> CreditApplicationResponse:
    """Registra la solicitud y devuelve lo que quedo almacenado.

    Devuelve 201 porque aqui si se crea un recurso, a diferencia de la simulacion.
    """
    return service.register(request)
