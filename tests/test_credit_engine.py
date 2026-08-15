"""Tests del motor de credito.

Los valores esperados estan fijados y fueron calculados de forma independiente al motor, con
una formulacion algebraica distinta de la anuidad y verificados descontando los flujos de
pago a la tasa periodica. No son la salida del motor copiada sobre si misma.

Caso canonico: vehiculo 8.000.000, cuota inicial 2.000.000, 24 meses, 24 % E.A.
"""

from decimal import Decimal

import pytest

from app.core.exceptions import BusinessRuleError
from app.domain.credit_engine import CreditPlan, build_credit_plan
from app.domain.credit_terms import CreditTerms
from app.domain.rules import (
    MAX_TERM_MONTHS,
    MAX_VEHICLE_VALUE_COP,
    MIN_TERM_MONTHS,
    MIN_VEHICLE_VALUE_COP,
)
from app.domain.vehicle import VehicleType

ANNUAL_RATE = Decimal("0.24")
MAX_ANNUAL_RATE = Decimal("0.45")


def build_terms(**overrides: object) -> CreditTerms:
    values: dict[str, object] = {
        "vehicle_type": VehicleType.ELECTRIC_MOTORCYCLE,
        "vehicle_value": Decimal("8000000.00"),
        "down_payment": Decimal("2000000.00"),
        "term_months": 24,
        "annual_interest_rate": ANNUAL_RATE,
    }
    values.update(overrides)
    return CreditTerms(**values)  # type: ignore[arg-type]


def build_plan(max_annual_rate: Decimal = MAX_ANNUAL_RATE, **overrides: object) -> CreditPlan:
    return build_credit_plan(build_terms(**overrides), max_annual_rate=max_annual_rate)


@pytest.fixture
def canonical_plan() -> CreditPlan:
    return build_plan()


class TestCanonicalCase:
    def test_summary_amounts(self, canonical_plan: CreditPlan) -> None:
        assert canonical_plan.financed_amount == Decimal("6000000.00")
        assert canonical_plan.monthly_payment == Decimal("310395.84")
        assert canonical_plan.total_interest == Decimal("1449499.98")
        assert canonical_plan.total_payment == Decimal("7449499.98")

    def test_schedule_has_one_entry_per_installment(self, canonical_plan: CreditPlan) -> None:
        assert len(canonical_plan.schedule) == 24
        assert [entry.installment_number for entry in canonical_plan.schedule] == list(range(1, 25))

    def test_first_installment_breakdown(self, canonical_plan: CreditPlan) -> None:
        first = canonical_plan.schedule[0]

        assert first.payment == Decimal("310395.84")
        assert first.interest == Decimal("108525.49")
        assert first.principal == Decimal("201870.35")
        assert first.remaining_balance == Decimal("5798129.65")

    def test_second_installment_breakdown(self, canonical_plan: CreditPlan) -> None:
        second = canonical_plan.schedule[1]

        assert second.payment == Decimal("310395.84")
        assert second.interest == Decimal("104874.15")
        assert second.principal == Decimal("205521.69")
        assert second.remaining_balance == Decimal("5592607.96")

    def test_last_installment_closes_the_balance(self, canonical_plan: CreditPlan) -> None:
        last = canonical_plan.schedule[-1]

        assert last.payment == Decimal("310395.66")
        assert last.interest == Decimal("5514.56")
        assert last.principal == Decimal("304881.10")
        assert last.remaining_balance == Decimal("0.00")


