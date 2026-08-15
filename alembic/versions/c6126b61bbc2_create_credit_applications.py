"""create credit_applications

Tabla unica de solicitudes: datos del solicitante, entradas de la simulacion, la tasa con
la que se calculo y el resultado financiero. Los CHECK reproducen a nivel de base de datos
las reglas del enunciado que son invariantes del dato.

Revision ID: c6126b61bbc2
Revises:
Create Date: 2026-08-14 11:28:51.156039

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6126b61bbc2"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "credit_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column(
            "vehicle_type",
            sa.Enum(
                "electric_bicycle",
                "electric_motorcycle",
                name="vehicle_type",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("vehicle_value", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("down_payment", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("term_months", sa.Integer(), nullable=False),
        sa.Column("annual_interest_rate", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.Column("financed_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("monthly_payment", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_interest", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_payment", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "vehicle_type IN ('electric_bicycle', 'electric_motorcycle')",
            name=op.f("ck_credit_applications_vehicle_type_allowed"),
        ),
        sa.CheckConstraint(
            "annual_interest_rate >= 0",
            name=op.f("ck_credit_applications_annual_interest_rate_non_negative"),
        ),
        sa.CheckConstraint(
            "down_payment <= vehicle_value",
            name=op.f("ck_credit_applications_down_payment_not_above_vehicle_value"),
        ),
        sa.CheckConstraint(
            "down_payment >= 0", name=op.f("ck_credit_applications_down_payment_non_negative")
        ),
        sa.CheckConstraint(
            "financed_amount > 0", name=op.f("ck_credit_applications_financed_amount_positive")
        ),
        sa.CheckConstraint(
            "monthly_payment >= 0 AND total_interest >= 0 AND total_payment >= 0",
            name=op.f("ck_credit_applications_results_non_negative"),
        ),
        sa.CheckConstraint(
            "term_months > 0", name=op.f("ck_credit_applications_term_months_positive")
        ),
        sa.CheckConstraint(
            "vehicle_value >= 500000", name=op.f("ck_credit_applications_vehicle_value_min")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_applications")),
    )
    op.create_index(
        op.f("ix_credit_applications_created_at"),
        "credit_applications",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_credit_applications_created_at"), table_name="credit_applications")
    op.drop_table("credit_applications")
