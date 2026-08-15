"""Contrato de error de la API.

Modelado como schema y no como diccionario suelto para que sea la misma definicion la que
usan los manejadores de error en tiempo de ejecucion y la que aparece documentada en OpenAPI.
"""

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Detalle por campo, presente solo en errores de validacion."""

    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