class TestStructuralInvariants:
    """Propiedades que deben cumplirse en cualquier plan, no solo en el caso canonico."""

    def test_principal_payments_add_up_to_the_financed_amount(
        self, canonical_plan: CreditPlan
    ) -> None:
        principal_total = sum(entry.principal for entry in canonical_plan.schedule)

        assert principal_total == canonical_plan.financed_amount

    def test_totals_are_consistent_with_the_schedule(self, canonical_plan: CreditPlan) -> None:
        assert sum(entry.payment for entry in canonical_plan.schedule) == (
            canonical_plan.total_payment
        )
        assert sum(entry.interest for entry in canonical_plan.schedule) == (
            canonical_plan.total_interest
        )
        assert canonical_plan.total_payment == (
            canonical_plan.financed_amount + canonical_plan.total_interest
        )

    def test_totals_are_not_the_installment_times_the_term(
        self, canonical_plan: CreditPlan
    ) -> None:
        """Multiplicar cuota por plazo daria un total distinto: el residuo va en la ultima."""
        assert canonical_plan.total_payment != canonical_plan.monthly_payment * 24

    def test_interest_decreases_and_principal_increases(self, canonical_plan: CreditPlan) -> None:
        interests = [entry.interest for entry in canonical_plan.schedule]
        principals = [entry.principal for entry in canonical_plan.schedule]

        assert interests == sorted(interests, reverse=True)
        assert principals == sorted(principals)

    def test_every_installment_but_the_last_equals_the_fixed_payment(
        self, canonical_plan: CreditPlan
    ) -> None:
        payments = {entry.payment for entry in canonical_plan.schedule[:-1]}

        assert payments == {canonical_plan.monthly_payment}

    def test_balance_decreases_monotonically_to_zero(self, canonical_plan: CreditPlan) -> None:
        balances = [entry.remaining_balance for entry in canonical_plan.schedule]

        assert balances == sorted(balances, reverse=True)
        assert balances[-1] == Decimal("0.00")

    def test_present_value_of_the_payments_matches_the_financed_amount(
        self, canonical_plan: CreditPlan
    ) -> None:
        """Verificacion independiente de la cuota: descontar los flujos devuelve el capital.

        Se admite hasta un peso de diferencia, que es el residuo de cuantizar la cuota.
        """
        rate = canonical_plan.monthly_interest_rate
        present_value = sum(
            entry.payment / (Decimal(1) + rate) ** entry.installment_number
            for entry in canonical_plan.schedule
        )

        assert abs(present_value - canonical_plan.financed_amount) < Decimal("1.00")

    def test_every_amount_is_a_decimal(self, canonical_plan: CreditPlan) -> None:
        """Ningun importe puede ser float: perderia centavos."""
        amounts = [
            canonical_plan.financed_amount,
            canonical_plan.monthly_payment,
            canonical_plan.total_interest,
            canonical_plan.total_payment,
        ]
        for entry in canonical_plan.schedule:
            amounts.extend(
                [entry.payment, entry.interest, entry.principal, entry.remaining_balance]
            )

        assert all(isinstance(amount, Decimal) for amount in amounts)

    def test_amounts_have_at_most_two_decimals(self, canonical_plan: CreditPlan) -> None:
        for entry in canonical_plan.schedule:
            assert -entry.payment.as_tuple().exponent <= 2
            assert -entry.interest.as_tuple().exponent <= 2
            assert -entry.principal.as_tuple().exponent <= 2
            assert -entry.remaining_balance.as_tuple().exponent <= 2

    def test_the_calculation_is_deterministic(self) -> None:
        assert build_plan() == build_plan()


class TestEdgeCases:
    def test_zero_down_payment_finances_the_whole_vehicle(self) -> None:
        plan = build_plan(down_payment=Decimal("0.00"))

        assert plan.financed_amount == Decimal("8000000.00")
        assert sum(entry.principal for entry in plan.schedule) == Decimal("8000000.00")

    def test_down_payment_below_the_vehicle_value_finances_the_difference(self) -> None:
        plan = build_plan(down_payment=Decimal("1500000.00"))

        assert plan.financed_amount == Decimal("6500000.00")
        assert sum(entry.principal for entry in plan.schedule) == Decimal("6500000.00")

    def test_down_payment_equal_to_the_vehicle_value_is_a_business_error(self) -> None:
        """Regla de negocio, no un CHECK de PostgreSQL: no hay nada que financiar."""
        with pytest.raises(BusinessRuleError, match="monto a financiar"):
            build_plan(down_payment=Decimal("8000000.00"))

    def test_minimum_term_produces_a_single_installment(self) -> None:
        plan = build_plan(
            vehicle_value=Decimal("500000.00"),
            down_payment=Decimal("0.00"),
            term_months=MIN_TERM_MONTHS,
        )

        assert len(plan.schedule) == 1
        assert plan.monthly_payment == Decimal("509043.79")
        assert plan.total_interest == Decimal("9043.79")
        assert plan.schedule[0].principal == Decimal("500000.00")
        assert plan.schedule[0].remaining_balance == Decimal("0.00")

    def test_maximum_term_is_accepted(self) -> None:
        plan = build_plan(term_months=MAX_TERM_MONTHS)

        assert len(plan.schedule) == MAX_TERM_MONTHS
        assert plan.schedule[-1].remaining_balance == Decimal("0.00")
        assert sum(entry.principal for entry in plan.schedule) == plan.financed_amount

    def test_minimum_vehicle_value_is_accepted(self) -> None:
        plan = build_plan(vehicle_value=MIN_VEHICLE_VALUE_COP, down_payment=Decimal("0.00"))

        assert plan.financed_amount == Decimal("500000.00")

    def test_maximum_vehicle_value_is_accepted_and_fits_the_monetary_column(self) -> None:
        """El tope existe para que los totales quepan en NUMERIC(14,2)."""
        plan = build_plan(
            vehicle_value=MAX_VEHICLE_VALUE_COP,
            down_payment=Decimal("0.00"),
            term_months=MAX_TERM_MONTHS,
        )

        assert plan.financed_amount == MAX_VEHICLE_VALUE_COP
        assert plan.total_payment < Decimal("999999999999.99")
        assert plan.schedule[-1].remaining_balance == Decimal("0.00")

    def test_zero_interest_rate_splits_the_capital_evenly(self) -> None:
        plan = build_plan(
            vehicle_value=Decimal("1000000.00"),
            down_payment=Decimal("0.00"),
            term_months=3,
            annual_interest_rate=Decimal("0"),
        )

        assert plan.monthly_payment == Decimal("333333.33")
        assert plan.total_interest == Decimal("0.00")
        assert plan.total_payment == Decimal("1000000.00")
        # El residuo de la division inexacta se cierra en la ultima cuota.
        assert plan.schedule[-1].payment == Decimal("333333.34")
        assert plan.schedule[-1].remaining_balance == Decimal("0.00")

    def test_amounts_with_cents_are_handled_without_losing_money(self) -> None:
        plan = build_plan(
            vehicle_value=Decimal("750000.55"),
            down_payment=Decimal("100000.33"),
            term_months=6,
        )

        assert plan.financed_amount == Decimal("650000.22")
        assert plan.monthly_payment == Decimal("115294.01")
        assert plan.total_interest == Decimal("41763.84")
        assert plan.total_payment == Decimal("691764.06")
        assert sum(entry.principal for entry in plan.schedule) == Decimal("650000.22")
        assert plan.schedule[-1].remaining_balance == Decimal("0.00")


