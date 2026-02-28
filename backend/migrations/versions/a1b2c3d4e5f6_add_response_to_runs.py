"""add_response_to_runs

Revision ID: a1b2c3d4e5f6
Revises: bdf9c29f78a5
Create Date: 2026-02-28 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "bdf9c29f78a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("response", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("runs", "response")
