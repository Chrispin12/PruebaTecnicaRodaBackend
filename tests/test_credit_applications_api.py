"""Tests de integracion de POST /api/v1/credit-applications.

Comprueban el flujo completo: contrato, reglas de negocio, recalculo en el servidor y
persistencia real en PostgreSQL. Los valores financieros esperados son los del caso canonico
verificado en los unit tests del motor.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.domain.rules import MAX_TERM_MONTHS
from app.domain.vehicle import VehicleType
from app.main import app
from app.models import CreditApplication

APPLICATIONS_URL = "/api/v1/credit-applications"

EXPECTED_FINANCED_AMOUNT = Decimal("6000000.00")
EXPECTED_MONTHLY_PAYMENT = Decimal("310395.84")
EXPECTED_TOTAL_INTEREST = Decimal("1449499.98")
EXPECTED_TOTAL_PAYMENT = Decimal("7449499.98")
EXPECTED_MONTHLY_RATE = Decimal("0.018088")

APPLICANT_FIELDS = ("first_name", "last_name", "email", "phone", "city")
TERMS_FIELDS = ("vehicle_type", "vehicle_value", "down_payment", "term_months")


def valid_payload(**overrides: object) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "first_name": "Laura",
        "last_name": "Gomez",
        "email": "laura.gomez@example.com",
        "phone": "3001234567",
        "city": "Bogota",
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


def stored_applications(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(CreditApplication)) or 0


class TestSuccessfulRegistration:
    def test_returns_201_with_the_applicant_and_the_credit_summary(
        self, client: TestClient
    ) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload())

        assert response.status_code == 201
        body = response.json()
        assert body["id"]
        assert body["created_at"]
        assert body["first_name"] == "Laura"
        assert body["last_name"] == "Gomez"
        assert body["email"] == "laura.gomez@example.com"
        assert body["phone"] == "3001234567"
        assert body["city"] == "Bogota"
        assert body["vehicle_type"] == "electric_motorcycle"
        assert money(body["financed_amount"]) == EXPECTED_FINANCED_AMOUNT
        assert money(body["monthly_payment"]) == EXPECTED_MONTHLY_PAYMENT
        assert money(body["total_interest"]) == EXPECTED_TOTAL_INTEREST
        assert money(body["total_payment"]) == EXPECTED_TOTAL_PAYMENT
        assert money(body["annual_interest_rate"]) == Decimal("0.24")
        assert money(body["monthly_interest_rate"]) == EXPECTED_MONTHLY_RATE

    def test_response_does_not_leak_infrastructure_or_the_schedule(
        self, client: TestClient
    ) -> None:
        """El plan de pagos es derivable y el cliente ya lo tiene de la simulacion."""
        body = client.post(APPLICATIONS_URL, json=valid_payload()).json()

        assert "schedule" not in body
        assert not [key for key in body if key.startswith("_")]

    def test_created_at_is_timezone_aware_and_recent(self, client: TestClient) -> None:
        body = client.post(APPLICATIONS_URL, json=valid_payload()).json()

        created_at = datetime.fromisoformat(body["created_at"])
        assert created_at.tzinfo is not None
        assert abs((datetime.now(UTC) - created_at).total_seconds()) < 60

    def test_trims_surrounding_whitespace_in_text_fields(self, client: TestClient) -> None:
        response = client.post(
            APPLICATIONS_URL, json=valid_payload(first_name="  Laura  ", city="  Bogota ")
        )

        body = response.json()
        assert body["first_name"] == "Laura"
        assert body["city"] == "Bogota"


class TestPersistence:
    def test_stores_the_application_in_postgresql(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload())

        stored = db_session.get(CreditApplication, response.json()["id"])
        assert stored is not None
        assert stored.first_name == "Laura"
        assert stored.email == "laura.gomez@example.com"
        assert stored.city == "Bogota"
        assert stored.vehicle_type is VehicleType.ELECTRIC_MOTORCYCLE
        assert stored.term_months == 24
        assert stored.created_at is not None

    def test_keeps_the_calculated_financial_values_as_decimal(
        self, client: TestClient, db_session: Session
    ) -> None:
        """La fila conserva el resultado presentado: no se recalcula para reconstruirlo."""
        response = client.post(APPLICATIONS_URL, json=valid_payload())

        stored = db_session.get(CreditApplication, response.json()["id"])
        assert stored is not None
        assert isinstance(stored.monthly_payment, Decimal)
        assert stored.vehicle_value == Decimal("8000000.00")
        assert stored.down_payment == Decimal("2000000.00")
        assert stored.financed_amount == EXPECTED_FINANCED_AMOUNT
        assert stored.monthly_payment == EXPECTED_MONTHLY_PAYMENT
        assert stored.total_interest == EXPECTED_TOTAL_INTEREST
        assert stored.total_payment == EXPECTED_TOTAL_PAYMENT
        assert stored.annual_interest_rate == Decimal("0.24")
        assert stored.monthly_interest_rate == EXPECTED_MONTHLY_RATE

    def test_the_response_matches_what_was_stored(
        self, client: TestClient, db_session: Session
    ) -> None:
        body = client.post(APPLICATIONS_URL, json=valid_payload()).json()

        stored = db_session.get(CreditApplication, body["id"])
        assert stored is not None
        assert money(body["monthly_payment"]) == stored.monthly_payment
        assert money(body["total_payment"]) == stored.total_payment

    def test_a_rejected_application_leaves_no_trace(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = client.post(
            APPLICATIONS_URL, json=valid_payload(vehicle_value="400000", down_payment="0")
        )

        assert response.status_code == 400
        assert stored_applications(db_session) == 0

    def test_rolls_back_and_hides_details_when_persistence_fails(
        self,
        client: TestClient,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """El fallo se provoca en el commit, que es donde puede romperse de verdad.

        Se usa `client` para heredar sus overrides y un TestClient con
        `raise_server_exceptions=False` porque interesa la respuesta que veria el usuario, no
        la excepcion que el TestClient reenvia por defecto.
        """
        commit_attempts: list[str] = []

        def broken_commit() -> None:
            commit_attempts.append("attempted")
            raise SQLAlchemyError("connection reset by peer")

        monkeypatch.setattr(db_session, "commit", broken_commit)

        with TestClient(app, raise_server_exceptions=False) as failing_client:
            response = failing_client.post(APPLICATIONS_URL, json=valid_payload())

        assert commit_attempts, "el test debe fallar al confirmar la transaccion, no antes"
        assert response.status_code == 500
        error = response.json()["error"]
        assert error["code"] == "INTERNAL_ERROR"
        # Ni SQL, ni traceback, ni el mensaje del driver.
        assert "connection reset" not in response.text
        assert "INSERT" not in response.text
        assert stored_applications(db_session) == 0


class TestBusinessRuleErrors:
    @pytest.mark.parametrize(
        ("overrides", "expected_message_fragment"),
        [
            ({"vehicle_value": "400000", "down_payment": "0"}, "valor del vehiculo"),
            ({"down_payment": "8000001.00"}, "cuota inicial no puede ser mayor"),
            ({"down_payment": "8000000.00"}, "monto a financiar"),
            ({"term_months": MAX_TERM_MONTHS + 1}, "plazo"),
        ],
    )
    def test_rejects_terms_that_break_a_business_rule(
        self,
        client: TestClient,
        db_session: Session,
        overrides: dict[str, object],
        expected_message_fragment: str,
    ) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload(**overrides))

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "BUSINESS_RULE_VIOLATION"
        assert expected_message_fragment in error["message"]
        assert stored_applications(db_session) == 0


class TestValidationErrors:
    @pytest.mark.parametrize(
        "invalid_email",
        ["laura.gomez", "laura@", "@example.com", "laura gomez@example.com", ""],
    )
    def test_rejects_an_invalid_email(self, client: TestClient, invalid_email: str) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload(email=invalid_email))

        assert response.status_code == 422
        assert "email" in [detail["field"] for detail in response.json()["error"]["details"]]

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            pytest.param("300123", id="too_short"),
            pytest.param("3001234567890123456", id="too_long"),
            pytest.param("300-123-4567", id="with_separators"),
            pytest.param("celular", id="not_numeric"),
            pytest.param("", id="empty"),
        ],
    )
    def test_rejects_an_invalid_phone(self, client: TestClient, invalid_phone: str) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload(phone=invalid_phone))

        assert response.status_code == 422
        assert "phone" in [detail["field"] for detail in response.json()["error"]["details"]]

    def test_accepts_an_international_prefix(self, client: TestClient) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload(phone="+573001234567"))

        assert response.status_code == 201

    @pytest.mark.parametrize("missing_field", APPLICANT_FIELDS + TERMS_FIELDS)
    def test_rejects_missing_required_fields(self, client: TestClient, missing_field: str) -> None:
        payload = valid_payload()
        del payload[missing_field]

        response = client.post(APPLICATIONS_URL, json=payload)

        assert response.status_code == 422
        fields = [detail["field"] for detail in response.json()["error"]["details"]]
        assert missing_field in fields

    @pytest.mark.parametrize("blank_field", ["first_name", "last_name", "city"])
    def test_rejects_blank_text_fields(self, client: TestClient, blank_field: str) -> None:
        """Solo espacios no es un nombre: se recorta y queda vacio."""
        response = client.post(APPLICATIONS_URL, json=valid_payload(**{blank_field: "   "}))

        assert response.status_code == 422

    def test_rejects_text_longer_than_the_column(self, client: TestClient) -> None:
        """El contrato corta antes: de otro modo el error vendria de PostgreSQL."""
        response = client.post(APPLICATIONS_URL, json=valid_payload(first_name="a" * 200))

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"term_months": 0}, id="term_not_positive"),
            pytest.param({"vehicle_value": "-8000000"}, id="value_negative"),
            pytest.param({"vehicle_value": "8000000.123"}, id="value_with_too_many_decimals"),
            pytest.param({"down_payment": "-1"}, id="down_payment_negative"),
            pytest.param({"vehicle_type": "electric_car"}, id="unsupported_vehicle_type"),
        ],
    )
    def test_rejects_malformed_terms(
        self, client: TestClient, overrides: dict[str, object]
    ) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload(**overrides))

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


class TestCalculationIsServerSide:
    @pytest.mark.parametrize(
        "computed_field",
        [
            "financed_amount",
            "monthly_payment",
            "total_interest",
            "total_payment",
            "annual_interest_rate",
            "monthly_interest_rate",
        ],
    )
    def test_client_cannot_send_financial_values(
        self, client: TestClient, db_session: Session, computed_field: str
    ) -> None:
        response = client.post(APPLICATIONS_URL, json=valid_payload(**{computed_field: "1.00"}))

        assert response.status_code == 422
        fields = [detail["field"] for detail in response.json()["error"]["details"]]
        assert computed_field in fields
        assert stored_applications(db_session) == 0

    def test_the_backend_recalculates_for_every_registration(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Cambiar solo las entradas cambia el resultado almacenado de forma coherente."""
        response = client.post(
            APPLICATIONS_URL,
            json=valid_payload(vehicle_value="5000000", down_payment="1234567.89", term_months=12),
        )

        stored = db_session.get(CreditApplication, response.json()["id"])
        assert stored is not None
        assert stored.financed_amount == Decimal("3765432.11")
        assert stored.total_payment == stored.financed_amount + stored.total_interest
        assert stored.monthly_payment != EXPECTED_MONTHLY_PAYMENT

    def test_the_registration_matches_the_simulation_for_the_same_terms(
        self, client: TestClient
    ) -> None:
        """Simular y solicitar deben calcular igual: comparten el mismo motor."""
        terms = {field: valid_payload()[field] for field in TERMS_FIELDS}

        simulation = client.post("/api/v1/simulations", json=terms).json()
        application = client.post(APPLICATIONS_URL, json=valid_payload()).json()

        for field in ("financed_amount", "monthly_payment", "total_interest", "total_payment"):
            assert money(application[field]) == money(simulation[field])
