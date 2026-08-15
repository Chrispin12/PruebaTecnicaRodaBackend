"""Motor de credito.

Dominio puro: este modulo no importa FastAPI, SQLAlchemy, PostgreSQL ni nada relacionado
con HTTP. Recibe condiciones, devuelve un plan de credito y puede probarse directamente.

SISTEMA DE AMORTIZACION
-----------------------
Se implementa amortizacion francesa, de cuota fija. Es un SUPUESTO TECNICO de esta prueba:
el enunciado no especifica sistema de amortizacion, y esto no afirma que Roda utilice
necesariamente este sistema.

En amortizacion francesa la cuota es constante; dentro de cada cuota el interes decrece y
el abono a capital crece, porque el interes se liquida sobre el saldo pendiente:

    cuota = P * i / (1 - (1 + i) ** -n)

    P = monto financiado
    i = tasa efectiva del periodo (conversion documentada en `app.domain.interest`)
    n = numero de cuotas

Con i = 0 esa expresion es indeterminada y la cuota es simplemente P / n.

Cambiar de sistema (por ejemplo al aleman, de abono a capital constante) implica sustituir
`_french_installment` y `_build_schedule`. Ni `CreditTerms` ni `CreditPlan` cambian, asi que
services, API y frontend no se ven afectados.

REDONDEO
--------
Cada linea de la tabla se cuantiza a centavos segun la politica de `app.domain.money`. La
diferencia acumulada por redondeo se concentra en la ultima cuota: su abono a capital es
exactamente el saldo pendiente, de modo que el saldo final es 0.00 y la suma de abonos a
capital es exactamente el monto financiado. Como consecuencia la ultima cuota puede diferir
en centavos de las anteriores, y por eso los totales se obtienen sumando la tabla y nunca
multiplicando la cuota por el plazo.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.domain.credit_terms import CreditTerms
from app.domain.interest import MONTHLY_PERIODS_PER_YEAR, periodic_rate_from_annual_effective
from app.domain.money import ZERO_MONEY, calculation_context, quantize_money
from app.domain.rules import validate_credit_terms


@dataclass(frozen=True)
class ScheduleEntry:
    """Una linea del plan de pagos (RF-04)."""

    installment_number: int
    payment: Decimal
    interest: Decimal
    principal: Decimal
    remaining_balance: Decimal


@dataclass(frozen=True)
class CreditPlan:
    """Resultado del calculo (RF-02 y RF-04).

    `monthly_payment` es la cuota fija del plan; la ultima linea de `schedule` puede diferir
    en centavos por el cierre de redondeo.
    """

    financed_amount: Decimal
    monthly_payment: Decimal
    monthly_interest_rate: Decimal
    total_interest: Decimal
    total_payment: Decimal
    schedule: tuple[ScheduleEntry, ...]


def build_credit_plan(terms: CreditTerms, *, max_annual_rate: Decimal) -> CreditPlan:
    """Calcula el plan de credito completo a partir de las condiciones dadas.

    Valida las reglas de negocio antes de calcular, de modo que no existe forma de obtener
    un plan a partir de condiciones invalidas.

    `max_annual_rate` es obligatorio y sin valor por defecto: el limite de tasa es una
    politica configurable y el motor no debe adivinarla.
    """
    validate_credit_terms(terms, max_annual_rate)

    financed_amount = terms.financed_amount
    monthly_rate = periodic_rate_from_annual_effective(
        terms.annual_interest_rate, MONTHLY_PERIODS_PER_YEAR
    )
    installment = _french_installment(financed_amount, monthly_rate, terms.term_months)
    schedule = _build_schedule(financed_amount, monthly_rate, terms.term_months, installment)

    return CreditPlan(
        financed_amount=financed_amount,
        monthly_payment=installment,
        monthly_interest_rate=monthly_rate,
        total_interest=_sum_money(entry.interest for entry in schedule),
        total_payment=_sum_money(entry.payment for entry in schedule),
        schedule=schedule,
    )


def _french_installment(
    financed_amount: Decimal,
    monthly_rate: Decimal,
    term_months: int,
) -> Decimal:
    """Cuota fija del sistema frances."""
    if monthly_rate == 0:
        return quantize_money(financed_amount / term_months)

    with calculation_context():
        discount_factor = Decimal(1) - (Decimal(1) + monthly_rate) ** -term_months
        return quantize_money(financed_amount * monthly_rate / discount_factor)


def _build_schedule(
    financed_amount: Decimal,
    monthly_rate: Decimal,
    term_months: int,
    installment: Decimal,
) -> tuple[ScheduleEntry, ...]:
    """Construye la tabla de amortizacion liquidando el interes sobre el saldo pendiente."""
    entries: list[ScheduleEntry] = []
    balance = financed_amount

    with calculation_context():
        for installment_number in range(1, term_months + 1):
            interest = quantize_money(balance * monthly_rate)

            if installment_number == term_months:
                # La ultima cuota liquida el saldo exacto y absorbe el residuo de redondeo.
                principal = balance
                payment = quantize_money(principal + interest)
            else:
                principal = quantize_money(installment - interest)
                payment = installment

            balance = quantize_money(balance - principal)
            entries.append(
                ScheduleEntry(
                    installment_number=installment_number,
                    payment=payment,
                    interest=interest,
                    principal=principal,
                    remaining_balance=balance,
                )
            )

    return tuple(entries)


def _sum_money(amounts: Iterable[Decimal]) -> Decimal:
    return quantize_money(sum(amounts, ZERO_MONEY))
