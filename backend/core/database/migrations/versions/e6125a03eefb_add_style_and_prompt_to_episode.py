"""add style and prompt to episode

Revision ID: e6125a03eefb
Revises: bca359048d1c
Create Date: 2026-07-11 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'e6125a03eefb'
down_revision: Union[str, Sequence[str], None] = 'bca359048d1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('episode', sa.Column('podcast_style', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='conversational'))
    op.add_column('episode', sa.Column('custom_prompt', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('episode', 'custom_prompt')
    op.drop_column('episode', 'podcast_style')
