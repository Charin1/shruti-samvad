"""
Tests for the content extraction fallback chain.

Bug this covers: trafilatura's own internal fetcher (trafilatura.fetch_url,
no custom headers) got a stripped-down response from real sites (confirmed
live against sebastianraschka.com: ~16KB vs. the ~62KB a browser-header
request receives), with no extractable article body — causing ~70% of
articles from that feed to end up with clean_text=None. The fix fetches HTML
with browser headers ourselves and falls back through readability-lxml, then
the feed's own raw_html, before giving up.
"""
from services.rss.workers.content_extractor import (
    _extract_with_readability,
    _extract_from_raw_html,
)
from services.rss.workers.feed_fetcher import BROWSER_HEADERS as fetcher_headers
from services.rss.workers.content_extractor import BROWSER_HEADERS as extractor_headers


ARTICLE_HTML = """
<html><head><title>Test Post</title></head>
<body>
<nav>Home About Contact</nav>
<article>
<h1>Understanding Gradient Descent</h1>
<p>Gradient descent is an optimization algorithm used to minimize a loss function.</p>
<p>It works by iteratively moving in the direction of steepest descent.</p>
</article>
<footer>Copyright 2026</footer>
</body></html>
"""


def test_extract_with_readability_parses_article_body():
    text = _extract_with_readability(ARTICLE_HTML)
    assert text is not None
    assert "Gradient descent is an optimization algorithm" in text
    assert "iteratively moving in the direction" in text


def test_extract_with_readability_returns_none_on_empty_input():
    assert _extract_with_readability("") is None


def test_extract_with_readability_returns_none_on_garbage_input():
    assert _extract_with_readability("<html><body></body></html>") is None


def test_extract_from_raw_html_strips_tags_to_plain_text():
    raw = "<p>Article URL: <a href='https://example.com'>https://example.com</a></p><p>Points: 42</p>"
    text = _extract_from_raw_html(raw)
    assert text is not None
    assert "Points: 42" in text
    assert "<p>" not in text


def test_extract_from_raw_html_returns_none_on_empty_input():
    assert _extract_from_raw_html("") is None


def test_content_extractor_reuses_feed_fetcher_browser_headers():
    """Must not duplicate/drift from feed_fetcher's headers — a future header
    tweak there (e.g. UA string bump) should apply here automatically."""
    assert extractor_headers is fetcher_headers
    assert "User-Agent" in extractor_headers
