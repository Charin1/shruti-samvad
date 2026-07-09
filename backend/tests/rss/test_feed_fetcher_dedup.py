"""
Tests for the race-tolerant article insert helper.

Bug this covers: the "SELECT then INSERT" dedup check in fetch_feed_task is a
classic TOCTOU race — confirmed live, overlapping fetch_feed_task runs for
the same feed (from worker restarts/duplicate processes) produced up to 3
duplicate Article rows for the same URL, since each run's SELECT missed the
others' not-yet-committed inserts. The fix adds a DB-level unique constraint
on article.url and wraps each insert in a SAVEPOINT so a losing race raises
IntegrityError scoped to just that insert, not the whole batch.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from services.rss.workers.feed_fetcher import _try_insert_article


class _FakeNestedTransaction:
    def __init__(self, raise_on_flush=None):
        self._raise_on_flush = raise_on_flush

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False  # never swallow — let IntegrityError propagate to the caller's try/except


def make_session(raise_on_flush: Exception | None):
    session = MagicMock()
    session.begin_nested = MagicMock(return_value=_FakeNestedTransaction())
    session.add = MagicMock()

    async def flush():
        if raise_on_flush:
            raise raise_on_flush

    session.flush = AsyncMock(side_effect=flush)
    return session


@pytest.mark.asyncio
async def test_insert_succeeds_when_no_conflict():
    session = make_session(raise_on_flush=None)
    article = MagicMock()
    result = await _try_insert_article(session, article)
    assert result is True
    session.add.assert_called_once_with(article)


@pytest.mark.asyncio
async def test_insert_returns_false_on_unique_constraint_race():
    session = make_session(raise_on_flush=IntegrityError("stmt", "params", Exception("unique violation")))
    article = MagicMock()
    result = await _try_insert_article(session, article)
    assert result is False


@pytest.mark.asyncio
async def test_insert_does_not_swallow_other_exceptions():
    session = make_session(raise_on_flush=RuntimeError("something else broke"))
    article = MagicMock()
    with pytest.raises(RuntimeError):
        await _try_insert_article(session, article)
