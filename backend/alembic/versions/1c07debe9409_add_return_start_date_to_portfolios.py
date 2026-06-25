"""add return_start_date to portfolios

Revision ID: 1c07debe9409
Revises: b5e3d8837265
Create Date: 2026-06-25 08:51:21.779346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c07debe9409'
down_revision: Union[str, Sequence[str], None] = 'b5e3d8837265'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "portfolios",
        sa.Column("return_start_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("portfolios", "return_start_date")
