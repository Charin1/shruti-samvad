"""
Tests for SQLAlchemy model import order.

Bug: podcast worker imported Article alone, which left Feed unregistered in the
mapper. This caused "Feed not found in Article mapper" at runtime.

Fix: models/__init__.py imports all models in dependency order. This test
verifies that importing from that module resolves both Feed and Article without
a mapper error.
"""


def test_all_models_importable_without_mapper_error():
    """Importing all models must not raise any SQLAlchemy mapper errors."""
    from core.database.models import (
        Feed,
        Article,
        Episode,
        EpisodeArticle,
        JobStatus,
        Folder,
        Tag,
        Rule,
    )
    assert Feed is not None
    assert Article is not None
    assert Episode is not None
    assert EpisodeArticle is not None


def test_article_has_feed_relationship():
    """Article.feed relationship must be resolvable (not a string forward ref)."""
    from core.database.models import Article
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(Article)
    rel_names = [r.key for r in mapper.relationships]
    assert "feed" in rel_names, "Article must have a 'feed' relationship"


def test_feed_has_articles_relationship():
    from core.database.models import Feed
    from sqlalchemy import inspect as sa_inspect

    mapper = sa_inspect(Feed)
    rel_names = [r.key for r in mapper.relationships]
    assert "articles" in rel_names, "Feed must have an 'articles' relationship"
