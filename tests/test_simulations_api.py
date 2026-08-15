"""Tests de integracion de POST /api/v1/simulations.

Los valores esperados son los mismos del caso canonico verificado en los unit tests del motor
(vehiculo 8.000.000, cuota inicial 2.000.000, 24 meses, 24 % E.A.), de modo que estos tests
comprueban tambien que la API no altera el calculo por el camino.
"""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.rules import MAX_TERM_MONTHS, MAX_VEHICLE_VALUE_COP, MIN_VEHICLE_VALUE_COP
from app.models.credit_application import CreditApplication

SIMULATIONS_URL = "/api/v1/simulations"

EXPECTED_FINANCED_AMOUNT = Decimal("6000000.00")
EXPECTED_MONTHLY_PAYMENT = Decimal("310395.84")
EXPECTED_TOTAL_INTEREST = Decimal("1449499.98")
EXPECTED_TOTAL_PAYMENT = Decimal("7449499.98")


def valid_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "vehicle_type": "electric_motorcycle",
        "vehicle_value": "8000000.00",
        "down_payment": "2000000.00",
        "term_months": 24,
    }
    payload.update(overrides)
    return payload


def money(value: object) -> Decimal:
    """Convierte un importe del JSON a Decimal sin pasar por float."""
    return Decimal(str(value))


class TestValidSimulation:
    def test_returns_the_expected_totals(self, client: TestClient) -> None:
        response = client.post(SIMULATIONS_URL, json=valid_payload())

        assert response.status_code == 200
        body = response.json()
        assert money(body["financed_amount"]) == EXPECTED_FINANCED_AMOUNT
        assert money(body["monthly_payment"]) == EXPECTED_MONTHLY_PAYMENT
        assert money(body["total_interest"]) == EXPECTED_TOTAL_INTEREST
        assert money(body["total_payment"]) == EXPECTED_TOTAL_PAYMENT

    def test_echoes_the_inputs_and_the_applied_rate(self, client: TestClient) -> None:
        response = client.post(SIMULATIONS_URL, json=valid_payload())

        body = response.json()
        assert body["vehicle_type"] == "electric_motorcycle"
        assert money(body["vehicle_value"]) == Decimal("8000000.00")
        assert money(body["down_payment"]) == Decimal("2000000.00")
        assert body["term_months"] == 24
        assert money(body["annual_interest_rate"]) == Decimal("0.24")
        assert money(body["monthly_interest_rate"]) == Decimal("0.018088")

    def test_returns_the_full_amortization_schedule(self, client: TestClient) -> None:
        response = client.post(SIMULATIONS_URL, json=valid_payload())

        schedule = response.json()["schedule"]
        assert len(schedule) == 24
        # Los importes viajan como cadenas: Pydantic serializa Decimal sin pasar por float.
        assert schedule[0] == {
            "installment_number": 1,
            "payment": "310395.84",
            "interest": "108525.49",
            "principal": "201870.35",
            "remaining_balance": "5798129.65",
        }
        assert money(schedule[-1]["remaining_balance"]) == Decimal("0.00")

    def test_schedule_is_consistent_with_the_totals(self, client: TestClient) -> None:
        """Si la API reordenara o truncara la tabla, los totales dejarian de cuadrar."""
        body = client.post(SIMULATIONS_URL, json=valid_payload()).json()
        schedule = body["schedule"]

        assert sum(money(item["payment"]) for item in schedule) == money(body["total_payment"])
        assert sum(money(item["interest"]) for item in schedule) == money(body["total_interest"])
        assert sum(money(item["principal"]) for item in schedule) == money(body["financed_amount"])

    def test_accepts_a_zero_down_payment(self, client: TestClient) -> None:
        response = client.post(SIMULATIONS_URL, json=valid_payload(down_payment="0"))

        assert response.status_code == 200
        assert money(response.json()["financed_amount"]) == Decimal("8000000.00")

    def test_accepts_the_boundary_values_of_the_domain(self, client: TestClient) -> None:
        response = client.post(
            SIMULATIONS_URL,
            json=valid_payload(
                vehicle_value=str(MIN_VEHICLE_VALUE_COP),
                down_payment="0",
                term_months=MAX_TERM_MONTHS,
            ),
        )

        assert response.status_code == 200
        assert len(response.json()["schedule"]) == MAX_TERM_MONTHS

    def test_does_not_persist_the_simulation(self, client: TestClient, db_session: Session) -> None:
        """Simular no es solicitar credito: no debe quedar rastro en la base de datos."""
        assert client.post(SIMULATIONS_URL, json=valid_payload()).status_code == 200

        stored = db_session.scalar(select(func.count()).select_from(CreditApplication))
        assert stored == 0


