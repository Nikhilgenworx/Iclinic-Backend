"""add user_id to patients table

Revision ID: a1b2c3d4e5f6
Revises: 06dc6fb5628f
Create Date: 2026-06-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "06dc6fb5628f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_unique_constraint("uq_patients_user_id", "patients", ["user_id"])
    op.create_index("ix_patients_user_id", "patients", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_patients_user_id", table_name="patients")
    op.drop_constraint("uq_patients_user_id", "patients", type_="unique")
    op.drop_column("patients", "user_id")
