import httpx
import trafilatura
from bs4 import BeautifulSoup
from readability import Document
from sqlmodel import select
from uuid import UUID

from core.database.session import async_session_maker
from core.database.models.article import Article
from .feed_fetcher import BROWSER_HEADERS


def _extract_with_readability(html: str) -> str | None:
    try:
        summary_html = Document(html).summary()
        text = BeautifulSoup(summary_html, "lxml").get_text("\n").strip()
        return text or None
    except Exception:
        return None


def _extract_from_raw_html(raw_html: str) -> str | None:
    try:
        text = BeautifulSoup(raw_html, "lxml").get_text("\n").strip()
        return text or None
    except Exception:
        return None


async def extract_content_task(ctx, article_id: UUID):
    """
    Extract clean text content from an article URL.

    We fetch the HTML ourselves with browser-like headers rather than letting
    trafilatura's `fetch_url` do it internally — trafilatura's own fetcher
    sends no real User-Agent, and some sites (confirmed: sebastianraschka.com,
    which serves a stripped-down ~16KB page to it vs. the real ~62KB page a
    browser gets) return a response with no extractable article body at all.

    Falls back to readability-lxml if trafilatura finds nothing in the fetched
    HTML, then to whatever raw_html the feed itself already provided, before
    giving up — so a single extraction failure doesn't leave the article with
    zero text when a usable fallback exists.
    """
    async with async_session_maker() as session:
        article = await session.get(Article, article_id)
        if not article:
            return f"Article {article_id} not found"

        html = None
        try:
            async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=20) as client:
                response = await client.get(article.url)
                response.raise_for_status()
                html = response.text
        except Exception as e:
            print(f"Failed to download {article.url}: {e}")

        clean_text = None
        if html:
            clean_text = trafilatura.extract(html)
            if not clean_text:
                clean_text = _extract_with_readability(html)

        if not clean_text and article.raw_html:
            clean_text = _extract_from_raw_html(article.raw_html)

        if not clean_text:
            return f"Failed to extract any content for {article.url}"

        article.clean_text = clean_text
        session.add(article)
        await session.commit()

        # Enqueue rules engine task
        await ctx['redis'].enqueue_job('run_rules_task', article.id)

    return f"Extracted content for: {article.title}"
