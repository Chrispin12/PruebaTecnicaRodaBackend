"""Excepciones de aplicacion.

No dependen de FastAPI: los services y el dominio pueden lanzarlas sin acoplarse al
transporte HTTP. La traduccion a respuestas HTTP vive en `app.api.error_handlers`.
"""

from http import HTTPStatus


class AppError(Exception):
    """Error controlado y esperado. Su mensaje es seguro para exponer al cliente."""

    status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BusinessRuleError(AppError):
    """Una regla de negocio no se cumple (por ejemplo, cuota inicial mayor al vehiculo).

    Responde 400 y no 422 para distinguirlo de un error de validacion de esquema: el cuerpo
    de la peticion estaba bien formado, lo que no se cumple es una regla del negocio.
    """

    status_code = HTTPStatus.BAD_REQUEST
    code = "BUSINESS_RULE_VIOLATION"


class NotFoundError(AppError):
    """El recurso solicitado no existe."""

    status_code = HTTPStatus.NOT_FOUND
    code = "NOT_FOUND"


class ServiceUnavailableError(AppError):
    """Una dependencia externa (base de datos) no esta disponible."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "SERVICE_UNAVAILABLE"
