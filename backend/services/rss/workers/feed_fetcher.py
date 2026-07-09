import feedparser
import httpx
import re
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from typing import List
from urllib.parse import urljoin, urlparse
from uuid import UUID

from core.database.session import async_session_maker
from core.database.models.feed import Feed
from core.database.models.article import Article
from ..logic.deduplication import normalize_url, calculate_content_hash


async def _try_insert_article(session, article: Article) -> bool:
    """
    Insert an article, tolerating a race against another overlapping fetch
    that inserts the same URL concurrently. The caller's "SELECT then insert"
    check above is only a fast-path — the DB's unique constraint on
    article.url is the actual guarantee (confirmed live: overlapping fetches
    for the same feed produced up to 3 duplicate rows for one URL before this
    constraint existed). A SAVEPOINT scopes the failure so it doesn't abort
    the rest of the batch's transaction.
    """
    try:
        async with session.begin_nested():
            session.add(article)
            await session.flush()
        return True
    except IntegrityError:
        return False

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _discover_feed_url(html: str, base_url: str) -> str | None:
    """Return the first RSS/Atom alternate link found in an HTML page, or None."""
    pattern = re.compile(
        r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    pattern2 = re.compile(
        r'<link[^>]+href=["\']([^"\']+)["\'][^>]+type=["\']application/(rss|atom)\+xml["\']',
        re.IGNORECASE,
    )
    m = pattern.search(html) or pattern2.search(html)
    if not m:
        return None
    href = m.group(2) if pattern.search(html) else m.group(1)
    return href if href.startswith("http") else urljoin(base_url, href)


def _parse_human_date(text: str) -> datetime | None:
    """Parse dates like 'Jun 12, 2026' or 'June 12 2026'."""
    m = re.search(r'([A-Za-z]{3,})\s+(\d{1,2}),?\s+(\d{4})', text.strip())
    if not m:
        return None
    month = _MONTH_MAP.get(m.group(1)[:3].lower())
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return None


def _scrape_article_cards(html: str, base_url: str) -> list[dict]:
    """
    Extract article cards from a server-rendered news listing page.
    Returns list of dicts with keys: url, title, published_at, description.
    """
    soup = BeautifulSoup(html, "lxml")
    origin = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(base_url))
    seen_urls: set[str] = set()
    cards: list[dict] = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only follow internal article-like paths (e.g. /news/slug, /blog/slug)
        if not re.match(r'^(/[a-z][a-z0-9-]*/[a-z0-9-]+|https?://)', href):
            continue
        full_url = href if href.startswith("http") else urljoin(origin, href)
        # Skip external links and non-article paths
        parsed = urlparse(full_url)
        if parsed.netloc and parsed.netloc != urlparse(base_url).netloc:
            continue
        if full_url in seen_urls:
            continue

        # Must have a heading inside
        heading = a.find(re.compile(r'^h[1-6]$'))
        if not heading:
            continue

        title = heading.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        # Date from <time> tag or date-like text
        published_at = datetime.now()
        time_tag = a.find("time")
        if time_tag:
            dt_attr = time_tag.get("datetime", "")
            parsed_dt = None
            if dt_attr:
                for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                    try:
                        parsed_dt = datetime.strptime(dt_attr[:19], fmt)
                        break
                    except ValueError:
                        pass
            if not parsed_dt:
                parsed_dt = _parse_human_date(time_tag.get_text())
            if parsed_dt:
                published_at = parsed_dt

        # Description from first <p> inside the card
        desc_tag = a.find("p")
        description = desc_tag.get_text(strip=True) if desc_tag else ""

        seen_urls.add(full_url)
        cards.append({
            "url": full_url,
            "title": title,
            "published_at": published_at,
            "description": description,
        })

    return cards


async def fetch_feed_task(ctx, feed_id: UUID):
    """
    Fetch and parse an RSS feed, then save new articles.
    Falls back to HTML autodiscovery then article-card scraping for pages without RSS.
    """
    async with async_session_maker() as session:
        feed = await session.get(Feed, feed_id)
        if not feed:
            return f"Feed {feed_id} not found"

        async with httpx.AsyncClient(headers=BROWSER_HEADERS, follow_redirects=True, timeout=30) as client:
            try:
                response = await client.get(feed.url)
                response.raise_for_status()
            except Exception as e:
                return f"Failed to fetch feed {feed.url}: {e}"

            content_type = response.headers.get("content-type", "")
            scraped_cards: list[dict] | None = None

            if "html" in content_type:
                discovered = _discover_feed_url(response.text, str(response.url))
                if discovered:
                    try:
                        response = await client.get(discovered)
                        response.raise_for_status()
                    except Exception as e:
                        return f"Discovered feed URL {discovered} could not be fetched: {e}"
                else:
                    # No RSS link — scrape article cards from the HTML listing page
                    scraped_cards = _scrape_article_cards(response.text, str(response.url))

        new_count = 0
        new_articles: List[Article] = []

        if scraped_cards is not None:
            for card in scraped_cards:
                url = normalize_url(card["url"])
                existing = await session.execute(select(Article).where(Article.url == url))
                if existing.scalars().first():
                    continue
                content_hash = calculate_content_hash(card["description"])
                article = Article(
                    feed_id=feed.id,
                    title=card["title"],
                    url=url,
                    published_at=card["published_at"],
                    content_hash=content_hash,
                    raw_html=card["description"] or None,
                )
                if await _try_insert_article(session, article):
                    new_articles.append(article)
                    new_count += 1
        else:
            parsed = feedparser.parse(response.text)
            for entry in parsed.entries:
                url = normalize_url(entry.link)
                existing = await session.execute(select(Article).where(Article.url == url))
                if existing.scalars().first():
                    continue

                published_at = datetime.now()
                if entry.get("published_parsed"):
                    published_at = datetime(*entry.published_parsed[:6])
                elif entry.get("updated_parsed"):
                    published_at = datetime(*entry.updated_parsed[:6])

                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                content_hash = calculate_content_hash(summary)

                raw_html = None
                if hasattr(entry, "content") and entry.content:
                    raw_html = entry.content[0].get("value", "") or None
                raw_html = raw_html or summary or None

                article = Article(
                    feed_id=feed.id,
                    title=entry.title,
                    url=url,
                    published_at=published_at,
                    content_hash=content_hash,
                    raw_html=raw_html,
                )
                if await _try_insert_article(session, article):
                    new_articles.append(article)
                    new_count += 1

        feed.last_fetched_at = datetime.now()
        session.add(feed)
        await session.commit()

        for article in new_articles:
            await ctx["redis"].enqueue_job("extract_content_task", str(article.id))

    return f"Fetched {new_count} new articles for {feed.title}"
