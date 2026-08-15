"""Traduccion de excepciones a respuestas HTTP.

Todas las respuestas de error comparten el mismo sobre:

    {"error": {"code": "...", "message": "...", "details": [...]}}

Un contrato unico permite al frontend manejar errores sin ramificar por endpoint.
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError
from app.schemas.errors import ErrorBody, ErrorDetail, ErrorResponse

logger = logging.getLogger(__name__)

GENERIC_ERROR_MESSAGE = "Ocurrio un error inesperado. Intentalo de nuevo mas tarde."

# Prefijos de `loc` que Pydantic agrega segun el origen del dato y que no aportan al
# cliente: lo relevante es el nombre del campo.
_LOCATION_PREFIXES = frozenset({"body", "query", "path", "header", "cookie"})

_HTTP_ERROR_CODES: dict[int, str] = {
    HTTPStatus.NOT_FOUND: "NOT_FOUND",
    HTTPStatus.METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    HTTPStatus.UNAUTHORIZED: "UNAUTHORIZED",
    HTTPStatus.FORBIDDEN: "FORBIDDEN",
}


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
) -> JSONResponse:
    """Construye el sobre de error a partir del schema, que es el mismo que documenta OpenAPI."""
    payload = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or None))
    return JSONResponse(status_code=status_code, content=payload.model_dump(exclude_none=True))


def _field_path(location: tuple[object, ...]) -> str:
    parts = [str(part) for part in location]
    if parts and parts[0] in _LOCATION_PREFIXES:
        parts = parts[1:]
    return ".".join(parts)


async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    logger.info("Error controlado %s: %s", exc.code, exc.message)
    return error_response(exc.status_code, exc.code, exc.message)


async def _handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    details = [
        ErrorDetail(field=_field_path(error["loc"]), message=error["msg"]) for error in exc.errors()
    ]
    return error_response(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR",
        "Los datos enviados no son validos.",
        details,
    )


async def _handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # Se busca por entero y no con HTTPStatus(...): un codigo no estandar lanzaria
    # ValueError dentro del propio manejador de errores y acabaria en un 500.
    code = _HTTP_ERROR_CODES.get(exc.status_code, "HTTP_ERROR")
    return error_response(exc.status_code, code, str(exc.detail))


async def _handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # El traceback queda en los logs del servidor; el cliente solo recibe un mensaje
    # generico para no filtrar detalles de implementacion.
    logger.exception("Error no controlado", exc_info=exc)
    return error_response(HTTPStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", GENERIC_ERROR_MESSAGE)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_unexpected_error)
