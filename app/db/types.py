"""Tipos de columna reutilizables.

El dinero se almacena en NUMERIC y se mapea a `decimal.Decimal`. No se usa DOUBLE
PRECISION (perdida de precision) ni el tipo MONEY de PostgreSQL (dependiente del locale
del servidor y engorroso de parsear).
"""

from decimal import Decimal
from typing import Annotated

from sqlalchemy import Numeric
from sqlalchemy.orm import mapped_column

from app.domain.interest import RATE_DECIMAL_PLACES

# Hasta 999.999.999.999,99 COP: mas que suficiente para vehiculos y totales de credito.
MONEY_PRECISION = 14
MONEY_SCALE = 2

# Tasas expresadas en fraccion decimal (0.240000 = 24 % E.A.). La escala la fija el dominio
# para que la tasa almacenada y la que devuelve la API tengan la misma precision.
RATE_PRECISION = 8
RATE_SCALE = RATE_DECIMAL_PLACES

Money = Annotated[Decimal, mapped_column(Numeric(MONEY_PRECISION, MONEY_SCALE))]
Rate = Annotated[Decimal, mapped_column(Numeric(RATE_PRECISION, RATE_SCALE))]
