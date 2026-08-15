"""customers and customer_id on credit_applications

Separa la identidad del solicitante (customers, email unico) de cada solicitud de credito.
Un cliente puede tener N solicitudes. El vehiculo sigue como snapshot en la solicitud.

Revision ID: a1b2c3d4e5f6
Revises: d4e404922d13
Create Date: 2026-08-15 03:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d4e404922d13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.String(length=80), nullable=False),
        sa.Column("last_name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("email", name="uq_customers_email"),
    )

    op.add_column(
        "credit_applications",
        sa.Column("customer_id", sa.Uuid(), nullable=True),
    )

    op.execute(
        sa.text(
            """
            INSERT INTO customers (id, first_name, last_name, email, phone, city, created_at)
            SELECT gen_random_uuid(), first_name, last_name, lower(email), phone, city, created_at
            FROM (
                SELECT DISTINCT ON (lower(email))
                    first_name, last_name, email, phone, city, created_at
                FROM credit_applications
                ORDER BY lower(email), created_at ASC
            ) AS distinct_applicants
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE credit_applications AS application
            SET customer_id = customer.id
            FROM customers AS customer
            WHERE lower(application.email) = customer.email
            """
        )
    )

    op.alter_column("credit_applications", "customer_id", nullable=False)
    op.create_index(
        op.f("ix_credit_applications_customer_id"),
        "credit_applications",
        ["customer_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_credit_applications_customer_id_customers"),
        "credit_applications",
        "customers",
        ["customer_id"],
        ["id"],
    )
    op.drop_column("credit_applications", "first_name")
    op.drop_column("credit_applications", "last_name")
    op.drop_column("credit_applications", "email")
    op.drop_column("credit_applications", "phone")
    op.drop_column("credit_applications", "city")


def downgrade() -> None:
    op.add_column("credit_applications", sa.Column("city", sa.String(length=80), nullable=True))
    op.add_column("credit_applications", sa.Column("phone", sa.String(length=20), nullable=True))
    op.add_column("credit_applications", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column(
        "credit_applications",
        sa.Column("last_name", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "credit_applications",
        sa.Column("first_name", sa.String(length=80), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE credit_applications AS application
            SET
                first_name = customer.first_name,
                last_name = customer.last_name,
                email = customer.email,
                phone = customer.phone,
                city = customer.city
            FROM customers AS customer
            WHERE application.customer_id = customer.id
            """
        )
    )
    op.alter_column("credit_applications", "first_name", nullable=False)
    op.alter_column("credit_applications", "last_name", nullable=False)
    op.alter_column("credit_applications", "email", nullable=False)
    op.alter_column("credit_applications", "phone", nullable=False)
    op.alter_column("credit_applications", "city", nullable=False)
    op.drop_constraint(
        op.f("fk_credit_applications_customer_id_customers"),
        "credit_applications",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_credit_applications_customer_id"), table_name="credit_applications")
    op.drop_column("credit_applications", "customer_id")
    op.drop_table("customers")