class TestRateLimits:
    def test_rate_below_the_maximum_is_accepted(self) -> None:
        plan = build_plan(annual_interest_rate=Decimal("0.30"))

        assert plan.monthly_interest_rate > Decimal("0")

    def test_rate_equal_to_the_maximum_is_accepted(self) -> None:
        plan = build_plan(annual_interest_rate=MAX_ANNUAL_RATE)

        assert plan.schedule[-1].remaining_balance == Decimal("0.00")

    def test_rate_above_the_maximum_is_rejected(self) -> None:
        with pytest.raises(BusinessRuleError, match="supera la tasa maxima"):
            build_plan(annual_interest_rate=MAX_ANNUAL_RATE + Decimal("0.000001"))

    def test_rejection_message_shows_both_rates_as_percentages(self) -> None:
        with pytest.raises(BusinessRuleError) as error:
            build_plan(annual_interest_rate=Decimal("0.60"))

        assert "60 % E.A." in str(error.value)
        assert "45 % E.A." in str(error.value)

    def test_zero_rate_is_allowed(self) -> None:
        plan = build_plan(annual_interest_rate=Decimal("0"))

        assert plan.total_interest == Decimal("0.00")

    def test_negative_rate_is_rejected(self) -> None:
        with pytest.raises(BusinessRuleError, match="tasa de interes"):
            build_plan(annual_interest_rate=Decimal("-0.01"))


class TestInvalidTerms:
    def test_rejects_vehicle_value_below_the_minimum(self) -> None:
        with pytest.raises(BusinessRuleError, match="valor del vehiculo"):
            build_plan(vehicle_value=Decimal("499999.99"), down_payment=Decimal("0.00"))

    def test_rejects_vehicle_value_above_the_maximum(self) -> None:
        """Sin este tope el plan se calcularia y fallaria al persistir en NUMERIC(14,2)."""
        with pytest.raises(BusinessRuleError, match="no puede superar"):
            build_plan(
                vehicle_value=MAX_VEHICLE_VALUE_COP + Decimal("0.01"),
                down_payment=Decimal("0.00"),
            )

    def test_rejects_down_payment_above_the_vehicle_value(self) -> None:
        with pytest.raises(BusinessRuleError, match="cuota inicial no puede ser mayor"):
            build_plan(down_payment=Decimal("8000001.00"))

    def test_rejects_negative_down_payment(self) -> None:
        with pytest.raises(BusinessRuleError, match="negativa"):
            build_plan(down_payment=Decimal("-1.00"))

    @pytest.mark.parametrize("term_months", [0, -6, MAX_TERM_MONTHS + 1])
    def test_rejects_terms_outside_the_allowed_range(self, term_months: int) -> None:
        with pytest.raises(BusinessRuleError, match="plazo"):
            build_plan(term_months=term_months)

    def test_business_rules_run_before_any_calculation(self) -> None:
        """Los limites se validan antes de construir la tabla, no despues."""
        with pytest.raises(BusinessRuleError):
            build_plan(term_months=10_000)
