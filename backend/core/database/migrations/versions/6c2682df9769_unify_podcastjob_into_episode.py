"""unify podcastjob into episode

Revision ID: 6c2682df9769
Revises: fe51cebf59c0
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '6c2682df9769'
down_revision: Union[str, Sequence[str], None] = 'fe51cebf59c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Unifies the single-article `podcastjob` table into a generalized `episode`
    table that can hold 1..N articles via the new `episodearticle` join table.
    Every existing podcastjob becomes a 1-article episode (position=0).
    """
    op.rename_table('podcastjob', 'episode')
    op.add_column('episode', sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('episode', sa.Column('review_requested', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('episode', sa.Column('target_minutes', sa.Float(), nullable=False, server_default='3.0'))

    # Postgres cannot ALTER TYPE ... ADD VALUE inside a transaction block.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'awaiting_review'")

    op.create_table(
        'episodearticle',
        sa.Column('episode_id', sa.Uuid(), nullable=False),
        sa.Column('article_id', sa.Uuid(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(['episode_id'], ['episode.id']),
        sa.ForeignKeyConstraint(['article_id'], ['article.id']),
        sa.PrimaryKeyConstraint('episode_id', 'article_id'),
    )

    # Backfill: every existing episode (former podcastjob) becomes a 1-article episode.
    op.execute(
        """
        INSERT INTO episodearticle (episode_id, article_id, position, summary)
        SELECT id, article_id, 0, summary FROM episode
        """
    )

    # Drop the old article_id FK/index/column now that episodearticle carries it.
    # The constraint name isn't hardcoded in the original migration (Postgres
    # auto-names it), so look it up dynamically instead of guessing.
    op.execute(
        """
        DO $$
        DECLARE
            fk_name text;
        BEGIN
            SELECT conname INTO fk_name
            FROM pg_constraint
            WHERE conrelid = 'episode'::regclass
              AND contype = 'f'
              AND conname LIKE '%article_id%';
            IF fk_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE episode DROP CONSTRAINT %I', fk_name);
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_podcastjob_article_id")
    op.drop_column('episode', 'article_id')


def downgrade() -> None:
    """Downgrade schema.

    Re-adds article_id to episode, backfilled from each episode's first
    (position=0) article, and drops the new multi-article scaffolding.

    Note: Postgres does not support removing a value from an existing enum
    type, so the 'awaiting_review' JobStatus value cannot be cleanly removed
    here — this is a known, documented limitation of this downgrade path.
    """
    op.add_column('episode', sa.Column('article_id', sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE episode e
        SET article_id = ea.article_id
        FROM episodearticle ea
        WHERE ea.episode_id = e.id AND ea.position = 0
        """
    )
    op.alter_column('episode', 'article_id', nullable=False)
    op.create_foreign_key('podcastjob_article_id_fkey', 'episode', 'article', ['article_id'], ['id'])
    op.create_index('ix_podcastjob_article_id', 'episode', ['article_id'], unique=False)

    op.drop_table('episodearticle')
    op.drop_column('episode', 'target_minutes')
    op.drop_column('episode', 'review_requested')
    op.drop_column('episode', 'title')
    op.rename_table('episode', 'podcastjob')
