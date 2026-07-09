"""unique constraint on article.url

Revision ID: de7313ad594e
Revises: 6c2682df9769
Create Date: 2026-07-09 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'de7313ad594e'
down_revision: Union[str, Sequence[str], None] = '6c2682df9769'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    The application-level "SELECT then INSERT" dedup check in feed_fetcher.py
    is racy under concurrent/overlapping fetches for the same feed (confirmed
    live: overlapping worker processes produced up to 3 duplicate rows for
    the same URL). A DB-level uniqueness guarantee is the actual fix; the
    app-level check remains as a fast-path to avoid a round-trip exception on
    the common case.
    """
    op.drop_index('ix_article_url', table_name='article')
    op.create_unique_constraint('uq_article_url', 'article', ['url'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_article_url', 'article', type_='unique')
    op.create_index('ix_article_url', 'article', ['url'], unique=False)
