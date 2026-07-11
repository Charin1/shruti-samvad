"""add bg_music to episode

Revision ID: a4817a03beef
Revises: e6125a03eefb
Create Date: 2026-07-11 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a4817a03beef'
down_revision: Union[str, Sequence[str], None] = 'e6125a03eefb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('episode', sa.Column('bg_music', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('episode', 'bg_music')
