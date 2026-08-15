"""Agregador de rutas de la API.

`/health` queda fuera del prefijo versionado: es una ruta de infraestructura que consultan las
sondas de Cloud Run, no parte del contrato publico que consume el frontend.
"""

from fastapi import APIRouter

from app.api.routes import credit_applications, simulations

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(simulations.router)
api_router.include_router(credit_applications.router)
