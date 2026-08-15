"""Verifica que la base de datos, no solo la API, protege las reglas del enunciado.

Si alguien inserta datos por fuera de la API (una carga manual, un script), PostgreSQL
debe seguir rechazando estados imposibles.
"""

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.vehicle import VehicleType
from app.models import CreditApplication, Customer


def build_customer(**overrides: Any) -> Customer:
    values: dict[str, Any] = {
        "first_name": "Laura",
        "last_name": "Gomez",
        "document_type": "cc",
        "document_number": "1023456789",
        "email": "laura.gomez@example.com",
        "phone": "3001234567",
        "city": "Bogota",
    }
    values.update(overrides)
    return Customer(**values)


def build_application(customer: Customer, **overrides: Any) -> CreditApplication:
    values: dict[str, Any] = {
        "customer": customer,
        "vehicle_type": VehicleType.ELECTRIC_MOTORCYCLE,
        "vehicle_value": Decimal("8000000.00"),
        "down_payment": Decimal("2000000.00"),
        "term_months": 24,
        "annual_interest_rate": Decimal("0.240000"),
        "monthly_interest_rate": Decimal("0.018088"),
        "financed_amount": Decimal("6000000.00"),
        "monthly_payment": Decimal("316513.00"),
        "total_interest": Decimal("1596312.00"),
        "total_payment": Decimal("7596312.00"),
    }
    values.update(overrides)
    return CreditApplication(**values)


def test_persists_a_valid_application(db_session: Session) -> None:
    customer = build_customer()
    application = build_application(customer)

    db_session.add(application)
    db_session.commit()

    stored = db_session.get(CreditApplication, application.id)
    assert stored is not None
    assert stored.created_at is not None
    assert stored.customer.email == "laura.gomez@example.com"
    assert stored.vehicle_type is VehicleType.ELECTRIC_MOTORCYCLE


def test_money_columns_round_trip_as_decimal(db_session: Session) -> None:
    """Los importes deben volver como Decimal: un float aqui significaria perder centavos."""
    application = build_application(build_customer(), vehicle_value=Decimal("8000000.55"))

    db_session.add(application)
    db_session.commit()
    db_session.expire_all()

    stored = db_session.get(CreditApplication, application.id)
    assert stored is not None
    assert isinstance(stored.vehicle_value, Decimal)
    assert stored.vehicle_value == Decimal("8000000.55")


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        # La cuota inicial baja tambien, para que el unico CHECK violado sea el minimo.
        (
            {"vehicle_value": Decimal("499999.99"), "down_payment": Decimal("0.00")},
            "vehicle_value_min",
        ),
        (
            {"down_payment": Decimal("9000000.00")},
            "down_payment_not_above_vehicle_value",
        ),
        ({"down_payment": Decimal("-1.00")}, "down_payment_non_negative"),
        ({"term_months": 0}, "term_months_positive"),
        ({"financed_amount": Decimal("0.00")}, "financed_amount_positive"),
        ({"annual_interest_rate": Decimal("-0.010000")}, "annual_interest_rate_non_negative"),
        ({"monthly_interest_rate": Decimal("-0.000001")}, "monthly_interest_rate_non_negative"),
    ],
)
def test_rejects_values_that_violate_business_invariants(
    db_session: Session, overrides: dict[str, Any], constraint: str
) -> None:
    db_session.add(build_application(build_customer(), **overrides))

    with pytest.raises(IntegrityError) as error:
        db_session.commit()

    assert constraint in str(error.value)


def test_rejects_unknown_vehicle_type(db_session: Session) -> None:
    """Se inserta con SQL directo porque el enum de SQLAlchemy filtraria el valor en Python.

    Lo que se comprueba aqui es el CHECK de la base de datos.
    """
    customer = build_customer()
    db_session.add(customer)
    db_session.flush()
    values = {
        "id": "11111111-1111-1111-1111-111111111111",
        "customer_id": str(customer.id),
        "vehicle_type": "gasoline_motorcycle",
        "vehicle_value": Decimal("8000000.00"),
        "down_payment": Decimal("2000000.00"),
        "term_months": 24,
        "annual_interest_rate": Decimal("0.240000"),
        "monthly_interest_rate": Decimal("0.018088"),
        "financed_amount": Decimal("6000000.00"),
        "monthly_payment": Decimal("316513.00"),
        "total_interest": Decimal("1596312.00"),
        "total_payment": Decimal("7596312.00"),
    }
    columns = ", ".join(values)
    placeholders = ", ".join(f":{column}" for column in values)
    statement = text(f"INSERT INTO credit_applications ({columns}) VALUES ({placeholders})")

    with pytest.raises(IntegrityError) as error:
        db_session.execute(statement, values)

    assert "vehicle_type" in str(error.value)
