from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "production"]

WILDCARD_ORIGIN = "*"


class Settings(BaseSettings):
    """Configuracion de la aplicacion.

    Todos los valores se leen de variables de entorno (o de un .env en desarrollo).
    `database_url` no tiene valor por defecto de forma intencional: la aplicacion debe
    fallar al arrancar si no se configura, en lugar de apuntar a una base implicita.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Roda Credit API"
    app_version: str = "0.1.0"
    environment: Environment = "local"
    log_level: str = "INFO"

    database_url: str

    # Tasa con la que la demo calcula las simulaciones, como fraccion decimal EFECTIVA ANUAL
    # (0.24 = 24 % E.A.). Ver `app.domain.interest` para la conversion a tasa mensual.
    # El enunciado de la prueba no define ninguna tasa: este valor es un SUPUESTO DE DEMO
    # configurable y NO representa la tasa real de Roda ni una condicion comercial suya.
    credit_annual_rate: Decimal = Field(default=Decimal("0.24"), ge=0)

    # Tope maximo de tasa que el sistema acepta, como fraccion decimal EFECTIVA ANUAL.
    # Es configuracion y no una constante del codigo porque los limites regulatorios varian
    # por modalidad de credito y por periodo. El valor por defecto es una REFERENCIA DE DEMO:
    # antes de usarse en produccion debe alinearse con el limite legal vigente aplicable.
    credit_max_annual_rate: Decimal = Field(default=Decimal("0.45"), ge=0)

    # Se recibe como cadena separada por comas porque es el formato natural de una
    # variable de entorno en Cloud Run; `cors_origins` expone la lista ya normalizada.
    cors_allow_origins: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _reject_wildcard_cors_in_production(self) -> "Settings":
        """Impide desplegar la API con CORS abierto a cualquier origen.

        En produccion el unico origen legitimo es el del frontend desplegado. Un comodin
        convierte cualquier pagina de internet en un cliente valido de la API, asi que se
        trata como error de configuracion y no como preferencia: es preferible que el
        despliegue falle de forma visible a que quede publicado y permisivo.
        """
        if self.environment == "production" and WILDCARD_ORIGIN in self.cors_origins:
            raise ValueError(
                "CORS_ALLOW_ORIGINS no puede ser '*' en produccion: indica el origen exacto "
                "del frontend desplegado."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
