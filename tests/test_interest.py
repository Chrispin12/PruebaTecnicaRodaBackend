"""Tests de la conversion de tasa anual efectiva a tasa periodica."""

from decimal import Decimal

import pytest

from app.domain.interest import (
    MONTHLY_PERIODS_PER_YEAR,
    format_annual_rate,
    periodic_rate_from_annual_effective,
)

ANNUAL_EFFECTIVE_RATE = Decimal("0.24")

# (1 + 0.24) ** (1/12) - 1, calculado con precision de 28 digitos.
EXPECTED_MONTHLY_RATE = Decimal("0.018087582483510674531353084")


def test_converts_annual_effective_rate_to_monthly() -> None:
    monthly_rate = periodic_rate_from_annual_effective(
        ANNUAL_EFFECTIVE_RATE, MONTHLY_PERIODS_PER_YEAR
    )

    assert monthly_rate == EXPECTED_MONTHLY_RATE


def test_monthly_rate_capitalized_twelve_times_returns_the_annual_rate() -> None:
    """Propiedad que define la equivalencia de tasas efectivas.

    Es la comprobacion que distingue la conversion compuesta de una simple division.
    """
    monthly_rate = periodic_rate_from_annual_effective(
        ANNUAL_EFFECTIVE_RATE, MONTHLY_PERIODS_PER_YEAR
    )

    capitalized = (Decimal(1) + monthly_rate) ** MONTHLY_PERIODS_PER_YEAR - Decimal(1)

    assert capitalized.quantize(Decimal("0.0000000001")) == ANNUAL_EFFECTIVE_RATE.quantize(
        Decimal("0.0000000001")
    )


def test_monthly_rate_is_lower_than_the_nominal_division() -> None:
    """Documenta la convencion elegida: 24 % E.A. equivale a 1.8088 %, no a 2.0000 %."""
    monthly_rate = periodic_rate_from_annual_effective(
        ANNUAL_EFFECTIVE_RATE, MONTHLY_PERIODS_PER_YEAR
    )

    nominal_division = ANNUAL_EFFECTIVE_RATE / MONTHLY_PERIODS_PER_YEAR

    assert monthly_rate < nominal_division
    assert monthly_rate.quantize(Decimal("0.000001")) == Decimal("0.018088")


def test_zero_annual_rate_yields_zero_periodic_rate() -> None:
    assert periodic_rate_from_annual_effective(Decimal(0), MONTHLY_PERIODS_PER_YEAR) == Decimal(0)


@pytest.mark.parametrize("periods_per_year", [0, -12])
def test_rejects_non_positive_periods_per_year(periods_per_year: int) -> None:
    with pytest.raises(ValueError, match="periods_per_year"):
        periodic_rate_from_annual_effective(ANNUAL_EFFECTIVE_RATE, periods_per_year)


def test_rejects_negative_annual_rate() -> None:
    with pytest.raises(ValueError, match="negativa"):
        periodic_rate_from_annual_effective(Decimal("-0.01"), MONTHLY_PERIODS_PER_YEAR)


@pytest.mark.parametrize(
    ("rate", "expected"),
    [
        (Decimal("0.24"), "24 % E.A."),
        (Decimal("0.45"), "45 % E.A."),
        (Decimal("0.245"), "24,5 % E.A."),
        (Decimal("0"), "0 % E.A."),
        # Decimal representaria 100 como 1E+2 con su formato por defecto.
        (Decimal("1"), "100 % E.A."),
    ],
)
def test_formats_annual_rate_as_a_percentage(rate: Decimal, expected: str) -> None:
    assert format_annual_rate(rate) == expected
