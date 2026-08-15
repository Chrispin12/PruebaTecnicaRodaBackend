"""Conversion de tasas de interes.

CONVENCION ASUMIDA EN ESTA PRUEBA
---------------------------------
La tasa configurada se interpreta como **tasa efectiva anual (E.A.)**, expresada en
fraccion decimal (0.24 = 24 % E.A.). Es la convencion con la que se cotiza el credito de
consumo en Colombia.

La tasa efectiva del periodo equivalente se obtiene por capitalizacion compuesta:

    i_p = (1 + i_EA) ** (1 / p) - 1

donde `p` es la cantidad de periodos por anio (12 para cuotas mensuales).

No se usa `i_EA / p`. Esa division corresponde a una tasa **nominal** anual con
capitalizacion periodica, que para el mismo numero cotizado produce una tasa periodica
mayor y por tanto una cuota mas alta. Con 24 % E.A. la diferencia es 1.8088 % mensual
frente a 2.0000 % mensual.

Consecuencia verificable: con p = 12, capitalizar la tasa periodica durante 12 periodos
devuelve exactamente la tasa efectiva anual original.
"""

from decimal import Decimal

from app.domain.money import MONEY_ROUNDING, calculation_context

MONTHLY_PERIODS_PER_YEAR = 12

# Precision con la que una tasa se representa fuera del calculo: al mostrarla y al
# almacenarla. Seis decimales distinguen una milesima de punto porcentual, suficiente para
# auditar la conversion. Es un unico numero para que la API y la base de datos no discrepen.
RATE_DECIMAL_PLACES = 6
RATE_QUANTUM = Decimal("0.000001")


def periodic_rate_from_annual_effective(
    annual_effective_rate: Decimal,
    periods_per_year: int,
) -> Decimal:
    """Convierte una tasa efectiva anual en la tasa efectiva del periodo.

    La tasa devuelta no se redondea: es un factor de calculo, no un importe.
    """
    if periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor que cero.")
    if annual_effective_rate < 0:
        raise ValueError("La tasa efectiva anual no puede ser negativa.")

    # Un credito sin intereses es un caso valido (financiacion a cero) y evita elevar a
    # potencia innecesariamente.
    if annual_effective_rate == 0:
        return Decimal(0)

    with calculation_context():
        exponent = Decimal(1) / Decimal(periods_per_year)
        return (Decimal(1) + annual_effective_rate) ** exponent - Decimal(1)


def quantize_rate(rate: Decimal) -> Decimal:
    """Redondea una tasa a su representacion externa.

    Solo para mostrar o almacenar. El calculo usa la tasa sin redondear: redondearla antes
    de calcular desplazaria la cuota en pesos.
    """
    return rate.quantize(RATE_QUANTUM, rounding=MONEY_ROUNDING)


def format_annual_rate(rate: Decimal) -> str:
    """Formatea una tasa como porcentaje efectivo anual: `24 % E.A.`.

    Se usa el formato fijo y no la representacion por defecto de Decimal, que para valores
    como 100 produce notacion cientifica (`1E+2`).
    """
    percentage = format((rate * 100).normalize(), "f")
    return f"{percentage.replace('.', ',')} % E.A."
