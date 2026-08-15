"""add identity document to customers

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-15 03:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "customers",
        sa.Column("document_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("document_number", sa.String(length=20), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE customers AS customer
            SET
                document_type = 'cc',
                document_number = numbered.document_number
            FROM (
                SELECT
                    id,
                    lpad((1000000000 + row_number() OVER (ORDER BY created_at, id))::text, 10, '0')
                        AS document_number
                FROM customers
            ) AS numbered
            WHERE customer.id = numbered.id
            """
        )
    )
    op.alter_column("customers", "document_type", nullable=False)
    op.alter_column("customers", "document_number", nullable=False)
    op.create_check_constraint(
        "document_type_allowed",
        "customers",
        "document_type IN ('cc', 'ce', 'passport')",
    )
    op.create_unique_constraint(
        "uq_customers_document",
        "customers",
        ["document_type", "document_number"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_customers_document", "customers", type_="unique")
    op.drop_constraint("ck_customers_document_type_allowed", "customers", type_="check")
    op.drop_column("customers", "document_number")
    op.drop_column("customers", "document_type")
