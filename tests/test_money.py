"""Tests de la politica monetaria: cuantizacion y formato colombiano."""

from decimal import Decimal

import pytest

from app.domain.money import format_cop, quantize_money


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("1.005"), Decimal("1.01")),  # ROUND_HALF_UP: el medio centavo sube
        (Decimal("1.004"), Decimal("1.00")),
        (Decimal("2.675"), Decimal("2.68")),  # con float daria 2.67
        (Decimal("0.5"), Decimal("0.50")),
        (Decimal("-1.005"), Decimal("-1.01")),
    ],
)
def test_quantize_money_applies_half_up_rounding(amount: Decimal, expected: Decimal) -> None:
    assert quantize_money(amount) == expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (Decimal("10000000"), "$10.000.000 COP"),
        (Decimal("500000"), "$500.000 COP"),
        (Decimal("1000000000"), "$1.000.000.000 COP"),
        (Decimal("999"), "$999 COP"),
        (Decimal("0"), "$0 COP"),
        # Los centavos se muestran solo si existen, con coma decimal.
        (Decimal("1234.56"), "$1.234,56 COP"),
        (Decimal("8000000.50"), "$8.000.000,50 COP"),
    ],
)
def test_format_cop_uses_colombian_convention(amount: Decimal, expected: str) -> None:
    assert format_cop(amount) == expected


def test_format_cop_never_uses_the_anglo_thousands_separator() -> None:
    formatted = format_cop(Decimal("10000000"))

    assert "," not in formatted
    assert formatted.count(".") == 2
