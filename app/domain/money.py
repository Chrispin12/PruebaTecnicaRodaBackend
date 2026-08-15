"""Politica monetaria del dominio. Unico lugar donde se define como se redondea dinero.

Reglas:

* Todo importe es `Decimal`. Nunca `float`: en binario 0.1 + 0.2 != 0.3, y un credito no
  puede perder centavos por el tipo de dato elegido.
* Los importes se cuantizan a 2 decimales con ROUND_HALF_UP, el redondeo comercial que el
  usuario espera al ver una cotizacion. No se usa ROUND_HALF_EVEN (redondeo bancario)
  porque redondear 0.005 hacia el par mas cercano resulta contraintuitivo en un importe
  que el cliente lee en pantalla.
* Los valores intermedios NO se redondean: tasas y factores de capitalizacion se calculan
  con precision completa y solo se cuantiza el resultado monetario. Redondear la tasa
  desplazaria la cuota en pesos.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from decimal import ROUND_HALF_UP, Decimal, localcontext

MONEY_DECIMAL_PLACES = 2
MONEY_QUANTUM = Decimal("0.01")
MONEY_ROUNDING = ROUND_HALF_UP

ZERO_MONEY = Decimal("0.00")

# Precision de los calculos intermedios. Se fija de forma explicita para que el resultado
# no dependa del contexto decimal que tenga configurado el proceso que llame al motor.
CALCULATION_PRECISION = 28


def quantize_money(amount: Decimal) -> Decimal:
    """Lleva un importe a centavos aplicando la politica de redondeo del dominio."""
    return amount.quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)


# Marcador temporal para intercambiar separadores sin que el reemplazo se pise a si mismo.
_SEPARATOR_PLACEHOLDER = "\x00"


def format_cop(amount: Decimal) -> str:
    """Formatea un importe en pesos colombianos: `$10.000.000 COP`.

    Convencion colombiana: punto como separador de miles y coma como separador decimal. Los
    centavos se muestran solo si existen, para que un umbral redondo no se lea `$500.000,00`.

    Centralizado aqui para que ningun mensaje de negocio reimplemente el formato ni deje
    escrito el numero como literal, lo que abriria la puerta a que texto y regla se separen.
    """
    quantized = quantize_money(amount)
    has_cents = quantized != quantized.to_integral_value()
    decimals = MONEY_DECIMAL_PLACES if has_cents else 0

    formatted = f"{quantized:,.{decimals}f}"
    formatted = (
        formatted.replace(",", _SEPARATOR_PLACEHOLDER)
        .replace(".", ",")
        .replace(_SEPARATOR_PLACEHOLDER, ".")
    )
    return f"${formatted} COP"


@contextmanager
def calculation_context() -> Iterator[None]:
    """Aisla los calculos en un contexto decimal de precision conocida."""
    with localcontext() as context:
        context.prec = CALCULATION_PRECISION
        yield
