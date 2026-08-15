"""Reglas de negocio del credito.

Unica fuente de verdad de los limites del enunciado y de los supuestos que este no define.
Las reglas se validan aqui, y no solo en Pydantic ni solo con CHECK de PostgreSQL, porque
cada capa protege algo distinto:

* Pydantic protege el contrato de entrada de la API (tipos, formatos, obligatoriedad).
* Los CHECK de PostgreSQL protegen la integridad de la tabla ante cualquier via de
  escritura, incluida una carga manual.
* Estas reglas protegen el dominio: todo el que invoque el motor las cumple, sea la API, un
  script o un test, y el resultado es un error de negocio con mensaje explicable en lugar de
  un IntegrityError o un DataError de la base de datos.
"""

from decimal import Decimal

from app.core.exceptions import BusinessRuleError
from app.domain.credit_terms import CreditTerms
from app.domain.interest import format_annual_rate
from app.domain.money import format_cop

# Enunciado, seccion 6: el valor del vehiculo debe ser mayor o igual a $500.000 COP.
MIN_VEHICLE_VALUE_COP = Decimal("500000")

# El enunciado no fija un maximo. Este tope es una PROTECCION TECNICA DE RANGO, no una
# condicion comercial de Roda: los importes se almacenan en NUMERIC(14,2) y sin tope un valor
# absurdo produciria un plan aparentemente valido que despues fallaria al persistir con un
# DataError opaco de PostgreSQL en lugar de un error de negocio entendible. Mil millones de
# pesos deja margen de sobra frente al precio de una bicicleta o una moto electrica.
MAX_VEHICLE_VALUE_COP = Decimal("1000000000")

# El enunciado no acota el plazo. Se exige que sea positivo (no existe un credito a cero
# cuotas) y se fija un maximo como proteccion de entrada: sin tope, un plazo arbitrario
# generaria una tabla de amortizacion de tamano ilimitado. Supuesto tecnico de la prueba.
MIN_TERM_MONTHS = 1
MAX_TERM_MONTHS = 60


def validate_credit_terms(terms: CreditTerms, max_annual_rate: Decimal) -> None:
    """Valida las precondiciones de negocio del calculo.

    `max_annual_rate` se recibe como parametro y no se lee de la configuracion aqui dentro:
    el dominio no conoce la configuracion de la aplicacion, y el limite es una politica que
    puede variar por modalidad y periodo.

    Lanza `BusinessRuleError` con un mensaje apto para mostrar al usuario final.
    """
    _validate_vehicle_value(terms)
    _validate_down_payment(terms)
    _validate_term(terms)
    _validate_rate(terms.annual_interest_rate, max_annual_rate)


def _validate_vehicle_value(terms: CreditTerms) -> None:
    if terms.vehicle_value < MIN_VEHICLE_VALUE_COP:
        raise BusinessRuleError(
            f"El valor del vehiculo debe ser mayor o igual a {format_cop(MIN_VEHICLE_VALUE_COP)}."
        )

    if terms.vehicle_value > MAX_VEHICLE_VALUE_COP:
        raise BusinessRuleError(
            f"El valor del vehiculo no puede superar {format_cop(MAX_VEHICLE_VALUE_COP)}."
        )


def _validate_down_payment(terms: CreditTerms) -> None:
    if terms.down_payment < 0:
        raise BusinessRuleError("La cuota inicial no puede ser negativa.")

    if terms.down_payment > terms.vehicle_value:
        raise BusinessRuleError("La cuota inicial no puede ser mayor al valor del vehiculo.")

    if terms.financed_amount <= 0:
        raise BusinessRuleError(
            "El monto a financiar debe ser mayor que cero: la cuota inicial cubre el valor "
            "total del vehiculo y no queda nada por financiar."
        )


def _validate_term(terms: CreditTerms) -> None:
    if not MIN_TERM_MONTHS <= terms.term_months <= MAX_TERM_MONTHS:
        raise BusinessRuleError(
            f"El plazo debe estar entre {MIN_TERM_MONTHS} y {MAX_TERM_MONTHS} meses."
        )


def _validate_rate(annual_rate: Decimal, max_annual_rate: Decimal) -> None:
    if annual_rate < 0:
        raise BusinessRuleError("La tasa de interes no puede ser negativa.")

    if annual_rate > max_annual_rate:
        raise BusinessRuleError(
            f"La tasa configurada ({format_annual_rate(annual_rate)}) supera la tasa maxima "
            f"permitida por el sistema ({format_annual_rate(max_annual_rate)})."
        )