class TestBusinessRuleErrors:
    """Reglas del dominio: la peticion esta bien formada, la operacion no es posible -> 400."""

    @pytest.mark.parametrize(
        ("overrides", "expected_message_fragment"),
        [
            ({"vehicle_value": "499999.99", "down_payment": "0"}, "valor del vehiculo"),
            (
                {
                    "vehicle_value": str(MAX_VEHICLE_VALUE_COP + Decimal("0.01")),
                    "down_payment": "0",
                },
                "no puede superar",
            ),
            ({"down_payment": "8000001.00"}, "cuota inicial no puede ser mayor"),
            ({"down_payment": "8000000.00"}, "monto a financiar"),
            ({"term_months": MAX_TERM_MONTHS + 1}, "plazo"),
        ],
    )
    def test_rejects_terms_that_break_a_business_rule(
        self,
        client: TestClient,
        overrides: dict[str, object],
        expected_message_fragment: str,
    ) -> None:
        response = client.post(SIMULATIONS_URL, json=valid_payload(**overrides))

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "BUSINESS_RULE_VIOLATION"
        assert expected_message_fragment in error["message"]

    def test_error_message_uses_colombian_money_format(self, client: TestClient) -> None:
        response = client.post(
            SIMULATIONS_URL, json=valid_payload(vehicle_value="400000", down_payment="0")
        )

        assert "$500.000 COP" in response.json()["error"]["message"]

    def test_business_errors_do_not_include_field_details(self, client: TestClient) -> None:
        """`details` es para errores de validacion; una regla de negocio no apunta a un campo."""
        response = client.post(SIMULATIONS_URL, json=valid_payload(down_payment="9000000.00"))

        assert "details" not in response.json()["error"]


class TestValidationErrors:
    """Contrato de entrada: la peticion no esta bien formada -> 422."""

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"term_months": 0}, id="term_not_positive"),
            pytest.param({"term_months": -12}, id="term_negative"),
            pytest.param({"term_months": "veinticuatro"}, id="term_not_a_number"),
            pytest.param({"vehicle_value": "0"}, id="value_not_positive"),
            pytest.param({"vehicle_value": "-8000000"}, id="value_negative"),
            pytest.param({"vehicle_value": "8000000.123"}, id="value_with_too_many_decimals"),
            pytest.param({"vehicle_value": "ocho millones"}, id="value_not_a_number"),
            pytest.param({"down_payment": "-1"}, id="down_payment_negative"),
            pytest.param({"vehicle_type": "electric_car"}, id="unsupported_vehicle_type"),
        ],
    )
    def test_rejects_malformed_input(
        self, client: TestClient, overrides: dict[str, object]
    ) -> None:
        response = client.post(SIMULATIONS_URL, json=valid_payload(**overrides))

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["details"]

    @pytest.mark.parametrize(
        "missing_field", ["vehicle_type", "vehicle_value", "down_payment", "term_months"]
    )
    def test_rejects_missing_fields(self, client: TestClient, missing_field: str) -> None:
        payload = valid_payload()
        del payload[missing_field]

        response = client.post(SIMULATIONS_URL, json=payload)

        assert response.status_code == 422
        fields = [detail["field"] for detail in response.json()["error"]["details"]]
        assert missing_field in fields


class TestCalculationIsServerSide:
    @pytest.mark.parametrize(
        "computed_field",
        ["monthly_payment", "total_interest", "financed_amount", "total_payment"],
    )
    def test_client_cannot_send_computed_values(
        self, client: TestClient, computed_field: str
    ) -> None:
        """No se ignoran en silencio: el contrato los rechaza para que el cliente lo sepa."""
        response = client.post(SIMULATIONS_URL, json=valid_payload(**{computed_field: "1.00"}))

        assert response.status_code == 422
        fields = [detail["field"] for detail in response.json()["error"]["details"]]
        assert computed_field in fields

    def test_client_cannot_choose_the_interest_rate(self, client: TestClient) -> None:
        """La tasa es configuracion del servidor, no un dato de entrada."""
        response = client.post(SIMULATIONS_URL, json=valid_payload(annual_interest_rate="0.01"))

        assert response.status_code == 422

    def test_the_backend_recomputes_the_financed_amount(self, client: TestClient) -> None:
        body = client.post(
            SIMULATIONS_URL, json=valid_payload(vehicle_value="5000000", down_payment="1234567.89")
        ).json()

        assert money(body["financed_amount"]) == Decimal("3765432.11")
        assert money(body["total_payment"]) == money(body["financed_amount"]) + money(
            body["total_interest"]
        )


class TestConfiguredRate:
    def test_the_configured_rate_is_the_one_applied(
        self,
        client: TestClient,
        override_rates: Callable[[Decimal, Decimal], None],
    ) -> None:
        override_rates(Decimal("0.30"), Decimal("0.45"))

        body = client.post(SIMULATIONS_URL, json=valid_payload()).json()

        assert money(body["annual_interest_rate"]) == Decimal("0.30")
        assert money(body["monthly_payment"]) > EXPECTED_MONTHLY_PAYMENT

    def test_a_rate_above_the_configured_maximum_is_rejected(
        self,
        client: TestClient,
        override_rates: Callable[[Decimal, Decimal], None],
    ) -> None:
        override_rates(Decimal("0.60"), Decimal("0.45"))

        response = client.post(SIMULATIONS_URL, json=valid_payload())

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "BUSINESS_RULE_VIOLATION"
        assert "supera la tasa maxima" in error["message"]


def test_health_still_works_after_mounting_the_api(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
